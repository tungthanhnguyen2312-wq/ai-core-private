"""Real retained Producer -> Consumer proof for nested current-screening consumption."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path


CONSUMER_ROOT = Path(__file__).resolve().parents[1]
PRODUCER_ROOT = CONSUMER_ROOT.parent / "stock-core-private"
DESCRIPTIVE = PRODUCER_ROOT / "operations-review/market-wide-current-technical-coverage-scaleout-v1-20260823/market_wide_current_descriptive_research_artifact.json"
SCREENING = PRODUCER_ROOT / "operations-review/current-market-screening-opportunity-comparison-foundation-v1-20260823/current_market_screening_opportunity_comparison_foundation_artifact.json"


@unittest.skipUnless(PRODUCER_ROOT.is_dir() and DESCRIPTIVE.exists() and SCREENING.exists(), "sibling retained artifacts unavailable")
class CurrentScreeningResearchFrozenTimeE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if str(PRODUCER_ROOT) not in sys.path:
            sys.path.insert(0, str(PRODUCER_ROOT))
        import export_ai_bundle  # noqa: E402
        from builders import build_ticker_context  # noqa: E402

        cls.producer = export_ai_bundle
        cls.consumer = build_ticker_context
        retained = cls.producer.load_current_market_screening_comparison_artifact(SCREENING)
        assert retained is not None
        cls.retained = retained

    def _entries(self, tickers, *, include_screening=True):
        entries = {ticker: {"ticker": ticker} for ticker in tickers}
        self.producer.attach_market_wide_current_descriptive_research(
            entries, include=True, artifact_path=str(DESCRIPTIVE),
            include_screening_comparison=include_screening,
            screening_comparison_artifact_path=str(SCREENING),
        )
        return entries

    def test_real_cross_section_is_byte_identical_and_coverage_aware(self):
        stale = next(ticker for ticker, record in self.retained["records"].items()
                     if record["market_relative_comparison"].get("reason") == "STALE_TECHNICAL_FEATURE_NOT_CURRENT_SESSION")
        sector_unavailable = next(ticker for ticker, record in self.retained["records"].items()
                                  if record["sector_relative_comparison"].get("reason") == "SECTOR_RELATIVE_COVERAGE_INSUFFICIENT")
        entries = self._entries(("AAA", "SHB", "A32", stale, sector_unavailable, "ZZZ_NOT_IN_RETAINED_UNIVERSE"))
        for ticker, entry in entries.items():
            context = {"ticker": ticker, "provenance": []}
            self.consumer.apply_bundle_market_wide_current_descriptive_research_contract(context, {"tickers": entries})
            producer_side = entry.get("market_wide_current_descriptive_research")
            consumer_side = context.get("market_wide_current_descriptive_research")
            if producer_side is None:
                self.assertIsNone(consumer_side)
                continue
            self.assertEqual(producer_side, consumer_side)
            screening = consumer_side["screening_comparison"]
            self.assertEqual(1510, screening["coverage_disclosure"]["denominator"])
            self.assertEqual(960, screening["coverage_disclosure"]["observed_session_cohort"])
            self.assertFalse(screening["is_actionable"])
        shb = entries["SHB"]["market_wide_current_descriptive_research"]["screening_comparison"]["ticker_context"]
        self.assertEqual("OTHER", shb["liquidity_context"]["g1_v_reconciliation_verdict"])
        self.assertFalse(shb["liquidity_context"]["g1_v_reconciliation_warning"]["exact_match"])
        self.assertEqual("UNAVAILABLE", entries[sector_unavailable]["market_wide_current_descriptive_research"]
                         ["screening_comparison"]["ticker_context"]["sector_relative_comparison"]["status"])
        self.assertEqual("STALE_TECHNICAL_FEATURE_NOT_CURRENT_SESSION", entries[stale]["market_wide_current_descriptive_research"]
                         ["screening_comparison"]["ticker_context"]["market_relative_comparison"]["reason"])

    def test_disabled_or_malformed_nested_extension_never_reaches_consumer(self):
        entries = self._entries(("AAA",), include_screening=False)
        self.assertNotIn("screening_comparison", entries["AAA"]["market_wide_current_descriptive_research"])

        entries = self._entries(("AAA",))
        malformed = copy.deepcopy(entries["AAA"])
        del malformed["market_wide_current_descriptive_research"]["screening_comparison"]["ticker_context"]["screen_membership"]
        context = {"ticker": "AAA", "provenance": []}
        self.consumer.apply_bundle_market_wide_current_descriptive_research_contract(context, {"tickers": {"AAA": malformed}})
        self.assertEqual("malformed", context["market_wide_current_descriptive_research"]["status"])


if __name__ == "__main__":
    unittest.main()
