"""Frozen-time Producer -> Consumer end-to-end proof for watchlist_tactical_entry_classifier.

Runs the actual stock-core-private Producer functions (never reimplemented or mocked) against the
actual retained artifact already on disk, then feeds the real output through this repository's own
Consumer contract -- offline, single-threaded, no DNSE/network reacquisition, no runtime or
production write. Mirrors test_market_wide_current_descriptive_research_frozen_time_e2e.py's
convention exactly. This never modifies stock-core-private: it only imports its already-committed
export_ai_bundle.py and watchlist_tactical_entry_classifier.py read-only, and only reads the
already-retained artifact JSON already on disk
(operations-review/watchlist-tactical-entry-decision-v1-20260823/
watchlist_tactical_entry_classifier_artifact.json). No DNSE/network call happens anywhere in this
path -- attach_watchlist_tactical_entry_classifier() is a pure local-file loader gated by a
content-hash check -- and no production/runtime database is touched.

Skipped (not failed) when the sibling stock-core-private checkout or its retained artifact is
unavailable in this environment.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

_CONSUMER_ROOT = Path(__file__).resolve().parents[1]
_PRODUCER_ROOT = _CONSUMER_ROOT.parent / "stock-core-private"
_ARTIFACT_PATH = (
    _PRODUCER_ROOT / "operations-review"
    / "watchlist-tactical-entry-decision-v1-20260823"
    / "watchlist_tactical_entry_classifier_artifact.json"
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
        import watchlist_tactical_entry_classifier  # noqa: E402
        cls.producer_bundle = export_ai_bundle
        cls.producer_artifact_module = watchlist_tactical_entry_classifier

    def _real_bundle_entries(self, tickers):
        entries = {t: {"ticker": t} for t in tickers}
        self.producer_bundle.attach_watchlist_tactical_entry_classifier(
            entries, include=True, artifact_path=str(_ARTIFACT_PATH),
        )
        return entries

    def test_retained_artifact_self_verifies_before_anything_is_attached(self):
        artifact = self.producer_bundle.load_watchlist_tactical_entry_classifier_artifact(_ARTIFACT_PATH)
        self.assertIsNotNone(artifact, "the retained checkpoint failed its own content-hash verification")
        recomputed = self.producer_artifact_module.content_identity(artifact)
        self.assertEqual(recomputed["artifact_sha256"], artifact["artifact_sha256"])

    def test_disabled_producer_flag_means_consumer_never_sees_the_key(self):
        from builders import build_ticker_context as consumer
        entries = {"HPG": {"ticker": "HPG"}}
        self.producer_bundle.attach_watchlist_tactical_entry_classifier(
            entries, include=False, artifact_path=str(_ARTIFACT_PATH),
        )
        ctx = {"ticker": "HPG", "provenance": []}
        consumer.apply_bundle_watchlist_tactical_entry_classifier_contract(ctx, {"tickers": entries})
        self.assertNotIn("watchlist_tactical_entry_classifier", ctx)

    def test_end_to_end_byte_identical_for_the_real_11_ticker_production_cohort(self):
        from builders import build_ticker_context as consumer
        cohort = ["POW", "SSI", "HPG", "EVF", "PAN", "PNJ", "FPT", "QNS", "VNM", "PVD", "NVL"]
        entries = self._real_bundle_entries(cohort)
        bundle = {"tickers": entries}
        seen_entry_states = set()
        for ticker in cohort:
            entry = entries[ticker]
            ctx = {"ticker": ticker, "provenance": []}
            consumer.apply_bundle_watchlist_tactical_entry_classifier_contract(ctx, bundle)
            producer_side = entry.get("watchlist_tactical_entry_classifier")
            consumer_side = ctx.get("watchlist_tactical_entry_classifier")
            self.assertIsNotNone(producer_side, f"{ticker}: real Producer artifact unexpectedly missing this ticker")
            self.assertEqual(producer_side, consumer_side, f"{ticker}: consumer output diverged from real Producer output")
            self.assertIs(False, consumer_side["is_actionable"])
            self.assertNotEqual("malformed", consumer_side["status"])
            if consumer_side["entry_state"]:
                seen_entry_states.add(consumer_side["entry_state"])
        # A genuine cross-section of real classifications, not a single cherry-picked case.
        self.assertGreaterEqual(len(seen_entry_states), 2)

    def test_real_vnm_uptrend_confirmed_survives_the_real_full_pipeline(self):
        """VNM is a real, independently-known strong-momentum name in this cohort (see
        docs/DECISIONS.md's 2026-08-23 entries); its classification must reach the Consumer
        unmodified."""
        from builders import build_ticker_context as consumer
        entries = self._real_bundle_entries(("VNM",))
        producer_side = entries["VNM"]["watchlist_tactical_entry_classifier"]
        ctx = {"ticker": "VNM", "provenance": []}
        consumer.apply_bundle_watchlist_tactical_entry_classifier_contract(ctx, {"tickers": entries})
        result = ctx["watchlist_tactical_entry_classifier"]
        self.assertEqual(producer_side, result)
        self.assertEqual(result["entry_state"], "UPTREND_CONFIRMED")
        self.assertEqual(result["action"], "HOLD_DO_NOT_ADD")

    def test_real_taxonomy_tables_travel_with_every_ticker(self):
        from builders import build_ticker_context as consumer
        entries = self._real_bundle_entries(("HPG",))
        ctx = {"ticker": "HPG", "provenance": []}
        consumer.apply_bundle_watchlist_tactical_entry_classifier_contract(ctx, {"tickers": entries})
        result = ctx["watchlist_tactical_entry_classifier"]
        self.assertEqual(len(result["state_taxonomy"]), 9)
        self.assertEqual(len(result["action_taxonomy"]), 7)
        self.assertEqual(set(result["action_by_entry_state"]), set(result["state_taxonomy"]))

    def test_real_full_position_ready_is_never_true_for_early_entry_or_accumulate(self):
        """Real-data proof (not just synthetic) that the structural gate holds across the entire
        real retained 1,683-candidate universe, not merely the 11-ticker production cohort."""
        artifact = self.producer_bundle.load_watchlist_tactical_entry_classifier_artifact(_ARTIFACT_PATH)
        offending = [
            ticker for ticker, record in artifact["records"].items()
            if record["action"] in ("EARLY_ENTRY", "ACCUMULATE_IN_BASE") and record["is_full_position_ready"] is True
        ]
        self.assertEqual(offending, [])

    def test_real_no_fabricated_target_price_or_probability_value_in_any_record(self):
        artifact = self.producer_bundle.load_watchlist_tactical_entry_classifier_artifact(_ARTIFACT_PATH)
        forbidden_keys = {"target_price", "probability", "expected_return_pct", "win_rate",
                          "position_size_pct", "shares_to_buy", "portfolio_weight"}
        for ticker, record in artifact["records"].items():
            with self.subTest(ticker=ticker):
                self.assertTrue(forbidden_keys.isdisjoint(record.keys()))


if __name__ == "__main__":
    unittest.main()
