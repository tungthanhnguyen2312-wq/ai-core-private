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

# TEST_FIXTURE_ONLY -- shape matches current_research_scenario_context_contract's
# scenario_context_summary derivation (per-axis scenario_status/status_rule only;
# supporting/opposing/risk evidence routes through the existing prose fields above).
_SCENARIO_CONTEXT_SUMMARY_FIXTURE = {
    "CONSERVATIVE": {"scenario_status": "SUPPORTED", "status_rule": "CONSERVATIVE_CONFIRMED_TREND_NO_MATERIAL_RISK"},
    "BASE": {"scenario_status": "SUPPORTED", "status_rule": "BASE_CURRENT_CLASSIFIED_STATE"},
    "SPECULATIVE": {"scenario_status": "NOT_SUPPORTED", "status_rule": "NO_EXPLICIT_EARLY_OR_HIGHER_UNCERTAINTY_EVIDENCE"},
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

    def test_risk_score_claim_rejected(self):
        """No numeric/global risk score exists anywhere in this schema."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["risk_context"].append("Risk score is 7/10.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_risk_score_claim", result["reasons"])

    def test_risk_grade_and_overall_risk_claims_rejected(self):
        for phrase in ("The overall risk here is elevated.", "This ticker has a risk grade of C."):
            with self.subTest(phrase=phrase):
                resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
                resp["risk_context"].append(phrase)
                result = validate_structured_research_synthesis_output(resp)
                self.assertEqual("rejected", result["status"])
                self.assertIn("prohibited_risk_score_claim", result["reasons"])

    def test_low_risk_or_safe_claim_rejected(self):
        """absence_is_not_low_risk: an empty material-risk list can never become a
        LOW_RISK/safe conclusion."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["risk_context"].append("The stock is low risk.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_low_risk_or_safe_claim", result["reasons"])

    def test_few_risk_flags_implies_safer_claim_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["unresolved_questions"].append("Few risk flags mean the stock is safer.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_low_risk_or_safe_claim", result["reasons"])

    def test_no_material_risk_established_factual_text_accepted(self):
        """Explicit false-positive guard named in the milestone spec: the exact
        NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE factual framing must never
        itself be rejected as a low-risk/safe claim."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["risk_context"].append(
            "No material risk has been established from the available evidence, but several data limitations remain."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_valuation_authority_limited_factual_text_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["unresolved_questions"].append(
            "Valuation authority is limited; no authoritative cheapness conclusion is available."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_risk_quantification_claims_rejected(self):
        """18. cannot generate probability/expected loss/VaR from risk evidence."""
        for phrase in (
            "These risks imply a 65% downside probability.",
            "The expected loss from this position is material.",
            "Value at risk is elevated given the financial stress.",
        ):
            with self.subTest(phrase=phrase):
                resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
                resp["risk_context"].append(phrase)
                result = validate_structured_research_synthesis_output(resp)
                self.assertEqual("rejected", result["status"])
                self.assertIn("prohibited_risk_quantification_claim", result["reasons"])

    def test_risk_override_claim_rejected(self):
        """Risk evidence may explain a deterministic action, never claim to override it --
        prohibited even when upstream_decision_context itself is untouched, since the
        false-authority framing is itself the harm."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_thesis"] = resp["counter_thesis"] + " The risk register overrides EARLY_ENTRY to WAIT."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_risk_override_claim", result["reasons"])

    def test_risk_sizing_inference_claim_rejected(self):
        """19. cannot generate position sizing/participation from risk evidence."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_thesis"] = resp["counter_thesis"] + " Risk register means position size should be reduced to 3%."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_risk_sizing_inference_claim", result["reasons"])

    def test_negated_risk_score_language_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append(
            "This synthesis does not compute a risk score; risk evidence is reported as separate qualitative items only."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

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

    # --- AI_SCENARIO_SYNTHESIS_INTEGRATION_V1 TESTS ---

    def test_scenario_context_summary_optional_field_accepted(self):
        """The new field is additive and optional -- present as a structured object,
        it does not disturb an otherwise-valid response."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["scenario_context_summary"] = copy.deepcopy(_SCENARIO_CONTEXT_SUMMARY_FIXTURE)
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])
        self.assertEqual(_SCENARIO_CONTEXT_SUMMARY_FIXTURE, result["accepted_output"]["scenario_context_summary"])

    def test_scenario_context_summary_wrong_type_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["scenario_context_summary"] = "CONSERVATIVE supported, BASE supported, SPECULATIVE not supported."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("wrong_field_type:scenario_context_summary", result["reasons"])

    def test_scenario_context_summary_exact_match_accepted(self):
        """22. old synthesis semantics preserved for the new field too: byte-exact
        quoting of the boundary's derived truth, never a recomputation."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["scenario_context_summary"] = copy.deepcopy(_SCENARIO_CONTEXT_SUMMARY_FIXTURE)
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"expected_scenario_context_summary": _SCENARIO_CONTEXT_SUMMARY_FIXTURE},
        )
        self.assertEqual("accepted", result["status"])

    def test_scenario_context_summary_mismatch_rejected(self):
        """Consumer never recomputes an axis status -- any divergence from the
        boundary's derived truth (here, an upgraded SPECULATIVE status) is rejected."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        tampered = copy.deepcopy(_SCENARIO_CONTEXT_SUMMARY_FIXTURE)
        tampered["SPECULATIVE"]["scenario_status"] = "SUPPORTED"
        resp["scenario_context_summary"] = tampered
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"expected_scenario_context_summary": _SCENARIO_CONTEXT_SUMMARY_FIXTURE},
        )
        self.assertEqual("rejected", result["status"])
        self.assertIn("scenario_context_summary_mismatch", result["reasons"])

    def test_scenario_context_summary_may_be_omitted_when_truth_available(self):
        """The field stays optional even when the boundary has real scenario truth to
        offer -- omitting it must never itself be a rejection reason."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        self.assertNotIn("scenario_context_summary", resp)
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"expected_scenario_context_summary": _SCENARIO_CONTEXT_SUMMARY_FIXTURE},
        )
        self.assertEqual("accepted", result["status"])

    def test_scenario_context_summary_cannot_cite_malformed_sibling(self):
        """19/20 (provenance boundary extended to this field too): a malformed
        scenario sibling cannot be cited through scenario_context_summary either."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["scenario_context_summary"] = copy.deepcopy(_SCENARIO_CONTEXT_SUMMARY_FIXTURE)
        result = validate_structured_research_synthesis_output(
            resp, contract_metadata={"scenario_context_status": "malformed"},
        )
        self.assertEqual("rejected", result["status"])
        self.assertIn("scenario_context_summary_cites_malformed_sibling", result["reasons"])

    def test_existing_response_without_scenario_field_backward_compatible(self):
        """22. old synthesis without the scenario sibling (and without this field at
        all) remains backward compatible -- nothing about this schema became newly
        mandatory."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("scenario_context_summary", result["accepted_output"])

    def test_base_most_likely_claim_rejected(self):
        """5. BASE cannot become most-likely."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " BASE is the most likely scenario here."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_scenario_likelihood_claim", result["reasons"])

    def test_base_expected_case_claim_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["supporting_evidence"].append("BASE is the expected case.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_scenario_likelihood_claim", result["reasons"])

    def test_speculative_less_likely_claim_rejected(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_evidence"].append("SPECULATIVE is less likely given current evidence.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_scenario_likelihood_claim", result["reasons"])

    def test_negated_scenario_likelihood_language_accepted(self):
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["authority_limitations"].append(
            "This synthesis does not claim BASE is the most likely scenario; BASE is only a current-state interpretation, not a probability."
        )
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_conservative_safest_claim_rejected(self):
        """7. CONSERVATIVE cannot become bearish/safe -- including the 'safest'
        superlative, which the pre-existing bare 'safe'/'safer' guard did not catch."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["risk_context"].append("CONSERVATIVE is the safest outcome.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_low_risk_or_safe_claim", result["reasons"])

    def test_conservative_bearish_bare_word_still_rejected_by_existing_guard(self):
        """7. CONSERVATIVE cannot become bearish -- already covered by the pre-existing
        bare bullish/bearish event-impact guard; documents that no new guard was needed
        for this specific wording (only for 'safest')."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_thesis"] = resp["counter_thesis"] + " CONSERVATIVE is bearish."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_impact_claim", result["reasons"])

    def test_speculative_bullish_bare_word_still_rejected_by_existing_guard(self):
        """6. SPECULATIVE cannot become bullish -- already covered by the pre-existing
        bare bullish/bearish event-impact guard."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " SPECULATIVE is bullish."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_impact_claim", result["reasons"])

    def test_speculative_higher_return_claim_rejected(self):
        """6. SPECULATIVE cannot become a higher-expected-return claim -- broader than
        the existing numeric expected-return regex, which requires a digit."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["counter_evidence"].append("SPECULATIVE offers a higher expected return than the other axes.")
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_scenario_return_inference_claim", result["reasons"])

    def test_scenario_action_override_claims_rejected(self):
        """9/10. scenario support/non-support cannot causally create or change an
        action -- even when upstream_decision_context itself is left untouched."""
        for phrase, reason in (
            ("BASE is supported, therefore BUY.", "prohibited_scenario_action_override_claim"),
            ("SPECULATIVE supported therefore EARLY_ENTRY.", "prohibited_scenario_action_override_claim"),
            ("CONSERVATIVE is not supported, so downgrade to WAIT.", "prohibited_scenario_action_override_claim"),
        ):
            with self.subTest(phrase=phrase):
                resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
                resp["counter_thesis"] = resp["counter_thesis"] + " " + phrase
                result = validate_structured_research_synthesis_output(resp)
                self.assertEqual("rejected", result["status"])
                self.assertIn(reason, result["reasons"])

    def test_scenario_supported_with_unchanged_action_not_a_false_positive(self):
        """Explicit false-positive guard named in the milestone spec: scenario support
        coexisting with an unchanged deterministic action must never itself be
        rejected."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " SPECULATIVE is supported but entry_action remains WAIT."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_base_supported_while_wait_stays_wait_not_a_false_positive(self):
        """9. BASE supported + WAIT stays WAIT -- explaining coexistence is not an
        override claim."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " BASE is supported by the current classified state, while the deterministic entry action remains WAIT."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("accepted", result["status"])

    def test_historical_win_rate_claim_rejected(self):
        """18. historical context cannot create a win rate."""
        resp = copy.deepcopy(_VALID_RESPONSE_FIXTURE)
        resp["historical_context_summary"] = resp["historical_context_summary"] + " The historical win rate for this setup is 70%."
        result = validate_structured_research_synthesis_output(resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_historical_win_rate_claim", result["reasons"])


if __name__ == "__main__":
    unittest.main()
