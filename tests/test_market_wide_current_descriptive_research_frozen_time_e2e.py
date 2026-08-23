"""Frozen-time Producer -> Consumer end-to-end proof for market_wide_current_descriptive_research.

Runs the actual stock-core-private Producer functions (never reimplemented or mocked) against
the actual retained artifact already on disk, then feeds the real output through this
repository's own Consumer contract -- offline, single-threaded, no DNSE/network reacquisition,
no runtime or production write. This never modifies stock-core-private: it only imports its
already-committed export_ai_bundle.py and market_wide_current_descriptive_research.py read-only,
and only reads the already-retained artifact JSON already on disk
(operations-review/market-wide-current-descriptive-research-v1-20260823/
market_wide_current_descriptive_research_artifact.json). No DNSE/network call happens anywhere in
this path -- attach_market_wide_current_descriptive_research() is a pure local-file loader gated
by a content-hash check -- and no production/runtime database is touched.

Skipped (not failed) when the sibling stock-core-private checkout or its retained artifact is
unavailable in this environment, so this stays a genuine environment-dependent E2E proof rather
than a hermetic unit test. See
test_market_wide_current_descriptive_research_contract_pass_through.py for hermetic coverage
using real values this exact test previously captured.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_CONSUMER_ROOT = Path(__file__).resolve().parents[1]
_PRODUCER_ROOT = _CONSUMER_ROOT.parent / "stock-core-private"
_ARTIFACT_PATH = (
    _PRODUCER_ROOT / "operations-review"
    / "market-wide-current-descriptive-research-v1-20260823"
    / "market_wide_current_descriptive_research_artifact.json"
)


@unittest.skipUnless(
    _PRODUCER_ROOT.is_dir() and _ARTIFACT_PATH.exists(),
    f"sibling Producer checkout or retained artifact not present at {_ARTIFACT_PATH}",
)
class FrozenTimeProducerConsumerEndToEndTests(unittest.TestCase):
    """Real Producer artifact -> real Producer attach layer -> real Consumer contract."""

    @classmethod
    def setUpClass(cls):
        if str(_PRODUCER_ROOT) not in sys.path:
            sys.path.insert(0, str(_PRODUCER_ROOT))
        import export_ai_bundle  # noqa: E402
        import market_wide_current_descriptive_research  # noqa: E402
        cls.producer_bundle = export_ai_bundle
        cls.producer_artifact_module = market_wide_current_descriptive_research

    def _real_bundle_entries(self, tickers):
        entries = {t: {"ticker": t} for t in tickers}
        self.producer_bundle.attach_market_wide_current_descriptive_research(
            entries, include=True, artifact_path=str(_ARTIFACT_PATH),
        )
        return entries

    def test_retained_artifact_self_verifies_before_anything_is_attached(self):
        artifact = self.producer_bundle.load_market_wide_current_descriptive_research_artifact(_ARTIFACT_PATH)
        self.assertIsNotNone(artifact, "the retained checkpoint failed its own content-hash verification")
        recomputed = self.producer_artifact_module.content_identity(artifact)
        self.assertEqual(recomputed["artifact_sha256"], artifact["artifact_sha256"])

    def test_disabled_producer_flag_means_consumer_never_sees_the_key(self):
        from builders import build_ticker_context as consumer
        entries = {"AAA": {"ticker": "AAA"}}
        self.producer_bundle.attach_market_wide_current_descriptive_research(
            entries, include=False, artifact_path=str(_ARTIFACT_PATH),
        )
        ctx = {"ticker": "AAA", "provenance": []}
        consumer.apply_bundle_market_wide_current_descriptive_research_contract(ctx, {"tickers": entries})
        self.assertNotIn("market_wide_current_descriptive_research", ctx)

    def test_end_to_end_byte_identical_for_every_activity_state_family(self):
        from builders import build_ticker_context as consumer
        entries = self._real_bundle_entries(("AAA", "SHB", "A32", "APP", "ZZZ_NOT_IN_RETAINED_UNIVERSE"))
        bundle = {"tickers": entries}
        seen_states = set()
        for ticker, entry in entries.items():
            ctx = {"ticker": ticker, "provenance": []}
            consumer.apply_bundle_market_wide_current_descriptive_research_contract(ctx, bundle)
            producer_side = entry.get("market_wide_current_descriptive_research")
            consumer_side = ctx.get("market_wide_current_descriptive_research")
            if producer_side is None:
                self.assertIsNone(consumer_side, f"{ticker}: consumer fabricated a key the real Producer never attached")
                continue
            self.assertEqual(producer_side, consumer_side, f"{ticker}: consumer output diverged from real Producer output")
            self.assertIs(False, consumer_side["is_actionable"])
            seen_states.add(consumer_side["activity_and_session_state"])
        # A genuine cross-section of the real retained universe, not a cherry-picked single case.
        self.assertIn("ACTIVE_LISTED_OBSERVED", seen_states)
        self.assertIn("ACTIVE_LISTED_NO_QUALIFIED_SESSION_OBSERVATION", seen_states)
        self.assertNotIn("market_wide_current_descriptive_research", entries["ZZZ_NOT_IN_RETAINED_UNIVERSE"])

    def test_real_shb_residual_survives_the_real_full_pipeline(self):
        from builders import build_ticker_context as consumer
        entries = self._real_bundle_entries(("SHB",))
        producer_side = entries["SHB"]["market_wide_current_descriptive_research"]
        self.assertEqual("ACTIVE_LISTED_OBSERVED", producer_side["activity_and_session_state"])
        self.assertNotEqual("EXACT_MATCH", producer_side["liquidity"]["g1_v_reconciliation"]["verdict"])
        ctx = {"ticker": "SHB", "provenance": []}
        consumer.apply_bundle_market_wide_current_descriptive_research_contract(ctx, {"tickers": entries})
        result = ctx["market_wide_current_descriptive_research"]
        self.assertEqual(producer_side["liquidity"]["g1_v_reconciliation"]["verdict"], result["liquidity"]["g1_v_reconciliation"]["verdict"])
        self.assertNotEqual("malformed", result["status"])

    def test_real_market_coverage_matches_the_retained_artifacts_own_summary(self):
        """denominator=1,510 and observed cohort=960 must reach the Consumer exactly as the
        Producer artifact itself reports them, for every ticker, not just eligible ones."""
        from builders import build_ticker_context as consumer
        entries = self._real_bundle_entries(("AAA", "A32"))
        artifact = self.producer_bundle.load_market_wide_current_descriptive_research_artifact(_ARTIFACT_PATH)
        expected_denominator = artifact["market_breadth"]["current_active_equity_denominator"]
        expected_observed = artifact["market_breadth"]["observed_session_cohort"]
        self.assertEqual(1510, expected_denominator)
        self.assertEqual(960, expected_observed)
        for ticker in ("AAA", "A32"):
            ctx = {"ticker": ticker, "provenance": []}
            consumer.apply_bundle_market_wide_current_descriptive_research_contract(ctx, {"tickers": entries})
            coverage = ctx["market_wide_current_descriptive_research"]["market_coverage"]
            self.assertEqual(expected_denominator, coverage["current_active_equity_denominator"])
            self.assertEqual(expected_observed, coverage["observed_session_cohort"])

    def test_real_stale_technical_feature_stays_stale_through_the_real_full_pipeline(self):
        """Finds a genuine ACTIVE_LISTED_NO_QUALIFIED_SESSION_OBSERVATION ticker whose technical
        features are SHADOW_ONLY but not same-session, and proves is_current_session=False
        survives the complete real Producer -> Consumer path unmodified."""
        from builders import build_ticker_context as consumer
        artifact = self.producer_bundle.load_market_wide_current_descriptive_research_artifact(_ARTIFACT_PATH)
        stale_ticker = next(
            t for t, r in artifact["records"].items()
            if r["activity_and_session_state"] == "ACTIVE_LISTED_NO_QUALIFIED_SESSION_OBSERVATION"
            and r["technical_features"].get("status") == "SHADOW_ONLY"
            and r["technical_features"].get("is_current_session") is False
        )
        entries = self._real_bundle_entries((stale_ticker,))
        producer_side = entries[stale_ticker]["market_wide_current_descriptive_research"]
        ctx = {"ticker": stale_ticker, "provenance": []}
        consumer.apply_bundle_market_wide_current_descriptive_research_contract(ctx, {"tickers": entries})
        result = ctx["market_wide_current_descriptive_research"]
        self.assertEqual(producer_side, result)
        self.assertFalse(result["technical_features"]["is_current_session"])
        self.assertNotEqual(result["session"], result["technical_features"]["feature_as_of_session"])


if __name__ == "__main__":
    unittest.main()
