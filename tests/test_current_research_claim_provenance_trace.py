from __future__ import annotations

import copy
import importlib.util
import json
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.current_research_claim_provenance_trace import (
    AUTHORITY_BLOCKED, COMPONENT_UNAVAILABLE, CONFLICT_FAIL_CLOSED, MALFORMED,
    SUPPORTED, SUPPORTED_WITH_LIMITATION, UNSUPPORTED_REFERENCE, UNRESOLVED,
    build_current_research_claim_provenance_trace, query_current_research_claim_provenance_trace,
    render_current_research_claim_provenance_trace_markdown, replay_current_research_claim_provenance_trace,
)
from builders.structured_research_synthesis_boundary import PACKET_SHADOW

_PACKET_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "packet_fixture", ROOT / "tests" / "test_current_research_decision_packet_contract_pass_through.py",
)
assert _PACKET_FIXTURE_SPEC is not None and _PACKET_FIXTURE_SPEC.loader is not None
_PACKET_FIXTURE = importlib.util.module_from_spec(_PACKET_FIXTURE_SPEC)
_PACKET_FIXTURE_SPEC.loader.exec_module(_PACKET_FIXTURE)


def _response(refs=None):
    return {
        "ticker": "TRACE", "analysis_session": "2026-08-25", "synthesis_status": "PARTIAL_EVIDENCE",
        "thesis": "Observed financial evidence is available.", "supporting_evidence": ["Revenue growth is an observed component."],
        "counter_thesis": "Evidence remains bounded.", "counter_evidence": ["The trace does not infer a forecast."],
        "historical_context_summary": "Historical context is descriptive only.", "valuation_context_summary": "Valuation authority remains bounded.",
        "market_context_summary": "Market context is descriptive.", "sector_context_summary": "Sector context is descriptive.",
        "relative_strength_context": [], "catalyst_context": [], "risk_context": [], "invalidation_conditions": [],
        "unresolved_questions": [], "authority_limitations": ["No recommendation is provided."],
        "upstream_decision_context": {}, "provenance_references": refs or ["current_financial_momentum_context.components.revenue_growth"],
        "is_actionable": False,
    }


def _context():
    return {
        "ticker": "TRACE",
        "provenance": [{"source_dataset": "current_financial_momentum_context"}],
        "current_financial_momentum_context": {
            "status": "available", "session": "2026-08-25", "source_artifact_identity": "current_financial_momentum_context:f1",
            "ticker_context": {"components": {"revenue_growth": {"status": "AVAILABLE", "periods": ["2026Q2"], "current_value": 0.1, "direction": "EXPANDING"}}},
        },
    }


def _trace(ctx=None, response=None, claim_map=None, mode="LEGACY_DIRECT"):
    return build_current_research_claim_provenance_trace(ctx or _context(), response or _response(), claim_evidence_map=claim_map, packet_consumption_mode=mode)


