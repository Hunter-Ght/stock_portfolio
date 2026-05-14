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

    def test_load_a_share_report_uses_new_filename_format(self):
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "2026-05-13_600519_MOUTAI_FLT_Ashare.json"
            report_path.write_text(json.dumps({
                "meta": {
                    "schema_version": "1.0.0",
                    "generated_at": "2026-05-13T10:00:00-07:00",
                },
                "ticker_analysis": [{
                    "company": "贵州茅台",
                    "action": "hold",
                    "scores": {"total_score": 80},
                    "price_plan": {"current_price": 1500},
                }],
            }), encoding="utf-8")
            (root / "2026-05-13_600519_MOUTAI_FLT_Ashare.md").write_text("# 贵州茅台", encoding="utf-8")

            reports = load_latest_reports_by_ticker([root])

        self.assertEqual(set(reports), {"600519"})
        report = reports["600519"]
        self.assertEqual(report.ticker, "600519")
        self.assertEqual(report.analysis["ticker"], "600519")
        self.assertEqual(report.analysis["letter_code"], "MOUTAI")
        self.assertEqual(report.analysis["market"], "Ashare")
        self.assertEqual(report.meta["skills"], ["FLT"])
        self.assertEqual(report.markdown_path.name, "2026-05-13_600519_MOUTAI_FLT_Ashare.md")

    def test_load_a_share_report_accepts_flt_scores_and_exchange_suffix(self):
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "2026-05-13_688981_SMIC_FLT_Ashare.json"
            report_path.write_text(json.dumps({
                "meta": {
                    "schema_version": "1.0.0",
                    "generated_at": "2026-05-13T10:30:00-07:00",
                },
                "ticker_analysis": [{
                    "ticker": "688981.SH",
                    "company": "中芯国际",
                    "action": "watch",
                    "flt_scores": {"total_score": 73},
                    "price_plan": {"current_price": 121.86},
                }],
            }), encoding="utf-8")

            reports = load_latest_reports_by_ticker([root])

        self.assertEqual(set(reports), {"688981"})
        self.assertEqual(reports["688981"].ticker, "688981")
        self.assertEqual(reports["688981"].analysis["scores"]["total_score"], 73)
        self.assertEqual(reports["688981"].analysis["flt_scores"]["total_score"], 73)

    def test_load_report_from_markdown_front_matter_without_json(self):
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "2026-05-13_688981_SMIC_FLT_Ashare.md"
            front_matter = {
                "schema_version": "1.0.0",
                "generated_at": "2026-05-13T10:30:00-07:00",
                "ticker": "688981.SH",
                "market": "Ashare",
                "company": "中芯国际",
                "skills": ["FLT"],
                "action": "hold_no_add / buy_on_pullback",
                "flt_scores": {"total_score": 73},
                "price_plan": {
                    "current_price": 121.86,
                    "buy_zone": [108, 116],
                    "trim_zone": [145, 160],
                    "invalid_price": 106,
                    "hard_stop": 100,
                },
            }
            report_path.write_text(
                "---\n"
                + json.dumps(front_matter, ensure_ascii=False, indent=2)
                + "\n---\n\n# 中芯国际完整报告\n",
                encoding="utf-8",
            )

            reports = load_latest_reports_by_ticker([root])

        self.assertEqual(set(reports), {"688981"})
        report = reports["688981"]
        self.assertEqual(report.path.name, "2026-05-13_688981_SMIC_FLT_Ashare.md")
        self.assertEqual(report.markdown_path.name, "2026-05-13_688981_SMIC_FLT_Ashare.md")
        self.assertEqual(report.ticker, "688981")
        self.assertEqual(report.meta["generated_at"], "2026-05-13T10:30:00-07:00")
        self.assertEqual(report.analysis["company"], "中芯国际")
        self.assertEqual(report.analysis["scores"]["total_score"], 73)
        self.assertEqual(report.analysis["price_plan"]["buy_zone"], [108, 116])

    def test_json_report_wins_when_matching_markdown_front_matter_exists(self):
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "2026-05-12_CRCL_xiaoyan_shufen.json"
            json_path.write_text(json.dumps({
                "meta": {"generated_at": "2026-05-12T10:00:00-07:00"},
                "ticker_analysis": [{
                    "ticker": "CRCL",
                    "action": "json_action",
                    "scores": {"total_score": 63},
                    "price_plan": {"current_price": 121.1},
                }],
            }), encoding="utf-8")
            md_path = root / "2026-05-12_CRCL_xiaoyan_shufen.md"
            md_path.write_text(
                "---\n"
                + json.dumps({
                    "generated_at": "2026-05-12T11:00:00-07:00",
                    "ticker": "CRCL",
                    "action": "markdown_action",
                    "scores": {"total_score": 99},
                    "price_plan": {"current_price": 130},
                })
                + "\n---\n\n# CRCL\n",
                encoding="utf-8",
            )

            reports = load_latest_reports_by_ticker([root])

        self.assertEqual(reports["CRCL"].analysis["action"], "json_action")
        self.assertEqual(reports["CRCL"].analysis["scores"]["total_score"], 63)
        self.assertEqual(reports["CRCL"].markdown_path.name, "2026-05-12_CRCL_xiaoyan_shufen.md")

    def test_default_report_dirs_include_us_and_a_share_subfolders(self):
        from services.research_store import default_report_dirs

        names = [path.as_posix() for path in default_report_dirs()]

        self.assertTrue(any(path.endswith("research_reports/us") for path in names))
        self.assertTrue(any(path.endswith("research_reports/a_share") for path in names))

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

    def test_a_share_symbol_detection(self):
        from components.stock_workbench import _is_a_share_symbol

        self.assertTrue(_is_a_share_symbol("600519.SS"))
        self.assertTrue(_is_a_share_symbol("000001.SZ"))
        self.assertTrue(_is_a_share_symbol("688001"))
        self.assertFalse(_is_a_share_symbol("AAPL"))
        self.assertFalse(_is_a_share_symbol("0700.HK"))

    def test_a_share_rows_only_include_holdings(self):
        from components.stock_workbench import _a_share_holding_rows

        rows = [
            {"symbol": "600519.SS", "source": "持仓"},
            {"symbol": "000001.SZ", "source": "关注"},
            {"symbol": "AAPL", "source": "持仓"},
        ]

        self.assertEqual([row["symbol"] for row in _a_share_holding_rows(rows)], ["600519.SS"])

    def test_a_share_watch_rows_only_include_watchlist(self):
        from components.stock_workbench import _a_share_watch_rows

        rows = [
            {"symbol": "600519.SS", "source": "持仓"},
            {"symbol": "000001.SZ", "source": "关注"},
            {"symbol": "AAPL", "source": "关注"},
        ]

        self.assertEqual([row["symbol"] for row in _a_share_watch_rows(rows)], ["000001.SZ"])

    def test_a_share_ticker_display_uses_company_name(self):
        from components.stock_workbench import _pool_table_rows

        rows = [{
            "symbol": "600519.SS",
            "source": "持仓",
            "is_a_share_view": True,
            "company_name": "贵州茅台",
            "current_price": 1500,
            "price_plan": {},
            "alerts": [],
        }]

        self.assertEqual(_pool_table_rows(rows)[0]["Ticker"], "600519.SS · 贵州茅台")

    def test_a_share_name_cache_normalizes_numeric_code(self):
        from services.a_share_names import load_a_share_names, set_a_share_name

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a_share_names.json"

            set_a_share_name("600519.SS", "贵州茅台", path=path)

            self.assertEqual(load_a_share_names(path=path), {"600519": "贵州茅台"})

    def test_build_stock_pool_matches_numeric_a_share_report_to_suffixed_holding(self):
        from importers.base import Position
        from services.research_store import ResearchReport, build_stock_pool

        positions = [
            Position(broker="IBKR", symbol="600519.SS", quantity=10, avg_cost=100, current_price=120),
        ]
        reports = {
            "600519": ResearchReport(
                path=Path("600519.json"),
                markdown_path=None,
                meta={"generated_at": "2026-05-13T10:00:00-07:00"},
                analysis={"ticker": "600519", "company": "贵州茅台", "price_plan": {"current_price": 120}, "scores": {"total_score": 80}},
            ),
        }

        pool = build_stock_pool(positions, watchlist_symbols=[], reports_by_ticker=reports)

        self.assertTrue(pool[0]["has_analysis"])
        self.assertEqual(pool[0]["report"].ticker, "600519")

    def test_orphan_reports_normalizes_a_share_pool_symbols(self):
        from services.research_store import ResearchReport, orphan_reports

        reports = {
            "600519": ResearchReport(
                path=Path("600519.json"),
                markdown_path=None,
                meta={},
                analysis={"ticker": "600519", "price_plan": {"current_price": 120}, "scores": {"total_score": 80}},
            ),
            "000001": ResearchReport(
                path=Path("000001.json"),
                markdown_path=None,
                meta={},
                analysis={"ticker": "000001", "price_plan": {"current_price": 10}, "scores": {"total_score": 70}},
            ),
        }

        orphans = orphan_reports(reports, [{"symbol": "600519.SS"}])

        self.assertEqual([report.ticker for report in orphans], ["000001"])

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
