"""Focused unit tests for the current_research_decision_packet Consumer pass-through.

Covers the AI_CURRENT_RESEARCH_DECISION_PACKET_INTEGRATION_V1 milestone's pass-through
half: opt-in absence, whole-packet fail-closed malformed handling, per-component local
fail-closed handling (a malformed component cannot destroy an unrelated valid one), and
exact preservation of packet identity, component manifest, current decision context, and
authority boundary. Shapes match stock-core-private's current_research_decision_packet.py
and export_ai_bundle.py's attach_current_research_decision_packet (pinned schema commit
457f39d, verified via `git show`, 2026-08-25).
"""

from __future__ import annotations

import copy
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.build_ticker_context import (
    apply_bundle_current_research_decision_packet_contract,
    current_research_decision_packet_contract,
)

TICKER = "TEST_TICKER"

_AUTHORITY_BOUNDARY = {
    "is_actionable": False, "no_global_authority_score": True, "upstream_decisions_passthrough_only": True,
    "source_sessions_preserved_independently": True,
    "no_recommendation_probability_expected_return_target_or_sizing": True,
    "raw_as_traded": "NOT_PROMOTED", "pit": "BLOCKED",
}
_FORBIDDEN_USES = ["recommendation", "probability", "expected_return", "target_price", "position_size", "sizing"]
_RISK_REGISTER_FORBIDDEN_USES = [
    "numeric_risk_score", "risk_adjusted_return", "expected_loss", "VaR", "probability",
    "position_size", "participation_cap", "recommendation", "strategy_eligibility",
    "research_priority", "entry_action", "VALUE", "daily_decision_queue",
]


def _manifest_present(name: str, identity: str, as_of: str | None = None) -> dict:
    return {
        "component_name": name, "status": "PRESENT",
        "source_artifact_identity": identity, "source_content_hash": identity.rsplit(":", 1)[-1],
        "source_as_of": as_of, "authority_use_status": "PASSTHROUGH_ONLY",
    }


def _manifest_absent(name: str) -> dict:
    return {
        "component_name": name, "status": "ABSENT",
        "source_artifact_identity": None, "source_as_of": None,
        "authority_use_status": "OPTIONAL_NOT_SUPPLIED",
    }


def _manifest_malformed(name: str, identity: str | None = None) -> dict:
    return {
        "component_name": name, "status": "MALFORMED",
        "source_artifact_identity": identity, "source_as_of": None,
        "authority_use_status": "FAIL_CLOSED_LOCALLY",
    }


def _risk_item(risk_id: str, status: str) -> dict:
    return {
        "risk_id": risk_id, "risk_domain": "FINANCIAL", "risk_type": "FINANCIAL_STRESS", "status": status,
        "severity_band": "MATERIAL" if status == "ESTABLISHED" else None,
        "source_context": "current_financial_momentum_context:f1", "source_as_of": "2026-08-24",
        "observed_facts": {"financial_momentum_state": "LOSS_MAKING_OR_STRESSED"},
        "reason_codes": ["LOSS_MAKING_OR_STRESSED_STATE"], "authority_tier": "OFFICIAL_QUALIFIED",
        "allowed_uses": ["CURRENT_RESEARCH_CONTEXT"], "prohibited_uses": list(_RISK_REGISTER_FORBIDDEN_USES),
    }


