import json
import tempfile
import unittest
from pathlib import Path


class StockWorkbenchServicesTest(unittest.TestCase):
    def test_load_latest_reports_by_ticker_uses_filename_and_generated_at(self):
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            older = root / "2026-05-11_CRCL_xiaoyan.json"
            newer = root / "2026-05-12_CRCL_xiaoyan_shufen.json"
            older.write_text(json.dumps({
                "meta": {
                    "schema_version": "1.0.0",
                    "report_id": "old",
                    "generated_at": "2026-05-11T10:00:00-07:00",
                    "tickers": ["CRCL"],
                },
                "ticker_analysis": [{
                    "ticker": "CRCL",
                    "action": "watch",
                    "conclusion": "old",
                    "scores": {"total_score": 50},
                    "price_plan": {"current_price": 100, "buy_zone": [90, 95], "trim_zone": [120, 130], "invalid_price": 80},
                }],
            }), encoding="utf-8")
            newer.write_text(json.dumps({
                "meta": {
                    "schema_version": "1.0.0",
                    "report_id": "new",
                    "generated_at": "2026-05-12T10:00:00-07:00",
                    "tickers": ["CRCL"],
                },
                "ticker_analysis": [{
                    "ticker": "CRCL",
                    "action": "buy_on_pullback",
                    "conclusion": "new",
                    "scores": {"total_score": 63},
                    "price_plan": {"current_price": 121.1, "buy_zone": [105, 115], "trim_zone": [140, 150], "invalid_price": 88},
                }],
            }), encoding="utf-8")
            (root / "2026-05-12_CRCL_xiaoyan_shufen.md").write_text("# Full report", encoding="utf-8")

            reports = load_latest_reports_by_ticker([root])

        self.assertEqual(set(reports), {"CRCL"})
        self.assertEqual(reports["CRCL"].meta["report_id"], "new")
        self.assertEqual(reports["CRCL"].analysis["action"], "buy_on_pullback")
        self.assertEqual(reports["CRCL"].markdown_path.name, "2026-05-12_CRCL_xiaoyan_shufen.md")

    def test_build_stock_pool_only_includes_holdings_and_watchlist(self):
        from importers.base import Position
        from services.research_store import ResearchReport, build_stock_pool

        positions = [
            Position(broker="IBKR", symbol="AAPL", quantity=10, avg_cost=100, current_price=120),
            Position(broker="IBKR", symbol="CASH_USD", quantity=1000, asset_type="cash"),
        ]
        reports = {
            "CRCL": ResearchReport(path=Path("CRCL.json"), markdown_path=None, meta={"generated_at": "2026-05-12T10:00:00-07:00"}, analysis={"ticker": "CRCL", "action": "watch", "price_plan": {}}),
            "AAPL": ResearchReport(path=Path("AAPL.json"), markdown_path=None, meta={"generated_at": "2026-05-11T10:00:00-07:00"}, analysis={"ticker": "AAPL", "action": "hold", "price_plan": {}}),
        }

        pool = build_stock_pool(positions, watchlist_symbols=["CRCL"], reports_by_ticker=reports)

        self.assertEqual([row["symbol"] for row in pool], ["AAPL", "CRCL"])
        self.assertEqual(pool[0]["source"], "持仓")
        self.assertEqual(pool[0]["has_analysis"], True)
        self.assertEqual(pool[1]["source"], "关注")
        self.assertEqual(pool[1]["has_analysis"], True)

    def test_build_stock_pool_matches_dashboard_stock_position_scope(self):
        from importers.base import Position
        from services.research_store import build_stock_pool

        positions = [
            Position(id="stock-aapl", broker="IBKR", symbol="AAPL", quantity=100, avg_cost=100, current_price=120),
            Position(id="call-aapl", broker="IBKR", symbol="AAPL 260618C00150000", quantity=-1, avg_cost=2, current_price=1),
            Position(id="stock-msft", broker="IBKR", symbol="MSFT", quantity=10, avg_cost=300, current_price=330),
        ]

        pool = build_stock_pool(positions, watchlist_symbols=[], reports_by_ticker={})

        self.assertEqual([row["symbol"] for row in pool], ["MSFT"])

    def test_select_label_hides_missing_analysis_status(self):
        from components.stock_workbench import _select_label

        rows = [
            {"symbol": "AAPL", "source": "持仓", "has_analysis": False},
            {"symbol": "CRCL", "source": "关注", "has_analysis": True},
        ]

        self.assertEqual(_select_label("AAPL", rows), "AAPL · 持仓")
        self.assertEqual(_select_label("CRCL", rows), "CRCL · 关注 · 有分析")

    def test_pool_table_height_expands_to_show_all_rows(self):
        from components.stock_workbench import _pool_table_height

        self.assertGreaterEqual(_pool_table_height(34), 35 * 34)
        self.assertLess(_pool_table_height(34), 1800)

    def test_pool_table_rows_do_not_include_market_value_column(self):
        from components.stock_workbench import _pool_table_rows

        rows = [{
            "symbol": "CRCL",
            "source": "持仓",
            "note": "等待回踩",
            "current_price": 123.45,
            "market_value": 1234.5,
            "has_analysis": True,
            "analysis_updated_at": "2026-05-12T10:00:00-07:00",
            "action": "watch",
            "total_score": 63,
            "price_plan": {"buy_zone": [105, 115], "trim_zone": [140, 150], "invalid_price": 88, "hard_stop": 80},
            "alerts": [],
        }]

        table_rows = _pool_table_rows(rows)

        self.assertNotIn("市值", table_rows[0])
        self.assertIn("备注", table_rows[0])
        self.assertEqual(table_rows[0]["失效价"], "$88.00")
        self.assertEqual(table_rows[0]["Hard Stop"], "$80.00")

    def test_current_price_color_uses_buy_upper_and_trim_lower(self):
        from components.stock_workbench import _current_price_color

        self.assertEqual(_current_price_color(114, {"buy_zone": [105, 115]}), "color: #dc2626; font-weight: 700")
        self.assertEqual(_current_price_color(151, {"trim_zone": [150, 160]}), "color: #16a34a; font-weight: 700")
        self.assertEqual(_current_price_color(130, {"buy_zone": [105, 115], "trim_zone": [150, 160]}), "")

    def test_current_price_color_prefers_trim_when_both_match(self):
        from components.stock_workbench import _current_price_color

        self.assertEqual(
            _current_price_color(120, {"buy_zone": [100, 130], "trim_zone": [110, 140]}),
            "color: #16a34a; font-weight: 700",
        )

    def test_stock_notes_are_saved_by_uppercase_symbol(self):
        from services.stock_notes import load_stock_notes, set_stock_note

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stock_notes.json"

            set_stock_note("crcl", "等待回踩", path=path)
            set_stock_note("AAPL", "估值偏贵", path=path)

            self.assertEqual(load_stock_notes(path=path), {
                "AAPL": "估值偏贵",
                "CRCL": "等待回踩",
            })

    def test_blank_stock_note_removes_symbol(self):
        from services.stock_notes import load_stock_notes, set_stock_note

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "stock_notes.json"

            set_stock_note("CRCL", "等待回踩", path=path)
            set_stock_note("CRCL", "   ", path=path)

            self.assertEqual(load_stock_notes(path=path), {})

    def test_evaluate_price_alerts_for_buy_trim_and_invalid_ranges(self):
        from services.alert_engine import evaluate_price_alerts

        price_plan = {
            "buy_zone": [105, 115],
            "add_zone": [90, 100],
            "trim_zone": [140, 150],
            "invalid_price": 88,
            "hard_stop": 80,
        }
        config = {
            "enabled": True,
            "buy_alert_enabled": True,
            "add_alert_enabled": True,
            "trim_alert_enabled": True,
            "exit_alert_enabled": True,
            "threshold_pct": 5,
        }

        self.assertEqual(evaluate_price_alerts("CRCL", 116, price_plan, config)[0]["type"], "buy")
        self.assertEqual(evaluate_price_alerts("CRCL", 138, price_plan, config)[0]["type"], "trim")
        self.assertEqual(evaluate_price_alerts("CRCL", 87, price_plan, config)[0]["label"], "跌破失效价")
        self.assertEqual(evaluate_price_alerts("CRCL", 121.1, price_plan, config), [])

    def test_evaluate_price_alerts_prioritizes_hard_stop_below_hard_stop(self):
        from services.alert_engine import evaluate_price_alerts

        price_plan = {"invalid_price": 88, "hard_stop": 80}
        config = {"enabled": True, "exit_alert_enabled": True}

        alert = evaluate_price_alerts("CRCL", 79, price_plan, config)[0]

        self.assertEqual(alert["type"], "exit")
        self.assertEqual(alert["label"], "跌破 Hard Stop")


if __name__ == "__main__":
    unittest.main()
