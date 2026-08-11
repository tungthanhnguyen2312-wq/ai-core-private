"""Consumer pass-through tests for the current_state_relative_valuation contract.

Mirrors tests/test_current_state_market_risk_contract_pass_through.py's pattern:
tickers[ticker].current_state_relative_valuation is a byte-identical pass-through of
stock-core-private/current_state_relative_valuation.py's
evaluate_current_state_relative_valuation() output (plus the bundle-level
"status"/"is_actionable" fields export_ai_bundle.py's attach layer adds). Consumer
never recomputes a price, a share count, a multiple, or a comparability verdict.
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
    apply_bundle_current_state_relative_valuation_contract,
    current_state_relative_valuation_contract,
)

# Shape-matched to the real Producer output, real values from a live run against
# dashboard-runtime on 2026-08-11 (this milestone): HPG's current DNSE price qualifies,
# but official-evidence current-share coverage does not yet reach that session, so
# every method is unavailable -- not a fabricated multiple.
_REAL_HPG_NOT_QUALIFIED = {
    "schema_version": "1.0.0", "ticker": "HPG", "source": "DNSE",
    "as_of_semantics": "current_market_price_on_qualified_historical_fundamentals",
    "formula_version": "current_state_relative_valuation_v1_current_price_x_official_current_shares",
    "is_actionable": False,
    "eligibility": {"ticker": "HPG", "eligible_for_current_state_price_analytics": True,
                    "status": "QUALIFIED_FOR_DNSE_CURRENT_STATE_PRICE_ANALYTICS"},
    "current_price": {"qualified": True, "as_of_session": "2026-08-07", "value_vnd": 22000.0,
                      "price_basis": "ADJUSTED_CONFIRMED"},
    "current_shares": {"bridge_result": {"status": "blocked",
                                         "current_shares": {"value": None, "qualified": False,
                                                            "reason": "opening_identity_unqualified"}},
                       "opening_identity_diagnostic": {"reason": "official_evidence_share_basis_unverifiable"}},
    "methods": {
        name: {
            "method": name, "state": "unavailable", "observed_value": None,
            "missing_inputs": ["qualified_current_shares_outstanding_for_session"],
            "is_actionable": False, "warnings": [], "limitations": [],
        }
        for name in ("market_cap", "pe", "pb", "ps", "enterprise_value", "ev_sales", "ev_ebitda")
    },
    "historical_comparison": {"status": "incomparable", "reasons": ["current_metric_unavailable"], "comparisons": {}},
    "warnings": [], "limitations": [],
    "status": "not_qualified",
}

_VNM_NOT_QUALIFIED = {
    "schema_version": "1.0.0", "ticker": "VNM", "source": "DNSE",
    "as_of_semantics": "current_market_price_on_qualified_historical_fundamentals",
    "formula_version": "current_state_relative_valuation_v1_current_price_x_official_current_shares",
    "is_actionable": False,
    "eligibility": {"ticker": "VNM", "eligible_for_current_state_price_analytics": False,
                    "status": "NOT_QUALIFIED_FOR_DNSE_PRICE_ANALYTICS"},
    "current_price": None, "current_shares": None,
    "methods": {
        name: {"method": name, "state": "unavailable", "observed_value": None,
               "missing_inputs": ["qualified_current_price", "qualified_current_shares_outstanding_for_session"],
               "is_actionable": False, "warnings": [], "limitations": []}
        for name in ("market_cap", "pe", "pb", "ps", "enterprise_value", "ev_sales", "ev_ebitda")
    },
    "historical_comparison": {"status": "incomparable", "reasons": ["current_metric_unavailable"], "comparisons": {}},
    "warnings": [], "limitations": [],
    "status": "not_qualified",
}


def _bundle(ticker: str, payload: dict) -> dict:
    return {"tickers": {ticker: {"current_state_relative_valuation": payload}}}


class PassThroughShapeTests(unittest.TestCase):
    def test_absent_field_returns_none(self):
        self.assertIsNone(current_state_relative_valuation_contract({"tickers": {"HPG": {}}}, "HPG"))
        self.assertIsNone(current_state_relative_valuation_contract(None, "HPG"))
        self.assertIsNone(current_state_relative_valuation_contract({}, "HPG"))

    def test_qualified_ticker_passes_through_byte_identical(self):
        bundle = _bundle("HPG", copy.deepcopy(_REAL_HPG_NOT_QUALIFIED))
        result = current_state_relative_valuation_contract(bundle, "HPG")
        self.assertEqual(_REAL_HPG_NOT_QUALIFIED, result)

    def test_result_is_a_deep_copy_not_the_same_object(self):
        payload = copy.deepcopy(_REAL_HPG_NOT_QUALIFIED)
        bundle = _bundle("HPG", payload)
        result = current_state_relative_valuation_contract(bundle, "HPG")
        result["methods"]["pe"]["state"] = "available"
        self.assertEqual("unavailable", payload["methods"]["pe"]["state"])

    def test_not_qualified_ticker_passes_through_verbatim_never_upgraded(self):
        bundle = _bundle("VNM", copy.deepcopy(_VNM_NOT_QUALIFIED))
        result = current_state_relative_valuation_contract(bundle, "VNM")
        self.assertEqual("not_qualified", result["status"])
        for method in result["methods"].values():
            self.assertEqual("unavailable", method["state"])
            self.assertIsNone(method["observed_value"])

    def test_malformed_non_mapping_fails_closed(self):
        bundle = _bundle("HPG", "not a mapping at all")
        result = current_state_relative_valuation_contract(bundle, "HPG")
        self.assertEqual("malformed", result["status"])
        self.assertIs(False, result["is_actionable"])

    def test_wrong_ticker_fails_closed(self):
        payload = copy.deepcopy(_REAL_HPG_NOT_QUALIFIED)  # ticker field says HPG
        bundle = {"tickers": {"VNM": {"current_state_relative_valuation": payload}}}
        result = current_state_relative_valuation_contract(bundle, "VNM")
        self.assertEqual("malformed", result["status"])

    def test_is_actionable_true_on_raw_input_fails_closed(self):
        payload = copy.deepcopy(_REAL_HPG_NOT_QUALIFIED)
        payload["is_actionable"] = True  # a Producer bug should never reach the Consumer as "actionable"
        bundle = _bundle("HPG", payload)
        result = current_state_relative_valuation_contract(bundle, "HPG")
        self.assertEqual("malformed", result["status"])

    def test_method_level_is_actionable_true_fails_closed(self):
        payload = copy.deepcopy(_REAL_HPG_NOT_QUALIFIED)
        payload["methods"]["pe"]["is_actionable"] = True
        bundle = _bundle("HPG", payload)
        result = current_state_relative_valuation_contract(bundle, "HPG")
        self.assertEqual("malformed", result["status"])

    def test_methods_not_a_mapping_fails_closed(self):
        payload = copy.deepcopy(_REAL_HPG_NOT_QUALIFIED)
        payload["methods"] = "not a mapping"
        bundle = _bundle("HPG", payload)
        result = current_state_relative_valuation_contract(bundle, "HPG")
        self.assertEqual("malformed", result["status"])


class ApplyBundleContractTests(unittest.TestCase):
    def test_apply_sets_context_key_and_provenance(self):
        context: dict = {"ticker": "HPG"}
        bundle = _bundle("HPG", copy.deepcopy(_REAL_HPG_NOT_QUALIFIED))
        apply_bundle_current_state_relative_valuation_contract(context, bundle)
        self.assertIn("current_state_relative_valuation", context)
        self.assertEqual("not_qualified", context["current_state_relative_valuation"]["status"])
        sources = [p["source_dataset"] for p in context["provenance"]]
        self.assertIn("current_state_relative_valuation", sources)

    def test_apply_is_noop_when_field_absent(self):
        context: dict = {"ticker": "HPG"}
        apply_bundle_current_state_relative_valuation_contract(context, {"tickers": {"HPG": {}}})
        self.assertNotIn("current_state_relative_valuation", context)
        self.assertEqual([], context.get("provenance", []))

    def test_apply_never_touches_relative_valuation_or_ticker_capability_matrix(self):
        context: dict = {
            "ticker": "HPG",
            "relative_valuation": {"methods": {"pe": {"state": "unavailable"}}, "status": "unknown"},
            "ticker_capability_matrix": {"market_actionable": {"current_valuation": {"status": "blocked"}}},
        }
        before_relative = copy.deepcopy(context["relative_valuation"])
        before_matrix = copy.deepcopy(context["ticker_capability_matrix"])
        bundle = _bundle("HPG", copy.deepcopy(_REAL_HPG_NOT_QUALIFIED))
        apply_bundle_current_state_relative_valuation_contract(context, bundle)
        self.assertEqual(before_relative, context["relative_valuation"])
        self.assertEqual(before_matrix, context["ticker_capability_matrix"])


class NoFabricatedClaimsTests(unittest.TestCase):
    """Structural proof that a not-qualified pass-through can never carry a numeric
    multiple or an implicit conclusion."""

    def test_unavailable_methods_carry_no_numeric_value(self):
        result = current_state_relative_valuation_contract(
            _bundle("HPG", copy.deepcopy(_REAL_HPG_NOT_QUALIFIED)), "HPG",
        )
        for method in result["methods"].values():
            if method["state"] != "available":
                self.assertIsNone(method["observed_value"])

    def test_incomparable_historical_comparison_carries_no_comparisons(self):
        result = current_state_relative_valuation_contract(
            _bundle("HPG", copy.deepcopy(_REAL_HPG_NOT_QUALIFIED)), "HPG",
        )
        self.assertEqual("incomparable", result["historical_comparison"]["status"])
        self.assertTrue(result["historical_comparison"]["reasons"])


if __name__ == "__main__":
    unittest.main()
