"""
IBKR (盈透证券) CSV 导入器

支持两种导出格式:
1. TWS Export Portfolio - 简单直接，列名与 TWS 界面一致
2. Flex Query Open Positions - 更标准化，字段更多

同时支持从 Activity Statement 提取现金余额
"""
from typing import Optional, List, Tuple
import pandas as pd
from .base import BaseImporter, Position
from utils.formatters import clean_numeric_string


class IBKRImporter(BaseImporter):
    BROKER_NAME = "IBKR"

    COLUMN_MAPPINGS = {
        'symbol': [
            'Symbol', 'symbol',
            'Instrument', 'instrument',
            'Financial Instrument', 'Ticker',
            'Asset', 'Contract',
        ],
        'description': [
            'Description', 'description',
            'Name', 'Security Name',
            'Asset Description',
        ],
        'quantity': [
            'Position', 'position',
            'Quantity', 'quantity',
            'Shares', 'shares',
            'Current Quantity',
        ],
        'avg_cost': [
            'Average Cost', 'average cost', 'Avg Cost',
            'CostBasisPrice', 'Cost Basis Price',
            'Average Price', 'Avg Price',
            'Cost Price',
        ],
        'current_price': [
            'Mark Price', 'mark price',
            'MarkPrice', 'Close Price',
            'Last Price', 'Price',
            'Current Price',
        ],
        'market_value': [
            'Market Value', 'market value',
            'MarketValue', 'Mkt Value',
            'Position Value',
        ],
        'unrealized_pnl': [
            'Unrealized P&L', 'Unrealized P/L',
            'Unrealized PnL', 'UnrealizedPnL',
            'FifoPnlUnrealized', 'Unrealized Gain/Loss',
            'Unrealized P&L',
        ],
        'currency': [
            'Currency', 'currency',
            'Trading Currency', 'Curr',
        ],
    }

    def _row_to_position(self, row: pd.Series) -> Optional[Position]:
        try:
            symbol = str(row.get('symbol', '')).strip()
            if not symbol or symbol.lower() in ('total', 'cash', ''):
                return None

            quantity = clean_numeric_string(row.get('quantity', 0))
            if quantity == 0:
                return None

            avg_cost = clean_numeric_string(row.get('avg_cost', 0))
            current_price = clean_numeric_string(row.get('current_price', 0))
            market_value = clean_numeric_string(row.get('market_value', 0))
            unrealized_pnl = clean_numeric_string(row.get('unrealized_pnl', 0))

            # 如果没有均价但有市值，反算均价
            if avg_cost == 0 and market_value != 0 and quantity != 0:
                if unrealized_pnl != 0:
                    cost_basis = market_value - unrealized_pnl
                    avg_cost = cost_basis / quantity

            pos = Position(
                broker=self.BROKER_NAME,
                symbol=symbol,
                description=str(row.get('description', '')),
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price,
                currency=str(row.get('currency', 'USD')).strip() or 'USD',
            )
            pos.compute_derived()
            return pos

        except Exception:
            return None

    @classmethod
    def detect(cls, df: pd.DataFrame) -> bool:
        """IBKR 特有检测: 查找 TWS/Flex Query 特征列"""
        cols_lower = [c.lower().strip() for c in df.columns]

        # TWS 导出特征
        tws_markers = ['position', 'mark price', 'average cost']
        if sum(1 for m in tws_markers if m in cols_lower) >= 2:
            return True

        # Flex Query 特征
        flex_markers = ['costbasisprice', 'fifopnlunrealized', 'markprice']
        if sum(1 for m in flex_markers if m in cols_lower) >= 2:
            return True

        return super().detect(df)


def parse_ibkr_csv(file_content) -> pd.DataFrame:
    """
    解析 IBKR CSV 文件，处理多段格式。
    IBKR 的 Activity Statement CSV 可能包含多个部分（以不同行标识），
    这里提取 Open Positions 部分。

    同时支持用户自定义格式：前两行包含现金数据，从第三行开始是持仓表头和数据。
    """
    import io

    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8', errors='ignore')

    lines = file_content.strip().split('\n')

    # 检测用户自定义格式：开头两行是现金数据
    # 第一行包含 EndingCash 关键字，第三行开始是真正持仓数据
    if len(lines) >= 3:
        first_line = lines[0].strip()
        if 'EndingCash' in first_line or 'EndingCashSecurities' in first_line:
            # 跳过前两行，从第三行开始读取
            content_joined = '\n'.join(lines[2:])
            return pd.read_csv(io.StringIO(content_joined))

    # 检查是否是 Activity Statement 多段格式
    is_multi_section = False
    for line in lines[:10]:
        if 'Open Positions' in line or 'Statement' in line:
            is_multi_section = True
            break

    if is_multi_section:
        # 提取 Open Positions 部分
        position_lines = []
        in_section = False
        header_found = False

        for line in lines:
            parts = line.split(',')
            section = parts[0].strip().strip('"')

            if section == 'Open Positions':
                in_section = True
                row_type = parts[1].strip().strip('"') if len(parts) > 1 else ''
                if row_type == 'Header' and not header_found:
                    header_line = ','.join(parts[2:])
                    position_lines.insert(0, header_line)
                    header_found = True
                elif row_type == 'Data':
                    data_line = ','.join(parts[2:])
                    position_lines.append(data_line)
            elif in_section and section != 'Open Positions':
                break

        if position_lines:
            return pd.read_csv(io.StringIO('\n'.join(position_lines)))

    # 普通 CSV 格式（TWS Export 或简单 Flex Query）
    return pd.read_csv(io.StringIO(file_content))


