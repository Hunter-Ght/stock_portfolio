"""A-share quote helpers using EastMoney with a Sina fallback."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

from services.a_share_names import normalize_a_share_code


def get_a_share_quotes(symbols: list[str]) -> dict[str, dict]:
    quotes = {}
    for raw_symbol in symbols:
        code = normalize_a_share_code(raw_symbol)
        if not code:
            continue
        quote = _fetch_eastmoney_quote(code) or _fetch_sina_quote(code)
        if quote:
            quotes[code] = quote
    return quotes


def _fetch_eastmoney_quote(code: str) -> dict:
    secid = _eastmoney_secid(code)
    if not secid:
        return {}
    fields = "f43,f44,f45,f46,f57,f58,f60,f168,f169,f170"
    params = urllib.parse.urlencode({"secid": secid, "fields": fields})
    url = f"https://push2.eastmoney.com/api/qt/stock/get?{params}"
    try:
        with urllib.request.urlopen(url, timeout=4) as response:
            payload = json.loads(response.read().decode("utf-8", errors="ignore"))
    except Exception:
        return {}
    data = payload.get("data") if isinstance(payload, dict) else {}
    if not isinstance(data, dict):
        return {}
    price = _eastmoney_price(data.get("f43"))
    previous_close = _eastmoney_price(data.get("f60")) or 0.0
    day_change = _eastmoney_price(data.get("f169")) or 0.0
    day_change_pct = _eastmoney_pct(data.get("f170"))
    if not price:
        return {}
    return {
        "price": price,
        "previous_close": previous_close,
        "day_change": day_change,
        "day_change_pct": day_change_pct,
        "name": str(data.get("f58") or "").strip(),
    }


def _eastmoney_price(value) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    raw = str(value or "").strip()
    if isinstance(value, int) or raw.lstrip("-").isdigit():
        return number / 100
    return number


def _eastmoney_pct(value) -> float:
    try:
        return float(value) / 100
    except (TypeError, ValueError):
        return 0.0


def _fetch_sina_quote(code: str) -> dict:
    symbol = _sina_symbol(code)
    if not symbol:
        return {}
    url = f"https://hq.sinajs.cn/list={urllib.parse.quote(symbol)}"
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://finance.sina.com.cn/",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=4) as response:
            text = response.read().decode("gb18030", errors="ignore")
    except Exception:
        return {}
    return _parse_sina_quote_response(text)


def _parse_sina_quote_response(text: str) -> dict:
    match = re.search(r'="(.*)"', text or "")
    if not match:
        return {}
    fields = match.group(1).split(",")
    if len(fields) < 4:
        return {}
    name = fields[0].strip()
    previous_close = _float_or_zero(fields[2])
    price = _float_or_zero(fields[3])
    if not name or not price:
        return {}
    day_change = price - previous_close if previous_close else 0.0
    day_change_pct = day_change / previous_close * 100 if previous_close else 0.0
    return {
        "price": round(price, 3),
        "previous_close": round(previous_close, 3),
        "day_change": round(day_change, 3),
        "day_change_pct": round(day_change_pct, 4),
        "name": name,
    }


def _float_or_zero(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _sina_symbol(code: str) -> str:
    if code.startswith(("5", "6", "9")):
        return f"sh{code}"
    if code.startswith(("0", "2", "3")):
        return f"sz{code}"
    if code.startswith(("4", "8")):
        return f"bj{code}"
    return ""


def _eastmoney_secid(code: str) -> str:
    if code.startswith(("5", "6", "9")):
        return f"1.{code}"
    if code.startswith(("0", "2", "3", "4", "8")):
        return f"0.{code}"
    return ""
