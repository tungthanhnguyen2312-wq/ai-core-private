"""Focused unit tests for the structured AI research-synthesis acceptance boundary.

Covers the AI_STRUCTURED_RESEARCH_SYNTHESIS_V1 VALIDATION list: upstream preservation,
mandatory counter-thesis, historical/valuation authority boundaries, missing/malformed
sibling handling, prohibited mint fields, distinct sibling sessions, provenance survival,
and backward compatibility with the existing (unmodified) context builder.
"""

from __future__ import annotations

import copy
import inspect
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.structured_research_synthesis_boundary import accept_structured_research_synthesis

# TEST_FIXTURE_ONLY -- synthetic fixtures for boundary tests. Shapes match the real
# canonical contracts produced by builders/build_ticker_context.py's
# apply_bundle_watchlist_tactical_entry_classifier_contract,
# apply_bundle_current_opportunity_decision_context_contract,
# apply_bundle_market_wide_historical_research_context_contract, and
# apply_bundle_market_wide_current_valuation_contract (field names and malformed
# sentinels verified against that source, 2026-08-25).
_TACTICAL_FIXTURE = {
    "ticker": "TEST_TICKER",
    "status": "classified",
    "is_actionable": False,
    "market_state": "NEUTRAL",
    "ticker_structure_state": "BASE_BUILDING",
    "entry_state": "BASE_BUILDING",
    "evidence_for": ["Price reclaimed the 20-session base midpoint."],
    "evidence_against": ["Volume has not confirmed the base."],
    "data_quality": {"confidence": "MEDIUM", "warnings": []},
    "action": "ACCUMULATE_IN_BASE",
    "entry_action": "ACCUMULATE_IN_BASE",
    "confirmation_trigger": "Close above the prior base high.",
    "invalidation": "Close below the prior base low.",
    "horizon": "MULTI_WEEK_SWING",
    "is_full_position_ready": False,
    "position_sizing_status": "NOT_EVALUATED",
    "fundamental_context": {"status": "NOT_IN_FUNDAMENTAL_COHORT"},
}
_OPPORTUNITY_FIXTURE = {
    "contract_version": "daily_opportunity_decision_queue/v1",
    "ticker_record": {
        "ticker": "TEST_TICKER",
        "research_priority_tier": "PRIORITY_NOW",
        "eligible_strategies": ["VALUE", "MOMENTUM"],
        "lane_specific_priority": {},
        "entry_action": "WAIT",
        "entry_relevant": True,
        "is_actionable": False,
        "authority_note": "Research priority only; not trade readiness.",
        "invalidation_or_context_warnings": [],
    },
}
_HISTORICAL_FIXTURE = {
    "ticker": "TEST_TICKER",
    "status": "available",
    "is_actionable": False,
    "research_mode": "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER",
    "session": "2026-08-20",
    "context_status": "AVAILABLE",
    "structural_state": {
        "status": "AVAILABLE", "value": "DETERIORATION",
        "not_entry_state": True, "not_strategy_eligibility": True,
    },
}
_VALUATION_FIXTURE = {
    "ticker": "TEST_TICKER",
    "status": "current_valuation_snapshot",
    "is_actionable": False,
    "price_input": {"session": "2026-08-24"},
    "metrics": {
        "pb": {"status": "READY", "value": 1.2},
        "ev_ebitda": {"status": "BLOCKED", "value": None},
        "ev_sales": {"status": "NOT_APPLICABLE", "value": None},
    },
}
_MARKET_SECTOR_FIXTURE = {
    "ticker": "TEST_TICKER",
    "session": "2026-08-25",
    "status": "available",
    "is_actionable": False,
    "research_mode": "CURRENT_SESSION_DESCRIPTIVE_MARKET_AND_SECTOR_CONTEXT",
    "market": {"current_breadth_state": "MIXED_BREADTH", "missing_current_session_count": 12},
    "ticker_context": {
        "ticker": "TEST_TICKER", "status": "AVAILABLE",
        "breadth_support_state": "MARKET_AND_GROUP_BREADTH_SUPPORT",
        "sector_leadership_context": {
            "status": "AVAILABLE", "leadership_state": "LEADING",
            "group_key": "QUALIFIED_CLASSIFICATION|QUALIFIED_ENTITY_CLASS|Steel",
        },
        "market_relative_momentum": {"status": "AVAILABLE", "momentum_bucket": "TOP_QUINTILE"},
    },
}
_FINANCIAL_MOMENTUM_FIXTURE = {
    "ticker": "TEST_TICKER",
    "session": "2026-08-24",
    "status": "available",
    "is_actionable": False,
    "research_mode": "CURRENT_RESEARCH_ONLY",
    "ticker_context": {
        "ticker": "TEST_TICKER",
        "evidence_tier": "OFFICIAL_QUALIFIED",
        "coverage_status": "FULL",
        "financial_momentum_state": "BROAD_IMPROVEMENT",
        "components": {
            "revenue_growth": {"status": "AVAILABLE", "direction": "EXPANDING"},
            "earnings_growth": {"status": "AVAILABLE", "direction": "EXPANDING"},
            "net_margin_change": {"status": "AVAILABLE", "direction": "DETERIORATING"},
            "operating_cash_flow": {"status": "BLOCKED", "direction": None},
        },
        "supporting_dimensions": ["revenue_growth", "earnings_growth"],
        "weakening_dimensions": ["net_margin_change"],
    },
}
_CORPORATE_EVENT_UPCOMING_ID = "current_corporate_event:test-upcoming-dividend"
_CORPORATE_EVENT_FIXTURE = {
    "ticker": "TEST_TICKER",
    "research_session": "2026-08-21",
    "status": "available",
    "is_actionable": False,
    "research_mode": "CURRENT_RESEARCH_ONLY",
    "ticker_context": {
        "ticker": "TEST_TICKER",
        "research_session": "2026-08-21",
        "events": [
            {
                "ticker": "TEST_TICKER", "event_type": "CASH_DIVIDEND", "event_status": "CONFIRMED_UPCOMING",
                "evidence_tier": "OFFICIAL_QUALIFIED", "record_date": "2026-09-03", "ex_date": "2026-08-28",
                "execution_date": None, "known_at": "2026-08-10", "temporal_completeness": "COMPLETE",
                "conflicts": [], "warnings": [], "insufficient_for_event_driven": False,
                "event_id": _CORPORATE_EVENT_UPCOMING_ID,
            },
        ],
        "confirmed_upcoming_count": 1, "planned_unresolved_count": 0, "conflicting_count": 0,
        "has_qualified_event": True, "does_not_enable_event_driven": True,
    },
}
_RISK_REGISTER_MATERIAL_ID = "TEST_TICKER:FINANCIAL:FINANCIAL_STRESS"
_RISK_REGISTER_LIMITATION_ID = "TEST_TICKER:VALUATION_AUTHORITY:VALUATION_METRICS_BLOCKED"
_RISK_REGISTER_FIXTURE = {
    "ticker": "TEST_TICKER",
    "source_artifact_identity": "current_research_risk_register:abc123",
    "source_contexts": {
        "historical": {"artifact_identity": "market_wide_historical_research_context:h1", "as_of": "2026-08-20", "available": True},
        "leadership": {"artifact_identity": "current_market_sector_leadership_context:l1", "as_of": "2026-08-25", "available": True},
        "financial": {"artifact_identity": "current_financial_momentum_context:f1", "as_of": "2026-08-24", "available": True},
        "event": {"artifact_identity": "current_corporate_event_context:e1", "as_of": "2026-08-21", "available": True},
        "valuation": {"artifact_identity": "market_wide_current_valuation_input_scaleout:v1", "as_of": "2026-08-24", "available": True},
    },
    "risk_register": {
        "ticker": "TEST_TICKER",
        "material_risks": [
            {
                "risk_id": _RISK_REGISTER_MATERIAL_ID, "risk_domain": "FINANCIAL", "risk_type": "FINANCIAL_STRESS",
                "status": "ESTABLISHED", "severity_band": "MATERIAL", "source_context": "current_financial_momentum_context:f1",
                "source_as_of": "2026-08-24", "observed_facts": {"financial_momentum_state": "LOSS_MAKING_OR_STRESSED"},
                "reason_codes": ["LOSS_MAKING_OR_STRESSED_STATE"], "authority_tier": "OFFICIAL_QUALIFIED",
            },
        ],
        "watch_risks": [],
        "data_authority_limitations": [
            {
                "risk_id": _RISK_REGISTER_LIMITATION_ID, "risk_domain": "VALUATION_AUTHORITY", "risk_type": "VALUATION_METRICS_BLOCKED",
                "status": "DATA_LIMITATION", "severity_band": "DATA_LIMITATION", "source_context": "market_wide_current_valuation_input_scaleout:v1",
                "source_as_of": "2026-08-24", "observed_facts": {"metric_status_counts": {"BLOCKED": 1}},
                "reason_codes": ["PER_METRIC_BLOCKED_STATUS_PRESERVED"], "authority_tier": "CURRENT_VALUATION_RESEARCH",
            },
        ],
        "unresolved_conflicts": [],
        "risk_register_status": "MATERIAL_RISKS_ESTABLISHED",
    },
}
_PROVENANCE_FIXTURE = [
    {"source_dataset": "historical_fundamental_brief"},
    {"source_dataset": "market_wide_historical_research_context"},
    {"source_dataset": "market_wide_current_valuation"},
    {"source_dataset": "watchlist_tactical_entry_classifier"},
    {"source_dataset": "daily_opportunity_decision_queue"},
    {"source_dataset": "current_market_sector_leadership_context"},
    {"source_dataset": "current_financial_momentum_context"},
    {"source_dataset": "current_corporate_event_context"},
    {"source_dataset": "current_research_risk_register"},
]
_TICKER_CONTEXT_FIXTURE = {
    "ticker": "TEST_TICKER",
    "provenance": _PROVENANCE_FIXTURE,
    "watchlist_tactical_entry_classifier": _TACTICAL_FIXTURE,
    "current_opportunity_decision_context": _OPPORTUNITY_FIXTURE,
    "market_wide_historical_research_context": _HISTORICAL_FIXTURE,
    "market_wide_current_valuation": _VALUATION_FIXTURE,
    "current_market_sector_leadership_context": _MARKET_SECTOR_FIXTURE,
    "current_financial_momentum_context": _FINANCIAL_MOMENTUM_FIXTURE,
    "current_corporate_event_context": _CORPORATE_EVENT_FIXTURE,
    "current_research_risk_register": _RISK_REGISTER_FIXTURE,
}
_EXPECTED_UPSTREAM = {
    "tactical_entry_classifier": {
        "entry_state": "BASE_BUILDING", "entry_action": "ACCUMULATE_IN_BASE", "action": "ACCUMULATE_IN_BASE",
        "horizon": "MULTI_WEEK_SWING", "is_full_position_ready": False, "position_sizing_status": "NOT_EVALUATED",
    },
    "opportunity_decision_queue": {
        "research_priority_tier": "PRIORITY_NOW", "entry_action": "WAIT", "entry_relevant": True,
    },
}
_AI_RESPONSE_FIXTURE = {
    "ticker": "TEST_TICKER",
    "analysis_session": "2026-08-24T09:00:00+07:00",
    "synthesis_status": "PARTIAL_EVIDENCE",
    "thesis": "Tactical structure is base-building while the opportunity queue marks the ticker PRIORITY_NOW research priority.",
    "supporting_evidence": [
        "watchlist_tactical_entry_classifier reports entry_state=BASE_BUILDING, action=ACCUMULATE_IN_BASE.",
        "daily_opportunity_decision_queue reports research_priority_tier=PRIORITY_NOW.",
        "current_financial_momentum_context reports OFFICIAL_QUALIFIED evidence_tier with revenue_growth and earnings_growth EXPANDING.",
    ],
    "counter_thesis": "The opportunity queue's own entry_action is WAIT, retained history shows a DETERIORATION structural state, and net margin is deteriorating even as revenue expands.",
    "counter_evidence": [
        "current_opportunity_decision_context ticker_record.entry_action = WAIT.",
        "market_wide_historical_research_context structural_state.value = DETERIORATION.",
        "current_financial_momentum_context reports net_margin_change CONTRACTING alongside revenue_growth EXPANDING, making the fundamental picture MIXED.",
    ],
    "historical_context_summary": "As of session 2026-08-20, market_wide_historical_research_context reports a DETERIORATION structural state; descriptive only, not an entry action.",
    "valuation_context_summary": "As of price session 2026-08-24, P/B is READY (1.2) while EV/EBITDA is BLOCKED and EV/Sales is NOT_APPLICABLE; no ticker-wide valuation verdict is implied.",
    "market_context_summary": "As of session 2026-08-25, current_market_sector_leadership_context reports MIXED_BREADTH market-wide participation; descriptive context, not a trade signal.",
    "sector_context_summary": "The ticker's own sector_leadership_context is AVAILABLE with leadership_state=LEADING on observed participation; descriptive only, not a research-priority upgrade.",
    "relative_strength_context": [
        "market_relative_momentum reports the ticker in the TOP_QUINTILE momentum bucket.",
        "breadth_support_state=MARKET_AND_GROUP_BREADTH_SUPPORT: both market and sector breadth corroborate the ticker's own technical posture.",
    ],
    "catalyst_context": [
        "current_corporate_event_context reports a CONFIRMED_UPCOMING CASH_DIVIDEND event with an evidenced ex_date of 2026-08-28; a confirmed research catalyst, not an implied price direction.",
    ],
    "risk_context": [
        "market_wide_historical_research_context reports a DETERIORATION structural state as a descriptive risk factor.",
        "current_financial_momentum_context reports net_margin_change as a weakening dimension despite expanding revenue and earnings.",
        "current_research_risk_register reports a MATERIAL FINANCIAL_STRESS item sourced from current_financial_momentum_context's LOSS_MAKING_OR_STRESSED state.",
    ],
    "invalidation_conditions": [
        "watchlist_tactical_entry_classifier invalidation: close below the prior base low.",
    ],
    "unresolved_questions": [
        "market_wide_current_valuation reports EV/EBITDA as BLOCKED; unresolved whether it would corroborate P/B.",
        "current_research_risk_register reports valuation authority as limited (VALUATION_METRICS_BLOCKED); no authoritative cheapness or expense conclusion is available.",
    ],
    "authority_limitations": [
        "EV/EBITDA is BLOCKED and EV/Sales is NOT_APPLICABLE; neither is usable valuation evidence.",
    ],
    "upstream_decision_context": copy.deepcopy(_EXPECTED_UPSTREAM),
    "provenance_references": [
        "watchlist_tactical_entry_classifier",
        "daily_opportunity_decision_queue",
        "market_wide_historical_research_context",
        "market_wide_current_valuation.metrics.pb",
        "current_market_sector_leadership_context",
        "current_financial_momentum_context.components.revenue_growth",
        "current_financial_momentum_context.components.earnings_growth",
        "current_financial_momentum_context.components.net_margin_change",
        f"current_corporate_event_context.events.{_CORPORATE_EVENT_UPCOMING_ID}",
        f"current_research_risk_register.material_risks.{_RISK_REGISTER_MATERIAL_ID}",
        f"current_research_risk_register.data_authority_limitations.{_RISK_REGISTER_LIMITATION_ID}",
    ],
    "is_actionable": False,
}


