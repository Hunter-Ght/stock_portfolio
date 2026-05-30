"""
图表组件 - 饼图、Treemap、柱状图 (支持 Spread 和 Cash)
"""
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
import re
from typing import List
from importers.base import Position
from services.spread_detector import detect_spreads, SpreadPosition
from utils.theme_colors import (
    CHART_COLORS, BROKER_COLORS, BROKER_DEFAULT,
    TEXT_PRIMARY, TEXT_SECONDARY, TEXT_MUTED, BORDER, PROFIT, LOSS,
    FONT_FAMILY,
)

# GICS 行业中文映射
SECTOR_CN = {
    'Technology': '信息技术',
    'Healthcare': '医疗健康',
    'Financial Services': '金融服务',
    'Consumer Cyclical': '可选消费',
    'Consumer Defensive': '必选消费',
    'Energy': '能源',
    'Industrials': '工业',
    'Basic Materials': '基础材料',
    'Real Estate': '房地产',
    'Communication Services': '通信服务',
    'Utilities': '公用事业',
}

# 自定义主题分类 (优先于 GICS 大类)
THEMATIC = {
    # ── 光模块/光概念 ──
    'LITE': '光模块/光概念',   # Lumentum
    'AAOI': '光模块/光概念',   # Applied Optoelectronics
    'COHR': '光模块/光概念',   # Coherent (原 II-VI)
    'GLW':  '光模块/光概念',   # Corning
    'AXTI': '光模块/光概念',   # AXT Inc (GaAs/GaSb 衬底)
    'CIEN': '光模块/光概念',   # Ciena
    'INFN': '光模块/光概念',   # Infinera
    'LUNA': '光模块/光概念',   # Luna Innovations
    'IIVI': '光模块/光概念',   # 原 Coherent 旧代码
    # ── 太空航天 ──
    'ASTS': '太空航天',       # AST SpaceMobile
    'RKLB': '太空航天',       # Rocket Lab
    'LUNR': '太空航天',       # Intuitive Machines
    'MNTS': '太空航天',       # Momentus
    'RDW':  '太空航天',       # Redwire
    'KTOS': '太空航天',       # Kratos Defense
    'BKSY': '太空航天',       # BlackSky
    'SPCE': '太空航天',       # Virgin Galactic
    'ASTR': '太空航天',       # Astra Space
    'LLAP': '太空航天',       # Terran Orbital
    # ── 有色矿业 ──
    'FCX':  '有色矿业',       # Freeport-McMoRan (铜金)
    'VALE': '有色矿业',       # Vale (铁矿)
    'CCJ':  '有色矿业',       # Cameco (铀矿)
    'UUUU': '有色矿业',       # Energy Fuels (铀/稀土)
    'METC': '有色矿业',       # Ramaco Resources (冶金煤)
    'ALM':  '有色矿业',       # Alma Gold
    'COPX': '有色矿业',       # Global X 铜矿 ETF
    'PALL': '有色矿业',       # 钯金 ETF
}

# 杠杆 ETF → 底层标的 映射
LEVERAGED_ETF = {
    # ── 光模块/光概念 底层 ──
    'AAOX': 'AAOI',
    'LITX': 'LITE',
    'GLWG': 'GLW',
    # ── 太空航天 底层 ──
    'ASTX': 'ASTS',
    # ── 有色矿业 (指数型，底层不在 THEMATIC 中) ──
    'NUGT': '__MINING__',     # 2x Gold Miners (GDX)
    # ── 医疗健康 (指数型) ──
    'LABU': '__BIOTECH__',    # 3x S&P Biotech (XBI)
    # ── 信息技术 底层 ──
    'METU': 'META',
    'AVGX': 'AVGO',
    'MSTZ': 'MSTR',
    'TSMX': 'TSM',
    'NVDX': 'NVDA',
    'NVDU': 'NVDA',
    'TSLL': 'TSLA',
    'CONL': 'COIN',
    'SOXL': 'SOXX',
    'TQQQ': 'QQQ',
    'UPRO': 'SPY',
    'SPXL': 'SPY',
    'FNGU': 'FNGS',
    'FNGO': 'FNGS',
    'AMZU': 'AMZN',
    'MSFU': 'MSFT',
    'AAPU': 'AAPL',
    'GOOU': 'GOOGL',
}


