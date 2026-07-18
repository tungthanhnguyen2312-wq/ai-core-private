"""Phase 1 missing-data contract and backward-compatibility tests."""

from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


contract = load_module("phase1_missing_data_contract", ROOT / "builders" / "missing_data_contract.py")
builder = load_module("phase1_context_builder", ROOT / "builders" / "build_ticker_context.py")


class MissingDataContractTests(unittest.TestCase):
    def test_missing_value_is_not_converted_to_zero(self):
        meta = contract.build_metric_meta(
            None,
            contract.MetricStatus.MAPPING_MISSING,
            reason="item_mapping_not_found",
        )
        output = {}
        contract.set_metric_with_meta(output, "ebit", meta)
        self.assertIsNone(output["ebit"])
        self.assertIsNone(output["ebit_meta"]["value"])

    def test_source_empty_differs_from_mapping_missing(self):
        source = contract.build_metric_meta(None, "source_empty")
        mapping = contract.build_metric_meta(None, "mapping_missing")
        self.assertNotEqual(source["status"], mapping["status"])

    def test_not_applicable_is_excluded_from_coverage(self):
        metrics = {
            "reported": contract.build_metric_meta(10, "reported"),
            "missing": contract.build_metric_meta(None, "mapping_missing"),
            "bank_sga": contract.build_metric_meta(None, "not_applicable"),
        }
        coverage = contract.build_section_coverage(metrics)
        self.assertEqual(coverage["expected_metrics"], 2)
        self.assertEqual(coverage["available_metrics"], 1)
        self.assertEqual(coverage["coverage"], 0.5)
        self.assertEqual(coverage["not_applicable_metrics"], ["bank_sga"])

    def test_derived_requires_formula_and_inputs(self):
        with self.assertRaises(ValueError):
            contract.build_metric_meta(12, "derived")
        meta = contract.build_metric_meta(
            12,
            "derived",
            formula="profit_before_tax + interest_expense",
            inputs=["profit_before_tax", "interest_expense"],
        )
        self.assertEqual(meta["formula"], "profit_before_tax + interest_expense")

    def test_unit_period_calendar_end_annualization_are_absent_unless_supplied(self):
        # item A: new optional fields must not change existing call sites' output shape.
        meta = contract.build_metric_meta(10, "reported")
        self.assertNotIn("unit", meta)
        self.assertNotIn("period_calendar_end", meta)
        self.assertNotIn("annualization", meta)

    def test_unit_period_calendar_end_annualization_are_present_when_supplied(self):
        meta = contract.build_metric_meta(
            0.0175, "derived", formula="net_profit / average_equity", inputs=["net_profit", "equity"],
            unit="ratio", period_calendar_end="2026-03-31", annualization="none",
        )
        self.assertEqual(meta["unit"], "ratio")
        self.assertEqual(meta["period_calendar_end"], "2026-03-31")
        self.assertEqual(meta["annualization"], "none")

    def test_metadata_is_strict_json_serializable(self):
        meta = contract.build_metric_meta(None, "not_queried", details={"attempts": []})
        self.assertIn('"not_queried"', json.dumps(meta, allow_nan=False))


