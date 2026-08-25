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
_PROVENANCE_FIXTURE = [
    {"source_dataset": "historical_fundamental_brief"},
    {"source_dataset": "market_wide_historical_research_context"},
    {"source_dataset": "market_wide_current_valuation"},
    {"source_dataset": "watchlist_tactical_entry_classifier"},
    {"source_dataset": "daily_opportunity_decision_queue"},
    {"source_dataset": "current_market_sector_leadership_context"},
    {"source_dataset": "current_financial_momentum_context"},
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
    "catalyst_context": [],
    "risk_context": [
        "market_wide_historical_research_context reports a DETERIORATION structural state as a descriptive risk factor.",
        "current_financial_momentum_context reports net_margin_change as a weakening dimension despite expanding revenue and earnings.",
    ],
    "invalidation_conditions": [
        "watchlist_tactical_entry_classifier invalidation: close below the prior base low.",
    ],
    "unresolved_questions": [
        "market_wide_current_valuation reports EV/EBITDA as BLOCKED; unresolved whether it would corroborate P/B.",
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
