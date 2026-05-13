"""Local watchlist persistence for the stock workbench."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"
ALERT_CONFIG_FILE = DATA_DIR / "alert_config.json"


def load_watchlist() -> list[dict]:
    if not WATCHLIST_FILE.exists():
        return []
    try:
        data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    symbols = data.get("symbols") if isinstance(data, dict) else data
    if not isinstance(symbols, list):
        return []
    result = []
    for item in symbols:
        if isinstance(item, str):
            result.append({"symbol": item.upper().strip(), "tags": [], "notes": "", "alert_enabled": True})
        elif isinstance(item, dict) and item.get("symbol"):
            copied = dict(item)
            copied["symbol"] = str(copied["symbol"]).upper().strip()
            copied.setdefault("tags", [])
            copied.setdefault("notes", "")
            copied.setdefault("alert_enabled", True)
            result.append(copied)
    return [item for item in result if item["symbol"]]


def save_watchlist(items: list[dict]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    clean = []
    seen = set()
    for item in items:
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        clean.append({
            "symbol": symbol,
            "tags": item.get("tags") or [],
            "notes": item.get("notes") or "",
            "created_at": item.get("created_at") or datetime.now().date().isoformat(),
            "alert_enabled": bool(item.get("alert_enabled", True)),
        })
    WATCHLIST_FILE.write_text(json.dumps({"symbols": clean}, indent=2, ensure_ascii=False), encoding="utf-8")


def add_to_watchlist(symbol: str, notes: str = "", tags: list[str] | None = None) -> None:
    symbol = symbol.upper().strip()
    if not symbol:
        return
    items = load_watchlist()
    if any(item["symbol"] == symbol for item in items):
        return
    items.append({
        "symbol": symbol,
        "tags": tags or [],
        "notes": notes,
        "created_at": datetime.now().date().isoformat(),
        "alert_enabled": True,
    })
    save_watchlist(items)


def remove_from_watchlist(symbol: str) -> None:
    symbol = symbol.upper().strip()
    save_watchlist([item for item in load_watchlist() if item["symbol"] != symbol])


def load_alert_config() -> dict:
    default = {
        "global_enabled": True,
        "default_threshold_pct": 3.0,
        "tickers": {},
    }
    if not ALERT_CONFIG_FILE.exists():
        return default
    try:
        data = json.loads(ALERT_CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return default
    if not isinstance(data, dict):
        return default
    return {**default, **data}


def save_alert_config(config: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    ALERT_CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")


def ticker_alert_config(symbol: str, config: dict | None = None) -> dict:
    config = config or load_alert_config()
    ticker_config = (config.get("tickers") or {}).get(symbol.upper(), {})
    return {
        "enabled": bool(config.get("global_enabled", True) and ticker_config.get("enabled", True)),
        "buy_alert_enabled": bool(ticker_config.get("buy_alert_enabled", True)),
        "add_alert_enabled": bool(ticker_config.get("add_alert_enabled", True)),
        "trim_alert_enabled": bool(ticker_config.get("trim_alert_enabled", True)),
        "exit_alert_enabled": bool(ticker_config.get("exit_alert_enabled", True)),
        "threshold_pct": float(ticker_config.get("threshold_pct", config.get("default_threshold_pct", 3.0))),
    }
