"""Phase 7 metric coverage, validation profile, and CLI tests."""

from __future__ import annotations

import copy
import json
import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builders import build_ticker_context as builder  # noqa: E402
from builders import context_coverage as coverage  # noqa: E402


CONFIG_PATH = ROOT / "validation" / "context_validation_profiles.json"
SCHEMA_PATH = ROOT / "validation" / "schemas" / "ticker_context.schema.json"


def meta(value, status="reported", reason=None):
    return {
        "value": value,
        "status": status,
        "reason": reason,
        "source": "fixture",
        "period": "2026-Q1",
        "basis": "fixture",
        "raw_item_id": None,
        "raw_label": None,
        "confidence": 1.0 if value is not None else 0.0,
    }


def context_fixture():
    financial = {
        "revenue": 100,
        "net_profit": 10,
        "total_assets": 500,
        "equity": 200,
        "total_liabilities": 300,
        "source_rows_found": True,
    }
    for metric in ("ebit", "ebitda", "interest_expense", "retained_earnings", "depreciation", "sga", "operating_cash_flow"):
        financial[metric] = 10
        financial[f"{metric}_meta"] = meta(10)
    return {
        "schema_version": "1.4.0",
        "ticker": "TEST",
        "generated_at": "2026-07-13T00:00:00+07:00",
        "analysis_cutoff": None,
        "mode": "test_context_package",
        "data_sources": ["fixture"],
        "latest_available_dates": {},
        "identity": {"ticker": "TEST"},
        "metadata": {"exchange": "HSX", "industry": "Food", "market_cap": 1000, "shares_outstanding": 100, "free_float_est": 0.5},
        "price_summary": {"last_date": "2026-07-13", "latest_close": 10, "trading_days": 300, "avg_volume_20d": 1000, "return_1m_pct": 2},
        "financial_summary": financial,
        "valuation_inputs": {},
        "technical_summary": {"rsi14": 50, "macd_hist": 1, "above_sma50": True, "above_sma200": True, "structure": "up", "rs_rating": 70},
        "news_summary": {"company_news_count": 1, "meta": meta(1)},
        "shareholder_summary": {"major_shareholders_count": 2, "meta": meta(2)},
        "risks": [],
        "data_quality": {"validation_status": "pending", "missing_sections": [], "warnings": [], "not_fully_confirmed": []},
        "provenance": [{"source": "fixture"}],
    }


class ContextCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = coverage.load_config(CONFIG_PATH)

    def validate(self, context, profile):
        return coverage.validate_profile(context, profile, self.config, schema_path=SCHEMA_PATH)

    def test_context_schema_valid_but_coverage_failed(self):
        context = context_fixture()
        context["financial_summary"]["operating_cash_flow"] = None
        context["financial_summary"]["operating_cash_flow_meta"] = meta(None, "mapping_missing", "ocf_missing")
        report = self.validate(context, "valuation")
        self.assertTrue(report["schema_valid"])
        self.assertFalse(report["profile_valid"])
        self.assertFalse(report["minimum_coverage_passed"])

    def test_current_snapshot_profile(self):
        report = self.validate(context_fixture(), "current_snapshot")
        self.assertTrue(report["profile_valid"])
        self.assertGreaterEqual(report["overall_coverage"], 0.8)

    def test_valuation_profile_requires_ocf(self):
        context = context_fixture()
        context["financial_summary"]["operating_cash_flow"] = None
        context["financial_summary"]["operating_cash_flow_meta"] = meta(None, "source_empty", "ocf_missing")
        report = self.validate(context, "valuation")
        self.assertTrue(any(item["section"] == "cash_flow" and item["metric"] == "operating_cash_flow" for item in report["blocking_missing"]))

    def test_technical_profile_does_not_require_ebitda(self):
        context = context_fixture()
        context["financial_summary"]["ebitda"] = None
        context["financial_summary"]["ebitda_meta"] = meta(None, "insufficient_periods", "ebitda_missing")
        report = self.validate(context, "technical_analysis")
        self.assertTrue(report["profile_valid"])
        self.assertFalse(any(item.get("metric") == "ebitda" for item in report["blocking_missing"]))

    def test_forensic_profile_requires_quality_metrics(self):
        context = context_fixture()
        for metric in ("retained_earnings", "interest_expense"):
            context["financial_summary"][metric] = None
            context["financial_summary"][f"{metric}_meta"] = meta(None, "mapping_missing", f"{metric}_missing")
        report = self.validate(context, "forensic")
        blocked = {item.get("metric") for item in report["blocking_missing"]}
        self.assertIn("retained_earnings", blocked)
        self.assertIn("interest_expense", blocked)

    def test_not_applicable_not_counted_as_missing(self):
        metrics = [
            {"metric": "revenue", "status": "reported"},
            {"metric": "sga", "status": "not_applicable"},
        ]
        result = coverage.calculate_section_coverage(metrics, self.config["profiles"]["forensic"])
        self.assertEqual(result["expected_metrics"], 1)
        self.assertEqual(result["missing_metrics"], [])
        self.assertEqual(result["coverage"], 1.0)

    def test_proxy_handling_depends_on_profile(self):
        metrics = [{"metric": "free_float_est", "status": "proxy"}]
        allowed = coverage.calculate_section_coverage(metrics, self.config["profiles"]["current_snapshot"])
        blocked = coverage.calculate_section_coverage(metrics, self.config["profiles"]["valuation"])
        self.assertEqual(allowed["coverage"], 0.5)
        self.assertEqual(blocked["coverage"], 0.0)

    def test_stale_handling_depends_on_profile(self):
        metrics = [{"metric": "snapshot", "status": "stale"}]
        allowed = coverage.calculate_section_coverage(metrics, self.config["profiles"]["current_snapshot"])
        blocked = coverage.calculate_section_coverage(metrics, self.config["profiles"]["technical_analysis"])
        self.assertEqual(allowed["coverage"], 0.5)
        self.assertEqual(blocked["coverage"], 0.0)

    def test_blocking_and_non_blocking_are_separated(self):
        context = context_fixture()
        context["price_summary"]["latest_close"] = None
        context["news_summary"] = {"company_news_count": 0, "meta": meta(None, "source_empty", "no_company_news")}
        report = self.validate(context, "current_snapshot")
        self.assertTrue(any(item.get("metric") == "latest_close" for item in report["blocking_missing"]))
        self.assertTrue(any(item.get("section") == "news" for item in report["non_blocking_missing"]))

    def test_section_coverage_denominator(self):
        metrics = [
            {"metric": "a", "status": "reported"},
            {"metric": "a", "status": "source_empty"},
            {"metric": "b", "status": "source_empty"},
            {"metric": "c", "status": "not_applicable"},
        ]
        result = coverage.calculate_section_coverage(metrics, self.config["profiles"]["current_snapshot"])
        self.assertEqual(result["expected_metrics"], 2)
        self.assertEqual(result["available_metrics"], 1)
        self.assertEqual(result["coverage"], 0.5)

    def test_empty_not_applicable_section_avoids_divide_by_zero(self):
        result = coverage.calculate_section_coverage(
            [{"metric": "sga", "status": "not_applicable"}],
            self.config["profiles"]["forensic"],
        )
        self.assertEqual(result["expected_metrics"], 0)
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["status"], "not_applicable")

    def test_cli_exit_zero_when_profile_passes(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "builders" / "build_ticker_context.py"), "PAN", "--validate-profile", "current_snapshot", "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertTrue(json.loads(run.stdout)["results"][0]["validation"]["profile_valid"])

    def test_cli_exit_nonzero_on_blocking_missing(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "builders" / "build_ticker_context.py"), "PAN", "--validate-profile", "valuation", "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(run.returncode, 3, run.stderr)
        self.assertFalse(json.loads(run.stdout)["results"][0]["validation"]["profile_valid"])

    def test_pan_coverage_report_is_deterministic(self):
        builder_config = builder.load_json(builder.CONFIG_PATH)
        template = builder.load_json((builder.WORKSPACE_ROOT / builder_config["context_template_path"]).resolve())
        summaries = builder.load_summary_layer(builder_config)
        first_context = builder.build_context_package("PAN", template, summaries)
        second_context = builder.build_context_package("PAN", template, summaries)
        first = self.validate(first_context, "valuation")
        second = self.validate(second_context, "valuation")
        self.assertEqual(first, second)
        self.assertEqual(coverage.render_markdown(first), coverage.render_markdown(second))

    def test_backtest_profile_blocks_point_in_time_ambiguity(self):
        report = self.validate(context_fixture(), "backtest")
        blocked = {item.get("metric") for item in report["blocking_missing"]}
        self.assertIn("analysis_cutoff", blocked)
        self.assertIn("financial_publication_date", blocked)
        self.assertIn("price_adjustment", blocked)

    def test_unknown_profile_has_dedicated_exit_code(self):
        run = subprocess.run(
            [sys.executable, str(ROOT / "builders" / "build_ticker_context.py"), "PAN", "--validate-profile", "does_not_exist", "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(run.returncode, 4)
        self.assertIn("PROFILE CONFIG ERROR", run.stderr)

    def test_universe_aggregation_has_required_columns(self):
        first = self.validate(context_fixture(), "current_snapshot")
        second_context = context_fixture()
        second_context["financial_summary"]["ebit"] = None
        second_context["financial_summary"]["ebit_meta"] = meta(None, "source_empty", "missing")
        rows = coverage.aggregate_universe([first, self.validate(second_context, "current_snapshot")])
        ebit = next(row for row in rows if row["metric"] == "financial_advanced.ebit")
        self.assertEqual(ebit["available"], 1)
        self.assertEqual(ebit["missing"], 1)
        self.assertEqual(ebit["coverage_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
