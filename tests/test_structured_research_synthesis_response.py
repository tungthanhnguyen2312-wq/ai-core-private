"""Focused unit tests for the structured AI research-synthesis response validator."""

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.structured_research_synthesis_response import validate_structured_research_synthesis_output

# TEST_FIXTURE_ONLY -- synthetic fixture for response-validator tests. Context-free by
# design: this module validates structure and text only. Context-aware truth checks
# (upstream decision quoting, evidence-reference traceability) are exercised against a
# real ticker context in test_structured_research_synthesis_boundary.py.
_VALID_RESPONSE_FIXTURE = {
    "ticker": "TEST_TICKER",
    "analysis_session": "2026-08-24T09:00:00+07:00",
    "synthesis_status": "PARTIAL_EVIDENCE",
    "thesis": "Operating cash flow has stayed positive across the retained FY2024 brief while the tactical classifier reports a base-building structure.",
    "supporting_evidence": [
        "historical_fundamental_brief reports positive FY2024 operating cash flow.",
        "watchlist_tactical_entry_classifier reports entry_state=BASE_BUILDING.",
    ],
    "counter_thesis": "The retained history shows a DETERIORATION structural state and the classifier's own confirmation trigger has not fired.",
    "counter_evidence": [
        "market_wide_historical_research_context reports structural_state.value=DETERIORATION.",
        "watchlist_tactical_entry_classifier confirmation_trigger has not been satisfied.",
    ],
    "historical_context_summary": "As of session 2026-08-20, market_wide_historical_research_context reports a DETERIORATION structural state; descriptive only, not an entry action.",
    "valuation_context_summary": "As of the valuation lane's own price session, P/B is RESEARCH_USABLE while EV/EBITDA is BLOCKED; RESEARCH_USABLE remains research-only.",
    "market_context_summary": "As of session 2026-08-25, current_market_sector_leadership_context reports MIXED_BREADTH market-wide participation; descriptive context, not a trade signal.",
    "sector_context_summary": "The ticker's own sector_leadership_context is AVAILABLE with leadership_state=LEADING on observed participation; descriptive only, not a research-priority upgrade.",
    "relative_strength_context": [
        "market_relative_momentum reports the ticker in the TOP_QUINTILE momentum bucket versus the current official-universe cohort.",
        "breadth_support_state=MARKET_AND_GROUP_BREADTH_SUPPORT: both market and sector breadth corroborate the ticker's own technical posture.",
    ],
    "catalyst_context": [
        "historical_decision_analysis lists a qualified catalyst window.",
    ],
    "risk_context": [
        "historical_decision_analysis retains a fundamental risk note about margin compression.",
    ],
    "invalidation_conditions": [
        "watchlist_tactical_entry_classifier invalidation: a close below the prior base low invalidates the base-building read.",
    ],
    "unresolved_questions": [
        "market_wide_current_valuation does not report EV/EBITDA (BLOCKED); unresolved whether it would corroborate P/B.",
    ],
    "authority_limitations": [
        "EV/EBITDA is BLOCKED and not usable as valuation evidence.",
    ],
    "upstream_decision_context": {
        "tactical_entry_classifier": {
            "entry_state": "BASE_BUILDING",
            "entry_action": "ACCUMULATE_IN_BASE",
            "action": "ACCUMULATE_IN_BASE",
            "horizon": "MULTI_WEEK_SWING",
            "is_full_position_ready": False,
            "position_sizing_status": "NOT_EVALUATED",
        },
    },
    "provenance_references": [
        "historical_fundamental_brief",
        "market_wide_historical_research_context",
        "market_wide_current_valuation.metrics.pb",
        "watchlist_tactical_entry_classifier",
        "current_market_sector_leadership_context",
    ],
    "is_actionable": False,
}


