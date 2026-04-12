import pandas as pd
from typing import Optional
from .base import BaseImporter, Position


class FirstradeImporter(BaseImporter):
    """
    Firstrade (第一证券) 导入器
    读取的往往是 .xlsx 结尾的文件 (positions)
    """
    BROKER_NAME = "Firstrade"

    # 标准化列名映射
    COLUMN_MAPPINGS = {
        'symbol': ['Symbol'],
        'quantity': ['Quantity'],
        'avg_cost': ['Unit Cost', 'Adj. Unit Cost', 'Cost'],
        'current_price': ['Last Price', 'Current Price', 'Price'],
        'market_value': ['Market Value', 'Value'],
    }

    def _row_to_position(self, row: pd.Series) -> Optional[Position]:
        """将一行 Firstrade 数据转换为 Position"""
        symbol = str(row.get('symbol', '')).strip()

        # 跳过空代码
        if not symbol or symbol == 'nan':
            return None
        
        # 跳过总计行之类的尾部数据
        if 'Total' in symbol or 'Summary' in symbol:
            return None

        try:
            quantity = float(row.get('quantity', 0))
            if quantity == 0:
                return None  # 跳过数量为0的

            avg_cost = float(row.get('avg_cost', 0))
            current_price = float(row.get('current_price', 0))

            pos = Position(
                broker=self.BROKER_NAME,
                symbol=symbol.upper(),
                quantity=quantity,
                avg_cost=avg_cost,
                current_price=current_price
            )

            # 让基类补全市值等计算
            pos.compute_derived()
            
            return pos

        except (ValueError, TypeError):
            # 类型转换失败的行跳过
            return None

def parse_firstrade_excel(content: bytes) -> pd.DataFrame:
    """预处理 Firstrade Excel 内容，返回标准 DataFrame"""
    import io
    # 读取 Excel
    try:
        df = pd.read_excel(io.BytesIO(content))
        return df
    except Exception as e:
        raise ValueError(f"无法解析 Firstrade Excel 文件: {str(e)}")
