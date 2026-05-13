"""Price-zone alert evaluation for manually imported stock research reports."""
from __future__ import annotations

from typing import Any


def evaluate_price_alerts(symbol: str, current_price: float | None, price_plan: dict, config: dict | None = None) -> list[dict]:
    config = config or {}
    if not config.get("enabled", True) or not current_price:
        return []

    threshold_pct = float(config.get("threshold_pct", 3.0))
    alerts: list[dict] = []

    invalid_price = _as_float(price_plan.get("invalid_price"))
    hard_stop = _as_float(price_plan.get("hard_stop"))
    if config.get("exit_alert_enabled", True):
        if hard_stop is not None and current_price <= hard_stop:
            alerts.append(_alert(symbol, "exit", "跌破 Hard Stop", current_price, hard_stop))
            return alerts
        if invalid_price is not None and current_price <= invalid_price:
            alerts.append(_alert(symbol, "exit", "跌破失效价", current_price, invalid_price))
            return alerts

    if config.get("buy_alert_enabled", True):
        buy_alert = _range_alert(symbol, "buy", "接近买入区", current_price, price_plan.get("buy_zone"), threshold_pct)
        if buy_alert:
            alerts.append(buy_alert)

    if config.get("add_alert_enabled", True):
        add_alert = _range_alert(symbol, "add", "接近加仓区", current_price, price_plan.get("add_zone"), threshold_pct)
        if add_alert:
            alerts.append(add_alert)

    if config.get("trim_alert_enabled", True):
        trim_alert = _range_alert(symbol, "trim", "接近减仓/止盈区", current_price, price_plan.get("trim_zone"), threshold_pct)
        if trim_alert:
            alerts.append(trim_alert)

    return alerts


def _range_alert(symbol: str, alert_type: str, label: str, price: float, zone: Any, threshold_pct: float) -> dict | None:
    parsed = _parse_zone(zone)
    if not parsed:
        return None
    low, high = parsed
    if low <= price <= high:
        return _alert(symbol, alert_type, f"进入{label.replace('接近', '')}", price, [low, high])

    nearest = low if price < low else high
    distance_pct = abs(price / nearest - 1) * 100 if nearest else 999
    if distance_pct <= threshold_pct:
        return _alert(symbol, alert_type, label, price, [low, high], round(distance_pct, 2))
    return None


def _parse_zone(zone: Any) -> tuple[float, float] | None:
    if not isinstance(zone, (list, tuple)) or len(zone) != 2:
        return None
    low = _as_float(zone[0])
    high = _as_float(zone[1])
    if low is None or high is None:
        return None
    return (min(low, high), max(low, high))


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _alert(symbol: str, alert_type: str, label: str, price: float, target: Any, distance_pct: float | None = None) -> dict:
    message = f"{symbol} {label}: 当前价 {price:.2f}, 目标 {target}"
    if distance_pct is not None:
        message += f", 距离约 {distance_pct:.2f}%"
    return {
        "symbol": symbol,
        "type": alert_type,
        "label": label,
        "price": price,
        "target": target,
        "distance_pct": distance_pct,
        "message": message,
    }