def extract_cash_from_ibkr(file_content) -> List[Position]:
    """
    从 IBKR Activity Statement / Flex Query CSV 提取现金余额。

    IBKR 报表中现金可能在以下位置:
    1. **新格式**: 文件前两行直接包含现金数据 (EndingCash, EndingCashSecurities, EndingCashCommodities)
    2. "Cash Report" section (Activity Statement)
    3. "Net Asset Value" section
    4. "Statement of Funds" section

    也支持从 NAV Summary 提取。
    """
    import io

    if isinstance(file_content, bytes):
        file_content = file_content.decode('utf-8', errors='ignore')

    lines = file_content.strip().split('\n')
    cash_positions = []

    # 方法1: 新格式 - 文件开头两行直接是现金数据
    # 格式示例:
    # "EndingCash","EndingCashSecurities","EndingCashCommodities"
    # "11924.432138722","11924.432138722","0"
    if len(lines) >= 2:
        first_line = lines[0].strip()
        if 'EndingCash' in first_line or 'EndingCashSecurities' in first_line:
            # 第一行是表头，第二行是数据
            parts = [p.strip().strip('"') for p in lines[1].split(',')]
            if len(parts) >= 2:
                # 优先用 EndingCashSecurities (证券账户现金)
                balance = clean_numeric_string(parts[1])
                if balance == 0 and len(parts) >= 1:
                    balance = clean_numeric_string(parts[0])
                if balance != 0:
                    cash_positions.append(Position(
                        broker="IBKR",
                        symbol="CASH_USD",
                        description="Cash Balance (USD)",
                        quantity=balance,
                        avg_cost=1.0,
                        current_price=1.0,
                        currency="USD",
                        asset_type="cash",
                    ))
                    return cash_positions

    # 方法2: 从 Cash Report 段提取
    in_cash_section = False
    for line in lines:
        parts = line.split(',')
        section = parts[0].strip().strip('"')

        if section in ('Cash Report', 'Statement of Funds'):
            in_cash_section = True
            row_type = parts[1].strip().strip('"') if len(parts) > 1 else ''
            if row_type == 'Data':
                # 查找 "Total" 行或各币种余额
                data_parts = [p.strip().strip('"') for p in parts[2:]]
                # 通常格式: Currency, Total, Securities, Futures, ...
                # 或: Header type, Currency, Balance
                for i, val in enumerate(data_parts):
                    if val == 'Total' or val == 'Ending Cash':
                        # 下一个值通常是余额
                        if i + 1 < len(data_parts):
                            balance = clean_numeric_string(data_parts[i + 1])
                            if balance != 0:
                                cash_positions.append(Position(
                                    broker="IBKR",
                                    symbol="CASH_USD",
                                    description="Cash Balance (USD)",
                                    quantity=balance,
                                    avg_cost=1.0,
                                    current_price=1.0,
                                    currency="USD",
                                    asset_type="cash",
                                ))
                                return cash_positions

        elif in_cash_section and section not in ('Cash Report', 'Statement of Funds', ''):
            in_cash_section = False

    # 方法3: 从 Net Asset Value 段提取
    in_nav_section = False
    for line in lines:
        parts = line.split(',')
        section = parts[0].strip().strip('"')

        if section == 'Net Asset Value':
            in_nav_section = True
            row_type = parts[1].strip().strip('"') if len(parts) > 1 else ''
            if row_type == 'Data':
                data_parts = [p.strip().strip('"') for p in parts[2:]]
                for i, val in enumerate(data_parts):
                    if val in ('Cash', 'Cash & Short-Term Receivables'):
                        if i + 1 < len(data_parts):
                            balance = clean_numeric_string(data_parts[i + 1])
                            if balance != 0:
                                cash_positions.append(Position(
                                    broker="IBKR",
                                    symbol="CASH_USD",
                                    description="Cash Balance (USD)",
                                    quantity=balance,
                                    avg_cost=1.0,
                                    current_price=1.0,
                                    currency="USD",
                                    asset_type="cash",
                                ))
                                return cash_positions

        elif in_nav_section and section not in ('Net Asset Value', ''):
            in_nav_section = False

    return cash_positions
