"""Frozen-time, market-wide Producer -> Consumer proof for packet shadow parity.

Runs the actual stock-core-private Producer attach_* functions (never reimplemented or
mocked) against the actual retained artifacts already on disk, feeds the real per-ticker
output through this repository's own apply_bundle_*_contract functions, and evaluates
market-wide packet-vs-legacy shadow parity over the real official research universe --
offline, single-threaded, no DNSE/network reacquisition, no runtime or production write.
Mirrors test_market_wide_current_descriptive_research_frozen_time_e2e.py's convention.

Skipped (not failed) when the sibling stock-core-private checkout or any of the retained
artifacts it depends on are unavailable in this environment.
"""

from __future__ import annotations

import unittest
from pathlib import Path

_CONSUMER_ROOT = Path(__file__).resolve().parents[1]
_PRODUCER_ROOT = _CONSUMER_ROOT.parent / "stock-core-private"
_PACKET_ARTIFACT_PATH = (
    _PRODUCER_ROOT / "operations-review" / "current-research-decision-packet-v1"
    / "current_research_decision_packet_artifact.json"
)

# A small, fast, cross-sectional cohort for everyday CI runs (real tickers spanning
# different sectors/entity types, not a cherry-picked single case). The full 1,507-ticker
# replay is exercised separately below, gated behind an explicit opt-in env var since it
# is not "bounded enough" to run by default on every invocation.
_SAMPLE_COHORT = ["HPG", "VNM", "VCB", "AAA", "SSI", "FPT", "QNS", "NVL"]


@unittest.skipUnless(
    _PRODUCER_ROOT.is_dir() and _PACKET_ARTIFACT_PATH.exists(),
    f"sibling Producer checkout or retained packet artifact not present at {_PACKET_ARTIFACT_PATH}",
)
class FrozenTimeMarketWidePacketShadowParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from builders.current_research_packet_shadow_parity import (
            build_market_wide_parity_report,
            load_market_wide_ticker_contexts_from_retained_artifacts,
            replay,
        )
        cls.build_market_wide_parity_report = staticmethod(build_market_wide_parity_report)
        cls.load_market_wide_ticker_contexts_from_retained_artifacts = staticmethod(
            load_market_wide_ticker_contexts_from_retained_artifacts
        )
        cls.replay = staticmethod(replay)

    def test_sample_cohort_replay_self_verifies_with_zero_residual(self):
        ticker_contexts = self.load_market_wide_ticker_contexts_from_retained_artifacts(
            _PRODUCER_ROOT, tickers=_SAMPLE_COHORT,
        )
        self.assertEqual(set(_SAMPLE_COHORT), set(ticker_contexts))
        artifact = self.build_market_wide_parity_report(ticker_contexts)
        self.replay(artifact)  # must not raise
        self.assertEqual(len(_SAMPLE_COHORT), artifact["denominator"])
        self.assertEqual(0, artifact["unexplained_residual_count"])
        self.assertEqual(0, artifact["totals"]["DUAL_CONFLICT_FAIL_CLOSED"])

    def test_sample_cohort_scenario_never_equated(self):
        """Real HPG/VNM/etc. data must reproduce the same structural guarantee the
        hermetic unit tests prove with synthetic fixtures."""
        ticker_contexts = self.load_market_wide_ticker_contexts_from_retained_artifacts(
            _PRODUCER_ROOT, tickers=_SAMPLE_COHORT,
        )
        artifact = self.build_market_wide_parity_report(ticker_contexts)
        scenario_breakdown = artifact["component_breakdown"]["scenario"]
        self.assertEqual(0, scenario_breakdown.get("DUAL_EQUIVALENT", 0))
        self.assertEqual(0, scenario_breakdown.get("DUAL_CONFLICT_FAIL_CLOSED", 0))

    def test_sample_cohort_content_identity_is_deterministic(self):
        ticker_contexts = self.load_market_wide_ticker_contexts_from_retained_artifacts(
            _PRODUCER_ROOT, tickers=_SAMPLE_COHORT,
        )
        first = self.build_market_wide_parity_report(ticker_contexts)
        second = self.build_market_wide_parity_report(
            self.load_market_wide_ticker_contexts_from_retained_artifacts(_PRODUCER_ROOT, tickers=_SAMPLE_COHORT)
        )
        self.assertEqual(first["artifact_sha256"], second["artifact_sha256"])

    @unittest.skipUnless(
        __import__("os").environ.get("RUN_FULL_MARKET_WIDE_PACKET_SHADOW_PARITY_REPLAY") == "1",
        "full 1,507-ticker replay is opt-in (set RUN_FULL_MARKET_WIDE_PACKET_SHADOW_PARITY_REPLAY=1); "
        "already exercised and retained via tools/run_current_research_packet_shadow_parity.py",
    )
    def test_full_retained_universe_replay_self_verifies_with_zero_residual(self):
        ticker_contexts = self.load_market_wide_ticker_contexts_from_retained_artifacts(_PRODUCER_ROOT)
        artifact = self.build_market_wide_parity_report(ticker_contexts)
        self.replay(artifact)
        self.assertEqual(1507, artifact["denominator"])
        self.assertEqual(0, artifact["unexplained_residual_count"])


if __name__ == "__main__":
    unittest.main()
