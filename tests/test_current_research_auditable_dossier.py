from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.current_research_auditable_dossier import (
    build_current_research_auditable_dossier, render_current_research_auditable_dossier_markdown,
    replay_current_research_auditable_dossier,
)

_FIXTURE_SPEC = importlib.util.spec_from_file_location(
    "trace_fixture", ROOT / "tests" / "test_current_research_claim_provenance_trace.py",
)
assert _FIXTURE_SPEC is not None and _FIXTURE_SPEC.loader is not None
_FIXTURE = importlib.util.module_from_spec(_FIXTURE_SPEC)
_FIXTURE_SPEC.loader.exec_module(_FIXTURE)


def _dossier(ctx=None, response=None, claim_map=None, mode="LEGACY_DIRECT"):
    return build_current_research_auditable_dossier(
        ctx or _FIXTURE._context(), response or _FIXTURE._response(),
        claim_evidence_map=claim_map, packet_consumption_mode=mode,
    )


class CurrentResearchAuditableDossierTests(unittest.TestCase):
    def test_01_accepted_response_materializes_dossier(self):
        self.assertEqual("READY_FOR_AUDIT", _dossier(claim_map={"thesis": ["current_financial_momentum_context.components.revenue_growth"]})["status"])

    def test_02_thesis_and_counter_thesis_are_verbatim(self):
        response = _FIXTURE._response(); dossier = _dossier(response=response)
        self.assertEqual(response["thesis"], dossier["current_research_thesis"])
        self.assertEqual(response["counter_thesis"], dossier["strongest_counter_thesis"])

    def test_03_identity_replays_deterministically(self):
        first, second = _dossier(), _dossier()
        self.assertEqual(first["dossier_identity"], second["dossier_identity"])
        replay_current_research_auditable_dossier(first)

    def test_04_trace_identity_is_retained(self):
        dossier = _dossier()
        self.assertTrue(dossier["research_identity"]["trace_identity"].startswith("current_research_claim_provenance_trace:"))

    def test_05_structured_synthesis_identity_is_retained(self):
        self.assertTrue(_dossier()["research_identity"]["structured_synthesis_identity"].startswith("structured_research_synthesis:"))

    def test_06_claim_provenance_contains_thesis(self):
        claim_ids = [claim["claim_id"] for claim in _dossier()["claim_provenance"]]
        self.assertIn("thesis", claim_ids)

    def test_07_package_wide_claims_remain_limited(self):
        thesis = _dossier()["claim_provenance"][0]
        self.assertEqual("SUPPORTED_WITH_LIMITATION", thesis["disposition"])

    def test_08_exact_claim_map_can_be_supported(self):
        dossier = _dossier(claim_map={"thesis": ["current_financial_momentum_context.components.revenue_growth"]})
        thesis = next(row for row in dossier["claim_provenance"] if row["claim_id"] == "thesis")
        self.assertEqual("SUPPORTED", thesis["disposition"])

    def test_09_unknown_ref_response_is_not_displayed_as_ready(self):
        response = _FIXTURE._response(["unknown:evidence"])
        dossier = _dossier(response=response)
        self.assertEqual("REJECTED_UNTRACEABLE", dossier["status"])

    def test_10_prohibited_claim_response_is_not_displayed_as_ready(self):
        response = _FIXTURE._response(); response["thesis"] = "This is a BUY recommendation."
        self.assertEqual("REJECTED_UNTRACEABLE", _dossier(response=response)["status"])

    def test_11_markdown_is_downstream_readable(self):
        markdown = render_current_research_auditable_dossier_markdown(_dossier())
        for section in ("RESEARCH IDENTITY", "CURRENT RESEARCH THESIS", "STRONGEST COUNTER-THESIS", "CLAIM PROVENANCE", "AUTHORITY SUMMARY"):
            self.assertIn(section, markdown)

    def test_12_scenario_families_are_distinct_sections(self):
        markdown = render_current_research_auditable_dossier_markdown(_dossier())
        self.assertIn("Evidence-Bound Scenario", markdown); self.assertIn("Research Scenario Axis", markdown)

    def test_13_current_state_preserves_source_contract_names(self):
        state = _dossier()["current_deterministic_state"]["upstream_source_contracts"]
        self.assertEqual({"tactical_entry_classifier", "opportunity_decision_queue"}, set(state))

    def test_14_default_path_remains_legacy_direct(self):
        self.assertEqual("LEGACY_DIRECT", _dossier()["authority_summary"]["packet_default_unchanged"])

    def test_15_authority_summary_has_no_recommendation_authority(self):
        prohibited = _dossier()["authority_summary"]["prohibited_interpretations"]
        self.assertIn("BUY_SELL_HOLD", prohibited); self.assertIn("PIT", prohibited)

    def test_16_unresolved_questions_are_verbatim(self):
        response = _FIXTURE._response(); response["unresolved_questions"] = ["A source remains unresolved."]
        self.assertEqual(response["unresolved_questions"], _dossier(response=response)["unresolved_questions"])

    def test_17_packet_shadow_is_presentation_metadata_only(self):
        dossier = _dossier(mode="PACKET_SHADOW")
        self.assertEqual("PACKET_SHADOW", dossier["research_identity"]["packet_consumption_mode"])
        self.assertEqual("LEGACY_DIRECT", dossier["authority_summary"]["packet_default_unchanged"])

    def test_18_rejected_markdown_does_not_render_thesis(self):
        response = _FIXTURE._response(["unknown:evidence"])
        markdown = render_current_research_auditable_dossier_markdown(_dossier(response=response))
        self.assertIn("REJECTED_UNTRACEABLE", markdown)
        self.assertNotIn("Observed financial evidence", markdown)

    def test_19_retained_parity_fixture_exposes_representative_conditions(self):
        path = ROOT / "operations-review" / "current-research-packet-shadow-parity-v1-20260825" / "current_research_packet_shadow_parity_artifact.json"
        artifact = json.loads(path.read_text(encoding="utf-8"))
        evidence = artifact["representative_evidence"]
        self.assertTrue(evidence["blocked_valuation_preserved"])
        self.assertTrue(evidence["technical_coverage_gap_without_whole_ticker_invalidation"])
        self.assertTrue(evidence["packet_only"])

    def test_20_no_current_path_imports_the_dossier(self):
        for path in (ROOT / "builders" / "build_ticker_context.py", ROOT / "builders" / "structured_research_synthesis_boundary.py", ROOT / "builders" / "current_research_packet_shadow_parity.py"):
            self.assertNotIn("current_research_auditable_dossier", path.read_text(encoding="utf-8"))

    def test_21_uncited_malformed_scenario_is_shown_as_empty_not_recomputed(self):
        ctx = _FIXTURE._context(); ctx["current_research_scenario_context"] = {"scenario_context": "malformed"}
        dossier = _dossier(ctx=ctx)
        self.assertEqual("READY_FOR_AUDIT", dossier["status"])
        self.assertEqual({}, dossier["current_deterministic_state"]["research_scenario_axis"])


if __name__ == "__main__":
    unittest.main()
