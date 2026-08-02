from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builders.historical_fundamental_brief_response import validate_historical_only_output


def brief(ticker="HPG"):
    return {
        "ticker": ticker, "reporting_period": "2024", "statement_scope": "consolidated",
        "publication_timestamp": "2025-03-24", "currency": "VND", "scale": 1,
        "provenance_references": {"capital_structure": "historical_capital_structure"},
        "historical_only": True, "market_dependent": False,
        "facts": [{"identity": "net_debt", "value": 1}],
        "data_warnings": ["price_basis_unknown_or_unverified", "volume_basis_unknown_or_unverified", "current_shares_unqualified"],
        "supported_inferences": [{"statement": "Net debt was positive.", "supporting_metrics": ["historical_capital_structure.net_debt"]}],
        "hypotheses": [], "missing_evidence": ["current qualified price basis is required"],
        "invalidation_conditions": ["scope change invalidates this brief"],
    }


class HistoricalFundamentalBriefResponseTests(unittest.TestCase):
    def test_valid_hpg_and_vnm_outputs_are_accepted_exactly(self):
        for ticker in ("HPG", "VNM"):
            canonical = brief(ticker)
            result = validate_historical_only_output(json.dumps(canonical), canonical)
            self.assertEqual(result["status"], "accepted")
            self.assertEqual(result["accepted_output"], canonical)

    def test_missing_or_wrong_category_fails_closed(self):
        for mutation in (lambda value: value.pop("facts"), lambda value: value.__setitem__("facts", {})):
            output = brief(); mutation(output)
            self.assertEqual(validate_historical_only_output(output, brief())["status"], "rejected")

    def test_unsupported_fact_hypothesis_or_removed_warning_is_rejected(self):
        for mutate in (
            lambda value: value["facts"].append({"identity": "unsupported", "value": 99}),
            lambda value: value["hypotheses"].append("new hypothesis"),
            lambda value: value.__setitem__("data_warnings", value["data_warnings"][1:]),
        ):
            output = brief(); mutate(output)
            self.assertEqual(validate_historical_only_output(output, brief())["status"], "rejected")

    def test_prohibited_claims_and_free_form_fail_closed_deterministically(self):
        output = brief(); output["supported_inferences"][0]["statement"] = "Buy because momentum is positive."
        first = validate_historical_only_output(output, brief())
        self.assertEqual(first, validate_historical_only_output(output, brief()))
        self.assertEqual(first["status"], "rejected")
        self.assertEqual(validate_historical_only_output("free form response", brief())["status"], "rejected")

    def test_readiness_and_lane_fields_cannot_be_added(self):
        output = brief(); output["analysis_readiness"] = "ready"; output["analysis_lane_eligibility"] = ["eligible"]
        self.assertEqual(validate_historical_only_output(output, brief())["status"], "rejected")


if __name__ == "__main__":
    unittest.main()
