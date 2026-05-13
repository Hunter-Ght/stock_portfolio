"""Streamlit page for manually imported stock research reports."""
import os
import sys

import streamlit as st


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from components.stock_workbench import render_stock_workbench


render_stock_workbench()
