"""Consumer pass-through tests for the market_wide_current_descriptive_research contract.

Mirrors tests/test_market_wide_current_liquidity_research_contract_pass_through.py's
structural-validity pattern and its convention of embedding real Producer values rather
than synthetic shapes.

tickers[ticker].market_wide_current_descriptive_research is a byte-identical pass-through
of one record from stock-core-private's retained market_wide_current_descriptive_research
artifact (tools/run_market_wide_current_descriptive_research.py), plus the
"status"/"is_actionable" fields export_ai_bundle.py's attach layer adds. Consumer never
recomputes breadth, sector cohorts, technical features, liquidity, traded value, turnover,
ADTV, ADV, a position size, or an execution capacity.

_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH below is real, captured 2026-08-23 for ticker AAA.
_REAL_SHB_SAME_SESSION_ELIGIBLE_RESIDUAL below is real, captured 2026-08-23 for ticker SHB.
_REAL_A32_NO_QUALIFIED_SESSION_TECHNICAL_MISSING below is real, captured 2026-08-23 for ticker A32.
_REAL_STALE_SESSION_NOT_CURRENT below is real, captured 2026-08-23 for ticker APP.
_REAL_DELISTED_OUT_OF_SCOPE below is real, captured 2026-08-23 for ticker AGE.
All five were captured by running the actual Producer
export_ai_bundle.attach_market_wide_current_descriptive_research() against the actual
retained checkpoint (operations-review/market-wide-current-descriptive-research-v1-20260823/
market_wide_current_descriptive_research_artifact.json, artifact_sha256=573bfafafad0ac18c58aca6d778952157078405d2a4039bb5a5eaae0938c0b97)
and feeding the result through this repository's own
apply_bundle_market_wide_current_descriptive_research_contract() -- the same frozen-time
proof re-run live (against the sibling Producer checkout, skipped if unavailable) in
FrozenTimeProducerConsumerEndToEndTests below. SHB is the real four-unit G1-vs-OHLC-v
residual (delta=4.0, verdict="OTHER") this milestone must never coerce. The "stale" fixture
has technical_features.status=SHADOW_ONLY but is_current_session=False -- a genuine
prior-session value that must never be reported as today's.
"""
from __future__ import annotations

import copy
import unittest

from builders import build_ticker_context as b