_RISK_REGISTER_COMPONENT = {
    "ticker": TICKER,
    "material_risks": [_risk_item(f"{TICKER}:financial:stress", "ESTABLISHED")],
    "watch_risks": [],
    "data_authority_limitations": [],
    "unresolved_conflicts": [],
    "risk_register_status": "MATERIAL_RISKS_ESTABLISHED",
}
_FINANCIAL_MOMENTUM_COMPONENT = {
    "as_of_financial_period": "2026Q2",
    "financial_momentum_state": "BROAD_IMPROVEMENT",
    "coverage_status": "FULL",
    "evidence_tier": "OFFICIAL_QUALIFIED",
    "components": {
        "revenue_growth": {"status": "AVAILABLE", "periods": ["2026Q2"], "warnings": [], "current_value": 0.12, "direction": "EXPANDING"},
        "operating_cash_flow": {"status": "BLOCKED", "periods": [], "warnings": ["blocked"], "current_value": None, "direction": None},
    },
    "blockers": [],
    "warnings": [],
}
_MARKET_SECTOR_COMPONENT = {
    "market": {"current_breadth_state": "MIXED_BREADTH"},
    "ticker_context": {
        "ticker": TICKER, "status": "AVAILABLE",
        "breadth_support_state": "MARKET_AND_GROUP_BREADTH_SUPPORT",
    },
}
_CORPORATE_EVENT_COMPONENT = {
    "qualified_event_count": 1, "planned_unresolved_count": 0, "temporal_incomplete_count": 0,
    "data_limited_count": 0, "conflicting_count": 0, "research_session": "2026-08-21",
    "events": [{
        "event_id": "current_corporate_event:test-upcoming-dividend", "event_status": "CONFIRMED_UPCOMING",
        "event_type": "CASH_DIVIDEND", "known_at": "2026-08-10", "published_at": "2026-08-10",
        "ex_date": "2026-08-28", "effective_date": None, "execution_date": None,
        "temporal_completeness": "COMPLETE", "evidence_tier": "OFFICIAL_EXCHANGE",
    }],
}
_VALUATION_COMPONENT = {
    "valuation_session": "2026-08-24",
    "share_basis_status": "CURRENT",
    "metrics": {
        "pb": {"status": "READY", "blocked_reasons": [], "price_session": "2026-08-24", "authority_tier": "CURRENT_RESEARCH_ONLY"},
        "ev_ebitda": {"status": "BLOCKED", "blocked_reasons": ["missing_ebitda"], "price_session": "2026-08-24", "authority_tier": "CURRENT_RESEARCH_ONLY"},
    },
    "value_strategy": None,
}
_HISTORICAL_COMPONENT = {
    "as_of_session": "2026-08-20",
    "context_status": "AVAILABLE",
    "structural_state": {"status": "AVAILABLE", "value": "DETERIORATION"},
    "volatility_regime": {"status": "AVAILABLE"},
    "momentum": {"status": "AVAILABLE"},
    "drawdown": {"status": "AVAILABLE"},
    "authority_boundary": {"PIT": "BLOCKED", "RAW_AS_TRADED": "NOT_PROMOTED"},
}
_SCENARIO_CASE = {"case_id": "c1", "probability_status": "UNKNOWN_UNCALIBRATED", "case_status": "CONDITIONAL"}
_SCENARIO_COMPONENT = {
    "scenario_disposition": "SCENARIO_READY",
    "current_state": "UPTREND_CONFIRMED",
    "bear_case": copy.deepcopy(_SCENARIO_CASE),
    "base_case": copy.deepcopy(_SCENARIO_CASE),
    "bull_case": copy.deepcopy(_SCENARIO_CASE),
    "authority_limitations": [],
}
_MANIFEST = {
    "scenario": _manifest_present("scenario", "current_evidence_bound_scenario:s1", "2026-08-25"),
    "risk_register": _manifest_present("risk_register", "current_research_risk_register:r1"),
    "market_sector": _manifest_present("market_sector", "current_market_sector_leadership_context:m1", "2026-08-25"),
    "financial_momentum": _manifest_present("financial_momentum", "current_financial_momentum_context:f1", "2026-08-24"),
    "corporate_event": _manifest_present("corporate_event", "current_corporate_event_context:e1", "2026-08-21"),
    "valuation": _manifest_present("valuation", "market_wide_current_valuation:v1", "2026-08-21"),
    "historical": _manifest_present("historical", "market_wide_historical_research_context:h1", "2026-08-24"),
}
_DECISION_CONTEXT = {
    "priority_tier": "PRIORITY_NOW", "entry_action": "WAIT", "eligible_strategies": ["TREND_MOMENTUM"],
    "lane_priority": {"TREND_MOMENTUM": "PRIORITY_NOW"}, "tactical_state": "UPTREND_CONFIRMED",
    "scenario_status": "SCENARIO_READY", "blocking_reasons": [], "invalidation_or_context_warnings": [],
    "source_input_identities": {"official_universe": "x1"},
}
_PACKET_RECORD = {
    "ticker": TICKER,
    "packet_status": "COMPLETE_FOR_AVAILABLE_COMPONENTS",
    "current_decision_context": copy.deepcopy(_DECISION_CONTEXT),
    "components": {
        "scenario_context": copy.deepcopy(_SCENARIO_COMPONENT),
        "risk_register": copy.deepcopy(_RISK_REGISTER_COMPONENT),
        "market_sector_context": copy.deepcopy(_MARKET_SECTOR_COMPONENT),
        "financial_momentum_context": copy.deepcopy(_FINANCIAL_MOMENTUM_COMPONENT),
        "corporate_event_context": copy.deepcopy(_CORPORATE_EVENT_COMPONENT),
        "valuation_context": copy.deepcopy(_VALUATION_COMPONENT),
        "historical_research_context": copy.deepcopy(_HISTORICAL_COMPONENT),
    },
    "unresolved_components": [],
    "authority_limitations": [],
    "warnings": ["Component absence does not revise upstream decision state."],
    "allowed_uses": ["AI_RESEARCH_NARRATIVE", "HUMAN_REVIEW", "AUDIT_REPLAY"],
    "prohibited_uses": list(_FORBIDDEN_USES),
    "is_actionable": False,
}
_PACKET_RAW = {
    "ticker": TICKER,
    "source_artifact_identity": "current_research_decision_packet:abc123",
    "packet": copy.deepcopy(_PACKET_RECORD),
    "component_manifest": copy.deepcopy(_MANIFEST),
    "authority_boundary": copy.deepcopy(_AUTHORITY_BOUNDARY),
    "is_actionable": False,
}


