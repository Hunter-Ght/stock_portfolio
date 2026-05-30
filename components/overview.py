"""
总览指标卡片组件
"""
import streamlit as st
from utils.formatters import format_currency, format_percentage, format_pnl
from utils.theme_colors import pnl_color, BROKER_COLORS, BROKER_DEFAULT


def render_overview(summary: dict):
    """渲染总览面板 - 关键指标卡片，总资产突出显示"""

    # 总资产大卡片
    total_mv = summary['total_market_value']
    pnl = summary['total_pnl']
    pnl_pct = summary['total_pnl_pct']
    day_change = summary['total_day_change']

    pnl_cls = "pnl-positive" if pnl >= 0 else "pnl-negative"
    day_cls = "pnl-positive" if day_change >= 0 else "pnl-negative"

    st.markdown(f"""
    <div class="card-hero">
        <div>
            <div class="label-muted">总资产</div>
            <div class="value-hero">{format_currency(total_mv)}</div>
        </div>
        <div style="text-align: right;">
            <div class="label-muted">总盈亏</div>
            <div class="value-medium {pnl_cls}">
                {format_pnl(pnl)} ({format_percentage(pnl_pct)})
            </div>
            <div class="label-muted" style="margin-top: 4px;">今日</div>
            <div class="value-small {day_cls}">
                {format_pnl(day_change)}
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 次要指标
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="投资成本",
            value=format_currency(summary['total_cost_basis']),
        )

    with col2:
        st.metric(
            label="现金余额",
            value=format_currency(summary.get('total_cash', 0)),
        )

    with col3:
        st.metric(
            label="持仓数量",
            value=f"{summary['position_count']} 只",
        )


def render_broker_summary(summary: dict):
    """渲染券商维度汇总"""
    broker_data = summary.get('broker_summary', {})
    if not broker_data:
        st.info("暂无持仓数据")
        return

    cols = st.columns(len(broker_data))
    for i, (broker, data) in enumerate(broker_data.items()):
        with cols[i]:
            accent = BROKER_COLORS.get(broker, BROKER_DEFAULT)
            pnl = data['pnl']
            pnl_pct = data['pnl_pct']
            pnl_cls = "pnl-positive" if pnl >= 0 else "pnl-negative"
            cash_amount = data.get('cash', 0)

            st.markdown(f"""
            <div class="card-broker" style="border-top: 3px solid {accent};">
                <div style="font-weight: 600; color: var(--color-text-primary); margin-bottom: 12px; font-size: 15px;">
                    {broker}
                </div>
                <div class="label-muted">总资产</div>
                <div class="value-medium" style="margin-bottom: 10px;">
                    {format_currency(data['market_value'])}
                </div>
                <div class="label-muted">投资盈亏</div>
                <div class="value-small {pnl_cls}" style="margin-bottom: 10px;">
                    {format_pnl(pnl)} ({format_percentage(pnl_pct)})
                </div>
                {f'<div class="label-muted">现金</div><div class="value-small" style="margin-bottom: 10px;">{format_currency(cash_amount)}</div>' if cash_amount != 0 else ''}
                <div class="label-muted">占比</div>
                <div class="value-small">{data['allocation_pct']:.1f}%</div>
                <div class="label-faint" style="margin-top: 8px;">{data['position_count']} 个持仓</div>
            </div>
            """, unsafe_allow_html=True)
