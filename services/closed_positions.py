"""Local closed-position review pool persistence for the stock workbench."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
CLOSED_POSITIONS_FILE = DATA_DIR / "closed_positions.json"


def load_closed_positions(path: Path | None = None) -> list[dict]:
    closed_path = path or CLOSED_POSITIONS_FILE
    if not closed_path.exists():
        return []
    try:
        data = json.loads(closed_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = data.get("symbols") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []

    result = []
    for item in items:
        if isinstance(item, str):
            copied = {"symbol": item, "notes": "", "closed_at": ""}
        elif isinstance(item, dict):
            copied = dict(item)
        else:
            continue
        symbol = str(copied.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        result.append({
            "symbol": symbol,
            "notes": str(copied.get("notes") or ""),
            "closed_at": str(copied.get("closed_at") or ""),
        })
    return _dedupe(result)


def save_closed_positions(items: list[dict], path: Path | None = None) -> None:
    closed_path = path or CLOSED_POSITIONS_FILE
    closed_path.parent.mkdir(parents=True, exist_ok=True)
    clean = []
    for item in _dedupe(items):
        clean.append({
            "symbol": item["symbol"],
            "notes": item.get("notes") or "",
            "closed_at": item.get("closed_at") or datetime.now().date().isoformat(),
        })
    closed_path.write_text(json.dumps({"symbols": clean}, indent=2, ensure_ascii=False), encoding="utf-8")


def add_closed_position(symbol: str, notes: str = "", path: Path | None = None) -> None:
    symbol = symbol.upper().strip()
    if not symbol:
        return
    items = load_closed_positions(path=path)
    if any(item["symbol"] == symbol for item in items):
        return
    items.append({
        "symbol": symbol,
        "notes": notes,
        "closed_at": datetime.now().date().isoformat(),
    })
    save_closed_positions(items, path=path)


def remove_closed_position(symbol: str, path: Path | None = None) -> None:
    symbol = symbol.upper().strip()
    save_closed_positions(
        [item for item in load_closed_positions(path=path) if item["symbol"] != symbol],
        path=path,
    )


def _dedupe(items: list[dict]) -> list[dict]:
    result = []
    seen = set()
    for item in items:
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        result.append({
            "symbol": symbol,
            "notes": item.get("notes") or "",
            "closed_at": item.get("closed_at") or "",
        })
    return result
