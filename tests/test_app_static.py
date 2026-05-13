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


if __name__ == "__main__":
    unittest.main()
