from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures"
sys.path.insert(0, str(ROOT))

from builders.context_coverage import (  # noqa: E402
    ProfileConfigError, calculate_section_coverage, load_config, validate_config, validate_profile,
)


CONFIG = ROOT / "validation" / "context_validation_profiles.json"


class ContextRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.config = load_config(CONFIG)
        cls.context = json.loads((FIXTURES / "regression" / "pan_context.json").read_text(encoding="utf-8"))

    def test_context_partial_is_not_full_valid(self):
        report = validate_profile(self.context, "valuation", self.config)
        self.assertEqual(report["overall_status"], "partial")
        self.assertFalse(report["profile_valid"])

    def test_valuation_profile_blocks_missing_ocf(self):
        report = validate_profile(self.context, "valuation", self.config)
        ocf = [item for item in report["blocking_missing"] if item.get("metric") == "operating_cash_flow"]
        self.assertEqual(len(ocf), 1)
        self.assertEqual(ocf[0]["status"], "source_empty")

    def test_not_applicable_does_not_reduce_coverage(self):
        result = calculate_section_coverage([
            {"metric": "revenue", "status": "reported"},
            {"metric": "sga", "status": "not_applicable"},
        ], self.config["profiles"]["forensic"])
        self.assertEqual(result["coverage"], 1.0)
        self.assertEqual(result["expected_metrics"], 1)

    def test_mutation_valuation_ocf_config_removed_is_rejected(self):
        mutated = copy.deepcopy(self.config)
        mutated["profiles"]["valuation"]["blocking_metrics"].remove("cash_flow.operating_cash_flow")
        with self.assertRaisesRegex(ProfileConfigError, "must block missing metric"):
            validate_config(mutated)

    def test_pan_context_validation_golden(self):
        report = validate_profile(self.context, "valuation", self.config)
        ocf = next(item for item in report["blocking_missing"] if item.get("metric") == "operating_cash_flow")
        actual = {
            "ticker": report["ticker"],
            "validation_profile": report["validation_profile"],
            "profile_valid": report["profile_valid"],
            "overall_status": report["overall_status"],
            "overall_coverage": report["overall_coverage"],
            "cash_flow_coverage": report["coverage"]["cash_flow"]["coverage"],
            "ocf_blocking_status": ocf["status"],
            "ocf_blocking_reason": ocf["reason"],
        }
        expected = json.loads((FIXTURES / "expected" / "pan_context_validation.json").read_text(encoding="utf-8"))
        self.assertEqual(actual, expected)

    def test_coverage_threshold_regression(self):
        report = validate_profile(self.context, "valuation", self.config)
        self.assertGreaterEqual(report["overall_coverage"], 0.90)
        self.assertEqual(report["minimum_overall_coverage"], 0.70)

    def test_fixture_is_deterministic(self):
        first = validate_profile(copy.deepcopy(self.context), "valuation", self.config)
        second = validate_profile(copy.deepcopy(self.context), "valuation", self.config)
        self.assertEqual(first, second)


if __name__ == "__main__":
    unittest.main()