class CurrentResearchClaimProvenanceTraceTests(unittest.TestCase):
    def test_01_valid_thesis_with_exact_map_supported(self):
        trace = _trace(claim_map={"thesis": ["current_financial_momentum_context.components.revenue_growth"]})
        self.assertEqual(SUPPORTED, trace["claim_entries"][0]["disposition"])

    def test_02_package_wide_refs_are_limited_not_exact(self):
        self.assertEqual(SUPPORTED_WITH_LIMITATION, _trace()["claim_entries"][0]["disposition"])

    def test_03_counter_thesis_is_a_traceable_claim(self):
        trace = _trace(claim_map={"counter_thesis": ["current_financial_momentum_context.components.revenue_growth"]})
        row = next(row for row in trace["claim_entries"] if row["claim_id"] == "counter_thesis")
        self.assertEqual(SUPPORTED, row["disposition"])

    def test_04_unknown_reference_is_untraceable(self):
        trace = _trace(claim_map={"thesis": ["unknown:evidence"]})
        self.assertEqual(UNSUPPORTED_REFERENCE, trace["claim_entries"][0]["disposition"])

    def test_05_missing_current_component_is_unavailable(self):
        trace = _trace(claim_map={"thesis": ["current_corporate_event_context.events.missing"]})
        self.assertEqual(COMPONENT_UNAVAILABLE, trace["claim_entries"][0]["disposition"])

    def test_06_missing_claim_map_entry_is_unresolved(self):
        self.assertEqual(UNRESOLVED, _trace(claim_map={})["claim_entries"][0]["disposition"])

    def test_07_prohibited_recommendation_is_authority_blocked(self):
        response = _response(); response["thesis"] = "This is a BUY recommendation."
        self.assertEqual(AUTHORITY_BLOCKED, _trace(response=response)["claim_entries"][0]["disposition"])

    def test_08_deterministic_identity_replays(self):
        first, second = _trace(), _trace()
        self.assertEqual(first["trace_identity"], second["trace_identity"])
        replay_current_research_claim_provenance_trace(first)

    def test_09_query_by_claim_type(self):
        rows = query_current_research_claim_provenance_trace(_trace(), claim_type="thesis")
        self.assertEqual(["thesis"], [row["claim_id"] for row in rows])

    def test_10_markdown_has_required_review_sections(self):
        rendered = render_current_research_claim_provenance_trace_markdown(_trace())
        self.assertIn("### CLAIM", rendered); self.assertIn("### SOURCE / AS-OF", rendered)

    def test_11_financial_period_stays_component_local(self):
        evidence = _trace()["claim_entries"][0]["evidence"][0]
        self.assertEqual([["2026Q2"]], evidence["temporal"].get("periods", []))

    def test_12_malformed_current_component_is_not_supported(self):
        ctx = _context(); ctx["current_financial_momentum_context"] = {"status": "malformed"}
        trace = _trace(ctx, _response(), {"thesis": ["current_financial_momentum_context.components.revenue_growth"]})
        self.assertEqual(MALFORMED, trace["claim_entries"][0]["disposition"])

    def test_13_blocked_valuation_is_authority_blocked(self):
        ctx = _context(); ctx["provenance"].append({"source_dataset": "market_wide_current_valuation"})
        ctx["market_wide_current_valuation"] = {"price_input": {"session": "2026-08-24"}, "metrics": {"ev_ebitda": {"status": "BLOCKED"}}}
        trace = _trace(ctx, _response(["market_wide_current_valuation"]), {"thesis": ["market_wide_current_valuation"]})
        self.assertEqual(AUTHORITY_BLOCKED, trace["claim_entries"][0]["disposition"])

    def test_14_historical_adjusted_limitations_are_preserved(self):
        ctx = _context(); ctx["provenance"].append({"source_dataset": "market_wide_historical_research_context"})
        ctx["market_wide_historical_research_context"] = {"session": "2026-08-20", "authority_boundary": {"PIT": "BLOCKED", "RAW_AS_TRADED": "NOT_PROMOTED"}}
        trace = _trace(ctx, _response(["market_wide_historical_research_context"]), {"thesis": ["market_wide_historical_research_context"]})
        self.assertIn("historical_adjusted_retrospective_not_pit_or_raw_as_traded", trace["claim_entries"][0]["reason_codes"])

    def test_15_planned_event_does_not_prove_execution(self):
        ctx = _context(); ctx["provenance"].append({"source_dataset": "current_corporate_event_context"})
        ctx["current_corporate_event_context"] = {"status": "available", "research_session": "2026-08-25", "ticker_context": {"events": [{"event_id": "event-1", "event_status": "CONFIRMED_UPCOMING", "record_date": "2026-08-26", "ex_date": "2026-08-27"}]}}
        ref = "current_corporate_event_context.events.event-1"
        trace = _trace(ctx, _response([ref]), {"thesis": [ref]})
        self.assertIn("event_status_does_not_prove_execution", trace["claim_entries"][0]["reason_codes"])

    def test_16_no_material_risk_is_not_low_risk(self):
        ctx = _context(); ctx["provenance"].append({"source_dataset": "current_research_risk_register"})
        ctx["current_research_risk_register"] = {"risk_register": {"risk_register_status": "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE"}, "source_contexts": {}}
        trace = _trace(ctx, _response(["current_research_risk_register"]), {"thesis": ["current_research_risk_register"]})
        self.assertIn("no_material_risk_established_is_not_low_risk", trace["claim_entries"][0]["reason_codes"])

    def test_17_packet_scenario_and_direct_scenario_are_separate(self):
        ctx = _context(); ctx["provenance"].append({"source_dataset": "current_research_scenario_context"})
        ctx["current_research_scenario_context"] = {"scenario_context": {"axes": {} }}; ctx["current_research_decision_packet"] = {"packet": {"components": {}}, "component_manifest": {}}
        trace = _trace(ctx, _response(["current_research_scenario_context"]), {"thesis": ["current_research_scenario_context"]}, PACKET_SHADOW)
        self.assertEqual("SEPARATE_NONCOMPARABLE_SCENARIO_CONTRACT", trace["claim_entries"][0]["evidence"][0]["duplicate_transport_disposition"])

    def test_18_packet_direct_equivalent_is_deduplicated(self):
        ctx = _context(); ctx["current_research_decision_packet"] = copy.deepcopy(_PACKET_FIXTURE._PACKET_RAW)
        trace = _trace(ctx, _response(), {"thesis": ["current_financial_momentum_context.components.revenue_growth"]}, PACKET_SHADOW)
        self.assertEqual("DEDUPLICATED_SAME_LOGICAL_EVIDENCE", trace["claim_entries"][0]["evidence"][0]["duplicate_transport_disposition"])

    def test_19_packet_direct_conflict_fails_closed(self):
        ctx = _context(); ctx["current_financial_momentum_context"]["source_artifact_identity"] = "current_financial_momentum_context:different"
        ctx["current_research_decision_packet"] = copy.deepcopy(_PACKET_FIXTURE._PACKET_RAW)
        trace = _trace(ctx, _response(), {"thesis": ["current_financial_momentum_context.components.revenue_growth"]}, PACKET_SHADOW)
        self.assertEqual(CONFLICT_FAIL_CLOSED, trace["claim_entries"][0]["disposition"])

    def test_20_packet_shadow_does_not_change_default_authority(self):
        trace = _trace(mode=PACKET_SHADOW)
        self.assertTrue(trace["authority_boundary"]["does_not_change_current_decisions_or_packet_default"])

    def test_21_evidence_is_minimal_not_full_artifact_copy(self):
        evidence = _trace()["claim_entries"][0]["evidence"][0]
        self.assertNotIn("current_value", evidence)

    def test_22_retained_packet_parity_representatives_remain_available(self):
        artifact_path = ROOT / "operations-review" / "current-research-packet-shadow-parity-v1-20260825" / "current_research_packet_shadow_parity_artifact.json"
        artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        self.assertEqual(1507, artifact["denominator"])
        self.assertEqual(1507, artifact["component_breakdown"]["financial_momentum"]["DUAL_EQUIVALENT"])
        self.assertTrue(artifact["representative_evidence"]["blocked_valuation_preserved"])
        self.assertTrue(artifact["representative_evidence"]["technical_coverage_gap_without_whole_ticker_invalidation"])
        self.assertTrue(artifact["representative_evidence"]["packet_only"])
        self.assertEqual(1507, artifact["component_breakdown"]["scenario"]["DUAL_NONCOMPARABLE_SEMANTICS"])


if __name__ == "__main__":
    unittest.main()