_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH = {'activity_and_session_state': 'ACTIVE_LISTED_OBSERVED',
 'blocked_outputs': {'backtesting': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'buy_sell_recommendations': 'RECOMMENDATION_PROHIBITED',
                     'corporate_action_or_ex_date': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_membership_or_active_universe_promotion': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_raw_as_traded_or_pit': 'RAW_AS_TRADED_NOT_PROMOTED',
                     'portfolio_weights_or_position_sizes': 'SIZING_EXECUTION_PROHIBITED',
                     'probabilities_or_target_prices': 'FORECAST_PROHIBITED',
                     'stock_rankings': 'RANKING_PROHIBITED',
                     'traded_value_turnover_adv_adtv': 'GROSS_TRADE_AMOUNT_NON_AUTHORITATIVE_SCALE_UNRESOLVED'},
 'in_current_descriptive_scope': True,
 'is_actionable': False,
 'liquidity': {'board_composition': {'MATCHED_ODD_LOT': {'active_volume_raw_total': 1218.0,
                                                         'boards': ['G4'],
                                                         'boards_not_counted': [],
                                                         'provider_raw_composition_ratio': 0.010662884756802184,
                                                         'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'},
                                     'MATCHED_ROUND_LOT': {'active_volume_raw_total': 112970.0,
                                                           'boards': ['G1'],
                                                           'boards_not_counted': [],
                                                           'provider_raw_composition_ratio': 0.988986938403894,
                                                           'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'},
                                     'PUT_THROUGH_ODD_LOT': {'active_volume_raw_total': 40.0,
                                                             'boards': ['T4', 'T6'],
                                                             'boards_not_counted': [{'activity_state': 'NOT_OBSERVED',
                                                                                     'board_id': 'T6'}],
                                                             'provider_raw_composition_ratio': 0.00035017683930384843,
                                                             'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'},
                                     'PUT_THROUGH_ROUND_LOT': {'active_volume_raw_total': 0.0,
                                                               'boards': ['T1', 'T3'],
                                                               'boards_not_counted': [{'activity_state': 'OBSERVED_INACTIVE_STALE',
                                                                                       'board_id': 'T1'},
                                                                                      {'activity_state': 'NOT_OBSERVED',
                                                                                       'board_id': 'T3'}],
                                                               'provider_raw_composition_ratio': 0.0,
                                                               'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'}},
               'current_ohlc_v': 1129700.0,
               'g1_v_reconciliation': {'candidate': {'candidate_id': 'C5',
                                                     'candidate_type': 'SCALED_G1',
                                                     'empirical_scale': 10.0,
                                                     'evidence_source': 'p0-b2ab-zero-match-root-cause-diagnosis-v1-20260818: '
                                                                        'daily_v / board_G1_quantity '
                                                                        'clusters at exactly 10.0 across '
                                                                        '35,164/35,231 (99.8098%) '
                                                                        'symbol-sessions over 40 retained '
                                                                        'trading dates; scale discovered '
                                                                        'from data, not from a provider unit '
                                                                        'assertion',
                                                     'scale_status': 'EMPIRICAL_CANDIDATE',
                                                     'semantic_unit_interpretation': 'UNKNOWN'},
                                       'candidate_value': 1129700.0,
                                       'contrast_with_orphaned_generator': {'orphaned_lineage_status': 'SOURCE_GENERATOR_NOT_IN_CURRENT_MAIN_ANCESTRY',
                                                                            'orphaned_source_commit': '2b7b38772e16c434c8adf5288cbc46ef0f7f4c02'},
                                       'delta': 0.0,
                                       'exact_match': True,
                                       'g1_cumulative_volume_raw': 112970.0,
                                       'lineage_status': 'LIVE_BOUNDED_ADAPTER_PROBE_2026_08_23',
                                       'ohlc_v': 1129700.0,
                                       'verdict': 'EXACT_MATCH'},
               'liquidity_research_contract': {'ADTV_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.gross_trade_amount_uniform_formula_check',
                                                                           'docs/STATE.md P0-B'],
                                                                 'reason': 'average daily traded VALUE '
                                                                           'inherits the same multi-session '
                                                                           'completeness blocker as ADV, '
                                                                           'plus the open grossTradeAmount '
                                                                           'board-dependent scale ambiguity '
                                                                           'documented in this module',
                                                                 'state': 'BLOCKED'},
                                               'ADV_VOLUME_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness',
                                                                                 'docs/STATE.md P0-B'],
                                                                       'reason': 'average daily volume '
                                                                                 'requires multiple complete '
                                                                                 'sessions; bounded '
                                                                                 'trades_history pagination '
                                                                                 'is proven '
                                                                                 'activity-dependent '
                                                                                 '(complete for a '
                                                                                 'low-activity name, '
                                                                                 'left-truncated for a '
                                                                                 "high-activity name's "
                                                                                 'auction burst) and cannot '
                                                                                 'be relied on across an '
                                                                                 'arbitrary multi-session '
                                                                                 'window within a finite '
                                                                                 'call budget',
                                                                       'state': 'BLOCKED'},
                                               'CURRENT_SESSION_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.board_latest_snapshot'],
                                                                                      'reason': 'trades_latest '
                                                                                                'gives a '
                                                                                                'complete, '
                                                                                                'non-paginated '
                                                                                                'per-board '
                                                                                                'cumulative '
                                                                                                'volume/value '
                                                                                                'reading for '
                                                                                                'the most '
                                                                                                'recently '
                                                                                                'active '
                                                                                                'session; '
                                                                                                'this is a '
                                                                                                'research-descriptive '
                                                                                                'capability '
                                                                                                'only, not a '
                                                                                                'promoted '
                                                                                                'liquidity/turnover '
                                                                                                'authority',
                                                                                      'state': 'ELIGIBLE'},
                                               'EXECUTION_CAPACITY': {'cites': ['docs/STATE.md Invariant 2'],
                                                                      'reason': 'a prerequisite of '
                                                                                'POSITION_SIZING; inherits '
                                                                                'the same block',
                                                                      'state': 'BLOCKED'},
                                               'HISTORICAL_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness'],
                                                                                 'reason': 'no bounded '
                                                                                           'historical scan '
                                                                                           'was supplied for '
                                                                                           'this evaluation',
                                                                                 'state': 'UNKNOWN'},
                                               'PIT_BACKTEST': {'cites': ['market_data_source_authority.DNSE_OHLC_PRICE_BASIS'],
                                                                'reason': 'DNSE OHLC price basis remains '
                                                                          'ADJUSTED_CONFIRMED_NON_RAW_NON_POINT_IN_TIME '
                                                                          "regardless of this milestone's "
                                                                          'volume findings',
                                                                'state': 'BLOCKED'},
                                               'POSITION_SIZING': {'cites': ['dnse_trades_liquidity_basis.derived_value_price_times_shares',
                                                                             'docs/STATE.md Invariant 2'],
                                                                   'reason': 'no historical completeness, no '
                                                                             'resolved lot-multiplier, no '
                                                                             'qualified PIT price basis',
                                                                   'state': 'BLOCKED'}},
               'session': '2026-08-21',
               'status': 'ELIGIBLE',
               'value_status': 'GROSS_TRADE_AMOUNT_RETAINED_ONLY_NON_AUTHORITATIVE_SCALE_BASIS_UNRESOLVED'},
 'market_coverage': {'coverage_ratio_of_denominator': 0.5052980132450331,
                     'coverage_ratio_of_observed_session_cohort': 0.7947916666666667,
                     'current_active_equity_denominator': 1510,
                     'observed_session_cohort': 960,
                     'quality_state': 'PARTIAL_COVERAGE_EXPLICIT',
                     'same_session_technical_feature_available_count': 763,
                     'stale_feature_available_but_not_current_session_count': 52},
 'membership_state': 'INCLUDED',
 'sector_classification': {'classification_evidence_id': '760e9963e6aed49c15d0617afdd80f2082ea7f8c28665847fb8d04294e8048f8',
                           'entity_class': 'corporate',
                           'source_artifact_identity': 'p2e3_entity_classification_promotion:f47d56819fc6c1668614338efc103c7eed1508159c8bae5f66f9a09f459680a9',
                           'source_id': 'canonical_instrument_reconciliation'},
 'sector_state': {'classification_label': 'corporate',
                  'minimum_member_requirement': 5,
                  'same_session_eligible_count': 27,
                  'status': 'AVAILABLE'},
 'session': '2026-08-21',
 'status': 'available',
 'technical_features': {'feature_as_of_session': '2026-08-21',
                        'feature_statuses': {'close': 'OBSERVED',
                                             'ma_20': 'SHADOW_ONLY',
                                             'ma_3': 'SHADOW_ONLY',
                                             'ma_5': 'SHADOW_ONLY',
                                             'momentum_20d': 'SHADOW_ONLY',
                                             'relative_volume_provider_scoped': 'DERIVED_PROXY',
                                             'return_1d': 'SHADOW_ONLY',
                                             'volatility_20d': 'SHADOW_ONLY'},
                        'historical_pit_eligible': False,
                        'is_current_session': True,
                        'method': 'retained_20_completed_session_window; no_imputation',
                        'price_basis': 'ADJUSTED_RETROSPECTIVE',
                        'status': 'SHADOW_ONLY',
                        'values': {'close': 7120.0,
                                   'ma_20': 7017.058823529412,
                                   'ma_3': 6973.333333333333,
                                   'ma_5': 7002.0,
                                   'momentum_20d': -0.009735744089012566,
                                   'relative_volume_provider_scoped': 1.1347496358796645,
                                   'return_1d': 0.03188405797101446,
                                   'volatility_20d': 0.014535860013712314},
                        'warnings': ['ADJUSTED_RETROSPECTIVE_NOT_RAW_AS_TRADED',
                                     'RELATIVE_VOLUME_IS_PROVIDER_SCOPED_NOT_LIQUIDITY_AUTHORITY']},
 'ticker': 'AAA',
 'trend_state': 'ABOVE_MA20'}

