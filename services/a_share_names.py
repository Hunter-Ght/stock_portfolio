"""A-share code/name helpers for the stock workbench."""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
A_SHARE_NAMES_FILE = DATA_DIR / "a_share_names.json"


def normalize_a_share_code(symbol: str) -> str:
    raw = str(symbol or "").upper().strip()
    code = raw.split(".", 1)[0]
    return code if len(code) == 6 and code.isdigit() else ""


def load_a_share_names(path: Path | None = None) -> dict[str, str]:
    names_path = path or A_SHARE_NAMES_FILE
    if not names_path.exists():
        return {}
    try:
        data = json.loads(names_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(data, dict):
        return {}
    names = {}
    for raw_code, raw_name in data.items():
        code = normalize_a_share_code(str(raw_code))
        name = str(raw_name or "").strip()
        if code and name:
            names[code] = name
    return dict(sorted(names.items()))


def save_a_share_names(names: dict[str, str], path: Path | None = None) -> None:
    names_path = path or A_SHARE_NAMES_FILE
    names_path.parent.mkdir(parents=True, exist_ok=True)
    clean = {}
    for raw_code, raw_name in names.items():
        code = normalize_a_share_code(str(raw_code))
        name = str(raw_name or "").strip()
        if code and name:
            clean[code] = name
    names_path.write_text(json.dumps(dict(sorted(clean.items())), indent=2, ensure_ascii=False), encoding="utf-8")


def set_a_share_name(symbol: str, name: str, path: Path | None = None) -> None:
    code = normalize_a_share_code(symbol)
    if not code:
        return
    names = load_a_share_names(path=path)
    cleaned_name = name.strip()
    if cleaned_name:
        names[code] = cleaned_name
    else:
        names.pop(code, None)
    save_a_share_names(names, path=path)


def get_a_share_name(symbol: str, fallback_name: str = "") -> str:
    code = normalize_a_share_code(symbol)
    if not code:
        return fallback_name.strip()

    fallback_name = fallback_name.strip()
    if fallback_name:
        set_a_share_name(code, fallback_name)
        return fallback_name

    cached = load_a_share_names().get(code, "")
    if cached:
        return cached

    fetched = _fetch_eastmoney_name(code)
    if fetched:
        set_a_share_name(code, fetched)
    return fetched


def _fetch_eastmoney_name(code: str) -> str:
    secid = _eastmoney_secid(code)
    if not secid:
        return ""
    params = urllib.parse.urlencode({"secid": secid, "fields": "f58"})
    url = f"https://push2.eastmoney.com/api/qt/stock/get?{params}"
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception:
        return ""
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return ""
    return str(data.get("f58") or "").strip()


def _eastmoney_secid(code: str) -> str:
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    if code.startswith(("0", "2", "3")):
        return f"0.{code}"
    if code.startswith(("4", "8")):
        return f"0.{code}"
    return ""
