"""
Charles Schwab (嘉信理财) CSV 导入器

Schwab 的 Positions 导出格式特点:
- 数值可能带有 ="$xxx" 格式
- 文件开头可能有标题行（非数据行）
- 最后可能有汇总行
- 现金余额在 "Cash & Cash Investments" 行
"""
from typing import Optional, List
import pandas as pd
from .base import BaseImporter, Position
from utils.formatters import clean_numeric_string


class SchwabImporter(BaseImporter):
    BROKER_NAME = "Schwab"

    COLUMN_MAPPINGS = {
        'symbol': [
            'Symbol', 'symbol',
            'Ticker', 'ticker',
        ],
        'description': [
            'Description', 'description',
            'Name', 'Security Name',
            'Security Description',
        ],
        'quantity': [
            'Quantity', 'quantity',
            'Shares', 'shares',
            'Qty', 'Qty (Quantity)',
        ],
        'current_price': [
            'Price', 'price',
            'Last Price', 'Market Price',
            'Current Price',
        ],
        'market_value': [
            'Market Value', 'market value',
            'Mkt Value', 'Value',
            'Current Value', 'Mkt Val (Market Value)',
            'Mkt Val',
        ],
        'avg_cost': [
            'Cost Basis', 'cost basis',
            'Cost/Share', 'Average Cost',
            'Avg Cost', 'Purchase Price',
            'Cost Basis Total',
        ],
        'unrealized_pnl': [
            'Gain/Loss', 'gain/loss',
            'Gain/Loss Dollar', 'Unrealized Gain/Loss',
            'P&L', 'Gain Loss', 'Gain $ (Gain/Loss $)',
            'Gain $',
        ],
        'unrealized_pnl_pct': [
            'Gain/Loss %', 'gain/loss %',
            'Gain/Loss Percent', '% Gain/Loss',
            'Gain % (Gain/Loss %)', 'Gain %',
        ],
    }

    def _row_to_position(self, row: pd.Series) -> Optional[Position]:
        try:
            symbol = str(row.get('symbol', '')).strip()
            description = str(row.get('description', '')).strip()

            # 检查是否是现金行
            symbol_lower = symbol.lower()
            desc_lower = description.lower()
            if any(keyword in symbol_lower or keyword in desc_lower
                   for keyword in ['cash', 'cash & cash investments', 'cash and money market']):
                # 从 market_value 列提取现金余额
                cash_balance = clean_numeric_string(row.get('market_value', 0))
                if cash_balance > 0:
                    return Position(
                        broker=self.BROKER_NAME,
                        symbol="CASH_USD",
                        description="Cash Balance (USD)",
                        quantity=cash_balance,
                        avg_cost=1.0,
                        current_price=1.0,
                        currency="USD",
                        asset_type="cash",
                    )
                return None

            # 过滤汇总行
            if not symbol or symbol.lower() in (
                'total', 'account total', 'positions total', '--',
            ):
                return None

            # 过滤非股票行
            if symbol.startswith('Account'):
                return None

            quantity = clean_numeric_string(row.get('quantity', 0))
            if quantity == 0:
                return None

            current_price = clean_numeric_string(row.get('current_price', 0))
            market_value = clean_numeric_string(row.get('market_value', 0))

            # Schwab 的 Cost Basis 通常是总成本，需要除以数量得到均价
            cost_basis_raw = clean_numeric_string(row.get('avg_cost', 0))

            # 判断是总成本还是单位成本
            # 如果 cost_basis 远大于 current_price，说明是总成本
            if cost_basis_raw > 0 and current_price > 0:
                if cost_basis_raw > current_price * 5 and quantity > 1:
                    # 这是总成本，除以数量
                    avg_cost = cost_basis_raw / quantity
                else:
                    avg_cost = cost_basis_raw
            else:
                avg_cost = cost_basis_raw

            pos = Position(
                broker=self.BROKER_NAME,
                symbol=symbol,
                description=description,
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                currency='USD',
            )
            pos.compute_derived()
            return pos

        except Exception:
            return None

    @classmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        """Schwab 特有检测"""
        cols_lower = [c.lower().strip() for c in df.columns]

        # Schwab 特征列 - 支持不同格式
        schwab_markers = [
            'cost basis', 'gain/loss', 'gain/loss %',
            'mkt val', 'qty (quantity)', 'price chng',
        ]
        if sum(1 for m in schwab_markers if m in cols_lower) >= 2:
            return True

        return super().detect(df)


def preprocess_schwab_csv(file_content) -> pd.DataFrame:
    """
    预处理 Schwab CSV 文件:
    - 跳过文件开头的非数据行
    - 处理 ="$xxx" 格式
    - 移除汇总行
    - 处理 Individual Positions 导出格式（开头有标题行）
    """
    import io

    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8', errors='ignore')

    lines = file_content.strip().split('\n')

    # 找到真正的表头行（包含 Symbol 的行）
    header_idx = 0
    for i, line in enumerate(lines):
        if 'Symbol' in line or 'symbol' in line:
            header_idx = i
            break

    # 只保留表头及之后的数据
    data_lines = lines[header_idx:]

    # 只清理 =" 前缀，不要移除所有引号（否则会破坏CSV格式）
    # 原始文件已经正确使用双引号包裹字段
    cleaned_lines = []
    for line in data_lines:
        line = line.replace('="', '')
        cleaned_lines.append(line)

    if cleaned_lines:
        try:
            return pd.read_csv(io.StringIO('\n'.join(cleaned_lines)))
        except Exception:
            # 如果解析失败，尝试使用更宽松的解析方式
            return pd.read_csv(io.StringIO('\n'.join(cleaned_lines)), on_bad_lines='skip')

    return pd.read_csv(io.StringIO(file_content))
