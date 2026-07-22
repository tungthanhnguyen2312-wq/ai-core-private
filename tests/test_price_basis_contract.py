"""Pure Phase 2 tests for consuming Phase 1 price-basis bundle metadata."""

from __future__ import annotations

import json
import unittest
from argparse import Namespace
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from builders import build_ticker_context as builder


def context() -> dict:
    return {
        "ticker": "TEST",
        "price_summary": {},
        "data_quality": {"flags": [], "warnings": [], "not_fully_confirmed": []},
        "provenance": [],
    }


class PriceBasisConsumerTests(unittest.TestCase):
    def test_adjusted_verified_propagates_without_unverified_warning(self):
        result = builder.apply_bundle_price_basis_contract(context(), {
            "price_basis": "adjusted", "price_basis_verified": True,
            "price_basis_provenance": {"source": "verified_contract"},
        })
        self.assertEqual(result["price_summary"]["price_basis"], "adjusted")
        self.assertTrue(result["price_summary"]["price_basis_verified"])
        self.assertFalse(any(flag["code"] == builder.PRICE_BASIS_UNVERIFIED_CODE
                             for flag in result["data_quality"]["flags"]))

    def test_raw_verified_propagates_without_unverified_warning(self):
        result = builder.apply_bundle_price_basis_contract(context(), {
            "price_basis": "raw", "price_basis_verified": True,
        })
        self.assertEqual(result["price_summary"]["price_basis"], "raw")
        self.assertTrue(result["price_summary"]["price_basis_verified"])
        self.assertFalse(result["data_quality"]["flags"])

    def test_unknown_unverified_adds_quality_flag_and_ai_warning(self):
        result = builder.apply_bundle_price_basis_contract(context(), {
            "price_basis": "unknown", "price_basis_verified": False,
        })
        self.assertEqual(result["price_summary"]["price_basis"], "unknown")
        self.assertFalse(result["price_summary"]["price_basis_verified"])
        flag = next(flag for flag in result["data_quality"]["flags"]
                    if flag["code"] == builder.PRICE_BASIS_UNVERIFIED_CODE)
        self.assertEqual(flag["severity"], "warning")
        self.assertIn("return, MA, and RS", flag["message"])

    def test_legacy_missing_contract_defaults_safely(self):
        result = builder.apply_bundle_price_basis_contract(context(), {})
        self.assertEqual(result["price_summary"]["price_basis"], "unknown")
        self.assertFalse(result["price_summary"]["price_basis_verified"])
        self.assertEqual(result["price_summary"]["price_basis_provenance"]["source"],
                         "missing_or_unverified_bundle_price_basis")

    def test_invalid_values_do_not_become_raw_or_adjusted(self):
        for payload in (
            {"price_basis": "split_adjusted", "price_basis_verified": True},
            {"price_basis": "raw", "price_basis_verified": False},
            {"price_basis": "adjusted", "price_basis_verified": "true"},
        ):
            contract = builder.normalize_price_basis_contract(payload)
            self.assertEqual(contract["price_basis"], "unknown")
            self.assertFalse(contract["price_basis_verified"])

    def test_verified_basis_removes_stale_unverified_flag(self):
        payload = context()
        payload["data_quality"]["flags"] = [{"code": builder.PRICE_BASIS_UNVERIFIED_CODE}]
        result = builder.apply_bundle_price_basis_contract(payload, {
            "price_basis": "raw", "price_basis_verified": True,
        })
        self.assertFalse(any(flag.get("code") == builder.PRICE_BASIS_UNVERIFIED_CODE
                             for flag in result["data_quality"]["flags"]))

    def test_context_serialization_keeps_canonical_contract(self):
        result = builder.apply_bundle_price_basis_contract(context(), {
            "price_basis": "adjusted", "price_basis_verified": True,
            "price_basis_provenance": {"source": "verified_contract"},
        })
        restored = json.loads(json.dumps(result, allow_nan=False))
        self.assertIn(restored["price_summary"]["price_basis"], builder.PRICE_BASIS_VALUES)
        self.assertIsInstance(restored["price_summary"]["price_basis_verified"], bool)


class PriceBasisWorkflowTests(unittest.TestCase):
    def _load_from_temp(self, content: str | None, filename: str = "analysis_bundle.json"):
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            if content is not None:
                (root / filename).write_text(content, encoding="utf-8")
            with patch.object(builder, "WORKSPACE_ROOT", root):
                return builder.load_optional_analysis_bundle({"source_paths": {"analysis_bundle": filename}})

    def test_loader_reads_adjusted_and_raw_contracts(self):
        for basis in ("adjusted", "raw"):
            payload, warning = self._load_from_temp(json.dumps({
                "price_basis": basis, "price_basis_verified": True,
            }))
            self.assertIsNone(warning)
            self.assertEqual(payload["price_basis"], basis)

    def test_loader_keeps_unknown_and_legacy_payloads_for_safe_normalization(self):
        unknown, warning = self._load_from_temp(json.dumps({
            "price_basis": "unknown", "price_basis_verified": False,
        }))
        self.assertIsNone(warning)
        self.assertEqual(builder.normalize_price_basis_contract(unknown)["price_basis"], "unknown")

        legacy, warning = self._load_from_temp(json.dumps({"schema_version": "1.0.0"}))
        self.assertIsNone(warning)
        self.assertFalse(builder.normalize_price_basis_contract(legacy)["price_basis_verified"])

    def test_loader_falls_back_for_missing_and_malformed_json(self):
        payload, warning = self._load_from_temp(None)
        self.assertEqual(payload, {})
        self.assertEqual(warning, "analysis_bundle_missing")

        payload, warning = self._load_from_temp("{")
        self.assertEqual(payload, {})
        self.assertEqual(warning, "analysis_bundle_invalid_json")

    def test_entry_point_passes_loaded_bundle_to_context_builder(self):
        args = Namespace(
            positional_ticker="TEST", ticker=[], tickers=None, output=None,
            dry_run=None, strict=None, validate_profile=None,
            coverage_report_json=None, coverage_report_markdown=None,
        )
        config = {
            "dry_run_default": True, "strict_mode_default": False, "max_batch_size": 10,
            "context_template_path": "context_packages/ticker_context_template.json",
            "default_output_dir": "exports/context_packages",
        }
        captured: dict = {}

        def build_context(*_args, **kwargs):
            captured.update(kwargs)
            return {
                "ticker": "TEST", "data_quality": {"warnings": [], "missing_sections": []},
                "price_summary": {}, "financial_summary": {}, "technical_summary": {},
                "news_summary": {}, "shareholder_summary": {}, "provenance": [{}],
            }

        validation = {"valid": True, "errors": [], "profile_valid": True, "schema_valid": True}
        with patch.object(builder, "_parse_args", return_value=args), \
             patch.object(builder, "load_json", side_effect=[config, {}]), \
             patch.object(builder, "load_summary_layer", return_value={}), \
             patch.object(builder, "load_optional_analysis_bundle", return_value=({"price_basis": "adjusted", "price_basis_verified": True}, None)), \
             patch.object(builder, "build_context_package", side_effect=build_context), \
             patch.object(builder, "validate_context", return_value=validation), \
             patch.object(builder, "validate_safe_output_path", return_value=Path("ignored.json")):
            self.assertEqual(builder.main(), 0)
        self.assertEqual(captured["bundle_payload"]["price_basis"], "adjusted")
        self.assertIsNone(captured["bundle_load_warning"])


if __name__ == "__main__":
    unittest.main()