class BuilderContractIntegrationTests(unittest.TestCase):
    def test_latest_null_ocf_uses_latest_non_null_reported_value(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,operating_cash_flow\n"
                "PAN,2025-Q4,quarter,1,1,1,1,1,100\n"
                "PAN,2026-Q1,quarter,2,2,2,2,2,\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("PAN")
        self.assertEqual(summary["operating_cash_flow"], 100)
        self.assertEqual(summary["operating_cash_flow_meta"]["status"], "reported")
        self.assertEqual(summary["operating_cash_flow_meta"]["period"], "2025-Q4")
        self.assertEqual(summary["operating_cash_flow_meta"]["basis"], "period_basis_unknown")
        self.assertTrue(summary["operating_cash_flow_meta"]["details"]["selected_latest_non_null_reported"])

    def test_valid_ttm_has_priority_over_reported_ocf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,"
                "operating_cash_flow,operating_cash_flow_reported,operating_cash_flow_ttm,operating_cash_flow_basis\n"
                "PAN,2025-Q4,quarter,1,1,1,1,1,100,100,400,ttm\n"
                "PAN,2026-Q1,quarter,2,2,2,2,2,,,,\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("PAN")
        self.assertEqual(summary["operating_cash_flow"], 400)
        self.assertEqual(summary["operating_cash_flow_meta"]["status"], "derived")
        self.assertEqual(summary["operating_cash_flow_meta"]["basis"], "ttm")

    def test_split_ocf_fields_preserve_ytd_basis_and_source_period(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,"
                "operating_cash_flow,operating_cash_flow_reported,operating_cash_flow_ytd,"
                "operating_cash_flow_quarter,operating_cash_flow_ttm,operating_cash_flow_basis,"
                "operating_cash_flow_basis_confidence\n"
                "PAN,2025-Q4,quarter,1,1,1,1,1,-20,-20,-20,,,ytd,0.9\n"
                "PAN,2026-Q1,quarter,2,2,2,2,2,,,,,,,\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("PAN")
        self.assertEqual(summary["operating_cash_flow"], -20)
        self.assertEqual(summary["operating_cash_flow_reported"], -20)
        self.assertEqual(summary["operating_cash_flow_ytd"], -20)
        self.assertIsNone(summary["operating_cash_flow_quarter"])
        self.assertIsNone(summary["operating_cash_flow_ttm"])
        self.assertEqual(summary["operating_cash_flow_meta"]["period"], "2025-Q4")
        self.assertEqual(summary["operating_cash_flow_meta"]["basis"], "ytd")
        self.assertEqual(summary["operating_cash_flow_meta"]["confidence"], 0.9)

    def test_advanced_scalar_compatibility_and_specific_status(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "financial_snapshot.csv").write_text(
                "ticker,period,period_type,revenue,net_profit,total_assets,equity,total_liabilities,operating_cash_flow\n"
                "PAN,2026-Q1,quarter,2,2,2,2,2,\n",
                encoding="utf-8",
            )
            with patch.object(builder, "VNSTOCK_ROOT", root):
                summary, _ = builder.load_financial_slice("PAN")
        self.assertIsNone(summary["interest_expense"])
        self.assertEqual(summary["interest_expense_meta"]["status"], "mapping_missing")
        self.assertIsNone(summary["ebitda"])
        self.assertEqual(summary["ebitda_meta"]["status"], "insufficient_periods")

    def test_shareholder_not_queried_is_not_zero_or_source_empty(self):
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "fixture.db"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE shareholders(ticker TEXT, shareholder_name TEXT, shares_owned REAL, pct REAL, source TEXT, updated_at TEXT)")
            connection.execute("CREATE TABLE shareholders_progress(ticker TEXT PRIMARY KEY, status TEXT, rows INTEGER, updated TEXT)")
            connection.commit()
            connection.close()
            summary, _ = builder.load_shareholder_slice("PAN", db)
        self.assertIsNone(summary["major_shareholders_count"])
        self.assertEqual(summary["returned_top_holders_count"], 0)
        self.assertEqual(summary["meta"]["status"], "not_queried")

    def test_shareholder_source_empty_is_distinct(self):
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "fixture.db"
            connection = sqlite3.connect(db)
            connection.execute("CREATE TABLE shareholders(ticker TEXT, shareholder_name TEXT, shares_owned REAL, pct REAL, source TEXT, updated_at TEXT)")
            connection.execute("CREATE TABLE shareholders_progress(ticker TEXT PRIMARY KEY, status TEXT, rows INTEGER, updated TEXT)")
            connection.execute("INSERT INTO shareholders_progress VALUES('PAN','empty',0,'2026-07-13')")
            connection.commit()
            connection.close()
            summary, _ = builder.load_shareholder_slice("PAN", db)
        self.assertEqual(summary["meta"]["status"], "source_empty")
        self.assertIsNone(summary["major_shareholders_count"])

    def test_no_company_news_has_explicit_status_and_coverage(self):
        summary, _ = builder.load_news_slice("PAN")
        self.assertEqual(summary["status"], "no_company_specific_news")
        self.assertEqual(summary["meta"]["status"], "source_empty")
        self.assertEqual(summary["company_news_count"], 0)
        self.assertGreater(summary["market_news_count"], 0)
        self.assertEqual(summary["coverage"]["coverage"], 0.0)
        self.assertFalse(builder.section_is_available({"news_summary": summary}, "news_summary"))


if __name__ == "__main__":
    unittest.main()
