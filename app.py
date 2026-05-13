"""Portfolio Tracker navigation entrypoint."""
import streamlit as st


st.set_page_config(
    page_title="Portfolio Tracker | 多券商持仓追踪",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/holdings_tracker.py", title="持仓追踪", icon="📊"),
    st.Page("pages/stock_analysis.py", title="个股工作台", icon="🔎"),
]

st.navigation(pages).run()
