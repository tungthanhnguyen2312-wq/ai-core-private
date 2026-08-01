"""Unit tests for Consumer Data-Truth Contracts Pass-Through.

Tests propagation of Producer data-truth and AI-safety contracts into Consumer
ticker context packages:
- financial_period_coverage
- valuation_namespaces
- share_basis_identities
- earnings_anomaly
- risk_semantics
- opportunity_ranking (verbatim Producer dict including schema_version, ticker, entity_type, state, ranking_key)
- ta_signal_semantics
- news_window_semantics (nested under news_related, not top-level)
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

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

_FULL_PRODUCER_OPPORTUNITY_RANKING = {
    "schema_version": "1.0.0",
    "ticker": "PNJ",
    "entity_type": "corporate",
    "state": "available",
    "dimensions": {
        "financial_quality": {"dimension": "financial_quality", "state": "available", "facts": [], "data_warnings": [], "reason": None, "is_actionable": False},
        "valuation": {"dimension": "valuation", "state": "available", "facts": [], "data_warnings": [], "reason": None, "is_actionable": False},
        "technical_current_market_readiness": {"dimension": "technical_current_market_readiness", "state": "available", "facts": [], "data_warnings": [], "reason": None, "is_actionable": False},
        "catalyst_evidence": {"dimension": "catalyst_evidence", "state": "available", "facts": [], "data_warnings": [], "reason": None, "is_actionable": False},
        "downside_invalidation": {"dimension": "downside_invalidation", "state": "available", "facts": [], "data_warnings": [], "reason": None, "is_actionable": False},
        "data_confidence": {"dimension": "data_confidence", "state": "available", "facts": [], "data_warnings": [], "reason": None, "is_actionable": False},
    },
    "ranking_key": [{"dimension": "financial_quality", "rank": 1, "score": 0.8}],
    "facts": [],
    "data_warnings": [],
    "inferences": [],
    "hypotheses": [],
    "interpretation_limits": ["No recommendation, probability, target price, or portfolio sizing."],
}

_FULL_PRODUCER_NEWS_RELATED = {
    "status": "ok",
    "company_news_count": 3,
    "sector_news_count": 1,
    "market_news_count": 5,
    "candidate_review_count": 3,
    "lookback_days": 7,
    "cutoff": "2026-07-23T00:00:00Z",
    "items": [],
    "candidate_items": [],
    "sector_items": [],
    "market_items": [],
    "latest_published_utc": "2026-07-30T08:00:00Z",
    "mapping_version": "1.0.0",
    "latest_news_count": 3,
    "sample_titles": ["Title A"],
    "ticker_linkage_method": "canonical_alias",
    "mapping_warning": None,
    "meta": {},
    "coverage": {},
    "metric_contract_version": "1.0.0",
    "news_window_semantics": {
        "cutoff_semantics": "lookback_window_start",
        "cutoff_timestamp": "2026-07-23T00:00:00Z",
        "cutoff_interpretation": "Articles published on or after this timestamp fall within the lookback window.",
        "mapping_coverage_status": "unqualified",
        "is_no_relevant_news_claim": False,
        "is_actionable": False,
        "interpretation_limits": ["Mapping coverage is not exhaustive."],
        "latest_published_utc": "2026-07-30T08:00:00Z",
    },
}


class DataTruthContractsPassThroughTests(unittest.TestCase):
    """Consumer pass-through unit tests for data-truth contracts."""

    # ── 1. opportunity_ranking verbatim pass-through ────────────────────────

    def test_opportunity_ranking_consumer_equals_full_producer_dict(self):
        """Consumer output must equal the full Producer opportunity_ranking dict verbatim."""
        bundle = {"tickers": {"PNJ": {"opportunity_ranking": copy.deepcopy(_FULL_PRODUCER_OPPORTUNITY_RANKING)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_opportunity_ranking_contract(context, bundle)
        self.assertEqual(context["opportunity_ranking"], _FULL_PRODUCER_OPPORTUNITY_RANKING)

    def test_opportunity_ranking_preserves_schema_version_ticker_entity_type_state_ranking_key(self):
        """No semantic field or ordered value is dropped."""
        bundle = {"tickers": {"PNJ": {"opportunity_ranking": copy.deepcopy(_FULL_PRODUCER_OPPORTUNITY_RANKING)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_opportunity_ranking_contract(context, bundle)
        result = context["opportunity_ranking"]
        self.assertEqual(result["schema_version"], "1.0.0")
        self.assertEqual(result["ticker"], "PNJ")
        self.assertEqual(result["entity_type"], "corporate")
        self.assertEqual(result["state"], "available")
        self.assertEqual(result["ranking_key"], _FULL_PRODUCER_OPPORTUNITY_RANKING["ranking_key"])

    def test_opportunity_ranking_legacy_compatibility_dimensions_still_present(self):
        """Legacy fields (dimensions, facts, data_warnings, interpretation_limits) remain intact."""
        bundle = {"tickers": {"PNJ": {"opportunity_ranking": copy.deepcopy(_FULL_PRODUCER_OPPORTUNITY_RANKING)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_opportunity_ranking_contract(context, bundle)
        result = context["opportunity_ranking"]
        self.assertIn("dimensions", result)
        self.assertIn("financial_quality", result["dimensions"])
        self.assertIn("facts", result)
        self.assertIn("data_warnings", result)
        self.assertIn("interpretation_limits", result)

    def test_opportunity_ranking_missing_in_bundle_returns_fail_closed(self):
        """Missing Producer input must remain missing (fail-closed, not invented)."""
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_opportunity_ranking_contract(context, bundle)
        result = context["opportunity_ranking"]
        self.assertEqual(result.get("status"), "unknown")
        self.assertIn("opportunity_ranking_not_in_bundle", str(result.get("reason", "")))

    # ── 2. news_related / news_window_semantics verbatim pass-through ───────

    def test_news_related_news_window_semantics_equals_producer_nested_dict(self):
        """context['news_related']['news_window_semantics'] must equal the Producer nested dict verbatim."""
        bundle = {"tickers": {"POW": {"news_related": copy.deepcopy(_FULL_PRODUCER_NEWS_RELATED)}}}
        context = {"ticker": "POW", "provenance": []}
        apply_bundle_news_window_semantics_contract(context, bundle)
        self.assertIn("news_related", context)
        self.assertEqual(
            context["news_related"]["news_window_semantics"],
            _FULL_PRODUCER_NEWS_RELATED["news_window_semantics"],
        )

    def test_news_related_raw_fields_remain_unchanged(self):
        """All raw news_related fields (counts, cutoff, items, etc.) are preserved."""
        bundle = {"tickers": {"POW": {"news_related": copy.deepcopy(_FULL_PRODUCER_NEWS_RELATED)}}}
        context = {"ticker": "POW", "provenance": []}
        apply_bundle_news_window_semantics_contract(context, bundle)
        nr = context["news_related"]
        self.assertEqual(nr["company_news_count"], 3)
        self.assertEqual(nr["cutoff"], "2026-07-23T00:00:00Z")
        self.assertEqual(nr["lookback_days"], 7)
        self.assertEqual(nr["latest_published_utc"], "2026-07-30T08:00:00Z")
        self.assertEqual(nr["sample_titles"], ["Title A"])

    def test_news_window_semantics_top_level_alias_matches_nested_value(self):
        """Top-level context['news_window_semantics'] equals nested news_related.news_window_semantics."""
        bundle = {"tickers": {"POW": {"news_related": copy.deepcopy(_FULL_PRODUCER_NEWS_RELATED)}}}
        context = {"ticker": "POW", "provenance": []}
        apply_bundle_news_window_semantics_contract(context, bundle)
        self.assertEqual(
            context.get("news_window_semantics"),
            _FULL_PRODUCER_NEWS_RELATED["news_window_semantics"],
        )
        self.assertEqual(
            context.get("news_window_semantics"),
            context["news_related"]["news_window_semantics"],
        )

    def test_news_window_semantics_missing_remains_missing(self):
        """Missing news_related means no news_related and no news_window_semantics in context."""
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_news_window_semantics_contract(context, bundle)
        self.assertNotIn("news_related", context)
        self.assertNotIn("news_window_semantics", context)

    # ── 3. Missing optional contracts remain missing ─────────────────────────

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
        self.assertNotIn("news_related", context)
        self.assertNotIn("news_window_semantics", context)

    # ── 4. Malformed data does not corrupt unrelated context ─────────────────

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

    def test_malformed_opportunity_ranking_fails_closed_without_corrupting_context(self):
        bundle = {"tickers": {"TEST": {"opportunity_ranking": "not_a_dict"}}}
        context = {"ticker": "TEST", "provenance": [], "metadata": {"ticker": "TEST"}}
        apply_bundle_opportunity_ranking_contract(context, bundle)
        result = context["opportunity_ranking"]
        self.assertEqual(result.get("status"), "unknown")
        self.assertEqual(context["metadata"]["ticker"], "TEST")

    # ── 5. Non-actionable and fail-closed states ─────────────────────────────

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

    # ── 6. All other Phase 3C contracts remain unchanged ─────────────────────

    def test_all_present_phase3c_contracts_pass_through_unchanged(self):
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
                    "risk_semantics": {
                        "volatility_status": "unverified",
                        "is_actionable": False,
                    },
                    "opportunity_ranking": copy.deepcopy(_FULL_PRODUCER_OPPORTUNITY_RANKING),
                    "news_related": copy.deepcopy(_FULL_PRODUCER_NEWS_RELATED),
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
        self.assertEqual(context["risk_semantics"]["volatility_status"], "unverified")
        # opportunity_ranking verbatim
        self.assertEqual(context["opportunity_ranking"], _FULL_PRODUCER_OPPORTUNITY_RANKING)
        # news_related verbatim (including nested news_window_semantics)
        self.assertEqual(context["news_related"], _FULL_PRODUCER_NEWS_RELATED)
        self.assertEqual(
            context["news_related"]["news_window_semantics"],
            _FULL_PRODUCER_NEWS_RELATED["news_window_semantics"],
        )
        self.assertEqual(
            context.get("news_window_semantics"),
            _FULL_PRODUCER_NEWS_RELATED["news_window_semantics"],
        )


if __name__ == "__main__":
    unittest.main()
