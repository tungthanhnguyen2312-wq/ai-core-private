from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.correlation_concentration_consumer_context import parse_correlation_concentration_context  # noqa: E402
from builders.build_ticker_context import apply_bundle_shadow_recommendation_narrative_contract  # noqa: E402
from builders.shadow_recommendation_consumer_narrative import (  # noqa: E402
    ATTACHMENT_KEY,
    attach_correlation_concentration_context,
    build_prompt_payload,
    parse_shadow_recommendation_attachment,
    render_fallback_narrative,
    validate_narrative_response,
)


SHADOW = ROOT.parent / "stock-core-private" / "operations-review" / "shadow-security-recommendation-v1-20260829" / "artifact.json"
C2 = ROOT.parent / "stock-core-private" / "operations-review" / "correlation-concentration-guard-v1-20260829" / "artifact.json"


@unittest.skipUnless(SHADOW.exists() and C2.exists(), "retained Producer C2 evidence is unavailable")
class CorrelationConcentrationConsumerContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shadow = json.loads(SHADOW.read_text(encoding="utf-8"))
        cls.c2 = json.loads(C2.read_text(encoding="utf-8"))

    def _shadow_input(self, ticker: str = "BSR"):
        entry = {ATTACHMENT_KEY: {"ticker": ticker, "source_artifact_identity": self.shadow["artifact_identity"],
            "recommendation_packet": copy.deepcopy(self.shadow["records"][ticker]),
            "authority_boundary": copy.deepcopy(self.shadow["authority_boundaries"]), "shadow_mode": "SHADOW_OPT_IN", "is_actionable": False}}
        parsed = parse_shadow_recommendation_attachment(entry, expected_ticker=ticker)
        self.assertEqual("SHADOW_RECOMMENDATION_READY", parsed["status"])
        return parsed["narrative_input"]

    def _attached(self, ticker: str = "BSR", artifact=None):
        source = self._shadow_input(ticker)
        attached = attach_correlation_concentration_context(source, self.c2 if artifact is None else artifact)
        self.assertEqual("CORRELATION_CONCENTRATION_READY", attached["status"])
        return source, attached["narrative_input"]

    def test_retained_bsr_gas_replay_preserves_exact_producer_context(self):
        source, item = self._attached()
        context = item["correlation_concentration_context"]
        pair = next(row for row in context["pairs_for_security"] if {row["ticker_i"], row["ticker_j"]} == {"BSR", "GAS"})
        self.assertEqual(0.8235585903592545, pair["correlation"])
        self.assertEqual((20, "JOINT_MATRIX_BLOCKED_T_RELATIVE_TO_N"), (context["selected_lookback_sessions"], context["joint_matrix_status"]))
        self.assertEqual((780, 0), (context["pairwise_ready_count"], context["pairwise_insufficient_or_unavailable_count"]))
        self.assertEqual(["BSR", "GAS"], context["concentration_groups_for_security"][0]["tickers"])
        self.assertEqual(source["recommendation_label"], item["recommendation_label"])
        self.assertEqual(source["recommendation_readiness"], item["recommendation_readiness"])

    def test_absence_is_backward_compatible(self):
        source = self._shadow_input()
        absent = attach_correlation_concentration_context(source, None)
        self.assertEqual("CORRELATION_CONCENTRATION_NOT_ATTACHED", absent["status"])
        fallback = render_fallback_narrative(source)
        self.assertNotIn("correlation_concentration_context", fallback)
        self.assertNotIn("correlation_concentration_context", build_prompt_payload(source))
        self.assertEqual("NARRATIVE_VALID", validate_narrative_response(fallback, source)["status"])

    def test_optional_bundle_boundary_attaches_only_validated_c2(self):
        ticker = "BSR"
        entry = {ATTACHMENT_KEY: {"ticker": ticker, "source_artifact_identity": self.shadow["artifact_identity"],
            "recommendation_packet": copy.deepcopy(self.shadow["records"][ticker]), "authority_boundary": copy.deepcopy(self.shadow["authority_boundaries"]),
            "shadow_mode": "SHADOW_OPT_IN", "is_actionable": False}}
        context = {"ticker": ticker, "provenance": []}
        apply_bundle_shadow_recommendation_narrative_contract(context, {"tickers": {ticker: entry}, "correlation_concentration_guard": self.c2})
        self.assertEqual("CORRELATION_CONCENTRATION_READY", context["shadow_recommendation_narrative"]["correlation_concentration_status"])
        self.assertIn("correlation_concentration_context", context["shadow_recommendation_narrative"]["narrative_input"])
        legacy = {"ticker": ticker, "provenance": []}
        apply_bundle_shadow_recommendation_narrative_contract(legacy, {"tickers": {ticker: entry}})
        self.assertNotIn("correlation_concentration_status", legacy["shadow_recommendation_narrative"])

    def test_prompt_fallback_and_group_order_are_deterministic(self):
        _, item = self._attached()
        self.assertEqual(build_prompt_payload(item), build_prompt_payload(item))
        fallback = render_fallback_narrative(item)
        self.assertEqual(fallback, render_fallback_narrative(item))
        self.assertEqual("NARRATIVE_VALID", validate_narrative_response(fallback, item)["status"])
        self.assertEqual(["BSR", "GAS"], fallback["correlation_concentration_context"]["producer_context"]["concentration_groups_for_security"][0]["tickers"])
        self.assertEqual(0.8, fallback["correlation_concentration_context"]["producer_context"]["threshold_contract"]["threshold"])

    def test_no_trigger_and_partial_context_remain_bounded(self):
        no_trigger = copy.deepcopy(self.c2)
        for row in no_trigger["pairwise_correlation_context"]:
            if {row["ticker_i"], row["ticker_j"]} == {"BSR", "GAS"}:
                row["correlation"] = 0.7
        no_trigger["concentration_groups"] = []
        no_trigger["guard_context"]["status"] = "NO_MATERIAL_CORRELATION_CONCENTRATION"
        no_trigger["validation"].update({"triggered_edge_count": 0, "triggered_group_count": 0, "concentrated_group_count": 0})
        _, no_trigger_item = self._attached(artifact=no_trigger)
        text = " ".join(claim["text"] for claim in render_fallback_narrative(no_trigger_item)["correlation_concentration_context"]["narrative_claims"])
        self.assertIn("does not establish diversification", text)
        partial = copy.deepcopy(no_trigger)
        partial["pairwise_correlation_context"][0].update({"status": "PAIRWISE_INSUFFICIENT_OR_PARTIAL", "correlation": None, "return_observations": None})
        partial["validation"].update({"pairwise_ready_count": 779, "pairwise_insufficient_or_unavailable_count": 1})
        partial["guard_context"]["status"] = "PARTIAL_PAIRWISE_VIEW"
        _, partial_item = self._attached(artifact=partial)
        partial_text = " ".join(claim["text"] for claim in render_fallback_narrative(partial_item)["correlation_concentration_context"]["narrative_claims"])
        self.assertIn("partial", partial_text)

    def test_invalid_contract_malformed_and_internal_conflict_fail_closed(self):
        source = self._shadow_input()
        invalid = copy.deepcopy(self.c2); invalid["contract_version"] = "correlation_concentration_guard/v2"
        self.assertEqual("UNSUPPORTED_CORRELATION_CONCENTRATION_CONTRACT", attach_correlation_concentration_context(source, invalid)["status"])
        malformed = copy.deepcopy(self.c2); malformed["pairwise_correlation_context"][0]["correlation"] = 1.2
        self.assertEqual("CORRELATION_CONCENTRATION_MALFORMED", attach_correlation_concentration_context(source, malformed)["status"])
        conflict = copy.deepcopy(self.c2); conflict["concentration_groups"] = []; conflict["validation"].update({"triggered_edge_count": 0, "triggered_group_count": 0})
        self.assertEqual("CORRELATION_CONCENTRATION_INTERNAL_INCONSISTENCY", attach_correlation_concentration_context(source, conflict)["status"])

    def test_validator_rejects_c2_mutation_recommendation_override_and_authority_output(self):
        _, item = self._attached()
        fallback = render_fallback_narrative(item)
        changed = copy.deepcopy(fallback); changed["correlation_concentration_context"]["producer_context"]["guard_status"] = "NO_MATERIAL_CORRELATION_CONCENTRATION"
        self.assertEqual("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", validate_narrative_response(changed, item)["status"])
        changed = copy.deepcopy(fallback); changed["recommendation_label"] = "WAIT_FOR_CONFIRMATION"
        self.assertEqual("NARRATIVE_REJECTED_RECOMMENDATION_OVERRIDE", validate_narrative_response(changed, item)["status"])
        changed = copy.deepcopy(fallback); changed["allocation"] = "any"
        self.assertEqual("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", validate_narrative_response(changed, item)["status"])
        changed = copy.deepcopy(fallback); changed["correlation_concentration_context"]["narrative_claims"][0]["text"] = "BUY after correlation review"
        self.assertEqual("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", validate_narrative_response(changed, item)["status"])


if __name__ == "__main__":
    unittest.main()
