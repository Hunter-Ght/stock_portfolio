"""
期权解析与垂直价差（Spread）识别模块

解析 IBKR OCC 格式期权代码，自动识别垂直价差策略：
- Bull Call Spread (买入看涨 + 卖出更高行权价看涨)
- Bear Put Spread (买入看跌 + 卖出更低行权价看跌)
- Covered Call (持有正股 + 卖出看涨)
"""
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple
from importers.base import Position


@dataclass
class OptionInfo:
    """解析后的期权信息"""
    underlying: str     # 标的代码: GLD, AAPL
    expiry: str         # 到期日: 260618 → 2026-06-18
    option_type: str    # C (Call) / P (Put)
    strike: float       # 行权价: 460.00
    raw_symbol: str     # 原始代码


def parse_option_symbol(symbol: str) -> Optional[OptionInfo]:
    """
    解析 IBKR OCC 格式的期权代码

    格式: UNDERLYING YYMMDD[C/P]SSSSSSSSS
    例:   GLD   260618C00460000  → GLD, 2026-06-18, Call, $460
          ASTS  260918C00110000  → ASTS, 2026-09-18, Call, $110
    """
    s = symbol.strip()

    # 正则匹配: 字母开头 + 空格 + 6位日期 + C/P + 8位数字
    pattern = r'^([A-Z]+)\s+(\d{6})([CP])(\d{8})$'
    match = re.match(pattern, s)

    if not match:
        return None

    underlying = match.group(1)
    expiry = match.group(2)
    opt_type = match.group(3)
    strike_raw = match.group(4)

    # 行权价: 最后 8 位，除以1000
    strike = int(strike_raw) / 1000.0

    return OptionInfo(
        underlying=underlying,
        expiry=expiry,
        option_type=opt_type,
        strike=strike,
        raw_symbol=s,
    )


def is_option(symbol: str) -> bool:
    """判断一个 symbol 是否是期权"""
    return parse_option_symbol(symbol) is not None


