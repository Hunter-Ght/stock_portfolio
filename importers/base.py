"""
基础导入器 - 定义持仓数据结构和导入接口
"""
from dataclasses import dataclass, field, asdict
from typing import List, Optional
import pandas as pd
from abc import ABC, abstractmethod
import uuid


@dataclass
class Position:
    """单个持仓数据结构"""
    id: str = ""
    broker: str = ""            # 券商名: IBKR, Schwab, Manual
    symbol: str = ""            # 股票代码
    description: str = ""       # 股票名称/描述
    quantity: float = 0.0       # 持仓数量 (负数 = 空头)
    avg_cost: float = 0.0       # 买入均价
    currency: str = "USD"       # 货币
    fx_rate: float = 1.0        # 汇率到基础货币(通常为USD)
    asset_type: str = "stock"   # 资产类型: stock, option, cash

    # 以下字段由实时行情填充
    current_price: float = 0.0
    market_value: float = 0.0
    cost_basis: float = 0.0
    unrealized_pnl: float = 0.0
    unrealized_pnl_pct: float = 0.0
    day_change: float = 0.0
    day_change_pct: float = 0.0

    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())[:8]
        # 标准化 symbol
        self.symbol = self.symbol.upper().strip()
        # 自动检测期权
        if self.asset_type == "stock" and self._looks_like_option():
            self.asset_type = "option"

    def _looks_like_option(self) -> bool:
        """检测 symbol 是否像期权代码"""
        import re
        return bool(re.match(r'^[A-Z]+\s+\d{6}[CP]\d{8}$', self.symbol))

    def compute_derived(self):
        """根据当前价格计算衍生字段，应用汇率"""
        if self.asset_type == "cash":
            # 现金: 没有盈亏概念
            self.market_value = self.quantity * self.fx_rate
            self.cost_basis = self.quantity * self.fx_rate
            self.unrealized_pnl = 0.0
            self.unrealized_pnl_pct = 0.0
            return

        self.cost_basis = self.quantity * self.avg_cost * self.fx_rate
        self.market_value = self.quantity * self.current_price * self.fx_rate

        if self.quantity > 0:
            # 多头: 盈亏 = 市值 - 成本
            if self.cost_basis > 0:
                self.unrealized_pnl = self.market_value - self.cost_basis
                self.unrealized_pnl_pct = (self.unrealized_pnl / self.cost_basis) * 100
            else:
                self.unrealized_pnl = 0.0
                self.unrealized_pnl_pct = 0.0
        elif self.quantity < 0:
            # 空头: 盈亏 = 收到的权利金 - 当前回购成本
            # cost_basis 为负值(代表收到的钱), market_value 为负值(代表需要回购的成本)
            # PnL = -(market_value - cost_basis) = cost_basis的绝对值 - market_value的绝对值
            self.unrealized_pnl = -(self.market_value - self.cost_basis)
            abs_cost = abs(self.cost_basis)
            if abs_cost > 0:
                self.unrealized_pnl_pct = (self.unrealized_pnl / abs_cost) * 100
            else:
                self.unrealized_pnl_pct = 0.0

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'Position':
        # 只取 Position 字段认识的 key
        valid_keys = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


class BaseImporter(ABC):
    """导入器基类"""

    BROKER_NAME: str = ""

    # 列名映射表: 标准名 -> 可能的列名列表
    COLUMN_MAPPINGS: dict = {}

    def parse(self, df: pd.DataFrame) -> List[Position]:
        """解析 DataFrame 为持仓列表"""
        # 标准化列名
        mapped_df = self._map_columns(df)

        # 转换为 Position 列表
        positions = []
        for _, row in mapped_df.iterrows():
            pos = self._row_to_position(row)
            if pos and pos.symbol and pos.quantity != 0:
                positions.append(pos)

        return positions

    def _map_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """将各种列名映射到标准列名"""
        col_map = {}
        df_cols_lower = {c.lower().strip(): c for c in df.columns}

        for standard_name, possible_names in self.COLUMN_MAPPINGS.items():
            for name in possible_names:
                if name.lower() in df_cols_lower:
                    col_map[df_cols_lower[name.lower()]] = standard_name
                    break

        if col_map:
            df = df.rename(columns=col_map)

        return df

    @abstractmethod
    def _row_to_position(self, row: pd.Series) -> Optional[Position]:
        """将一行数据转换为 Position（子类实现）"""
        pass

    @classmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        """检测 DataFrame 是否匹配此导入器"""
        cols_lower = [c.lower().strip() for c in df.columns]
        # 看是否能匹配到足够多的列
        match_count = 0
        for possible_names in cls.COLUMN_MAPPINGS.values():
            for name in possible_names:
                if name.lower() in cols_lower:
                    match_count += 1
                    break
        return match_count >= 2  # 至少匹配2个标准列
