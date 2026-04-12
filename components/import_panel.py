"""
导入面板组件 - CSV 上传、自动检测、预览、手动录入、现金管理
"""
import streamlit as st
import pandas as pd
from typing import List, Optional
from importers.base import Position
from importers.ibkr import IBKRImporter, parse_ibkr_csv, extract_cash_from_ibkr
from importers.schwab import SchwabImporter, preprocess_schwab_csv
from importers.firstrade import FirstradeImporter, parse_firstrade_excel
from services.portfolio import (
    add_positions, add_cash, remove_position,
    remove_broker_positions, load_positions,
)


def render_import_panel():
    """渲染导入面板（侧边栏）"""

    st.sidebar.markdown("---")
    st.sidebar.markdown("## 📥 导入持仓")

    # 文件上传
    uploaded_file = st.sidebar.file_uploader(
        "上传持仓文件",
        type=['csv', 'xlsx'],
        help="支持 IBKR / Schwab 的 csv, 以及 Firstrade 的 xlsx 文件",
        key="csv_uploader",
    )

    if uploaded_file is not None:
        _handle_file_upload(uploaded_file)

    st.sidebar.markdown("---")

    # 现金余额
    st.sidebar.markdown("## 💵 现金余额")
    _render_cash_form()

    st.sidebar.markdown("---")

    # 手动添加
    st.sidebar.markdown("## ✏️ 手动添加")
    _render_manual_add_form()

    st.sidebar.markdown("---")

    # 管理
    st.sidebar.markdown("## 🗂️ 管理持仓")
    _render_manage_section()


def _handle_file_upload(uploaded_file):
    """处理上传的文件"""
    try:
        content = uploaded_file.read()
        uploaded_file.seek(0)
        filename = uploaded_file.name.lower()

        broker_choice = st.sidebar.radio(
            "选择券商",
            ["🔍 自动检测", "🟠 IBKR (盈透)", "🔵 Schwab (嘉信)", "🟢 Firstrade"],
            key="broker_choice",
        )

        if broker_choice == "🟠 IBKR (盈透)":
            df = parse_ibkr_csv(content.decode('utf-8', errors='ignore'))
            importer = IBKRImporter()
        elif broker_choice == "🔵 Schwab (嘉信)":
            df = preprocess_schwab_csv(content.decode('utf-8', errors='ignore'))
            importer = SchwabImporter()
        elif broker_choice == "🟢 Firstrade":
            df = parse_firstrade_excel(content)
            importer = FirstradeImporter()
        else:
            df, importer = _auto_detect(content, filename)

        if df is None or importer is None:
            st.sidebar.error("❌ 无法识别 CSV 格式，请手动选择券商。")
            return

        positions = importer.parse(df)

        # 尝试提取现金（IBKR Activity Statement）
        cash_positions = []
        if importer.BROKER_NAME == "IBKR":
            try:
                cash_positions = extract_cash_from_ibkr(content)
            except Exception:
                pass

        if not positions and not cash_positions:
            st.sidebar.warning("⚠️ CSV 中未找到有效持仓数据。请检查文件格式。")
            st.sidebar.markdown("**原始数据预览:**")
            st.sidebar.dataframe(df.head(5), use_container_width=True)
            return

        # 显示解析预览
        total_count = len(positions) + len(cash_positions)
        st.sidebar.success(f"✅ 检测到 **{importer.BROKER_NAME}** 格式，解析出 **{len(positions)}** 个持仓")

        # 统计: 股票 vs 期权
        stock_count = sum(1 for p in positions if p.asset_type != 'option')
        option_count = sum(1 for p in positions if p.asset_type == 'option')
        if option_count > 0:
            st.sidebar.info(f"其中 {stock_count} 个股票/ETF，{option_count} 个期权合约")

        if cash_positions:
            for cp in cash_positions:
                st.sidebar.info(f"💵 检测到现金余额: ${cp.quantity:,.2f}")

        preview_data = []
        for p in positions[:15]:  # 最多预览15个
            preview_data.append({
                '代码': p.symbol[:25],
                '数量': p.quantity,
                '均价': f"${p.avg_cost:.2f}",
            })

        if preview_data:
            st.sidebar.dataframe(
                pd.DataFrame(preview_data),
                use_container_width=True,
                hide_index=True,
            )
            if len(positions) > 15:
                st.sidebar.caption(f"... 还有 {len(positions) - 15} 个持仓")

        replace = st.sidebar.checkbox(
            f"替换 {importer.BROKER_NAME} 的所有旧持仓",
            value=True,
            key="replace_broker",
        )

        if st.sidebar.button("📥 确认导入", type="primary", use_container_width=True):
            all_positions = positions + cash_positions
            add_positions(all_positions, replace_broker=replace)
            st.sidebar.success(f"🎉 成功导入 {len(positions)} 个持仓！")
            if cash_positions:
                st.sidebar.success(f"💵 现金余额已更新")
            if 'prices_updated' in st.session_state:
                del st.session_state['prices_updated']
            st.rerun()

    except Exception as e:
        st.sidebar.error(f"❌ 解析文件时出错: {str(e)}")


