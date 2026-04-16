"""
📊 多券商美股持仓追踪 Dashboard
-------------------------------
整合 IBKR (盈透) 和 Schwab (嘉信) 的持仓数据，
实时追踪总市值、盈亏、资产配置。
"""
import streamlit as st
import sys
import os

# 设置项目根目录到 Python 路径
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from services.portfolio import load_positions, update_prices, get_portfolio_summary
from components.overview import render_overview, render_broker_summary
from components.charts import (
    render_allocation_pie,
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
        if 'prices_updated' in st.session_state:
            del st.session_state['prices_updated']

# ─── 页面配置 ─────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Tracker | 多券商持仓追踪",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)



# ─── 侧边栏 ─────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align: center; padding: 20px 0 10px 0;">
        <div style="font-size: 40px;">📊</div>
        <div style="
            font-size: 20px;
            font-weight: 700;
            background: linear-gradient(90deg, #6366f1, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        ">Portfolio Tracker</div>
        <div style="color: #64748b; font-size: 12px; margin-top: 4px;">多券商持仓追踪</div>
    </div>
    """, unsafe_allow_html=True)



    # 刷新行情按钮
    st.markdown("---")
    if st.button("🔄 刷新实时行情", use_container_width=True, type="primary"):
        st.session_state['do_refresh'] = True
        st.rerun()

    # 导入面板
    render_import_panel()

# ─── 主内容区 ────────────────────────────────────────────

# 标题
st.markdown("""
<div style="padding: 0 0 10px 0;">
    <h1 style="margin: 0; font-size: 32px;">Portfolio Dashboard</h1>
    <p style="margin: 4px 0 0 0; font-size: 14px; opacity: 0.8;">
        实时追踪你的多券商美股持仓
    </p>
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
        with st.spinner("📡 正在获取实时行情..."):
            positions = update_prices(positions)
            st.session_state['do_refresh'] = False
            import datetime
            st.session_state['last_refresh'] = datetime.datetime.now().strftime("%H:%M:%S")
            st.rerun()  # 刷新后 rerun 展示新数据

    # 显示上次更新状态
    last_refresh = st.session_state.get('last_refresh', None)
    if last_refresh:
        st.caption(f"✅ 行情已于 {last_refresh} 更新 · 点击左侧「刷新实时行情」获取最新价格")
    else:
        st.caption("💡 当前显示上次导入/刷新的价格 · 点击左侧「🔄 刷新实时行情」获取最新价格")

    # 计算汇总
    summary = get_portfolio_summary(positions)

    # ─── 总览指标 ────────────────────────
    render_overview(summary)

    st.markdown("---")

    # ─── 券商汇总 ────────────────────────
    st.markdown("### 🏦 券商概览")
    render_broker_summary(summary)

    st.markdown("---")

    # ─── 图表区域 ────────────────────────
    st.markdown("### 📈 资产分析")

    tab1, tab2, tab3, tab4 = st.tabs([
        "🍩 持仓占比",
        "🗺️ 资产地图",
        "📊 盈亏对比",
        "🏦 券商占比",
    ])

    with tab1:
        render_allocation_pie(positions)

    with tab2:
        render_treemap(positions)

    with tab3:
        render_pnl_bar(positions)

    with tab4:
        render_broker_allocation_donut(summary)

    st.markdown("---")

    # ─── 持仓明细 ────────────────────────
    st.markdown("### 📋 持仓明细")
    render_positions_table(positions)

else:
    # 空状态
    if is_light:
        bg_start = "rgba(99, 102, 241, 0.05)"
        bg_end = "rgba(139, 92, 246, 0.02)"
        border_color = "rgba(99, 102, 241, 0.3)"
        title_color = "#1e293b"
    else:
        bg_start = "rgba(99, 102, 241, 0.08)"
        bg_end = "rgba(139, 92, 246, 0.05)"
        border_color = "rgba(99, 102, 241, 0.3)"
        title_color = "#c7d2fe"

    st.markdown(f"""
    <div style="
        text-align: center;
        padding: 80px 20px;
        background: linear-gradient(135deg, {bg_start}, {bg_end});
        border: 1px dashed {border_color};
        border-radius: 20px;
        margin: 40px 0;
    ">
        <div style="font-size: 60px; margin-bottom: 20px;">📂</div>
        <h2 style="margin-bottom: 12px;">欢迎使用 Portfolio Tracker</h2>
        <p style="font-size: 16px; max-width: 500px; margin: 0 auto; line-height: 1.8; opacity: 0.8;">
            开始追踪你的投资组合：<br>
            ① 通过左侧面板上传 <strong>IBKR</strong> 或 <strong>Schwab</strong> 的 CSV 导出文件<br>
            ② 或者手动添加持仓<br>
            ③ Dashboard 将自动获取实时行情并展示分析
        </p>
    </div>
    """, unsafe_allow_html=True)

    # 快速示例导入
    st.markdown("### 🚀 快速体验")
    st.markdown("点击下方按钮导入示例数据，快速预览 Dashboard 效果：")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🟠 导入 IBKR 示例数据", use_container_width=True):
            _load_sample('ibkr')
            st.rerun()
    with col2:
        if st.button("🔵 导入 Schwab 示例数据", use_container_width=True):
            _load_sample('schwab')
            st.rerun()

# ─── 页脚 ────────────────────────────────────────────────
st.markdown("""
<div style="
    text-align: center;
    padding: 30px 0 10px 0;
    color: #4a4a6a;
    font-size: 12px;
">
    Portfolio Tracker v1.0 · 数据来源: Yahoo Finance · 仅供个人投资参考
</div>
""", unsafe_allow_html=True)

