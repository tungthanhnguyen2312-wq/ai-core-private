"""Consumer pass-through tests for the market_wide_current_fundamental_research contract.

Mirrors tests/test_market_wide_current_liquidity_research_contract_pass_through.py's convention
of embedding real Producer values rather than synthetic shapes.

tickers[ticker].market_wide_current_fundamental_research is a byte-identical pass-through of one
record from stock-core-private's retained market_wide_current_fundamental_research artifact
(tools/run_market_wide_current_fundamental_research.py), plus the "status"/"is_actionable"/
"source_artifact_identity"/"coverage" fields export_ai_bundle.py's attach layer adds. Consumer
never recomputes a metric value, growth rate, ratio, or sector-applicability gate, and never
upgrades a PROVIDER_RESEARCH/BLOCKED ticker toward OFFICIAL_QUALIFIED.

_REAL_PNJ_RECORD, _REAL_AAA_RECORD, and _REAL_CCS_RECORD below are real values captured
2026-08-23 by running the actual Producer export_ai_bundle.build_market_wide_current_fundamental
_research_for_ticker_safe() against the actual retained checkpoint
(operations-review/market-wide-current-fundamental-research-v1-20260823/market_wide_current_
fundamental_research_artifact.json, artifact_sha256=cdfe21a3ce86d0b3327e021e29b8be0c23669fd19dcf
546ac98c3986e6bd6344). PNJ is the real, deliberately-chosen edge case this milestone must
preserve: it is OFFICIAL_QUALIFIED (real official evidence retained and reconciled) yet its own
`fundamental_research_readiness` is "BLOCKED" -- zero of its ten metrics reach EXACT_QUALIFIED or
DERIVED_PROXY, because the metrics needing net_income/operating_cash_flow/total_interest_bearing_
debt/a second period are all MISSING. Evidence presence and usable-metric presence are two
different numbers; this test suite must never conflate them.
"""
from __future__ import annotations

import copy
import unittest

from builders import build_ticker_context as b

_REAL_PNJ_RECORD = {'authoritative_periods_available': ['2024'],
 'authority_tier': 'OFFICIAL_QUALIFIED',
 'blocked_metrics': [{'blocked_reason': 'MISSING_INPUTS:operating_cash_flow,net_income',
                      'metric_id': 'cash_flow_minus_earnings',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_INPUTS:operating_cash_flow,net_income',
                      'metric_id': 'cash_flow_to_earnings',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_INPUTS:total_interest_bearing_debt',
                      'metric_id': 'debt_to_equity',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_CONSECUTIVE_PRIOR_PERIOD',
                      'metric_id': 'earnings_growth_yoy',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_INPUTS:total_interest_bearing_debt',
                      'metric_id': 'net_debt',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_INPUTS:net_income,revenue',
                      'metric_id': 'net_margin',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_CONSECUTIVE_PRIOR_PERIOD',
                      'metric_id': 'operating_cash_flow_growth_yoy',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_INPUTS:net_income',
                      'metric_id': 'return_on_assets',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_INPUTS:net_income',
                      'metric_id': 'return_on_equity',
                      'periods_used': ['2024'],
                      'status': 'MISSING'},
                     {'blocked_reason': 'MISSING_CONSECUTIVE_PRIOR_PERIOD',
                      'metric_id': 'revenue_growth_yoy',
                      'periods_used': ['2024'],
                      'status': 'MISSING'}],
 'coverage': {'blocked_no_source_count': 3,
              'candidate_count': 523,
              'derived_proxy_metrics': 22,
              'exact_qualified_metrics': 94,
              'issuers_with_official_facts': 13,
              'issuers_with_usable_deterministic_metrics': 11,
              'missing_or_blocked_metrics': 49,
              'not_applicable_metrics': 9,
              'provider_research_tier_count': 507},
 'entity_class': 'corporate',
 'evidence_completeness': {'all_metric_lineage_present': True,
                           'conflict_fact_keys': [],
                           'positive_authoritative_fact_count': 4},
 'fundamental_research_readiness': 'BLOCKED',
 'history_readiness': {'compatible_annual_period_count': 1,
                       'currencies': ['VND'],
                       'currency_continuity': True,
                       'gaps': [],
                       'multi_period_growth_available': False,
                       'periods': ['2024'],
                       'point_in_time_eligible_fact_count': 4,
                       'point_in_time_status': 'QUALIFIED',
                       'statement_scope_continuity': True,
                       'statement_scopes': ['consolidated']},
 'is_actionable': False,
 'metric_family_states': {'balance_sheet': 'BALANCE_SHEET_BLOCKED',
                          'cashflow': 'CASHFLOW_BLOCKED',
                          'growth': 'GROWTH_BLOCKED',
                          'profitability': 'PROFITABILITY_BLOCKED'},
 'metrics': [{'blocked_reason': 'MISSING_INPUTS:operating_cash_flow,net_income',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'cash_flow_minus_earnings',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_INPUTS:operating_cash_flow,net_income',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'cash_flow_to_earnings',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_INPUTS:total_interest_bearing_debt',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'debt_to_equity',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_CONSECUTIVE_PRIOR_PERIOD',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'earnings_growth_yoy',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_INPUTS:total_interest_bearing_debt',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'net_debt',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_INPUTS:net_income,revenue',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'net_margin',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_CONSECUTIVE_PRIOR_PERIOD',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'operating_cash_flow_growth_yoy',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_INPUTS:net_income',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'return_on_assets',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_INPUTS:net_income',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'return_on_equity',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []},
             {'blocked_reason': 'MISSING_CONSECUTIVE_PRIOR_PERIOD',
              'currency': None,
              'entity_class': 'corporate',
              'evidence_lineage': [],
              'input_fact_ids': [],
              'method': None,
              'metric_id': 'revenue_growth_yoy',
              'periods_used': ['2024'],
              'point_in_time_eligibility': 'NOT_ELIGIBLE',
              'statement_scope': None,
              'status': 'MISSING',
              'value': None,
              'warnings': []}],
 'sector': 'corporate',
 'source_artifact_identity': 'market_wide_current_fundamental_research:cdfe21a3ce86d0b3327e021e29b8be0c23669fd19dcf546ac98c3986e6bd6344',
 'status': 'official_qualified',
 'supersedes_frozen_p3f10_disposition': 'STATEMENT_SCOPE_UNKNOWN',
 'ticker': 'PNJ'}

