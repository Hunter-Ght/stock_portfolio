"""Sector configuration and sector-level view builder."""
from __future__ import annotations

import copy
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.research_store import ResearchReport


SECTOR_CONFIG: dict[str, dict] = {
    "bio": {
        "name": "🧬 生物医药",
        "etf": "XBI",
        "color": "#1D9E75",
        "sector_triggers": [
            "XBI 单周 < −6% → 全板块逃顶分析",
            "FDA PDUFA 关键日期",
            "板块利好钝化（好消息但不涨）",
            "XBI 持仓回撤 > 15%",
        ],
    },
    "nuc": {
        "name": "☢️ 核能 / 清洁能源",
        "etf": "URA",
        "color": "#BA7517",
        "sector_triggers": [
            "铀价涨幅放缓连续 3 周",
            "URA 单周 < −7%",
            "能源政策重大变化",
            "LNG 现货价连续下行",
        ],
    },
    "tech": {
        "name": "💻 科技 / AI",
        "etf": "IGV",
        "color": "#185FA5",
        "sector_triggers": [
            "NVDA 财报收跌 > 5%",
            "hyperscaler Capex 指引下修",
            "SMH 单周 < −7%",
            "IGV 持仓回撤 > 12%",
        ],
    },
    "mat": {
        "name": "🔋 材料 / 大宗商品",
        "etf": "GSG",
        "color": "#534AB7",
        "sector_triggers": [
            "大宗商品价格连续 3 周下行",
            "美元 DXY > 106",
            "中国需求数据转弱",
        ],
    },
    "ind": {
        "name": "🏭 工业 / 国防",
        "etf": "ITA",
        "color": "#5F5E5A",
        "sector_triggers": [
            "国防预算削减信号",
            "PMI < 48 连续两月",
            "ITA 单周 < −6%",
        ],
    },
    "oth": {
        "name": "📋 其他",
        "etf": None,
        "color": "#888880",
        "sector_triggers": ["个股独立判断"],
    },
}

# Keywords to infer sector key from free-text sector strings (old format).
# Order matters: more specific sectors are checked before broader ones (e.g. "ind" before "mat"
# so "Aerospace & Defense Materials" resolves to "ind" rather than "mat").
_SECTOR_KEYWORD_MAP: dict[str, list[str]] = {
    "bio": ["bio", "pharma", "medical", "drug", "oncolog", "genomic", "health", "therapeut"],
    "nuc": ["nuclear", "uranium", "clean energy", "solar", "wind", "lng", "natural gas"],
    "tech": [
        "tech", "ai ", "artificial intelligence", "software", "cloud", "semiconductor",
        "digital", "internet", "communication", "crypto", "fintech", "financial tech",
        "saas", "data", "cybersec", "network",
    ],
    "ind": ["industrial", "defense", "aerospace", "manufactur", "construct", "transport", "logistic"],
    "mat": ["material", "commodity", "metal", "mining", "steel", "copper", "lithium", "battery", "chemical"],
}


def infer_sector_key(sector_str: str) -> str:
    """Map a free-text sector string to a SECTOR_CONFIG key, falling back to 'oth'."""
    s = (sector_str or "").lower()
    for key, keywords in _SECTOR_KEYWORD_MAP.items():
        if any(kw in s for kw in keywords):
            return key
    return "oth"


def build_sector_view(reports: dict[str, "ResearchReport"]) -> dict[str, dict]:
    """Return SECTOR_CONFIG enriched with tickers extracted from reports."""
    result: dict[str, dict] = copy.deepcopy(SECTOR_CONFIG)
    for cfg in result.values():
        cfg["tickers"] = []

    for ticker, report in sorted(reports.items()):
        analysis = report.analysis
        sector_raw = str(analysis.get("sector") or "")
        sector_key = sector_raw if sector_raw in result else infer_sector_key(sector_raw)
        result[sector_key]["tickers"].append({
            "ticker": ticker,
            "company": str(analysis.get("company") or ""),
            "action": str(analysis.get("action") or ""),
            "watch_triggers": list(analysis.get("watch_triggers") or []),
        })

    return result
