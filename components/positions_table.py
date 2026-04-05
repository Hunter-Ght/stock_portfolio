"""
持仓明细表组件 - 支持显示 Spread 组合和现金
"""
import streamlit as st
import pandas as pd
from typing import List
from importers.base import Position
from services.spread_detector import detect_spreads, SpreadPosition
from utils.formatters import format_currency, format_percentage


def render_positions_table(positions: List[Position], show_broker_filter: bool = True):
    """渲染持仓明细表 - 自动识别 Spread 并分组展示"""
    if not positions:
        st.info("📭 暂无持仓数据，请通过左侧面板导入 CSV 或手动添加持仓。")
        return

    # 识别 spreads
    spreads, stock_positions, cash_positions = detect_spreads(positions)

    # 券商筛选
    all_items = positions  # 用于提取券商列表
    if show_broker_filter:
        brokers = sorted(set(p.broker for p in all_items))
        if len(brokers) > 1:
            selected_broker = st.selectbox(
                "🏦 按券商筛选",
                ["全部"] + brokers,
                key="broker_filter",
            )
            if selected_broker != "全部":
                stock_positions = [p for p in stock_positions if p.broker == selected_broker]
                spreads = [s for s in spreads if s.broker == selected_broker]
                cash_positions = [p for p in cash_positions if p.broker == selected_broker]

    # === 正股持仓表 ===
    if stock_positions:
        st.markdown("#### 📊 股票 & ETF 持仓")
        _render_stock_table(stock_positions)

    # === 期权组合表 ===
    if spreads:
        st.markdown("#### 🎯 期权策略组合")
        _render_spread_table(spreads)

    # === 现金 ===
    if cash_positions:
        st.markdown("#### 💵 现金余额")
        _render_cash_table(cash_positions)

    # 总计
    st.markdown("---")
    total_stock_mv = sum(p.market_value for p in stock_positions)
    total_stock_pnl = sum(p.unrealized_pnl for p in stock_positions)
    total_spread_mv = sum(s.current_value for s in spreads)
    total_spread_pnl = sum(s.unrealized_pnl for s in spreads)
    total_cash = sum(p.quantity for p in cash_positions)

    total_mv = total_stock_mv + total_spread_mv + total_cash
    total_pnl = total_stock_pnl + total_spread_pnl

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f"**总资产:** {format_currency(total_mv)}")
    with col2:
        pnl_color = "green" if total_pnl >= 0 else "red"
        st.markdown(f"**投资盈亏:** <span style='color:{pnl_color}'>{format_currency(total_pnl)}</span>", unsafe_allow_html=True)
    with col3:
        st.markdown(f"**现金:** {format_currency(total_cash)}")
    with col4:
        st.markdown(f"**持仓数:** {len(stock_positions)} 股票 + {len(spreads)} 期权策略")


def _render_stock_table(positions: List[Position]):
    """渲染正股明细表"""
    table_data = []
    for p in positions:
        pnl_emoji = "🟢" if p.unrealized_pnl >= 0 else "🔴"
        table_data.append({
            '券商': p.broker,
            '代码': p.symbol,
            '名称': p.description[:25] if p.description else '',
            '数量': f"{p.quantity:,.0f}" if p.quantity == int(p.quantity) else f"{p.quantity:,.2f}",
            '买入均价': f"${p.avg_cost:,.2f}",
            '现价': f"${p.current_price:,.2f}",
            '市值': f"${p.market_value:,.2f}",
            '盈亏': f"{pnl_emoji} ${p.unrealized_pnl:+,.2f}",
            '盈亏%': f"{p.unrealized_pnl_pct:+.2f}%",
            '_pnl_sort': p.unrealized_pnl,
            '_mv_sort': p.market_value,
        })

    df = pd.DataFrame(table_data)

    sort_col = st.selectbox(
        "📊 排序方式",
        ["按市值 (大→小)", "按盈亏金额 (大→小)", "按盈亏% (大→小)", "按代码 (A→Z)"],
        key="stock_sort_option",
    )

    if sort_col == "按市值 (大→小)":
        df = df.sort_values('_mv_sort', ascending=False)
    elif sort_col == "按盈亏金额 (大→小)":
        df = df.sort_values('_pnl_sort', ascending=False)
    elif sort_col == "按盈亏% (大→小)":
        df = df.sort_values('盈亏%', ascending=False)
    else:
        df = df.sort_values('代码')

    display_cols = ['券商', '代码', '名称', '数量', '买入均价', '现价', '市值', '盈亏', '盈亏%']

    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        height=min(500, len(df) * 38 + 40),
    )