_REAL_SHB_SAME_SESSION_ELIGIBLE_RESIDUAL = {'activity_and_session_state': 'ACTIVE_LISTED_OBSERVED',
 'blocked_outputs': {'backtesting': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'buy_sell_recommendations': 'RECOMMENDATION_PROHIBITED',
                     'corporate_action_or_ex_date': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_membership_or_active_universe_promotion': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_raw_as_traded_or_pit': 'RAW_AS_TRADED_NOT_PROMOTED',
                     'portfolio_weights_or_position_sizes': 'SIZING_EXECUTION_PROHIBITED',
                     'probabilities_or_target_prices': 'FORECAST_PROHIBITED',
                     'stock_rankings': 'RANKING_PROHIBITED',
                     'traded_value_turnover_adv_adtv': 'GROSS_TRADE_AMOUNT_NON_AUTHORITATIVE_SCALE_UNRESOLVED'},
 'in_current_descriptive_scope': True,
 'is_actionable': False,
 'liquidity': {'board_composition': {'MATCHED_ODD_LOT': {'active_volume_raw_total': 22319.0,
                                                         'boards': ['G4'],
                                                         'boards_not_counted': [],
                                                         'provider_raw_composition_ratio': 0.002715016233045442,
                                                         'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'},
                                     'MATCHED_ROUND_LOT': {'active_volume_raw_total': 6961550.0,
                                                           'boards': ['G1'],
                                                           'boards_not_counted': [],
                                                           'provider_raw_composition_ratio': 0.8468444489967066,
                                                           'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'},
                                     'PUT_THROUGH_ODD_LOT': {'active_volume_raw_total': 8.0,
                                                             'boards': ['T4', 'T6'],
                                                             'boards_not_counted': [{'activity_state': 'NOT_OBSERVED',
                                                                                     'board_id': 'T6'}],
                                                             'provider_raw_composition_ratio': 9.731676985690907e-07,
                                                             'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'},
                                     'PUT_THROUGH_ROUND_LOT': {'active_volume_raw_total': 1236700.0,
                                                               'boards': ['T1', 'T3'],
                                                               'boards_not_counted': [{'activity_state': 'OBSERVED_INACTIVE_STALE',
                                                                                       'board_id': 'T3'}],
                                                               'provider_raw_composition_ratio': 0.15043956160254932,
                                                               'ratio_basis': 'CURRENT_SESSION_PROVIDER_RAW_COUNTERS_ONLY_NOT_EXECUTED_SHARE_OR_TURNOVER_RATIO'}},
               'current_ohlc_v': 69615504.0,
               'g1_v_reconciliation': {'candidate': {'candidate_id': 'C5',
                                                     'candidate_type': 'SCALED_G1',
                                                     'empirical_scale': 10.0,
                                                     'evidence_source': 'p0-b2ab-zero-match-root-cause-diagnosis-v1-20260818: '
                                                                        'daily_v / board_G1_quantity '
                                                                        'clusters at exactly 10.0 across '
                                                                        '35,164/35,231 (99.8098%) '
                                                                        'symbol-sessions over 40 retained '
                                                                        'trading dates; scale discovered '
                                                                        'from data, not from a provider unit '
                                                                        'assertion',
                                                     'scale_status': 'EMPIRICAL_CANDIDATE',
                                                     'semantic_unit_interpretation': 'UNKNOWN'},
                                       'candidate_value': 69615500.0,
                                       'contrast_with_orphaned_generator': {'orphaned_lineage_status': 'SOURCE_GENERATOR_NOT_IN_CURRENT_MAIN_ANCESTRY',
                                                                            'orphaned_source_commit': '2b7b38772e16c434c8adf5288cbc46ef0f7f4c02'},
                                       'delta': 4.0,
                                       'exact_match': False,
                                       'g1_cumulative_volume_raw': 6961550.0,
                                       'lineage_status': 'LIVE_BOUNDED_ADAPTER_PROBE_2026_08_23',
                                       'ohlc_v': 69615504.0,
                                       'verdict': 'OTHER'},
               'liquidity_research_contract': {'ADTV_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.gross_trade_amount_uniform_formula_check',
                                                                           'docs/STATE.md P0-B'],
                                                                 'reason': 'average daily traded VALUE '
                                                                           'inherits the same multi-session '
                                                                           'completeness blocker as ADV, '
                                                                           'plus the open grossTradeAmount '
                                                                           'board-dependent scale ambiguity '
                                                                           'documented in this module',
                                                                 'state': 'BLOCKED'},
                                               'ADV_VOLUME_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness',
                                                                                 'docs/STATE.md P0-B'],
                                                                       'reason': 'average daily volume '
                                                                                 'requires multiple complete '
                                                                                 'sessions; bounded '
                                                                                 'trades_history pagination '
                                                                                 'is proven '
                                                                                 'activity-dependent '
                                                                                 '(complete for a '
                                                                                 'low-activity name, '
                                                                                 'left-truncated for a '
                                                                                 "high-activity name's "
                                                                                 'auction burst) and cannot '
                                                                                 'be relied on across an '
                                                                                 'arbitrary multi-session '
                                                                                 'window within a finite '
                                                                                 'call budget',
                                                                       'state': 'BLOCKED'},
                                               'CURRENT_SESSION_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.board_latest_snapshot'],
                                                                                      'reason': 'trades_latest '
                                                                                                'gives a '
                                                                                                'complete, '
                                                                                                'non-paginated '
                                                                                                'per-board '
                                                                                                'cumulative '
                                                                                                'volume/value '
                                                                                                'reading for '
                                                                                                'the most '
                                                                                                'recently '
                                                                                                'active '
                                                                                                'session; '
                                                                                                'this is a '
                                                                                                'research-descriptive '
                                                                                                'capability '
                                                                                                'only, not a '
                                                                                                'promoted '
                                                                                                'liquidity/turnover '
                                                                                                'authority',
                                                                                      'state': 'ELIGIBLE'},
                                               'EXECUTION_CAPACITY': {'cites': ['docs/STATE.md Invariant 2'],
                                                                      'reason': 'a prerequisite of '
                                                                                'POSITION_SIZING; inherits '
                                                                                'the same block',
                                                                      'state': 'BLOCKED'},
                                               'HISTORICAL_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness'],
                                                                                 'reason': 'no bounded '
                                                                                           'historical scan '
                                                                                           'was supplied for '
                                                                                           'this evaluation',
                                                                                 'state': 'UNKNOWN'},
                                               'PIT_BACKTEST': {'cites': ['market_data_source_authority.DNSE_OHLC_PRICE_BASIS'],
                                                                'reason': 'DNSE OHLC price basis remains '
                                                                          'ADJUSTED_CONFIRMED_NON_RAW_NON_POINT_IN_TIME '
                                                                          "regardless of this milestone's "
                                                                          'volume findings',
                                                                'state': 'BLOCKED'},
                                               'POSITION_SIZING': {'cites': ['dnse_trades_liquidity_basis.derived_value_price_times_shares',
                                                                             'docs/STATE.md Invariant 2'],
                                                                   'reason': 'no historical completeness, no '
                                                                             'resolved lot-multiplier, no '
                                                                             'qualified PIT price basis',
                                                                   'state': 'BLOCKED'}},
               'session': '2026-08-21',
               'status': 'ELIGIBLE',
               'value_status': 'GROSS_TRADE_AMOUNT_RETAINED_ONLY_NON_AUTHORITATIVE_SCALE_BASIS_UNRESOLVED'},
 'market_coverage': {'coverage_ratio_of_denominator': 0.5052980132450331,
                     'coverage_ratio_of_observed_session_cohort': 0.7947916666666667,
                     'current_active_equity_denominator': 1510,
                     'observed_session_cohort': 960,
                     'quality_state': 'PARTIAL_COVERAGE_EXPLICIT',
                     'same_session_technical_feature_available_count': 763,
                     'stale_feature_available_but_not_current_session_count': 52},
 'membership_state': 'INCLUDED',
 'sector_classification': {'as_of': '2026-07-09 11:55',
                           'classification_authority': 'PROVIDER_DESCRIPTIVE_CLASSIFICATION',
                           'classification_level': 'PROVIDER_INDUSTRY',
                           'classification_namespace': 'VCI.symbols_by_industries/retained-20260728',
                           'conflict_or_missing_reason': None,
                           'provider_qualification_status': 'reported',
                           'raw_label': 'Ngân hàng',
                           'safe_normalized_label': 'ngân hàng',
                           'source_artifact': 'vnstock_metadata_snapshot_20260728T122548Z_16fe54ee3497.jsonl',
                           'source_provider': 'VCI'},
 'sector_state': {'classification_label': 'ngân hàng',
                  'minimum_member_requirement': 5,
                  'same_session_eligible_count': 21,
                  'status': 'AVAILABLE'},
 'session': '2026-08-21',
 'status': 'available',
 'technical_features': {'feature_as_of_session': '2026-08-21',
                        'feature_statuses': {'close': 'OBSERVED',
                                             'ma_20': 'SHADOW_ONLY',
                                             'ma_3': 'SHADOW_ONLY',
                                             'ma_5': 'SHADOW_ONLY',
                                             'momentum_20d': 'SHADOW_ONLY',
                                             'relative_volume_provider_scoped': 'DERIVED_PROXY',
                                             'return_1d': 'SHADOW_ONLY',
                                             'volatility_20d': 'SHADOW_ONLY'},
                        'historical_pit_eligible': False,
                        'is_current_session': True,
                        'method': 'retained_20_completed_session_window; no_imputation',
                        'price_basis': 'ADJUSTED_RETROSPECTIVE',
                        'status': 'SHADOW_ONLY',
                        'values': {'close': 11900.0,
                                   'ma_20': 12047.058823529413,
                                   'ma_3': 11666.666666666666,
                                   'ma_5': 11650.0,
                                   'momentum_20d': -0.11194029850746268,
                                   'relative_volume_provider_scoped': 1.4592043866994635,
                                   'return_1d': 0.02586206896551735,
                                   'volatility_20d': 0.021194459099025932},
                        'warnings': ['ADJUSTED_RETROSPECTIVE_NOT_RAW_AS_TRADED',
                                     'RELATIVE_VOLUME_IS_PROVIDER_SCOPED_NOT_LIQUIDITY_AUTHORITY']},
 'ticker': 'SHB',
 'trend_state': 'AT_OR_BELOW_MA20'}

