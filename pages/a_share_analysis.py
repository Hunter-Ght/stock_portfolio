"""Streamlit page for manually imported A-share research reports."""
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.stock_workbench import render_stock_workbench


render_stock_workbench(market="Ashare")
