"""A-share holdings page components."""
from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from services.a_share_portfolio import (
    add_a_share_position,
    get_a_share_portfolio_summary,
    load_a_share_positions,
    remove_a_share_position,
    update_a_share_prices,
)


def render_a_share_holdings() -> None:
    st.title("A股持仓追踪")
    st.caption("独立追踪 A股持仓，数据保存到 data/a_share_positions.json。")

    with st.sidebar:
        st.markdown("## ✏️ 添加 A股持仓")
        with st.form("a_share_add_form", clear_on_submit=True):
            symbol = st.text_input("股票代码", placeholder="688981")
            name = st.text_input("中文名", placeholder="可选，留空会尝试自动补齐")
            quantity = st.number_input("数量", min_value=0.0, step=100.0)
            avg_cost = st.number_input("买入均价 (CNY)", min_value=0.0, step=0.01)
            submitted = st.form_submit_button("添加/更新", use_container_width=True)
        if submitted:
            add_a_share_position(symbol, quantity, avg_cost, name=name)
            st.rerun()

        st.markdown("---")
        if st.button("刷新A股行情", type="primary", use_container_width=True):
            with st.spinner("正在获取 A股行情..."):
                update_a_share_prices(load_a_share_positions())
            st.rerun()

    positions = load_a_share_positions()
    if not positions:
        st.info("暂无 A股持仓。请在左侧输入数字代码、数量和成本。")
        return

    for position in positions:
        position.compute_derived()

    render_a_share_overview(get_a_share_portfolio_summary(positions))

    st.markdown("---")
    st.markdown("### 📈 资产分析")
    tab_allocation, tab_pnl = st.tabs(["持仓占比", "盈亏对比"])
    with tab_allocation:
        render_a_share_allocation_chart(positions)
    with tab_pnl:
        render_a_share_pnl_chart(positions)

    st.markdown("---")
    st.markdown("### 📋 持仓明细")
    render_a_share_positions_table(positions)
    render_a_share_manage_section(positions)


def render_a_share_overview(summary: dict) -> None:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("总市值", _fmt_cny(summary["total_market_value"]))
    col2.metric("总成本", _fmt_cny(summary["total_cost_basis"]))
    col3.metric("总盈亏", _fmt_cny(summary["total_pnl"]), f"{summary['total_pnl_pct']:+.2f}%")
    col4.metric("今日涨跌", _fmt_cny(summary["total_day_change"]), f"{summary['total_day_change_pct']:+.2f}%")
    col5.metric("持仓数量", summary["position_count"])


def render_a_share_allocation_chart(positions) -> None:
    rows = [
        {"标的": _display_name(position), "市值": abs(position.market_value)}
        for position in positions
        if abs(position.market_value) > 0
    ]
    if not rows:
        st.info("暂无可展示的市值数据。")
        return
    fig = px.pie(pd.DataFrame(rows), names="标的", values="市值", hole=0.45)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig, use_container_width=True)


def render_a_share_pnl_chart(positions) -> None:
    rows = [
        {
            "name": _display_name(position),
            "pnl": position.unrealized_pnl,
            "pnl_pct": position.unrealized_pnl_pct,
        }
        for position in positions
    ]
    if not rows:
        st.info("暂无可展示的盈亏数据。")
        return
    df = pd.DataFrame(rows).sort_values("pnl", ascending=True)
    colors = ['#ef4444' if value < 0 else '#22c55e' for value in df["pnl"]]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df["pnl"],
        y=df["name"],
        orientation="h",
        marker_color=colors,
        text=[f"¥{value:+,.0f} ({pct:+.1f}%)" for value, pct in zip(df["pnl"], df["pnl_pct"])],
        textposition="outside",
        textfont=dict(size=11),
        hovertemplate=(
            "<b>%{y}</b><br>"
            "盈亏: ¥%{x:,.2f}<br>"
            "<extra></extra>"
        ),
    ))
    fig.update_layout(
        xaxis=dict(title="盈亏金额 (CNY)"),
        margin=dict(l=10, r=130, t=30, b=40),
        height=max(300, len(rows) * 35 + 80),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_a_share_positions_table(positions) -> None:
    rows = []
    for position in positions:
        rows.append({
            "代码": position.symbol,
            "名称": position.description or "",
            "数量": position.quantity,
            "成本": f"¥{position.avg_cost:,.2f}",
            "现价": f"¥{position.current_price:,.2f}",
            "市值": f"¥{position.market_value:,.2f}",
            "盈亏": f"¥{position.unrealized_pnl:+,.2f}",
            "盈亏%": f"{position.unrealized_pnl_pct:+.2f}%",
            "今日涨跌%": f"{position.day_change_pct:+.2f}%",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_a_share_manage_section(positions) -> None:
    with st.expander("管理 A股持仓", expanded=False):
        selected = st.selectbox(
            "选择持仓",
            [""] + [position.id for position in positions],
            format_func=lambda position_id: _position_label(position_id, positions),
        )
        if selected and st.button("删除", use_container_width=True):
            remove_a_share_position(selected)
            st.rerun()


def _display_name(position) -> str:
    return f"{position.symbol} · {position.description}" if position.description else position.symbol


def _fmt_cny(value: float) -> str:
    return f"¥{value:,.2f}"


def _position_label(position_id: str, positions) -> str:
    if not position_id:
        return "选择持仓"
    position = next((item for item in positions if item.id == position_id), None)
    if not position:
        return position_id
    name = f" · {position.description}" if position.description else ""
    return f"{position.symbol}{name} × {position.quantity:g}"
