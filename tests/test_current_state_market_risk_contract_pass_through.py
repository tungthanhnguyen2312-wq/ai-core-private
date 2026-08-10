"""Consumer pass-through tests for the current_state_market_risk contract.

Mirrors tests/test_dnse_foreign_flow_contract_pass_through.py's pattern:
tickers[ticker].current_state_market_risk is a byte-identical pass-through of
stock-core-private/dnse_current_state_market_risk.py's
compute_current_state_beta_correlation() output (plus the bundle-level
"status"/"is_actionable" fields export_ai_bundle.py's attach layer adds).
Consumer never recomputes a beta, correlation, or any statistic derived from
them.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.build_ticker_context import (  # noqa: E402
    apply_bundle_current_state_market_risk_contract,
    current_state_market_risk_contract,
)

# Shape-matched to the real Producer output, real values from the
# 2026-08-10 CURRENT_STATE_BETA_CORRELATION_READY milestone.
_REAL_HPG_MARKET_RISK = {
    "schema_version": "1.0.0", "ticker": "HPG", "benchmark": "VNINDEX",
    "status": "available",
    "source_scope": {"stock_source": "DNSE", "benchmark_source": "DNSE",
                     "same_source_no_fallback_mixing": True, "reason": None},
    "stock_price_contract": {"price_basis": "ADJUSTED_CONFIRMED",
                             "price_basis_contract_version": "dnse_ohlc_price_basis/2026-08-10",
                             "qualification_scope": "evidence_bounded_ticker_and_action_type"},
    "benchmark_return_contract": {"index_level_unit": "index_points",
                                  "source_contract_version": "dnse_index_return_series/2026-08-10"},
    "analysis_time_semantics": (
        "current_state_using_retrospectively_adjusted_stock_history_and_current_benchmark_history"
    ),
    "pit_backtest_eligible": False,
    "input_gates": {"stock_qualified": True, "stock_reason": None,
                    "benchmark_qualified": True, "benchmark_reason": None,
                    "source_scope_ok": True, "source_scope_reason": None},
    "aligned_sessions": {"aligned_pairs": [], "stock_return_count": 18, "benchmark_return_count": 18,
                         "paired_return_count": 18, "dropped_stock_sessions": [], "dropped_benchmark_sessions": []},
    "paired_return_count": 18, "stock_return_count": 18, "benchmark_return_count": 18,
    "dropped_stock_sessions": [], "dropped_benchmark_sessions": [],
    "beta": {"value": 0.8093285134496059, "sample_adequacy": "MATHEMATICALLY_COMPUTABLE", "reason": None},
    "correlation": {"value": 0.5664164065437041, "sample_adequacy": "MATHEMATICALLY_COMPUTABLE", "reason": None},
    "sample_adequacy": "MATHEMATICALLY_COMPUTABLE",
    "coverage": {"status": "complete", "paired_return_count": 18, "minimum_required": 2,
                "sample_adequacy": "MATHEMATICALLY_COMPUTABLE", "reason": None},
    "qualification_status": "CURRENT_STATE_BETA_CORRELATION_QUALIFIED",
    "warnings": ["short_observation_window_statistical_confidence_is_limited",
                "mathematically_computable_is_not_the_same_claim_as_statistically_strong",
                "descriptive_current_state_statistic_only_not_a_recommendation_or_risk_grade",
                "correlation_and_beta_are_not_evidence_of_causation",
                "current_state_only_no_point_in_time_or_backtest_authority",
                "not_wired_into_production_bundle_ranking_or_publication"],
    "provenance": {"stock_provenance": {}, "benchmark_provenance": {},
                  "contract_module": "dnse_current_state_market_risk.py", "contract_version": "1.0.0"},
    "is_actionable": False,
}

_VNM_NOT_QUALIFIED = {
    "schema_version": "1.0.0", "ticker": "VNM", "benchmark": "VNINDEX",
    "status": "not_qualified",
    "source_scope": {"stock_source": "DNSE", "benchmark_source": "DNSE",
                     "same_source_no_fallback_mixing": True, "reason": None},
    "stock_price_contract": {"price_basis": None, "price_basis_contract_version": None,
                             "qualification_scope": None},
    "benchmark_return_contract": {"index_level_unit": "index_points",
                                  "source_contract_version": "dnse_index_return_series/2026-08-10"},
    "analysis_time_semantics": (
        "current_state_using_retrospectively_adjusted_stock_history_and_current_benchmark_history"
    ),
    "pit_backtest_eligible": False,
    "input_gates": {"stock_qualified": False,
                    "stock_reason": "stock_ticker_not_qualified_for_dnse_current_state_price_analytics",
                    "benchmark_qualified": True, "benchmark_reason": None,
                    "source_scope_ok": True, "source_scope_reason": None},
    "aligned_sessions": {"aligned_pairs": [], "stock_return_count": 0, "benchmark_return_count": 0,
                         "paired_return_count": 0, "dropped_stock_sessions": [], "dropped_benchmark_sessions": []},
    "paired_return_count": 0, "stock_return_count": 0, "benchmark_return_count": 0,
    "dropped_stock_sessions": [], "dropped_benchmark_sessions": [],
    "beta": {"value": None, "sample_adequacy": None, "reason": None},
    "correlation": {"value": None, "sample_adequacy": None, "reason": None},
    "sample_adequacy": None,
    "coverage": {"status": "not_qualified",
                "reason": "stock_ticker_not_qualified_for_dnse_current_state_price_analytics"},
    "qualification_status": "CURRENT_STATE_BETA_CORRELATION_NOT_QUALIFIED",
    "warnings": ["short_observation_window_statistical_confidence_is_limited"],
    "provenance": {"stock_provenance": {}, "benchmark_provenance": {},
                  "contract_module": "dnse_current_state_market_risk.py", "contract_version": "1.0.0"},
    "is_actionable": False,
}


class CurrentStateMarketRiskPassThroughTests(unittest.TestCase):
    def test_passes_through_verbatim(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertEqual(_REAL_HPG_MARKET_RISK, context["current_state_market_risk"])

    def test_exact_beta_and_correlation_preserved(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        result = context["current_state_market_risk"]
        self.assertEqual(0.8093285134496059, result["beta"]["value"])
        self.assertEqual(0.5664164065437041, result["correlation"]["value"])

    def test_paired_return_count_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertEqual(18, context["current_state_market_risk"]["paired_return_count"])

    def test_sample_adequacy_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertEqual("MATHEMATICALLY_COMPUTABLE", context["current_state_market_risk"]["sample_adequacy"])

    def test_warnings_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertEqual(_REAL_HPG_MARKET_RISK["warnings"], context["current_state_market_risk"]["warnings"])

    def test_pit_backtest_eligible_false_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertIs(False, context["current_state_market_risk"]["pit_backtest_eligible"])

    def test_is_actionable_false_retained(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertIs(False, context["current_state_market_risk"]["is_actionable"])

    def test_not_qualified_ticker_passes_through_unchanged_no_fabricated_value(self):
        bundle = {"tickers": {"VNM": {"current_state_market_risk": copy.deepcopy(_VNM_NOT_QUALIFIED)}}}
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        result = context["current_state_market_risk"]
        self.assertEqual("not_qualified", result["status"])
        self.assertIsNone(result["beta"]["value"])
        self.assertIsNone(result["correlation"]["value"])

    def test_field_missing_remains_absent_backward_compatible(self):
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertNotIn("current_state_market_risk", context)

    def test_ticker_absent_from_bundle_entirely_remains_backward_compatible(self):
        bundle = {"tickers": {}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertNotIn("current_state_market_risk", context)

    def test_none_bundle_remains_backward_compatible(self):
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, None)
        self.assertNotIn("current_state_market_risk", context)

    def test_malformed_contract_fails_closed_locally(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": "not-a-dict"}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertEqual("malformed", context["current_state_market_risk"]["status"])
        self.assertIs(False, context["current_state_market_risk"]["is_actionable"])
        self.assertIs(False, context["current_state_market_risk"]["pit_backtest_eligible"])

    def test_malformed_input_does_not_corrupt_other_context_fields(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": "not-a-dict"}}}
        context = {"ticker": "HPG", "provenance": [], "some_other_field": "untouched"}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertEqual("untouched", context["some_other_field"])

    def test_provenance_entry_recorded(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        sources = [p.get("source_dataset") for p in context["provenance"]]
        self.assertIn("current_state_market_risk", sources)

    def test_does_not_read_or_merge_the_separate_risk_analysis_field(self):
        bundle = {"tickers": {"HPG": {
            "current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK),
            "risk_analysis": {"market_risk": {"point_in_time_beta": {"value": 1.23}}},
        }}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertNotIn("risk_analysis", context)
        self.assertNotIn("point_in_time_beta", str(context["current_state_market_risk"]))

    def test_contract_function_returns_deep_copy_not_alias(self):
        original = copy.deepcopy(_REAL_HPG_MARKET_RISK)
        bundle = {"tickers": {"HPG": {"current_state_market_risk": original}}}
        result = current_state_market_risk_contract(bundle, "HPG")
        result["status"] = "mutated"
        self.assertEqual("available", original["status"])  # source untouched

    def test_no_secret_or_credential_like_value(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        dumped = str(context["current_state_market_risk"]).lower()
        for forbidden in ("token", "secret", "signature", "authorization", "x-api-key", "cookie"):
            self.assertNotIn(forbidden, dumped)

    def test_no_volume_field_anywhere(self):
        bundle = {"tickers": {"HPG": {"current_state_market_risk": copy.deepcopy(_REAL_HPG_MARKET_RISK)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_current_state_market_risk_contract(context, bundle)
        self.assertNotIn("volume", str(context["current_state_market_risk"]).lower())


if __name__ == "__main__":
    unittest.main()