def _auto_detect(content: bytes, filename: str) -> tuple:
    """自动检测文件格式"""
    import io

    if filename.endswith('.xlsx'):
        try:
            df = parse_firstrade_excel(content)
            if FirstradeImporter.detect(df):
                return df, FirstradeImporter()
        except Exception:
            pass
        return None, None

    text = content.decode('utf-8', errors='ignore')

    try:
        df = parse_ibkr_csv(text)
        if IBKRImporter.detect(df):
            return df, IBKRImporter()
    except Exception:
        pass

    try:
        df = preprocess_schwab_csv(text)
        if SchwabImporter.detect(df):
            return df, SchwabImporter()
    except Exception:
        pass

    try:
        df = pd.read_csv(io.StringIO(text))
        if IBKRImporter.detect(df):
            return df, IBKRImporter()
        if SchwabImporter.detect(df):
            return df, SchwabImporter()
    except Exception:
        pass

    return None, None


def _render_cash_form():
    """现金余额输入表单"""
    with st.sidebar.form("cash_form", clear_on_submit=False):
        broker = st.selectbox("券商", ["IBKR", "Schwab", "Firstrade", "其他"], key="cash_broker")
        amount = st.number_input(
            "现金余额 ($)",
            min_value=0.0,
            step=100.0,
            key="cash_amount",
            help="输入该券商账户中的现金/购买力余额",
        )

        submitted = st.form_submit_button("💵 更新现金", use_container_width=True)

        if submitted and amount > 0:
            broker_name = broker if broker != "其他" else "Manual"
            add_cash(broker_name, amount)
            st.success(f"✅ 已更新 {broker} 现金余额: ${amount:,.2f}")
            if 'prices_updated' in st.session_state:
                del st.session_state['prices_updated']
            st.rerun()


def _render_manual_add_form():
    """手动添加持仓表单"""
    with st.sidebar.form("manual_add_form", clear_on_submit=True):
        broker = st.selectbox("券商", ["IBKR", "Schwab", "Firstrade", "其他"], key="manual_broker")
        symbol = st.text_input("股票代码", placeholder="例: AAPL", key="manual_symbol")
        quantity = st.number_input("数量", min_value=0.0, step=1.0, key="manual_qty")
        avg_cost = st.number_input("买入均价 ($)", min_value=0.0, step=0.01, key="manual_cost")

        submitted = st.form_submit_button("➕ 添加", use_container_width=True)

        if submitted:
            if symbol and quantity > 0 and avg_cost > 0:
                pos = Position(
                    broker=broker if broker != "其他" else "Manual",
                    symbol=symbol.upper().strip(),
                    quantity=quantity,
                    avg_cost=avg_cost,
                )
                pos.compute_derived()
                add_positions([pos])
                st.success(f"✅ 已添加 {symbol.upper()}")
                if 'prices_updated' in st.session_state:
                    del st.session_state['prices_updated']
                st.rerun()
            else:
                st.error("请填写完整信息")


def _render_manage_section():
    """管理持仓区域"""
    positions = load_positions()

    if not positions:
        st.sidebar.info("暂无持仓数据")
        return

    # 按券商删除
    brokers = sorted(set(p.broker for p in positions))
    for broker in brokers:
        broker_positions = [p for p in positions if p.broker == broker]
        if st.sidebar.button(
            f"🗑️ 清除 {broker} 所有持仓 ({len(broker_positions)}个)",
            key=f"del_broker_{broker}",
        ):
            remove_broker_positions(broker)
            if 'prices_updated' in st.session_state:
                del st.session_state['prices_updated']
            st.rerun()

    # 删除单个持仓（只显示非期权的主要持仓，避免列表过长）
    st.sidebar.markdown("---")
    st.sidebar.markdown("**删除单个持仓:**")
    non_option = [p for p in positions if p.asset_type != 'option']
    # 按symbol字母排序，显示所有非期权持仓
    non_option_sorted = sorted(non_option, key=lambda p: p.symbol)
    for p in non_option_sorted:
        col1, col2 = st.sidebar.columns([3, 1])
        with col1:
            if p.asset_type == 'cash':
                st.markdown(f"💵 `{p.broker}` **{p.currency}** ${p.quantity:,.0f}")
            else:
                st.markdown(f"`{p.broker}` **{p.symbol}** ×{p.quantity:.0f}")
        with col2:
            if st.button("🗑️", key=f"del_{p.id}"):
                remove_position(p.id)
                if 'prices_updated' in st.session_state:
                    del st.session_state['prices_updated']
                st.rerun()
