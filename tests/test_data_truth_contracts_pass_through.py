"""Unit tests for Consumer Data-Truth Contracts Pass-Through.

Tests propagation of Producer data-truth and AI-safety contracts into Consumer
ticker context packages:
- financial_period_coverage
- valuation_namespaces
- share_basis_identities
- earnings_anomaly
- risk_semantics (canonical nested tickers[ticker].analysis_score.risk_semantics, with a
  legacy top-level tickers[ticker].risk_semantics fallback used only when canonical is absent)
- opportunity_ranking (verbatim Producer dict including schema_version, ticker, entity_type, state, ranking_key)
- ta_signal_semantics
- news_window_semantics (nested under news_related, not top-level)
- analysis_lane_eligibility (optional Phase 4B/4C lane-eligibility result list, verbatim
  pass-through; absent in every current bundle -- legacy-compatible by construction)
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Imported through the package path, not by putting `builders/` on sys.path: a bare
# `import build_ticker_context` creates a SECOND module object distinct from
# `builders.build_ticker_context`, and every exception class it defines or imports is
# then a different class. That made `except SnapshotError` miss in
# test_metadata_registry_shadow_compare whenever these modules were collected first --
# a suite that passed alone and failed together.

from builders.build_ticker_context import (
    apply_bundle_analysis_lane_eligibility_contract,
    apply_bundle_distribution_evidence_contract,
    apply_bundle_earnings_anomaly_contract,
    apply_bundle_financial_period_coverage_contract,
    apply_bundle_fundamental_quality_evidence_contract,
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
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)

        self.assertNotIn("financial_period_coverage", context)
        self.assertNotIn("valuation_namespaces", context)
        self.assertNotIn("share_basis_identities", context)
        self.assertNotIn("earnings_anomaly", context)
        self.assertNotIn("news_related", context)
        self.assertNotIn("news_window_semantics", context)
        self.assertNotIn("risk_semantics", context)
        self.assertNotIn("analysis_lane_eligibility", context)

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

    # ── 7. risk_semantics canonical nested path (analysis_score.risk_semantics) ──

    _CANONICAL_RISK_SEMANTICS = {
        "legacy_field": "risk",
        "legacy_field_ambiguity": "The field name 'risk' is legacy nomenclature and must not be interpreted as higher-means-more-risk.",
        "polarity": "higher_is_safer",
        "score_value": 100,
        "interpretation": "100 means no configured penalty flags were triggered (maximum configured safety score). 0 means all penalty flags were triggered.",
        "limitations": [
            "100 means no configured penalty flags were triggered; it is not a calibrated probability of loss.",
            "It is not an investment-attractiveness score.",
        ],
        "is_actionable": False,
    }

    def test_risk_semantics_nested_canonical_passes_through_verbatim(self):
        """context['risk_semantics'] must equal the full nested analysis_score.risk_semantics dict verbatim."""
        bundle = {
            "tickers": {
                "HPG": {
                    "analysis_score": {
                        "session_date": "2026-Q1", "regime": "neutral", "values": {"risk": 100},
                        "risk_semantics": copy.deepcopy(self._CANONICAL_RISK_SEMANTICS),
                    },
                }
            }
        }
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_risk_semantics_contract(context, bundle)
        self.assertEqual(context["risk_semantics"], self._CANONICAL_RISK_SEMANTICS)

    def test_risk_semantics_canonical_nested_overrides_conflicting_legacy_top_level(self):
        """When both a canonical nested and a conflicting legacy top-level value are present,
        the canonical nested value must win."""
        legacy_conflicting = {
            "legacy_field": "risk", "legacy_field_ambiguity": "stale copy", "polarity": "higher_is_safer",
            "score_value": 0, "interpretation": "stale legacy copy", "limitations": [], "is_actionable": False,
        }
        bundle = {
            "tickers": {
                "HPG": {
                    "risk_semantics": legacy_conflicting,
                    "analysis_score": {"risk_semantics": copy.deepcopy(self._CANONICAL_RISK_SEMANTICS)},
                }
            }
        }
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_risk_semantics_contract(context, bundle)
        self.assertEqual(context["risk_semantics"], self._CANONICAL_RISK_SEMANTICS)
        self.assertEqual(context["risk_semantics"]["score_value"], 100)

    def test_risk_semantics_legacy_top_level_fallback_when_canonical_absent(self):
        """A legacy top-level risk_semantics is still honored when analysis_score.risk_semantics
        is absent (backward-compatible fallback only, not the canonical source)."""
        legacy_only = {
            "legacy_field": "risk", "legacy_field_ambiguity": "...", "polarity": "higher_is_safer",
            "score_value": 55, "interpretation": "...", "limitations": [], "is_actionable": False,
        }
        bundle = {"tickers": {"HPG": {"risk_semantics": legacy_only}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_risk_semantics_contract(context, bundle)
        self.assertEqual(context["risk_semantics"], legacy_only)

    def test_risk_semantics_missing_from_both_locations_remains_missing(self):
        bundle = {
            "tickers": {
                "HPG": {
                    "analysis_score": {"session_date": "2026-Q1", "regime": None, "values": None, "risk_semantics": None},
                }
            }
        }
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_risk_semantics_contract(context, bundle)
        self.assertNotIn("risk_semantics", context)

    def test_risk_semantics_malformed_canonical_fails_closed_without_corrupting_context(self):
        bundle = {"tickers": {"TEST": {"analysis_score": {"risk_semantics": "not_a_dict"}}}}
        context = {"ticker": "TEST", "provenance": [], "metadata": {"ticker": "TEST"}}
        apply_bundle_risk_semantics_contract(context, bundle)
        self.assertEqual(context["risk_semantics"]["status"], "malformed")
        self.assertEqual(context["metadata"]["ticker"], "TEST")

    def test_risk_semantics_preserves_all_required_subfields(self):
        bundle = {"tickers": {"HPG": {"analysis_score": {"risk_semantics": copy.deepcopy(self._CANONICAL_RISK_SEMANTICS)}}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_risk_semantics_contract(context, bundle)
        result = context["risk_semantics"]
        for field in ("legacy_field", "legacy_field_ambiguity", "polarity", "score_value", "interpretation", "limitations", "is_actionable"):
            self.assertIn(field, result)
        self.assertEqual(result["polarity"], "higher_is_safer")
        self.assertEqual(result["score_value"], 100)
        self.assertFalse(result["is_actionable"])

    def test_analysis_score_structure_unchanged_by_risk_semantics_read(self):
        """Reading risk_semantics must not mutate the source analysis_score dict in the bundle."""
        analysis_score = {
            "session_date": "2026-Q1", "regime": "neutral", "values": {"risk": 100},
            "risk_semantics": copy.deepcopy(self._CANONICAL_RISK_SEMANTICS),
        }
        original_analysis_score = copy.deepcopy(analysis_score)
        bundle = {"tickers": {"HPG": {"analysis_score": analysis_score}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_risk_semantics_contract(context, bundle)
        self.assertEqual(bundle["tickers"]["HPG"]["analysis_score"], original_analysis_score)

    # ── 8. analysis_lane_eligibility (Phase 4B/4C) verbatim pass-through ─────

    # Real Phase 4C shadow-evaluation result for PNJ, taken verbatim from
    # operations-review/phase_4c_lane_shadow_20260801T081307Z/lane_results.json
    # ("tickers[ticker].analysis_lane_eligibility" is not wired into any Producer bundle
    # yet -- this is the exact list shape a future Producer milestone would place there).
    # Chosen over another ticker specifically because its real blocked_avoid result is
    # eligible_for_analysis, needed to test that this is preserved as a classification only.
    _REAL_PNJ_LANE_ELIGIBILITY = json.loads(r'''
    [{"lane": "quality_growth", "status": "insufficient_evidence", "eligible": false, "blocking_reasons": ["entity_type_unknown"], "data_warnings": ["adjusted_return_claims_blocked:price_basis='unknown':tickers.PNJ.price_basis_provenance.price_basis", "liquidity_claims_blocked:volume_basis='unknown':tickers.PNJ.price_basis_provenance.volume_basis", "backtest_claims_blocked:price_or_volume_basis_unverified:tickers.PNJ.price_basis_provenance", "valuation_change_claims_blocked:pe:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pe", "valuation_change_claims_blocked:pb:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pb", "ta_signal_present_not_a_signal:Presence of a TA signal record indicates signal availability, not an investment action or complete technical conclusion.", "zero_or_partial_news_mapping_is_not_a_no_news_claim"], "required_evidence": ["confirmed corporate entity_type"], "supporting_paths": ["tickers.PNJ.entity_type"], "limitations": ["entity_type is unknown/unclassified; corporate quality/growth framing is not confirmed applicable.", "risk_semantics, opportunity_ranking, ta_signal_semantics, and news_window_semantics are evidence-availability / fail-closed metadata, not investment signals; this evaluator's evidence-availability ordering must not be read as investment attractiveness (Phase 4A Principles 1 and 5; Phase 4B gates 6 and 9)."], "is_actionable": false}, {"lane": "income_defensive", "status": "insufficient_evidence", "eligible": false, "blocking_reasons": ["distribution_evidence_contract_not_available_to_this_evaluator", "share_basis_identity_not_available:current_vs_period_end", "share_basis_identity_not_available:current_vs_weighted_average", "share_basis_identity_not_available:period_end_vs_weighted_average"], "data_warnings": ["entity_type_unknown", "risk_semantics_present_no_safety_threshold_defined_yet", "adjusted_return_claims_blocked:price_basis='unknown':tickers.PNJ.price_basis_provenance.price_basis", "liquidity_claims_blocked:volume_basis='unknown':tickers.PNJ.price_basis_provenance.volume_basis", "backtest_claims_blocked:price_or_volume_basis_unverified:tickers.PNJ.price_basis_provenance", "valuation_change_claims_blocked:pe:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pe", "valuation_change_claims_blocked:pb:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pb", "ta_signal_present_not_a_signal:Presence of a TA signal record indicates signal availability, not an investment action or complete technical conclusion.", "zero_or_partial_news_mapping_is_not_a_no_news_claim"], "required_evidence": ["corporate_action_distribution_evidence (not a named input to this milestone)"], "supporting_paths": ["tickers.PNJ.entity_type", "tickers.PNJ.risk_semantics", "tickers.PNJ.share_basis_identities", "tickers.PNJ.financial_period_coverage"], "limitations": ["income_defensive eligibility fundamentally requires distribution/dividend evidence, which is not among the ten Phase 4A/4B named input contracts; this result never reaches eligible_for_analysis in this milestone.", "risk_semantics.score_value polarity is higher_is_safer (legacy field name 'risk' must not be read as higher-means-more-risk); no safety threshold is defined yet, so this evaluator does not classify the numeric value.", "risk_semantics, opportunity_ranking, ta_signal_semantics, and news_window_semantics are evidence-availability / fail-closed metadata, not investment signals; this evaluator's evidence-availability ordering must not be read as investment attractiveness (Phase 4A Principles 1 and 5; Phase 4B gates 6 and 9)."], "is_actionable": false}, {"lane": "structural_catalyst", "status": "insufficient_evidence", "eligible": false, "blocking_reasons": ["opportunity_ranking_dimension_state:unknown"], "data_warnings": ["adjusted_return_claims_blocked:price_basis='unknown':tickers.PNJ.price_basis_provenance.price_basis", "liquidity_claims_blocked:volume_basis='unknown':tickers.PNJ.price_basis_provenance.volume_basis", "backtest_claims_blocked:price_or_volume_basis_unverified:tickers.PNJ.price_basis_provenance", "valuation_change_claims_blocked:pe:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pe", "valuation_change_claims_blocked:pb:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pb", "ta_signal_present_not_a_signal:Presence of a TA signal record indicates signal availability, not an investment action or complete technical conclusion.", "zero_or_partial_news_mapping_is_not_a_no_news_claim"], "required_evidence": ["opportunity_ranking.dimensions.catalyst_evidence"], "supporting_paths": ["tickers.PNJ.opportunity_ranking.dimensions.catalyst_evidence"], "limitations": ["Catalyst *evidence-availability* only; naming or tagging an actual catalyst against the Phase 4A Section 5 taxonomy is a separate, not-yet-implemented step.", "risk_semantics, opportunity_ranking, ta_signal_semantics, and news_window_semantics are evidence-availability / fail-closed metadata, not investment signals; this evaluator's evidence-availability ordering must not be read as investment attractiveness (Phase 4A Principles 1 and 5; Phase 4B gates 6 and 9)."], "is_actionable": false}, {"lane": "distressed_high_risk", "status": "insufficient_evidence", "eligible": false, "blocking_reasons": ["no_evidenced_stress_signal_found"], "data_warnings": ["risk_semantics present but no safety threshold is defined in this milestone; not used to trigger or exclude this lane.", "adjusted_return_claims_blocked:price_basis='unknown':tickers.PNJ.price_basis_provenance.price_basis", "liquidity_claims_blocked:volume_basis='unknown':tickers.PNJ.price_basis_provenance.volume_basis", "backtest_claims_blocked:price_or_volume_basis_unverified:tickers.PNJ.price_basis_provenance", "valuation_change_claims_blocked:pe:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pe", "valuation_change_claims_blocked:pb:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pb", "ta_signal_present_not_a_signal:Presence of a TA signal record indicates signal availability, not an investment action or complete technical conclusion.", "zero_or_partial_news_mapping_is_not_a_no_news_claim"], "required_evidence": [], "supporting_paths": ["tickers.PNJ.risk_semantics.score_value"], "limitations": ["risk_semantics.score_value polarity is higher_is_safer (legacy field name 'risk' must not be read as higher-means-more-risk).", "risk_semantics, opportunity_ranking, ta_signal_semantics, and news_window_semantics are evidence-availability / fail-closed metadata, not investment signals; this evaluator's evidence-availability ordering must not be read as investment attractiveness (Phase 4A Principles 1 and 5; Phase 4B gates 6 and 9)."], "is_actionable": false}, {"lane": "blocked_avoid", "status": "eligible_for_analysis", "eligible": true, "blocking_reasons": [], "data_warnings": ["blocked_avoid_trigger:entity_type_unknown", "adjusted_return_claims_blocked:price_basis='unknown':tickers.PNJ.price_basis_provenance.price_basis", "liquidity_claims_blocked:volume_basis='unknown':tickers.PNJ.price_basis_provenance.volume_basis", "backtest_claims_blocked:price_or_volume_basis_unverified:tickers.PNJ.price_basis_provenance", "valuation_change_claims_blocked:pe:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pe", "valuation_change_claims_blocked:pb:insufficient_identity:tickers.PNJ.valuation_namespaces.comparability.metrics.pb", "ta_signal_present_not_a_signal:Presence of a TA signal record indicates signal availability, not an investment action or complete technical conclusion.", "zero_or_partial_news_mapping_is_not_a_no_news_claim"], "required_evidence": [], "supporting_paths": ["tickers.PNJ.entity_type"], "limitations": ["blocked_avoid membership reflects evidence insufficiency, not a judgment on the underlying company; a caller integrating this evaluator should treat blocked_avoid eligibility as overriding membership in the other four lanes for the same ticker/cutoff -- this pure per-lane evaluator does not enforce that override itself.", "risk_semantics, opportunity_ranking, ta_signal_semantics, and news_window_semantics are evidence-availability / fail-closed metadata, not investment signals; this evaluator's evidence-availability ordering must not be read as investment attractiveness (Phase 4A Principles 1 and 5; Phase 4B gates 6 and 9)."], "is_actionable": false}]
    ''')

    def test_analysis_lane_eligibility_passes_through_verbatim(self):
        """A complete five-lane contract must pass through byte-identical."""
        bundle = {"tickers": {"PNJ": {"analysis_lane_eligibility": copy.deepcopy(self._REAL_PNJ_LANE_ELIGIBILITY)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        self.assertEqual(context["analysis_lane_eligibility"], self._REAL_PNJ_LANE_ELIGIBILITY)

    def test_analysis_lane_eligibility_statuses_and_supporting_paths_unchanged(self):
        bundle = {"tickers": {"PNJ": {"analysis_lane_eligibility": copy.deepcopy(self._REAL_PNJ_LANE_ELIGIBILITY)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        result = context["analysis_lane_eligibility"]
        self.assertEqual([r["lane"] for r in result], [r["lane"] for r in self._REAL_PNJ_LANE_ELIGIBILITY])
        for expected, actual in zip(self._REAL_PNJ_LANE_ELIGIBILITY, result):
            self.assertEqual(actual["status"], expected["status"])
            self.assertEqual(actual["supporting_paths"], expected["supporting_paths"])

    def test_analysis_lane_eligibility_is_actionable_false_for_every_lane(self):
        bundle = {"tickers": {"PNJ": {"analysis_lane_eligibility": copy.deepcopy(self._REAL_PNJ_LANE_ELIGIBILITY)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        for lane_result in context["analysis_lane_eligibility"]:
            self.assertIs(lane_result["is_actionable"], False)

    def test_blocked_avoid_eligible_remains_classification_not_recommendation(self):
        """blocked_avoid.status == eligible_for_analysis must not be reinterpreted as a
        recommendation; the module's own disclaiming limitation text must survive verbatim,
        and no score/rank/recommendation field is added alongside it."""
        bundle = {"tickers": {"PNJ": {"analysis_lane_eligibility": copy.deepcopy(self._REAL_PNJ_LANE_ELIGIBILITY)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        blocked_avoid = next(r for r in context["analysis_lane_eligibility"] if r["lane"] == "blocked_avoid")
        self.assertEqual(blocked_avoid["status"], "eligible_for_analysis")
        self.assertTrue(blocked_avoid["eligible"])
        self.assertFalse(blocked_avoid["is_actionable"])
        self.assertTrue(any("not a judgment on the underlying company" in lim for lim in blocked_avoid["limitations"]))
        self.assertEqual(set(blocked_avoid.keys()), {
            "lane", "status", "eligible", "blocking_reasons", "data_warnings",
            "required_evidence", "supporting_paths", "limitations", "is_actionable",
        })

    def test_analysis_lane_eligibility_no_score_or_ranking_fields_introduced(self):
        """No universal score or ticker ranking is created by the pass-through; lane order
        is preserved exactly as supplied (never re-sorted by any derived attractiveness)."""
        bundle = {"tickers": {"PNJ": {"analysis_lane_eligibility": copy.deepcopy(self._REAL_PNJ_LANE_ELIGIBILITY)}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        result = context["analysis_lane_eligibility"]
        self.assertIsInstance(result, list)
        for lane_result in result:
            self.assertNotIn("score", lane_result)
            self.assertNotIn("rank", lane_result)
            self.assertNotIn("recommendation", lane_result)
        self.assertEqual(
            [r["lane"] for r in result],
            ["quality_growth", "income_defensive", "structural_catalyst", "distressed_high_risk", "blocked_avoid"],
        )

    def test_analysis_lane_eligibility_missing_remains_absent(self):
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        self.assertNotIn("analysis_lane_eligibility", context)

    def test_analysis_lane_eligibility_malformed_fails_closed_without_corrupting_context(self):
        bundle = {"tickers": {"TEST": {"analysis_lane_eligibility": "not_a_list"}}}
        context = {"ticker": "TEST", "provenance": [], "metadata": {"ticker": "TEST"}}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        self.assertEqual(context["analysis_lane_eligibility"]["status"], "malformed")
        self.assertEqual(context["metadata"]["ticker"], "TEST")

    def test_analysis_lane_eligibility_does_not_disturb_existing_data_truth_contracts(self):
        bundle = {
            "tickers": {
                "PNJ": {
                    "financial_period_coverage": {"latest_raw_period": "2026-Q1", "is_actionable": False},
                    "earnings_anomaly": {"status": "not_observed", "is_actionable": False},
                    "analysis_lane_eligibility": copy.deepcopy(self._REAL_PNJ_LANE_ELIGIBILITY),
                }
            }
        }
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_earnings_anomaly_contract(context, bundle)
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        self.assertEqual(context["financial_period_coverage"]["latest_raw_period"], "2026-Q1")
        self.assertEqual(context["earnings_anomaly"]["status"], "not_observed")
        self.assertIn("analysis_lane_eligibility", context)

    def test_analysis_lane_eligibility_source_input_not_mutated(self):
        source_list = copy.deepcopy(self._REAL_PNJ_LANE_ELIGIBILITY)
        original = copy.deepcopy(source_list)
        bundle = {"tickers": {"PNJ": {"analysis_lane_eligibility": source_list}}}
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        context["analysis_lane_eligibility"][0]["status"] = "mutated_for_test"
        self.assertEqual(source_list, original)
        self.assertEqual(bundle["tickers"]["PNJ"]["analysis_lane_eligibility"], original)

    def test_analysis_lane_eligibility_legacy_bundle_without_field_unaffected(self):
        """Legacy bundles (no analysis_lane_eligibility key at all -- every current real
        bundle) must keep building all other contracts normally with no such key added."""
        bundle = {
            "tickers": {
                "PNJ": {
                    "financial_period_coverage": {"latest_raw_period": "2026-Q1", "is_actionable": False},
                }
            }
        }
        context = {"ticker": "PNJ", "provenance": []}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_analysis_lane_eligibility_contract(context, bundle)
        self.assertEqual(context["financial_period_coverage"]["latest_raw_period"], "2026-Q1")
        self.assertNotIn("analysis_lane_eligibility", context)

    # ── 9. distribution_evidence (Phase 5D) verbatim pass-through ────────────

    # Shape matches stock-core-private/distribution_evidence.py::build_distribution_evidence_for_ticker()
    # exactly (schema_version, ticker, coverage_status, cash_distributions, non_cash_distributions,
    # latest_cash_distribution, qualified_cash_event_count, covered_periods, history_status,
    # blocking_reasons, limitations, provenance, is_actionable) -- not wired into any Producer
    # bundle by default (opt-in only), so this is legacy-compatible by construction.
    _REAL_VNM_DISTRIBUTION_EVIDENCE = {
        "schema_version": "1.0.0", "ticker": "VNM", "coverage_status": "available",
        "cash_distributions": [
            {"event_id": "e2024", "distribution_type": "cash_distribution", "ticker": "VNM",
             "issuer": "Vietnam Dairy Products Joint Stock Company", "declaration_date": "2024-12-05",
             "record_date": "2024-12-27", "ex_date": None, "payment_date": "2025-02-28",
             "effective_date": None, "amount": 500, "currency": "VND", "unit": "per_share",
             "per_share_basis": "common", "event_status": "completed",
             "source_authority": "KPMG Limited Vietnam / Issuer IR Portal",
             "evidence": {"evidence_id": "ev1", "citation_id": "c1", "document_sha256": "abc123"},
             "qualification_state": "qualified", "ledger_entry_id": "le1"},
            {"event_id": "e2023", "distribution_type": "cash_distribution", "ticker": "VNM",
             "issuer": "Vietnam Dairy Products Joint Stock Company", "declaration_date": "2023-08-10",
             "record_date": "2023-09-05", "ex_date": None, "payment_date": "2023-10-20",
             "effective_date": None, "amount": 1500, "currency": "VND", "unit": "per_share",
             "per_share_basis": "common", "event_status": "completed",
             "source_authority": "KPMG Limited Vietnam / Issuer IR Portal",
             "evidence": {"evidence_id": "ev1", "citation_id": "c2", "document_sha256": "abc123"},
             "qualification_state": "qualified", "ledger_entry_id": "le2"},
        ],
        "non_cash_distributions": [
            {"event_id": "e2021", "distribution_type": "stock_dividend", "ticker": "VNM",
             "issuer": "Vietnam Dairy Products Joint Stock Company", "declaration_date": "2021-06-15",
             "record_date": "2021-07-20", "ex_date": None, "distribution_date": None, "effective_date": None,
             "entitlement_ratio": {"new_shares": 1, "existing_shares": 10, "ratio_float": 0.1},
             "funding_source": "undistributed_earnings", "share_class": "common", "event_status": "completed",
             "source_authority": "KPMG Limited Vietnam / Issuer IR Portal",
             "evidence": {"evidence_id": "ev1", "citation_id": "c3", "document_sha256": "abc123"},
             "qualification_state": "qualified", "ledger_entry_id": "le3"},
        ],
        "latest_cash_distribution": {"event_id": "e2024", "record_date": "2024-12-27", "amount": 500},
        "qualified_cash_event_count": 2, "covered_periods": ["2023", "2024"],
        "history_status": "multi_period_available", "blocking_reasons": [],
        "limitations": ["No dividend yield, payout ratio, CAGR, total return, or adjusted return is derived by this contract."],
        "provenance": {"source": "corporate_action_ledger.build_corporate_action_ledger", "ledger_version": "1.0.0"},
        "is_actionable": False,
    }

    def test_distribution_evidence_passes_through_verbatim(self):
        bundle = {"tickers": {"VNM": {"distribution_evidence": copy.deepcopy(self._REAL_VNM_DISTRIBUTION_EVIDENCE)}}}
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_distribution_evidence_contract(context, bundle)
        self.assertEqual(context["distribution_evidence"], self._REAL_VNM_DISTRIBUTION_EVIDENCE)

    def test_distribution_evidence_cash_and_non_cash_lists_unchanged(self):
        bundle = {"tickers": {"VNM": {"distribution_evidence": copy.deepcopy(self._REAL_VNM_DISTRIBUTION_EVIDENCE)}}}
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_distribution_evidence_contract(context, bundle)
        result = context["distribution_evidence"]
        self.assertEqual(len(result["cash_distributions"]), 2)
        self.assertEqual(len(result["non_cash_distributions"]), 1)
        self.assertEqual(result["cash_distributions"][0]["distribution_type"], "cash_distribution")
        self.assertEqual(result["non_cash_distributions"][0]["distribution_type"], "stock_dividend")

    def test_distribution_evidence_is_actionable_false(self):
        bundle = {"tickers": {"VNM": {"distribution_evidence": copy.deepcopy(self._REAL_VNM_DISTRIBUTION_EVIDENCE)}}}
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_distribution_evidence_contract(context, bundle)
        self.assertIs(context["distribution_evidence"]["is_actionable"], False)

    def test_distribution_evidence_no_yield_payout_or_return_field_introduced(self):
        """Consumer pass-through must not add or compute any derived income metric."""
        bundle = {"tickers": {"VNM": {"distribution_evidence": copy.deepcopy(self._REAL_VNM_DISTRIBUTION_EVIDENCE)}}}
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_distribution_evidence_contract(context, bundle)
        result = context["distribution_evidence"]
        for forbidden in ("dividend_yield", "yield", "payout_ratio", "cagr", "total_return", "adjusted_return"):
            self.assertNotIn(forbidden, result)

    def test_distribution_evidence_missing_remains_absent(self):
        bundle = {"tickers": {"HPG": {}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_distribution_evidence_contract(context, bundle)
        self.assertNotIn("distribution_evidence", context)

    def test_distribution_evidence_hpg_missing_coverage_status_passes_through(self):
        """HPG negative-control shape: coverage_status='missing' passes through unchanged --
        Consumer never upgrades or reinterprets it."""
        hpg_missing = {
            "schema_version": "1.0.0", "ticker": "HPG", "coverage_status": "missing",
            "cash_distributions": [], "non_cash_distributions": [], "latest_cash_distribution": None,
            "qualified_cash_event_count": 0, "covered_periods": [], "history_status": "no_qualified_events",
            "blocking_reasons": [], "limitations": [], "provenance": {}, "is_actionable": False,
        }
        bundle = {"tickers": {"HPG": {"distribution_evidence": copy.deepcopy(hpg_missing)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_distribution_evidence_contract(context, bundle)
        self.assertEqual(context["distribution_evidence"], hpg_missing)

    def test_distribution_evidence_malformed_fails_closed_without_corrupting_context(self):
        bundle = {"tickers": {"TEST": {"distribution_evidence": "not_a_dict"}}}
        context = {"ticker": "TEST", "provenance": [], "metadata": {"ticker": "TEST"}}
        apply_bundle_distribution_evidence_contract(context, bundle)
        self.assertEqual(context["distribution_evidence"]["status"], "malformed")
        self.assertEqual(context["metadata"]["ticker"], "TEST")

    def test_distribution_evidence_does_not_disturb_existing_data_truth_contracts(self):
        bundle = {
            "tickers": {
                "VNM": {
                    "financial_period_coverage": {"latest_raw_period": "2024", "is_actionable": False},
                    "earnings_anomaly": {"status": "not_observed", "is_actionable": False},
                    "distribution_evidence": copy.deepcopy(self._REAL_VNM_DISTRIBUTION_EVIDENCE),
                }
            }
        }
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_earnings_anomaly_contract(context, bundle)
        apply_bundle_distribution_evidence_contract(context, bundle)
        self.assertEqual(context["financial_period_coverage"]["latest_raw_period"], "2024")
        self.assertEqual(context["earnings_anomaly"]["status"], "not_observed")
        self.assertIn("distribution_evidence", context)

    def test_distribution_evidence_source_input_not_mutated(self):
        source = copy.deepcopy(self._REAL_VNM_DISTRIBUTION_EVIDENCE)
        original = copy.deepcopy(source)
        bundle = {"tickers": {"VNM": {"distribution_evidence": source}}}
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_distribution_evidence_contract(context, bundle)
        context["distribution_evidence"]["coverage_status"] = "mutated_for_test"
        context["distribution_evidence"]["cash_distributions"].append({"injected": True})
        self.assertEqual(source, original)
        self.assertEqual(bundle["tickers"]["VNM"]["distribution_evidence"], original)

    def test_distribution_evidence_legacy_bundle_without_field_unaffected(self):
        """Legacy bundles (no distribution_evidence key at all -- every current real bundle)
        must keep building all other contracts normally with no such key added."""
        bundle = {
            "tickers": {
                "VNM": {
                    "financial_period_coverage": {"latest_raw_period": "2024", "is_actionable": False},
                }
            }
        }
        context = {"ticker": "VNM", "provenance": []}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_distribution_evidence_contract(context, bundle)
        self.assertEqual(context["financial_period_coverage"]["latest_raw_period"], "2024")
        self.assertNotIn("distribution_evidence", context)

    # ── 10. fundamental_quality_evidence (Phase 6A) verbatim pass-through ────

    # Shape matches stock-core-private/fundamental_quality_evidence.py::
    # build_fundamental_quality_evidence_for_ticker() exactly. Distinct field from the
    # separate, always-present legacy "fundamental_quality" multi-model dict -- not wired
    # into any Producer bundle by default (opt-in only), so this is legacy-compatible by
    # construction.
    _REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE = {
        "schema_version": "1.0.0", "ticker": "HPG", "model": "earnings_quality_cash_conversion",
        "model_version": "1.0.0", "status": "available", "applicability": "applicable",
        "reporting_period": "2024", "statement_scope": "consolidated",
        "inputs": [
            {"canonical_field_identity": "operating_cash_flow", "ticker": "HPG", "reporting_period": "2024",
             "reporting_frequency": "annual", "statement_scope": "consolidated", "currency": "VND", "scale": 1,
             "observation_id": ["a486f2957b63bef716a8db6ae33a46bb539306256976bc866e1da5fee5845282"],
             "citation_id": "11ac48d5cb813ac6e531bf51f3baf652914683c15ed03140a1227ebc31c9b642",
             "evidence_id": "a7c3711d1b02c131a87fef4a0f5bd4d5fbd780bbb0c07665111a358a2ddcd2a8",
             "source_hash": "304a93a65e1587f625e0045d6ec9bcfba6647d19df4034cfd8fc1ec7b62eeb64",
             "qualification_status": "qualified", "rejection_reason": None},
            {"canonical_field_identity": "net_income", "ticker": "HPG", "reporting_period": "2024",
             "reporting_frequency": "annual", "statement_scope": "consolidated", "currency": "VND", "scale": 1,
             "observation_id": ["176f95f0873710e18ab6dd3cb65b337d53746e11da708796657ee65016bc5ebe"],
             "citation_id": "802d2394d85e6eb065133976f2f4530fcc31fed9feea1dcdcc5f1882e0e7c763",
             "evidence_id": "a7c3711d1b02c131a87fef4a0f5bd4d5fbd780bbb0c07665111a358a2ddcd2a8",
             "source_hash": "304a93a65e1587f625e0045d6ec9bcfba6647d19df4034cfd8fc1ec7b62eeb64",
             "qualification_status": "qualified", "rejection_reason": None},
        ],
        "metrics": {"cash_conversion_ratio": 0.5497110617765166, "operating_cash_flow_less_net_income": -5413123180859},
        "data_warnings": [], "blocking_reasons": [],
        "limitations": ["This contract reports a single-period cash-conversion ratio and accrual gap only."],
        "provenance": {"source": "financial_canonical", "evidence_manifest_path": "data/official-evidence/manifest.json"},
        "is_actionable": False,
    }

    def test_fundamental_quality_evidence_passes_through_verbatim(self):
        bundle = {"tickers": {"HPG": {"fundamental_quality_evidence": copy.deepcopy(self._REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertEqual(context["fundamental_quality_evidence"], self._REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE)

    def test_fundamental_quality_evidence_distinct_from_legacy_fundamental_quality_field(self):
        """The new opt-in contract must never read, overwrite, or merge with the separate,
        always-present legacy fundamental_quality multi-model field."""
        legacy = {"schema_version": "1.2.0", "entity_type": "corporate", "models": {"dupont_roe": {"score_or_value": 0.1}}}
        bundle = {"tickers": {"HPG": {
            "fundamental_quality": copy.deepcopy(legacy),
            "fundamental_quality_evidence": copy.deepcopy(self._REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE),
        }}}
        context = {"ticker": "HPG", "provenance": [], "fundamental_quality": copy.deepcopy(legacy)}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertEqual(context["fundamental_quality"], legacy)
        self.assertEqual(context["fundamental_quality_evidence"]["model"], "earnings_quality_cash_conversion")

    def test_fundamental_quality_evidence_is_actionable_false(self):
        bundle = {"tickers": {"HPG": {"fundamental_quality_evidence": copy.deepcopy(self._REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertIs(context["fundamental_quality_evidence"]["is_actionable"], False)

    def test_fundamental_quality_evidence_no_score_rank_or_recommendation_field_introduced(self):
        bundle = {"tickers": {"HPG": {"fundamental_quality_evidence": copy.deepcopy(self._REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE)}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        result = context["fundamental_quality_evidence"]
        for forbidden in ("score", "rank", "recommendation", "rating", "target_price"):
            self.assertNotIn(forbidden, result)
            self.assertNotIn(forbidden, result["metrics"])

    def test_fundamental_quality_evidence_missing_remains_absent(self):
        bundle = {"tickers": {"PAN": {}}}
        context = {"ticker": "PAN", "provenance": []}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertNotIn("fundamental_quality_evidence", context)

    def test_fundamental_quality_evidence_unavailable_status_passes_through(self):
        """Negative-control shape: status='unavailable' passes through unchanged -- Consumer
        never upgrades or reinterprets it."""
        unavailable = {
            "schema_version": "1.0.0", "ticker": "PAN", "model": "earnings_quality_cash_conversion",
            "model_version": "1.0.0", "status": "unavailable", "applicability": "applicable",
            "reporting_period": None, "statement_scope": None, "inputs": [], "metrics": {},
            "data_warnings": [], "blocking_reasons": ["no_verified_financial_period"],
            "limitations": [], "provenance": {}, "is_actionable": False,
        }
        bundle = {"tickers": {"PAN": {"fundamental_quality_evidence": copy.deepcopy(unavailable)}}}
        context = {"ticker": "PAN", "provenance": []}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertEqual(context["fundamental_quality_evidence"], unavailable)

    def test_fundamental_quality_evidence_malformed_fails_closed_without_corrupting_context(self):
        bundle = {"tickers": {"TEST": {"fundamental_quality_evidence": "not_a_dict"}}}
        context = {"ticker": "TEST", "provenance": [], "metadata": {"ticker": "TEST"}}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertEqual(context["fundamental_quality_evidence"]["status"], "malformed")
        self.assertEqual(context["metadata"]["ticker"], "TEST")

    def test_fundamental_quality_evidence_does_not_disturb_existing_data_truth_contracts(self):
        bundle = {
            "tickers": {
                "HPG": {
                    "financial_period_coverage": {"latest_raw_period": "2024", "is_actionable": False},
                    "distribution_evidence": copy.deepcopy(self._REAL_VNM_DISTRIBUTION_EVIDENCE),
                    "fundamental_quality_evidence": copy.deepcopy(self._REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE),
                }
            }
        }
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_distribution_evidence_contract(context, bundle)
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertEqual(context["financial_period_coverage"]["latest_raw_period"], "2024")
        self.assertIn("distribution_evidence", context)
        self.assertIn("fundamental_quality_evidence", context)

    def test_fundamental_quality_evidence_source_input_not_mutated(self):
        source = copy.deepcopy(self._REAL_HPG_FUNDAMENTAL_QUALITY_EVIDENCE)
        original = copy.deepcopy(source)
        bundle = {"tickers": {"HPG": {"fundamental_quality_evidence": source}}}
        context = {"ticker": "HPG", "provenance": []}
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        context["fundamental_quality_evidence"]["status"] = "mutated_for_test"
        context["fundamental_quality_evidence"]["inputs"].append({"injected": True})
        self.assertEqual(source, original)
        self.assertEqual(bundle["tickers"]["HPG"]["fundamental_quality_evidence"], original)

    def test_fundamental_quality_evidence_legacy_bundle_without_field_unaffected(self):
        """Legacy bundles (no fundamental_quality_evidence key at all -- every current real
        bundle) must keep building all other contracts, including the separate legacy
        fundamental_quality field, normally with no new key added."""
        legacy = {"schema_version": "1.2.0", "entity_type": "corporate", "models": {}}
        bundle = {"tickers": {"HPG": {
            "financial_period_coverage": {"latest_raw_period": "2024", "is_actionable": False},
            "fundamental_quality": copy.deepcopy(legacy),
        }}}
        context = {"ticker": "HPG", "provenance": [], "fundamental_quality": copy.deepcopy(legacy)}
        apply_bundle_financial_period_coverage_contract(context, bundle)
        apply_bundle_fundamental_quality_evidence_contract(context, bundle)
        self.assertEqual(context["financial_period_coverage"]["latest_raw_period"], "2024")
        self.assertEqual(context["fundamental_quality"], legacy)
        self.assertNotIn("fundamental_quality_evidence", context)


if __name__ == "__main__":
    unittest.main()
