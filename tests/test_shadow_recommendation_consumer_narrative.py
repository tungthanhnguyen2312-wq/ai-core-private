from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.shadow_recommendation_consumer_narrative import (  # noqa: E402
    ATTACHMENT_KEY,
    PRODUCER_CONTRACT_VERSION,
    build_prompt_payload,
    parse_shadow_recommendation_attachment,
    render_fallback_narrative,
    validate_full_producer_artifact,
    validate_narrative_response,
)
from builders.build_ticker_context import apply_bundle_shadow_recommendation_narrative_contract  # noqa: E402


PRODUCER_ARTIFACT = ROOT.parent / "stock-core-private" / "operations-review" / "shadow-security-recommendation-v1-20260829" / "artifact.json"


@unittest.skipUnless(PRODUCER_ARTIFACT.exists(), "retained Producer artifact is unavailable")
class ShadowRecommendationConsumerNarrativeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.artifact = json.loads(PRODUCER_ARTIFACT.read_text(encoding="utf-8"))

    def _entry(self, ticker: str, *, version: str | None = None):
        attachment = {
            "ticker": ticker,
            "source_artifact_identity": self.artifact["artifact_identity"],
            "recommendation_packet": copy.deepcopy(self.artifact["records"][ticker]),
            "authority_boundary": copy.deepcopy(self.artifact["authority_boundaries"]),
            "shadow_mode": "SHADOW_OPT_IN",
            "is_actionable": False,
        }
        if version is not None:
            attachment["producer_contract_version"] = version
        return {ATTACHMENT_KEY: attachment}

    def _input(self, ticker: str):
        result = parse_shadow_recommendation_attachment(self._entry(ticker), expected_ticker=ticker)
        self.assertEqual("SHADOW_RECOMMENDATION_READY", result["status"])
        return result["narrative_input"]

    def test_optional_attachment_and_unknown_contract_fail_closed(self):
        self.assertEqual("SHADOW_RECOMMENDATION_NOT_ATTACHED", parse_shadow_recommendation_attachment({}, expected_ticker="BFC")["status"])
        unsupported = parse_shadow_recommendation_attachment(self._entry("BFC", version="shadow_security_recommendation/v2"), expected_ticker="BFC")
        self.assertEqual("UNSUPPORTED_SHADOW_RECOMMENDATION_CONTRACT", unsupported["status"])
        explicit_v1 = parse_shadow_recommendation_attachment(self._entry("BFC", version=PRODUCER_CONTRACT_VERSION), expected_ticker="BFC")
        self.assertEqual("SHADOW_RECOMMENDATION_READY", explicit_v1["status"])

    def test_optional_bundle_integration_preserves_legacy_context(self):
        legacy = {"ticker": "BFC", "provenance": []}
        apply_bundle_shadow_recommendation_narrative_contract(legacy, {"tickers": {"BFC": {}}})
        self.assertNotIn("shadow_recommendation_narrative", legacy)
        attached = {"ticker": "BFC", "provenance": []}
        apply_bundle_shadow_recommendation_narrative_contract(attached, {"tickers": {"BFC": self._entry("BFC")}})
        self.assertEqual("SHADOW_RECOMMENDATION_READY", attached["shadow_recommendation_narrative"]["status"])

    def test_all_six_labels_and_readiness_are_immutable(self):
        seen = set()
        readiness = set()
        for ticker in sorted(self.artifact["records"]):
            item = self._input(ticker)
            fallback = render_fallback_narrative(item)
            self.assertEqual("NARRATIVE_VALID", validate_narrative_response(fallback, item)["status"])
            self.assertEqual(item["recommendation_label"], fallback["recommendation_label"])
            self.assertEqual(item["recommendation_readiness"], fallback["recommendation_readiness"])
            seen.add(item["recommendation_label"])
            readiness.add(item["recommendation_readiness"])
        self.assertEqual(set(self.artifact["metadata"]["recommendation_vocabulary"]), seen)
        self.assertEqual({"RECOMMENDATION_READY", "RECOMMENDATION_CONDITIONAL", "RECOMMENDATION_NOT_READY"}, readiness)

    def test_prompt_and_fallback_are_deterministic_and_preserve_unknowns(self):
        item = self._input("BFC")
        self.assertEqual(build_prompt_payload(item), build_prompt_payload(item))
        fallback = render_fallback_narrative(item)
        self.assertEqual(fallback, render_fallback_narrative(item))
        self.assertEqual(item["recommendation_packet"]["technical_invalidation"]["current_trigger_state"], "UNKNOWN")
        self.assertEqual(item["recommendation_packet"]["fundamental_invalidation"]["current_trigger_state"], "NOT_TRIGGERED")
        self.assertEqual("NOT_ESTABLISHED", item["recommendation_packet"]["temporal_context"]["close_price_execution_eligibility"])

    def test_validator_rejects_overrides_authority_and_unsupported_facts(self):
        item = self._input("BFC")
        valid = render_fallback_narrative(item)
        changed = copy.deepcopy(valid); changed["recommendation_label"] = "WAIT_FOR_CONFIRMATION"
        self.assertEqual("NARRATIVE_REJECTED_RECOMMENDATION_OVERRIDE", validate_narrative_response(changed, item)["status"])
        changed = copy.deepcopy(valid); changed["action"] = "BUY"
        self.assertEqual("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", validate_narrative_response(changed, item)["status"])
        changed = copy.deepcopy(valid); changed["supporting_evidence"][0]["numeric_facts"] = ["999999"]
        self.assertEqual("NARRATIVE_REJECTED_UNSUPPORTED_FACT", validate_narrative_response(changed, item)["status"])
        changed = copy.deepcopy(valid); changed["counter_thesis"][0]["source_locator"]["source_section"] = "absent_section"
        self.assertEqual("NARRATIVE_REJECTED_UNSUPPORTED_FACT", validate_narrative_response(changed, item)["status"])
        changed = copy.deepcopy(valid); del changed["risk"]
        self.assertEqual("NARRATIVE_REJECTED_SCHEMA", validate_narrative_response(changed, item)["status"])

    def test_full_retained_artifact_replays_without_count_drift(self):
        report = validate_full_producer_artifact(self.artifact, producer_head="f4f95c6dcc757e41136ef08f9badba39fb00aad2", consumer_start_head="c69b50ce8291bee293ba7b40ea4affb15ec256ca")
        self.assertEqual((523, 0), (report["denominator"], report["residual"]))
        self.assertEqual(self.artifact["validation"]["recommendation_counts"], report["label_preservation_counts"])
        self.assertEqual(self.artifact["validation"]["readiness_counts"], report["readiness_preservation_counts"])
        self.assertEqual(523, report["fallback_render_coverage"])
        self.assertEqual(0, report["label_drift_count"])
        self.assertEqual(0, report["readiness_drift_count"])
        self.assertEqual({"BUY": 0, "SELL": 0, "HOLD": 0}, {key: report["forbidden_authority_output_counts"][key] for key in ("BUY", "SELL", "HOLD")})


if __name__ == "__main__":
    unittest.main()
