"""
图表组件 - 饼图、Treemap、柱状图 (支持 Spread 和 Cash)
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from typing import List
from importers.base import Position
from services.spread_detector import detect_spreads, SpreadPosition


# 颜色主题
LIGHT_COLORS = [
    '#6366f1', '#8b5cf6', '#a78bfa', '#c084fc',
    '#f472b6', '#fb7185', '#f97316', '#f59e0b',
    '#10b981', '#34d399', '#0ea5e9', '#3b82f6',
    '#818cf8', '#e879f9', '#38bdf8', '#2dd4bf',
]

DARK_COLORS = [
    '#6366f1', '#8b5cf6', '#a78bfa', '#c084fc',
    '#f472b6', '#fb7185', '#f97316', '#facc15',
    '#4ade80', '#34d399', '#22d3ee', '#60a5fa',
    '#818cf8', '#e879f9', '#38bdf8', '#2dd4bf',
]


def _get_text_color():
    """根据主题获取合适的文字颜色"""
    import streamlit as st
    is_light = st.session_state.get('theme', 'dark') == 'light'
    return '#1e293b' if is_light else '#e0e0e0'


def _get_grid_color():
    """根据主题获取合适的网格颜色"""
    import streamlit as st
    is_light = st.session_state.get('theme', 'dark') == 'light'
    return 'rgba(0,0,0,0.05)' if is_light else 'rgba(255,255,255,0.05)'


def _get_zeroline_color():
    """根据主题获取合适的零线颜色"""
    import streamlit as st
    is_light = st.session_state.get('theme', 'dark') == 'light'
    return 'rgba(0,0,0,0.2)' if is_light else 'rgba(255,255,255,0.2)'


def _get_colors():
    """根据主题获取颜色序列"""
    import streamlit as st
    is_light = st.session_state.get('theme', 'dark') == 'light'
    return LIGHT_COLORS if is_light else DARK_COLORS


def _build_display_data(positions: List[Position]):
    """
    构建展示用数据: 将期权合并为 Spread, 保留正股, 加入现金

    Returns:
        list of dict: [{'name': ..., 'market_value': ..., 'pnl': ..., 'type': ..., 'broker': ...}]
    """
    spreads, stocks, cash_positions = detect_spreads(positions)

    items = []

    # 正股
    for p in stocks:
        if abs(p.market_value) > 0:
            items.append({
                'name': p.symbol,
                'market_value': abs(p.market_value),
                'pnl': p.unrealized_pnl,
                'pnl_pct': p.unrealized_pnl_pct,
                'type': '股票/ETF',
                'broker': p.broker,
            })

    # Spread 组合
    for s in spreads:
        if abs(s.current_value) > 0:
            items.append({
                'name': s.display_symbol,
                'market_value': abs(s.current_value),
                'pnl': s.unrealized_pnl,
                'pnl_pct': s.unrealized_pnl_pct,
                'type': s.spread_type,
                'broker': s.broker,
            })

    # 现金
    for p in cash_positions:
        if p.quantity > 0:
            items.append({
                'name': f"💵 {p.broker} Cash",
                'market_value': p.quantity,
                'pnl': 0,
                'pnl_pct': 0,
                'type': '现金',
                'broker': p.broker,
            })

    return items


def render_allocation_pie(positions: List[Position]):
    """渲染持仓占比饼图 (包含 Spread 和现金)"""
    items = _build_display_data(positions)
    if not items:
        st.info("暂无有效数据")
        return

    import pandas as pd
    df = pd.DataFrame(items)
    colors = _get_colors()
    text_color = _get_text_color()

    fig = px.pie(
        df,
        values='market_value',
        names='name',
        color_discrete_sequence=colors,
        hole=0.45,
    )

    fig.update_traces(
        textposition='inside',
        textinfo='label+percent',
        textfont_size=11,
        hovertemplate='<b>%{label}</b><br>市值: $%{value:,.2f}<br>占比: %{percent}<extra></extra>',
    )

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=text_color, family='Inter, sans-serif'),
        legend=dict(
            orientation='v',
            yanchor='middle',
            y=0.5,
            xanchor='left',
            x=1.05,
            font=dict(size=11, color=text_color),
        ),
        margin=dict(l=20, r=20, t=30, b=20),
        height=450,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_treemap(positions: List[Position]):
    """渲染矩形树图 - 按类型分层"""
    items = _build_display_data(positions)
    if not items:
        st.info("暂无有效数据")
        return

    import pandas as pd
    df = pd.DataFrame(items)
    text_color = _get_text_color()

    fig = px.treemap(
        df,
        path=['type', 'name'],
        values='market_value',
        color='pnl_pct',
        color_continuous_scale=['#ef4444', '#fbbf24', '#22c55e'],
        color_continuous_midpoint=0,
        hover_data={'market_value': ':,.2f', 'pnl': ':,.2f', 'pnl_pct': ':.2f'},
    )

    fig.update_traces(
        textinfo='label+value+percent root',
        texttemplate='<b>%{label}</b><br>$%{value:,.0f}<br>%{percentRoot:.1%}',
        hovertemplate=(
            '<b>%{label}</b><br>'
            '市值: $%{value:,.2f}<br>'
            '盈亏: $%{customdata[1]:,.2f}<br>'
            '盈亏%: %{customdata[2]:.2f}%'
            '<extra></extra>'
        ),
    )

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=text_color, family='Inter, sans-serif'),
        margin=dict(l=10, r=10, t=30, b=10),
        height=420,
        coloraxis_colorbar=dict(
            title='盈亏%',
            tickformat='.0f',
            ticksuffix='%',
            tickfont=dict(color=text_color),
            titlefont=dict(color=text_color),
        ),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_pnl_bar(positions: List[Position]):
    """渲染盈亏柱状图 (含 Spread)"""
    items = _build_display_data(positions)
    items = [i for i in items if i['type'] != '现金']  # 现金不参与盈亏

    if not items:
        st.info("暂无有效数据")
        return

    import pandas as pd
    df = pd.DataFrame(items)
    df = df.sort_values('pnl', ascending=True)
    text_color = _get_text_color()
    grid_color = _get_grid_color()
    zero_color = _get_zeroline_color()

    colors = ['#ef4444' if v < 0 else '#22c55e' for v in df['pnl']]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df['pnl'],
        y=df['name'],
        orientation='h',
        marker_color=colors,
        text=[f"${v:+,.0f} ({p:+.1f}%)" for v, p in zip(df['pnl'], df['pnl_pct'])],
        textposition='outside',
        textfont=dict(size=11, color=text_color),
        hovertemplate=(
            '<b>%{y}</b><br>'
            '盈亏: $%{x:,.2f}<br>'
            '<extra></extra>'
        ),
    ))

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=text_color, family='Inter, sans-serif'),
        xaxis=dict(
            gridcolor=grid_color,
            zerolinecolor=zero_color,
            title='盈亏金额 (USD)',
            title_font=dict(color=text_color),
            tickfont=dict(color=text_color),
        ),
        yaxis=dict(
            gridcolor=grid_color,
            tickfont=dict(color=text_color),
        ),
        margin=dict(l=10, r=130, t=30, b=40),
        height=max(300, len(items) * 35 + 80),
    )

    st.plotly_chart(fig, use_container_width=True)


def render_broker_allocation_donut(summary: dict):
    """渲染各券商资产占比环形图"""
    broker_data = summary.get('broker_summary', {})
    if not broker_data:
        return

    text_color = _get_text_color()
    brokers = list(broker_data.keys())
    values = [broker_data[b]['market_value'] for b in brokers]

    broker_colors = {
        'IBKR': '#f97316',
        'Schwab': '#3b82f6',
        'Manual': '#8b5cf6',
    }
    colors = [broker_colors.get(b, '#64748b') for b in brokers]

    fig = go.Figure(data=[go.Pie(
        labels=brokers,
        values=values,
        hole=0.55,
        marker=dict(colors=colors),
        textinfo='label+percent',
        textfont=dict(size=14, color=text_color),
        hovertemplate='<b>%{label}</b><br>总资产: $%{value:,.2f}<br>占比: %{percent}<extra></extra>',
    )])

    # 注释文字颜色需要根据主题调整
    is_light = st.session_state.get('theme', 'dark') == 'light'
    ann_color = '#64748b' if is_light else '#aaa'

    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color=text_color, family='Inter, sans-serif'),
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=-0.15,
            xanchor='center',
            x=0.5,
            font=dict(color=text_color),
        ),
        margin=dict(l=20, r=20, t=20, b=40),
        height=320,
        annotations=[dict(
            text='<b>券商占比</b>',
            x=0.5, y=0.5,
            font_size=14,
            font_color=ann_color,
            showarrow=False,
        )],
    )

    st.plotly_chart(fig, use_container_width=True)