def _render_spread_table(spreads: List[SpreadPosition]):
    """渲染期权组合表"""
    table_data = []
    for s in spreads:
        pnl_emoji = "🟢" if s.unrealized_pnl >= 0 else "🔴"

        # 策略类型图标
        type_icons = {
            "Bull Call Spread": "📈",
            "Bear Call Spread": "📉",
            "Bear Put Spread": "📉",
            "Bull Put Spread": "📈",
            "Covered Call": "🛡️",
            "Naked Option": "🎲",
        }
        icon = type_icons.get(s.spread_type, "📋")

        table_data.append({
            '券商': s.broker,
            '策略': f"{icon} {s.spread_type}",
            '组合': s.display_name,
            '组数': f"{s.quantity}",
            '净成本': f"${s.total_cost:,.2f}",
            '当前价值': f"${s.current_value:,.2f}",
            '盈亏': f"{pnl_emoji} ${s.unrealized_pnl:+,.2f}",
            '盈亏%': f"{s.unrealized_pnl_pct:+.2f}%",
            '_pnl_sort': s.unrealized_pnl,
            '_mv_sort': abs(s.current_value),
        })

    df = pd.DataFrame(table_data)
    df = df.sort_values('_mv_sort', ascending=False)

    display_cols = ['券商', '策略', '组合', '组数', '净成本', '当前价值', '盈亏', '盈亏%']

    st.dataframe(
        df[display_cols],
        use_container_width=True,
        hide_index=True,
        height=min(400, len(df) * 38 + 40),
    )

    # 展开/折叠显示各腿明细
    with st.expander("🔍 展开期权各腿明细"):
        for s in spreads:
            st.markdown(f"**{s.display_name}** × {s.quantity}")
            legs = []
            if s.long_leg:
                legs.append({
                    '方向': '🟢 买入',
                    'Symbol': s.long_leg.symbol,
                    '描述': s.long_leg.description,
                    '数量': s.long_leg.quantity,
                    '均价': f"${s.long_leg.avg_cost:,.4f}",
                    '现价': f"${s.long_leg.current_price:,.4f}",
                })
            if s.short_leg:
                legs.append({
                    '方向': '🔴 卖出',
                    'Symbol': s.short_leg.symbol,
                    '描述': s.short_leg.description,
                    '数量': s.short_leg.quantity,
                    '均价': f"${s.short_leg.avg_cost:,.4f}",
                    '现价': f"${s.short_leg.current_price:,.4f}",
                })
            if s.stock_leg:
                legs.append({
                    '方向': '📊 正股',
                    'Symbol': s.stock_leg.symbol,
                    '描述': s.stock_leg.description,
                    '数量': s.stock_leg.quantity,
                    '均价': f"${s.stock_leg.avg_cost:,.2f}",
                    '现价': f"${s.stock_leg.current_price:,.2f}",
                })
            if legs:
                st.dataframe(pd.DataFrame(legs), hide_index=True, use_container_width=True)
            st.markdown("---")


def _render_cash_table(cash_positions: List[Position]):
    """渲染现金余额表"""
    table_data = []
    for p in cash_positions:
        table_data.append({
            '券商': p.broker,
            '币种': p.currency,
            '余额': f"${p.quantity:,.2f}",
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