def _bundle(raw) -> dict:
    return {"tickers": {TICKER: {"current_research_decision_packet": raw}}}


class CurrentResearchDecisionPacketPassThroughTests(unittest.TestCase):
    # --- Opt-in absence ---
    def test_absent_field_returns_none(self):
        self.assertIsNone(current_research_decision_packet_contract({"tickers": {TICKER: {}}}, TICKER))

    def test_absent_bundle_returns_none(self):
        self.assertIsNone(current_research_decision_packet_contract(None, TICKER))

    def test_ticker_outside_bundle_returns_none(self):
        self.assertIsNone(current_research_decision_packet_contract(_bundle(_PACKET_RAW), "OTHER_TICKER"))

    # --- Valid full packet: exact pass-through ---
    def test_valid_full_packet_passes_through_unchanged(self):
        result = current_research_decision_packet_contract(_bundle(_PACKET_RAW), TICKER)
        self.assertEqual(_PACKET_RAW, result)

    def test_deterministic_repeated_call(self):
        bundle = _bundle(_PACKET_RAW)
        first = current_research_decision_packet_contract(bundle, TICKER)
        second = current_research_decision_packet_contract(bundle, TICKER)
        self.assertEqual(first, second)

    def test_result_is_a_deep_copy_not_aliased(self):
        raw = copy.deepcopy(_PACKET_RAW)
        bundle = _bundle(raw)
        result = current_research_decision_packet_contract(bundle, TICKER)
        result["packet"]["components"]["risk_register"]["risk_register_status"] = "TAMPERED"
        self.assertEqual("MATERIAL_RISKS_ESTABLISHED", raw["packet"]["components"]["risk_register"]["risk_register_status"])

    def test_packet_identity_prefix_preserved(self):
        result = current_research_decision_packet_contract(_bundle(_PACKET_RAW), TICKER)
        self.assertTrue(result["source_artifact_identity"].startswith("current_research_decision_packet:"))

    def test_component_manifest_preserved_exactly(self):
        result = current_research_decision_packet_contract(_bundle(_PACKET_RAW), TICKER)
        self.assertEqual(_MANIFEST, result["component_manifest"])

    def test_authority_boundary_preserved_exactly(self):
        result = current_research_decision_packet_contract(_bundle(_PACKET_RAW), TICKER)
        self.assertEqual(_AUTHORITY_BOUNDARY, result["authority_boundary"])

    def test_current_decision_context_preserved_verbatim(self):
        result = current_research_decision_packet_contract(_bundle(_PACKET_RAW), TICKER)
        self.assertEqual(_DECISION_CONTEXT, result["packet"]["current_decision_context"])

    def test_allowed_and_prohibited_uses_preserved(self):
        result = current_research_decision_packet_contract(_bundle(_PACKET_RAW), TICKER)
        self.assertEqual(["AI_RESEARCH_NARRATIVE", "HUMAN_REVIEW", "AUDIT_REPLAY"], result["packet"]["allowed_uses"])
        self.assertEqual(set(_FORBIDDEN_USES), set(result["packet"]["prohibited_uses"]))

    # --- Whole-packet fail-closed (envelope-level tamper) ---
    def test_ticker_mismatch_in_envelope_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["ticker"] = "WRONG_TICKER"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])
        self.assertNotIn("packet", result)

    def test_ticker_mismatch_in_record_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["ticker"] = "WRONG_TICKER"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_is_actionable_true_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["is_actionable"] = True
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_wrong_identity_prefix_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["source_artifact_identity"] = "some_other_artifact:abc123"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_missing_manifest_component_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        del raw["component_manifest"]["historical"]
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_extra_manifest_component_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["component_manifest"]["unexpected"] = _manifest_absent("unexpected")
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_tampered_authority_boundary_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["authority_boundary"]["is_actionable"] = True
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_prohibited_uses_missing_a_forbidden_entry_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["prohibited_uses"] = ["recommendation"]
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_components_entry_without_present_manifest_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["component_manifest"]["scenario"] = _manifest_absent("scenario")
        # components.scenario_context still populated even though manifest now says ABSENT
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    def test_authority_limitations_inconsistent_with_unresolved_is_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["authority_limitations"] = ["scenario_UNAVAILABLE_OR_MALFORMED"]
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["status"])

    # --- ABSENT component (opt-in, not malformed) ---
    def test_absent_component_is_not_treated_as_malformed(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["component_manifest"]["historical"] = _manifest_absent("historical")
        del raw["packet"]["components"]["historical_research_context"]
        raw["packet"]["unresolved_components"] = ["historical"]
        raw["packet"]["authority_limitations"] = ["historical_UNAVAILABLE_OR_MALFORMED"]
        raw["packet"]["packet_status"] = "PARTIAL"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("PARTIAL", result["packet"]["packet_status"])
        self.assertNotIn("historical_research_context", result["packet"]["components"])
        self.assertEqual(["historical"], result["packet"]["unresolved_components"])
        self.assertEqual("ABSENT", result["component_manifest"]["historical"]["status"])
        # Every other component remains fully valid and untouched.
        self.assertEqual(_RISK_REGISTER_COMPONENT, result["packet"]["components"]["risk_register"])

    # --- MALFORMED component at the manifest level (Producer's own finding) ---
    def test_manifest_malformed_component_has_no_row_and_is_unresolved(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["component_manifest"]["valuation"] = _manifest_malformed("valuation", "market_wide_current_valuation:bad")
        del raw["packet"]["components"]["valuation_context"]
        raw["packet"]["unresolved_components"] = ["valuation"]
        raw["packet"]["authority_limitations"] = ["valuation_UNAVAILABLE_OR_MALFORMED"]
        raw["packet"]["packet_status"] = "PARTIAL"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertNotEqual("malformed", result.get("status"))
        self.assertNotIn("valuation_context", result["packet"]["components"])
        self.assertEqual("MALFORMED", result["component_manifest"]["valuation"]["status"])

    # --- Local, per-component fail-closed (Consumer's own structural check) ---
    def test_one_locally_malformed_component_does_not_erase_others(self):
        raw = copy.deepcopy(_PACKET_RAW)
        # risk_register_status inconsistent with a non-empty material_risks list.
        raw["packet"]["components"]["risk_register"]["risk_register_status"] = "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertNotEqual("malformed", result.get("status"))
        self.assertEqual("malformed", result["packet"]["components"]["risk_register"]["status"])
        self.assertIn("current_research_decision_packet_component_risk_register_malformed",
                      result["packet"]["components"]["risk_register"]["reason_codes"])
        # Unrelated valid components are untouched.
        self.assertEqual(_FINANCIAL_MOMENTUM_COMPONENT, result["packet"]["components"]["financial_momentum_context"])
        self.assertEqual(_SCENARIO_COMPONENT, result["packet"]["components"]["scenario_context"])
        self.assertEqual(_MARKET_SECTOR_COMPONENT, result["packet"]["components"]["market_sector_context"])
        self.assertEqual(_CORPORATE_EVENT_COMPONENT, result["packet"]["components"]["corporate_event_context"])
        self.assertEqual(_VALUATION_COMPONENT, result["packet"]["components"]["valuation_context"])
        self.assertEqual(_HISTORICAL_COMPONENT, result["packet"]["components"]["historical_research_context"])

    def test_locally_malformed_financial_momentum_component(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["components"]["financial_momentum_context"]["financial_momentum_state"] = "NOT_A_REAL_STATE"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["packet"]["components"]["financial_momentum_context"]["status"])

    def test_locally_malformed_market_sector_component(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["components"]["market_sector_context"]["ticker_context"]["ticker"] = "WRONG_TICKER"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["packet"]["components"]["market_sector_context"]["status"])

    def test_locally_malformed_corporate_event_component(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["components"]["corporate_event_context"]["events"][0]["event_status"] = "NOT_A_REAL_STATUS"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["packet"]["components"]["corporate_event_context"]["status"])

    def test_locally_malformed_valuation_component(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["components"]["valuation_context"]["metrics"]["pb"]["status"] = "NOT_A_REAL_STATUS"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["packet"]["components"]["valuation_context"]["status"])

    def test_locally_malformed_historical_component(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["components"]["historical_research_context"]["authority_boundary"]["PIT"] = "NOT_BLOCKED"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["packet"]["components"]["historical_research_context"]["status"])

    def test_locally_malformed_scenario_component(self):
        raw = copy.deepcopy(_PACKET_RAW)
        raw["packet"]["components"]["scenario_context"]["scenario_disposition"] = "NOT_A_REAL_DISPOSITION"
        result = current_research_decision_packet_contract(_bundle(raw), TICKER)
        self.assertEqual("malformed", result["packet"]["components"]["scenario_context"]["status"])

    # --- apply_bundle wiring ---
    def test_apply_bundle_sets_context_key_and_provenance(self):
        context = {"ticker": TICKER, "provenance": []}
        apply_bundle_current_research_decision_packet_contract(context, _bundle(_PACKET_RAW))
        self.assertEqual(_PACKET_RAW, context["current_research_decision_packet"])
        datasets = [entry["source_dataset"] for entry in context["provenance"]]
        self.assertIn("current_research_decision_packet", datasets)

    def test_apply_bundle_no_op_when_absent(self):
        context = {"ticker": TICKER, "provenance": []}
        apply_bundle_current_research_decision_packet_contract(context, {"tickers": {TICKER: {}}})
        self.assertNotIn("current_research_decision_packet", context)
        self.assertEqual([], context["provenance"])


if __name__ == "__main__":
    unittest.main()
