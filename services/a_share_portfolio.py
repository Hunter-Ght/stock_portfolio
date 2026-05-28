"""A-share position persistence and price refresh."""
from __future__ import annotations

import json
from pathlib import Path

from importers.base import Position
from services.a_share_market_data import get_a_share_quotes
from services.a_share_names import get_a_share_name, normalize_a_share_code


ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT_DIR / "data"
A_SHARE_POSITIONS_FILE = DATA_DIR / "a_share_positions.json"


def load_a_share_positions(path: Path | None = None) -> list[Position]:
    positions_path = path or A_SHARE_POSITIONS_FILE
    if not positions_path.exists():
        return []
    try:
        data = json.loads(positions_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    items = data.get("positions") if isinstance(data, dict) else data
    if not isinstance(items, list):
        return []
    positions = []
    for item in items:
        if not isinstance(item, dict):
            continue
        position = Position.from_dict(item)
        code = normalize_a_share_code(position.symbol)
        if not code:
            continue
        position.symbol = code
        position.currency = "CNY"
        position.asset_type = "stock"
        position.compute_derived()
        positions.append(position)
    return positions


def save_a_share_positions(positions: list[Position], path: Path | None = None) -> None:
    positions_path = path or A_SHARE_POSITIONS_FILE
    positions_path.parent.mkdir(parents=True, exist_ok=True)
    clean = []
    for position in positions:
        code = normalize_a_share_code(position.symbol)
        if not code:
            continue
        position.symbol = code
        position.currency = "CNY"
        position.asset_type = "stock"
        position.compute_derived()
        clean.append(position.to_dict())
    positions_path.write_text(json.dumps({"positions": clean}, indent=2, ensure_ascii=False), encoding="utf-8")


def add_a_share_position(
    symbol: str,
    quantity: float,
    avg_cost: float,
    name: str = "",
    path: Path | None = None,
) -> None:
    code = normalize_a_share_code(symbol)
    if not code or quantity <= 0 or avg_cost <= 0:
        return
    positions = load_a_share_positions(path=path)
    description = name.strip() or get_a_share_name(code)
    position = Position(
        broker="A股",
        symbol=code,
        description=description,
        quantity=quantity,
        avg_cost=avg_cost,
        current_price=avg_cost,
        currency="CNY",
        asset_type="stock",
    )
    position.compute_derived()
    replaced = False
    for index, existing in enumerate(positions):
        if existing.symbol == code:
            position.id = existing.id
            positions[index] = position
            replaced = True
            break
    if not replaced:
        positions.append(position)
    save_a_share_positions(positions, path=path)
    update_a_share_price(code, path=path)


def remove_a_share_position(position_id: str, path: Path | None = None) -> None:
    save_a_share_positions(
        [position for position in load_a_share_positions(path=path) if position.id != position_id],
        path=path,
    )


def update_a_share_prices(positions: list[Position], path: Path | None = None) -> list[Position]:
    quotes = get_a_share_quotes([position.symbol for position in positions])
    updated = False
    for position in positions:
        quote = quotes.get(normalize_a_share_code(position.symbol))
        updated = _apply_quote(position, quote) or updated
    if updated:
        save_a_share_positions(positions, path=path)
    return positions


def update_a_share_price(symbol: str, path: Path | None = None) -> list[Position]:
    code = normalize_a_share_code(symbol)
    positions = load_a_share_positions(path=path)
    if not code:
        return positions
    quote = get_a_share_quotes([code]).get(code)
    updated = False
    for position in positions:
        if normalize_a_share_code(position.symbol) != code:
            position.compute_derived()
            continue
        updated = _apply_quote(position, quote) or updated
    if updated:
        save_a_share_positions(positions, path=path)
    return positions


def _apply_quote(position: Position, quote: dict | None) -> bool:
    if not quote:
        position.compute_derived()
        return False
    position.current_price = quote["price"]
    position.day_change = quote.get("day_change", 0.0)
    position.day_change_pct = quote.get("day_change_pct", 0.0)
    if quote.get("name") and not position.description:
        position.description = quote["name"]
    position.compute_derived()
    return True


def get_a_share_portfolio_summary(positions: list[Position]) -> dict:
    total_market_value = sum(position.market_value for position in positions)
    total_cost_basis = sum(position.cost_basis for position in positions)
    total_pnl = total_market_value - total_cost_basis
    total_pnl_pct = (total_pnl / total_cost_basis * 100) if total_cost_basis else 0.0
    total_day_change = sum((position.day_change or 0.0) * position.quantity for position in positions)
    total_day_change_pct = (total_day_change / (total_market_value - total_day_change) * 100) if total_market_value != total_day_change else 0.0
    return {
        "total_market_value": total_market_value,
        "total_cost_basis": total_cost_basis,
        "total_pnl": total_pnl,
        "total_pnl_pct": total_pnl_pct,
        "total_day_change": total_day_change,
        "total_day_change_pct": total_day_change_pct,
        "position_count": len(positions),
    }
