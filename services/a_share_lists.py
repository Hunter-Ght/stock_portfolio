"""A-share watchlist and closed-review list persistence with one-time migration."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from services.a_share_names import normalize_a_share_code
from services.closed_positions import CLOSED_POSITIONS_FILE
from services.watchlist import WATCHLIST_FILE


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
A_SHARE_WATCHLIST_FILE = DATA_DIR / "a_share_watchlist.json"
A_SHARE_CLOSED_FILE = DATA_DIR / "a_share_closed_positions.json"


def load_a_share_watchlist(
    path: Path | None = None,
    source_watchlist_path: Path | None = None,
) -> list[dict]:
    target = path or A_SHARE_WATCHLIST_FILE
    source = source_watchlist_path or WATCHLIST_FILE
    _migrate_a_share_items(source, target)
    return _load_symbol_items(target, default_key="symbols")


def add_a_share_watchlist(symbol: str, notes: str = "", path: Path | None = None) -> None:
    _add_item(path or A_SHARE_WATCHLIST_FILE, symbol, notes, date_key="created_at")


def remove_a_share_watchlist(symbol: str, path: Path | None = None) -> None:
    _remove_item(path or A_SHARE_WATCHLIST_FILE, symbol)


def load_a_share_closed_positions(
    path: Path | None = None,
    source_closed_path: Path | None = None,
) -> list[dict]:
    target = path or A_SHARE_CLOSED_FILE
    source = source_closed_path or CLOSED_POSITIONS_FILE
    _migrate_a_share_items(source, target)
    return _load_symbol_items(target, default_key="symbols")


def add_a_share_closed_position(symbol: str, notes: str = "", path: Path | None = None) -> None:
    _add_item(path or A_SHARE_CLOSED_FILE, symbol, notes, date_key="closed_at")


def remove_a_share_closed_position(symbol: str, path: Path | None = None) -> None:
    _remove_item(path or A_SHARE_CLOSED_FILE, symbol)


def _migrate_a_share_items(source_path: Path, target_path: Path) -> None:
    source_items = _load_symbol_items(source_path, default_key="symbols")
    if not source_items:
        return
    a_items = [item for item in source_items if _is_a_share_symbol(item["symbol"])]
    if not a_items:
        return
    us_items = [item for item in source_items if not _is_a_share_symbol(item["symbol"])]
    target_items = _load_symbol_items(target_path, default_key="symbols")
    target_symbols = {item["symbol"] for item in target_items}
    for item in a_items:
        if item["symbol"] not in target_symbols:
            target_items.append(item)
            target_symbols.add(item["symbol"])
    _save_symbol_items(target_path, target_items)
    _save_symbol_items(source_path, us_items)


def _load_symbol_items(path: Path, default_key: str) -> list[dict]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = data.get(default_key) if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    result = []
    seen = set()
    for item in items:
        if isinstance(item, str):
            copied = {"symbol": item, "notes": ""}
        elif isinstance(item, dict):
            copied = dict(item)
        else:
            continue
        symbol = str(copied.get("symbol") or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        copied["symbol"] = symbol
        copied.setdefault("notes", "")
        result.append(copied)
    return result


def _save_symbol_items(path: Path, items: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean = []
    seen = set()
    for item in items:
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        copied = dict(item)
        copied["symbol"] = symbol
        copied.setdefault("notes", "")
        clean.append(copied)
    path.write_text(json.dumps({"symbols": clean}, indent=2, ensure_ascii=False), encoding="utf-8")


def _add_item(path: Path, symbol: str, notes: str, date_key: str) -> None:
    symbol = symbol.upper().strip()
    if not _is_a_share_symbol(symbol):
        return
    items = _load_symbol_items(path, default_key="symbols")
    if any(item["symbol"] == symbol for item in items):
        return
    items.append({
        "symbol": symbol,
        "notes": notes,
        date_key: datetime.now().date().isoformat(),
    })
    _save_symbol_items(path, items)


def _remove_item(path: Path, symbol: str) -> None:
    symbol = symbol.upper().strip()
    _save_symbol_items(
        path,
        [item for item in _load_symbol_items(path, default_key="symbols") if item["symbol"] != symbol],
    )


def _is_a_share_symbol(symbol: str) -> bool:
    return bool(normalize_a_share_code(symbol))
