"""Stock research workbench UI components."""
from __future__ import annotations

from datetime import datetime
import re

import pandas as pd
import streamlit as st

from services.alert_engine import evaluate_price_alerts
from services.sector_config import SECTOR_CONFIG, build_sector_view, infer_sector_key
from services.a_share_lists import (
    add_a_share_closed_position,
    add_a_share_watchlist,
    load_a_share_closed_positions,
    load_a_share_watchlist,
    remove_a_share_closed_position,
    remove_a_share_watchlist,
)
from services.a_share_names import load_a_share_names, normalize_a_share_code
from services.a_share_portfolio import load_a_share_positions
from services.closed_positions import add_closed_position, load_closed_positions, remove_closed_position
from services.market_data import get_quotes
from services.portfolio import load_positions
from services.research_store import (
    build_stock_pool,
    load_latest_reports_by_ticker,
    orphan_reports,
)
from services.stock_notes import load_stock_notes, set_stock_note
from services.watchlist import (
    add_to_watchlist,
    load_alert_config,
    load_watchlist,
    remove_from_watchlist,
    ticker_alert_config,
)
_WORKBENCH_CSS = """<style>
.wb-sum{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:12px}
.wb-sm{background:#f7f7f5;border-radius:8px;padding:10px 14px}
.wb-sm .wbv{font-size:22px;font-weight:500;line-height:1.2}
.wb-sm .wbl{font-size:11px;color:#9c9a94;margin-top:3px}
.wb-lgd{display:flex;flex-wrap:wrap;gap:8px;padding:0 0 8px;font-size:11px;color:#9c9a94;align-items:center}
.ldot{width:7px;height:7px;border-radius:50%;display:inline-block;margin-right:3px;vertical-align:middle}
.lgd-tip{padding:1px 8px;border:0.5px solid #ccc9c2;border-radius:4px;color:#6b6a66}
.wb-strgs{display:flex;flex-wrap:wrap;gap:4px;margin-bottom:8px}
.wb-strg{font-size:11px;padding:2px 8px;border-radius:6px;border:0.5px solid #e5e3de;color:#6b6a66;background:#fff}
.wb-tbl{width:100%;border-collapse:collapse;font-size:12px}
.wb-tbl th{font-size:10px;font-weight:500;letter-spacing:.04em;color:#9c9a94;padding:3px 8px;border-bottom:0.5px solid #e5e3de;white-space:nowrap;text-transform:uppercase}
.wb-tbl td{padding:5px 8px;border-bottom:0.5px solid #e5e3de;vertical-align:middle}
.wb-tk{font-size:13px;font-weight:500;line-height:1.2}
.wb-sc{font-size:10px;color:#9c9a94;margin-top:2px}
.wb-sc b{color:#6b6a66;font-weight:500}
.wb-pv{font-size:13px;font-weight:500}
.wb-bdg{display:inline-block;font-size:10px;padding:2px 7px;border-radius:5px;font-weight:500;white-space:nowrap}
.bdg-G{background:#E1F5EE;color:#085041}
.bdg-T{background:#E1F5EE;color:#0F6E56}
.bdg-A{background:#FEF0DC;color:#633806}
.bdg-R{background:#FDEAEA;color:#791F1F}
.bdg-B{background:#E4EEF9;color:#0C447C}
.bdg-P{background:#EEEDFE;color:#3C3489}
.bdg-N{background:#f7f7f5;color:#6b6a66}
.wb-nobar{font-size:11px;color:#9c9a94}
.bw{position:relative;width:100%;height:7px;border-radius:3px;border:0.5px solid #e5e3de;background:#f7f7f5}
.bzone{position:absolute;height:100%;border-radius:2px;top:0}
.bline{position:absolute;width:1.5px;height:100%;top:0}
.bdot{position:absolute;width:9px;height:9px;border-radius:50%;top:-1px;border:1.5px solid #fff;transform:translateX(-50%);z-index:2}
.wb-earv{font-size:12px;font-weight:500;white-space:nowrap}
.wb-earsub{font-size:10px;margin-top:1px;white-space:nowrap}
.wb-ti{display:flex;flex-wrap:wrap;gap:4px;padding:6px 10px;align-items:center}
.wb-tc{font-size:10px;padding:2px 8px;border-radius:5px;border:0.5px solid #e5e3de;color:#6b6a66;background:#fff}
.wb-tca{border-color:#BA7517!important;color:#633806!important;background:#FEF0DC!important}
.wb-tcsrc{font-size:10px;color:#9c9a94;margin-left:6px;flex-shrink:0}
.wb-trow td{background:#f7f7f5!important;border-bottom:0.5px solid #e5e3de;padding:0}
.hot-buy td{background:rgba(29,158,117,.05)!important}
.hot-trim td{background:rgba(186,117,23,.05)!important}
</style>"""

_ACTION_MAP = [
    ("buy_now",        "立即买入", "G"),
    ("buy_on_pullback","回调买入", "T"),
    ("small_probe",    "小仓试探", "T"),
    ("hold_no_add",    "持有不加", "B"),
    ("hold",           "持有",     "B"),
    ("watch",          "观察",     "P"),
    ("trim",           "减仓",     "A"),
    ("avoid",          "回避",     "R"),
]


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _row_sector(row: dict) -> str:
    report = row.get("report")
    if not report:
        return "oth"
    sector_raw = str(report.analysis.get("sector") or "")
    return sector_raw if sector_raw in SECTOR_CONFIG else infer_sector_key(sector_raw)


