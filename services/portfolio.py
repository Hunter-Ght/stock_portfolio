"""
持仓管理服务 - CRUD、聚合、JSON 持久化
"""
import json
import os
import re
from typing import List, Optional, Dict
from importers.base import Position
from services.market_data import get_quotes, get_sectors
from services.spread_detector import is_option, parse_option_symbol

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data')
PORTFOLIO_FILE = os.path.join(DATA_DIR, 'portfolio.json')


def _occ_to_yf_symbol(option_symbol: str) -> Optional[str]:
    """将 IBKR OCC 期权代码转为 yfinance 格式
    'ASTS  260918C00110000' → 'ASTS260918C00110000'
    """
    info = parse_option_symbol(option_symbol)
    if not info:
        return None
    yy = info.expiry[:2]
    mm = info.expiry[2:4]
    dd = info.expiry[4:6]
    strike_int = int(info.strike * 1000)
    return f"{info.underlying}{yy}{mm}{dd}{info.option_type}{strike_int:08d}"


def _fetch_option_prices(option_positions: List[Position]) -> Dict[str, float]:
    """通过 yfinance 获取期权最新收盘价（per-share，即期权报价单位）
    返回 {occ_symbol: latest_close}
    """
    import yfinance as yf
    from concurrent.futures import ThreadPoolExecutor, as_completed

    result = {}

    def _fetch(sym: str):
        yf_sym = _occ_to_yf_symbol(sym)
        if not yf_sym:
            return sym, 0.0
        try:
            hist = yf.Ticker(yf_sym).history(period='2d')
            if hist.empty:
                return sym, 0.0
            closes = hist['Close'].dropna()
            return sym, float(closes.iloc[-1]) if len(closes) > 0 else 0.0
        except Exception:
            return sym, 0.0

    symbols = [p.symbol for p in option_positions if p.symbol]
    with ThreadPoolExecutor(max_workers=5) as ex:
        futures = [ex.submit(_fetch, s) for s in symbols]
        for f in as_completed(futures):
            try:
                sym, price = f.result()
                if price > 0:
                    result[sym] = price
            except Exception:
                continue
    return result


