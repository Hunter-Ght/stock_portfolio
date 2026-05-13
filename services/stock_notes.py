"""Local per-ticker notes for the stock workbench."""
from __future__ import annotations

import json
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
STOCK_NOTES_FILE = DATA_DIR / "stock_notes.json"


def load_stock_notes(path: Path | None = None) -> dict[str, str]:
    notes_path = path or STOCK_NOTES_FILE
    if not notes_path.exists():
        return {}
    try:
        data = json.loads(notes_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    notes: dict[str, str] = {}
    for raw_symbol, raw_note in data.items():
        symbol = str(raw_symbol or "").upper().strip()
        note = str(raw_note or "").strip()
        if symbol and note:
            notes[symbol] = note
    return dict(sorted(notes.items()))


def save_stock_notes(notes: dict[str, str], path: Path | None = None) -> None:
    notes_path = path or STOCK_NOTES_FILE
    notes_path.parent.mkdir(parents=True, exist_ok=True)
    clean = {
        str(symbol).upper().strip(): str(note).strip()
        for symbol, note in notes.items()
        if str(symbol).strip() and str(note).strip()
    }
    notes_path.write_text(json.dumps(dict(sorted(clean.items())), indent=2, ensure_ascii=False), encoding="utf-8")


def set_stock_note(symbol: str, note: str, path: Path | None = None) -> None:
    symbol = symbol.upper().strip()
    if not symbol:
        return
    notes = load_stock_notes(path=path)
    cleaned_note = note.strip()
    if cleaned_note:
        notes[symbol] = cleaned_note
    else:
        notes.pop(symbol, None)
    save_stock_notes(notes, path=path)
