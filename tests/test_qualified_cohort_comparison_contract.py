import copy
import unittest

from builders import build_ticker_context as builder


def comparison():
    return {
        "schema_version": "1.0.0", "status": "available", "cohort_name": "qualified_historical_fundamental_cohort",
        "cohort_tickers": ["HPG", "VNM", "PAN", "PVD", "NVL"], "historical_only": True,
        "market_dependent": False, "is_actionable": False, "cross_sectional_comparison": "available",
        "multi_period_trend": "insufficient_history", "ranking_prohibited": True, "rows": [{"ticker": "HPG"}],
    }


class QualifiedCohortComparisonConsumerTests(unittest.TestCase):
    def test_verbatim_pass_through_without_comparison_or_fx_logic(self):
        payload = comparison()
        context = {"ticker": "HPG", "provenance": []}
        result = builder.apply_bundle_qualified_cohort_comparison_contract(
            context, {"tickers": {"HPG": {"qualified_cohort_comparison": payload}}},
        )
        self.assertEqual(result["qualified_cohort_comparison"], payload)
        self.assertEqual(result["provenance"][-1]["source_dataset"], "qualified_cohort_comparison")
        self.assertEqual(result["qualified_cohort_comparison"], copy.deepcopy(payload))

    def test_malformed_or_wrong_cohort_fails_closed(self):
        context = {"ticker": "HPG", "provenance": []}
        result = builder.apply_bundle_qualified_cohort_comparison_contract(
            context, {"tickers": {"HPG": {"qualified_cohort_comparison": {"status": "available"}}}},
        )
        self.assertEqual(result["qualified_cohort_comparison"]["status"], "malformed")
        self.assertFalse(result["qualified_cohort_comparison"]["is_actionable"])


if __name__ == "__main__":
    unittest.main()
