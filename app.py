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

# ─── 主题配置 ─────────────────────────────────────────────
# 初始化主题状态
if 'theme' not in st.session_state:
    st.session_state['theme'] = 'dark'  # 默认深色主题

# ─── 页面配置 ─────────────────────────────────────────────
st.set_page_config(
    page_title="Portfolio Tracker | 多券商持仓追踪",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── 根据主题输出 CSS ──────────────────────────────────────────
is_light = st.session_state['theme'] == 'light'

if is_light:
    # 浅色主题 CSS
    css = """
    <style>
        /* Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* 全局字体 */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* 主背景 */
        .stApp {
            background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
        }

        /* 侧边栏样式 */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f8fafc 100%);
            border-right: 1px solid rgba(99, 102, 241, 0.15);
        }

        /* 指标卡片 */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, #ffffff 0%, #f8fafc 100%);
            border: 1px solid rgba(99, 102, 241, 0.2);
            border-radius: 16px;
            padding: 20px 24px;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.08);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(15, 23, 42, 0.12);
        }

        [data-testid="stMetricLabel"] {
            font-size: 14px !important;
            font-weight: 500 !important;
            color: #64748b !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 28px !important;
            font-weight: 700 !important;
            color: #0f172a !important;
        }

        /* 标题 */
        h1 {
            background: linear-gradient(90deg, #1e293b, #475569);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700 !important;
        }

        h2, h3 {
            color: #1e293b !important;
            font-weight: 600 !important;
        }

        /* 分隔线 */
        hr {
            border-color: rgba(99, 102, 241, 0.15) !important;
        }

        /* 表格样式 */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(15, 23, 42, 0.1);
        }

        /* 按钮样式 */
        .stButton > button {
            border-radius: 10px;
            border: 1px solid rgba(99, 102, 241, 0.3);
            background: #ffffff;
            color: #1e293b;
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            border-color: #6366f1;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.15);
            background: #f8fafc;
            color: #1e293b;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
            color: white !important;
        }

        .stButton > button[kind="primary"]:hover {
            background: linear-gradient(135deg, #4338ca, #4f46e5) !important;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3) !important;
        }

        .stButton > button[kind="secondary"] {
            background: #ffffff !important;
            color: #1e293b !important;
            border: 1px solid rgba(99, 102, 241, 0.4) !important;
        }

        .stButton > button[kind="secondary"]:hover {
            background: #f8fafc !important;
            color: #1e293b !important;
            border-color: #6366f1 !important;
        }

        /* Tab 样式 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
            background: transparent !important;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            padding: 8px 16px;
            color: #64748b !important;
            background-color: transparent !important;
        }

        .stTabs [data-baseweb="tab"] span {
            color: #64748b !important;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.08));
            color: #1e293b !important;
        }

        .stTabs [aria-selected="true"] span {
            color: #1e293b !important;
        }

        /* Expander inside tabs */
        .stTabs [data-testid="stExpander"] {
            background-color: #ffffff !important;
        }
        .stTabs [data-testid="stExpander"] summary {
            color: #1e293b !important;
        }
        .stTabs [data-testid="stExpander"] summary:hover {
            background-color: #f1f5f9 !important;
        }

        /* 文件上传 */
        [data-testid="stFileUploader"] {
            border-radius: 12px;
        }

        /* Select box */
        [data-testid="stSelectbox"] {
            border-radius: 8px;
        }

        /* 侧边栏标题 */
        section[data-testid="stSidebar"] h2 {
            font-size: 18px !important;
            margin-top: 8px !important;
            color: #1e293b !important;
        }

        /* 动画: 进入 */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .element-container {
            animation: fadeInUp 0.4s ease-out;
        }

        /* 隐藏 streamlit footer */
        footer {
            visibility: hidden;
        }

        /* info/success 提示框 */
        [data-testid="stAlert"] {
            border-radius: 10px;
            border: 1px solid rgba(99, 102, 241, 0.2);
            background: #ffffff;
        }

        /* 文本颜色 */
        p, .stMarkdown {
            color: #334155;
        }

        /* 表格文字颜色覆盖 */
        .stDataFrame {
            color: #1e293b;
        }

        /*  caption 颜色 */
        .stCaption {
            color: #64748b;
        }

        /* === 修复输入框/选择框背景 === */
        /* Selectbox dropdown */
        [data-testid="stSelectbox"] > div > div {
            background-color: #ffffff !important;
        }
        [data-testid="stSelectbox"] label {
            color: #1e293b !important;
        }

        /* Text input / Number input */
        [data-testid="stNumberInput"] input {
            background-color: #ffffff !important;
            color: #1e293b !important;
            border-color: rgba(15, 23, 42, 0.1) !important;
        }
        [data-testid="stNumberInput"] label {
            color: #1e293b !important;
        }

        [data-testid="stTextInput"] input {
            background-color: #ffffff !important;
            color: #1e293b !important;
            border-color: rgba(15, 23, 42, 0.1) !important;
        }
        [data-testid="stTextInput"] label {
            color: #1e293b !important;
        }

        /* File uploader */
        [data-testid="stFileUploader"] section {
            background-color: #ffffff !important;
            border-color: rgba(15, 23, 42, 0.1) !important;
        }
        [data-testid="stFileUploader"] span {
            color: #1e293b !important;
        }

        /* Checkbox */
        [data-testid="stCheckbox"] label {
            color: #1e293b !important;
        }

        /* Radio buttons */
        [data-testid="stRadio"] label {
            color: #1e293b !important;
        }
        [data-testid="stRadio"] span {
            color: #1e293b !important;
        }

        /* Form */
        [data-testid="stForm"] {
            background-color: transparent !important;
        }

        /* DataFrame table */
        .stDataFrame table {
            background-color: #ffffff !important;
        }
        .stDataFrame th {
            background-color: #f1f5f9 !important;
            color: #1e293b !important;
        }
        .stDataFrame td {
            color: #1e293b !important;
        }

        /* Sort selectbox in table area */
        .stSelectbox div {
            background-color: #ffffff !important;
        }
        .stSelectbox label {
            color: #1e293b !important;
        }

        /* Expanders */
        [data-testid="stExpander"] {
            background-color: #ffffff !important;
            border-color: rgba(15, 23, 42, 0.1) !important;
        }
        [data-testid="stExpander"] summary {
            color: #1e293b !important;
        }

        /* 顶部工具栏 / 头部 */
        [data-testid="stHeader"] {
            background-color: transparent !important;
        }
        [data-testid="stToolbar"] {
            background-color: transparent !important;
        }
        .stAppToolbar {
            background-color: transparent !important;
        }
        [data-testid="stToolbar"] button {
            color: #1e293b !important;
        }
        [data-testid="stToolbar"] svg {
            fill: #1e293b !important;
            color: #1e293b !important;
        }

        /* Streamlit top right menu */
        .stMainMenu svg {
            fill: #1e293b !important;
        }

        /* 滑动条 */
        [data-testid="stSlider"] label {
            color: #1e293b !important;
        }

        /* 下拉选项弹窗 - 完整修复 */
         [role="listbox"] {
             background-color: #ffffff !important;
             border: 1px solid rgba(15, 23, 42, 0.1) !important;
         }
         [role="option"] {
             color: #1e293b !important;
             background-color: transparent !important;
         }
         [role="option"]:hover {
             background-color: #f1f5f9 !important;
             color: #1e293b !important;
         }
         [data-selected="true"] {
             background-color: rgba(99, 102, 241, 0.1) !important;
             color: #1e293b !important;
         }
         /* 下拉框弹出层容器 */
         .stSelectbox [role="listbox"] {
             background-color: #ffffff !important;
         }
         .stSelectbox [role="option"] {
             color: #1e293b !important;
         }
         .stSelectbox [role="option"]:hover {
             background-color: #f1f5f9 !important;
         }
         /* 所有ul/li下拉 */
         ul {
             background-color: #ffffff !important;
         }
         li {
             color: #1e293b !important;
         }
         li:hover {
             background-color: #f1f5f9 !important;
         }

         /* Label 文字颜色全局 */
         label {
             color: #1e293b !important;
         }

         /* === 修复按钮和数字输入框加减号 === */
         /* Number input step buttons (+/-) */
         [data-testid="stNumberInput"] button {
             background-color: #f1f5f9 !important;
             color: #1e293b !important;
             border-color: rgba(15, 23, 42, 0.1) !important;
         }
         [data-testid="stNumberInput"] button:hover {
             background-color: #e2e8f0 !important;
         }

         /* File uploader button */
         [data-testid="stFileUploader"] button {
             background-color: #6366f1 !important;
             color: #ffffff !important;
         }
         [data-testid="stFileUploader"] button:hover {
             background-color: #4f46e5 !important;
         }

         /* Buttons in forms */
         [data-testid="stForm"] button {
             background-color: #ffffff !important;
             color: #1e293b !important;
         }
         [data-testid="stForm"] button[type="submit"] {
             background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
             color: white !important;
         }

         /* === 完整表格背景修复 - 暴力覆盖所有层级 白底黑字 === */
         /* 表格容器 - 所有层级背景都变白 */
         .stDataFrame,
         .stDataFrame *,
         .stDataFrame > div,
         .stDataFrame > div > div,
         .stDataFrame > div > div > div,
         .stDataFrame > div > div > div > div {
             background-color: #ffffff !important;
         }

         /* 暴力覆盖所有文字 - 全部变黑 */
         .stDataFrame *,
         .stDataFrame *::before,
         .stDataFrame *::after {
             color: #1e293b !important;
             fill: #1e293b !important;
             background-color: transparent !important;
         }

         /* 表格整体 */
         .stDataFrame table {
             background-color: #ffffff !important;
             border-collapse: collapse;
         }

         /* 表头 - 浅灰背景 */
         .stDataFrame thead,
         .stDataFrame thead *,
         .stDataFrame thead tr,
         .stDataFrame thead tr *,
         .stDataFrame thead tr th,
         .stDataFrame thead tr th *,
         .stDataFrame thead tr th div,
         .stDataFrame thead tr th span {
             background-color: #f1f5f9 !important;
             color: #1e293b !important;
         }

         /* 表体 - 白色背景 */
         .stDataFrame tbody,
         .stDataFrame tbody *,
         .stDataFrame tbody tr,
         .stDataFrame tbody tr * {
             background-color: #ffffff !important;
         }

         .stDataFrame tbody tr:hover {
             background-color: #f8fafc !important;
         }

         .stDataFrame tbody tr:hover * {
             background-color: transparent !important;
         }

         .stDataFrame tbody td,
         .stDataFrame tbody td *,
         .stDataFrame tbody td div,
         .stDataFrame tbody td div *,
         .stDataFrame tbody td span,
         .stDataFrame tbody td a {
             background-color: transparent !important;
             color: #1e293b !important;
         }

         /* 单元格内文字 */
         .stDataFrame div div,
         .stDataFrame div div * {
             color: #1e293b !important;
             background-color: transparent !important;
         }

         /* SVG文字 */
         .stDataFrame svg,
         .stDataFrame svg *,
         .stDataFrame svg text {
             background-color: transparent !important;
             fill: #1e293b !important;
             stroke: none !important;
         }

         /* 排序框在表格上方 */
         .stDataFrame + .stSelectbox {
             margin-bottom: 8px;
         }
         .stDataFrame + .stSelectbox,
         .stDataFrame + .stSelectbox * {
             background-color: #ffffff !important;
         }
         .stDataFrame + .stSelectbox label {
             color: #1e293b !important;
         }

         /* 清空所有深色背景继承 */
         .stDataFrame [class*="css"] {
             color: #1e293b !important;
             background-color: transparent !important;
         }

         /* 修复侧边栏删除区域文字和背景 */
         section[data-testid="stSidebar"] .stMarkdown p {
             color: #1e293b !important;
         }
         section[data-testid="stSidebar"] div {
             color: #1e293b !important;
         }

         /* 修复所有markdown文字颜色 */
         .stMarkdown p {
             color: #334155 !important;
         }
         .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4 {
             color: #1e293b !important;
         }

         /* 修复信息框文字 */
         [data-testid="stAlert"] .stMarkdown p {
             color: #1e293b !important;
         }

         /* 下拉框选项高亮 */
         [data-selected="true"] {
             background-color: rgba(99, 102, 241, 0.1) !important;
         }
     </style>
     """
else:
    # 深色主题 CSS (原有样式)
    css = """
    <style>
        /* Google Fonts */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* 全局字体 */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif;
        }

        /* 主背景渐变 */
        .stApp {
            background: linear-gradient(180deg, #0a0a1a 0%, #0f0f2a 50%, #0a0a1a 100%);
        }

        /* 侧边栏样式 */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #12122a 0%, #0d0d20 100%);
            border-right: 1px solid rgba(99, 102, 241, 0.2);
        }

        /* 指标卡片 */
        [data-testid="stMetric"] {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.15), rgba(139, 92, 246, 0.08));
            border: 1px solid rgba(99, 102, 241, 0.25);
            border-radius: 16px;
            padding: 20px 24px;
            box-shadow: 0 4px 20px rgba(99, 102, 241, 0.1);
            transition: transform 0.2s ease, box-shadow 0.2s ease;
        }

        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 30px rgba(99, 102, 241, 0.2);
        }

        [data-testid="stMetricLabel"] {
            font-size: 14px !important;
            font-weight: 500 !important;
            color: #a5b4fc !important;
        }

        [data-testid="stMetricValue"] {
            font-size: 28px !important;
            font-weight: 700 !important;
            color: #e0e7ff !important;
        }

        /* 正向 delta */
        [data-testid="stMetricDelta"] svg[viewBox="0 0 24 24"] {
            /* keep default */
        }

        /* 标题 */
        h1 {
            background: linear-gradient(90deg, #6366f1, #a78bfa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-weight: 700 !important;
        }

        h2, h3 {
            color: #c7d2fe !important;
            font-weight: 600 !important;
        }

        /* 分隔线 */
        hr {
            border-color: rgba(99, 102, 241, 0.2) !important;
        }

        /* 表格样式 */
        [data-testid="stDataFrame"] {
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid rgba(99, 102, 241, 0.15);
        }

        /* 按钮样式 */
        .stButton > button {
            border-radius: 10px;
            border: 1px solid rgba(99, 102, 241, 0.3);
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            border-color: rgba(99, 102, 241, 0.6);
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.2);
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
            color: white !important;
        }

        /* Tab 样式 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 8px;
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 8px;
            padding: 8px 16px;
            color: #a5b4fc;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.15));
            color: #e0e7ff !important;
        }

        /* 文件上传 */
        [data-testid="stFileUploader"] {
            border-radius: 12px;
        }

        /* Select box */
        [data-testid="stSelectbox"] {
            border-radius: 8px;
        }

        /* 侧边栏标题 */
        section[data-testid="stSidebar"] h2 {
            font-size: 18px !important;
            margin-top: 8px !important;
        }

        /* 动画: 进入 */
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .element-container {
            animation: fadeInUp 0.4s ease-out;
        }

        /* 隐藏 streamlit footer */
        footer {
            visibility: hidden;
        }

        /* info/success 提示框 */
        [data-testid="stAlert"] {
            border-radius: 10px;
            border: 1px solid rgba(99, 102, 241, 0.2);
        }
    </style>
    """

st.markdown(css, unsafe_allow_html=True)

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

    # 主题切换
    st.markdown("---")
    st.markdown("### 🎨 主题设置")
    current_theme = st.session_state['theme']
    theme_label = "☀️ 浅色主题" if current_theme == 'dark' else "🌙 深色主题"
    if st.button(theme_label, use_container_width=True):
        # 切换主题
        new_theme = 'light' if current_theme == 'dark' else 'dark'
        st.session_state['theme'] = new_theme
        st.rerun()

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
    <p style="color: #64748b; margin: 4px 0 0 0; font-size: 14px;">
        实时追踪你的多券商美股持仓 · IBKR & Schwab
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
        <h2 style="color: {title_color}; margin-bottom: 12px;">欢迎使用 Portfolio Tracker</h2>
        <p style="color: #64748b; font-size: 16px; max-width: 500px; margin: 0 auto; line-height: 1.8;">
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

