"""
实时行情获取服务 - 使用 yfinance 批量下载 (快速版)
"""
import yfinance as yf
from typing import Dict, List
import pandas as pd


def get_quotes(symbols: List[str]) -> Dict[str, dict]:
    """
    批量获取股票实时行情 - 使用 yf.download() 一次性获取所有数据

    返回:
        {
            'AAPL': {
                'price': 178.50,
                'previous_close': 177.20,
                'day_change': 1.30,
                'day_change_pct': 0.73,
                'name': 'AAPL',
            },
            ...
        }
    """
    if not symbols:
        return {}

    result = {}

    # 过滤掉明显无效的 symbol
    valid_symbols = [s for s in symbols if s and len(s) <= 10 and s.isalpha() or '.' in s]
    # 也包含含数字的 symbol (如 7709.HK)
    valid_symbols = [s for s in symbols if s and len(s) <= 12]

    if not valid_symbols:
        return {}

    try:
        # yf.download 一次性批量下载，比逐个 Ticker 快 10x+
        data = yf.download(
            tickers=valid_symbols,
            period='2d',
            progress=False,
            threads=True,
            group_by='ticker',
        )

        if data.empty:
            return {}

        for symbol in valid_symbols:
            try:
                # 单个 symbol 时 DataFrame 结构不同
                if len(valid_symbols) == 1:
                    sym_data = data
                else:
                    if symbol not in data.columns.get_level_values(0):
                        continue
                    sym_data = data[symbol]

                if sym_data.empty or sym_data['Close'].dropna().empty:
                    continue

                closes = sym_data['Close'].dropna()
                current_price = float(closes.iloc[-1])
                previous_close = float(closes.iloc[-2]) if len(closes) >= 2 else current_price

                day_change = current_price - previous_close
                day_change_pct = (day_change / previous_close * 100) if previous_close else 0

                result[symbol] = {
                    'price': current_price,
                    'previous_close': previous_close,
                    'day_change': day_change,
                    'day_change_pct': day_change_pct,
                    'name': symbol,  # 不再逐个查 info，太慢
                }

            except Exception:
                continue

    except Exception:
        # fallback: 逐个快速查询
        for symbol in valid_symbols[:20]:  # 最多查20个，避免太慢
            try:
                ticker = yf.Ticker(symbol)
                hist = ticker.history(period='2d')

                if hist.empty:
                    continue

                closes = hist['Close'].dropna()
                current_price = float(closes.iloc[-1]) if len(closes) >= 1 else 0
                previous_close = float(closes.iloc[-2]) if len(closes) >= 2 else current_price

                day_change = current_price - previous_close
                day_change_pct = (day_change / previous_close * 100) if previous_close else 0

                result[symbol] = {
                    'price': current_price,
                    'previous_close': previous_close,
                    'day_change': day_change,
                    'day_change_pct': day_change_pct,
                    'name': symbol,
                }

            except Exception:
                continue

    return result
