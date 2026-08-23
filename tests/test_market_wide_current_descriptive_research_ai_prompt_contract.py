"""Dedicated prompt-contract tests for the market_wide_current_descriptive_research lane.

Mirrors tests/test_multi_angle_ai_prompt_contract.py's pattern of asserting required substrings
directly against the shipped prompt file, so a future edit that silently drops the coverage-
disclosure or no-ranking guardrail text fails a test rather than only a manual review.
"""
from __future__ import annotations

import unittest
from pathlib import Path

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "ai_analysis_templates.md").read_text(encoding="utf-8")


class MarketWideCurrentDescriptiveResearchAiPromptContractTests(unittest.TestCase):
    def test_lane_is_explicit(self):
        self.assertIn("`market_wide_current_descriptive_research`", PROMPT)

    def test_coverage_disclosure_is_mandatory(self):
        self.assertIn("`market_coverage`", PROMPT)
        self.assertIn("`current_active_equity_denominator`", PROMPT)
        self.assertIn("`observed_session_cohort`", PROMPT)
        self.assertIn("never describe a statistic bounded by the smaller same-session count as if it covered the full denominator", PROMPT)

    def test_stale_vs_current_session_distinction_is_guarded(self):
        self.assertIn("`technical_features.is_current_session`", PROMPT)
        self.assertIn("`is_current_session=false`", PROMPT)
        self.assertIn("never as today's return, momentum, or trend", PROMPT)

    def test_sector_insufficient_coverage_is_guarded(self):
        self.assertIn('`sector_state.status = "UNAVAILABLE_INSUFFICIENT_COVERAGE"`', PROMPT)
        self.assertIn("never filled in, estimated, or treated as zero/neutral", PROMPT)

    def test_activity_states_are_distinct(self):
        for state in (
            "`ACTIVE_LISTED_OBSERVED`",
            "`ACTIVE_LISTED_NO_QUALIFIED_SESSION_OBSERVATION`",
            "`INACTIVE_OR_DELISTED`",
            "`UNSUPPORTED_OR_INVALID_PROVIDER_SYMBOL`",
        ):
            self.assertIn(state, PROMPT)
        self.assertIn("never collapsed into a simple \"active\" vs. \"inactive\" split", PROMPT)

    def test_blocked_outputs_referenced_and_binding(self):
        self.assertIn("`blocked_outputs`", PROMPT)
        self.assertIn("treat every listed key as binding regardless of how favorable the underlying descriptive numbers look", PROMPT)

    def test_liquidity_reuses_existing_liquidity_lane_semantics(self):
        self.assertIn('`liquidity.status="ELIGIBLE"`', PROMPT)

    def test_is_actionable_false_stated_for_this_lane(self):
        # Appears once for market_wide_current_liquidity_research and once more for this lane.
        self.assertGreaterEqual(PROMPT.count("`is_actionable=false` always."), 2)

    def test_prohibited_claims_extended_for_this_lane(self):
        self.assertIn("describing `market_wide_current_descriptive_research`'s same-session breadth/sector/technical-feature statistics as covering the full", PROMPT)
        self.assertIn("reporting a stale (`is_current_session=false`) technical-feature value as if it were the current session's return, momentum, or trend", PROMPT)
        self.assertIn("filling in, estimating, or treating as zero/neutral a sector whose `sector_state.status` is `UNAVAILABLE_INSUFFICIENT_COVERAGE`", PROMPT)
        self.assertIn("deriving a ranking, recommendation, probability, target price, portfolio weight, position size, or traded-value/turnover/ADV/ADTV figure from any `market_wide_current_descriptive_research` field", PROMPT)


if __name__ == "__main__":
    unittest.main()
