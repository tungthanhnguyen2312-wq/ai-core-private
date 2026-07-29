import unittest
from builders import build_ticker_context as b


class RiskAnalysisContractTests(unittest.TestCase):
    def test_legacy(self):
        self.assertEqual(b.risk_analysis_contract({"tickers": {"A": {}}}, "A")["status"], "unknown")

    def test_vnm_pit_beta_and_correlation_passthrough(self):
        vnm_risk_payload = {
            "schema_version": "1.0.0",
            "reference_at": "2026-07-29T11:37:10Z",
            "dimensions": {
                "market_risk": "available",
                "liquidity": "available",
                "concentration": "unavailable",
                "position_sizing_readiness": "unavailable",
                "data_confidence": "partial",
            },
            "market_risk": {
                "realized_volatility": {"metric": "realized_volatility", "state": "available", "value": 0.015},
                "point_in_time_beta": {
                    "metric": "point_in_time_beta",
                    "state": "available",
                    "value": 0.85,
                    "benchmark": "VNINDEX",
                    "observation_window": "60_sessions",
                    "as_of_date": "2024-06-10",
                    "is_actionable": True,
                },
                "point_in_time_correlation": {
                    "metric": "point_in_time_correlation",
                    "state": "available",
                    "value": 0.78,
                    "benchmark": "VNINDEX",
                    "observation_window": "60_sessions",
                    "as_of_date": "2024-06-10",
                    "is_actionable": True,
                },
            },
            "liquidity_risk": {"average_volume": {"metric": "average_volume", "state": "available", "value": 1500000.0}},
            "portfolio_risk": {"state": "unavailable", "reason": "holdings_contract_absent"},
            "position_sizing": {"state": "unavailable", "reason": "holdings_cash_risk_budget_and_qualified_risk_inputs_required"},
        }
        bundle = {"tickers": {"VNM": {"risk_analysis": vnm_risk_payload}}}
        res = b.risk_analysis_contract(bundle, "VNM")
        self.assertEqual(res, vnm_risk_payload)

        ctx = {"ticker": "VNM"}
        b.apply_bundle_risk_analysis_contract(ctx, bundle)
        self.assertEqual(ctx["risk_analysis"], vnm_risk_payload)
        self.assertNotIn("alpha", ctx["risk_analysis"])
        self.assertNotIn("recommendation", ctx["risk_analysis"])

    def test_hpg_and_vcb_unavailability_passthrough(self):
        hpg_payload = {
            "market_risk": {
                "point_in_time_beta": {"metric": "point_in_time_beta", "state": "unavailable", "reason": "unqualified_ticker_or_missing_alignment_chain"},
                "point_in_time_correlation": {"metric": "point_in_time_correlation", "state": "unavailable", "reason": "unqualified_ticker_or_missing_alignment_chain"},
            }
        }
        bundle = {"tickers": {"HPG": {"risk_analysis": hpg_payload}}}
        res = b.risk_analysis_contract(bundle, "HPG")
        self.assertEqual(res["market_risk"]["point_in_time_beta"]["state"], "unavailable")
        self.assertEqual(res["market_risk"]["point_in_time_correlation"]["state"], "unavailable")


if __name__ == "__main__":
    unittest.main()
