"""Phase 9 downstream compatibility tests against snapshot schema v2."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builders import build_ticker_context as builder  # noqa: E402
from builders import context_coverage as coverage  # noqa: E402


class SnapshotConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        config = builder.load_json(builder.CONFIG_PATH)
        template = builder.load_json((builder.WORKSPACE_ROOT / config["context_template_path"]).resolve())
        cls.context = builder.build_context_package("PAN", template, builder.load_summary_layer(config))
        cls.validation_config = coverage.load_config(ROOT / "validation" / "context_validation_profiles.json")

    def test_consumer_reads_compatibility_fields(self):
        financial = self.context["financial_summary"]
        self.assertEqual(financial["snapshot_schema_version"], "2.0")
        self.assertEqual(financial["ebit"], 600_682_628_000)
        self.assertEqual(financial["operating_cash_flow"], -2_885_506_210_000)
        self.assertEqual(financial["operating_cash_flow_reported"], -2_885_506_210_000)

    def test_consumer_handles_metric_metadata(self):
        financial = self.context["financial_summary"]
        self.assertEqual(financial["ebit_meta"]["status"], "derived")
        self.assertEqual(financial["ebit_meta"]["source"], "derived_financial_statement")
        self.assertEqual(financial["ebit_meta"]["formula"], "profit_before_tax + interest_expense")
        self.assertEqual(financial["ebit_meta"]["inputs"], ["profit_before_tax", "interest_expense"])
        self.assertEqual(financial["ebitda_meta"]["status"], "insufficient_periods")

    def test_context_uses_rebuilt_snapshot(self):
        financial = self.context["financial_summary"]
        self.assertEqual(financial["latest_period"], "2026-Q1")
        self.assertEqual(financial["retained_earnings"], 2_618_950_443_317)
        self.assertEqual(financial["sga"], 353_782_849_000)

    def test_context_status_contracts_after_rebuild(self):
        news = self.context["news_summary"]
        shareholder = self.context["shareholder_summary"]
        self.assertEqual(news["status"], "no_company_specific_news")
        self.assertEqual(news["company_news_count"], 0)
        self.assertEqual(news["sector_news_count"], 0)
        self.assertEqual(news["market_news_count"], 100)
        self.assertEqual(shareholder["status"], "not_queried")
        self.assertIsNone(shareholder["major_shareholders_count"])

    def test_consumer_distinguishes_zero_null_and_status(self):
        self.assertEqual(builder._number("0"), 0.0)
        self.assertIsNone(builder._number(""))
        self.assertEqual(self.context["news_summary"]["meta"]["status"], "source_empty")

    def test_profiles_keep_purpose_specific_semantics(self):
        current = coverage.validate_profile(self.context, "current_snapshot", self.validation_config)
        backtest = coverage.validate_profile(self.context, "backtest", self.validation_config)
        self.assertTrue(current["profile_valid"])
        self.assertFalse(backtest["profile_valid"])
        self.assertIn("analysis_cutoff", {item.get("metric") for item in backtest["blocking_missing"]})

    def test_representative_tickers_read_schema_v2(self):
        for ticker in ("PAN", "HPG", "VCB", "SSI", "BVH"):
            financial, _ = builder.load_financial_slice(ticker)
            self.assertEqual(financial["snapshot_schema_version"], "2.0", ticker)
            self.assertTrue(financial["source_rows_found"], ticker)


if __name__ == "__main__":
    unittest.main()