def _get_underlying_symbol(option_symbol: str) -> str:
    """
    从期权代码中提取底层 ticker
    'ASTS 260918C00110000' → 'ASTS'
    """
    m = re.match(r'^([A-Z]+)\s+\d{6}[CP]\d+$', option_symbol)
    return m.group(1) if m else option_symbol


def _resolve_sector(symbol: str, gics_sector: str) -> str:
    """
    确定行业分类: 自定义主题 > 杠杆ETF底层归类 > GICS行业
    支持期权符号 (如 "ASTS 260918C00110000")
    """
    sym = symbol.upper().strip()

    # 1. 直接命中自定义主题
    if sym in THEMATIC:
        return THEMATIC[sym]

    # 2. 期权: 提取底层 ticker 后查主题
    underlying = _get_underlying_symbol(sym)
    if underlying != sym and underlying in THEMATIC:
        return THEMATIC[underlying]

    # 3. 杠杆 ETF: 查底层标的
    mapped = LEVERAGED_ETF.get(sym)
    if mapped:
        # 指数型 ETF 直接映射到行业
        if mapped == '__MINING__':
            return '有色矿业'
        if mapped == '__BIOTECH__':
            return '医疗健康'
        # 底层是具体 ticker，查主题
        if mapped in THEMATIC:
            return THEMATIC[mapped]
        # 底层不在自定义主题中，用底层 ticker 的 GICS（此处无，标记为未知）
        return SECTOR_CN.get(gics_sector, gics_sector) if gics_sector else '信息技术'

    # 4. 回退到 GICS 行业
    return SECTOR_CN.get(gics_sector, gics_sector) if gics_sector else '其他'


def _get_colors():
    return CHART_COLORS


# Plotly 浅色主题模板
_LIGHT_TEMPLATE = dict(
    layout=dict(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font=dict(family=FONT_FAMILY, color=TEXT_SECONDARY, size=12),
        title=dict(
            font=dict(color=TEXT_PRIMARY, size=16, family=FONT_FAMILY),
            x=0.02, xanchor='left',
        ),
        legend=dict(
            font=dict(color=TEXT_SECONDARY, size=11, family=FONT_FAMILY),
            bgcolor='rgba(0,0,0,0)',
            borderwidth=0,
        ),
        xaxis=dict(
            gridcolor=BORDER, gridwidth=1, zerolinecolor='#d6d3d1',
            tickfont=dict(color=TEXT_MUTED, family=FONT_FAMILY),
            title=dict(font=dict(color=TEXT_MUTED, size=11)),
        ),
        yaxis=dict(
            gridcolor=BORDER, gridwidth=1, zerolinecolor='#d6d3d1',
            tickfont=dict(color=TEXT_MUTED, family=FONT_FAMILY),
            title=dict(font=dict(color=TEXT_MUTED, size=11)),
        ),
        hoverlabel=dict(
            bgcolor=TEXT_PRIMARY,
            font=dict(color='#ffffff', size=12, family=FONT_FAMILY),
            bordercolor='rgba(0,0,0,0)',
        ),
    )
)


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
                'name': f"{p.broker} Cash",
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
        template=_LIGHT_TEMPLATE,
        legend=dict(
            orientation='v',
            yanchor='middle',
            y=0.5,
            xanchor='left',
            x=1.05,
            font=dict(size=11, color='#57534e'),
        ),
        margin=dict(l=20, r=20, t=30, b=20),
        height=450,
    )

    st.plotly_chart(fig, use_container_width=True)


