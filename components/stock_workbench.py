"""Stock research workbench UI components."""
from __future__ import annotations

from datetime import datetime
import re

import pandas as pd
import streamlit as st

from services.alert_engine import evaluate_price_alerts
from services.a_share_names import get_a_share_name
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
def render_stock_workbench() -> None:
    st.title("个股工作台")
    st.caption("读取本地 JSON 研究报告，不调用 AI；持仓池与持仓追踪页的股票 & ETF 持仓保持同一口径。")
    _render_analysis_refresh_control()

    positions = load_positions()
    watchlist_items = load_watchlist()
    watchlist_symbols = [item["symbol"] for item in watchlist_items]
    reports = load_latest_reports_by_ticker()
    pool_rows = build_stock_pool(positions, watchlist_symbols, reports)
    notes = load_stock_notes()
    for row in pool_rows:
        row["note"] = notes.get(row["symbol"], "")

    _render_watchlist_controls(watchlist_symbols)

    if not pool_rows:
        st.info("暂无持仓或关注股票。可以先在上方添加关注 ticker，或回主页面导入持仓。")
        _render_orphan_reports(reports, pool_rows)
        return

    prices = _current_prices(pool_rows)
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

    holdings_rows = _us_holding_rows(pool_rows)
    watch_rows = _us_watch_rows(pool_rows)
    a_share_holding_rows = _decorate_a_share_rows(_a_share_holding_rows(pool_rows))
    a_share_watch_rows = _decorate_a_share_rows(_a_share_watch_rows(pool_rows))

    tab_holdings, tab_watch, tab_a_share_holdings, tab_a_share_watch, tab_orphans = st.tabs([
        "持仓",
        "关注",
        "A股持仓",
        "A股关注",
        "未归档分析",
    ])
    with tab_holdings:
        _render_pool_table("持仓池", holdings_rows)
        _render_note_editor(holdings_rows, "holdings")
        _render_pool_detail_selector(holdings_rows, "holdings")
    with tab_watch:
        _render_pool_table("关注池", watch_rows)
        _render_note_editor(watch_rows, "watchlist")
        _render_pool_detail_selector(watch_rows, "watchlist")
    with tab_a_share_holdings:
        _render_pool_table("A股持仓池", a_share_holding_rows)
        _render_note_editor(a_share_holding_rows, "a_share_holdings")
        _render_pool_detail_selector(a_share_holding_rows, "a_share_holdings")
    with tab_a_share_watch:
        _render_pool_table("A股关注池", a_share_watch_rows)
        _render_note_editor(a_share_watch_rows, "a_share_watchlist")
        _render_pool_detail_selector(a_share_watch_rows, "a_share_watchlist")
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


def _render_watchlist_controls(existing_symbols: list[str]) -> None:
    with st.expander("管理关注列表", expanded=False):
        col1, col2 = st.columns([2, 3])
        with col1:
            symbol = st.text_input("添加 ticker", placeholder="CRCL", key="watchlist_add_symbol")
        with col2:
            notes = st.text_input("备注", placeholder="等待回撤 / 产业链观察", key="watchlist_add_notes")
        if st.button("加入关注", type="primary", use_container_width=True):
            if symbol.strip():
                add_to_watchlist(symbol, notes=notes)
                st.rerun()

        if existing_symbols:
            remove_symbol = st.selectbox("从关注列表移除", [""] + existing_symbols)
            if remove_symbol and st.button("移除关注", use_container_width=True):
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

        xiaoyan_total_score = (
            row.get("total_score_xiaoyan")
            if row.get("total_score_xiaoyan") is not None
            else scores.get("total_score")
        )

        shufen_total_score = (
            row.get("total_score_shufen")
            if row.get("total_score_shufen") is not None
            else shufen_scores.get("total_score")
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


def _decorate_a_share_rows(rows: list[dict]) -> list[dict]:
    for row in rows:
        report = row.get("report")
        analysis = report.analysis if report else {}
        row["is_a_share_view"] = True
        row["company_name"] = get_a_share_name(row.get("symbol", ""), analysis.get("company") or "")
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


def _render_pool_detail_selector(rows: list[dict], key_prefix: str) -> None:
    if not rows:
        return
    st.markdown("---")
    selected = st.selectbox(
        "选择 ticker 查看详情",
        [row["symbol"] for row in rows],
        format_func=lambda symbol: _select_label(symbol, rows),
        key=f"{key_prefix}_detail_symbol",
    )
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

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("当前动作", analysis.get("action") or "-")
    col2.metric("晓言总分", xiaoyan_scores.get("total_score", "-"))
    col3.metric("淑芬总分", shufen_scores.get("total_score", "-"))
    col4.metric("胜率", _fmt_probability(probability))

    for alert in row.get("alerts") or []:
        st.warning(alert["message"])

    st.markdown("#### 完整报告")
    if report.markdown_path:
        st.markdown(report.markdown_path.read_text(encoding="utf-8"))
    else:
        st.json({"meta": report.meta, "ticker_analysis": analysis}, expanded=False)


def _render_orphan_reports(reports: dict, pool_rows: list[dict]) -> None:
    orphans = orphan_reports(reports, pool_rows)
    if not orphans:
        st.info("暂无数据。")
        return
    st.warning("以下报告已有分析，但 ticker 不在持仓或关注池中。")
    for report in orphans:
        ticker = report.ticker
        col1, col2, col3 = st.columns([1, 3, 1])
        col1.markdown(f"**{ticker}**")
        col2.caption(str(report.path))
        if col3.button("加入关注", key=f"add_orphan_{ticker}"):
            add_to_watchlist(ticker)
            st.rerun()


def _current_prices(rows: list[dict]) -> dict[str, float]:
    symbols = [row["symbol"] for row in rows if row["symbol"]]
    quotes = get_quotes(symbols)
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
