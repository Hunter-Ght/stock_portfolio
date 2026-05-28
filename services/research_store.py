"""
Research report storage helpers for the stock workbench.

Reports are manually produced JSON or Markdown files named:
YYYY-MM-DD_TICKER_skill1_skill2.json
YYYY-MM-DD_数字股票代码_字母代码_FLT_Ashare.json
Markdown reports can either pair with JSON or include JSON front matter.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from importers.base import Position
from services.a_share_names import normalize_a_share_code
from services.spread_detector import detect_spreads


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RESEARCH_DIR = DATA_DIR / "research_reports"
US_REPORT_NAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<ticker>[A-Z0-9.\-]+)_(?P<skills>.+)\.(?:json|md)$", re.IGNORECASE)
A_SHARE_REPORT_NAME_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<ticker>\d{6})_(?P<letter_code>[A-Z0-9.\-]+)_(?P<skills>.+)_Ashare\.(?:json|md)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ResearchReport:
    path: Path
    markdown_path: Path | None
    meta: dict
    analysis: dict

    @property
    def ticker(self) -> str:
        ticker = str(self.analysis.get("ticker") or "").upper().strip()
        if (self.analysis.get("market") or self.meta.get("market")) == "Ashare":
            return normalize_a_share_code(ticker) or normalize_a_share_code(self.meta.get("ticker", "")) or ticker
        return ticker

    @property
    def generated_at(self) -> str:
        return str(self.meta.get("generated_at") or "")


def default_report_dirs() -> list[Path]:
    """Return report directories, keeping data/ root compatibility for existing samples."""
    return [
        RESEARCH_DIR / "us",
        RESEARCH_DIR / "a_share",
        RESEARCH_DIR / "ashare",
        RESEARCH_DIR,
        DATA_DIR,
    ]


def load_latest_reports_by_ticker(report_dirs: Iterable[Path] | None = None) -> dict[str, ResearchReport]:
    """Load the newest valid report per ticker from the configured directories."""
    latest: dict[str, ResearchReport] = {}
    for report in iter_reports(report_dirs):
        ticker = report.ticker
        if not ticker:
            continue
        current = latest.get(ticker)
        if current is None or _report_sort_key(report) > _report_sort_key(current):
            latest[ticker] = report
    return dict(sorted(latest.items()))


def iter_reports(report_dirs: Iterable[Path] | None = None) -> list[ResearchReport]:
    reports: list[ResearchReport] = []
    seen_paths: set[Path] = set()
    for directory in report_dirs or default_report_dirs():
        directory = Path(directory)
        if not directory.exists():
            continue
        for path in _report_candidates(directory):
            resolved = path.resolve()
            if resolved in seen_paths or not _looks_like_report_file(path):
                continue
            seen_paths.add(resolved)
            report = load_report(path)
            if report is not None:
                reports.append(report)
    return reports


def load_report(path: Path) -> ResearchReport | None:
    name_info = _report_name_info(Path(path))
    if Path(path).suffix.lower() == ".md":
        return _load_markdown_report(Path(path), name_info)

    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None

    # New flat format: top-level ticker with no ticker_analysis wrapper
    if data.get("ticker") and "ticker_analysis" not in data:
        return _load_flat_json_report(Path(path), data, name_info)

    meta = dict(data.get("meta") or {})
    if name_info:
        meta.setdefault("report_date", name_info["date"])
        meta.setdefault("ticker", name_info["ticker"])
        meta.setdefault("market", name_info["market"])
        meta.setdefault("skills", name_info["skills"])
        if name_info.get("letter_code"):
            meta.setdefault("letter_code", name_info["letter_code"])
    analyses = data.get("ticker_analysis") or []
    if not isinstance(analyses, list):
        return None

    reports: list[ResearchReport] = []
    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue
        analysis = dict(analysis)
        if name_info:
            if name_info["market"] == "Ashare":
                analysis["ticker"] = normalize_a_share_code(analysis.get("ticker", "")) or name_info["ticker"]
            else:
                analysis.setdefault("ticker", name_info["ticker"])
            analysis.setdefault("market", name_info["market"])
            analysis.setdefault("skills", name_info["skills"])
            if name_info.get("letter_code"):
                analysis.setdefault("letter_code", name_info["letter_code"])
        _normalize_score_fields(analysis)
        if not _has_minimum_analysis_fields(meta, analysis):
            continue
        reports.append(ResearchReport(
            path=Path(path),
            markdown_path=_matching_markdown_path(Path(path)),
            meta=meta,
            analysis=analysis,
        ))

    return reports[0] if reports else None


def _load_flat_json_report(path: Path, data: dict, name_info: dict | None) -> ResearchReport | None:
    """Load a new-style flat JSON report (schema v1.1+ without meta/ticker_analysis wrappers)."""
    meta_keys = {"schema_version", "generated_at", "market", "skills", "company"}
    meta = {k: data[k] for k in meta_keys if k in data}
    if name_info:
        meta.setdefault("report_date", name_info["date"])
        meta.setdefault("market", name_info["market"])
        meta.setdefault("skills", name_info["skills"])
        if name_info.get("letter_code"):
            meta.setdefault("letter_code", name_info["letter_code"])

    analysis = dict(data)
    if name_info:
        if name_info["market"] == "Ashare":
            analysis["ticker"] = normalize_a_share_code(analysis.get("ticker", "")) or name_info["ticker"]
        else:
            analysis.setdefault("ticker", name_info["ticker"])
        analysis.setdefault("market", name_info["market"])
        analysis.setdefault("skills", name_info["skills"])
        if name_info.get("letter_code"):
            analysis.setdefault("letter_code", name_info["letter_code"])

    _normalize_score_fields(analysis)
    if not _has_minimum_analysis_fields(meta, analysis):
        return None
    return ResearchReport(
        path=path,
        markdown_path=_matching_markdown_path(path),
        meta=meta,
        analysis=analysis,
    )


def _load_markdown_report(path: Path, name_info: dict | None) -> ResearchReport | None:
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return None
    front_matter = _extract_json_front_matter(content)
    if not front_matter:
        return None

    meta, analysis = _front_matter_to_report_parts(front_matter, name_info)
    _normalize_score_fields(analysis)
    if not _has_minimum_analysis_fields(meta, analysis):
        return None
    return ResearchReport(
        path=path,
        markdown_path=path,
        meta=meta,
        analysis=analysis,
    )


def build_stock_pool(
    positions: list[Position],
    watchlist_symbols: list[str],
    reports_by_ticker: dict[str, ResearchReport],
    closed_items: list[dict] | None = None,
) -> list[dict]:
    """Build the workbench pool from holdings + watchlist + closed review items."""
    holdings: dict[str, dict] = {}
    for position in _dashboard_stock_positions(positions):
        symbol = position.symbol.upper().strip()
        if not symbol:
            continue
        entry = holdings.setdefault(symbol, {
            "symbol": symbol,
            "sources": set(),
            "quantity": 0.0,
            "market_value": 0.0,
            "unrealized_pnl": 0.0,
            "current_price": 0.0,
        })
        entry["sources"].add("持仓")
        entry["quantity"] += float(position.quantity or 0)
        entry["market_value"] += float(position.market_value or 0)
        entry["unrealized_pnl"] += float(position.unrealized_pnl or 0)
        if position.current_price:
            entry["current_price"] = float(position.current_price)

    watchlist = []
    for raw_symbol in watchlist_symbols:
        symbol = raw_symbol.upper().strip()
        if symbol:
            watchlist.append(symbol)

    closed = []
    for item in closed_items or []:
        symbol = str(item.get("symbol") or "").upper().strip()
        if symbol:
            closed.append({**item, "symbol": symbol})

    active_symbols = set(holdings) | set(watchlist)
    closed_symbols = [item["symbol"] for item in closed if item["symbol"] not in active_symbols]
    symbols = sorted(active_symbols) + sorted(set(closed_symbols))
    rows = []
    for symbol in symbols:
        holding = holdings.get(symbol, {
            "sources": set(),
            "quantity": 0.0,
            "market_value": 0.0,
            "unrealized_pnl": 0.0,
            "current_price": 0.0,
        })
        sources = set(holding["sources"])
        if symbol in watchlist:
            sources.add("关注")
        closed_item = next((item for item in closed if item["symbol"] == symbol), {})
        if symbol not in active_symbols:
            sources.add("已平仓复盘")
        report = _report_for_symbol(symbol, reports_by_ticker)
        analysis = report.analysis if report else {}
        price_plan = analysis.get("price_plan") or {}
        rows.append({
            "symbol": symbol,
            "source": "+".join(sorted(sources, key=lambda v: 0 if v == "持仓" else 1)),
            "quantity": holding["quantity"],
            "market_value": holding["market_value"],
            "unrealized_pnl": holding["unrealized_pnl"],
            "current_price": holding["current_price"] or price_plan.get("current_price"),
            "has_analysis": report is not None,
            "report": report,
            "analysis_updated_at": report.generated_at if report else "",
            "action": analysis.get("action") or "",
            "conclusion": analysis.get("conclusion") or "",
            "total_score": (analysis.get("scores") or {}).get("total_score"),
            "shufen_score": (analysis.get("shufen_scores") or {}).get("total_score"),
            "price_plan": price_plan,
            "note": closed_item.get("notes") or "",
            "closed_at": closed_item.get("closed_at") or "",
        })
    return rows


def _dashboard_stock_positions(positions: list[Position]) -> list[Position]:
    """Return the same stock positions shown by the portfolio dashboard."""
    _, stock_positions, _ = detect_spreads(positions)
    return stock_positions


def _report_for_symbol(symbol: str, reports_by_ticker: dict[str, ResearchReport]) -> ResearchReport | None:
    direct = reports_by_ticker.get(symbol)
    if direct is not None:
        return direct
    code = normalize_a_share_code(symbol)
    return reports_by_ticker.get(code) if code else None


def orphan_reports(reports_by_ticker: dict[str, ResearchReport], pool_rows: list[dict]) -> list[ResearchReport]:
    pool_symbols = {row["symbol"] for row in pool_rows}
    normalized_pool_symbols = {
        normalize_a_share_code(symbol) or symbol
        for symbol in pool_symbols
    }
    return [
        report for ticker, report in sorted(reports_by_ticker.items())
        if ticker not in pool_symbols and ticker not in normalized_pool_symbols
    ]


def _looks_like_report_file(path: Path) -> bool:
    return _report_name_info(path) is not None


def _report_candidates(directory: Path) -> list[Path]:
    json_paths = sorted(directory.glob("*.json"))
    json_stems = {path.stem for path in json_paths}
    markdown_paths = [
        path for path in sorted(directory.glob("*.md"))
        if path.stem not in json_stems
    ]
    return json_paths + markdown_paths


def _report_name_info(path: Path) -> dict | None:
    name = path.name
    a_share_match = A_SHARE_REPORT_NAME_RE.match(name)
    if a_share_match:
        skills = [part for part in a_share_match.group("skills").split("_") if part]
        return {
            "date": a_share_match.group("date"),
            "ticker": a_share_match.group("ticker").upper(),
            "letter_code": a_share_match.group("letter_code").upper(),
            "skills": skills,
            "market": "Ashare",
        }

    us_match = US_REPORT_NAME_RE.match(name)
    if not us_match:
        return None
    skills = [part for part in us_match.group("skills").replace(".json", "").split("_") if part]
    return {
        "date": us_match.group("date"),
        "ticker": us_match.group("ticker").upper(),
        "letter_code": "",
        "skills": skills,
        "market": "US",
    }


def _matching_markdown_path(path: Path) -> Path | None:
    markdown = path.with_suffix(".md")
    return markdown if markdown.exists() else None


def _extract_json_front_matter(content: str) -> dict | None:
    if not content.startswith("---"):
        return None
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            raw = "\n".join(lines[1:index]).strip()
            if not raw:
                return None
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return None
            return parsed if isinstance(parsed, dict) else None
    return None


def _front_matter_to_report_parts(front_matter: dict, name_info: dict | None) -> tuple[dict, dict]:
    meta_keys = {
        "schema_version",
        "report_id",
        "generated_at",
        "timezone",
        "method_used",
        "analysis_mode",
        "tickers",
        "report_date",
        "market",
        "skills",
        "letter_code",
        "base_currency",
        "data_freshness",
        "notes",
    }
    meta = {key: front_matter[key] for key in meta_keys if key in front_matter}
    analysis = dict(front_matter)

    if name_info:
        meta.setdefault("report_date", name_info["date"])
        meta.setdefault("ticker", name_info["ticker"])
        meta.setdefault("market", name_info["market"])
        meta.setdefault("skills", name_info["skills"])
        if name_info.get("letter_code"):
            meta.setdefault("letter_code", name_info["letter_code"])
        if name_info["market"] == "Ashare":
            analysis["ticker"] = normalize_a_share_code(analysis.get("ticker", "")) or name_info["ticker"]
        else:
            analysis.setdefault("ticker", name_info["ticker"])
        analysis.setdefault("market", name_info["market"])
        analysis.setdefault("skills", name_info["skills"])
        if name_info.get("letter_code"):
            analysis.setdefault("letter_code", name_info["letter_code"])

    return meta, analysis


def _has_minimum_analysis_fields(meta: dict, analysis: dict) -> bool:
    if not (meta.get("generated_at") and analysis.get("ticker")):
        return False
    scores = analysis.get("scores") or {}
    price_plan = analysis.get("price_plan") or {}
    return "total_score" in scores and "current_price" in price_plan


def _normalize_score_fields(analysis: dict) -> None:
    scores = analysis.get("scores")
    if isinstance(scores, dict) and "total_score" in scores:
        # New flat format: scores may contain xiaoyan/shufen sub-keys
        if "shufen" in scores and not analysis.get("shufen_scores"):
            analysis["shufen_scores"] = {"total_score": scores["shufen"]}
        return
    for key in ("flt_scores", "xiaoyan_scores", "shufen_scores"):
        fallback = analysis.get(key)
        if isinstance(fallback, dict) and "total_score" in fallback:
            analysis["scores"] = fallback
            return


def _report_sort_key(report: ResearchReport) -> tuple[str, str]:
    generated = report.generated_at
    try:
        generated = datetime.fromisoformat(generated).isoformat()
    except ValueError:
        pass
    return generated, report.path.name