def _row_hot_level(row: dict) -> int:
    pp = row.get("price_plan") or {}
    price = _to_float(row.get("current_price"))
    if price is None:
        return 0
    hs = _to_float(pp.get("hard_stop"))
    iv = _to_float(pp.get("invalid_price"))
    if hs and price <= hs:
        return 3
    if iv and price <= iv:
        return 2
    tl = _zone_bound(pp.get("trim_zone"), 0)
    if tl and price >= tl:
        return 2
    bu = _zone_bound(pp.get("buy_zone"), 1)
    bl = _zone_bound(pp.get("buy_zone"), 0)
    if bu and price <= bu:
        return 1
    if bl and price < bl and (bl - price) / bl <= 0.05:
        return 1
    return 0


def _row_status(row: dict) -> tuple[str, str]:
    pp = row.get("price_plan") or {}
    price = _to_float(row.get("current_price"))
    bz = pp.get("buy_zone")
    if not bz or price is None:
        return "待分析", "N"
    hs = _to_float(pp.get("hard_stop"))
    iv = _to_float(pp.get("invalid_price"))
    tl = _zone_bound(pp.get("trim_zone"), 0)
    bl = _zone_bound(bz, 0)
    bu = _zone_bound(bz, 1)
    if hs and price <= hs:
        return "硬止损", "R"
    if iv and price <= iv:
        return "失效区间", "R"
    if tl and price >= tl:
        return "减仓触发", "A"
    if bl and bu and bl <= price <= bu:
        return "买入区 ✓", "T"
    if bl and price < bl and (bl - price) / bl <= 0.05:
        return "接近买入", "G"
    if bu and price > bu:
        return "持有中", "B"
    return "等待机会", "N"


def _action_badge(action: str) -> str:
    if not action or action in ("-", ""):
        return '<span style="font-size:11px;color:#9c9a94">—</span>'
    label, css = action, "N"
    for key, lbl, cls in _ACTION_MAP:
        if key in action:
            label = action.replace(key, lbl)
            css = cls
            break
    return f'<span class="wb-bdg bdg-{css}">{_esc(label.replace("/", " / "))}</span>'


def _pn(v) -> str:
    """Compact price number: integer if ≥100, one decimal otherwise."""
    f = _to_float(v)
    if f is None:
        return "?"
    return str(int(round(f))) if f >= 100 else f"{f:.1f}"


def _price_bar_html(pp: dict, cur_price) -> str:
    price = _to_float(cur_price)
    bl = _zone_bound(pp.get("buy_zone"), 0)
    bh = _zone_bound(pp.get("buy_zone"), 1)
    tl = _zone_bound(pp.get("trim_zone"), 0)
    th = _zone_bound(pp.get("trim_zone"), 1)
    hs = _to_float(pp.get("hard_stop"))
    iv = _to_float(pp.get("invalid_price"))

    # Number row: always built from whatever data is available
    num_parts = []
    if bl and bh:
        num_parts.append(f'<span style="color:#1D9E75;font-weight:500">买 {_pn(bl)}–{_pn(bh)}</span>')
    if tl and th:
        num_parts.append(f'<span style="color:#BA7517;font-weight:500">减 {_pn(tl)}–{_pn(th)}</span>')
    if iv:
        num_parts.append(f'<span style="color:#9c9a94">失效 {_pn(iv)}</span>')
    num_html = (
        '<div style="font-size:10px;margin-top:3px;display:flex;gap:8px;flex-wrap:wrap">'
        + "".join(num_parts)
        + "</div>"
    ) if num_parts else ""

    fallback = num_html or '<span class="wb-nobar">—</span>'
    if not (bl and th and hs):
        return f'<div>{fallback}</div>'

    lo, hi = hs * 0.87, th * 1.14
    r = hi - lo
    if r <= 0:
        return f'<div>{fallback}</div>'

    def pct(v: float) -> float:
        return max(0.0, min(100.0, (v - lo) / r * 100))

    bw = max(pct(bh) - pct(bl), 0.8) if bh else 0.0
    tw = (pct(th) - pct(tl)) if (th and tl) else 0.0
    dot = ""
    if price is not None:
        if tl and price >= tl:
            dc = "#BA7517"
        elif bl and bh and bl <= price <= bh:
            dc = "#1D9E75"
        elif iv and price <= iv:
            dc = "#E24B4A"
        elif bl and price < bl and (bl - price) / bl <= 0.05:
            dc = "#5DCAA5"
        else:
            dc = "#888880"
        dot = f'<div class="bdot" style="left:{pct(price):.1f}%;background:{dc}"></div>'
    bar = (
        f'<div class="bw">'
        f'<div class="bzone" style="left:{pct(bl):.1f}%;width:{bw:.1f}%;background:#9FE1CB"></div>'
        f'<div class="bzone" style="left:{pct(tl or bl):.1f}%;width:{tw:.1f}%;background:#FAC775"></div>'
        f'<div class="bline" style="left:{pct(hs):.1f}%;background:#E24B4A;opacity:.5"></div>'
        f'{dot}'
        f'</div>'
    )
    return f'<div>{bar}{num_html}</div>'


