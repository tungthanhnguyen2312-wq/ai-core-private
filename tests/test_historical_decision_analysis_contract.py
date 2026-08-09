import unittest

from builders import build_ticker_context as builder


def analysis(ticker="HPG"):
    return {
        "schema_version": "1.0.0", "ticker": ticker, "analysis_mode": "historical_only_qualified_data",
        "historical_only": True, "market_dependent": False, "is_actionable": False,
        "eligibility": {"status": "eligible", "reason_codes": []}, "quality_assessment": {},
        "risks": [], "catalysts": [], "scenarios": {"bear": {}, "base": {}, "bull": {}},
        "invalidation_conditions": ["later qualified fact conflicts"], "historical_conclusion": {"status": "historically_mixed"},
    }


class HistoricalDecisionAnalysisConsumerTests(unittest.TestCase):
    def test_passes_through_without_recomputation(self):
        context = {"ticker": "HPG", "provenance": []}
        result = builder.apply_bundle_historical_decision_analysis_contract(
            context, {"tickers": {"HPG": {"historical_decision_analysis": analysis()}}}
        )
        self.assertEqual(result["historical_decision_analysis"], analysis())
        self.assertEqual(result["provenance"][-1]["source_dataset"], "historical_decision_analysis")

    def test_malformed_or_wrong_ticker_fails_closed(self):
        context = {"ticker": "HPG", "provenance": []}
        result = builder.apply_bundle_historical_decision_analysis_contract(
            context, {"tickers": {"HPG": {"historical_decision_analysis": analysis("VNM")}}}
        )
        self.assertEqual(result["historical_decision_analysis"]["status"], "malformed")
        self.assertFalse(result["historical_decision_analysis"]["is_actionable"])


if __name__ == "__main__":
    unittest.main()
