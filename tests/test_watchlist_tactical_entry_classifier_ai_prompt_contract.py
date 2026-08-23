"""Dedicated prompt-contract tests for the watchlist_tactical_entry_classifier lane.

Mirrors tests/test_market_wide_current_descriptive_research_ai_prompt_contract.py's pattern of
asserting required substrings directly against the shipped prompt file, so a future edit that
silently drops a guardrail fails a test rather than only a manual review.
"""
from __future__ import annotations

import unittest
from pathlib import Path

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "ai_analysis_templates.md").read_text(encoding="utf-8")


class WatchlistTacticalEntryClassifierAiPromptContractTests(unittest.TestCase):
    def test_lane_is_explicit(self):
        self.assertIn("`watchlist_tactical_entry_classifier`", PROMPT)

    def test_not_an_execution_instruction(self):
        self.assertIn("never an execution instruction, order, or automated trade signal", PROMPT)
        self.assertIn("`requires_human_review=true`", PROMPT)

    def test_all_nine_entry_states_named(self):
        for state in (
            "`DOWNTREND`", "`SELLING_PRESSURE_EASING`", "`EARLY_REVERSAL_CANDIDATE`", "`BASE_BUILDING`",
            "`SIDEWAYS_NEUTRAL`", "`BREAKOUT_READY`", "`UPTREND_CONFIRMED`", "`DISTRIBUTION_RISK`", "`BREAKDOWN_RISK`",
        ):
            with self.subTest(state=state):
                self.assertIn(state, PROMPT)

    def test_all_seven_actions_named(self):
        for action in (
            "`EARLY_ENTRY`", "`BUY_ON_CONFIRMATION`", "`ACCUMULATE_IN_BASE`", "`HOLD_DO_NOT_ADD`",
            "`WAIT`", "`AVOID`", "`REDUCE_EXIT`",
        ):
            with self.subTest(action=action):
                self.assertIn(action, PROMPT)

    def test_no_confirmed_bottom_or_top_language(self):
        self.assertIn("never describe either as a confirmed bottom, a confirmed reversal, or a confirmed uptrend", PROMPT)

    def test_early_entry_and_accumulate_never_full_position(self):
        self.assertIn('never carry `is_full_position_ready=true` under any circumstance', PROMPT)
        self.assertIn("do not describe either action as appropriate for a full-size position", PROMPT)

    def test_full_position_ready_is_unconditional_not_gate_conditions(self):
        """2026-08-23 closeout correction: position sizing is not implemented, so
        is_full_position_ready is unconditionally false/NOT_EVALUATED for every ticker -- there is
        no longer a conditional gate (liquidity/fundamental/market-backdrop) under which it can
        ever become true, for BREAKOUT_READY or any other entry_state."""
        self.assertIn('`is_full_position_ready` is unconditionally `false`', PROMPT)
        self.assertIn('`position_sizing_status` is unconditionally `"NOT_EVALUATED"`', PROMPT)
        self.assertIn("neither does any other state", PROMPT)

    def test_entry_action_is_primary_and_excludes_hold_and_reduce(self):
        self.assertIn("`entry_action`", PROMPT)
        self.assertIn("is the PRIMARY field for whether to enter", PROMPT)
        self.assertIn("never returns `HOLD_DO_NOT_ADD` or `REDUCE_EXIT`", PROMPT)
        self.assertIn("SECONDARY, position-management-conditional", PROMPT)
        self.assertIn("never use `action` to answer whether to enter a ticker whose holdings are unknown or zero", PROMPT)

    def test_missing_fundamental_narrows_not_forces_wait(self):
        self.assertIn("`NOT_IN_FUNDAMENTAL_COHORT`", PROMPT)
        self.assertIn("never by themselves force a `WAIT` action when the tactical evidence is otherwise sufficient", PROMPT)

    def test_market_state_is_context_not_a_gate(self):
        self.assertIn("never a market forecast or timing call, and never a gate the model may use to override a ticker's own `entry_state`", PROMPT)

    def test_is_actionable_false_stated_for_this_lane(self):
        self.assertIn("`is_actionable=false` and `requires_human_review=true` always", PROMPT)

    def test_prohibited_claims_extended_for_this_lane(self):
        self.assertIn("describing a `watchlist_tactical_entry_classifier` `entry_state` of `EARLY_REVERSAL_CANDIDATE` or `BASE_BUILDING` as a confirmed bottom", PROMPT)
        self.assertIn('treating `action="EARLY_ENTRY"` or `action="ACCUMULATE_IN_BASE"` as appropriate for a full-size position', PROMPT)
        self.assertIn("fabricating a probability of success, a target price, an expected return, or a position-size/share-count figure", PROMPT)
        self.assertIn("treating `watchlist_tactical_entry_classifier.market_state` as a market forecast or timing call", PROMPT)
        self.assertIn("treating `watchlist_tactical_entry_classifier`'s output as an automated trade signal, order, or execution instruction", PROMPT)

    def test_prohibited_claims_cover_action_entry_action_conflation_and_sizing(self):
        """2026-08-23 closeout correction: two new prohibited-claims items guard the entry/
        position-management split and the unconditional non-readiness of full-position sizing."""
        self.assertIn("treating `action`'s `HOLD_DO_NOT_ADD` or `REDUCE_EXIT` value as an answer to whether to enter a ticker when it is not known whether the user currently holds it", PROMPT)
        self.assertIn("claiming or implying `is_full_position_ready=true`, or any other full or complete position-sizing readiness, for any ticker", PROMPT)


if __name__ == "__main__":
    unittest.main()