_REAL_A32_NO_QUALIFIED_SESSION_TECHNICAL_MISSING = {'activity_and_session_state': 'ACTIVE_LISTED_NO_QUALIFIED_SESSION_OBSERVATION',
 'blocked_outputs': {'backtesting': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'buy_sell_recommendations': 'RECOMMENDATION_PROHIBITED',
                     'corporate_action_or_ex_date': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_membership_or_active_universe_promotion': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_raw_as_traded_or_pit': 'RAW_AS_TRADED_NOT_PROMOTED',
                     'portfolio_weights_or_position_sizes': 'SIZING_EXECUTION_PROHIBITED',
                     'probabilities_or_target_prices': 'FORECAST_PROHIBITED',
                     'stock_rankings': 'RANKING_PROHIBITED',
                     'traded_value_turnover_adv_adtv': 'GROSS_TRADE_AMOUNT_NON_AUTHORITATIVE_SCALE_UNRESOLVED'},
 'in_current_descriptive_scope': True,
 'is_actionable': False,
 'liquidity': {'liquidity_disposition': 'MISSING',
               'reason': 'COMPATIBLE_CURRENT_OHLC_V_MISSING',
               'status': 'UNAVAILABLE'},
 'market_coverage': {'coverage_ratio_of_denominator': 0.5052980132450331,
                     'coverage_ratio_of_observed_session_cohort': 0.7947916666666667,
                     'current_active_equity_denominator': 1510,
                     'observed_session_cohort': 960,
                     'quality_state': 'PARTIAL_COVERAGE_EXPLICIT',
                     'same_session_technical_feature_available_count': 763,
                     'stale_feature_available_but_not_current_session_count': 52},
 'membership_state': 'INCLUDED',
 'sector_classification': {'classification_evidence_id': 'def879e2819079b1c0ded5e9b6f360d8571786c5116a0e2fe20757b690c13ac8',
                           'entity_class': 'corporate',
                           'source_artifact_identity': 'p2e3_entity_classification_promotion:f47d56819fc6c1668614338efc103c7eed1508159c8bae5f66f9a09f459680a9',
                           'source_id': 'canonical_instrument_reconciliation'},
 'sector_state': {'classification_label': 'corporate',
                  'minimum_member_requirement': 5,
                  'same_session_eligible_count': 27,
                  'status': 'AVAILABLE'},
 'session': '2026-08-21',
 'status': 'available',
 'technical_features': {'blockers': ['COMPLETE_20_SESSION_WINDOW_REQUIRED'],
                        'feature_as_of_session': '2026-08-17',
                        'is_current_session': False,
                        'status': 'MISSING',
                        'values': {}},
 'ticker': 'A32',
 'trend_state': None}

