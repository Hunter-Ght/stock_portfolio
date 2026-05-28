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

    def test_closed_positions_are_loaded_from_separate_review_pool(self):
        from services.closed_positions import add_closed_position, load_closed_positions, remove_closed_position

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "closed_positions.json"

            add_closed_position("crcl", notes="卖出后复盘", path=path)
            add_closed_position("CRCL", notes="重复不新增", path=path)
            add_closed_position("688981.SH", notes="A股复盘", path=path)

            items = load_closed_positions(path=path)
            self.assertEqual([item["symbol"] for item in items], ["CRCL", "688981.SH"])
            self.assertEqual(items[0]["notes"], "卖出后复盘")
            self.assertIn("closed_at", items[0])

            remove_closed_position("crcl", path=path)
            self.assertEqual([item["symbol"] for item in load_closed_positions(path=path)], ["688981.SH"])

    def test_a_share_watchlist_migrates_from_us_watchlist(self):
        from services.a_share_lists import load_a_share_watchlist

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            us_path = root / "watchlist.json"
            a_path = root / "a_share_watchlist.json"
            us_path.write_text(json.dumps({
                "symbols": [
                    {"symbol": "AAPL", "notes": "us"},
                    {"symbol": "688981", "notes": "smic"},
                    {"symbol": "600519.SS", "notes": "moutai"},
                ]
            }), encoding="utf-8")

            migrated = load_a_share_watchlist(path=a_path, source_watchlist_path=us_path)
            remaining = json.loads(us_path.read_text(encoding="utf-8"))["symbols"]

        self.assertEqual([item["symbol"] for item in migrated], ["688981", "600519.SS"])
        self.assertEqual([item["symbol"] for item in remaining], ["AAPL"])

    def test_a_share_closed_positions_migrate_from_us_closed_positions(self):
        from services.a_share_lists import load_a_share_closed_positions

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            us_path = root / "closed_positions.json"
            a_path = root / "a_share_closed_positions.json"
            us_path.write_text(json.dumps({
                "symbols": [
                    {"symbol": "CRCL", "notes": "us closed"},
                    {"symbol": "300136", "notes": "a closed"},
                ]
            }), encoding="utf-8")

            migrated = load_a_share_closed_positions(path=a_path, source_closed_path=us_path)
            remaining = json.loads(us_path.read_text(encoding="utf-8"))["symbols"]

        self.assertEqual([item["symbol"] for item in migrated], ["300136"])
        self.assertEqual([item["symbol"] for item in remaining], ["CRCL"])

    def test_a_share_position_store_saves_numeric_code_and_computes_values(self):
        from services.a_share_portfolio import add_a_share_position, load_a_share_positions, remove_a_share_position

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a_share_positions.json"

            add_a_share_position("688981.SH", quantity=100, avg_cost=90, name="中芯国际", path=path)
            positions = load_a_share_positions(path=path)

            self.assertEqual(positions[0].symbol, "688981")
            self.assertEqual(positions[0].description, "中芯国际")
            self.assertEqual(positions[0].currency, "CNY")
            self.assertEqual(positions[0].cost_basis, 9000)

            remove_a_share_position(positions[0].id, path=path)
            self.assertEqual(load_a_share_positions(path=path), [])

    def test_add_a_share_position_refreshes_only_added_symbol_price(self):
        from unittest.mock import patch

        from services.a_share_portfolio import add_a_share_position, load_a_share_positions

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "a_share_positions.json"

            with patch("services.a_share_portfolio.get_a_share_quotes") as get_quotes:
                get_quotes.return_value = {
                    "688126": {
                        "price": 24.45,
                        "previous_close": 24.07,
                        "day_change": 0.38,
                        "day_change_pct": 1.5787,
                        "name": "沪硅产业",
                    }
                }
                add_a_share_position("688126", quantity=400, avg_cost=22.865, path=path)

            positions = load_a_share_positions(path=path)

        get_quotes.assert_called_once_with(["688126"])
        self.assertEqual(len(positions), 1)
        self.assertEqual(positions[0].symbol, "688126")
        self.assertEqual(positions[0].description, "沪硅产业")
        self.assertEqual(positions[0].current_price, 24.45)
        self.assertEqual(positions[0].day_change_pct, 1.5787)

    def test_a_share_portfolio_summary_uses_cny_values(self):
        from importers.base import Position
        from services.a_share_portfolio import get_a_share_portfolio_summary

        positions = [
            Position(symbol="688981", description="中芯国际", quantity=100, avg_cost=90, current_price=120, currency="CNY"),
            Position(symbol="600519", description="贵州茅台", quantity=10, avg_cost=1400, current_price=1500, currency="CNY"),
        ]
        for position in positions:
            position.compute_derived()

        summary = get_a_share_portfolio_summary(positions)

        self.assertEqual(summary["position_count"], 2)
        self.assertEqual(summary["total_market_value"], 27000)
        self.assertEqual(summary["total_cost_basis"], 23000)
        self.assertEqual(summary["total_pnl"], 4000)
        self.assertAlmostEqual(summary["total_pnl_pct"], 17.3913, places=3)
        self.assertEqual(summary["total_day_change"], 0)

    def test_build_stock_pool_includes_closed_review_items_after_holdings_and_watchlist(self):
        from importers.base import Position
        from services.research_store import ResearchReport, build_stock_pool

        positions = [
            Position(broker="IBKR", symbol="AAPL", quantity=10, avg_cost=100, current_price=120),
        ]
        reports = {
            "AAPL": ResearchReport(path=Path("AAPL.json"), markdown_path=None, meta={"generated_at": "2026-05-11T10:00:00-07:00"}, analysis={"ticker": "AAPL", "action": "hold", "price_plan": {}}),
            "CRCL": ResearchReport(path=Path("CRCL.json"), markdown_path=None, meta={"generated_at": "2026-05-12T10:00:00-07:00"}, analysis={"ticker": "CRCL", "action": "watch", "scores": {"total_score": 63}, "price_plan": {"current_price": 121.1}}),
        }

        pool = build_stock_pool(
            positions,
            watchlist_symbols=[],
            reports_by_ticker=reports,
            closed_items=[{"symbol": "CRCL", "notes": "卖出后复盘", "closed_at": "2026-05-15"}],
        )

        self.assertEqual([row["symbol"] for row in pool], ["AAPL", "CRCL"])
        self.assertEqual(pool[1]["source"], "已平仓复盘")
        self.assertEqual(pool[1]["note"], "卖出后复盘")
        self.assertEqual(pool[1]["has_analysis"], True)

    def test_build_stock_pool_excludes_closed_review_when_symbol_is_active(self):
        from importers.base import Position
        from services.research_store import build_stock_pool

        positions = [
            Position(broker="IBKR", symbol="AAPL", quantity=10, avg_cost=100, current_price=120),
        ]

        pool = build_stock_pool(
            positions,
            watchlist_symbols=["CRCL"],
            reports_by_ticker={},
            closed_items=[
                {"symbol": "AAPL", "notes": "重新买回"},
                {"symbol": "CRCL", "notes": "重新关注"},
                {"symbol": "MSFT", "notes": "继续复盘"},
            ],
        )

        self.assertEqual([row["symbol"] for row in pool], ["AAPL", "CRCL", "MSFT"])
        self.assertEqual([row["source"] for row in pool], ["持仓", "关注", "已平仓复盘"])

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

    def test_sina_quote_parser_supports_star_market_symbol(self):
        from services.a_share_market_data import _parse_sina_quote_response, _sina_symbol

        response = (
            'var hq_str_sh688126="沪硅产业,24.070,24.070,24.450,25.700,23.730,'
            '24.450,24.460,121305248,2995673449.000,12428,24.450,'
            '2026-05-18,14:31:18,00,";'
        )

        quote = _parse_sina_quote_response(response)

        self.assertEqual(_sina_symbol("688126"), "sh688126")
        self.assertEqual(_sina_symbol("300750"), "sz300750")
        self.assertEqual(quote["name"], "沪硅产业")
        self.assertEqual(quote["price"], 24.45)
        self.assertEqual(quote["previous_close"], 24.07)
        self.assertAlmostEqual(quote["day_change"], 0.38, places=2)
        self.assertAlmostEqual(quote["day_change_pct"], 1.5787, places=3)

    def test_sina_name_parser_supports_star_market_symbol(self):
        from services.a_share_names import _parse_sina_name_response, _sina_symbol

        response = 'var hq_str_sh688126="沪硅产业,24.070,24.070,24.450,25.700,23.730";'

        self.assertEqual(_sina_symbol("688126"), "sh688126")
        self.assertEqual(_parse_sina_name_response(response), "沪硅产业")

    def test_eastmoney_price_parser_scales_integer_cents(self):
        from services.a_share_market_data import _eastmoney_price

        self.assertEqual(_eastmoney_price(2454), 24.54)
        self.assertEqual(_eastmoney_price(47), 0.47)
        self.assertEqual(_eastmoney_price("24.54"), 24.54)

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

    def test_load_flat_json_report_new_format(self):
        """New flat format (no meta/ticker_analysis wrappers) is loaded correctly."""
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report_path = root / "2026-05-27_CRM_xiaoyan_shufen.json"
            report_path.write_text(json.dumps({
                "schema_version": "1.1.0",
                "generated_at": "2026-05-27T12:00:00-07:00",
                "ticker": "CRM",
                "market": "US",
                "company": "Salesforce, Inc.",
                "skills": ["xiaoyan", "shufen"],
                "action": "watch / buy_on_pullback",
                "scores": {
                    "total_score": 70,
                    "xiaoyan": 35,
                    "shufen": 35,
                },
                "sector": "tech",
                "price_plan": {
                    "current_price": 183.0,
                    "buy_zone": [163, 178],
                    "trim_zone": [230, 255],
                    "invalid_price": 152,
                    "hard_stop": 145,
                },
                "watch_triggers": [
                    "FY2027 全年指引下调任何幅度",
                    "cRPO 同比跌破 12%",
                ],
            }), encoding="utf-8")

            reports = load_latest_reports_by_ticker([root])

        self.assertEqual(set(reports), {"CRM"})
        report = reports["CRM"]
        self.assertEqual(report.ticker, "CRM")
        self.assertEqual(report.meta["generated_at"], "2026-05-27T12:00:00-07:00")
        self.assertEqual(report.analysis["action"], "watch / buy_on_pullback")
        self.assertEqual(report.analysis["sector"], "tech")
        self.assertEqual(report.analysis["scores"]["total_score"], 70)
        self.assertEqual(report.analysis["price_plan"]["current_price"], 183.0)
        self.assertEqual(report.analysis["watch_triggers"], ["FY2027 全年指引下调任何幅度", "cRPO 同比跌破 12%"])

    def test_flat_format_normalizes_shufen_scores(self):
        """scores.shufen in new format is synthesized into shufen_scores.total_score."""
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "2026-05-27_CRM_xiaoyan_shufen.json").write_text(json.dumps({
                "schema_version": "1.1.0",
                "generated_at": "2026-05-27T12:00:00-07:00",
                "ticker": "CRM",
                "market": "US",
                "scores": {"total_score": 70, "xiaoyan": 35, "shufen": 35},
                "price_plan": {"current_price": 183.0},
            }), encoding="utf-8")

            reports = load_latest_reports_by_ticker([root])

        report = reports["CRM"]
        self.assertEqual(report.analysis["shufen_scores"]["total_score"], 35)

    def test_flat_format_and_old_format_coexist(self):
        """Old-format report for AAPL and new-format for CRM can be loaded together."""
        from services.research_store import load_latest_reports_by_ticker

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "2026-05-12_AAPL_xiaoyan_shufen.json").write_text(json.dumps({
                "meta": {"generated_at": "2026-05-12T10:00:00-07:00"},
                "ticker_analysis": [{
                    "ticker": "AAPL",
                    "action": "hold",
                    "scores": {"total_score": 65},
                    "price_plan": {"current_price": 200.0},
                }],
            }), encoding="utf-8")
            (root / "2026-05-27_CRM_xiaoyan_shufen.json").write_text(json.dumps({
                "schema_version": "1.1.0",
                "generated_at": "2026-05-27T12:00:00-07:00",
                "ticker": "CRM",
                "market": "US",
                "scores": {"total_score": 70, "xiaoyan": 35, "shufen": 35},
                "price_plan": {"current_price": 183.0},
            }), encoding="utf-8")

            reports = load_latest_reports_by_ticker([root])

        self.assertIn("AAPL", reports)
        self.assertIn("CRM", reports)
        self.assertEqual(reports["AAPL"].analysis["scores"]["total_score"], 65)
        self.assertEqual(reports["CRM"].analysis["scores"]["total_score"], 70)

    def test_infer_sector_key_maps_free_text_to_config_key(self):
        from services.sector_config import infer_sector_key

        self.assertEqual(infer_sector_key("Industrials / Aerospace & Defense Materials"), "ind")
        self.assertEqual(infer_sector_key("Technology / AI Cloud Platform"), "tech")
        self.assertEqual(infer_sector_key("Biotech / Oncology"), "bio")
        self.assertEqual(infer_sector_key("Materials / Lithium Mining"), "mat")
        self.assertEqual(infer_sector_key("Nuclear Power Generation"), "nuc")
        self.assertEqual(infer_sector_key("Real Estate"), "oth")

    def test_build_sector_view_groups_tickers_by_sector(self):
        from pathlib import Path
        from services.research_store import ResearchReport
        from services.sector_config import build_sector_view

        reports = {
            "CRM": ResearchReport(
                path=Path("CRM.json"), markdown_path=None,
                meta={"generated_at": "2026-05-27T12:00:00-07:00"},
                analysis={
                    "ticker": "CRM", "company": "Salesforce, Inc.",
                    "action": "watch", "sector": "tech",
                    "watch_triggers": ["FY2027 指引下调"],
                },
            ),
            "ATI": ResearchReport(
                path=Path("ATI.json"), markdown_path=None,
                meta={"generated_at": "2026-05-12T10:00:00-07:00"},
                analysis={
                    "ticker": "ATI", "company": "ATI Inc.",
                    "action": "hold", "sector": "Industrials / Aerospace & Defense",
                    "watch_triggers": [],
                },
            ),
        }

        sector_view = build_sector_view(reports)

        tech_tickers = [e["ticker"] for e in sector_view["tech"]["tickers"]]
        ind_tickers = [e["ticker"] for e in sector_view["ind"]["tickers"]]
        self.assertIn("CRM", tech_tickers)
        self.assertIn("ATI", ind_tickers)
        crm_entry = next(e for e in sector_view["tech"]["tickers"] if e["ticker"] == "CRM")
        self.assertEqual(crm_entry["watch_triggers"], ["FY2027 指引下调"])
        self.assertIn("sector_triggers", sector_view["tech"])


if __name__ == "__main__":
    unittest.main()