@dataclass
class SpreadPosition:
    """一个垂直价差组合"""
    id: str = ""
    broker: str = ""
    spread_type: str = ""           # "Bull Call Spread", "Bear Put Spread", "Covered Call", etc.
    underlying: str = ""            # 标的代码
    expiry: str = ""                # 到期日
    long_strike: float = 0.0       # 买入行权价
    short_strike: float = 0.0      # 卖出行权价
    quantity: int = 0              # 组数
    option_type: str = ""           # C / P
    # 各条腿
    long_leg: Optional[Position] = None
    short_leg: Optional[Position] = None
    stock_leg: Optional[Position] = None  # covered call 的正股

    # 计算字段
    net_debit: float = 0.0         # 净支出 (per spread)
    total_cost: float = 0.0        # 总成本
    current_value: float = 0.0     # 当前价值
    unrealized_pnl: float = 0.0    # 未实现盈亏
    unrealized_pnl_pct: float = 0.0
    max_profit: float = 0.0        # 最大利润 (per spread)
    max_loss: float = 0.0          # 最大亏损 (per spread)

    @property
    def display_name(self) -> str:
        """适合展示的名称"""
        expiry_fmt = f"20{self.expiry[:2]}-{self.expiry[2:4]}-{self.expiry[4:6]}"
        if self.spread_type == "Covered Call":
            return f"{self.underlying} Covered Call ${self.short_strike:.0f} ({expiry_fmt})"
        elif self.spread_type == "Naked Option":
            side = "Call" if self.option_type == "C" else "Put"
            return f"{self.underlying} {side} ${self.long_strike:.0f} ({expiry_fmt})"
        else:
            return f"{self.underlying} {self.spread_type} ${self.long_strike:.0f}/{self.short_strike:.0f} ({expiry_fmt})"

    @property
    def display_symbol(self) -> str:
        """简短代码"""
        if self.spread_type == "Covered Call":
            return f"{self.underlying} CC{self.short_strike:.0f}"
        elif self.spread_type == "Naked Option":
            return f"{self.underlying} {self.option_type}{self.long_strike:.0f}"
        else:
            return f"{self.underlying} {self.long_strike:.0f}/{self.short_strike:.0f}{self.option_type}"

    def compute(self):
        """计算价差组合的价值和盈亏"""
        # 期权合约乘数 (标准美股期权 = 100)
        multiplier = 100

        if self.spread_type == "Covered Call":
            # Covered call: 正股价值 + 卖出期权价值
            if self.stock_leg and self.short_leg:
                stock_mv = abs(self.stock_leg.market_value)
                stock_cost = abs(self.stock_leg.cost_basis)
                # 卖出期权: 收到权利金 (quantity 为负, market_value 为负)
                opt_mv = self.short_leg.market_value * multiplier  # 负值 (空头)
                opt_cost = self.short_leg.cost_basis * multiplier  # 负值

                self.current_value = stock_mv + opt_mv  # stock - option 价值
                self.total_cost = stock_cost + opt_cost  # stock - premium received
                self.unrealized_pnl = self.current_value - self.total_cost
                if self.total_cost != 0:
                    self.unrealized_pnl_pct = (self.unrealized_pnl / abs(self.total_cost)) * 100

        elif self.spread_type == "Naked Option":
            # 裸期权
            if self.long_leg:
                self.current_value = abs(self.long_leg.market_value) * multiplier
                self.total_cost = abs(self.long_leg.cost_basis) * multiplier
                self.unrealized_pnl = self.current_value - self.total_cost
                if self.total_cost != 0:
                    self.unrealized_pnl_pct = (self.unrealized_pnl / abs(self.total_cost)) * 100

        else:
            # 垂直价差
            if self.long_leg and self.short_leg:
                # IBKR 的 avg_cost 和 current_price 是每股(每份合约)的价格
                # 要乘以 multiplier (100) 得到每份合约的实际价值
                long_cost_per_spread = abs(self.long_leg.avg_cost) * multiplier
                short_cost_per_spread = abs(self.short_leg.avg_cost) * multiplier
                long_price_per_spread = abs(self.long_leg.current_price) * multiplier
                short_price_per_spread = abs(self.short_leg.current_price) * multiplier

                # 净支出 (per spread)
                self.net_debit = long_cost_per_spread - short_cost_per_spread

                # 总成本 = 净支出 × 组数
                self.total_cost = self.net_debit * self.quantity

                # 当前价值
                current_value_per = long_price_per_spread - short_price_per_spread
                self.current_value = current_value_per * self.quantity

                # 盈亏
                self.unrealized_pnl = self.current_value - self.total_cost
                if self.total_cost != 0:
                    self.unrealized_pnl_pct = (self.unrealized_pnl / abs(self.total_cost)) * 100

                # 最大利润/亏损 (per spread, for bull call spread)
                spread_width = abs(self.short_strike - self.long_strike) * multiplier
                self.max_profit = spread_width - self.net_debit  # per spread
                self.max_loss = self.net_debit  # per spread