_REAL_STALE_SESSION_NOT_CURRENT = {'activity_and_session_state': 'ACTIVE_LISTED_NO_QUALIFIED_SESSION_OBSERVATION',
 'blocked_outputs': {'backtesting': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'buy_sell_recommendations': 'RECOMMENDATION_PROHIBITED',
                     'corporate_action_or_ex_date': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_membership_or_active_universe_promotion': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_raw_as_traded_or_pit': 'RAW_AS_TRADED_NOT_PROMOTED',
                     'portfolio_weights_or_position_sizes': 'SIZING_EXECUTION_PROHIBITED',
                     'probabilities_or_target_prices': 'FORECAST_PROHIBITED',
                     'stock_rankings': 'RANKING_PROHIBITED',
                     'traded_value_turnover_adv_adtv': 'GROSS_TRADE_AMOUNT_NON_AUTHORITATIVE_SCALE_UNRESOLVED'},
 'in_current_descriptive_scope': True,
 'is_actionable': False,
 'liquidity': {'liquidity_disposition': 'MISSING',
               'reason': 'COMPATIBLE_CURRENT_OHLC_V_MISSING',
               'status': 'UNAVAILABLE'},
 'market_coverage': {'coverage_ratio_of_denominator': 0.5052980132450331,
                     'coverage_ratio_of_observed_session_cohort': 0.7947916666666667,
                     'current_active_equity_denominator': 1510,
                     'observed_session_cohort': 960,
                     'quality_state': 'PARTIAL_COVERAGE_EXPLICIT',
                     'same_session_technical_feature_available_count': 763,
                     'stale_feature_available_but_not_current_session_count': 52},
 'membership_state': 'INCLUDED',
 'sector_classification': {'as_of': '2026-07-12 20:38',
                           'classification_authority': 'PROVIDER_DESCRIPTIVE_CLASSIFICATION',
                           'classification_level': 'PROVIDER_INDUSTRY',
                           'classification_namespace': 'VCI.symbols_by_industries/retained-20260728',
                           'conflict_or_missing_reason': None,
                           'provider_qualification_status': 'reported',
                           'raw_label': 'Hóa chất',
                           'safe_normalized_label': 'hóa chất',
                           'source_artifact': 'vnstock_metadata_snapshot_20260728T122548Z_16fe54ee3497.jsonl',
                           'source_provider': 'VCI'},
 'sector_state': {'classification_label': 'hóa chất',
                  'minimum_member_requirement': 5,
                  'same_session_eligible_count': 36,
                  'status': 'AVAILABLE'},
 'session': '2026-08-21',
 'status': 'available',
 'technical_features': {'feature_as_of_session': '2026-08-20',
                        'feature_statuses': {'close': 'OBSERVED',
                                             'ma_20': 'SHADOW_ONLY',
                                             'ma_3': 'SHADOW_ONLY',
                                             'ma_5': 'SHADOW_ONLY',
                                             'momentum_20d': 'SHADOW_ONLY',
                                             'relative_volume_provider_scoped': 'DERIVED_PROXY',
                                             'return_1d': 'SHADOW_ONLY',
                                             'volatility_20d': 'SHADOW_ONLY'},
                        'historical_pit_eligible': False,
                        'is_current_session': False,
                        'method': 'retained_20_completed_session_window; no_imputation',
                        'price_basis': 'ADJUSTED_RETROSPECTIVE',
                        'status': 'SHADOW_ONLY',
                        'values': {'close': 4100.0,
                                   'ma_20': 4096.428571428572,
                                   'ma_3': 4133.333333333333,
                                   'ma_5': 4160.0,
                                   'momentum_20d': -0.023809523809523836,
                                   'relative_volume_provider_scoped': 0.4444444444444444,
                                   'return_1d': 0.0,
                                   'volatility_20d': 0.03715435792364839},
                        'warnings': ['ADJUSTED_RETROSPECTIVE_NOT_RAW_AS_TRADED',
                                     'RELATIVE_VOLUME_IS_PROVIDER_SCOPED_NOT_LIQUIDITY_AUTHORITY']},
 'ticker': 'APP',
 'trend_state': None}

