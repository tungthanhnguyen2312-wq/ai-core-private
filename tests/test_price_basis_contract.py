"""Unit tests for Consumer Price and Volume Basis Metadata Integration.

Tests propagation of Producer-qualified price and volume basis metadata into Consumer
ticker context packages, backward compatibility, non-mixing enforcement, and provenance.
"""

from __future__ import annotations

import unittest
from pathlib import Path
import sys

WORKTREE = Path(__file__).resolve().parent.parent
if str(WORKTREE) not in sys.path:
    sys.path.insert(0, str(WORKTREE))

# Imported through the package path, not by putting `builders/` on sys.path: a bare
# `import build_ticker_context` creates a SECOND module object distinct from
# `builders.build_ticker_context`, and every exception class it defines or imports is
# then a different class. That made `except SnapshotError` miss in
# test_metadata_registry_shadow_compare whenever these modules were collected first --
# a suite that passed alone and failed together.

from builders.build_ticker_context import (
    apply_bundle_price_basis_contract,
    normalize_price_basis_contract,
    validate_context_basis_compatibility,
)


class ConsumerPriceBasisIntegrationTests(unittest.TestCase):
    def test_raw_basis_propagation(self):
        bundle = {
            "price_basis": "raw",
            "price_basis_verified": True,
            "volume_basis": "raw_shares_traded",
            "volume_basis_verified": True,
            "adjustment_source": "upstream_vci",
            "effective_date": "2026-07-28",
            "limitations": [],
        }
        contract = normalize_price_basis_contract(bundle)
        self.assertEqual(contract["price_basis"], "raw")
        self.assertTrue(contract["price_basis_verified"])
        self.assertTrue(contract["is_actionable"])
        self.assertEqual(contract["volume_basis"], "raw_shares_traded")
        self.assertEqual(contract["adjustment_source"], "upstream_vci")

    def test_adjusted_basis_propagation(self):
        bundle = {
            "price_basis": "adjusted",
            "price_basis_verified": True,
            "volume_basis": "raw_shares_traded",
            "volume_basis_verified": True,
            "adjustment_source": "corporate_actions_pipeline",
            "effective_date": "2026-07-28",
            "limitations": [],
        }
        contract = normalize_price_basis_contract(bundle)
        self.assertEqual(contract["price_basis"], "adjusted")
        self.assertTrue(contract["price_basis_verified"])
        self.assertTrue(contract["is_actionable"])
        self.assertEqual(contract["volume_basis"], "raw_shares_traded")

    def test_unknown_or_missing_basis_fails_closed(self):
        # Missing or unverified bundle returns unknown & non-actionable
        bundle = {"price_basis": "raw", "price_basis_verified": False}
        contract = normalize_price_basis_contract(bundle)
        self.assertEqual(contract["price_basis"], "unknown")
        self.assertFalse(contract["price_basis_verified"])
        self.assertFalse(contract["is_actionable"])
        self.assertIsNone(contract["adjustment_source"])
        self.assertEqual(contract["volume_basis"], "unknown")
        self.assertFalse(contract["volume_basis_verified"])
        self.assertTrue(len(contract["limitations"]) > 0)

    def test_volume_basis_requires_explicit_valid_basis_and_true_verification(self):
        missing_verification = normalize_price_basis_contract({"volume_basis": "raw_shares_traded"})
        string_verification = normalize_price_basis_contract({
            "volume_basis": "raw_shares_traded", "volume_basis_verified": "true",
        })
        for contract in (missing_verification, string_verification):
            self.assertEqual(contract["volume_basis"], "unknown")
            self.assertFalse(contract["volume_basis_verified"])

    def test_independent_volume_basis_handling(self):
        bundle = {
            "price_basis": "adjusted",
            "price_basis_verified": True,
            "volume_basis": "raw_shares_traded",
            "volume_basis_verified": True,
        }
        contract = normalize_price_basis_contract(bundle)
        self.assertEqual(contract["price_basis"], "adjusted")
        self.assertEqual(contract["volume_basis"], "raw_shares_traded")
        self.assertTrue(contract["volume_basis_verified"])

    def test_provenance_preservation(self):
        context = {"ticker": "HPG"}
        bundle = {
            "price_basis": "raw",
            "price_basis_verified": True,
            "volume_basis": "raw_shares_traded",
            "volume_basis_verified": True,
            "price_basis_provenance": {"provider": "VCI"},
            "limitations": [],
        }
        updated = apply_bundle_price_basis_contract(context, bundle)
        self.assertEqual(updated["price_summary"]["price_basis"], "raw")
        self.assertEqual(updated["price_summary"]["volume_basis"], "raw_shares_traded")
        prov_entry = next((p for p in updated["provenance"] if p.get("source_dataset") == "price_basis_contract"), None)
        self.assertIsNotNone(prov_entry)
        self.assertEqual(prov_entry["price_basis"], "raw")
        self.assertEqual(prov_entry["volume_basis"], "raw_shares_traded")

    def test_incompatible_basis_rejection(self):
        context_raw = {"price_summary": {"price_basis": "raw", "price_basis_verified": True}}
        context_adj = {"price_summary": {"price_basis": "adjusted", "price_basis_verified": True}}

        with self.assertRaises(ValueError):
            validate_context_basis_compatibility(context_raw, context_adj, strict=True)

        compat = validate_context_basis_compatibility(context_raw, context_adj, strict=False)
        self.assertFalse(compat["is_compatible"])
        self.assertEqual(compat["reason"], "mixed_raw_and_adjusted_basis")

    def test_old_context_compatibility(self):
        # Empty bundle / legacy context
        context = {"ticker": "SSI"}
        updated = apply_bundle_price_basis_contract(context, {})
        self.assertEqual(updated["price_summary"]["price_basis"], "unknown")
        self.assertFalse(updated["price_summary"]["price_basis_verified"])
        self.assertEqual(updated["price_summary"]["volume_basis"], "unknown")
        self.assertFalse(updated["price_summary"]["volume_basis_verified"])
        self.assertIn("OHLCV volume basis", updated["data_quality"]["not_fully_confirmed"])

    def test_deterministic_repeated_output(self):
        bundle = {
            "price_basis": "raw",
            "price_basis_verified": True,
            "volume_basis": "raw_shares_traded",
            "volume_basis_verified": True,
        }
        c1 = normalize_price_basis_contract(bundle)
        c2 = normalize_price_basis_contract(bundle)
        self.assertEqual(c1, c2)


if __name__ == "__main__":
    unittest.main()