def detect_spreads(positions: List[Position]) -> Tuple[List[SpreadPosition], List[Position], List[Position]]:
    """
    从持仓列表中识别垂直价差组合

    Returns:
        (spreads, remaining_stock_positions, cash_positions)
        - spreads: 识别出的 spread 列表
        - remaining_stock_positions: 未参与 spread 的正股持仓
        - cash_positions: 现金持仓
    """
    # 分离期权和非期权
    options = []          # (OptionInfo, Position)
    stocks = []           # Position (正股)
    cash_positions = []   # Position (现金)

    for pos in positions:
        if getattr(pos, 'asset_type', '') == 'cash':
            cash_positions.append(pos)
            continue

        opt_info = parse_option_symbol(pos.symbol)
        if opt_info:
            options.append((opt_info, pos))
        else:
            stocks.append(pos)

    # 按 (标的, 到期日, 期权类型) 分组
    from collections import defaultdict
    groups = defaultdict(list)
    for opt_info, pos in options:
        key = (opt_info.underlying, opt_info.expiry, opt_info.option_type)
        groups[key].append((opt_info, pos))

    spreads = []
    used_option_ids = set()
    used_stock_ids = set()

    # 对每个分组，尝试配对 long/short 形成 spread
    for (underlying, expiry, opt_type), group in groups.items():
        # 分离多头和空头
        longs = [(info, pos) for info, pos in group if pos.quantity > 0]
        shorts = [(info, pos) for info, pos in group if pos.quantity < 0]

        # 排序: long 按行权价从低到高, short 按行权价从低到高
        longs.sort(key=lambda x: x[0].strike)
        shorts.sort(key=lambda x: x[0].strike)

        # 贪心匹配: 每个 long 尝试与一个 short 配对
        remaining_longs = []
        remaining_shorts = list(shorts)

        for l_info, l_pos in longs:
            l_qty = int(abs(l_pos.quantity))
            matched = False

            for s_idx, (s_info, s_pos) in enumerate(remaining_shorts):
                s_qty = int(abs(s_pos.quantity))
                if s_qty <= 0:
                    continue

                # 配对数量 = min(long数量, short数量)
                spread_qty = min(l_qty, s_qty)

                if spread_qty > 0:
                    # 确定 spread 类型
                    if opt_type == 'C':
                        if l_info.strike < s_info.strike:
                            spread_type = "Bull Call Spread"
                        else:
                            spread_type = "Bear Call Spread"
                    else:  # Put
                        if l_info.strike > s_info.strike:
                            spread_type = "Bear Put Spread"
                        else:
                            spread_type = "Bull Put Spread"

                    spread = SpreadPosition(
                        id=f"sp_{l_pos.id}_{s_pos.id}",
                        broker=l_pos.broker,
                        spread_type=spread_type,
                        underlying=underlying,
                        expiry=expiry,
                        long_strike=l_info.strike,
                        short_strike=s_info.strike,
                        quantity=spread_qty,
                        option_type=opt_type,
                        long_leg=l_pos,
                        short_leg=s_pos,
                    )
                    spread.compute()
                    spreads.append(spread)

                    used_option_ids.add(l_pos.id)
                    used_option_ids.add(s_pos.id)

                    # 更新剩余数量
                    l_qty -= spread_qty
                    remaining_shorts[s_idx] = (s_info, Position(
                        id=s_pos.id, broker=s_pos.broker, symbol=s_pos.symbol,
                        description=s_pos.description,
                        quantity=-(s_qty - spread_qty),
                        avg_cost=s_pos.avg_cost,
                        current_price=s_pos.current_price,
                        currency=s_pos.currency,
                    ))

                    matched = True

            if l_qty > 0:
                remaining_longs.append((l_info, Position(
                    id=l_pos.id, broker=l_pos.broker, symbol=l_pos.symbol,
                    description=l_pos.description,
                    quantity=l_qty,
                    avg_cost=l_pos.avg_cost,
                    current_price=l_pos.current_price,
                    currency=l_pos.currency,
                )))

    # 检查是否有 covered call (正股 + 空头 call，且行权价 > 当前股价)
    # 先找未配对的空头 call
    unmatched_short_calls = []
    for (underlying, expiry, opt_type), group in groups.items():
        if opt_type != 'C':
            continue
        for info, pos in group:
            if pos.id not in used_option_ids and pos.quantity < 0:
                unmatched_short_calls.append((info, pos))

    for s_info, s_pos in unmatched_short_calls:
        # 查找匹配的正股
        for stock in stocks:
            if stock.symbol == s_info.underlying and stock.id not in used_stock_ids:
                s_qty = int(abs(s_pos.quantity))
                stock_lots = int(stock.quantity) // 100  # 每100股可以 cover 一个合约

                if stock_lots > 0 and s_qty > 0:
                    cover_qty = min(stock_lots, s_qty)

                    spread = SpreadPosition(
                        id=f"cc_{stock.id}_{s_pos.id}",
                        broker=stock.broker,
                        spread_type="Covered Call",
                        underlying=s_info.underlying,
                        expiry=s_info.expiry,
                        short_strike=s_info.strike,
                        quantity=cover_qty,
                        option_type='C',
                        stock_leg=stock,
                        short_leg=s_pos,
                    )
                    spread.compute()
                    spreads.append(spread)

                    used_option_ids.add(s_pos.id)
                    used_stock_ids.add(stock.id)
                    break

    # 未配对的裸期权作为 Naked Option
    for (underlying, expiry, opt_type), group in groups.items():
        for info, pos in group:
            if pos.id not in used_option_ids and pos.quantity > 0:
                spread = SpreadPosition(
                    id=f"nk_{pos.id}",
                    broker=pos.broker,
                    spread_type="Naked Option",
                    underlying=underlying,
                    expiry=expiry,
                    long_strike=info.strike,
                    quantity=int(abs(pos.quantity)),
                    option_type=opt_type,
                    long_leg=pos,
                )
                spread.compute()
                spreads.append(spread)
                used_option_ids.add(pos.id)

    # 未参与 spread 的正股
    remaining_stocks = [s for s in stocks if s.id not in used_stock_ids]

    return spreads, remaining_stocks, cash_positions
