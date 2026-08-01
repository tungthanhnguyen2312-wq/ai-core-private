import json
import tempfile
import unittest
from pathlib import Path
from builders import build_ticker_context as builder
class AnalysisReadinessConsumerTests(unittest.TestCase):
    def _load(self, proof=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bundle = root / "analysis_bundle.json"
            bundle.write_text(json.dumps({"tickers": {"HPG": {}, "VNM": {}}}), encoding="utf-8")
            if proof is not None:
                (root / "bundle_manifest.json").write_text(json.dumps({"trusted_subset": proof}), encoding="utf-8")
            return builder.load_optional_analysis_bundle({"source_paths": {"analysis_bundle": str(bundle)}})
    def test_legacy_and_malformed_are_conservative_unknown(self):
        self.assertEqual(builder.analysis_readiness_contract({"tickers": {"HPG": {}}}, "HPG")["status"], "unknown")
        self.assertEqual(builder.analysis_readiness_contract({"tickers": {"HPG": {"analysis_readiness": {}}}}, "HPG")["status"], "unknown")
    def test_ready_requires_actionable_and_degraded_warns(self):
        bundle = {"tickers": {"HPG": {"analysis_readiness": {"reference_at": "2026-07-26T00:00:00+00:00", "domains": {"market_technical": {"state": "degraded", "reason": "stale", "required_inputs": [], "is_actionable": False}}}}}}
        value = builder.analysis_readiness_contract(bundle, "HPG"); self.assertEqual(value["status"], "available"); self.assertFalse(value["inferences_allowed"]); self.assertTrue(value["data_warnings"])
    def test_untrusted_bundle_cannot_pass_readiness_or_lanes(self):
        bundle = {"trusted_subset_validation": {"state": "untrusted", "reason": "manifest_invalid"}, "tickers": {"HPG": {"analysis_readiness": {"domains": {}}, "analysis_lane_eligibility": []}}}
        self.assertEqual(builder.analysis_readiness_contract(bundle, "HPG")["status"], "unknown")
        self.assertEqual(builder.analysis_lane_eligibility_contract(bundle, "HPG")["status"], "untrusted")
    def test_manifest_states_are_fail_closed(self):
        payload, warning = self._load(); self.assertEqual(payload["trusted_subset_validation"]["state"], "legacy_untrusted"); self.assertEqual(warning, "trusted_subset_legacy_untrusted")
        proof = {"schema_version": "1.0.0", "tickers": ["HPG", "VNM"], "session_identity": "2026-07-30", "bundle_filename": "analysis_bundle.json", "bundle_sha256": "bad", "per_ticker": {"HPG": {"session_identity": "2026-07-30"}, "VNM": {"session_identity": "2026-07-30"}}, "trust_state": "exact_session_qualified"}
        payload, warning = self._load(proof); self.assertEqual(payload["trusted_subset_validation"]["state"], "untrusted"); self.assertEqual(warning, "trusted_subset_untrusted")
    def test_valid_manifest_is_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); bundle = root / "analysis_bundle.json"
            bundle.write_text(json.dumps({"tickers": {"HPG": {}, "VNM": {}}}), encoding="utf-8")
            proof = {"schema_version": "1.0.0", "tickers": ["HPG", "VNM"], "session_identity": "2026-07-30", "bundle_filename": "analysis_bundle.json", "bundle_sha256": __import__("hashlib").sha256(bundle.read_bytes()).hexdigest(), "per_ticker": {"HPG": {"session_identity": "2026-07-30"}, "VNM": {"session_identity": "2026-07-30"}}, "price_basis": {"verified": True}, "volume_basis": {"verified": True}, "trust_state": "exact_session_qualified"}
            (root / "bundle_manifest.json").write_text(json.dumps({"trusted_subset": proof}), encoding="utf-8")
            payload, warning = builder.load_optional_analysis_bundle({"source_paths": {"analysis_bundle": str(bundle)}})
            self.assertEqual(payload["trusted_subset_validation"]["state"], "exact_session_trusted"); self.assertIsNone(warning)
if __name__ == "__main__": unittest.main()