_REAL_AAA_RECORD = {'allowed_uses': ['descriptive_context',
                  'provider_series_growth',
                  'sector_aware_research',
                  'shadow_comparison'],
 'authority_tier': 'PROVIDER_RESEARCH',
 'coverage': {'blocked_no_source_count': 3,
              'candidate_count': 523,
              'derived_proxy_metrics': 22,
              'exact_qualified_metrics': 94,
              'issuers_with_official_facts': 13,
              'issuers_with_usable_deterministic_metrics': 11,
              'missing_or_blocked_metrics': 49,
              'not_applicable_metrics': 9,
              'provider_research_tier_count': 507},
 'disposition': 'STATEMENT_SCOPE_UNKNOWN',
 'forbidden_uses': ['official_label',
                    'historical_pit_claim',
                    'execution_actionability',
                    'target_price',
                    'portfolio_sizing',
                    'authoritative_valuation_input'],
 'is_actionable': False,
 'official_tier_blocked_detail': 'NO_APPROVED_OFFICIAL_SOURCE_ROUTE_IN_REGISTRY',
 'official_tier_blocked_reason': 'NO_APPROVED_ROUTE_FOUND',
 'provider_tier_blocked_reason': 'PROVIDER_OBSERVATION_SCOPE_CURRENCY_SCALE_NOT_INDEPENDENTLY_EVIDENCED',
 'raw_observation_count': 1123,
 'raw_providers': ['KBS', 'VCI'],
 'raw_statement_families': ['balance_sheet', 'cash_flow', 'income_statement'],
 'reporting_periods': ['2024-Q2', '2024-Q3', '2024-Q4', '2025-Q1', '2025-Q2', '2025-Q3', '2025-Q4', '2026-Q1'],
 'scope_currency_scale_status': 'UNKNOWN_FAIL_CLOSED',
 'sector': 'unknown',
 'source_artifact_identity': 'market_wide_current_fundamental_research:cdfe21a3ce86d0b3327e021e29b8be0c23669fd19dcf546ac98c3986e6bd6344',
 'status': 'provider_research',
 'ticker': 'AAA'}

_REAL_CCS_RECORD = {'allowed_uses': [],
 'authority_tier': 'BLOCKED',
 'coverage': {'blocked_no_source_count': 3,
              'candidate_count': 523,
              'derived_proxy_metrics': 22,
              'exact_qualified_metrics': 94,
              'issuers_with_official_facts': 13,
              'issuers_with_usable_deterministic_metrics': 11,
              'missing_or_blocked_metrics': 49,
              'not_applicable_metrics': 9,
              'provider_research_tier_count': 507},
 'disposition': 'SOURCE_MISSING',
 'forbidden_uses': ['official_label',
                    'historical_pit_claim',
                    'execution_actionability',
                    'target_price',
                    'portfolio_sizing',
                    'authoritative_valuation_input'],
 'is_actionable': False,
 'official_tier_blocked_detail': 'NO_APPROVED_OFFICIAL_SOURCE_ROUTE_IN_REGISTRY',
 'official_tier_blocked_reason': 'NO_APPROVED_ROUTE_FOUND',
 'provider_tier_blocked_reason': 'MISSING_FINANCIAL_SOURCE_PAYLOAD',
 'raw_observation_count': 0,
 'raw_providers': [],
 'raw_statement_families': [],
 'reporting_periods': [],
 'scope_currency_scale_status': 'NOT_APPLICABLE_NO_SOURCE',
 'sector': 'unknown',
 'source_artifact_identity': 'market_wide_current_fundamental_research:cdfe21a3ce86d0b3327e021e29b8be0c23669fd19dcf546ac98c3986e6bd6344',
 'status': 'blocked',
 'ticker': 'CCS'}


