"""Proofs for apply_bundle_qualified_market_observations_contract: verbatim pass-through,
narrow-never-widen, and no ticket for a Producer bug to leak through as actionable.
"""

from __future__ import annotations

import unittest

from builders import build_ticker_context as b

_VALID_AVAILABLE = {
    "schema_version": "1.0.0", "ticker": "HPG", "status": "available", "provider": "VCI",
    "namespace": "provider_scoped", "descriptive_only": True,
    "price_basis": {"price_basis": "empirically_event_adjusted"},
    "descriptive_price": {"latest_close": 22000.0}, "descriptive_volume": {"latest_volume": 100},
    "return_descriptors": {"window_return": 0.01}, "is_actionable": False,
    "liquidity_actionable": False, "market_dependent": False,
    "prohibited_claims": ["current_valuation"], "warnings": [],
}

_VALID_UNAVAILABLE = {
    "schema_version": "1.0.0", "ticker": "PVD", "status": "unavailable",
    "reason": "insufficient_session_history", "provider": None, "is_actionable": False,
    "liquidity_actionable": False, "descriptive_price": None, "descriptive_volume": None,
    "return_descriptors": None, "prohibited_claims": [],
}


def _bundle(ticker: str, raw) -> dict:
    return {"tickers": {ticker: {"qualified_market_observations": raw}}}


class VerbatimPassThrough(unittest.TestCase):
    def test_valid_available_passes_through_unchanged(self):
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", _VALID_AVAILABLE))
        self.assertEqual(ctx["qualified_market_observations"], _VALID_AVAILABLE)
        self.assertEqual(ctx["provenance"][-1]["source_dataset"], "qualified_market_observations")

    def test_valid_unavailable_is_not_treated_as_malformed(self):
        """An unavailable verdict is itself a valid Producer answer, not something to
        fall back from -- the same principle qualified_research_brief already follows."""
        ctx = {"ticker": "PVD", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("PVD", _VALID_UNAVAILABLE))
        self.assertEqual(ctx["qualified_market_observations"], _VALID_UNAVAILABLE)
        self.assertEqual(ctx["qualified_market_observations"]["status"], "unavailable")

    def test_no_recomputation_deepcopy_not_shared_reference(self):
        raw = dict(_VALID_AVAILABLE)
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", raw))
        ctx["qualified_market_observations"]["ticker"] = "MUTATED"
        self.assertEqual(raw["ticker"], "HPG")

    def test_absent_key_leaves_context_untouched(self):
        ctx = {"ticker": "FPT", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, {"tickers": {"FPT": {}}})
        self.assertNotIn("qualified_market_observations", ctx)


class NeverWidensAProducerVerdict(unittest.TestCase):
    def test_is_actionable_true_is_refused(self):
        bad = {**_VALID_AVAILABLE, "is_actionable": True}
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", bad))
        self.assertEqual(ctx["qualified_market_observations"]["status"], "malformed")
        self.assertFalse(ctx["qualified_market_observations"]["is_actionable"])

    def test_liquidity_actionable_true_is_refused(self):
        bad = {**_VALID_AVAILABLE, "liquidity_actionable": True}
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", bad))
        self.assertEqual(ctx["qualified_market_observations"]["status"], "malformed")

    def test_available_without_descriptive_only_marker_is_refused(self):
        bad = {k: v for k, v in _VALID_AVAILABLE.items() if k != "descriptive_only"}
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", bad))
        self.assertEqual(ctx["qualified_market_observations"]["status"], "malformed")

    def test_available_with_wrong_namespace_is_refused(self):
        bad = {**_VALID_AVAILABLE, "namespace": "generic"}
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", bad))
        self.assertEqual(ctx["qualified_market_observations"]["status"], "malformed")

    def test_ticker_mismatch_is_refused(self):
        bad = {**_VALID_AVAILABLE, "ticker": "VNM"}
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", bad))
        self.assertEqual(ctx["qualified_market_observations"]["status"], "malformed")

    def test_unknown_status_value_is_refused(self):
        bad = {**_VALID_AVAILABLE, "status": "definitely_available_trust_me"}
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", bad))
        self.assertEqual(ctx["qualified_market_observations"]["status"], "malformed")

    def test_non_mapping_raw_is_refused(self):
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", ["not", "a", "mapping"]))
        self.assertEqual(ctx["qualified_market_observations"]["status"], "malformed")

    def test_malformed_result_is_still_non_actionable(self):
        bad = {**_VALID_AVAILABLE, "is_actionable": True}
        ctx = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_qualified_market_observations_contract(ctx, _bundle("HPG", bad))
        self.assertFalse(ctx["qualified_market_observations"]["is_actionable"])
        self.assertFalse(ctx["qualified_market_observations"]["liquidity_actionable"])


if __name__ == "__main__":
    unittest.main()