def _extract_ea_date(analysis: dict) -> str | None:
    """Return the raw earnings window string (may be ISO date or quarter estimate)."""
    for key in ("earnings_date", "next_earnings_date"):
        v = analysis.get(key)
        if v:
            return str(v).strip()
    for cat in (analysis.get("catalysts") or []):
        if not isinstance(cat, dict):
            continue
        ev = str(cat.get("event") or "").lower()
        if any(k in ev for k in ("earning", "财报")):
            d = cat.get("expected_window") or cat.get("date")
            if d:
                return str(d).strip()
    return None


def _earnings_cell_html(analysis: dict) -> str:
    ea_str = _extract_ea_date(analysis)
    if not ea_str or ea_str.lower() in ("quarterly", "tbd", "n/a", ""):
        return '<span style="font-size:10px;color:#9c9a94">—</span>'

    # Try exact date prefix (e.g. "2026-05-27 after market close")
    iso_m = re.match(r"(\d{4}-\d{2}-\d{2})", ea_str)
    if iso_m:
        try:
            from datetime import date as _date
            ea = _date.fromisoformat(iso_m.group(1))
            days = (ea - _date.today()).days
            if days < 0:
                return '<span style="font-size:10px;color:#9c9a94">已过</span>'
            color = "#C0282A" if days <= 14 else "#915410" if days <= 35 else "#9c9a94"
            return (
                f'<div class="wb-earv" style="color:{color}">{ea.strftime("%b")} {ea.day}</div>'
                f'<div class="wb-earsub" style="color:{color}">{days}天后</div>'
            )
        except (ValueError, TypeError):
            pass

    # Quarter estimate: "2026-Q2", "2026-Q2 / likely August 2026", "FY2026 Q4"
    q_m = re.search(r"Q([1-4])", ea_str, re.IGNORECASE)
    yr_m = re.search(r"(20\d{2})", ea_str)
    if q_m:
        label = (f"{yr_m.group(1)} " if yr_m else "") + f"Q{q_m.group(1)}"
        return f'<div class="wb-earsub" style="color:#9c9a94">~{label}</div>'

    # Month name estimate: "2026-May", "likely July-August 2026"
    mo_m = re.search(r"(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", ea_str, re.IGNORECASE)
    if mo_m:
        label = (f"{yr_m.group(1)} " if yr_m else "") + mo_m.group(1)[:3].capitalize()
        return f'<div class="wb-earsub" style="color:#9c9a94">~{label}</div>'

    return '<span style="font-size:10px;color:#9c9a94">—</span>'


def _row_earnings_within(row: dict, max_days: int) -> bool:
    report = row.get("report")
    if not report:
        return False
    ea_str = _extract_ea_date(report.analysis)
    if not ea_str:
        return False
    iso_m = re.match(r"(\d{4}-\d{2}-\d{2})", ea_str)
    if not iso_m:
        return False
    try:
        from datetime import date as _date
        d = (_date.fromisoformat(iso_m.group(1)) - _date.today()).days
        return 0 <= d <= max_days
    except (ValueError, TypeError):
        return False


def _sort_by_hot(rows: list[dict]) -> list[dict]:
    def key(r: dict):
        hot = _row_hot_level(r)
        ea = 9999
        report = r.get("report")
        if report:
            ea_str = _extract_ea_date(report.analysis)
            if ea_str:
                try:
                    from datetime import date as _date
                    d = (_date.fromisoformat(ea_str) - _date.today()).days
                    if d >= 0:
                        ea = d
                except (ValueError, TypeError):
                    pass
        return (-hot, ea, r["symbol"])
    return sorted(rows, key=key)


def _price_css_color(cur_price, pp: dict) -> str:
    price = _to_float(cur_price)
    if price is None:
        return ""
    tl = _zone_bound(pp.get("trim_zone"), 0)
    bl = _zone_bound(pp.get("buy_zone"), 0)
    bh = _zone_bound(pp.get("buy_zone"), 1)
    iv = _to_float(pp.get("invalid_price"))
    if tl and price >= tl:
        return "color:#BA7517"
    if bl and bh and bl <= price <= bh:
        return "color:#1D9E75"
    if iv and price <= iv:
        return "color:#C0282A"
    return ""


