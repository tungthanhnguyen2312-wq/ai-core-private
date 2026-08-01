"""Unit tests for Consumer Data-Truth Contracts Pass-Through.

Tests propagation of Producer data-truth and AI-safety contracts into Consumer
ticker context packages:
- financial_period_coverage
- valuation_namespaces
- share_basis_identities
- earnings_anomaly
- risk_semantics
- opportunity_ranking
- ta_signal_semantics
- news_window_semantics
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BUILDERS_DIR = ROOT / "builders"
if str(BUILDERS_DIR) not in sys.path:
    sys.path.insert(0, str(BUILDERS_DIR))

from build_ticker_context import (
    apply_bundle_earnings_anomaly_contract,
    apply_bundle_financial_period_coverage_contract,
    apply_bundle_news_window_semantics_contract,
    apply_bundle_opportunity_ranking_contract,
    apply_bundle_risk_semantics_contract,
    apply_bundle_share_basis_identities_contract,
    apply_bundle_ta_signal_semantics_contract,
    apply_bundle_valuation_namespaces_contract,
)


class DataTruthContractsPassThroughTests(unittest.TestCase):
    """Consumer pass-through unit tests for data-truth contracts."""

    def test_all_present_contracts_pass_through_unchanged(self):
        bundle = {
            "tickers": {
                "PNJ": {
                    "financial_period_coverage": {
                        "latest_raw_period": "2026-Q1",
                        "latest_calendar_eligible_period": "2026-Q1",
                        "is_actionable": False,
                    },
                    "valuation_namespaces": {
                        "live_vendor": {"pe": 11.98},
                        "historical_calculated": {"pe": 10.55},
                        "comparability": {"is_actionable": False},
                    },
                    "share_basis_identities": {
                        "current_market": {"value": 334000000},
                        "financial_period_end": {"value": 330000000},
                        "comparability": {"is_actionable": False},
                    },
                    "earnings_anomaly": {
                        "status": "anomaly_observed",
                        "trigger": "profit_after_tax_exceeds_revenue",
                        "explanation_status": "insufficient_statement_detail",
                        "is_actionable": False,
                    },
                    "ta_signal_semantics": {
                        "rsi14": {"qualification_status": "qualified"},
                        "is_actionable": False,
                    },
                    "news_window_semantics": {
                        "window_type": "standard_7d",
                        "is_actionable": False,
                    },
                    "risk_semantics": {
                        "volatility_status": "unverified",
                        "is_actionable": False,
                    },
                    "opportunity_ranking": {
                        "state": "available",
                        "dimensions": {
                            "financial_quality": {"state": "available"},
                            "valuation": {"state": "available"},
                            "technical_current_market_readiness": {"state": "available"},
                            "catalyst_evidence": {"state": "available"},
                            "downside_invalidation": {"state": "available"},
                            "data_confidence": {"state": "available"},
                        },
                        "facts": [{"rank": 1}],
                        "data_warnings": [],
                        "inferences": [],
                        "hypotheses": [],
                        "interpretation_limits": ["No recommendation, probability, target price, or portfolio sizing."],
                        "is_actionable": False,
                    },
                }
            }
        }
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_valuation_namespaces_contract(context, bundle)
        apply_bundle_share_basis_identities_contract(context, bundle)
        apply_bundle_earnings_anomaly_contract(context, bundle)
        apply_bundle_ta_signal_semantics_contract(context, bundle)
        apply_bundle_news_window_semantics_contract(context, bundle)
        apply_bundle_risk_semantics_contract(context, bundle)
        apply_bundle_opportunity_ranking_contract(context, bundle)

        self.assertEqual(context["financial_period_coverage"]["latest_raw_period"], "2026-Q1")
        self.assertEqual(context["valuation_namespaces"]["live_vendor"]["pe"], 11.98)
        self.assertEqual(context["share_basis_identities"]["current_market"]["value"], 334000000)
        self.assertEqual(context["earnings_anomaly"]["status"], "anomaly_observed")
        self.assertEqual(context["ta_signal_semantics"]["rsi14"]["qualification_status"], "qualified")
        self.assertEqual(context["news_window_semantics"]["window_type"], "standard_7d")
        self.assertEqual(context["risk_semantics"]["volatility_status"], "unverified")
        self.assertEqual(context["opportunity_ranking"]["status"], "available")

    def test_missing_contracts_preserve_legacy_compatibility(self):
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}

        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_valuation_namespaces_contract(context, bundle)
        apply_bundle_share_basis_identities_contract(context, bundle)
        apply_bundle_earnings_anomaly_contract(context, bundle)
        apply_bundle_ta_signal_semantics_contract(context, bundle)
        apply_bundle_news_window_semantics_contract(context, bundle)
        apply_bundle_risk_semantics_contract(context, bundle)

        self.assertNotIn("financial_period_coverage", context)
        self.assertNotIn("valuation_namespaces", context)
        self.assertNotIn("share_basis_identities", context)
        self.assertNotIn("earnings_anomaly", context)

    def test_null_and_unavailable_states_are_not_promoted(self):
        bundle = {
            "tickers": {
                "NVL": {
                    "earnings_anomaly": {
                        "status": "anomaly_observed",
                        "explanation_status": "insufficient_statement_detail",
                        "data_quality_status": "source_values_observed_verification_unavailable",
                        "is_actionable": False,
                    }
                }
            }
        }
        context = {"ticker": "NVL", "provenance": []}
        apply_bundle_earnings_anomaly_contract(context, bundle)
        contract = context["earnings_anomaly"]
        self.assertEqual(contract["explanation_status"], "insufficient_statement_detail")
        self.assertEqual(contract["data_quality_status"], "source_values_observed_verification_unavailable")
        self.assertFalse(contract["is_actionable"])

    def test_malformed_optional_contract_data_does_not_corrupt_unrelated_context(self):
        bundle = {
            "tickers": {
                "TEST": {
                    "financial_period_coverage": "invalid_string_not_dict",
                    "earnings_anomaly": ["invalid_list"],
                }
            }
        }
        context = {"ticker": "TEST", "provenance": [], "metadata": {"ticker": "TEST"}}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_earnings_anomaly_contract(context, bundle)

        self.assertEqual(context["financial_period_coverage"]["coverage_status"], "malformed")
        self.assertEqual(context["earnings_anomaly"]["status"], "malformed")
        self.assertEqual(context["metadata"]["ticker"], "TEST")

    def test_non_actionable_fields_remain_non_actionable(self):
        bundle = {
            "tickers": {
                "PNJ": {
                    "share_basis_identities": {
                        "comparability": {"pairs": {}, "is_actionable": False},
                        "is_actionable": False,
                    }
                }
            }
        }
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_share_basis_identities_contract(context, bundle)
        self.assertFalse(context["share_basis_identities"]["is_actionable"])


if __name__ == "__main__":
    unittest.main()
