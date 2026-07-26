import unittest
from builders import build_ticker_context as builder
class AnalysisReadinessConsumerTests(unittest.TestCase):
    def test_legacy_and_malformed_are_conservative_unknown(self):
        self.assertEqual(builder.analysis_readiness_contract({"tickers": {"HPG": {}}}, "HPG")["status"], "unknown")
        self.assertEqual(builder.analysis_readiness_contract({"tickers": {"HPG": {"analysis_readiness": {}}}}, "HPG")["status"], "unknown")
    def test_ready_requires_actionable_and_degraded_warns(self):
        bundle = {"tickers": {"HPG": {"analysis_readiness": {"reference_at": "2026-07-26T00:00:00+00:00", "domains": {"market_technical": {"state": "degraded", "reason": "stale", "required_inputs": [], "is_actionable": False}}}}}}
        value = builder.analysis_readiness_contract(bundle, "HPG"); self.assertEqual(value["status"], "available"); self.assertFalse(value["inferences_allowed"]); self.assertTrue(value["data_warnings"])
if __name__ == "__main__": unittest.main()
