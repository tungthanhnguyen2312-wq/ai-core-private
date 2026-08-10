"""Unit tests for the multi-angle synthesis response validator.

Tests fail-closed structural validation, prohibited claim detection, and false-positive
safety for negated safety statements.
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

from builders.multi_angle_synthesis_response import validate_multi_angle_synthesis_output

# TEST_FIXTURE_ONLY -- synthetic fixture for multi-angle synthesis tests.
# Does NOT import retained production data.
_VALID_SYNTHESIS_FIXTURE = {
    "ticker": "TEST_TICKER",
    "facts": [
        "FY2024 operating cash flow was positive.",
        "Bounded 18-session cumulative return was -0.022.",
        "Bounded 18-session beta was 0.809 with 18 paired returns.",
        "Foreign net buy value was positive over retained sessions.",
    ],
    "data_warnings": [
        "analysis_time_semantics = current_state_using_retrospectively_adjusted_history.",
        "pit_backtest_eligible = false; these observations are not point-in-time backtest evidence.",
        "is_actionable = false; evidence does not justify a BUY recommendation.",
        "sample_adequacy = MATHEMATICALLY_COMPUTABLE; 18 pairs is a bounded sample, not statistically robust.",
        "SMA20 is unavailable.",
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
        "Point-in-time backtest dataset.",
    ],
    "invalidation_conditions": [
        "Deterioration in upcoming quarterly operating cash flows.",
    ],
}


class MultiAngleSynthesisResponseValidatorTests(unittest.TestCase):
    # --- VALID CASES ---
    def test_valid_seven_category_structured_response_accepted(self):
        result = validate_multi_angle_synthesis_output(
            json.dumps(_VALID_SYNTHESIS_FIXTURE),
            contract_metadata={"requires_conflicting_evidence": True, "unavailable_indicators": ["sma_20"]},
        )
        self.assertEqual("accepted", result["status"])
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE, result["accepted_output"])

    def test_facts_preserved_unchanged(self):
        result = validate_multi_angle_synthesis_output(copy.deepcopy(_VALID_SYNTHESIS_FIXTURE))
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE["facts"], result["accepted_output"]["facts"])

    def test_warnings_preserved_unchanged(self):
        result = validate_multi_angle_synthesis_output(copy.deepcopy(_VALID_SYNTHESIS_FIXTURE))
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE["data_warnings"], result["accepted_output"]["data_warnings"])

    def test_inference_preserved_unchanged(self):
        result = validate_multi_angle_synthesis_output(copy.deepcopy(_VALID_SYNTHESIS_FIXTURE))
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE["supported_inferences"], result["accepted_output"]["supported_inferences"])

    def test_conflicting_evidence_preserved_unchanged(self):
        result = validate_multi_angle_synthesis_output(copy.deepcopy(_VALID_SYNTHESIS_FIXTURE))
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE["conflicting_evidence"], result["accepted_output"]["conflicting_evidence"])

    def test_hypotheses_preserved_unchanged(self):
        result = validate_multi_angle_synthesis_output(copy.deepcopy(_VALID_SYNTHESIS_FIXTURE))
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE["hypotheses"], result["accepted_output"]["hypotheses"])

    def test_missing_evidence_preserved_unchanged(self):
        result = validate_multi_angle_synthesis_output(copy.deepcopy(_VALID_SYNTHESIS_FIXTURE))
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE["missing_evidence"], result["accepted_output"]["missing_evidence"])

    def test_invalidation_preserved_unchanged(self):
        result = validate_multi_angle_synthesis_output(copy.deepcopy(_VALID_SYNTHESIS_FIXTURE))
        self.assertEqual(_VALID_SYNTHESIS_FIXTURE["invalidation_conditions"], result["accepted_output"]["invalidation_conditions"])

    def test_explicit_pit_false_safety_statement_accepted(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["data_warnings"].append("These observations are not point-in-time backtest evidence.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("accepted", result["status"])

    def test_descriptive_beta_correlation_statement_accepted(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("Beta and correlation are descriptive statistics over the bounded paired sample.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("accepted", result["status"])

    def test_descriptive_foreign_flow_value_statement_accepted(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("Foreign net buy value was positive over the retained observations.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("accepted", result["status"])

    def test_unavailable_sma_explicitly_reported_as_unavailable_accepted(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["data_warnings"].append("SMA20 is unavailable.")
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unavailable_indicators": ["sma_20"]})
        self.assertEqual("accepted", result["status"])

    def test_deterministic_repeated_validation(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        res1 = validate_multi_angle_synthesis_output(output)
        res2 = validate_multi_angle_synthesis_output(output)
        self.assertEqual(res1, res2)

    # --- FAIL CLOSED CASES ---
    def test_rejects_non_json_structure(self):
        result = validate_multi_angle_synthesis_output("free form response text")
        self.assertEqual("rejected", result["status"])
        self.assertIn("response_not_valid_json", result["reasons"])

    def test_rejects_missing_required_category(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        del output["conflicting_evidence"]
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("missing_category:conflicting_evidence", result["reasons"])

    def test_rejects_unexpected_top_level_recommendation_field(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["recommendation"] = "BUY"
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:recommendation", result["reasons"])

    def test_rejects_affirmative_buy_recommendation(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("We recommend a BUY for this stock.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_rejects_affirmative_sell_recommendation(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("This stock is a SELL.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_rejects_affirmative_hold_recommendation(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("Issue a HOLD recommendation.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_rejects_affirmative_target_price_claim(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("Target price of 35000 VND.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_rejects_affirmative_position_sizing_claim(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("Recommended position size: 5% of portfolio.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_rejects_pit_backtest_proof_claim(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("These current-state metrics provide backtest proof.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_pit_backtest_proof_claim", result["reasons"])

    def test_rejects_statistically_robust_claim_from_mathematically_computable(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("18 paired observations is statistically robust beta.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_statistical_robustness_claim", result["reasons"])

    def test_rejects_statistically_significant_claim_without_authority(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("The 18-session return is statistically significant beta.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_statistical_robustness_claim", result["reasons"])

    def test_rejects_correlation_causation_claim(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("Correlation proves causation between benchmark and stock.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_correlation_causality_claim", result["reasons"])

    def test_rejects_institutional_accumulation_from_foreign_flow_value(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("Foreign institutions accumulated the stock aggressively.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_foreign_flow_overclaim", result["reasons"])

    def test_rejects_causal_price_impact_from_foreign_flow(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["supported_inferences"].append("Foreign buying caused the stock price surge.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_foreign_flow_overclaim", result["reasons"])

    def test_rejects_qualified_foreign_volume_claim_without_authority(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("Foreign volume was = 5000000 shares.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_foreign_flow_overclaim", result["reasons"])

    def test_rejects_foreign_room_claim_without_authority(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("Foreign room is = 49%.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_foreign_flow_overclaim", result["reasons"])

    def test_rejects_flow_turnover_claim_without_authority(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("The flow to turnover ratio was 15%.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_foreign_flow_overclaim", result["reasons"])

    def test_rejects_fabricated_unavailable_sma20(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("SMA20 = 28.5")
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unavailable_indicators": ["sma_20"]})
        self.assertEqual("rejected", result["status"])
        self.assertIn("fabricated_unavailable_sma20_indicator", result["reasons"])

    def test_rejects_price_above_below_sma20_when_sma_unavailable(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("Price is above SMA20.")
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unavailable_indicators": ["sma_20"]})
        self.assertEqual("rejected", result["status"])
        self.assertIn("fabricated_unavailable_sma20_indicator", result["reasons"])

    def test_rejects_empty_conflicting_evidence_when_required(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["conflicting_evidence"] = []
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"requires_conflicting_evidence": True})
        self.assertEqual("rejected", result["status"])
        self.assertIn("conflicting_evidence_required_but_empty", result["reasons"])

    def test_rejects_hypothesis_inserted_into_facts(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("Hypothesis: short term price drop is temporary.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("rejected", result["status"])
        self.assertIn("hypothesis_inserted_into_facts", result["reasons"])

    # --- FALSE POSITIVE SAFETY TESTS (STEP 13) ---
    def test_accepts_negated_buy_recommendation_disclaimer(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["data_warnings"].append("This evidence does not justify a BUY recommendation.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("accepted", result["status"])

    def test_accepts_negated_correlation_causation_disclaimer(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["data_warnings"].append("Correlation does not imply causation.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("accepted", result["status"])

    def test_accepts_negated_pit_backtest_disclaimer(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["data_warnings"].append("These observations are not point-in-time backtest evidence.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("accepted", result["status"])

    def test_accepts_negated_foreign_accumulation_disclaimer(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["data_warnings"].append("Foreign net buy value does not prove institutional accumulation.")
        result = validate_multi_angle_synthesis_output(output)
        self.assertEqual("accepted", result["status"])

    def test_accepts_explicit_unavailable_sma_disclaimer(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["data_warnings"].append("SMA20 is unavailable.")
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unavailable_indicators": ["sma_20"]})
        self.assertEqual("accepted", result["status"])

    # --- METADATA VALIDATION TESTS ---

    def test_contract_metadata_none_accepted(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata=None)
        self.assertEqual("accepted", result["status"])

    def test_contract_metadata_string_rejected(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata="invalid_str")
        self.assertEqual("rejected", result["status"])
        self.assertIn("contract_metadata_invalid", result["reasons"])

    def test_contract_metadata_list_rejected(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata=["invalid"])
        self.assertEqual("rejected", result["status"])
        self.assertIn("contract_metadata_invalid", result["reasons"])

    def test_unavailable_indicators_wrong_scalar_type_rejected(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unavailable_indicators": "sma_20"})
        self.assertEqual("rejected", result["status"])
        self.assertIn("contract_metadata_invalid:unavailable_indicators", result["reasons"])

    def test_unavailable_indicators_non_string_entry_rejected(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unavailable_indicators": ["sma_20", 123]})
        self.assertEqual("rejected", result["status"])
        self.assertIn("contract_metadata_invalid:unavailable_indicators", result["reasons"])

    def test_requires_conflicting_evidence_string_rejected(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"requires_conflicting_evidence": "true"})
        self.assertEqual("rejected", result["status"])
        self.assertIn("contract_metadata_invalid:requires_conflicting_evidence", result["reasons"])

    def test_requires_conflicting_evidence_integer_rejected(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"requires_conflicting_evidence": 1})
        self.assertEqual("rejected", result["status"])
        self.assertIn("contract_metadata_invalid:requires_conflicting_evidence", result["reasons"])

    def test_unknown_metadata_key_rejected(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unknown_key": "val"})
        self.assertEqual("rejected", result["status"])
        self.assertIn("unexpected_contract_metadata_fields:unknown_key", result["reasons"])

    def test_valid_unavailable_indicators_activates_sma_guard(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["facts"].append("SMA20 = 28.5")
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"unavailable_indicators": ["sma_20"]})
        self.assertEqual("rejected", result["status"])
        self.assertIn("fabricated_unavailable_sma20_indicator", result["reasons"])

    def test_valid_requires_conflicting_evidence_requires_non_empty_conflicting_evidence(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        output["conflicting_evidence"] = []
        result = validate_multi_angle_synthesis_output(output, contract_metadata={"requires_conflicting_evidence": True})
        self.assertEqual("rejected", result["status"])
        self.assertIn("conflicting_evidence_required_but_empty", result["reasons"])

    def test_repeated_malformed_metadata_validation_deterministic(self):
        output = copy.deepcopy(_VALID_SYNTHESIS_FIXTURE)
        res1 = validate_multi_angle_synthesis_output(output, contract_metadata="invalid_str")
        res2 = validate_multi_angle_synthesis_output(output, contract_metadata="invalid_str")
        self.assertEqual(res1, res2)


if __name__ == "__main__":
    unittest.main()

