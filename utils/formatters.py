"""
数字和货币格式化工具
"""


def format_currency(value: float, currency: str = "USD") -> str:
    """格式化货币显示"""
    if currency == "USD":
        if abs(value) >= 1_000_000:
            return f"${value:,.0f}"
        return f"${value:,.2f}"
    return f"{value:,.2f} {currency}"


def format_percentage(value: float) -> str:
    """格式化百分比显示"""
    return f"{value:+.2f}%"


def format_pnl(value: float) -> str:
    """格式化盈亏显示（带正负号）"""
    if abs(value) >= 1_000_000:
        return f"{'+'if value >= 0 else ''}{value:,.0f}"
    return f"{'+'if value >= 0 else ''}{value:,.2f}"


def format_number(value: float, decimals: int = 2) -> str:
    """通用数字格式化"""
    return f"{value:,.{decimals}f}"


def clean_numeric_string(value) -> float:
    """
    清洗数值字符串，处理各种格式:
    - '$100.50' -> 100.50
    - '="$100.50"' -> 100.50  (Schwab 特殊格式)
    - '1,234.56' -> 1234.56
    - '--' -> 0.0
    """
    if isinstance(value, (int, float)):
        return float(value)

    if not isinstance(value, str):
        return 0.0

    s = str(value).strip()

    # 处理空值和占位符
    if s in ('', '--', 'N/A', 'n/a', 'nan', '-'):
        return 0.0

    # 处理 Schwab 特殊格式: ="$100.50"
    s = s.replace('="', '').replace('"', '')

    # 移除货币符号和空格
    s = s.replace('$', '').replace('¥', '').replace('€', '').replace(' ', '')

    # 移除千分位逗号
    s = s.replace(',', '')

    # 处理百分号
    s = s.replace('%', '')

    # 处理括号表示负数: (100.50) -> -100.50
    if s.startswith('(') and s.endswith(')'):
        s = '-' + s[1:-1]

    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0