class StructuredResearchSynthesisBoundaryTests(unittest.TestCase):
    # --- VALID BOUNDARY CASES ---
    def test_valid_full_context_accepted(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertEqual(resp, result["accepted_output"])
        self.assertEqual(_EXPECTED_UPSTREAM, result["derived_contract_metadata"]["expected_upstream_decision_context"])

    def test_deterministic_repeated_call(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        res1 = accept_structured_research_synthesis(ctx, resp)
        res2 = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual(res1, res2)

    def test_evidence_references_and_provenance_survive(self):
        """VALIDATION case: evidence references/provenance survive where supplied."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual(resp["provenance_references"], result["accepted_output"]["provenance_references"])
        result["accepted_output"]["provenance_references"].append("mutated")
        self.assertNotIn("mutated", resp["provenance_references"])

    # --- AI_MARKET_SECTOR_CONTEXT_SYNTHESIS_INTEGRATION_V1 TESTS ---

    def test_valid_market_context_passes(self):
        """1. valid market context passes."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        self.assertEqual("available", result["derived_contract_metadata"]["market_sector_context_status"])

    def test_valid_sector_leadership_passes(self):
        """2. valid sector leadership passes."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        self.assertEqual("LEADING", ctx["current_market_sector_leadership_context"]["ticker_context"]["sector_leadership_context"]["leadership_state"])
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])

    def test_ticker_relative_context_preserved(self):
        """3. ticker-relative context preserved (relative_strength_context survives verbatim)."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertEqual(resp["relative_strength_context"], result["accepted_output"]["relative_strength_context"])

    def test_market_data_limited_stays_limited(self):
        """4. market DATA_LIMITED stays a limitation, distinct from AVAILABLE -- never neutral/positive."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_market_sector_leadership_context"]["status"] = "data_limited"
        ctx["current_market_sector_leadership_context"]["market"]["current_breadth_state"] = "DATA_LIMITED"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["market_context_summary"] = "As of session 2026-08-25, market breadth is DATA_LIMITED (below the minimum observed cohort); this is a coverage limitation, not a neutral or positive signal."
        resp["authority_limitations"].append("Market breadth is DATA_LIMITED for this session.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertEqual("data_limited", result["derived_contract_metadata"]["market_sector_context_status"])
        self.assertNotEqual("available", result["derived_contract_metadata"]["market_sector_context_status"])

    def test_unknown_sector_stays_unknown(self):
        """5. unknown sector stays unknown -- never inferred by the AI from the ticker name."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_market_sector_leadership_context"]["ticker_context"]["sector_leadership_context"] = {
            "status": "UNAVAILABLE", "reason": "SECTOR_IDENTITY_UNKNOWN",
        }
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["sector_context_summary"] = "The ticker's sector identity is UNAVAILABLE (SECTOR_IDENTITY_UNKNOWN); no sector leadership claim can be made."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_missing_current_session_names_do_not_become_unchanged_or_zero(self):
        """6. missing current-session observations are coverage gaps, never unchanged/zero returns."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_market_sector_leadership_context"]["market"]["missing_current_session_count"] = 47
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["market_context_summary"] = "As of session 2026-08-25, 47 official-universe tickers have no current-session bar; this is an explicit coverage gap, not an unchanged or zero return, over the remaining MIXED_BREADTH participation."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_malformed_market_sector_sibling_fails_closed(self):
        """7. malformed context fails closed -- cannot be cited once malformed."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_market_sector_leadership_context"] = {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_market_sector_leadership_context_malformed"],
        }
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("rejected", result["status"])
        self.assertTrue(any(r.startswith("unknown_evidence_reference:") for r in result["reasons"]))
        self.assertEqual("malformed", result["derived_contract_metadata"]["market_sector_context_status"])

    def test_absent_market_sector_sibling_allows_partial_synthesis(self):
        """8. absent sibling allows a valid PARTIAL synthesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_market_sector_leadership_context"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_market_sector_leadership_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["market_context_summary"] = "current_market_sector_leadership_context is not supplied in this context package."
        resp["sector_context_summary"] = "current_market_sector_leadership_context is not supplied in this context package."
        resp["relative_strength_context"] = []
        resp["provenance_references"] = [r for r in resp["provenance_references"] if r != "current_market_sector_leadership_context"]
        resp["authority_limitations"].append("Current market/sector leadership context is unavailable for this ticker.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("market_sector_context_status", result["derived_contract_metadata"])

    def test_market_sector_provenance_reference_survives(self):
        """9. provenance reference to the new sibling survives where supplied."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertIn("current_market_sector_leadership_context", result["accepted_output"]["provenance_references"])
        self.assertIn("current_market_sector_leadership_context", result["derived_contract_metadata"]["known_evidence_refs"])

    def test_market_sector_evidence_cannot_change_research_priority(self):
        """10. market/sector context cannot change research_priority, even cited as justification."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["opportunity_decision_queue"]["research_priority_tier"] = "PRIORITY_NOW_UPGRADED"
        resp["thesis"] = resp["thesis"] + " Broad market and sector breadth support upgrading research priority."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_market_sector_evidence_cannot_change_entry_action(self):
        """11. market/sector context cannot change entry_action, even cited as justification."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["tactical_entry_classifier"]["entry_action"] = "BUY_ON_CONFIRMATION"
        resp["thesis"] = resp["thesis"] + " Strong sector leadership justifies the stronger entry action."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_market_sector_context_cannot_create_recommendation(self):
        """12. cannot create a BUY/SELL/HOLD recommendation from market/sector evidence."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["market_context_summary"] = resp["market_context_summary"] + " Broad breadth means we recommend BUY."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    def test_market_sector_context_cannot_create_numeric_probability(self):
        """13. cannot create a numeric probability/confidence from market/sector evidence."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["sector_context_summary"] = resp["sector_context_summary"] + " This gives an 85% probability of continued leadership."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_probability_or_expected_return_claim", result["reasons"])

    def test_no_opaque_combined_score_across_lanes(self):
        """14. no opaque combined score across market + sector + technical + valuation."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " Combined market, sector, and valuation score of 8.5/10."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_combined_score_claim", result["reasons"])

    def test_strong_ticker_weak_sector_supports_counter_thesis_without_action(self):
        """15. strong ticker + weak sector can support a counter-thesis without becoming an action."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_market_sector_leadership_context"]["ticker_context"]["sector_leadership_context"]["leadership_state"] = "WEAKENING"
        ctx["current_market_sector_leadership_context"]["ticker_context"]["breadth_support_state"] = "ISOLATED_OR_MIXED_PARTICIPATION"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["counter_thesis"] = (
            "The ticker's own technical structure is base-building, but its sector is currently WEAKENING and "
            "participation is ISOLATED_OR_MIXED, so the setup is relatively isolated rather than broadly confirmed."
        )
        resp["counter_evidence"] = resp["counter_evidence"] + [
            "current_market_sector_leadership_context reports sector_leadership_context.leadership_state=WEAKENING.",
            "current_market_sector_leadership_context reports breadth_support_state=ISOLATED_OR_MIXED_PARTICIPATION.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_existing_synthesis_without_market_sector_sibling_backward_compatible(self):
        """16. existing synthesis (built before this milestone, with no market/sector sibling
        at all) remains backward compatible -- identical to the absent-sibling PARTIAL case,
        proving nothing in the schema became newly mandatory for old-shape contexts."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_market_sector_leadership_context"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_market_sector_leadership_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["market_context_summary"] = "current_market_sector_leadership_context is not supplied in this context package."
        resp["sector_context_summary"] = "current_market_sector_leadership_context is not supplied in this context package."
        resp["relative_strength_context"] = []
        resp["provenance_references"] = [r for r in resp["provenance_references"] if r != "current_market_sector_leadership_context"]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    # --- AI_FINANCIAL_MOMENTUM_SYNTHESIS_INTEGRATION_V1 TESTS ---

    def test_valid_financial_context_passes(self):
        """1. valid financial context passes."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        self.assertEqual("available", result["derived_contract_metadata"]["financial_momentum_context_status"])

    def test_official_qualified_tier_preserved(self):
        """2. official-qualified tier preserved."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        self.assertEqual("OFFICIAL_QUALIFIED", ctx["current_financial_momentum_context"]["ticker_context"]["evidence_tier"])
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertIn("OFFICIAL_QUALIFIED", result["accepted_output"]["supporting_evidence"][2])

    def test_provider_research_tier_preserved(self):
        """3. provider-research tier preserved -- never described as official-qualified."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_financial_momentum_context"]["ticker_context"]["evidence_tier"] = "PROVIDER_RESEARCH"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["supporting_evidence"] = [
            "watchlist_tactical_entry_classifier reports entry_state=BASE_BUILDING, action=ACCUMULATE_IN_BASE.",
            "daily_opportunity_decision_queue reports research_priority_tier=PRIORITY_NOW.",
            "current_financial_momentum_context reports PROVIDER_RESEARCH evidence_tier with revenue_growth and earnings_growth EXPANDING.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertIn("PROVIDER_RESEARCH", result["accepted_output"]["supporting_evidence"][2])

    def test_broad_improvement_supports_thesis_without_action_upgrade(self):
        """4. BROAD_IMPROVEMENT can support thesis without an action upgrade."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        self.assertEqual("BROAD_IMPROVEMENT", ctx["current_financial_momentum_context"]["ticker_context"]["financial_momentum_state"])
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " Official evidence shows a BROAD_IMPROVEMENT financial momentum state."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertEqual("WAIT", result["accepted_output"]["upstream_decision_context"]["opportunity_decision_queue"]["entry_action"])

    def test_deteriorating_supports_counter_thesis(self):
        """5. DETERIORATING can support a counter-thesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_financial_momentum_context"]["ticker_context"]["financial_momentum_state"] = "DETERIORATING"
        ctx["current_financial_momentum_context"]["ticker_context"]["supporting_dimensions"] = []
        ctx["current_financial_momentum_context"]["ticker_context"]["weakening_dimensions"] = ["revenue_growth", "earnings_growth"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["counter_thesis"] = resp["counter_thesis"] + " current_financial_momentum_context also reports a DETERIORATING financial momentum state."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_revenue_up_margin_down_remains_mixed_evidence(self):
        """6. revenue up + margin down remains mixed evidence, not forced to one verdict."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        fm = ctx["current_financial_momentum_context"]["ticker_context"]
        self.assertIn("revenue_growth", fm["supporting_dimensions"])
        self.assertIn("net_margin_change", fm["weakening_dimensions"])
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        # Cited in supporting_evidence (revenue/earnings) AND counter_evidence/risk_context
        # (margin) simultaneously -- both survive, neither forces the other out.
        self.assertTrue(any("current_financial_momentum_context" in item for item in result["accepted_output"]["supporting_evidence"]))
        self.assertTrue(any("current_financial_momentum_context" in item for item in result["accepted_output"]["counter_evidence"]))
        self.assertTrue(any("current_financial_momentum_context" in item for item in result["accepted_output"]["risk_context"]))

    def test_loss_making_state_preserved(self):
        """7. negative/loss state preserved."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_financial_momentum_context"]["ticker_context"]["financial_momentum_state"] = "LOSS_MAKING_OR_STRESSED"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["counter_thesis"] = resp["counter_thesis"] + " current_financial_momentum_context reports LOSS_MAKING_OR_STRESSED."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_bank_industrial_metrics_remain_not_applicable(self):
        """8. bank industrial metrics remain NA."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        fm = ctx["current_financial_momentum_context"]["ticker_context"]
        fm["entity_class"] = "bank"
        fm["components"]["revenue_growth"] = {"status": "NOT_APPLICABLE", "direction": None}
        fm["components"]["net_margin_change"] = {"status": "NOT_APPLICABLE", "direction": None}
        fm["components"]["operating_cash_flow"] = {"status": "NOT_APPLICABLE", "direction": None}
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["provenance_references"] = [
            r for r in resp["provenance_references"]
            if r not in {"current_financial_momentum_context.components.revenue_growth", "current_financial_momentum_context.components.net_margin_change"}
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        known_refs = result["derived_contract_metadata"]["known_evidence_refs"]
        self.assertNotIn("current_financial_momentum_context.components.revenue_growth", known_refs)
        self.assertNotIn("current_financial_momentum_context.components.net_margin_change", known_refs)

    def test_missing_comparison_stays_insufficient_not_citable(self):
        """9. missing comparison stays insufficient/partial -- never silently citable as usable evidence."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        known_refs = result["derived_contract_metadata"]["known_evidence_refs"]
        self.assertNotIn("current_financial_momentum_context.components.operating_cash_flow", known_refs)
        self.assertIn("current_financial_momentum_context.components.revenue_growth", known_refs)

    def test_absent_financial_sibling_allows_partial_synthesis(self):
        """10. absent financial sibling allows a valid PARTIAL synthesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_financial_momentum_context"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_financial_momentum_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["supporting_evidence"] = resp["supporting_evidence"][:2]
        resp["counter_evidence"] = resp["counter_evidence"][:2]
        resp["risk_context"] = resp["risk_context"][:1]
        resp["provenance_references"] = [
            r for r in resp["provenance_references"] if not r.startswith("current_financial_momentum_context")
        ]
        resp["authority_limitations"].append("current_financial_momentum_context is not supplied for this ticker.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("financial_momentum_context_status", result["derived_contract_metadata"])

    def test_malformed_financial_sibling_cannot_be_cited(self):
        """11. malformed financial sibling cannot be cited."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_financial_momentum_context"] = {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_financial_momentum_context_malformed"],
        }
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("rejected", result["status"])
        self.assertTrue(any(r.startswith("unknown_evidence_reference:") for r in result["reasons"]))
        self.assertEqual("malformed", result["derived_contract_metadata"]["financial_momentum_context_status"])

    def test_financial_momentum_provenance_survives(self):
        """12. provenance survives."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertIn("current_financial_momentum_context.components.revenue_growth", result["accepted_output"]["provenance_references"])
        self.assertIn("current_financial_momentum_context.components.revenue_growth", result["derived_contract_metadata"]["known_evidence_refs"])

    def test_financial_context_cannot_change_research_priority(self):
        """13. financial context cannot change research_priority."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["opportunity_decision_queue"]["research_priority_tier"] = "PRIORITY_NOW_UPGRADED"
        resp["thesis"] = resp["thesis"] + " Broad official financial improvement supports upgrading priority."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_financial_context_cannot_change_strategy_eligibility(self):
        """14. cannot change strategy eligibility (no strategy-eligibility field exists to mint)."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["strategy_eligibility"] = "ELIGIBLE"
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:strategy_eligibility", result["reasons"])

    def test_financial_context_cannot_change_entry_action(self):
        """15. cannot change entry_action, even cited as justification."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["tactical_entry_classifier"]["entry_action"] = "BUY_ON_CONFIRMATION"
        resp["thesis"] = resp["thesis"] + " Official financial improvement justifies a stronger entry action."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_no_target_forecast_probability_recommendation_sizing_from_financial_context(self):
        """16. cannot produce target/forecast/probability/recommendation/sizing."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        for key, value in (
            ("target_price", 35000), ("probability", 0.8), ("recommendation", "BUY"), ("position_size", "5%"),
        ):
            with self.subTest(key=key):
                resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
                resp[key] = value
                result = accept_structured_research_synthesis(ctx, resp)
                self.assertEqual("rejected", result["status"])
                self.assertIn(f"prohibited_top_level_key:{key}", result["reasons"])
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " We forecast continued earnings growth next year."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_forecast_claim", result["reasons"])

    def test_financial_and_market_sessions_remain_distinct(self):
        """17. different financial/market sessions remain distinct."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_financial_momentum_context"]["session"] = "2026-08-10"
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        meta = result["derived_contract_metadata"]
        self.assertEqual("2026-08-10", meta["financial_momentum_context_session"])
        self.assertEqual("2026-08-25", meta["market_sector_context_session"])
        self.assertNotEqual(meta["financial_momentum_context_session"], meta["market_sector_context_session"])

    def test_financial_momentum_session_may_be_absent_and_still_accepted(self):
        """Financial momentum's own session may legitimately be None (Producer had no
        current_descriptive sibling at artifact-build time) -- distinct from malformed."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_financial_momentum_context"]["session"] = None
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("financial_momentum_context_session", result["derived_contract_metadata"])
        self.assertEqual("available", result["derived_contract_metadata"]["financial_momentum_context_status"])

    def test_existing_synthesis_without_financial_momentum_sibling_backward_compatible(self):
        """18. existing synthesis (built before this milestone, with no financial-momentum
        sibling at all) remains backward compatible."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_financial_momentum_context"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_financial_momentum_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["supporting_evidence"] = resp["supporting_evidence"][:2]
        resp["counter_evidence"] = resp["counter_evidence"][:2]
        resp["risk_context"] = resp["risk_context"][:1]
        resp["provenance_references"] = [
            r for r in resp["provenance_references"] if not r.startswith("current_financial_momentum_context")
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    # --- AI_CORPORATE_EVENT_SYNTHESIS_INTEGRATION_V1 TESTS ---

    def test_valid_corporate_event_context_passes(self):
        """1. valid confirmed-upcoming event passes."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        self.assertEqual("available", result["derived_contract_metadata"]["corporate_event_context_status"])

    def test_executed_event_status_preserved(self):
        """2. valid executed event passes, distinct from CONFIRMED_UPCOMING."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "EXECUTED"
        event["execution_date"] = "2026-06-20"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = [
            "current_corporate_event_context reports the CASH_DIVIDEND event as EXECUTED with execution_date=2026-06-20.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_planned_not_executed_supports_unresolved_questions(self):
        """3. planned-not-executed stays planned -- reported as an open question, not an
        upgraded action."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "PLANNED_NOT_EXECUTED"
        event["ex_date"] = None
        event["execution_date"] = None
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = []
        resp["unresolved_questions"] = list(resp["unresolved_questions"]) + [
            "current_corporate_event_context reports the CASH_DIVIDEND event as PLANNED_NOT_EXECUTED; whether it will be executed is not yet resolved.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_record_date_only_event_has_no_ex_date(self):
        """4. record-date-only event retains no ex-date."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "TEMPORAL_DETAILS_INCOMPLETE"
        event["ex_date"] = None
        event["temporal_completeness"] = "INCOMPLETE"
        self.assertIsNone(event["ex_date"])
        self.assertIsNotNone(event["record_date"])
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = [
            "current_corporate_event_context reports record_date=2026-09-03 for the CASH_DIVIDEND event; ex_date is not retained, so the event is TEMPORAL_DETAILS_INCOMPLETE.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_temporal_incomplete_event_limits_conclusion(self):
        """5. temporal-incomplete remains incomplete -- cited as a limiting factor."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "TEMPORAL_DETAILS_INCOMPLETE"
        event["ex_date"] = None
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = []
        resp["authority_limitations"] = list(resp["authority_limitations"]) + [
            "current_corporate_event_context's CASH_DIVIDEND event is temporally incomplete, so a stronger event interpretation is unavailable.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_conflicting_evidence_event_remains_conflict(self):
        """6. conflicting evidence remains conflict, not silently resolved."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "CONFLICTING_EVIDENCE"
        event["conflicts"] = ["ex_date"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = []
        resp["risk_context"] = list(resp["risk_context"]) + [
            "current_corporate_event_context reports CONFLICTING_EVIDENCE on the CASH_DIVIDEND event's ex_date; the conflict is unresolved, not decided by source preference.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_known_at_and_session_discipline_preserved(self):
        """7. known-at/as-of discipline preserved: the event's own known_at and this
        sibling's own research_session are tracked independently of every other session."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        self.assertEqual("2026-08-10", event["known_at"])
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        meta = result["derived_contract_metadata"]
        self.assertEqual("2026-08-21", meta["corporate_event_context_session"])
        self.assertEqual("2026-08-24", meta["valuation_context_session"])
        self.assertNotEqual(meta["corporate_event_context_session"], meta["valuation_context_session"])

    def test_corporate_event_provenance_survives(self):
        """9. exact event provenance survives."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        ref = f"current_corporate_event_context.events.{_CORPORATE_EVENT_UPCOMING_ID}"
        self.assertIn(ref, result["accepted_output"]["provenance_references"])
        self.assertIn(ref, result["derived_contract_metadata"]["known_evidence_refs"])

    def test_absent_corporate_event_sibling_allows_partial_synthesis(self):
        """10. absent event sibling allows a valid PARTIAL synthesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_corporate_event_context"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_corporate_event_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = []
        resp["provenance_references"] = [
            r for r in resp["provenance_references"] if not r.startswith("current_corporate_event_context")
        ]
        resp["authority_limitations"] = list(resp["authority_limitations"]) + [
            "current_corporate_event_context is not supplied for this ticker.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("corporate_event_context_status", result["derived_contract_metadata"])

    def test_malformed_corporate_event_sibling_cannot_be_cited(self):
        """11. malformed event sibling cannot be cited."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_corporate_event_context"] = {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_corporate_event_context_malformed"],
        }
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("rejected", result["status"])
        self.assertTrue(any(r.startswith("unknown_evidence_reference:") for r in result["reasons"]))
        self.assertEqual("malformed", result["derived_contract_metadata"]["corporate_event_context_status"])

    def test_event_evidence_supports_thesis(self):
        """12. event evidence can support thesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " A confirmed upcoming cash dividend with an evidenced ex_date is a qualified near-term catalyst."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_event_evidence_supports_counter_thesis_or_risk(self):
        """13. event evidence can support counter-thesis/risk -- a cancelled event removes
        a prior catalyst rather than only ever supporting the thesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "CANCELLED"
        event["ex_date"] = None
        ctx["current_corporate_event_context"]["ticker_context"]["confirmed_upcoming_count"] = 0
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = []
        resp["counter_thesis"] = resp["counter_thesis"] + " The previously retained cash-dividend event is now CANCELLED, removing a prior research catalyst."
        resp["risk_context"] = list(resp["risk_context"]) + [
            "current_corporate_event_context reports the cash-dividend event as CANCELLED.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_corporate_event_context_cannot_enable_event_driven(self):
        """14. event context cannot enable EVENT_DRIVEN eligibility."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " The confirmed dividend event confirms EVENT_DRIVEN eligibility."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_driven_eligibility_claim", result["reasons"])

    def test_corporate_event_cannot_change_research_priority(self):
        """15. cannot modify research_priority."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["opportunity_decision_queue"]["research_priority_tier"] = "PRIORITY_NOW_UPGRADED"
        resp["thesis"] = resp["thesis"] + " The confirmed dividend event supports upgrading research priority."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_corporate_event_cannot_change_entry_action(self):
        """16. cannot modify entry_action, even cited as justification."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["tactical_entry_classifier"]["entry_action"] = "BUY_ON_CONFIRMATION"
        resp["thesis"] = resp["thesis"] + " The confirmed dividend event justifies a stronger entry action."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_corporate_event_cannot_fabricate_price_impact(self):
        """17. cannot fabricate price impact (bullish/bearish/reaction language)."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " This dividend confirmation is bullish and should lift the share price."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_impact_claim", result["reasons"])

    def test_corporate_event_cannot_fabricate_probability(self):
        """18. cannot fabricate an event reaction probability."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " The event has a 70% probability of a positive reaction."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_probability_or_expected_return_claim", result["reasons"])

    def test_corporate_event_cannot_fabricate_recommendation_or_sizing(self):
        """19. cannot fabricate a recommendation or sizing figure from event evidence."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["thesis"] = resp["thesis"] + " Buy before the record date to capture the dividend."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])
        for key, value in (("recommendation", "BUY"), ("position_size", "5%")):
            with self.subTest(key=key):
                resp2 = copy.deepcopy(_AI_RESPONSE_FIXTURE)
                resp2[key] = value
                result2 = accept_structured_research_synthesis(ctx, resp2)
                self.assertEqual("rejected", result2["status"])
                self.assertIn(f"prohibited_top_level_key:{key}", result2["reasons"])

    def test_corporate_event_cannot_infer_missing_ex_date(self):
        """RESPONSE GUARDS: free-text synthesis cannot fabricate an inferred ex-date, e.g.
        the 'record_date minus one trading day' heuristic the authority boundary forbids."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "TEMPORAL_DETAILS_INCOMPLETE"
        event["ex_date"] = None
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = [
            "current_corporate_event_context reports record_date without ex_date; the ex-date is estimated as one trading day before the record date.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_inferred_ex_date_claim", result["reasons"])

    def test_corporate_event_cannot_invent_execution_status(self):
        """RESPONSE GUARDS: free-text synthesis cannot invent an execution status a
        PLANNED_NOT_EXECUTED record does not carry."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        event = ctx["current_corporate_event_context"]["ticker_context"]["events"][0]
        event["event_status"] = "PLANNED_NOT_EXECUTED"
        event["execution_date"] = None
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = [
            "The approved issuance should be treated as already executed given the strength of the other evidence.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_event_status_inference_claim", result["reasons"])

    def test_existing_synthesis_without_corporate_event_sibling_backward_compatible(self):
        """20. existing synthesis (built before this milestone, with no corporate-event
        sibling at all) remains backward compatible."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_corporate_event_context"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_corporate_event_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["catalyst_context"] = []
        resp["provenance_references"] = [
            r for r in resp["provenance_references"] if not r.startswith("current_corporate_event_context")
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    # --- AI_RISK_REGISTER_SYNTHESIS_INTEGRATION_V1 TESTS ---

    def test_valid_material_risk_survives(self):
        """1. valid material risk survives."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        self.assertEqual("MATERIAL_RISKS_ESTABLISHED", result["derived_contract_metadata"]["risk_register_status"])

    def test_valid_watch_risk_survives(self):
        """2. valid watch risk survives, distinct from a material risk."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        watch_id = "TEST_TICKER:PRICE_TECHNICAL:ELEVATED_HISTORICAL_VOLATILITY_REGIME"
        ctx["current_research_risk_register"]["risk_register"]["watch_risks"] = [{
            "risk_id": watch_id, "risk_domain": "PRICE_TECHNICAL", "risk_type": "ELEVATED_HISTORICAL_VOLATILITY_REGIME",
            "status": "WATCH", "severity_band": "WATCH", "source_context": "market_wide_historical_research_context:h1",
            "source_as_of": "2026-08-20", "observed_facts": {"volatility_regime": "HIGH"},
            "reason_codes": ["WITHIN_TICKER_VOLATILITY_REGIME_HIGH"], "authority_tier": "RETROSPECTIVE_DESCRIPTIVE",
        }]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["risk_context"] = list(resp["risk_context"]) + [
            f"current_research_risk_register reports a WATCH item ({watch_id}) for elevated historical volatility.",
        ]
        resp["provenance_references"] = list(resp["provenance_references"]) + [
            f"current_research_risk_register.watch_risks.{watch_id}",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_data_limitation_remains_limitation(self):
        """3. data limitation remains limitation, not folded into material/watch risk."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        register = ctx["current_research_risk_register"]["risk_register"]
        self.assertEqual(1, len(register["data_authority_limitations"]))
        self.assertEqual(0, len(register["watch_risks"]))
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        known_refs = result["derived_contract_metadata"]["known_evidence_refs"]
        self.assertIn(f"current_research_risk_register.data_authority_limitations.{_RISK_REGISTER_LIMITATION_ID}", known_refs)

    def test_conflict_remains_conflict(self):
        """4. conflict remains conflict -- citable specifically as an unresolved conflict."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        conflict_id = "TEST_TICKER:CORPORATE_EVENT:EVENT_EVIDENCE_CONFLICT"
        ctx["current_research_risk_register"]["risk_register"]["unresolved_conflicts"] = [{
            "risk_id": conflict_id, "risk_domain": "CORPORATE_EVENT", "risk_type": "EVENT_EVIDENCE_CONFLICT",
            "status": "UNRESOLVED_CONFLICT", "severity_band": None, "source_context": "current_corporate_event_context:e1",
            "source_as_of": "2026-08-21", "observed_facts": {"conflicting_count": 1},
            "reason_codes": ["CONFLICTING_EVIDENCE"], "authority_tier": "CONFLICTING_EVIDENCE",
        }]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["risk_context"] = list(resp["risk_context"]) + [
            f"current_research_risk_register reports an unresolved event-evidence conflict ({conflict_id}); the conflict is not resolved by source preference.",
        ]
        resp["provenance_references"] = list(resp["provenance_references"]) + [
            f"current_research_risk_register.unresolved_conflicts.{conflict_id}",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_no_material_risk_established_does_not_become_low_risk(self):
        """5. no-material-risk-established does not become a LOW_RISK/safe claim."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_research_risk_register"]["risk_register"]["material_risks"] = []
        ctx["current_research_risk_register"]["risk_register"]["risk_register_status"] = "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["risk_context"] = [
            "current_research_risk_register reports NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE, but the valuation-authority data limitation remains.",
        ]
        resp["provenance_references"] = [r for r in resp["provenance_references"] if not r.startswith("current_research_risk_register.material_risks")]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        # The prohibited framing is rejected even though the underlying fact is accurate.
        resp["risk_context"].append("The absence of an established material risk means the stock is low risk.")
        rejected = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", rejected["status"])
        self.assertIn("prohibited_low_risk_or_safe_claim", rejected["reasons"])

    def test_blocked_valuation_authority_does_not_become_expensive_or_cheap(self):
        """6. blocked valuation authority does not become an expensive/cheap claim."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["unresolved_questions"] = [
            "current_research_risk_register reports valuation authority as limited; the stock is undervalued relative to peers.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_valuation_overclaim", result["reasons"])

    def test_unknown_sector_does_not_become_economic_sector_risk(self):
        """7. unknown sector is a data/authority limitation, never reframed as an economic
        sector risk -- Producer classifies it as DATA_AUTHORITY, and the citation must
        match that classification rather than upgrading it to SECTOR_RELATIVE risk."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        sector_limit_id = "TEST_TICKER:DATA_AUTHORITY:SECTOR_CONTEXT_UNAVAILABLE"
        ctx["current_research_risk_register"]["risk_register"]["data_authority_limitations"].append({
            "risk_id": sector_limit_id, "risk_domain": "DATA_AUTHORITY", "risk_type": "SECTOR_CONTEXT_UNAVAILABLE",
            "status": "DATA_LIMITATION", "severity_band": "DATA_LIMITATION", "source_context": "current_market_sector_leadership_context:l1",
            "source_as_of": "2026-08-25", "observed_facts": {"sector_status": "UNAVAILABLE", "reason": "SECTOR_IDENTITY_UNKNOWN"},
            "reason_codes": ["SECTOR_IDENTITY_UNKNOWN"], "authority_tier": "CURRENT_SESSION_DESCRIPTIVE",
        })
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["unresolved_questions"] = list(resp["unresolved_questions"]) + [
            f"current_research_risk_register ({sector_limit_id}) reports the ticker's sector identity as unavailable; this is a data-authority limitation, not an economic sector risk.",
        ]
        resp["provenance_references"] = list(resp["provenance_references"]) + [
            f"current_research_risk_register.data_authority_limitations.{sector_limit_id}",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_risk_evidence_supports_counter_thesis(self):
        """8. risk evidence can support counter-thesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["counter_thesis"] = resp["counter_thesis"] + " current_research_risk_register also reports a MATERIAL FINANCIAL_STRESS item, reinforcing the caution."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_risk_evidence_supports_risk_context(self):
        """9. risk evidence can support risk_context (already exercised by the base
        fixture; this confirms the citation is independently traceable)."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        self.assertTrue(any("current_research_risk_register" in item for item in result["accepted_output"]["risk_context"]))

    def test_absent_risk_register_sibling_allows_partial_synthesis(self):
        """10. absent sibling allows a valid PARTIAL synthesis."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_research_risk_register"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_research_risk_register"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["risk_context"] = resp["risk_context"][:2]
        resp["unresolved_questions"] = resp["unresolved_questions"][:1]
        resp["provenance_references"] = [
            r for r in resp["provenance_references"] if not r.startswith("current_research_risk_register")
        ]
        resp["authority_limitations"] = list(resp["authority_limitations"]) + [
            "current_research_risk_register is not supplied for this ticker.",
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])
        self.assertNotIn("risk_register_status", result["derived_contract_metadata"])

    def test_malformed_risk_register_sibling_cannot_be_cited(self):
        """11. malformed sibling cannot be cited."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["current_research_risk_register"] = {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_research_risk_register_malformed"],
        }
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("rejected", result["status"])
        self.assertTrue(any(r.startswith("unknown_evidence_reference:") for r in result["reasons"]))
        self.assertEqual("malformed", result["derived_contract_metadata"]["risk_register_status"])

    def test_risk_item_provenance_survives(self):
        """12. item provenance survives."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        material_ref = f"current_research_risk_register.material_risks.{_RISK_REGISTER_MATERIAL_ID}"
        limitation_ref = f"current_research_risk_register.data_authority_limitations.{_RISK_REGISTER_LIMITATION_ID}"
        self.assertIn(material_ref, result["accepted_output"]["provenance_references"])
        self.assertIn(material_ref, result["derived_contract_metadata"]["known_evidence_refs"])
        self.assertIn(limitation_ref, result["derived_contract_metadata"]["known_evidence_refs"])

    def test_risk_register_source_sessions_remain_independent(self):
        """13. source sessions remain independent -- the register's own five source
        as-of identities are tracked distinctly from each other and from every other
        sibling's session."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        sessions = result["derived_contract_metadata"]["risk_register_source_sessions"]
        self.assertEqual("2026-08-20", sessions["historical"])
        self.assertEqual("2026-08-24", sessions["financial"])
        self.assertEqual("2026-08-24", sessions["valuation"])
        self.assertEqual("2026-08-21", sessions["event"])
        self.assertNotEqual(sessions["historical"], sessions["event"])

    def test_risk_register_cannot_alter_strategy_eligibility(self):
        """14. risk register cannot alter strategy eligibility (no strategy-eligibility
        field exists to mint)."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["strategy_eligibility"] = "NOT_ELIGIBLE"
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_top_level_key:strategy_eligibility", result["reasons"])

    def test_risk_register_cannot_alter_research_priority(self):
        """15. cannot alter research_priority, even cited as justification."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["opportunity_decision_queue"]["research_priority_tier"] = "DEPRIORITIZED"
        resp["counter_thesis"] = resp["counter_thesis"] + " The material financial-stress risk justifies deprioritizing research."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_risk_register_cannot_alter_entry_action(self):
        """16. cannot alter entry_action, and cannot claim to override it either."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["tactical_entry_classifier"]["entry_action"] = "AVOID"
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])
        # The prose framing "overrides" the deterministic action is independently rejected,
        # even without touching upstream_decision_context itself.
        resp2 = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp2["counter_thesis"] = resp2["counter_thesis"] + " The risk register overrides ACCUMULATE_IN_BASE to WAIT."
        result2 = accept_structured_research_synthesis(ctx, resp2)
        self.assertEqual("rejected", result2["status"])
        self.assertIn("prohibited_risk_override_claim", result2["reasons"])

    def test_risk_register_cannot_generate_risk_score(self):
        """17. cannot generate a numeric/global risk score."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["risk_context"].append("Risk score is 7/10.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_risk_score_claim", result["reasons"])

    def test_risk_register_cannot_generate_probability_expected_loss_or_var(self):
        """18. cannot generate probability/expected loss/VaR."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        for phrase, reason in (
            ("These risks imply a 65% downside probability.", "prohibited_risk_quantification_claim"),
            ("The expected loss from this position is material.", "prohibited_risk_quantification_claim"),
            ("Value at risk is elevated given the financial stress.", "prohibited_risk_quantification_claim"),
        ):
            with self.subTest(phrase=phrase):
                resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
                resp["risk_context"].append(phrase)
                result = accept_structured_research_synthesis(ctx, resp)
                self.assertEqual("rejected", result["status"])
                self.assertIn(reason, result["reasons"])

    def test_risk_register_cannot_generate_position_sizing_or_participation(self):
        """19. cannot generate position sizing/participation."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["counter_thesis"] = resp["counter_thesis"] + " Risk register means position size should be reduced to 3%."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_risk_sizing_inference_claim", result["reasons"])

    def test_existing_synthesis_without_risk_register_sibling_backward_compatible(self):
        """20. old synthesis without risk sibling remains backward compatible."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["current_research_risk_register"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "current_research_risk_register"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["risk_context"] = resp["risk_context"][:2]
        resp["unresolved_questions"] = resp["unresolved_questions"][:1]
        resp["provenance_references"] = [
            r for r in resp["provenance_references"] if not r.startswith("current_research_risk_register")
        ]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    # --- VALIDATION #1: upstream preserved, WAIT cannot become BUY ---
    def test_upstream_decision_context_preserved(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["opportunity_decision_queue"]["entry_action"] = "BUY"
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_upstream_tactical_entry_action_cannot_be_changed(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["upstream_decision_context"]["tactical_entry_classifier"]["entry_action"] = "AVOID"
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])

    def test_no_upstream_lanes_present_requires_empty_upstream_decision_context(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["watchlist_tactical_entry_classifier"]
        del ctx["current_opportunity_decision_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["provenance_references"] = ["market_wide_historical_research_context", "market_wide_current_valuation.metrics.pb"]
        # AI still claims the (now absent) upstream fields -- must be rejected.
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("upstream_decision_context_mismatch", result["reasons"])
        # Correcting to the true empty upstream is accepted.
        resp["upstream_decision_context"] = {}
        resp["thesis"] = "Historical and valuation context are the only qualified evidence available."
        resp["supporting_evidence"] = ["market_wide_current_valuation reports P/B as READY."]
        resp["counter_thesis"] = "The retained history shows a DETERIORATION structural state."
        resp["counter_evidence"] = ["market_wide_historical_research_context structural_state.value = DETERIORATION."]
        result2 = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result2["status"])
        self.assertEqual({}, result2["derived_contract_metadata"]["expected_upstream_decision_context"])

    # --- VALIDATION #2: counter-thesis required ---
    def test_counter_thesis_required(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        del resp["counter_thesis"]
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("missing_field:counter_thesis", result["reasons"])

    # --- VALIDATION #3: historical structural_state cannot become action ---
    def test_historical_structural_state_cannot_become_action(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["historical_context_summary"] = "Given the DETERIORATION structural state, we recommend SELL."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_recommendation_or_action_claim", result["reasons"])

    # --- VALIDATION #4: RESEARCH_USABLE valuation stays research-only ---
    def test_research_usable_valuation_metric_accepted_when_described_honestly(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["market_wide_current_valuation"]["metrics"]["pb"]["status"] = "RESEARCH_USABLE"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["valuation_context_summary"] = "P/B is RESEARCH_USABLE (research-only, not authoritative valuation)."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    def test_research_usable_valuation_cannot_become_cheapness_verdict(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["market_wide_current_valuation"]["metrics"]["pb"]["status"] = "RESEARCH_USABLE"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["valuation_context_summary"] = "P/B shows the stock is undervalued relative to peers."
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_valuation_overclaim", result["reasons"])

    # --- VALIDATION #6: READY remains READY if supplied (not silently merged with RESEARCH_USABLE) ---
    def test_ready_valuation_metric_remains_ready_and_citable(self):
        """A READY metric must stay independently citable and honestly describable as
        READY -- distinct from RESEARCH_USABLE, not silently downgraded or merged."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        self.assertEqual("READY", ctx["market_wide_current_valuation"]["metrics"]["pb"]["status"])
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        self.assertIn("market_wide_current_valuation.metrics.pb", result["derived_contract_metadata"]["known_evidence_refs"])
        # A READY metric overclaimed as a cheapness verdict is rejected exactly like a
        # RESEARCH_USABLE one -- READY status does not grant extra authority either.
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["valuation_context_summary"] = "P/B is READY and the stock is undervalued relative to peers."
        overclaim_result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", overclaim_result["status"])
        self.assertIn("prohibited_valuation_overclaim", overclaim_result["reasons"])

    # --- VALIDATION #5 / #6: BLOCKED / NOT_APPLICABLE stay distinct and non-blocking ---
    def test_blocked_valuation_metric_not_citable_but_does_not_block_synthesis(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        known_refs = result["derived_contract_metadata"]["known_evidence_refs"]
        self.assertNotIn("market_wide_current_valuation.metrics.ev_ebitda", known_refs)
        self.assertIn("market_wide_current_valuation.metrics.pb", known_refs)

    def test_not_applicable_valuation_metric_remains_na_and_non_blocking(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        known_refs = result["derived_contract_metadata"]["known_evidence_refs"]
        self.assertNotIn("market_wide_current_valuation.metrics.ev_sales", known_refs)

    # --- VALIDATION #7: absent historical context still allows a partial synthesis ---
    def test_absent_historical_context_allows_partial_synthesis(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["market_wide_historical_research_context"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "market_wide_historical_research_context"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["historical_context_summary"] = "market_wide_historical_research_context is not supplied in this context package."
        resp["counter_thesis"] = "The opportunity queue's own entry_action is WAIT despite PRIORITY_NOW research priority."
        resp["counter_evidence"] = ["current_opportunity_decision_context ticker_record.entry_action = WAIT."]
        resp["risk_context"] = []
        resp["provenance_references"] = ["watchlist_tactical_entry_classifier", "daily_opportunity_decision_queue", "market_wide_current_valuation.metrics.pb"]
        resp["authority_limitations"].append("Historical retrospective context is unavailable for this ticker.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    # --- VALIDATION #8: absent valuation context still allows a partial synthesis ---
    def test_absent_valuation_context_allows_partial_synthesis(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        del ctx["market_wide_current_valuation"]
        ctx["provenance"] = [p for p in ctx["provenance"] if p["source_dataset"] != "market_wide_current_valuation"]
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["valuation_context_summary"] = "market_wide_current_valuation is not supplied in this context package."
        resp["provenance_references"] = ["watchlist_tactical_entry_classifier", "daily_opportunity_decision_queue", "market_wide_historical_research_context"]
        resp["authority_limitations"].append("Current valuation context is unavailable for this ticker.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    # --- VALIDATION #9: malformed supplied sibling fails closed ---
    def test_malformed_historical_sibling_cannot_be_cited(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["market_wide_historical_research_context"] = {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["market_wide_historical_research_context_malformed"],
        }
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        # Still cites the malformed section as if it were usable evidence.
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertTrue(any(r.startswith("unknown_evidence_reference:") for r in result["reasons"]))
        self.assertEqual("malformed", result["derived_contract_metadata"]["historical_context_status"])

    def test_malformed_historical_sibling_not_cited_still_allows_synthesis(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["market_wide_historical_research_context"] = {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["market_wide_historical_research_context_malformed"],
        }
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["historical_context_summary"] = "market_wide_historical_research_context is malformed and cannot be used as evidence."
        resp["counter_thesis"] = "The opportunity queue's own entry_action is WAIT despite PRIORITY_NOW research priority."
        resp["counter_evidence"] = ["current_opportunity_decision_context ticker_record.entry_action = WAIT."]
        resp["risk_context"] = []
        resp["provenance_references"] = ["watchlist_tactical_entry_classifier", "daily_opportunity_decision_queue", "market_wide_current_valuation.metrics.pb"]
        resp["authority_limitations"].append("Historical retrospective context is malformed and unavailable.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("accepted", result["status"])

    # --- VALIDATION #10: no invented target_price / probability / expected_return / sizing / recommendation ---
    def test_no_invented_authority_fields_accepted_via_boundary(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        for key, value in (
            ("target_price", 35000),
            ("probability", 0.8),
            ("expected_return", 0.15),
            ("position_size", "5%"),
            ("recommendation", "BUY"),
        ):
            with self.subTest(key=key):
                resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
                resp[key] = value
                result = accept_structured_research_synthesis(ctx, resp)
                self.assertEqual("rejected", result["status"])
                self.assertIn(f"prohibited_top_level_key:{key}", result["reasons"])

    # --- VALIDATION #11: separate sibling sessions remain distinct ---
    def test_separate_sibling_sessions_remain_distinct(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        result = accept_structured_research_synthesis(ctx, copy.deepcopy(_AI_RESPONSE_FIXTURE))
        self.assertEqual("accepted", result["status"])
        meta = result["derived_contract_metadata"]
        self.assertEqual("2026-08-20", meta["historical_context_session"])
        self.assertEqual("2026-08-24", meta["valuation_context_session"])
        self.assertNotEqual(meta["historical_context_session"], meta["valuation_context_session"])

    def test_capacity_or_participation_claim_rejected_through_boundary(self):
        """This contract consumes no liquidity/traded-value lane -- confirms the
        currently-restricted ADTV20_MATCHED_VALUE Producer fact (position sizing /
        participation / capacity all blocked) cannot leak into the narrative even
        though this milestone never integrates that lane at all."""
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["risk_context"].append("The stock has strong liquidity participation capacity.")
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("prohibited_capacity_or_participation_claim", result["reasons"])

    # --- VALIDATION #13: backward compatibility with the existing context builder ---
    def test_build_ticker_context_has_no_coupling_to_new_synthesis_module(self):
        """A context package built without this milestone must be unaffected by it:
        build_ticker_context.py is never imported by, or made to import, the new
        synthesis modules -- the AI synthesis stays a fully decoupled, optional
        validation contract, same architectural role as multi_angle_synthesis."""
        import builders.build_ticker_context as btc
        source = inspect.getsource(btc)
        self.assertNotIn("structured_research_synthesis", source)

    # --- MECHANICAL / FAIL-CLOSED BOUNDARY CASES ---
    def test_malformed_ticker_context_type_rejected(self):
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        result = accept_structured_research_synthesis("not_a_mapping", resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_context_invalid_type", result["reasons"])

    def test_malformed_sibling_shape_rejected(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        ctx["watchlist_tactical_entry_classifier"] = "not_a_mapping"
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_context_malformed:watchlist_tactical_entry_classifier", result["reasons"])

    def test_ticker_mismatch_between_response_and_context_rejected(self):
        ctx = copy.deepcopy(_TICKER_CONTEXT_FIXTURE)
        resp = copy.deepcopy(_AI_RESPONSE_FIXTURE)
        resp["ticker"] = "OTHER_TICKER"
        result = accept_structured_research_synthesis(ctx, resp)
        self.assertEqual("rejected", result["status"])
        self.assertIn("ticker_mismatch", result["reasons"])


if __name__ == "__main__":
    unittest.main()