def _sector_table_html(rows: list[dict]) -> str:
    html = (
        '<table class="wb-tbl">'
        '<thead><tr>'
        '<th style="width:12%">标的</th>'
        '<th style="width:10%">当前价</th>'
        '<th style="width:11%">动作</th>'
        '<th style="width:22%">价格区间</th>'
        '<th style="width:11%">状态</th>'
        '<th style="width:10%">下次财报</th>'
        '<th style="width:10%">分析日</th>'
        '<th style="width:14%">备注</th>'
        '</tr></thead><tbody>'
    )
    for row in rows:
        report = row.get("report")
        analysis = report.analysis if report else {}
        pp = row.get("price_plan") or {}
        cur = row.get("current_price")
        scores = analysis.get("scores") or {}
        shufen_s = analysis.get("shufen_scores") or {}
        xscore = scores.get("xiaoyan") if "xiaoyan" in scores else scores.get("total_score")
        sscore = shufen_s.get("total_score") or scores.get("shufen")
        triggers = analysis.get("watch_triggers") or []
        hot = _row_hot_level(row)
        row_cls = "hot-trim" if hot >= 2 else "hot-buy" if hot == 1 else ""

        parts = []
        if xscore is not None:
            parts.append(f"X<b>{xscore}</b>")
        if sscore is not None:
            parts.append(f"S<b>{sscore}</b>")
        score_html = " · ".join(parts) or '<span style="color:#9c9a94">待分析</span>'

        pcolor = _price_css_color(cur, pp)
        pstr = _fmt_price(cur) if cur else "—"
        slabel, scls = _row_status(row)
        adate = _short_date(row.get("analysis_updated_at"))
        note = _esc(row.get("note") or "")
        note_html = (
            f'<span style="font-size:11px;color:#6b6a66">{note}</span>'
            if note else
            '<span style="font-size:11px;color:#9c9a94">—</span>'
        )

        html += (
            f'<tr class="{row_cls}">'
            f'<td><div class="wb-tk">{_esc(row["symbol"])}</div>'
            f'<div class="wb-sc">{score_html}</div></td>'
            f'<td><span class="wb-pv" style="{pcolor}">{pstr}</span></td>'
            f'<td>{_action_badge(row.get("action") or "")}</td>'
            f'<td style="padding-right:14px">{_price_bar_html(pp, cur)}</td>'
            f'<td><span class="wb-bdg bdg-{scls}">{slabel}</span></td>'
            f'<td>{_earnings_cell_html(analysis)}</td>'
            f'<td><span style="font-size:10px;color:#9c9a94">{adate}</span></td>'
            f'<td>{note_html}</td>'
            f'</tr>'
        )
        if triggers:
            chips = "".join(
                f'<span class="wb-tc{" wb-tca" if t.startswith("⚠️") else ""}">{_esc(t)}</span>'
                for t in triggers
            )
            html += (
                f'<tr class="wb-trow"><td colspan="8">'
                f'<div class="wb-ti">{chips}'
                f'<span class="wb-tcsrc">watch_triggers</span>'
                f'</div></td></tr>'
            )
    html += "</tbody></table>"
    return html


def _render_us_pool_sector_grouped(title: str, rows: list[dict]) -> None:
    """Render US pool rows grouped by sector with collapsible headers and price bars."""
    st.subheader(title)
    if not rows:
        st.info("暂无数据。")
        return

    st.markdown(_WORKBENCH_CSS, unsafe_allow_html=True)

    total = len(rows)
    buy_n = sum(1 for r in rows if _row_hot_level(r) == 1)
    trim_n = sum(1 for r in rows if _row_hot_level(r) >= 2)
    ear_n = sum(1 for r in rows if _row_earnings_within(r, 35))
    st.markdown(
        f'<div class="wb-sum">'
        f'<div class="wb-sm"><div class="wbv">{total}</div><div class="wbl">总个股</div></div>'
        f'<div class="wb-sm"><div class="wbv" style="color:#0F6E56">{buy_n}</div><div class="wbl">买入触发</div></div>'
        f'<div class="wb-sm"><div class="wbv" style="color:#915410">{trim_n}</div><div class="wbl">减仓触发</div></div>'
        f'<div class="wb-sm"><div class="wbv" style="color:#0C447C">{ear_n}</div><div class="wbl">35天内财报</div></div>'
        f'</div>'
        f'<div class="wb-lgd">'
        f'<span><span class="ldot" style="background:#1D9E75"></span>买入区</span>'
        f'<span><span class="ldot" style="background:#5DCAA5"></span>接近买入</span>'
        f'<span><span class="ldot" style="background:#BA7517"></span>减仓区</span>'
        f'<span><span class="ldot" style="background:#444444"></span>止损/失效</span>'
        f'<span class="lgd-tip">⚡ 条件内嵌展示</span>'
        f'</div>',
        unsafe_allow_html=True,
    )

    for sk in ["bio", "nuc", "tech", "mat", "ind", "oth"]:
        sector_rows = [r for r in rows if _row_sector(r) == sk]
        if not sector_rows:
            continue
        cfg = SECTOR_CONFIG[sk]
        hot_n = sum(1 for r in sector_rows if _row_hot_level(r) > 0)
        urg_n = sum(1 for r in sector_rows if _row_hot_level(r) >= 2)
        etf = cfg.get("etf") or "—"
        label = f"{cfg['name']}  ·  {etf}  ·  {len(sector_rows)} 只"
        if hot_n:
            label += f"  🟢 {hot_n}"
        if urg_n:
            label += f"  🟠 {urg_n}"
        with st.expander(label, expanded=bool(hot_n)):
            chips = "".join(f'<span class="wb-strg">⚡ {_esc(t)}</span>' for t in cfg["sector_triggers"])
            st.markdown(f'<div class="wb-strgs">{chips}</div>', unsafe_allow_html=True)
            st.markdown(_sector_table_html(_sort_by_hot(sector_rows)), unsafe_allow_html=True)

    for row in rows:
        for alert in row.get("alerts") or []:
            if alert["type"] == "exit":
                st.error(alert["message"])
            elif alert["type"] == "trim":
                st.info(alert["message"])
            else:
                st.warning(alert["message"])


