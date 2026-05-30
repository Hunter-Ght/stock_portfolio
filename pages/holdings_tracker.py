"""
多券商美股持仓追踪 Dashboard
-------------------------------
整合 IBKR、Schwab、Firstrade 的持仓数据，
实时追踪总市值、盈亏、资产配置。
"""
import streamlit as st
import sys
import os

# 设置项目根目录到 Python 路径
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.portfolio import load_positions, update_prices, get_portfolio_summary
from components.overview import render_overview, render_broker_summary
from components.charts import (
    render_allocation_pie,
    render_sector_pie,
    render_treemap,
    render_pnl_bar,
    render_broker_allocation_donut,
)
from components.positions_table import render_positions_table
from components.import_panel import render_import_panel
import pandas as pd
from importers.ibkr import IBKRImporter
from importers.schwab import SchwabImporter, preprocess_schwab_csv
from services.portfolio import add_positions


def _load_sample(broker: str):
    """加载示例数据"""
    sample_dir = os.path.join(ROOT_DIR, 'data', 'samples')

    if broker == 'ibkr':
        df = pd.read_csv(os.path.join(sample_dir, 'ibkr_sample.csv'))
        importer = IBKRImporter()
    else:
        with open(os.path.join(sample_dir, 'schwab_sample.csv'), 'r') as f:
            content = f.read()
        df = preprocess_schwab_csv(content)
        importer = SchwabImporter()

    positions = importer.parse(df)
    if positions:
        add_positions(positions, replace_broker=True)
        st.session_state['do_refresh'] = True
        st.session_state.pop('prices_updated', None)

# ─── 侧边栏 ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="sidebar-brand">
        <div class="sidebar-brand-title">Portfolio Tracker</div>
        <div class="sidebar-brand-sub">多券商持仓追踪</div>
    </div>
    """, unsafe_allow_html=True)



    # 刷新行情按钮
    st.markdown("---")
    if st.button("刷新实时行情", use_container_width=True, type="primary"):
        st.session_state['do_refresh'] = True
        st.rerun()

    # 导入面板
    render_import_panel()

# ─── 主内容区 ────────────────────────────────────────────

# 标题
st.markdown("""
<div class="page-header" style="padding: 0 0 12px 0;">
    <h1>Dashboard</h1>
    <p>实时追踪你的多券商美股持仓</p>
</div>
""", unsafe_allow_html=True)

# 加载持仓
positions = load_positions()

if positions:
    # 先用 JSON 中保存的价格直接计算展示（秒开）
    for p in positions:
        p.compute_derived()

    # 如果用户点了刷新按钮，后台更新行情
    if st.session_state.get('do_refresh', False):
        with st.spinner("正在获取实时行情..."):
            positions = update_prices(positions)
            st.session_state['do_refresh'] = False
            import datetime
            st.session_state['last_refresh'] = datetime.datetime.now().strftime("%H:%M:%S")
            st.rerun()  # 刷新后 rerun 展示新数据

    # 显示上次更新状态
    last_refresh = st.session_state.get('last_refresh', None)
    if last_refresh:
        st.caption(f"行情已于 {last_refresh} 更新")
    else:
        st.caption("当前显示上次导入/刷新的价格，点击左侧「刷新实时行情」获取最新价格")

    # 计算汇总
    summary = get_portfolio_summary(positions)

    # ─── 总览指标 ────────────────────────
    render_overview(summary)

    st.markdown("---")

    # ─── 券商汇总 ────────────────────────
    st.markdown("""
    <div class="section-header">
        <div class="eyebrow">BROKERS</div>
        <h3>券商概览</h3>
    </div>
    """, unsafe_allow_html=True)
    render_broker_summary(summary)

    st.markdown("---")

    # ─── 图表区域 ────────────────────────
    st.markdown("""
    <div class="section-header">
        <div class="eyebrow">ANALYSIS</div>
        <h3>资产分析</h3>
    </div>
    """, unsafe_allow_html=True)

    tab1, tab2, tab3, tab4 = st.tabs([
        "持仓占比",
        "资产地图",
        "盈亏对比",
        "券商占比",
    ])

    with tab1:
        col1, col2 = st.columns([3, 2])
        with col1:
            render_allocation_pie(positions)
        with col2:
            render_sector_pie(positions)

    with tab2:
        render_treemap(positions)

    with tab3:
        render_pnl_bar(positions)

    with tab4:
        render_broker_allocation_donut(summary)

    st.markdown("---")

    # ─── 持仓明细 ────────────────────────
    st.markdown("""
    <div class="section-header">
        <div class="eyebrow">POSITIONS</div>
        <h3>持仓明细</h3>
    </div>
    """, unsafe_allow_html=True)
    render_positions_table(positions)

else:
    # 空状态
    st.markdown("""
    <div class="empty-state">
        <h2>欢迎使用 Portfolio Tracker</h2>
        <p>
            开始追踪你的投资组合：<br>
            通过左侧面板上传券商的持仓文件，或手动添加持仓
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 快速示例导入
    st.markdown("### 快速体验")
    st.markdown("点击下方按钮导入示例数据，快速预览 Dashboard 效果：")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("导入 IBKR 示例数据", use_container_width=True):
            _load_sample('ibkr')
            st.rerun()
    with col2:
        if st.button("导入 Schwab 示例数据", use_container_width=True):
            _load_sample('schwab')
            st.rerun()

# ─── 页脚 ────────────────────────────────────────────────
st.markdown("""
<div class="page-footer">
    数据来源: Yahoo Finance / 仅供个人投资参考
</div>
""", unsafe_allow_html=True)
