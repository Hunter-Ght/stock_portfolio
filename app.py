"""Portfolio Tracker navigation entrypoint."""
import streamlit as st
import os


st.set_page_config(
    page_title="Portfolio Tracker | 多券商持仓追踪",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject global theme CSS (available on all pages)
_theme_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'theme.css')
if os.path.exists(_theme_path):
    with open(_theme_path, 'r') as _f:
        st.markdown(f'<style>{_f.read()}</style>', unsafe_allow_html=True)

pages = [
    st.Page("pages/holdings_tracker.py", title="持仓追踪", icon="📊"),
    st.Page("pages/stock_analysis.py", title="美股工作台", icon="🔎"),
    st.Page("pages/a_share_holdings.py", title="A股持仓追踪", icon="🇨🇳"),
    st.Page("pages/a_share_analysis.py", title="A股工作台", icon="🧭"),
]

st.navigation(pages).run()
