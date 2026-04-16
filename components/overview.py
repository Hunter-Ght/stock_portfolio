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

    cols = st.columns(len(broker_data))
    for i, (broker, data) in enumerate(broker_data.items()):
        with cols[i]:
            # 券商图标
            icon = "🟠" if broker == "IBKR" else "🔵" if broker == "Schwab" else "🟢" if broker == "Firstrade" else "⚪"
            st.markdown(f"### {icon} {broker}")

            # 使用 Streamlit 原生 container，自动适配浅色/深色主题
            pnl_color = "green" if data['pnl'] >= 0 else "red"
            cash_amount = data.get('cash', 0)

            with st.container(border=True):
                st.metric("总资产", format_currency(data["market_value"]))
                
                # 财务明细
                st.markdown(
                    f"<div style='margin-bottom: 4px; font-size: 14px; opacity: 0.8;'>投资盈亏</div>"
                    f"<div style='color: {pnl_color}; font-size: 18px; font-weight: 500;'>{format_pnl(data['pnl'])} ({format_percentage(data['pnl_pct'])})</div>", 
                    unsafe_allow_html=True
                )

                if cash_amount != 0:
                    st.markdown(
                        f"<div style='margin-top: 8px; margin-bottom: 4px; font-size: 14px; opacity: 0.8;'>现金</div>"
                        f"<div style='font-size: 16px; font-weight: 500;'>{format_currency(cash_amount)}</div>", 
                        unsafe_allow_html=True
                    )

                st.markdown(
                    f"<div style='margin-top: 8px; margin-bottom: 4px; font-size: 14px; opacity: 0.8;'>占总资产</div>"
                    f"<div style='font-size: 16px; font-weight: 500;'>{data['allocation_pct']:.1f}%</div>",
                    unsafe_allow_html=True
                )
                
                st.caption(f"{data['position_count']} 个持仓")