_REAL_DELISTED_OUT_OF_SCOPE = {'activity_and_session_state': 'INACTIVE_OR_DELISTED',
 'blocked_outputs': {'backtesting': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'buy_sell_recommendations': 'RECOMMENDATION_PROHIBITED',
                     'corporate_action_or_ex_date': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_membership_or_active_universe_promotion': 'OUT_OF_SCOPE_THIS_MILESTONE',
                     'historical_raw_as_traded_or_pit': 'RAW_AS_TRADED_NOT_PROMOTED',
                     'portfolio_weights_or_position_sizes': 'SIZING_EXECUTION_PROHIBITED',
                     'probabilities_or_target_prices': 'FORECAST_PROHIBITED',
                     'stock_rankings': 'RANKING_PROHIBITED',
                     'traded_value_turnover_adv_adtv': 'GROSS_TRADE_AMOUNT_NON_AUTHORITATIVE_SCALE_UNRESOLVED'},
 'in_current_descriptive_scope': False,
 'is_actionable': False,
 'liquidity': {'reason': 'OUT_OF_CURRENT_DESCRIPTIVE_SCOPE', 'status': 'NOT_APPLICABLE'},
 'market_coverage': {'coverage_ratio_of_denominator': 0.5052980132450331,
                     'coverage_ratio_of_observed_session_cohort': 0.7947916666666667,
                     'current_active_equity_denominator': 1510,
                     'observed_session_cohort': 960,
                     'quality_state': 'PARTIAL_COVERAGE_EXPLICIT',
                     'same_session_technical_feature_available_count': 763,
                     'stale_feature_available_but_not_current_session_count': 52},
 'membership_state': 'UNKNOWN',
 'sector_classification': {'as_of': '2026-07-12 20:36',
                           'classification_authority': 'PROVIDER_DESCRIPTIVE_CLASSIFICATION',
                           'classification_level': 'PROVIDER_INDUSTRY',
                           'classification_namespace': 'VCI.symbols_by_industries/retained-20260728',
                           'conflict_or_missing_reason': None,
                           'provider_qualification_status': 'reported',
                           'raw_label': 'Hàng & Dịch vụ Công nghiệp',
                           'safe_normalized_label': 'hàng & dịch vụ công nghiệp',
                           'source_artifact': 'vnstock_metadata_snapshot_20260728T122548Z_16fe54ee3497.jsonl',
                           'source_provider': 'VCI'},
 'sector_state': {'classification_label': 'hàng & dịch vụ công nghiệp',
                  'minimum_member_requirement': 5,
                  'same_session_eligible_count': 96,
                  'status': 'AVAILABLE'},
 'session': '2026-08-21',
 'status': 'not_available',
 'technical_features': {'feature_as_of_session': None,
                        'is_current_session': False,
                        'reason': 'OUT_OF_CURRENT_DESCRIPTIVE_SCOPE',
                        'status': 'NOT_APPLICABLE',
                        'values': {}},
 'ticker': 'AGE',
 'trend_state': None}


