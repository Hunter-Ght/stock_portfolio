import ast
import unittest
from pathlib import Path


class AppStaticTest(unittest.TestCase):
    def test_is_light_is_defined_before_empty_state_branch_uses_it(self):
        tree = ast.parse(Path("pages/holdings_tracker.py").read_text(encoding="utf-8"))
        first_assignment = None
        first_load = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id == "is_light":
                if isinstance(node.ctx, ast.Store):
                    first_assignment = node.lineno if first_assignment is None else min(first_assignment, node.lineno)
                elif isinstance(node.ctx, ast.Load):
                    first_load = node.lineno if first_load is None else min(first_load, node.lineno)

        self.assertIsNotNone(first_assignment)
        self.assertIsNotNone(first_load)
        self.assertLess(first_assignment, first_load)

    def test_import_panel_requests_price_refresh_after_position_adds(self):
        source = Path("components/import_panel.py").read_text(encoding="utf-8")

        self.assertIn("def _request_price_refresh", source)
        self.assertGreaterEqual(source.count("_request_price_refresh()"), 3)

    def test_stock_workbench_refresh_control_runs_before_report_load(self):
        source = Path("components/stock_workbench.py").read_text(encoding="utf-8")

        self.assertIn("刷新分析文件", source)
        self.assertLess(
            source.index("_render_analysis_refresh_control()"),
            source.index("load_latest_reports_by_ticker()"),
        )

    def test_stock_workbench_detail_only_keeps_full_report(self):
        source = Path("components/stock_workbench.py").read_text(encoding="utf-8")
        detail_source = source[source.index("def _render_detail"):source.index("def _render_orphan_reports")]

        self.assertIn("完整报告", detail_source)
        self.assertNotIn("决策摘要", detail_source)
        self.assertNotIn("价格计划", detail_source)
        self.assertNotIn("交易规则", detail_source)
        self.assertNotIn("催化验证", detail_source)

    def test_stock_workbench_has_a_share_holdings_tab(self):
        source = Path("components/stock_workbench.py").read_text(encoding="utf-8")

        self.assertIn("已平仓复盘", source)
        self.assertIn("market == \"Ashare\"", source)
        self.assertIn('st.tabs(["A股持仓", "A股关注", "已平仓复盘", "未归档分析"])', source)
        self.assertIn('st.tabs(["持仓", "关注", "已平仓复盘", "未归档分析"])', source)

    def test_navigation_splits_us_and_a_share_pages(self):
        source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('title="持仓追踪"', source)
        self.assertIn('title="美股工作台"', source)
        self.assertIn('title="A股持仓追踪"', source)
        self.assertIn('title="A股工作台"', source)
        self.assertIn("pages/a_share_holdings.py", source)
        self.assertIn("pages/a_share_analysis.py", source)

    def test_a_share_pages_call_a_share_components(self):
        holdings = Path("pages/a_share_holdings.py").read_text(encoding="utf-8")
        analysis = Path("pages/a_share_analysis.py").read_text(encoding="utf-8")

        self.assertIn("render_a_share_holdings", holdings)
        self.assertIn('render_stock_workbench(market="Ashare")', analysis)

    def test_a_share_holdings_page_is_dashboard_style(self):
        source = Path("components/a_share_holdings.py").read_text(encoding="utf-8")

        self.assertIn('st.title("A股持仓追踪")', source)
        self.assertIn("get_a_share_portfolio_summary", source)
        self.assertIn("render_a_share_overview", source)
        self.assertIn("render_a_share_allocation_chart", source)
        self.assertIn("render_a_share_pnl_chart", source)
        self.assertIn("render_a_share_positions_table", source)
        self.assertIn("管理 A股持仓", source)

    def test_a_share_pnl_chart_matches_us_horizontal_bar_style(self):
        source = Path("components/a_share_holdings.py").read_text(encoding="utf-8")
        chart_source = source[source.index("def render_a_share_pnl_chart"):source.index("def render_a_share_positions_table")]

        self.assertIn("go.Figure()", chart_source)
        self.assertIn("orientation=\"h\"", chart_source)
        self.assertIn("sort_values(\"pnl\", ascending=True)", chart_source)
        self.assertIn("'#ef4444' if value < 0 else '#22c55e'", chart_source)
        self.assertIn("盈亏金额 (CNY)", chart_source)

    def test_stock_workbench_has_closed_review_actions(self):
        source = Path("components/stock_workbench.py").read_text(encoding="utf-8")

        self.assertIn("load_closed_positions", source)
        self.assertIn("add_closed_position", source)
        self.assertIn("remove_closed_position", source)
        self.assertIn("移入复盘", source)
        self.assertIn("移回关注", source)
        self.assertIn("移出复盘", source)

    def test_stock_workbench_does_not_auto_render_first_detail(self):
        source = Path("components/stock_workbench.py").read_text(encoding="utf-8")
        selector_source = source[source.index("def _render_pool_detail_selector"):source.index("def _render_detail")]

        self.assertIn('[""] + [row["symbol"] for row in rows]', selector_source)
        self.assertIn('if selected:', selector_source)
        self.assertIn('placeholder="选择后加载详情"', selector_source)

    def test_stock_workbench_uses_cached_quotes_with_manual_refresh(self):
        source = Path("components/stock_workbench.py").read_text(encoding="utf-8")

        self.assertIn("刷新行情", source)
        self.assertIn("@st.cache_data(ttl=900", source)
        self.assertIn("_current_prices.clear()", source)


if __name__ == "__main__":
    unittest.main()
