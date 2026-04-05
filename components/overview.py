"""
总览指标卡片组件
"""
import streamlit as st
from utils.formatters import format_currency, format_percentage, format_pnl


def render_overview(summary: dict):
    """渲染总览面板 - 5个关键指标卡片"""

    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="📊 总资产",
            value=format_currency(summary['total_market_value']),
            delta=None,
        )

    with col2:
        st.metric(
            label="💰 投资成本",
            value=format_currency(summary['total_cost_basis']),
        )

    with col3:
        pnl = summary['total_pnl']
        pnl_pct = summary['total_pnl_pct']
        st.metric(
            label="📈 总盈亏",
            value=format_currency(pnl),
            delta=f"{format_percentage(pnl_pct)}",
        )

    with col4:
        day_change = summary['total_day_change']
        st.metric(
            label="📅 今日变动",
            value=format_currency(day_change),
            delta=format_pnl(day_change),
        )

    with col5:
        total_cash = summary.get('total_cash', 0)
        st.metric(
            label="💵 现金",
            value=format_currency(total_cash),
        )


def render_broker_summary(summary: dict):
    """渲染券商维度汇总"""
    import streamlit as st
    broker_data = summary.get('broker_summary', {})
    if not broker_data:
        st.info("暂无持仓数据")
        return

    # 根据主题适配颜色
    is_light = st.session_state.get('theme', 'dark') == 'light'
    if is_light:
        bg_start = "rgba(255, 255, 255, 0.9)"
        bg_end = "rgba(248, 250, 252, 0.8)"
        border_color = "rgba(15, 23, 42, 0.1)"
        label_color = "#64748b"
        value_color = "#0f172a"
        cash_color = "#d97706"
        alloc_color = "#2563eb"
        minor_color = "#475569"
    else:
        bg_start = "rgba(30,30,50,0.8)"
        bg_end = "rgba(40,40,70,0.6)"
        border_color = "rgba(255,255,255,0.1)"
        label_color = "#aaa"
        value_color = "#fff"
        cash_color = "#fbbf24"
        alloc_color = "#64b5f6"
        minor_color = "#888"

    cols = st.columns(len(broker_data))
    for i, (broker, data) in enumerate(broker_data.items()):
        with cols[i]:
            # 券商图标
            icon = "🟠" if broker == "IBKR" else "🔵" if broker == "Schwab" else "⚪"
            st.markdown(f"### {icon} {broker}")

            # Create a container with custom styling
            pnl_color = "green" if data['pnl'] >= 0 else "red"
            cash_amount = data.get('cash', 0)

            # Using single-line HTML to avoid any parsing issues
            html = (
                f'<div style="background: linear-gradient(135deg, {bg_start}, {bg_end}); '
                f'border: 1px solid {border_color}; '
                'border-radius: 12px; padding: 16px; margin-bottom: 8px;">'
                f'<div style="color: {label_color}; font-size: 13px;">总资产</div>'
                f'<div style="color: {value_color}; font-size: 22px; font-weight: 600;">{format_currency(data["market_value"])}</div>'
                f'<div style="margin-top: 8px; color: {label_color}; font-size: 13px;">投资盈亏</div>'
                f'<div style="color: {pnl_color}; font-size: 18px; font-weight: 500;">{format_pnl(data["pnl"])} ({format_percentage(data["pnl_pct"])})</div>'
            )

            if cash_amount != 0:
                html += (
                    f'<div style="margin-top: 8px; color: {label_color}; font-size: 13px;">现金</div>'
                    f'<div style="color: {cash_color}; font-size: 16px;">{format_currency(cash_amount)}</div>'
                )

            html += (
                f'<div style="margin-top: 8px; color: {label_color}; font-size: 13px;">占总资产</div>'
                f'<div style="color: {alloc_color}; font-size: 16px;">{data["allocation_pct"]:.1f}%</div>'
                f'<div style="margin-top: 4px; color: {minor_color}; font-size: 12px;">{data["position_count"]} 个持仓</div>'
                '</div>'
            )

            st.markdown(html, unsafe_allow_html=True)