def render_stock_workbench(market: str = "US") -> None:
    is_a_share = market == "Ashare"
    st.title("A股工作台" if is_a_share else "美股工作台")
    st.caption("读取本地 JSON/Markdown 研究报告，不调用 AI；表格先加载，详情按需打开。")
    _render_analysis_refresh_control()

    positions = load_a_share_positions() if is_a_share else load_positions()
    watchlist_items = load_a_share_watchlist() if is_a_share else load_watchlist()
    watchlist_symbols = [item["symbol"] for item in watchlist_items]
    closed_items = load_a_share_closed_positions() if is_a_share else load_closed_positions()
    reports = _reports_for_market(load_latest_reports_by_ticker(), market)
    pool_rows = build_stock_pool(positions, watchlist_symbols, reports, closed_items=closed_items)
    notes = load_stock_notes()
    for row in pool_rows:
        row["note"] = notes.get(row["symbol"], "") or row.get("note", "")

    _render_watchlist_controls(watchlist_symbols, market)

    if not pool_rows:
        st.info("暂无持仓或关注股票。可以先在上方添加关注 ticker，或回主页面导入持仓。")
        _render_orphan_reports(reports, pool_rows)
        return

    _render_market_price_refresh_control()
    prices = _current_prices(tuple(row["symbol"] for row in pool_rows if row["symbol"]))
    for row in pool_rows:
        if prices.get(row["symbol"]):
            row["current_price"] = prices[row["symbol"]]

    alert_config = load_alert_config()
    for row in pool_rows:
        row["alerts"] = evaluate_price_alerts(
            row["symbol"],
            row.get("current_price"),
            row.get("price_plan") or {},
            ticker_alert_config(row["symbol"], alert_config),
        )

    if is_a_share:
        holdings_rows = _decorate_a_share_rows(_a_share_holding_rows(pool_rows))
        watch_rows = _decorate_a_share_rows(_a_share_watch_rows(pool_rows))
        holding_title = "A股持仓池"
        watch_title = "A股关注池"
        tab_holdings, tab_watch, tab_closed, tab_orphans = st.tabs(["A股持仓", "A股关注", "已平仓复盘", "未归档分析"])
    else:
        holdings_rows = _us_holding_rows(pool_rows)
        watch_rows = _us_watch_rows(pool_rows)
        holding_title = "持仓池"
        watch_title = "关注池"
        tab_holdings, tab_watch, tab_closed, tab_orphans = st.tabs(["持仓", "关注", "已平仓复盘", "未归档分析"])
    closed_rows = _decorate_a_share_rows(_closed_review_rows(pool_rows))

    with tab_holdings:
        if is_a_share:
            _render_pool_table(holding_title, holdings_rows)
        else:
            _render_us_pool_sector_grouped(holding_title, holdings_rows)
        _render_note_editor(holdings_rows, "holdings")
        _render_pool_detail_selector(holdings_rows, "holdings")
    with tab_watch:
        if is_a_share:
            _render_pool_table(watch_title, watch_rows)
        else:
            _render_us_pool_sector_grouped(watch_title, watch_rows)
        _render_move_to_closed_control(watch_rows, "watchlist", market)
        _render_note_editor(watch_rows, "watchlist")
        _render_pool_detail_selector(watch_rows, "watchlist")
    with tab_closed:
        _render_pool_table("已平仓复盘池", closed_rows)
        _render_closed_review_controls(closed_rows, market)
        _render_pool_detail_selector(closed_rows, "closed_review")
    with tab_orphans:
        _render_orphan_reports(reports, pool_rows)


def _render_analysis_refresh_control() -> None:
    col_refresh, col_status = st.columns([1, 4])
    with col_refresh:
        if st.button("刷新分析文件", use_container_width=True):
            st.cache_data.clear()
            st.session_state["analysis_files_refreshed_at"] = datetime.now().strftime("%H:%M:%S")
    refreshed_at = st.session_state.get("analysis_files_refreshed_at")
    if refreshed_at:
        with col_status:
            st.caption(f"分析文件已于 {refreshed_at} 重新加载")


def _render_market_price_refresh_control() -> None:
    col_refresh, col_status = st.columns([1, 4])
    with col_refresh:
        if st.button("刷新行情", use_container_width=True):
            _current_prices.clear()
            st.session_state["market_prices_refreshed_at"] = datetime.now().strftime("%H:%M:%S")
    refreshed_at = st.session_state.get("market_prices_refreshed_at")
    if refreshed_at:
        with col_status:
            st.caption(f"行情已于 {refreshed_at} 重新刷新；平时会使用 15 分钟缓存")


def _render_watchlist_controls(existing_symbols: list[str], market: str) -> None:
    with st.expander("管理关注列表", expanded=False):
        col1, col2 = st.columns([2, 3])
        with col1:
            symbol = st.text_input("添加 ticker", placeholder="688981" if market == "Ashare" else "CRCL", key=f"{market}_watchlist_add_symbol")
        with col2:
            notes = st.text_input("备注", placeholder="等待回撤 / 产业链观察", key=f"{market}_watchlist_add_notes")
        if st.button("加入关注", type="primary", use_container_width=True, key=f"{market}_add_watchlist"):
            if symbol.strip():
                if market == "Ashare":
                    add_a_share_watchlist(symbol, notes=notes)
                else:
                    add_to_watchlist(symbol, notes=notes)
                st.rerun()

        if existing_symbols:
            remove_symbol = st.selectbox("从关注列表移除", [""] + existing_symbols, key=f"{market}_remove_watchlist_symbol")
            if remove_symbol and st.button("移除关注", use_container_width=True, key=f"{market}_remove_watchlist"):
                if market == "Ashare":
                    remove_a_share_watchlist(remove_symbol)
                else:
                    remove_from_watchlist(remove_symbol)
                st.rerun()