def _bundle(ticker: str, raw) -> dict:
    return {"tickers": {ticker: {"market_wide_current_fundamental_research": raw}}}


class VerbatimPassThrough(unittest.TestCase):
    def test_official_qualified_passes_through_unchanged(self) -> None:
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", _REAL_PNJ_RECORD))
        self.assertEqual(_REAL_PNJ_RECORD, ctx["market_wide_current_fundamental_research"])
        self.assertEqual(ctx["provenance"][-1]["source_dataset"], "market_wide_current_fundamental_research")

    def test_official_qualified_but_readiness_blocked_never_conflated(self) -> None:
        """The one requirement this milestone names explicitly: evidence presence
        (OFFICIAL_QUALIFIED) and usable-metric presence (fundamental_research_readiness) are two
        different questions. PNJ answers yes to the first and no to the second; that must survive
        Consumer pass-through exactly, never smoothed over."""
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", _REAL_PNJ_RECORD))
        result = ctx["market_wide_current_fundamental_research"]
        self.assertEqual("OFFICIAL_QUALIFIED", result["authority_tier"])
        self.assertEqual("BLOCKED", result["fundamental_research_readiness"])
        self.assertEqual("STATEMENT_SCOPE_UNKNOWN", result["supersedes_frozen_p3f10_disposition"])
        self.assertTrue(all(metric["status"] == "MISSING" for metric in result["metrics"]))

    def test_provider_research_passes_through_not_treated_as_malformed(self) -> None:
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", _REAL_AAA_RECORD))
        result = ctx["market_wide_current_fundamental_research"]
        self.assertEqual(_REAL_AAA_RECORD, result)
        self.assertEqual("PROVIDER_RESEARCH", result["authority_tier"])
        self.assertNotIn("metrics", result)

    def test_blocked_no_source_passes_through_not_treated_as_malformed(self) -> None:
        ctx = {"ticker": "CCS", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("CCS", _REAL_CCS_RECORD))
        result = ctx["market_wide_current_fundamental_research"]
        self.assertEqual(_REAL_CCS_RECORD, result)
        self.assertEqual("BLOCKED", result["authority_tier"])
        self.assertEqual([], result["allowed_uses"])

    def test_out_of_universe_ticker_has_no_key_distinct_from_blocked(self) -> None:
        ctx = {"ticker": "ZZZ_NOT_IN_UNIVERSE", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", _REAL_AAA_RECORD))
        self.assertNotIn("market_wide_current_fundamental_research", ctx)

    def test_absent_key_leaves_context_untouched(self) -> None:
        ctx = {"ticker": "FPT", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, {"tickers": {"FPT": {}}})
        self.assertNotIn("market_wide_current_fundamental_research", ctx)

    def test_none_bundle_remains_backward_compatible(self) -> None:
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, None)
        self.assertNotIn("market_wide_current_fundamental_research", ctx)

    def test_no_recomputation_deepcopy_not_shared_reference(self) -> None:
        raw = copy.deepcopy(_REAL_PNJ_RECORD)
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", raw))
        ctx["market_wide_current_fundamental_research"]["metrics"][0]["value"] = 999999.0
        self.assertIsNone(raw["metrics"][0]["value"])

    def test_provenance_entry_recorded(self) -> None:
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", _REAL_AAA_RECORD))
        sources = [p.get("source_dataset") for p in ctx["provenance"]]
        self.assertIn("market_wide_current_fundamental_research", sources)

    def test_no_secret_or_credential_like_value(self) -> None:
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", _REAL_PNJ_RECORD))
        dumped = str(ctx["market_wide_current_fundamental_research"]).lower()
        for forbidden in ("token", "secret", "signature", "authorization", "x-api-key", "cookie", "password"):
            self.assertNotIn(forbidden, dumped)


