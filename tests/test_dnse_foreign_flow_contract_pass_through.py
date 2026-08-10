"""Consumer pass-through tests for the DNSE foreign-flow VALUE contract.

Mirrors tests/test_data_truth_contracts_pass_through.py's distribution_evidence
pattern: tickers[ticker].foreign_flow is a byte-identical pass-through of
stock-core-private/dnse_foreign_flow_store.py::build_series()'s output. Consumer
never recomputes a net value, derives an ownership/free-float percentage, or
computes a flow/trading-value ratio.
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
    apply_bundle_foreign_flow_contract,
    foreign_flow_contract,
)

# Shape-matched to the real Producer output (dnse_foreign_flow_store.build_series()),
# values from the retained 2026-08-10 pilot.
_REAL_HPG_FOREIGN_FLOW = {
    "schema_version": "1.0.0", "ticker": "HPG", "status": "available", "source": "DNSE",
    "source_contract_version": "dnse_foreign_flow/2026-08-10",
    "source_scope": "per_ticker_foreign_investor_value_flow", "point_in_time_status": "qualified",
    "latest_session": {
        "ticker": "HPG", "session_date": "2026-08-07", "observed_at": "2026-08-07 15:33:11.407",
        "foreign_buy_value_vnd": 47907362050, "foreign_sell_value_vnd": 20350730400,
        "foreign_net_value_vnd": 27556631650, "source": "DNSE",
        "source_contract_version": "dnse_foreign_flow/2026-08-10", "point_in_time_status": "qualified",
        "provenance": {"source_endpoint": "/price/HPG/foreign-trading", "board_id": "G4",
                       "exchange": "STO", "trading_session_id": "99", "query_window": None,
                       "event_scoped": {"buy_value": 2232050, "sell_value": 7490400}},
        "qualification_status": "QUALIFIED_VALUE_ONLY",
    },
    "observations": [],  # trimmed for the fixture; pass-through does not inspect its shape
    "qualified_session_count": 5, "cumulative_net_value_vnd": 431178984350,
    "cumulative_window": {"first_session": "2026-08-03", "last_session": "2026-08-07", "session_count": 5},
    "positive_session_count": 5, "negative_session_count": 0, "neutral_session_count": 0,
    "current_consecutive_net_buy_sessions": 5, "current_consecutive_net_sell_sessions": 0,
    "window_summaries": {
        "5_session": {"window_size": 5, "coverage": "complete", "reason": None,
                      "cumulative_net_value_vnd": 431178984350,
                      "sessions": ["2026-08-03", "2026-08-04", "2026-08-05", "2026-08-06", "2026-08-07"],
                      "buy_value_vnd": 706984050300, "sell_value_vnd": 275805065950},
        "10_session": {"window_size": 10, "coverage": "incomplete",
                       "reason": "only 5 qualified session(s) retained, need 10",
                       "cumulative_net_value_vnd": None, "sessions": [], "buy_value_vnd": None,
                       "sell_value_vnd": None},
    },
    "warnings": ["foreign_volume_not_represented_here_unqualified_by_contract",
                 "foreign_room_not_represented_here_unqualified_by_contract",
                 "no_ownership_or_free_float_percentage_is_derived"],
    "limitations": ["is_actionable is always false; this contract carries qualified foreign-value "
                     "flow evidence only, never an investment signal or recommendation."],
    "is_actionable": False,
}

_HPG_MISSING_STATUS = {
    "schema_version": "1.0.0", "ticker": "POW", "status": "missing", "source": "DNSE",
    "source_contract_version": "dnse_foreign_flow/2026-08-10",
    "source_scope": "per_ticker_foreign_investor_value_flow", "point_in_time_status": "not_applicable",
    "latest_session": None, "observations": [], "qualified_session_count": 0,
    "cumulative_net_value_vnd": None,
    "cumulative_window": {"first_session": None, "last_session": None, "session_count": 0},
    "positive_session_count": 0, "negative_session_count": 0, "neutral_session_count": 0,
    "current_consecutive_net_buy_sessions": 0, "current_consecutive_net_sell_sessions": 0,
    "window_summaries": {"5_session": {"window_size": 5, "coverage": "incomplete",
                                        "reason": "only 0 qualified session(s) retained, need 5",
                                        "cumulative_net_value_vnd": None, "sessions": [],
                                        "buy_value_vnd": None, "sell_value_vnd": None},
                         "10_session": {"window_size": 10, "coverage": "incomplete",
                                        "reason": "only 0 qualified session(s) retained, need 10",
                                        "cumulative_net_value_vnd": None, "sessions": [],
                                        "buy_value_vnd": None, "sell_value_vnd": None}},
    "warnings": [], "limitations": [], "is_actionable": False,
}


class ForeignFlowPassThroughTests(unittest.TestCase):
    def test_foreign_flow_passes_through_verbatim(self):
        bundle = {"tickers": {"HPG": {"foreign_flow": copy.deepcopy(_REAL_HPG_FOREIGN_FLOW)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertEqual(_REAL_HPG_FOREIGN_FLOW, context["foreign_flow"])

    def test_exact_values_and_status_preserved(self):
        bundle = {"tickers": {"HPG": {"foreign_flow": copy.deepcopy(_REAL_HPG_FOREIGN_FLOW)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        result = context["foreign_flow"]
        self.assertEqual(431178984350, result["cumulative_net_value_vnd"])
        self.assertEqual(27556631650, result["latest_session"]["foreign_net_value_vnd"])
        self.assertEqual("available", result["status"])

    def test_missing_status_ticker_passes_through_unchanged(self):
        """A ticker with status="missing" (no retained DNSE data, e.g. POW/PAN/PVD/NVL/QNS
        outside the pilot ticker set) still passes through -- Consumer never upgrades or
        hides an honest "missing" status."""
        bundle = {"tickers": {"POW": {"foreign_flow": copy.deepcopy(_HPG_MISSING_STATUS)}}}
        context = {"ticker": "POW", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertEqual("missing", context["foreign_flow"]["status"])
        self.assertIsNone(context["foreign_flow"]["cumulative_net_value_vnd"])

    def test_foreign_flow_missing_remains_absent(self):
        """Old contexts without foreign_flow (every current bundle -- opt-in only) stay
        backward compatible: no key is added, no exception is raised."""
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertNotIn("foreign_flow", context)

    def test_ticker_absent_from_bundle_entirely_remains_backward_compatible(self):
        bundle = {"tickers": {}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertNotIn("foreign_flow", context)

    def test_none_bundle_remains_backward_compatible(self):
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, None)
        self.assertNotIn("foreign_flow", context)

    def test_malformed_foreign_flow_fails_closed_locally(self):
        bundle = {"tickers": {"HPG": {"foreign_flow": "not-a-dict"}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertEqual("malformed", context["foreign_flow"]["status"])
        self.assertIs(False, context["foreign_flow"]["is_actionable"])

    def test_malformed_input_does_not_corrupt_other_context_fields(self):
        bundle = {"tickers": {"HPG": {"foreign_flow": "not-a-dict"}}}
        context = {"ticker": "HPG", "provenance": [], "some_other_field": "untouched"}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertEqual("untouched", context["some_other_field"])

    def test_no_ownership_or_free_float_percentage_field_introduced(self):
        bundle = {"tickers": {"HPG": {"foreign_flow": copy.deepcopy(_REAL_HPG_FOREIGN_FLOW)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        dumped_keys = str(context["foreign_flow"].keys())
        for forbidden in ("ownership_pct", "free_float_pct", "flow_to_turnover_ratio"):
            self.assertNotIn(forbidden, dumped_keys)

    def test_provenance_entry_recorded(self):
        bundle = {"tickers": {"HPG": {"foreign_flow": copy.deepcopy(_REAL_HPG_FOREIGN_FLOW)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        sources = [p.get("source_dataset") for p in context["provenance"]]
        self.assertIn("foreign_flow", sources)

    def test_freshness_verdict_passes_through_verbatim(self):
        """The production freshness envelope (added alongside authoritative release
        enablement) is just another field in the same verbatim pass-through -- Consumer
        never recomputes or reinterprets it."""
        with_freshness = copy.deepcopy(_REAL_HPG_FOREIGN_FLOW)
        with_freshness["freshness"] = {
            "reference_session_date": "2026-08-07", "latest_qualified_session_date": "2026-08-07",
            "sessions_behind": 0, "status": "current", "reason": None,
        }
        bundle = {"tickers": {"HPG": {"foreign_flow": with_freshness}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertEqual("current", context["foreign_flow"]["freshness"]["status"])
        self.assertEqual(0, context["foreign_flow"]["freshness"]["sessions_behind"])

    def test_stale_freshness_status_is_not_upgraded_to_current(self):
        stale = copy.deepcopy(_REAL_HPG_FOREIGN_FLOW)
        stale["freshness"] = {
            "reference_session_date": "2026-08-10", "latest_qualified_session_date": "2026-08-07",
            "sessions_behind": 1, "status": "stale",
            "reason": "retained foreign-flow data is 1 trading session(s) behind the reference session",
        }
        bundle = {"tickers": {"HPG": {"foreign_flow": stale}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_foreign_flow_contract(context, bundle)
        self.assertEqual("stale", context["foreign_flow"]["freshness"]["status"])
        self.assertEqual(1, context["foreign_flow"]["freshness"]["sessions_behind"])

    def test_foreign_flow_contract_function_returns_deep_copy_not_alias(self):
        original = copy.deepcopy(_REAL_HPG_FOREIGN_FLOW)
        bundle = {"tickers": {"HPG": {"foreign_flow": original}}}
        result = foreign_flow_contract(bundle, "HPG")
        result["status"] = "mutated"
        self.assertEqual("available", original["status"])  # source untouched


if __name__ == "__main__":
    unittest.main()