def _render_pool_table(title: str, rows: list[dict]) -> None:
    st.subheader(title)
    if not rows:
        st.info("暂无数据。")
        return

    table = _pool_table_rows(rows)
    df = pd.DataFrame(table)
    st.dataframe(
        _style_pool_table(df, rows),
        use_container_width=True,
        hide_index=True,
        height=_pool_table_height(len(table)),
        column_config={
            "提醒": st.column_config.TextColumn(
                "提醒",
                width="medium",
            ),
            "备注": st.column_config.TextColumn(
                "备注",
                width="large",
            ),
        },
    )

    for row in rows:
        for alert in row.get("alerts") or []:
            if alert["type"] == "exit":
                st.error(alert["message"])
            elif alert["type"] in {"trim"}:
                st.info(alert["message"])
            else:
                st.warning(alert["message"])


def _pool_table_rows(rows: list[dict]) -> list[dict]:
    table = []
    for row in rows:
        alerts = row.get("alerts") or []
        report = row.get("report")
        analysis = report.analysis if report else {}

        scores = analysis.get("scores") or {}
        shufen_scores = analysis.get("shufen_scores") or {}

        # New format stores per-skill sub-scores under scores.xiaoyan / scores.shufen
        xiaoyan_total_score = (
            row.get("total_score_xiaoyan")
            if row.get("total_score_xiaoyan") is not None
            else scores.get("xiaoyan") if "xiaoyan" in scores else scores.get("total_score")
        )

        shufen_total_score = (
            row.get("total_score_shufen")
            if row.get("total_score_shufen") is not None
            else shufen_scores.get("total_score") or scores.get("shufen")
        )
        table.append({
            "Ticker": _ticker_display(row),
            "来源": row["source"],
            "当前价": _fmt_price(row.get("current_price")),
            "最新分析": _short_date(row.get("analysis_updated_at")),
            "动作": row.get("action") or "-",
            "xiaoyan总分": xiaoyan_total_score if xiaoyan_total_score is not None else "-",
            "shufen总分": shufen_total_score if shufen_total_score is not None else "-",
            "买入区": _fmt_zone((row.get("price_plan") or {}).get("buy_zone")),
            "减仓区": _fmt_zone((row.get("price_plan") or {}).get("trim_zone")),
            "失效价": _fmt_price((row.get("price_plan") or {}).get("invalid_price")),
            "Hard Stop": _fmt_price((row.get("price_plan") or {}).get("hard_stop")),
            "提醒": " / ".join(alert["label"] for alert in alerts) if alerts else "-",
            "备注": row.get("note") or "-",
        })
    return table


def _ticker_display(row: dict) -> str:
    symbol = row["symbol"]
    company_name = str(row.get("company_name") or "").strip()
    if row.get("is_a_share_view") and company_name:
        return f"{symbol} · {company_name}"
    return symbol


def _style_pool_table(df: pd.DataFrame, rows: list[dict]):
    styles = []
    for row in rows:
        color = _current_price_color(row.get("current_price"), row.get("price_plan") or {})
        styles.append(["" if column != "当前价" else color for column in df.columns])
    return df.style.apply(lambda _: pd.DataFrame(styles, index=df.index, columns=df.columns), axis=None)


def _us_holding_rows(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if "持仓" in row.get("source", "") and not _is_a_share_symbol(row.get("symbol", ""))
    ]


def _us_watch_rows(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if "关注" in row.get("source", "") and not _is_a_share_symbol(row.get("symbol", ""))
    ]


def _a_share_holding_rows(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if "持仓" in row.get("source", "") and _is_a_share_symbol(row.get("symbol", ""))
    ]


def _a_share_watch_rows(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if "关注" in row.get("source", "") and _is_a_share_symbol(row.get("symbol", ""))
    ]


def _closed_review_rows(rows: list[dict]) -> list[dict]:
    return [
        row for row in rows
        if "已平仓复盘" in row.get("source", "")
    ]


def _reports_for_market(reports: dict, market: str) -> dict:
    if market == "Ashare":
        return {
            ticker: report for ticker, report in reports.items()
            if _is_a_share_symbol(ticker) or report.analysis.get("market") == "Ashare"
        }
    return {
        ticker: report for ticker, report in reports.items()
        if not _is_a_share_symbol(ticker) and report.analysis.get("market") != "Ashare"
    }


def _decorate_a_share_rows(rows: list[dict]) -> list[dict]:
    cached_names = load_a_share_names()
    for row in rows:
        if not _is_a_share_symbol(row.get("symbol", "")):
            continue
        report = row.get("report")
        analysis = report.analysis if report else {}
        row["is_a_share_view"] = True
        code = normalize_a_share_code(row.get("symbol", ""))
        row["company_name"] = (analysis.get("company") or cached_names.get(code, "")).strip()
    return rows


def _is_a_share_symbol(symbol: str) -> bool:
    symbol = str(symbol or "").upper().strip()
    if not symbol:
        return False
    if symbol.endswith((".SS", ".SZ", ".SH", ".BJ")):
        return bool(re.match(r"^\d{6}\.(SS|SZ|SH|BJ)$", symbol))
    return bool(re.match(r"^\d{6}$", symbol))