def ensure_data_dir():
    """确保数据目录存在"""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_positions() -> List[Position]:
    """从 JSON 文件加载持仓数据"""
    ensure_data_dir()
    if not os.path.exists(PORTFOLIO_FILE):
        return []

    try:
        with open(PORTFOLIO_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
        positions = [Position.from_dict(d) for d in data]
        # 重新计算衍生字段，确保价格乘数等逻辑生效
        for p in positions:
            p.compute_derived()
        return positions
    except (json.JSONDecodeError, Exception):
        return []


def save_positions(positions: List[Position]):
    """保存持仓数据到 JSON 文件"""
    ensure_data_dir()
    data = [p.to_dict() for p in positions]
    with open(PORTFOLIO_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_positions(new_positions: List[Position], replace_broker: bool = False):
    """
    添加持仓

    Args:
        new_positions: 新的持仓列表
        replace_broker: 如果为 True，则替换同一券商的所有持仓（但保留现金）
    """
    existing = load_positions()

    if replace_broker and new_positions:
        broker = new_positions[0].broker
        # 移除同一券商的旧持仓（但保留现金条目，除非新数据也包含现金）
        new_has_cash = any(p.asset_type == 'cash' for p in new_positions)
        if new_has_cash:
            existing = [p for p in existing if p.broker != broker]
        else:
            existing = [p for p in existing if p.broker != broker or p.asset_type == 'cash']

    # 合并同券商同 symbol 的持仓
    for new_pos in new_positions:
        found = False
        for i, existing_pos in enumerate(existing):
            if existing_pos.broker == new_pos.broker and existing_pos.symbol == new_pos.symbol:
                existing[i] = new_pos
                found = True
                break
        if not found:
            existing.append(new_pos)

    save_positions(existing)


def add_cash(broker: str, amount: float, currency: str = "USD"):
    """添加或更新某券商的现金余额"""
    positions = load_positions()

    cash_symbol = f"CASH_{currency}"

    # 查找已有的现金条目
    found = False
    for i, p in enumerate(positions):
        if p.broker == broker and p.symbol == cash_symbol and p.asset_type == 'cash':
            positions[i].quantity = amount
            positions[i].market_value = amount
            positions[i].cost_basis = amount
            found = True
            break

    if not found:
        cash_pos = Position(
            broker=broker,
            symbol=cash_symbol,
            description=f"Cash Balance ({currency})",
            quantity=amount,
            avg_cost=1.0,
            current_price=1.0,
            currency=currency,
            asset_type="cash",
        )
        cash_pos.compute_derived()
        positions.append(cash_pos)

    save_positions(positions)


def remove_position(position_id: str):
    """删除单个持仓"""
    positions = load_positions()
    positions = [p for p in positions if p.id != position_id]
    save_positions(positions)


def remove_broker_positions(broker: str):
    """删除某券商的所有持仓"""
    positions = load_positions()
    positions = [p for p in positions if p.broker != broker]
    save_positions(positions)


def clear_all_positions():
    """清空所有持仓"""
    save_positions([])


def update_prices(positions: List[Position]) -> List[Position]:
    """
    用实时行情更新持仓价格

    Returns:
        更新后的持仓列表
    """
    if not positions:
        return positions

    # 收集需要查行情的 symbol（排除现金和期权）
    symbols_to_fetch = list(set(
        p.symbol for p in positions
        if p.symbol and p.asset_type != 'cash' and not is_option(p.symbol)
    ))

    # 收集期权持仓（单独处理）
    option_positions = [p for p in positions if is_option(p.symbol)]

    # 批量获取正股行情
    quotes = get_quotes(symbols_to_fetch)

    # 批量获取期权行情（通过 yfinance Ticker 逐个查询）
    option_quotes = _fetch_option_prices(option_positions)

    # 更新每个持仓
    updated_count = 0
    for pos in positions:
        if pos.asset_type == 'cash':
            pos.compute_derived()
            continue

        if pos.symbol in quotes:
            quote = quotes[pos.symbol]
            if quote['price'] > 0:
                pos.current_price = quote['price']
                pos.day_change = quote['day_change']
                pos.day_change_pct = quote['day_change_pct']
                updated_count += 1
            pos.compute_derived()
        elif is_option(pos.symbol):
            # 用 yfinance 获取期权最新价格（per-share）
            if pos.symbol in option_quotes:
                pos.current_price = option_quotes[pos.symbol]
                updated_count += 1
            pos.compute_derived()

    # 更新后保存到 JSON，下次打开直接用新价格
    if updated_count > 0:
        # 补全缺失的行业数据
        missing_sector = list(set(
            p.symbol for p in positions
            if p.asset_type != 'cash' and not p.sector and not is_option(p.symbol)
        ))
        if missing_sector:
            sectors = get_sectors(missing_sector)
            for pos in positions:
                if pos.symbol in sectors and not pos.sector:
                    pos.sector = sectors[pos.symbol]

        save_positions(positions)

    return positions


def get_portfolio_summary(positions: List[Position]) -> dict:
    """
    计算投资组合汇总信息，包含现金

    Returns:
        {
            'total_market_value': 总市值 (含现金),
            'total_cost_basis': 总成本,
            'total_pnl': 总盈亏,
            'total_pnl_pct': 总盈亏百分比,
            'total_day_change': 今日变动,
            'total_cash': 现金总额,
            'position_count': 持仓数量,
            'broker_summary': { ... },
        }
    """
    # 分离现金和投资仓位
    cash_positions = [p for p in positions if p.asset_type == 'cash']
    invest_positions = [p for p in positions if p.asset_type != 'cash']

    total_cash = sum(p.quantity for p in cash_positions)

    # 投资仓位的市值和成本
    invest_market_value = sum(p.market_value for p in invest_positions)
    invest_cost_basis = sum(p.cost_basis for p in invest_positions)
    invest_pnl = invest_market_value - invest_cost_basis

    # 总资产 = 投资市值 + 现金
    total_market_value = invest_market_value + total_cash
    total_pnl_pct = (invest_pnl / invest_cost_basis * 100) if invest_cost_basis else 0

    # 今日变动
    total_day_change = sum(
        p.day_change * p.quantity for p in invest_positions
        if p.asset_type != 'cash'
    )

    # 按券商分组
    broker_summary = {}
    for pos in positions:
        if pos.broker not in broker_summary:
            broker_summary[pos.broker] = {
                'market_value': 0,
                'cost_basis': 0,
                'pnl': 0,
                'position_count': 0,
                'cash': 0,
            }
        b = broker_summary[pos.broker]
        if pos.asset_type == 'cash':
            b['cash'] += pos.quantity
            b['market_value'] += pos.quantity
        else:
            b['market_value'] += pos.market_value
            b['cost_basis'] += pos.cost_basis
            b['pnl'] += pos.unrealized_pnl
            b['position_count'] += 1

    for broker, b in broker_summary.items():
        b['pnl_pct'] = (b['pnl'] / b['cost_basis'] * 100) if b['cost_basis'] else 0
        b['allocation_pct'] = (b['market_value'] / total_market_value * 100) if total_market_value else 0

    return {
        'total_market_value': total_market_value,
        'total_cost_basis': invest_cost_basis,
        'total_pnl': invest_pnl,
        'total_pnl_pct': total_pnl_pct,
        'total_day_change': total_day_change,
        'total_cash': total_cash,
        'position_count': len(invest_positions),
        'broker_summary': broker_summary,
    }