class StructuredResearchSynthesisResponseTests(unittest.TestCase):
    # --- VALID CASES ---
    def test_valid_response_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])
        self.assertEqual(resp, result["accepted_output"])
        self.assertEqual([], result["reasons"])

    def test_valid_response_as_json_string_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(json.dumps(resp))
        self.assertEqual("accepted", result["status"])
        self.assertEqual(resp, result["accepted_output"])

    def test_accepted_output_is_a_deep_copy(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(resp)
        result["accepted_output"]["thesis"] = "mutated"
        self.assertEqual(_VALID_RESPONSE_FIXTURE["thesis"], resp["thesis"])

    def test_deterministic_repeated_call(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        res1 = validate_structured_research_synthesis_output(resp)
        res2 = validate_structured_research_synthesis_output(resp)
        self.assertEqual(res1, res2)

    def test_negated_probability_language_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append("Do not infer a probability of success from this evidence.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_empty_optional_categories_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["catalyst_context"] = []
        resp["risk_context"] = []
        resp["invalidation_conditions"] = []
        resp["unresolved_questions"] = []
        resp["authority_limitations"] = []
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    # --- STRUCTURAL REJECTIONS ---
    def test_invalid_json_rejected(self):
        result = validate_structured_research_synthesis_output("{not valid json")
        self.assertEqual("rejected", result["status"])
        self.assertIn("response_not_valid_json", result["reasons"])

    def test_non_object_response_rejected(self):
        result = validate_structured_research_synthesis_output(json.dumps(["a", "list"]))
        self.assertEqual("rejected", result["status"])
        self.assertIn("response_not_structured_object", result["reasons"])

    def test_missing_thesis_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        del resp["thesis"]
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("missing_field:thesis", result["reasons"])

    def test_missing_counter_thesis_rejected(self):
        """VALIDATION case: counter-thesis is required for a valid synthesis."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        del resp["counter_thesis"]
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("missing_field:counter_thesis", result["reasons"])

    def test_empty_counter_thesis_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_thesis"] = "   "
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("empty_required_field:counter_thesis", result["reasons"])

    def test_empty_counter_evidence_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_evidence"] = []
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("empty_required_category:counter_evidence", result["reasons"])

    def test_empty_supporting_evidence_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["supporting_evidence"] = []
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("empty_required_category:supporting_evidence", result["reasons"])

    def test_empty_provenance_references_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["provenance_references"] = []
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("empty_required_category:provenance_references", result["reasons"])

    def test_invalid_synthesis_status_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["synthesis_status"] = "HIGH_CONFIDENCE"
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("invalid_synthesis_status", result["reasons"])

    def test_wrong_category_type_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["supporting_evidence"] = "not_a_list"
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("wrong_category_type:supporting_evidence", result["reasons"])

    def test_non_string_list_item_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["catalyst_context"] = [123]
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("wrong_category_type:catalyst_context", result["reasons"])

    def test_upstream_decision_context_wrong_type_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["upstream_decision_context"] = "not_an_object"
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("wrong_field_type:upstream_decision_context", result["reasons"])

    def test_is_actionable_missing_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        del resp["is_actionable"]
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("missing_field:is_actionable", result["reasons"])

    def test_is_actionable_true_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["is_actionable"] = True
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("is_actionable_must_be_false", result["reasons"])

    def test_unexpected_field_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["extra_free_form_field"] = "not part of the contract"
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("unexpected_response_fields:extra_free_form_field", result["reasons"])

    # --- CORE AUTHORITY RULE: prohibited top-level minted fields ---
    def test_prohibited_top_level_target_price_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["target_price"] = 35000
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:target_price", result["reasons"])

    def test_prohibited_top_level_entry_action_rejected(self):
        """entry_action may only live, quoted, inside upstream_decision_context."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["entry_action"] = "BUY"
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:entry_action", result["reasons"])

    def test_prohibited_top_level_probability_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["probability"] = 0.8
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:probability", result["reasons"])

    def test_prohibited_top_level_position_size_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["position_size"] = "5%"
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:position_size", result["reasons"])

    def test_prohibited_top_level_recommendation_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["recommendation"] = "BUY"
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:recommendation", result["reasons"])

    # --- TEXTUAL SAFETY: affirmative claims anywhere in the narrative ---
    def test_recommendation_claim_in_thesis_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " We recommend BUY."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_target_price_claim_in_valuation_summary_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["valuation_context_summary"] = resp["valuation_context_summary"] + " Target price of 35000."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_probability_claim_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["supporting_evidence"].append("There is an 80% probability of a rebound.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_probability_or_expected_return_claim", result["reasons"])

    def test_expected_return_claim_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_evidence"].append("Expected return of 15% over the next quarter.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_probability_or_expected_return_claim", result["reasons"])

    def test_valuation_overclaim_rejected(self):
        """RESEARCH_USABLE/READY valuation metrics must never become a cheapness verdict."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["valuation_context_summary"] = "The stock is undervalued relative to peers."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_valuation_overclaim", result["reasons"])

    def test_forecast_claim_rejected(self):
        """Financial momentum (and every other current-research lane) is retrospective/
        current, never forward-looking."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " We forecast continued earnings growth."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_forecast_claim", result["reasons"])

    def test_will_likely_grow_forecast_claim_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_evidence"].append("Revenue will likely grow next quarter based on the current trend.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_forecast_claim", result["reasons"])

    def test_negated_forecast_language_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append(
            "This synthesis does not claim revenue will likely grow next quarter; only retained comparable-period evidence is reported."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_event_impact_claim_rejected(self):
        """Corporate-event existence is a temporal/evidentiary fact, never a price-
        direction claim -- 'bullish'/'bearish' language is prohibited."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["catalyst_context"].append("The confirmed dividend event is bullish for the stock.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_impact_claim", result["reasons"])

    def test_event_reaction_language_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " The market should react positively to this confirmed event."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_impact_claim", result["reasons"])

    def test_negated_event_impact_language_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append(
            "This synthesis does not claim the confirmed dividend event is bullish; event existence is not a price-impact claim."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_event_driven_eligibility_claim_rejected(self):
        """EVENT_DRIVEN eligibility is a separate deterministic authority this contract
        never mints; a retained corporate event cannot confirm or enable it."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["catalyst_context"].append("This retained event confirms EVENT_DRIVEN eligibility.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_driven_eligibility_claim", result["reasons"])

    def test_inferred_ex_date_claim_rejected(self):
        """record_date != ex_date is binding; the 'minus one trading day' heuristic (or
        any equivalent inference) is prohibited."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["catalyst_context"].append(
            "The retained record has record_date without ex_date; the ex-date is assumed to be one trading day before the record date."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_inferred_ex_date_claim", result["reasons"])

    def test_negated_ex_date_inference_language_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append(
            "The ex-date is not estimated or inferred from the record date; only the retained ex_date field, when present, is used."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_event_status_inference_claim_rejected(self):
        """planned/approved != executed; the AI cannot self-infer completion from a
        planned/approved record with no retained execution evidence."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["catalyst_context"].append(
            "The approved issuance can be considered executed given the strength of the other evidence."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_status_inference_claim", result["reasons"])

    def test_buy_before_record_date_claim_rejected(self):
        """Event-based imperative timing action ('Buy before the record date.') is a
        BUY/SELL claim the declarative recommendation regex alone would not catch."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " Buy before the record date to capture the dividend."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_capacity_or_participation_claim_rejected(self):
        """This contract consumes no liquidity/traded-value lane (e.g. the currently
        restricted ADTV20_MATCHED_VALUE Producer lane); it must never imply how much
        size a position could absorb."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["risk_context"].append("The stock has sufficient liquidity for a large position.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_capacity_or_participation_claim", result["reasons"])

    def test_execution_capacity_claim_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append("Current volume gives this ticker strong execution capacity.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_capacity_or_participation_claim", result["reasons"])

    def test_negated_capacity_claim_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append("This synthesis does not consume a liquidity lane and cannot state execution capacity.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_historical_structural_state_action_claim_rejected(self):
        """VALIDATION case: historical structural_state cannot become an action claim."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["historical_context_summary"] = "Given the DETERIORATION structural state, we recommend SELL."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    # --- CONTEXT-DERIVED TRUTH CHECKS (metadata supplied by the boundary) ---
    def test_ticker_mismatch_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(resp, contract_metadata={"expected_ticker": "OTHER"})
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_mismatch", result["reasons"])

    def test_upstream_decision_context_mismatch_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        expected = {"tactical_entry_classifier": {"entry_action": "WAIT"}}
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"expected_upstream_decision_context": expected},
        )
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_upstream_decision_context_exact_match_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"expected_upstream_decision_context": resp["upstream_decision_context"]},
        )
        self.assertEqual("accepted", result["status"])

    def test_unknown_evidence_reference_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"known_evidence_refs": ["historical_fundamental_brief"]},
        )
        self.assertEqual("rejected", result["status"])
        self.assertTrue(any(r.startswith("unknown_evidence_reference:") for r in result["reasons"]))

    def test_known_evidence_references_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"known_evidence_refs": resp["provenance_references"]},
        )
        self.assertEqual("accepted", result["status"])

    def test_contract_metadata_invalid_type_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(resp, contract_metadata="not_a_mapping")
        self.assertEqual("rejected", result["status"])
        self.assertIn("contract_metadata_invalid", result["reasons"])

    def test_unexpected_contract_metadata_field_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(resp, contract_metadata={"bogus_key": 1})
        self.assertEqual("rejected", result["status"])
        self.assertIn("unexpected_contract_metadata_fields:bogus_key", result["reasons"])


if __name__ == "__main__":
    unittest.main()