def _current_price_color(current_price, price_plan: dict) -> str:
    price = _to_float(current_price)
    if price is None:
        return ""

    trim_zone = price_plan.get("trim_zone")
    trim_lower = _zone_bound(trim_zone, 0)
    if trim_lower is not None and price >= trim_lower:
        return "color: #16a34a; font-weight: 700"

    buy_zone = price_plan.get("buy_zone")
    buy_upper = _zone_bound(buy_zone, 1)
    if buy_upper is not None and price <= buy_upper:
        return "color: #dc2626; font-weight: 700"

    return ""


def _zone_bound(zone, index: int) -> float | None:
    if not isinstance(zone, (list, tuple)) or len(zone) <= index:
        return None
    return _to_float(zone[index])


def _to_float(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _render_note_editor(rows: list[dict], key_prefix: str) -> None:
    if not rows:
        return
    with st.expander("编辑备注", expanded=False):
        symbols = [row["symbol"] for row in rows]
        selected = st.selectbox(
            "选择 ticker",
            symbols,
            format_func=lambda symbol: _select_label(symbol, rows),
            key=f"{key_prefix}_note_symbol",
        )
        row = next((item for item in rows if item["symbol"] == selected), {})
        note = st.text_area(
            "备注",
            value=row.get("note") or "",
            height=90,
            key=f"{key_prefix}_note_text",
            placeholder="例如：等待回踩到买入区 / 财报前不加仓 / 需要复核产业链变化",
        )
        if st.button("保存备注", type="primary", use_container_width=True, key=f"{key_prefix}_save_note"):
            set_stock_note(selected, note)
            st.success(f"已保存 {selected} 备注")
            st.rerun()


def _render_move_to_closed_control(rows: list[dict], key_prefix: str, market: str) -> None:
    if not rows:
        return
    with st.expander("移入已平仓复盘", expanded=False):
        selected = st.selectbox(
            "选择 ticker",
            [""] + [row["symbol"] for row in rows],
            format_func=lambda symbol: _select_label(symbol, rows),
            key=f"{key_prefix}_closed_symbol",
        )
        notes = st.text_input(
            "复盘备注",
            placeholder="例如：已止盈，后续观察 thesis 是否兑现",
            key=f"{key_prefix}_closed_notes",
        )
        if selected and st.button("移入复盘", use_container_width=True, key=f"{key_prefix}_move_closed"):
            if market == "Ashare":
                add_a_share_closed_position(selected, notes=notes)
                remove_a_share_watchlist(selected)
            else:
                add_closed_position(selected, notes=notes)
                remove_from_watchlist(selected)
            st.rerun()


def _render_closed_review_controls(rows: list[dict], market: str) -> None:
    if not rows:
        return
    with st.expander("管理已平仓复盘", expanded=False):
        selected = st.selectbox(
            "选择 ticker",
            [""] + [row["symbol"] for row in rows],
            format_func=lambda symbol: _select_label(symbol, rows),
            key="closed_review_manage_symbol",
        )
        col_watch, col_remove = st.columns(2)
        if selected and col_watch.button("移回关注", use_container_width=True):
            if market == "Ashare":
                add_a_share_watchlist(selected)
                remove_a_share_closed_position(selected)
            else:
                add_to_watchlist(selected)
                remove_closed_position(selected)
            st.rerun()
        if selected and col_remove.button("移出复盘", use_container_width=True):
            if market == "Ashare":
                remove_a_share_closed_position(selected)
            else:
                remove_closed_position(selected)
            st.rerun()


def _render_pool_detail_selector(rows: list[dict], key_prefix: str) -> None:
    if not rows:
        return
    st.markdown("---")
    selected = st.selectbox(
        "选择 ticker 查看详情",
        [""] + [row["symbol"] for row in rows],
        format_func=lambda symbol: _select_label(symbol, rows),
        placeholder="选择后加载详情",
        key=f"{key_prefix}_detail_symbol",
    )
    if selected:
        row = next((item for item in rows if item["symbol"] == selected), None)
        if row:
            _render_detail(row)


def _render_detail(row: dict) -> None:
    st.subheader(f"{row['symbol']} 详情")
    report = row.get("report")
    if not report:
        st.info("这个 ticker 暂无本地分析报告。把符合命名规则的 JSON 放到 data/ 或 data/research_reports/ 后会自动出现。")
        return

    analysis = report.analysis
    xiaoyan_scores = analysis.get("scores") or {}
    shufen_scores = analysis.get("shufen_scores") or {}
    probability = analysis.get("probability") or {}

    # New format stores per-skill sub-scores under scores.xiaoyan / scores.shufen
    xiaoyan_display = xiaoyan_scores.get("xiaoyan") if "xiaoyan" in xiaoyan_scores else xiaoyan_scores.get("total_score", "-")
    shufen_display = shufen_scores.get("total_score", "-")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("当前动作", analysis.get("action") or "-")
    col2.metric("晓言总分", xiaoyan_display)
    col3.metric("淑芬总分", shufen_display)
    col4.metric("胜率", _fmt_probability(probability))

    for alert in row.get("alerts") or []:
        st.warning(alert["message"])

    watch_triggers = analysis.get("watch_triggers") or []
    if watch_triggers:
        st.markdown("#### 离场 / 预警触发条件")
        for trigger in watch_triggers:
            st.markdown(f"- {trigger}")

    st.markdown("#### 完整报告")
    if report.markdown_path:
        st.markdown(report.markdown_path.read_text(encoding="utf-8"))
    else:
        st.json({"meta": report.meta, "ticker_analysis": analysis}, expanded=False)


def _render_sector_view(reports: dict) -> None:
    st.subheader("板块视图")
    st.caption("按板块汇总持仓 / 关注中的 ticker，展示板块级别触发条件和个股预警条件。")
    sector_view = build_sector_view(reports)
    for sector_key, cfg in sector_view.items():
        tickers = cfg["tickers"]
        label = cfg["name"]
        etf = cfg.get("etf")
        etf_suffix = f" · ETF: {etf}" if etf else ""
        with st.expander(f"{label}{etf_suffix}（{len(tickers)} 个）", expanded=bool(tickers)):
            st.markdown("**板块触发条件**")
            for trigger in cfg["sector_triggers"]:
                st.markdown(f"- {trigger}")
            if not tickers:
                st.caption("暂无 ticker 归入本板块。")
                continue
            for entry in tickers:
                ticker = entry["ticker"]
                company = entry["company"]
                action = entry["action"]
                header = f"**{ticker}**"
                if company:
                    header += f" · {company}"
                if action:
                    header += f" · `{action}`"
                st.markdown(header)
                for wt in entry["watch_triggers"]:
                    st.markdown(f"  - {wt}")
                if not entry["watch_triggers"]:
                    st.caption(f"  {ticker} 暂无个股预警条件（旧版报告格式）。")


def _render_orphan_reports(reports: dict, pool_rows: list[dict]) -> None:
    orphans = orphan_reports(reports, pool_rows)
    if not orphans:
        st.info("暂无数据。")
        return
    st.warning("以下报告已有分析，但 ticker 不在持仓或关注池中。")
    for report in orphans:
        ticker = report.ticker
        col1, col2, col3, col4 = st.columns([1, 3, 1, 1])
        col1.markdown(f"**{ticker}**")
        col2.caption(str(report.path))
        if col3.button("加入关注", key=f"add_orphan_{ticker}"):
            if _is_a_share_symbol(ticker):
                add_a_share_watchlist(ticker)
            else:
                add_to_watchlist(ticker)
            st.rerun()
        if col4.button("加入复盘", key=f"review_orphan_{ticker}"):
            if _is_a_share_symbol(ticker):
                add_a_share_closed_position(ticker, notes="从未归档分析加入复盘")
            else:
                add_closed_position(ticker, notes="从未归档分析加入复盘")
            st.rerun()


@st.cache_data(ttl=900, show_spinner=False)
def _current_prices(symbols: tuple[str, ...]) -> dict[str, float]:
    quotes = get_quotes(list(symbols))
    return {symbol: quote["price"] for symbol, quote in quotes.items() if quote.get("price")}


def _render_score_table(scores: dict, shufen_scores: dict) -> None:
    rows = []
    for label, value in scores.items():
        rows.append({"体系": "xiaoyan", "项目": label, "分数": value})
    for label, value in shufen_scores.items():
        rows.append({"体系": "shufen", "项目": label, "分数": value})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _render_price_plan(price_plan: dict) -> None:
    rows = [
        ("当前价", _fmt_price(price_plan.get("current_price"))),
        ("买入区", _fmt_zone(price_plan.get("buy_zone"))),
        ("加仓区", _fmt_zone(price_plan.get("add_zone"))),
        ("减仓区", _fmt_zone(price_plan.get("trim_zone"))),
        ("Bull Target", _fmt_zone(price_plan.get("bull_target"))),
        ("Base Target", _fmt_price(price_plan.get("base_target"))),
        ("Bear Price", _fmt_price(price_plan.get("bear_price"))),
        ("Invalid Price", _fmt_price(price_plan.get("invalid_price"))),
        ("Hard Stop", _fmt_price(price_plan.get("hard_stop"))),
    ]
    st.dataframe(pd.DataFrame(rows, columns=["项目", "值"]), use_container_width=True, hide_index=True)


def _render_catalysts(catalysts: list[dict]) -> None:
    if not catalysts:
        return
    st.markdown("#### 催化事件")
    st.dataframe(pd.DataFrame(catalysts), use_container_width=True, hide_index=True)


def _render_list_section(title: str, items) -> None:
    if not items:
        return
    st.markdown(f"#### {title}")
    for item in items:
        st.markdown(f"- {item}")


def _select_label(symbol: str, rows: list[dict]) -> str:
    if not symbol:
        return "选择后加载详情"
    row = next((item for item in rows if item["symbol"] == symbol), {})
    label = f"{symbol} · {row.get('source', '')}"
    if row.get("has_analysis"):
        label = f"{label} · 有分析"
    return label


def _pool_table_height(row_count: int) -> int:
    header_height = 38
    row_height = 35
    bottom_padding = 8
    return header_height + max(row_count, 1) * row_height + bottom_padding


def _fmt_zone(zone) -> str:
    if isinstance(zone, (list, tuple)) and len(zone) == 2:
        return f"{_fmt_price(zone[0])} - {_fmt_price(zone[1])}"
    return "-"


def _fmt_price(value) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "-"


def _fmt_probability(probability: dict) -> str:
    low = probability.get("win_rate_low")
    high = probability.get("win_rate_high")
    if low is None or high is None:
        return "-"
    return f"{float(low) * 100:.0f}%-{float(high) * 100:.0f}%"


def _short_date(value: str | None) -> str:
    if not value:
        return "-"
    return str(value)[:10]
