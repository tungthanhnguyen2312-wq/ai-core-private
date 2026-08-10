"""Focused unit tests for the Consumer multi-angle synthesis acceptance boundary.

Tests context shape validation, deterministic metadata derivation, boundary pass-through,
and fail-closed rejection handling.
"""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.multi_angle_synthesis_boundary import accept_multi_angle_synthesis

# TEST_FIXTURE_ONLY -- synthetic fixture for boundary tests.
# Does NOT import retained production data.
# Shape matches the real canonical contract (verified against a real fresh Consumer
# context and stock-core-private/dnse_current_state_price_analytics.py's own source):
# SMA20 lives at current_state_price_analytics.technical_indicators.sma_20.status, not
# at a top-level current_state_price_analytics.sma_20.
_VALID_CANONICAL_CONTEXT_FIXTURE = {
    "ticker": "TEST_TICKER",
    "historical_only": False,
    "current_state_price_analytics": {
        "status": "available",
        "technical_indicators": {
            "status": "available",
            "sma_20": {
                "status": "unavailable",
                "reason": "insufficient_session_history",
            },
        },
    },
    "current_state_market_risk": {
        "status": "available",
        "beta": 0.809,
    },
}

_VALID_AI_RESPONSE_FIXTURE = {
    "ticker": "TEST_TICKER",
    "facts": [
        "FY2024 operating cash flow was positive.",
        "Bounded 18-session cumulative return was -0.022.",
    ],
    "data_warnings": [
        "SMA20 is unavailable.",
        "is_actionable = false; evidence does not justify a BUY recommendation.",
    ],
    "supported_inferences": [
        "Stock exhibited lower sensitivity to the benchmark over the 18-session observation window.",
    ],
    "conflicting_evidence": [
        "Constructive fundamental facts and negative bounded-window price return point in different directions.",
    ],
    "hypotheses": [
        "Short-term price drawdown may reflect broader sector consolidation.",
    ],
    "missing_evidence": [
        "Sufficient session history for 20-session SMA.",
    ],
    "invalidation_conditions": [
        "Deterioration in upcoming quarterly operating cash flows.",
    ],
}