def render_sector_pie(positions: List[Position]):
    """渲染行业占比饼图，hover 显示该行业下各股票明细"""
    # 按行业聚合市值，并记录每行业的持仓明细
    sector_values = {}
    sector_stocks = {}  # sector -> [(symbol, market_value), ...]
    for p in positions:
        if p.asset_type == 'cash':
            sector = '现金'
            value = p.quantity
            sym_label = f"{p.broker} Cash"
        else:
            sector = _resolve_sector(p.symbol, p.sector)
            value = abs(p.market_value)
            sym_label = p.symbol
        if value > 0:
            sector_values[sector] = sector_values.get(sector, 0) + value
            sector_stocks.setdefault(sector, []).append((sym_label, value))

    if not sector_values:
        st.info("暂无有效数据")
        return

    # 按市值降序排列
    sorted_sectors = sorted(sector_values.items(), key=lambda x: -x[1])
    labels = [s[0] for s in sorted_sectors]
    values = [s[1] for s in sorted_sectors]

    # 构建 hover 文本: 把标题+股票明细+小计拼成一个完整字符串，避免 customdata 索引问题
    hover_texts = []
    total_value = sum(values)
    for sector_name in labels:
        stocks = sorted(sector_stocks.get(sector_name, []), key=lambda x: -x[1])
        pct = sector_values[sector_name] / total_value * 100 if total_value else 0
        lines = [f"  {sym}  ${val:,.0f}" for sym, val in stocks]
        detail = "<br>".join(lines)
        text = (
            f"<b>{sector_name}</b> ({pct:.1f}%)"
            f"<br>──────────────"
            f"<br>{detail}"
            f"<br>──────────────"
            f"<br>小计: ${sector_values[sector_name]:,.2f}"
        )
        hover_texts.append(text)

    colors = _get_colors()

    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.45,
        marker=dict(colors=colors[:len(labels)]),
        textinfo='label+percent',
        textfont_size=11,
        customdata=hover_texts,
        hovertemplate='%{customdata}<extra></extra>',
    )])

    fig.update_layout(
        template=_LIGHT_TEMPLATE,
        legend=dict(
            orientation='v',
            yanchor='middle',
            y=0.5,
            xanchor='left',
            x=1.05,
            font=dict(size=11, color='#57534e'),
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
        template=_LIGHT_TEMPLATE,
        margin=dict(l=10, r=10, t=30, b=10),
        height=420,
        coloraxis_colorbar=dict(
            title='盈亏%',
            tickformat='.0f',
            ticksuffix='%',
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

    colors = [LOSS if v < 0 else PROFIT for v in df['pnl']]

    fig = go.Figure()

    fig.add_trace(go.Bar(
        x=df['pnl'],
        y=df['name'],
        orientation='h',
        marker_color=colors,
        text=[f"${v:+,.0f} ({p:+.1f}%)" for v, p in zip(df['pnl'], df['pnl_pct'])],
        textposition='outside',
        textfont=dict(size=11),
        hovertemplate=(
            '<b>%{y}</b><br>'
            '盈亏: $%{x:,.2f}<br>'
            '<extra></extra>'
        ),
    ))

    fig.update_layout(
        template=_LIGHT_TEMPLATE,
        xaxis=dict(
            title='盈亏金额 (USD)',
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
    brokers = list(broker_data.keys())
    values = [broker_data[b]['market_value'] for b in brokers]

    colors = [BROKER_COLORS.get(b, BROKER_DEFAULT) for b in brokers]

    fig = go.Figure(data=[go.Pie(
        labels=brokers,
        values=values,
        hole=0.55,
        marker=dict(colors=colors),
        textinfo='label+percent',
        textfont=dict(size=14),
        hovertemplate='<b>%{label}</b><br>总资产: $%{value:,.2f}<br>占比: %{percent}<extra></extra>',
    )])

    fig.update_layout(
        template=_LIGHT_TEMPLATE,
        showlegend=True,
        legend=dict(
            orientation='h',
            yanchor='bottom',
            y=-0.15,
            xanchor='center',
            x=0.5,
            font=dict(color='#57534e'),
        ),
        margin=dict(l=20, r=20, t=20, b=40),
        height=320,
        annotations=[dict(
            text='<b>券商占比</b>',
            x=0.5, y=0.5,
            font_size=14,
            font_color='#292524',
            showarrow=False,
        )],
    )

    st.plotly_chart(fig, use_container_width=True)
