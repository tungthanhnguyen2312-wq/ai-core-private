"""P1.5 Consumer proof: the capability matrix is copied verbatim or fails closed."""
from __future__ import annotations

import copy
import unittest

from builders import build_ticker_context as b


def _capability(status: str, *, descriptive_only: bool = False) -> dict:
    return {
        "status": status, "authority_status": status, "reason_codes": ["stable_reason"],
        "authority": "producer_authority", "trust_tier": None,
        "descriptive_only": descriptive_only, "is_actionable": False,
        "dependencies": ["upstream_contract"],
    }


def _matrix(ticker: str = "HPG") -> dict:
    return {
        "schema_version": "1.0.0", "ticker": ticker,
        "identity": {"entity_type": "corporate", "status": "available", "analysis_archetype_qualification": _capability("available")},
        "fundamental_data": {"canonical_financial_facts": _capability("available")},
        "market_descriptive": {"qualified_market_observations": _capability("descriptive_only", descriptive_only=True)},
        "market_actionable": {"current_valuation": _capability("blocked")},
        "research": {"qualified_research_brief": _capability("available")},
        "portfolio": {"allocation_eligibility": _capability("blocked_input")},
        "market_data_authority": {"market_data_track": "WAITING_EXTERNAL_ACCESS"},
        "summary": {"trust_is_capability_specific": True, "overall_status": "mixed_capability", "is_actionable": False},
        "conflicts": [], "is_actionable": False,
    }


class TickerCapabilityMatrixPassThroughTests(unittest.TestCase):
    def test_valid_matrix_passes_through_verbatim(self) -> None:
        raw = _matrix()
        context = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_ticker_capability_matrix_contract(context, {"tickers": {"HPG": {"ticker_capability_matrix": raw}}})
        self.assertEqual(context["ticker_capability_matrix"], raw)
        self.assertEqual(context["provenance"][-1]["source_dataset"], "ticker_capability_matrix")

    def test_copy_is_not_shared_and_never_infers_eligibility(self) -> None:
        raw = _matrix()
        context = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_ticker_capability_matrix_contract(context, {"tickers": {"HPG": {"ticker_capability_matrix": raw}}})
        context["ticker_capability_matrix"]["market_actionable"]["current_valuation"]["status"] = "available"
        self.assertEqual(raw["market_actionable"]["current_valuation"]["status"], "blocked")

    def test_actionable_or_ticker_mismatch_matrix_is_refused(self) -> None:
        for raw in ({**_matrix(), "is_actionable": True}, _matrix("VNM")):
            context = {"ticker": "HPG", "provenance": []}
            b.apply_bundle_ticker_capability_matrix_contract(context, {"tickers": {"HPG": {"ticker_capability_matrix": raw}}})
            self.assertEqual(context["ticker_capability_matrix"]["status"], "malformed")
            self.assertFalse(context["ticker_capability_matrix"]["is_actionable"])

    def test_unknown_capability_status_is_refused(self) -> None:
        raw = copy.deepcopy(_matrix())
        raw["market_actionable"]["current_valuation"]["status"] = "surely_actionable"
        context = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_ticker_capability_matrix_contract(context, {"tickers": {"HPG": {"ticker_capability_matrix": raw}}})
        self.assertEqual(context["ticker_capability_matrix"]["status"], "malformed")

    def test_actionable_identity_subcapability_is_refused(self) -> None:
        raw = copy.deepcopy(_matrix())
        raw["identity"]["analysis_archetype_qualification"]["is_actionable"] = True
        context = {"ticker": "HPG", "provenance": []}
        b.apply_bundle_ticker_capability_matrix_contract(context, {"tickers": {"HPG": {"ticker_capability_matrix": raw}}})
        self.assertEqual(context["ticker_capability_matrix"]["status"], "malformed")


if __name__ == "__main__":
    unittest.main()
