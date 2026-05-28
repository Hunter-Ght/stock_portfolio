"""Streamlit page for A-share holdings."""
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.a_share_holdings import render_a_share_holdings


render_a_share_holdings()