class MultiAngleSynthesisBoundaryTests(unittest.TestCase):
    # --- VALID BOUNDARY CASES ---
    def test_valid_context_with_sma20_unavailable_accepted(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertEqual(["sma_20"], result["derived_contract_metadata"].get("unavailable_indicators"))
        self.assertEqual(resp, result["accepted_output"])

    def test_valid_seven_category_response_accepted(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, json.dumps(resp))
        self.assertEqual("accepted", result["status"])
        self.assertEqual(resp, result["accepted_output"])

    def test_current_state_price_analytics_absent_accepted(self):
        ctx = {"ticker": "TEST_TICKER"}
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("unavailable_indicators", result["derived_contract_metadata"])

    def test_valid_negated_recommendation_disclaimer_accepted_through_boundary(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["data_warnings"].append("This evidence does not justify a BUY recommendation.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_repeated_boundary_call_deterministic(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        res1 = accept_multi_angle_synthesis(ctx, resp)
        res2 = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual(res1, res2)

    def test_valid_conflict_required_response_accepted(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=True)
        self.assertEqual("accepted", result["status"])
        self.assertTrue(result["derived_contract_metadata"].get("requires_conflicting_evidence"))

    # --- FAIL-CLOSED BOUNDARY CASES ---
    def test_sma20_unavailable_response_invents_value_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["facts"].append("SMA20 = 28.5")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("fabricated_unavailable_sma20_indicator", result["reasons"])

    def test_sma20_unavailable_response_says_price_above_sma20_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["facts"].append("Price is above SMA20.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("fabricated_unavailable_sma20_indicator", result["reasons"])

    def test_malformed_ticker_context_rejected(self):
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis("invalid_string_context", resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_context_invalid_type", result["reasons"])

    def test_malformed_sma20_metadata_source_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["current_state_price_analytics"]["technical_indicators"]["sma_20"] = "invalid_string_sma20"
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_context_malformed:sma_20", result["reasons"])

    def test_malformed_sma20_status_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["current_state_price_analytics"]["technical_indicators"]["sma_20"]["status"] = 123
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_context_malformed:sma_20_status", result["reasons"])

    def test_malformed_technical_indicators_structure_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["current_state_price_analytics"]["technical_indicators"] = "invalid_string_technical_indicators"
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_context_malformed:technical_indicators", result["reasons"])

    def test_canonical_nested_sma20_available_not_marked_unavailable(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["current_state_price_analytics"]["technical_indicators"]["sma_20"] = {
            "status": "available", "value": 25.4, "as_of_session": "2026-08-07",
        }
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["data_warnings"] = [w for w in resp["data_warnings"] if "SMA20 is unavailable" not in w]
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("unavailable_indicators", result["derived_contract_metadata"])

    def test_legacy_top_level_sma20_shape_is_not_read(self):
        """Regression guard: a pre-existing, never-real top-level
        current_state_price_analytics.sma_20 must not be read by the boundary --
        only the canonical current_state_price_analytics.technical_indicators.sma_20
        path is authoritative. Proves the fix uses the real shape, not the old
        test-only shape."""
        ctx = {
            "ticker": "TEST_TICKER",
            "current_state_price_analytics": {
                "status": "available",
                "sma_20": {"status": "unavailable", "reason": "legacy_shape_should_be_ignored"},
            },
        }
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("unavailable_indicators", result["derived_contract_metadata"])

    def test_metadata_derivation_deterministic_across_repeated_calls(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        res1 = accept_multi_angle_synthesis(ctx, resp)
        res2 = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual(
            res1["derived_contract_metadata"], res2["derived_contract_metadata"],
        )
        self.assertEqual(["sma_20"], res1["derived_contract_metadata"].get("unavailable_indicators"))

    def test_affirmative_buy_sell_hold_output_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["supported_inferences"].append("We recommend BUY.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_target_price_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["supported_inferences"].append("Target price of 35000 VND.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_position_sizing_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["supported_inferences"].append("Recommended position size: 5% of portfolio.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_pit_backtest_proof_claim_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["supported_inferences"].append("These metrics provide backtest proof.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_pit_backtest_proof_claim", result["reasons"])

    def test_correlation_causality_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["supported_inferences"].append("Correlation proves causation between index and stock.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_correlation_causality_claim", result["reasons"])

    def test_unauthorized_foreign_room_volume_claim_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["facts"].append("Foreign room is = 49%.")
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_foreign_flow_overclaim", result["reasons"])

    def test_conflict_required_case_with_empty_conflicting_evidence_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["conflicting_evidence"] = []
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=True)
        self.assertEqual("rejected", result["status"])
        self.assertIn("conflicting_evidence_required_but_empty", result["reasons"])

    # --- MONOTONIC CONFLICT PRECEDENCE & TYPE SAFETY TESTS ---

    def test_context_true_caller_false_cannot_weaken_conflict_requirement(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["requires_conflicting_evidence"] = True
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["conflicting_evidence"] = []
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=False)
        self.assertEqual("rejected", result["status"])
        self.assertTrue(result["derived_contract_metadata"].get("requires_conflicting_evidence"))
        self.assertIn("conflicting_evidence_required_but_empty", result["reasons"])

    def test_context_true_caller_none_requires_conflict(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["requires_conflicting_evidence"] = True
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["conflicting_evidence"] = []
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=None)
        self.assertEqual("rejected", result["status"])
        self.assertTrue(result["derived_contract_metadata"].get("requires_conflicting_evidence"))

    def test_context_false_caller_true_requires_conflict(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["requires_conflicting_evidence"] = False
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["conflicting_evidence"] = []
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=True)
        self.assertEqual("rejected", result["status"])
        self.assertTrue(result["derived_contract_metadata"].get("requires_conflicting_evidence"))

    def test_context_absent_caller_true_requires_conflict(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["conflicting_evidence"] = []
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=True)
        self.assertEqual("rejected", result["status"])
        self.assertTrue(result["derived_contract_metadata"].get("requires_conflicting_evidence"))

    def test_context_absent_caller_false_does_not_require_conflict(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        resp["conflicting_evidence"] = []
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=False)
        self.assertEqual("accepted", result["status"])
        self.assertFalse(result["derived_contract_metadata"].get("requires_conflicting_evidence"))

    def test_malformed_caller_conflict_string_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence="true")
        self.assertEqual("rejected", result["status"])
        self.assertIn("trusted_caller_input_invalid:requires_conflicting_evidence", result["reasons"])

    def test_malformed_caller_conflict_integer_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=1)
        self.assertEqual("rejected", result["status"])
        self.assertIn("trusted_caller_input_invalid:requires_conflicting_evidence", result["reasons"])

    def test_malformed_context_conflict_flag_rejected(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["requires_conflicting_evidence"] = "invalid_string"
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        result = accept_multi_angle_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_context_malformed:requires_conflicting_evidence", result["reasons"])

    def test_conflict_precedence_is_deterministic(self):
        ctx = copy.deepcopy(_VALID_CANONICAL_CONTEXT_FIXTURE)
        ctx["requires_conflicting_evidence"] = True
        resp = copy.deepcopy(_VALID_AI_RESPONSE_FIXTURE)
        res1 = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=False)
        res2 = accept_multi_angle_synthesis(ctx, resp, requires_conflicting_evidence=False)
        self.assertEqual(res1, res2)


if __name__ == "__main__":
    unittest.main()

