"""Consumer pass-through tests for the current_state_price_analytics contract.

Mirrors tests/test_current_state_market_risk_contract_pass_through.py's pattern:
tickers[ticker].current_state_price_analytics is a byte-identical pass-through of
stock-core-private/dnse_current_state_price_analytics.py's output.
Consumer never recomputes returns, volatility, drawdown, RSI, SMA, or any statistic.
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.build_ticker_context import (  # noqa: E402
    apply_bundle_current_state_price_analytics_contract,
    current_state_price_analytics_contract,
)

# CONTRACT_PARITY_FIXTURE (TEST_FIXTURE_ONLY)
# Shape-matched to the canonical Producer output baseline using known real HPG values.
# NOT A REAL_RUNTIME_FETCH -- used solely for INPUT VALUE == OUTPUT VALUE transport validation.
CONTRACT_PARITY_FIXTURE = {
    "schema_version": "1.0.0",
    "ticker": "HPG",
    "status": "available",
    "source": "DNSE",
    "price_basis": "ADJUSTED_CONFIRMED",
    "price_basis_contract_version": "dnse_ohlc_price_basis/2026-08-10",
    "analysis_time_semantics": "current_state_using_retrospectively_adjusted_history",
    "pit_backtest_eligible": False,
    "is_actionable": False,
    "coverage": {
        "status": "complete",
        "observation_count": 19,
        "return_count": 18,
    },
    "observation_count": 19,
    "return_count": 18,
    "simple_returns": [
        -0.01, 0.005, -0.02, 0.015, -0.008, 0.002, -0.012, 0.003, -0.005,
        0.001, -0.015, 0.008, -0.004, 0.006, -0.01, 0.002, -0.003, 0.001,
    ],
    "cumulative_return": -0.022222222222222254,
    "realized_volatility": 0.021398909938627342,
    "maximum_drawdown": -0.09555555555555558,
    "rsi_14": {
        "status": "available",
        "value": 47.273030438640725,
        "period": 14,
        "method": "wilder_smoothing",
    },
    "sma_20": {
        "status": "unavailable",
        "value": None,
        "period": 20,
        "reason": "insufficient_observations_requires_minimum_20",
    },
    "warnings": [
        "short_observation_window_statistical_confidence_is_limited",
        "descriptive_current_state_statistic_only_not_a_recommendation_or_trading_signal",
        "current_state_only_no_point_in_time_or_backtest_authority",
    ],
    "provenance": {
        "contract_module": "dnse_current_state_price_analytics.py",
        "contract_version": "1.0.0",
        "stock_source": "DNSE",
    },
}

# Non-qualified synthetic fixture for VNM (TEST_FIXTURE_ONLY)
_VNM_NOT_QUALIFIED_PRICE_ANALYTICS = {
    "schema_version": "1.0.0",
    "ticker": "VNM",
    "status": "not_qualified",
    "source": "DNSE",
    "price_basis": None,
    "price_basis_contract_version": None,
    "analysis_time_semantics": "current_state_using_retrospectively_adjusted_history",
    "pit_backtest_eligible": False,
    "is_actionable": False,
    "coverage": {
        "status": "not_qualified",
        "observation_count": 0,
        "return_count": 0,
        "reason": "stock_ticker_not_qualified_for_dnse_current_state_price_analytics",
    },
    "observation_count": 0,
    "return_count": 0,
    "cumulative_return": None,
    "realized_volatility": None,
    "maximum_drawdown": None,
    "rsi_14": {"status": "not_qualified", "value": None},
    "sma_20": {"status": "not_qualified", "value": None},
    "warnings": ["stock_ticker_not_qualified_for_dnse_current_state_price_analytics"],
    "provenance": {
        "contract_module": "dnse_current_state_price_analytics.py",
        "contract_version": "1.0.0",
    },
}


class CurrentStatePriceAnalyticsPassThroughTests(unittest.TestCase):
    def test_passes_through_verbatim(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertEqual(CONTRACT_PARITY_FIXTURE, context["current_state_price_analytics"])

    def test_exact_numeric_values_preserved(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        result = context["current_state_price_analytics"]
        self.assertEqual(-0.022222222222222254, result["cumulative_return"])
        self.assertEqual(0.021398909938627342, result["realized_volatility"])
        self.assertEqual(-0.09555555555555558, result["maximum_drawdown"])

    def test_nested_rsi_structure_preserved(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        rsi = context["current_state_price_analytics"]["rsi_14"]
        self.assertEqual("available", rsi["status"])
        self.assertEqual(47.273030438640725, rsi["value"])

    def test_unavailable_sma20_preserved_exactly(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        sma = context["current_state_price_analytics"]["sma_20"]
        self.assertEqual("unavailable", sma["status"])
        self.assertIsNone(sma["value"])

    def test_observation_count_preserved(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertEqual(19, context["current_state_price_analytics"]["observation_count"])

    def test_return_count_preserved(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertEqual(18, context["current_state_price_analytics"]["return_count"])

    def test_analysis_time_semantics_preserved(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertEqual(
            "current_state_using_retrospectively_adjusted_history",
            context["current_state_price_analytics"]["analysis_time_semantics"],
        )

    def test_pit_backtest_eligible_false_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertIs(False, context["current_state_price_analytics"]["pit_backtest_eligible"])

    def test_is_actionable_false_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertIs(False, context["current_state_price_analytics"]["is_actionable"])

    def test_warnings_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertEqual(
            CONTRACT_PARITY_FIXTURE["warnings"],
            context["current_state_price_analytics"]["warnings"],
        )

    def test_provenance_entry_recorded(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        sources = [p.get("source_dataset") for p in context["provenance"]]
        self.assertIn("current_state_price_analytics", sources)

    def test_field_missing_remains_absent_backward_compatible(self):
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertNotIn("current_state_price_analytics", context)

    def test_ticker_absent_from_bundle_entirely_remains_backward_compatible(self):
        bundle = {"tickers": {}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertNotIn("current_state_price_analytics", context)

    def test_none_bundle_remains_backward_compatible(self):
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, None)
        self.assertNotIn("current_state_price_analytics", context)

    def test_malformed_contract_fails_closed_locally(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": "not-a-dict"}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertEqual("malformed", context["current_state_price_analytics"]["status"])
        self.assertIs(False, context["current_state_price_analytics"]["is_actionable"])
        self.assertIs(False, context["current_state_price_analytics"]["pit_backtest_eligible"])

    def test_malformed_input_does_not_corrupt_other_context_fields(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": "not-a-dict"}}}
        context = {"ticker": "HPG", "provenance": [], "some_other_field": "untouched"}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertEqual("untouched", context["some_other_field"])

    def test_no_recomputation_performed(self):
        """Contract returns deep copy of input; modification does not alter source."""
        original = copy.deepcopy(CONTRACT_PARITY_FIXTURE)
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": original}}}
        result = current_state_price_analytics_contract(bundle, "HPG")
        result["cumulative_return"] = 999.0
        self.assertEqual(-0.022222222222222254, original["cumulative_return"])

    def test_no_numeric_rounding_applied(self):
        """Floating point values preserve full precision without round()."""
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        val = context["current_state_price_analytics"]["cumulative_return"]
        self.assertEqual(str(CONTRACT_PARITY_FIXTURE["cumulative_return"]), str(val))

    def test_market_risk_section_unchanged_and_coexists(self):
        """Multi-angle context test: market risk coexists without being overwritten."""
        market_risk = {"status": "available", "beta": {"value": 0.809}}
        bundle = {
            "tickers": {
                "HPG": {
                    "current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE),
                    "current_state_market_risk": market_risk,
                }
            }
        }
        context = {"ticker": "HPG", "provenance": [], "current_state_market_risk": market_risk}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertIn("current_state_price_analytics", context)
        self.assertEqual(market_risk, context["current_state_market_risk"])

    def test_foreign_flow_section_unchanged_and_coexists(self):
        """Multi-angle context test: foreign flow coexists without being overwritten."""
        foreign_flow = {"status": "available", "cumulative_net_value_vnd": 123456}
        bundle = {
            "tickers": {
                "HPG": {
                    "current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE),
                    "foreign_flow": foreign_flow,
                }
            }
        }
        context = {"ticker": "HPG", "provenance": [], "foreign_flow": foreign_flow}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertIn("current_state_price_analytics", context)
        self.assertEqual(foreign_flow, context["foreign_flow"])

    def test_historical_fundamental_brief_unchanged_and_coexists(self):
        """Multi-angle context test: fundamental brief coexists without being overwritten."""
        brief = {"status": "available", "facts": {"revenue": 1000}}
        bundle = {
            "tickers": {
                "HPG": {
                    "current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE),
                    "historical_fundamental_brief": brief,
                }
            }
        }
        context = {"ticker": "HPG", "provenance": [], "historical_fundamental_brief": brief}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        self.assertIn("current_state_price_analytics", context)
        self.assertEqual(brief, context["historical_fundamental_brief"])

    def test_not_qualified_ticker_passes_through_unchanged_no_fabricated_value(self):
        bundle = {"tickers": {"VNM": {"current_state_price_analytics": copy.deepcopy(_VNM_NOT_QUALIFIED_PRICE_ANALYTICS)}}}
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        result = context["current_state_price_analytics"]
        self.assertEqual("not_qualified", result["status"])
        self.assertIsNone(result["cumulative_return"])
        self.assertIsNone(result["rsi_14"]["value"])

    def test_no_test_fixture_imported_by_production_code(self):
        import builders.build_ticker_context as btc
        self.assertFalse(hasattr(btc, "CONTRACT_PARITY_FIXTURE"))
        self.assertFalse(hasattr(btc, "_VNM_NOT_QUALIFIED_PRICE_ANALYTICS"))

    def test_serialization_deterministic(self):
        bundle = {"tickers": {"HPG": {"current_state_price_analytics": copy.deepcopy(CONTRACT_PARITY_FIXTURE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_price_analytics_contract(context, bundle)
        dumped1 = json.dumps(context, sort_keys=True)
        dumped2 = json.dumps(context, sort_keys=True)
        self.assertEqual(dumped1, dumped2)


if __name__ == "__main__":
    unittest.main()