class NeverWidensAProducerVerdict(unittest.TestCase):
    def test_is_actionable_true_is_refused(self) -> None:
        bad = {**_REAL_PNJ_RECORD, "is_actionable": True}
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", bad))
        result = ctx["market_wide_current_fundamental_research"]
        self.assertEqual("malformed", result["status"])
        self.assertFalse(result["is_actionable"])

    def test_official_qualified_missing_metrics_is_refused(self) -> None:
        bad = {k: v for k, v in _REAL_PNJ_RECORD.items() if k != "metrics"}
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_official_qualified_missing_metric_family_states_is_refused(self) -> None:
        bad = {k: v for k, v in _REAL_PNJ_RECORD.items() if k != "metric_family_states"}
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_provider_research_carrying_metrics_is_refused(self) -> None:
        """A PROVIDER_RESEARCH record must never carry a computed metric -- if one appears
        (e.g. from a corrupted upstream payload), this is treated as a contract violation, not a
        surprising but valid research finding."""
        bad = {**_REAL_AAA_RECORD, "metrics": [{"metric_id": "net_margin", "value": 0.1}]}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_same_provider_series_trends_pass_through_without_absolute_value(self) -> None:
        trend = {
            "authority_tier": "PROVIDER_RESEARCH", "status": "AVAILABLE", "usable_metric_count": 1,
            "metrics": {
                "revenue_growth": {
                    "ticker": "AAA", "metric_id": "revenue_growth", "metric_family": "revenue",
                    "method": "same_provider_consecutive_quarter_provider_series_trend/v1",
                    "authority_tier": "PROVIDER_RESEARCH", "status": "AVAILABLE", "provider": "VCI",
                    "periods": ["2025-Q4", "2026-Q1"], "growth_fraction": 0.1,
                    "lineage": [{"fact_id": "a"}, {"fact_id": "b"}],
                    "data_limitations": ["provider_scoped_research_only_not_official_qualified"],
                    "comparability_scope": "same_ticker_same_provider_same_canonical_metric_consecutive_quarterly_periods_only",
                    "blocked_reason": None,
                }
            },
        }
        raw = {**_REAL_AAA_RECORD, "provider_series_trends": trend}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", raw))
        self.assertEqual(trend, ctx["market_wide_current_fundamental_research"]["provider_series_trends"])

    def test_provider_series_trend_absolute_value_is_refused(self) -> None:
        bad = {**_REAL_AAA_RECORD, "provider_series_trends": {
            "authority_tier": "PROVIDER_RESEARCH", "status": "AVAILABLE", "metrics": {
                "revenue_growth": {
                    "ticker": "AAA", "authority_tier": "PROVIDER_RESEARCH", "status": "AVAILABLE",
                    "provider": "VCI", "periods": ["2025-Q4", "2026-Q1"], "method": "m",
                    "lineage": [], "data_limitations": [], "comparability_scope": "same_provider_only",
                    "blocked_reason": None, "value": 123,
                }
            },
        }}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_ticker_mismatch_is_refused(self) -> None:
        bad = {**_REAL_PNJ_RECORD, "ticker": "VNM"}
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_unknown_authority_tier_is_refused(self) -> None:
        bad = {**_REAL_AAA_RECORD, "authority_tier": "DEFINITELY_OFFICIAL_TRUST_ME"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_unknown_status_value_is_refused(self) -> None:
        bad = {**_REAL_AAA_RECORD, "status": "definitely_official_trust_me"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_provider_research_upgraded_to_official_tier_label_alone_is_refused(self) -> None:
        """Flipping only the authority_tier label to OFFICIAL_QUALIFIED without the required
        official-tier fields (metrics/metric_family_states/fundamental_research_readiness/
        entity_class) must fail closed, never be accepted as a promotion."""
        bad = {**_REAL_AAA_RECORD, "authority_tier": "OFFICIAL_QUALIFIED"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_non_mapping_raw_is_refused(self) -> None:
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", ["not", "a", "mapping"]))
        self.assertEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])

    def test_malformed_result_is_still_non_actionable(self) -> None:
        bad = {**_REAL_PNJ_RECORD, "is_actionable": True}
        ctx = {"ticker": "PNJ", "provenance": []}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", bad))
        self.assertFalse(ctx["market_wide_current_fundamental_research"]["is_actionable"])

    def test_malformed_input_does_not_corrupt_other_context_fields(self) -> None:
        ctx = {"ticker": "PNJ", "provenance": [], "some_other_field": "untouched"}
        b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle("PNJ", "not-a-dict"))
        self.assertEqual("untouched", ctx["some_other_field"])

    def test_blocked_and_provider_research_records_not_refused_for_lacking_metrics(self) -> None:
        for raw in (_REAL_AAA_RECORD, _REAL_CCS_RECORD):
            ctx = {"ticker": raw["ticker"], "provenance": []}
            b.apply_bundle_market_wide_current_fundamental_research_contract(ctx, _bundle(raw["ticker"], raw))
            self.assertNotEqual("malformed", ctx["market_wide_current_fundamental_research"]["status"])


if __name__ == "__main__":
    unittest.main()