def _bundle(ticker: str, raw) -> dict:
    return {"tickers": {ticker: {"market_wide_current_descriptive_research": raw}}}


class VerbatimPassThrough(unittest.TestCase):
    def test_same_session_eligible_passes_through_unchanged(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", _REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH))
        self.assertEqual(_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH, ctx["market_wide_current_descriptive_research"])
        self.assertEqual(ctx["provenance"][-1]["source_dataset"], "market_wide_current_descriptive_research")

    def test_shb_four_unit_residual_preserved_verbatim_never_coerced(self):
        """The one requirement this milestone names explicitly for liquidity: SHB's non-exact
        reconciliation must survive Consumer pass-through exactly, never upgraded to EXACT_MATCH."""
        ctx = {"ticker": "SHB", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("SHB", _REAL_SHB_SAME_SESSION_ELIGIBLE_RESIDUAL))
        result = ctx["market_wide_current_descriptive_research"]
        self.assertEqual(_REAL_SHB_SAME_SESSION_ELIGIBLE_RESIDUAL, result)
        self.assertEqual("OTHER", result["liquidity"]["g1_v_reconciliation"]["verdict"])
        self.assertEqual(4.0, result["liquidity"]["g1_v_reconciliation"]["delta"])
        self.assertFalse(result["liquidity"]["g1_v_reconciliation"]["exact_match"])

    def test_no_qualified_session_technical_missing_passes_through(self):
        ctx = {"ticker": "A32", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("A32", _REAL_A32_NO_QUALIFIED_SESSION_TECHNICAL_MISSING))
        result = ctx["market_wide_current_descriptive_research"]
        self.assertEqual(_REAL_A32_NO_QUALIFIED_SESSION_TECHNICAL_MISSING, result)
        self.assertEqual("MISSING", result["technical_features"]["status"])
        self.assertEqual("UNAVAILABLE", result["liquidity"]["status"])

    def test_stale_technical_feature_never_reported_as_current_session(self):
        """The one requirement this milestone names explicitly for technical features: a stale
        prior-session value must survive Consumer pass-through with is_current_session still
        False, never silently promoted to look like today's reading."""
        ctx = {"ticker": "APP", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("APP", _REAL_STALE_SESSION_NOT_CURRENT))
        result = ctx["market_wide_current_descriptive_research"]
        self.assertEqual(_REAL_STALE_SESSION_NOT_CURRENT, result)
        self.assertEqual("SHADOW_ONLY", result["technical_features"]["status"])
        self.assertFalse(result["technical_features"]["is_current_session"])
        self.assertNotEqual(result["session"], result["technical_features"]["feature_as_of_session"])

    def test_delisted_out_of_scope_passes_through_not_treated_as_malformed(self):
        ctx = {"ticker": "AGE", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AGE", _REAL_DELISTED_OUT_OF_SCOPE))
        result = ctx["market_wide_current_descriptive_research"]
        self.assertEqual(_REAL_DELISTED_OUT_OF_SCOPE, result)
        self.assertEqual("INACTIVE_OR_DELISTED", result["activity_and_session_state"])
        self.assertFalse(result["in_current_descriptive_scope"])
        self.assertEqual("not_available", result["status"])

    def test_market_coverage_denominator_and_observed_cohort_always_present(self):
        """denominator=1,510 and observed cohort=960 must travel with every ticker, not just
        same-session-eligible ones, so coverage is never lost when a reader looks at one ticker."""
        for raw in (_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH, _REAL_SHB_SAME_SESSION_ELIGIBLE_RESIDUAL,
                    _REAL_A32_NO_QUALIFIED_SESSION_TECHNICAL_MISSING, _REAL_STALE_SESSION_NOT_CURRENT,
                    _REAL_DELISTED_OUT_OF_SCOPE):
            ctx = {"ticker": raw["ticker"], "provenance": []}
            b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle(raw["ticker"], raw))
            coverage = ctx["market_wide_current_descriptive_research"]["market_coverage"]
            self.assertEqual(1510, coverage["current_active_equity_denominator"])
            self.assertEqual(960, coverage["observed_session_cohort"])

    def test_out_of_universe_ticker_has_no_key(self):
        ctx = {"ticker": "ZZZ_NOT_IN_UNIVERSE", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", _REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH))
        self.assertNotIn("market_wide_current_descriptive_research", ctx)

    def test_absent_key_leaves_context_untouched(self):
        ctx = {"ticker": "FPT", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, {"tickers": {"FPT": {}}})
        self.assertNotIn("market_wide_current_descriptive_research", ctx)

    def test_none_bundle_remains_backward_compatible(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, None)
        self.assertNotIn("market_wide_current_descriptive_research", ctx)

    def test_no_recomputation_deepcopy_not_shared_reference(self):
        raw = copy.deepcopy(_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH)
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", raw))
        ctx["market_wide_current_descriptive_research"]["activity_and_session_state"] = "MUTATED"
        self.assertEqual("ACTIVE_LISTED_OBSERVED", raw["activity_and_session_state"])

    def test_provenance_entry_recorded(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", _REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH))
        sources = [p.get("source_dataset") for p in ctx["provenance"]]
        self.assertIn("market_wide_current_descriptive_research", sources)

    def test_no_secret_or_credential_like_value(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", _REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH))
        dumped = str(ctx["market_wide_current_descriptive_research"]).lower()
        for forbidden in ("token", "secret", "signature", "authorization", "x-api-key", "cookie", "password"):
            self.assertNotIn(forbidden, dumped)

    def test_no_ranking_recommendation_or_sizing_field_anywhere(self):
        """Checks dict KEYS only (not substrings of prose): the real record's own
        blocked_outputs legitimately names "probabilities_or_target_prices" as a key it
        prohibits, and liquidity_research_contract legitimately mentions "turnover" in
        disclaimer text, neither of which should trip this search."""
        forbidden_keys = {"rank", "recommendation_score", "target_price", "buy_signal", "sell_signal",
                          "position_size", "turnover", "adtv", "adv", "traded_value"}

        def collect_keys(obj, found):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k).lower() in forbidden_keys:
                        found.add(str(k))
                    collect_keys(v, found)
            elif isinstance(obj, list):
                for item in obj:
                    collect_keys(item, found)

        for raw in (_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH, _REAL_SHB_SAME_SESSION_ELIGIBLE_RESIDUAL):
            ctx = {"ticker": raw["ticker"], "provenance": []}
            b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle(raw["ticker"], raw))
            found: set[str] = set()
            collect_keys(ctx["market_wide_current_descriptive_research"], found)
            self.assertEqual(set(), found, f"forbidden field(s) present: {found}")


class NeverWidensAProducerVerdict(unittest.TestCase):
    def test_is_actionable_true_is_refused(self):
        bad = {**_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH, "is_actionable": True}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        result = ctx["market_wide_current_descriptive_research"]
        self.assertEqual("malformed", result["status"])
        self.assertFalse(result["is_actionable"])

    def test_available_missing_technical_features_is_refused(self):
        bad = {k: v for k, v in _REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH.items() if k != "technical_features"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_available_missing_market_coverage_is_refused(self):
        bad = {k: v for k, v in _REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH.items() if k != "market_coverage"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_available_missing_blocked_outputs_is_refused(self):
        bad = {k: v for k, v in _REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH.items() if k != "blocked_outputs"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_ticker_mismatch_is_refused(self):
        bad = {**_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH, "ticker": "VNM"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_unknown_activity_state_is_refused(self):
        bad = {**_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH, "activity_and_session_state": "DEFINITELY_FINE_TRUST_ME"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_unknown_status_value_is_refused(self):
        bad = {**_REAL_A32_NO_QUALIFIED_SESSION_TECHNICAL_MISSING, "status": "definitely_available_trust_me"}
        ctx = {"ticker": "A32", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("A32", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_eligible_liquidity_missing_reconciliation_is_refused(self):
        bad = copy.deepcopy(_REAL_SHB_SAME_SESSION_ELIGIBLE_RESIDUAL)
        bad["liquidity"] = {k: v for k, v in bad["liquidity"].items() if k != "g1_v_reconciliation"}
        ctx = {"ticker": "SHB", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("SHB", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_shadow_only_missing_is_current_session_flag_is_refused(self):
        """The one requirement this milestone names explicitly for staleness: a SHADOW_ONLY
        technical-features record that drops is_current_session cannot be silently trusted,
        since that flag is the only thing distinguishing a genuine same-session reading from a
        stale one."""
        bad = copy.deepcopy(_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH)
        del bad["technical_features"]["is_current_session"]
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_non_mapping_raw_is_refused(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", ["not", "a", "mapping"]))
        self.assertEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_malformed_result_is_still_non_actionable(self):
        bad = {**_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH, "is_actionable": True}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        self.assertFalse(ctx["market_wide_current_descriptive_research"]["is_actionable"])

    def test_malformed_input_does_not_corrupt_other_context_fields(self):
        ctx = {"ticker": "AAA", "provenance": [], "some_other_field": "untouched"}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", "not-a-dict"))
        self.assertEqual("untouched", ctx["some_other_field"])

    def test_not_available_records_are_not_refused_for_lacking_liquidity_board_composition(self):
        """A non-"available" status, and an "UNAVAILABLE"/"NOT_APPLICABLE" liquidity state, are
        themselves valid Producer answers -- the same principle
        market_wide_current_liquidity_research already follows for MISSING/PROVIDER_REJECTED."""
        for raw in (_REAL_A32_NO_QUALIFIED_SESSION_TECHNICAL_MISSING, _REAL_DELISTED_OUT_OF_SCOPE):
            ctx = {"ticker": raw["ticker"], "provenance": []}
            b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle(raw["ticker"], raw))
            self.assertNotEqual("malformed", ctx["market_wide_current_descriptive_research"]["status"])

    def test_sector_state_insufficient_coverage_is_not_refused(self):
        """A sector below the minimum cohort size is itself a valid, non-malformed Producer
        answer -- it must never be rejected merely because it reports fewer eligible members,
        and this milestone requires it be preserved verbatim, never filled in or broadened."""
        bad = copy.deepcopy(_REAL_AAA_SAME_SESSION_ELIGIBLE_EXACT_MATCH)
        bad["sector_state"] = {"classification_label": "TINY_SECTOR", "status": "UNAVAILABLE_INSUFFICIENT_COVERAGE",
                               "same_session_eligible_count": 2, "minimum_member_requirement": 5}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_descriptive_research_contract(ctx, _bundle("AAA", bad))
        result = ctx["market_wide_current_descriptive_research"]
        self.assertNotEqual("malformed", result["status"])
        self.assertEqual("UNAVAILABLE_INSUFFICIENT_COVERAGE", result["sector_state"]["status"])


if __name__ == "__main__":
    unittest.main()

