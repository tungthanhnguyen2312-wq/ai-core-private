"""Phase 4 context adapter tests for advanced financial provenance."""

from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from builders import build_ticker_context as builder


class Phase4AdvancedContextTests(unittest.TestCase):
    def test_derived_metrics_keep_formula_and_inputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,"
                "operating_cash_flow,ebit,ebit_status,ebit_basis,ebit_formula,ebit_inputs,"
                "ebitda,ebitda_status,ebitda_reason,interest_expense,interest_expense_status,"
                "retained_earnings_end_period,retained_earnings_status,depreciation,depreciation_status,"
                "sga,sga_status,sga_basis,sga_formula,sga_inputs\n"
                "PAN,2026-Q1,quarter,1,1,1,1,1,,110,derived,derived,profit_before_tax + interest_expense,"
                "\"[\"\"profit_before_tax\"\", \"\"interest_expense\"\"]\",,insufficient_periods,"
                "missing_ebit_or_complete_da_inputs,10,reported,100,reported,,source_empty,70,derived,derived,"
                "selling_expense + general_admin_expense,\"[\"\"selling_expense\"\", \"\"general_admin_expense\"\"]\"\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("PAN")
        self.assertEqual(summary["ebit"], 110)
        self.assertEqual(summary["ebit_meta"]["status"], "derived")
        self.assertEqual(summary["ebit_meta"]["inputs"], ["profit_before_tax", "interest_expense"])
        self.assertEqual(summary["sga_meta"]["status"], "derived")
        self.assertEqual(summary["ebitda_meta"]["status"], "insufficient_periods")
        self.assertEqual(summary["retained_earnings"], 100)

    def test_load_vnstock_entity_type_reuses_the_real_registry(self):
        # item E: identity.entity_type must come from VNSTOCK's own financial_mapping.py
        # registry (dynamic import, same pattern as load_news_slice), never a duplicated
        # classification that could silently drift from what bctc_processor.py used.
        self.assertEqual(builder.load_vnstock_entity_type("PAN"), "corporate")
        self.assertEqual(builder.load_vnstock_entity_type("EVF"), "finance_company")
        self.assertEqual(builder.load_vnstock_entity_type("ZZZZ_NOT_A_REAL_TICKER"), "unknown")

    def test_not_applicable_sga_is_excluded_from_coverage(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,"
                "operating_cash_flow,sga,sga_status,sga_reason\n"
                "VCB,2026-Q1,quarter,1,1,1,1,1,,,not_applicable,corporate_sga_structure_not_applicable\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("VCB")
        self.assertEqual(summary["sga_meta"]["status"], "not_applicable")
        self.assertIn("sga", summary["coverage"]["not_applicable_metrics"])


class RoeMetricAndShareProxyTests(unittest.TestCase):
    """item A/C (Data Contract Hardening v1.1): financial_summary.roe_quarter/roe_fy/roe_ttm
    and eps_calc/book_value must carry full metric-meta (never a bare number that could be
    confused with metadata.roe's differently-scaled trailing percentage)."""

    def test_roe_quarter_meta_carries_unit_basis_and_period_calendar_end(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,"
                "operating_cash_flow,roe_quarter,roe_quarter_unit,roe_quarter_basis,roe_quarter_annualization,"
                "roe_quarter_period,roe_quarter_period_calendar_end,roe_quarter_source,roe_quarter_formula,"
                "roe_quarter_status,roe_quarter_reason,roe_fy,roe_fy_status,roe_fy_reason,"
                "roe_ttm,roe_ttm_status,roe_ttm_reason\n"
                "POW,2026-Q1,quarter,1,1,1,1,1,,0.017514,ratio,quarter_average_equity,none,2026-Q1,2026-03-31,"
                "financial_snapshot_derived,net_profit_quarter / average(equity),derived,,"
                ",not_applicable,not_this_period_type,"
                ",insufficient_periods,requires_four_consecutive_reported_quarters_and_ttm_window_equity\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("POW")
        self.assertAlmostEqual(summary["roe_quarter"], 0.017514, places=6)
        self.assertEqual(summary["roe_quarter_meta"]["unit"], "ratio")
        self.assertEqual(summary["roe_quarter_meta"]["basis"], "quarter_average_equity")
        self.assertEqual(summary["roe_quarter_meta"]["period_calendar_end"], "2026-03-31")
        self.assertEqual(summary["roe_quarter_meta"]["status"], "derived")
        self.assertIsNone(summary["roe_fy"])
        self.assertEqual(summary["roe_fy_meta"]["status"], "not_applicable")
        self.assertIsNone(summary["roe_ttm"])
        self.assertEqual(summary["roe_ttm_meta"]["status"], "insufficient_periods")
        self.assertEqual(
            summary["roe_ttm_meta"]["reason"], "requires_four_consecutive_reported_quarters_and_ttm_window_equity"
        )
        # item design decision #2: never folded into coverage_scope/FINANCIAL_CONTRACT_METRICS.
        self.assertNotIn("roe_quarter", summary["coverage_scope"])

    def test_eps_calc_and_book_value_are_proxy_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,"
                "operating_cash_flow,eps_calc,eps_calc_status,eps_calc_basis,book_value,book_value_status,book_value_basis\n"
                "PAN,2026-Q1,quarter,1,1,1,1,1,,2065.99,proxy,net_profit_over_shares_period_end_not_weighted_average,"
                "46888.0,proxy,equity_over_shares_period_end_not_weighted_average\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("PAN")
        self.assertEqual(summary["eps_calc_meta"]["status"], "proxy")
        self.assertNotEqual(summary["eps_calc_meta"]["status"], "reported")
        self.assertEqual(summary["book_value_meta"]["status"], "proxy")

    def test_valuation_inputs_roe_meta_distinguishes_external_percent_from_local_ratio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db_path = root / "vn_stock.db"
            connection = sqlite3.connect(db_path)
            connection.execute(
                "CREATE TABLE metadata(ticker TEXT PRIMARY KEY, exchange TEXT, industry TEXT, "
                "foreign_room_pct REAL, pe REAL, pb REAL, roe REAL, market_cap REAL, "
                "shares_outstanding REAL, free_float_est REAL, dividend_yield REAL, "
                "margin_status TEXT, updated TEXT)"
            )
            connection.execute(
                "INSERT INTO metadata VALUES('POW','HSX','Utilities',10.0,9.0,1.0,6.94,1,3067845688,1,0,NULL,'2026-07-09')"
            )
            connection.execute("CREATE TABLE ohlcv(ticker TEXT, date TEXT, open REAL, high REAL, low REAL, close REAL, volume REAL, source TEXT)")
            connection.execute("CREATE TABLE shareholders(ticker TEXT, shareholder_name TEXT, shares_owned REAL, pct REAL, source TEXT, updated_at TEXT)")
            connection.execute("CREATE TABLE shareholders_progress(ticker TEXT PRIMARY KEY, status TEXT, rows INTEGER, updated TEXT)")
            connection.commit()
            connection.close()
            metadata, _ = builder.load_metadata_slice("POW", db_path)
        roe_meta = builder.build_metric_meta(
            metadata["roe"], builder.MetricStatus.REPORTED, source="vnstock_metadata_snapshot",
            basis="trailing_ttm_external_provider", unit="percent", confidence=1.0,
        )
        self.assertEqual(metadata["roe"], 6.94)
        self.assertEqual(roe_meta["unit"], "percent")
        self.assertNotEqual(roe_meta.get("unit"), "ratio")


class ShareReconciliationTests(unittest.TestCase):
    """item D: shares_period_end (financial_snapshot) vs shares_current (metadata) — real
    HPG/PAN mismatches are material (>=10%), POW/SSI are not, from general threshold logic."""

    def _build_db(self, root: Path, shares_outstanding: float) -> Path:
        db_path = root / "vn_stock.db"
        connection = sqlite3.connect(db_path)
        connection.execute(
            "CREATE TABLE metadata(ticker TEXT PRIMARY KEY, shares_outstanding REAL, updated TEXT)"
        )
        connection.execute("INSERT INTO metadata VALUES('HPG', ?, '2026-07-09')", (shares_outstanding,))
        connection.commit()
        connection.close()
        return db_path

    def test_material_mismatch_uses_general_threshold_not_a_hardcoded_ticker(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,shares_period_end\nHPG,2026-Q1,quarter,7675465855\n",
                encoding="utf-8",
            )
            db_path = self._build_db(root, 8442964520.0)  # real HPG numbers: 10.00% mismatch
            with patch.object(builder, "VNSTOCK_ROOT", root):
                result, _ = builder.load_share_reconciliation_slice("HPG", db_path)
        self.assertEqual(result["status"], "material_warning")
        self.assertGreaterEqual(result["mismatch_pct"], 10.0)
        self.assertIsNotNone(result["possible_reason"])
        self.assertEqual(result["weighted_average_shares_basic_meta"]["status"], "proxy")
        self.assertEqual(result["weighted_average_shares_basic_meta"]["details"]["proxy_of"], "shares_period_end")

    def test_matching_shares_are_ok_no_false_positive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,shares_period_end\nHPG,2026-Q1,quarter,3067845688\n",
                encoding="utf-8",
            )
            db_path = self._build_db(root, 3067845688.0)  # identical -> 0% mismatch
            with patch.object(builder, "VNSTOCK_ROOT", root):
                result, _ = builder.load_share_reconciliation_slice("HPG", db_path)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["mismatch_pct"], 0.0)
        self.assertIsNone(result["possible_reason"])


if __name__ == "__main__":
    unittest.main()
