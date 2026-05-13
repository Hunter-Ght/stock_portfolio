"""
Research report storage helpers for the stock workbench.

Reports are manually produced JSON files named:
YYYY-MM-DD_TICKER_skill1_skill2.json
Optional full-text markdown reports can use the same stem with .md.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from importers.base import Position
from services.spread_detector import detect_spreads


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
RESEARCH_DIR = DATA_DIR / "research_reports"
REPORT_NAME_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})_(?P<ticker>[A-Z0-9.\-]+)_.+\.json$")


@dataclass(frozen=True)
class ResearchReport:
    path: Path
    markdown_path: Path | None
    meta: dict
    analysis: dict

    @property
    def ticker(self) -> str:
        return str(self.analysis.get("ticker") or "").upper().strip()

    @property
    def generated_at(self) -> str:
        return str(self.meta.get("generated_at") or "")


def default_report_dirs() -> list[Path]:
    """Return report directories, keeping data/ root compatibility for existing samples."""
    return [RESEARCH_DIR, DATA_DIR]


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
        for path in sorted(directory.glob("*.json")):
            resolved = path.resolve()
            if resolved in seen_paths or not _looks_like_report_file(path):
                continue
            seen_paths.add(resolved)
            report = load_report(path)
            if report is not None:
                reports.append(report)
    return reports


def load_report(path: Path) -> ResearchReport | None:
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None

    meta = data.get("meta") or {}
    analyses = data.get("ticker_analysis") or []
    if not isinstance(analyses, list):
        return None

    reports: list[ResearchReport] = []
    for analysis in analyses:
        if not isinstance(analysis, dict):
            continue
        if not _has_minimum_analysis_fields(meta, analysis):
            continue
        reports.append(ResearchReport(
            path=Path(path),
            markdown_path=_matching_markdown_path(Path(path)),
            meta=meta,
            analysis=analysis,
        ))

    return reports[0] if reports else None


def build_stock_pool(
    positions: list[Position],
    watchlist_symbols: list[str],
    reports_by_ticker: dict[str, ResearchReport],
) -> list[dict]:
    """Build the workbench pool from holdings + watchlist only."""
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

    symbols = sorted(set(holdings) | set(watchlist))
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
        report = reports_by_ticker.get(symbol)
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
        })
    return rows


def _dashboard_stock_positions(positions: list[Position]) -> list[Position]:
    """Return the same stock positions shown by the portfolio dashboard."""
    _, stock_positions, _ = detect_spreads(positions)
    return stock_positions


def orphan_reports(reports_by_ticker: dict[str, ResearchReport], pool_rows: list[dict]) -> list[ResearchReport]:
    pool_symbols = {row["symbol"] for row in pool_rows}
    return [report for ticker, report in sorted(reports_by_ticker.items()) if ticker not in pool_symbols]


def _looks_like_report_file(path: Path) -> bool:
    return bool(REPORT_NAME_RE.match(path.name))


def _matching_markdown_path(path: Path) -> Path | None:
    markdown = path.with_suffix(".md")
    return markdown if markdown.exists() else None


def _has_minimum_analysis_fields(meta: dict, analysis: dict) -> bool:
    if not (meta.get("generated_at") and analysis.get("ticker")):
        return False
    scores = analysis.get("scores") or {}
    price_plan = analysis.get("price_plan") or {}
    return "total_score" in scores and "current_price" in price_plan


def _report_sort_key(report: ResearchReport) -> tuple[str, str]:
    generated = report.generated_at
    try:
        generated = datetime.fromisoformat(generated).isoformat()
    except ValueError:
        pass
    return generated, report.path.name
