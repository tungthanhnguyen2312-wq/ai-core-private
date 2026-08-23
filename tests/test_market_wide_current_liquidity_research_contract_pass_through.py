"""Consumer pass-through tests for the market_wide_current_liquidity_research contract.

Mirrors tests/test_qualified_market_observations_contract.py's structural-validity pattern
(this contract is a market-wide, ticker-keyed dataset, not a single-ticker evidence store like
current_state_market_risk) and tests/test_current_state_market_risk_contract_pass_through.py's
convention of embedding real Producer values rather than synthetic shapes.

tickers[ticker].market_wide_current_liquidity_research is a byte-identical pass-through of one
record from stock-core-private's retained market_wide_current_liquidity_research artifact
(tools/run_market_wide_current_liquidity_research.py), plus the "status"/"is_actionable"/
"reconciliation_verdict" fields export_ai_bundle.py's attach layer adds. Consumer never
recomputes board composition, a reconciliation verdict, a traded value, turnover, ADTV, ADV, a
position size, or an execution capacity.

_REAL_AAA_ELIGIBLE_EXACT_MATCH, _REAL_SHB_ELIGIBLE_RESIDUAL, _REAL_A32_MISSING, and
_REAL_CYC_PROVIDER_REJECTED below are real values captured 2026-08-23 by running the actual
Producer export_ai_bundle.attach_market_wide_current_liquidity_research() against the actual
retained checkpoint (operations-review/market-wide-current-liquidity-research-v1-20260823-
resumable/market_wide_current_liquidity_research_artifact.json,
artifact_sha256=dc9b464914c8da2a8b27e51ab0e427d099f8d5fa5fd5d3392cb65e85f09ecbbb) and feeding the
result through this repository's own apply_bundle_market_wide_current_liquidity_research_contract()
-- the same frozen-time proof re-run live (against the sibling Producer checkout, skipped if
unavailable) in FrozenTimeProducerConsumerEndToEndTests below. SHB is the real four-unit
G1-vs-OHLC-v residual (delta=4.0, verdict="OTHER") this milestone must never coerce.
"""
from __future__ import annotations

import copy
import unittest

from builders import build_ticker_context as b

_REAL_AAA_ELIGIBLE_EXACT_MATCH = {'board_composition': {'MATCHED_ODD_LOT': {'active_volume_raw_total': 1218.0,
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
 'board_snapshot': {'boards': {'G1': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 7.006,
                                      'board_id': 'G1',
                                      'board_semantic': 'ROUND_LOT',
                                      'cumulative_gross_trade_amount_raw': 7.915136,
                                      'cumulative_volume_raw': 112970.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000AAA4',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 7.12,
                                      'match_quantity_raw': 1000.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '4cd32d7490784cea85c2ed94af0f625fe6aca6f83921196df313530b280e26e6',
                                      'raw_time': '2026-08-21 14:45:01.582',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'SELL',
                                      'symbol': 'AAA'},
                               'G4': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 7.009,
                                      'board_id': 'G4',
                                      'board_semantic': 'ODD_LOT',
                                      'cumulative_gross_trade_amount_raw': 0.00853662,
                                      'cumulative_volume_raw': 1218.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000AAA4',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 7.1,
                                      'match_quantity_raw': 1.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': 'f247fb04f0e1a0b49ad2e195d1f92fa01de23874a0f5523df7fd58a7940fd6f3',
                                      'raw_time': '2026-08-21 14:45:00.877',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'SELL',
                                      'symbol': 'AAA'},
                               'T1': {'activity_state': 'OBSERVED_INACTIVE_STALE',
                                      'avg_price_kvnd': 6.35,
                                      'board_id': 'T1',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT',
                                      'cumulative_gross_trade_amount_raw': 2.52476,
                                      'cumulative_volume_raw': 39760.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000AAA4',
                                      'last_active_session_date': '2026-07-29',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 6.35,
                                      'match_quantity_raw': 3890.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': 'b97f098473a0370fa29c7a157e47334c010272493e2121628aed9bcfe7ee3de3',
                                      'raw_time': '2026-07-29 14:03:31.268',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-07-29',
                                      'side_raw': 'SELL',
                                      'symbol': 'AAA'},
                               'T3': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT'},
                               'T4': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 6.42,
                                      'board_id': 'T4',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT',
                                      'cumulative_gross_trade_amount_raw': 0.0002568,
                                      'cumulative_volume_raw': 40.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000AAA4',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 6.42,
                                      'match_quantity_raw': 1.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '9cebfd2cc16a8e7a81125aa2fd1fbb8f9ee28e56f3481689630d508a9ac4d74e',
                                      'raw_time': '2026-08-21 14:13:55.276',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'SELL',
                                      'symbol': 'AAA'},
                               'T6': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT'}},
                    'target_session_date': '2026-08-21'},
 'current_ohlc_v': 1129700.0,
 'disposition': 'CURRENT_SESSION_DESCRIPTIVE_ELIGIBLE',
 'g1_v_reconciliation': {'candidate': {'candidate_id': 'C5',
                                       'candidate_type': 'SCALED_G1',
                                       'empirical_scale': 10.0,
                                       'evidence_source': 'p0-b2ab-zero-match-root-cause-diagnosis-v1-20260818: '
                                                          'daily_v / board_G1_quantity clusters at '
                                                          'exactly 10.0 across 35,164/35,231 '
                                                          '(99.8098%) symbol-sessions over 40 '
                                                          'retained trading dates; scale '
                                                          'discovered from data, not from a '
                                                          'provider unit assertion',
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
 'is_actionable': False,
 'liquidity_research_contract': {'ADTV_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.gross_trade_amount_uniform_formula_check',
                                                             'docs/STATE.md P0-B'],
                                                   'reason': 'average daily traded VALUE inherits '
                                                             'the same multi-session completeness '
                                                             'blocker as ADV, plus the open '
                                                             'grossTradeAmount board-dependent '
                                                             'scale ambiguity documented in this '
                                                             'module',
                                                   'state': 'BLOCKED'},
                                 'ADV_VOLUME_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness',
                                                                   'docs/STATE.md P0-B'],
                                                         'reason': 'average daily volume requires '
                                                                   'multiple complete sessions; '
                                                                   'bounded trades_history '
                                                                   'pagination is proven '
                                                                   'activity-dependent (complete '
                                                                   'for a low-activity name, '
                                                                   'left-truncated for a '
                                                                   "high-activity name's auction "
                                                                   'burst) and cannot be relied on '
                                                                   'across an arbitrary '
                                                                   'multi-session window within a '
                                                                   'finite call budget',
                                                         'state': 'BLOCKED'},
                                 'CURRENT_SESSION_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.board_latest_snapshot'],
                                                                        'reason': 'trades_latest '
                                                                                  'gives a '
                                                                                  'complete, '
                                                                                  'non-paginated '
                                                                                  'per-board '
                                                                                  'cumulative '
                                                                                  'volume/value '
                                                                                  'reading for the '
                                                                                  'most recently '
                                                                                  'active session; '
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
                                                                  'POSITION_SIZING; inherits the '
                                                                  'same block',
                                                        'state': 'BLOCKED'},
                                 'HISTORICAL_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness'],
                                                                   'reason': 'no bounded '
                                                                             'historical scan was '
                                                                             'supplied for this '
                                                                             'evaluation',
                                                                   'state': 'UNKNOWN'},
                                 'PIT_BACKTEST': {'cites': ['market_data_source_authority.DNSE_OHLC_PRICE_BASIS'],
                                                  'reason': 'DNSE OHLC price basis remains '
                                                            'ADJUSTED_CONFIRMED_NON_RAW_NON_POINT_IN_TIME '
                                                            "regardless of this milestone's volume "
                                                            'findings',
                                                  'state': 'BLOCKED'},
                                 'POSITION_SIZING': {'cites': ['dnse_trades_liquidity_basis.derived_value_price_times_shares',
                                                               'docs/STATE.md Invariant 2'],
                                                     'reason': 'no historical completeness, no '
                                                               'resolved lot-multiplier, no '
                                                               'qualified PIT price basis',
                                                     'state': 'BLOCKED'}},
 'reconciliation_verdict': 'EXACT_MATCH',
 'session': '2026-08-21',
 'status': 'available',
 'ticker': 'AAA',
 'value_status': 'GROSS_TRADE_AMOUNT_RETAINED_ONLY_NON_AUTHORITATIVE_SCALE_BASIS_UNRESOLVED'}

_REAL_SHB_ELIGIBLE_RESIDUAL = {'board_composition': {'MATCHED_ODD_LOT': {'active_volume_raw_total': 22319.0,
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
 'board_snapshot': {'boards': {'G1': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 11.76,
                                      'board_id': 'G1',
                                      'board_semantic': 'ROUND_LOT',
                                      'cumulative_gross_trade_amount_raw': 818.672845,
                                      'cumulative_volume_raw': 6961550.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000SHB9',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 11.9,
                                      'match_quantity_raw': 320.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '2555cb5bcd0f07c344e985c308d0c06d78626fa98c23808726c9508aa7807877',
                                      'raw_time': '2026-08-21 14:45:04.815',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'BUY',
                                      'symbol': 'SHB'},
                               'G4': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 11.759,
                                      'board_id': 'G4',
                                      'board_semantic': 'ODD_LOT',
                                      'cumulative_gross_trade_amount_raw': 0.26245235,
                                      'cumulative_volume_raw': 22319.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000SHB9',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 11.85,
                                      'match_quantity_raw': 10.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '6045db821452fbba19c74fb5e875d3a7a6d1eb1689d6c1b2e3b2e1840ab7502a',
                                      'raw_time': '2026-08-21 14:45:01.246',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'SELL',
                                      'symbol': 'SHB'},
                               'T1': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 11.197,
                                      'board_id': 'T1',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT',
                                      'cumulative_gross_trade_amount_raw': 138.477,
                                      'cumulative_volume_raw': 1236700.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000SHB9',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 11.0,
                                      'match_quantity_raw': 46700.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '6d4c09b40b61712c07bf5719e391305ec1099135d27362e7bb146017432952d3',
                                      'raw_time': '2026-08-21 13:43:40.716',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'SELL',
                                      'symbol': 'SHB'},
                               'T3': {'activity_state': 'OBSERVED_INACTIVE_STALE',
                                      'avg_price_kvnd': 12.4,
                                      'board_id': 'T3',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT',
                                      'cumulative_gross_trade_amount_raw': 24.8,
                                      'cumulative_volume_raw': 200000.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000SHB9',
                                      'last_active_session_date': '2026-08-19',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 12.4,
                                      'match_quantity_raw': 200000.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': 'a8a3a3b44d6d56aadbe0b4579b2c3e2453ee9fa3ce2bc89182eddc30ddce08d2',
                                      'raw_time': '2026-08-19 14:46:12.047',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-19',
                                      'side_raw': 'UNSPECIFIED',
                                      'symbol': 'SHB'},
                               'T4': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 10.8,
                                      'board_id': 'T4',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT',
                                      'cumulative_gross_trade_amount_raw': 8.64e-05,
                                      'cumulative_volume_raw': 8.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000SHB9',
                                      'market_id_raw': 'STO',
                                      'match_price_kvnd': 10.8,
                                      'match_quantity_raw': 1.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '20c5eae0330cf71356b115eacc671e29dd5aa28a5e98991e37b34e1862d02987',
                                      'raw_time': '2026-08-21 13:34:02.624',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'SELL',
                                      'symbol': 'SHB'},
                               'T6': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT'}},
                    'target_session_date': '2026-08-21'},
 'current_ohlc_v': 69615504.0,
 'disposition': 'CURRENT_SESSION_DESCRIPTIVE_ELIGIBLE',
 'g1_v_reconciliation': {'candidate': {'candidate_id': 'C5',
                                       'candidate_type': 'SCALED_G1',
                                       'empirical_scale': 10.0,
                                       'evidence_source': 'p0-b2ab-zero-match-root-cause-diagnosis-v1-20260818: '
                                                          'daily_v / board_G1_quantity clusters at '
                                                          'exactly 10.0 across 35,164/35,231 '
                                                          '(99.8098%) symbol-sessions over 40 '
                                                          'retained trading dates; scale '
                                                          'discovered from data, not from a '
                                                          'provider unit assertion',
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
 'is_actionable': False,
 'liquidity_research_contract': {'ADTV_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.gross_trade_amount_uniform_formula_check',
                                                             'docs/STATE.md P0-B'],
                                                   'reason': 'average daily traded VALUE inherits '
                                                             'the same multi-session completeness '
                                                             'blocker as ADV, plus the open '
                                                             'grossTradeAmount board-dependent '
                                                             'scale ambiguity documented in this '
                                                             'module',
                                                   'state': 'BLOCKED'},
                                 'ADV_VOLUME_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness',
                                                                   'docs/STATE.md P0-B'],
                                                         'reason': 'average daily volume requires '
                                                                   'multiple complete sessions; '
                                                                   'bounded trades_history '
                                                                   'pagination is proven '
                                                                   'activity-dependent (complete '
                                                                   'for a low-activity name, '
                                                                   'left-truncated for a '
                                                                   "high-activity name's auction "
                                                                   'burst) and cannot be relied on '
                                                                   'across an arbitrary '
                                                                   'multi-session window within a '
                                                                   'finite call budget',
                                                         'state': 'BLOCKED'},
                                 'CURRENT_SESSION_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.board_latest_snapshot'],
                                                                        'reason': 'trades_latest '
                                                                                  'gives a '
                                                                                  'complete, '
                                                                                  'non-paginated '
                                                                                  'per-board '
                                                                                  'cumulative '
                                                                                  'volume/value '
                                                                                  'reading for the '
                                                                                  'most recently '
                                                                                  'active session; '
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
                                                                  'POSITION_SIZING; inherits the '
                                                                  'same block',
                                                        'state': 'BLOCKED'},
                                 'HISTORICAL_LIQUIDITY_RESEARCH': {'cites': ['dnse_trades_liquidity_basis.scan_completeness'],
                                                                   'reason': 'no bounded '
                                                                             'historical scan was '
                                                                             'supplied for this '
                                                                             'evaluation',
                                                                   'state': 'UNKNOWN'},
                                 'PIT_BACKTEST': {'cites': ['market_data_source_authority.DNSE_OHLC_PRICE_BASIS'],
                                                  'reason': 'DNSE OHLC price basis remains '
                                                            'ADJUSTED_CONFIRMED_NON_RAW_NON_POINT_IN_TIME '
                                                            "regardless of this milestone's volume "
                                                            'findings',
                                                  'state': 'BLOCKED'},
                                 'POSITION_SIZING': {'cites': ['dnse_trades_liquidity_basis.derived_value_price_times_shares',
                                                               'docs/STATE.md Invariant 2'],
                                                     'reason': 'no historical completeness, no '
                                                               'resolved lot-multiplier, no '
                                                               'qualified PIT price basis',
                                                     'state': 'BLOCKED'}},
 'reconciliation_verdict': 'OTHER',
 'session': '2026-08-21',
 'status': 'available',
 'ticker': 'SHB',
 'value_status': 'GROSS_TRADE_AMOUNT_RETAINED_ONLY_NON_AUTHORITATIVE_SCALE_BASIS_UNRESOLVED'}

_REAL_A32_MISSING = {'board_snapshot': {'boards': {'G1': {'activity_state': 'OBSERVED_INACTIVE_STALE',
                                      'avg_price_kvnd': 29.7,
                                      'board_id': 'G1',
                                      'board_semantic': 'ROUND_LOT',
                                      'cumulative_gross_trade_amount_raw': 0.00297,
                                      'cumulative_volume_raw': 10.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000A329',
                                      'last_active_session_date': '2026-08-17',
                                      'market_id_raw': 'UPX',
                                      'match_price_kvnd': 29.7,
                                      'match_quantity_raw': 10.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '0b41d761459b2176b6190f06e53ef642224d380e88586b6065898e8e06cb4a31',
                                      'raw_time': '2026-08-17 14:12:38.542',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-17',
                                      'side_raw': 'BUY',
                                      'symbol': 'A32'},
                               'G4': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 30.0,
                                      'board_id': 'G4',
                                      'board_semantic': 'ODD_LOT',
                                      'cumulative_gross_trade_amount_raw': 3e-05,
                                      'cumulative_volume_raw': 1.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000A329',
                                      'market_id_raw': 'UPX',
                                      'match_price_kvnd': 30.0,
                                      'match_quantity_raw': 1.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '9fde5f5d05b06f34c40a91a27fbc9a7a3462a7b0752fb8f2d2310a3278a22e4b',
                                      'raw_time': '2026-08-21 13:00:02.029',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-08-21',
                                      'side_raw': 'SELL',
                                      'symbol': 'A32'},
                               'T1': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT'},
                               'T3': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT'},
                               'T4': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT'},
                               'T6': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT'}},
                    'target_session_date': '2026-08-21'},
 'disposition': 'MISSING',
 'is_actionable': False,
 'reason': 'COMPATIBLE_CURRENT_OHLC_V_MISSING',
 'reconciliation_verdict': None,
 'status': 'not_available',
 'ticker': 'A32'}

_REAL_CYC_PROVIDER_REJECTED = {'board_snapshot': {'boards': {'G1': {'activity_state': 'OBSERVED_INACTIVE_STALE',
                                      'avg_price_kvnd': 1.2,
                                      'board_id': 'G1',
                                      'board_semantic': 'ROUND_LOT',
                                      'cumulative_gross_trade_amount_raw': 0.00036,
                                      'cumulative_volume_raw': 30.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000CYC6',
                                      'last_active_session_date': '2026-04-17',
                                      'market_id_raw': 'UPX',
                                      'match_price_kvnd': 1.2,
                                      'match_quantity_raw': 30.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': 'ef66c4326cb24fa91cee356166a3f71240d654d2ce5c73f7181ee438ba587587',
                                      'raw_time': '2026-04-17 09:16:47.999',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-04-17',
                                      'side_raw': 'BUY',
                                      'symbol': 'CYC'},
                               'G4': {'activity_state': 'OBSERVED_ACTIVE_THIS_SESSION',
                                      'avg_price_kvnd': 1.1,
                                      'board_id': 'G4',
                                      'board_semantic': 'ODD_LOT',
                                      'cumulative_gross_trade_amount_raw': 5.5e-05,
                                      'cumulative_volume_raw': 50.0,
                                      'endpoint': 'trades_latest',
                                      'isin_raw': 'VN000000CYC6',
                                      'market_id_raw': 'UPX',
                                      'match_price_kvnd': 1.1,
                                      'match_quantity_raw': 50.0,
                                      'parse_status': 'PARSED',
                                      'provider': 'DNSE',
                                      'raw_sha256': '56c5d35ada64b4f82306e8efc98154911ca8bbe8d5b988d5483d340f4f139552',
                                      'raw_time': '2026-07-24 09:02:01.700',
                                      'schema_version': 'dnse_trade_tick/v1',
                                      'session_date': '2026-07-24',
                                      'side_raw': 'BUY',
                                      'symbol': 'CYC'},
                               'T1': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT'},
                               'T3': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ROUND_LOT'},
                               'T4': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT'},
                               'T6': {'activity_state': 'NOT_OBSERVED',
                                      'board_semantic': 'PUT_THROUGH_ODD_LOT'}},
                    'target_session_date': '2026-07-24'},
 'disposition': 'PROVIDER_REJECTED',
 'is_actionable': False,
 'reason': 'CURRENT_OHLC_UNAVAILABLE',
 'reconciliation_verdict': None,
 'status': 'not_available',
 'ticker': 'CYC'}


def _bundle(ticker: str, raw) -> dict:
    return {"tickers": {ticker: {"market_wide_current_liquidity_research": raw}}}


class VerbatimPassThrough(unittest.TestCase):
    def test_eligible_exact_match_passes_through_unchanged(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", _REAL_AAA_ELIGIBLE_EXACT_MATCH))
        self.assertEqual(_REAL_AAA_ELIGIBLE_EXACT_MATCH, ctx["market_wide_current_liquidity_research"])
        self.assertEqual(ctx["provenance"][-1]["source_dataset"], "market_wide_current_liquidity_research")

    def test_shb_four_unit_residual_preserved_verbatim_never_coerced(self):
        """The one requirement this milestone names explicitly: SHB's non-exact reconciliation
        must survive Consumer pass-through exactly, never upgraded to EXACT_MATCH."""
        ctx = {"ticker": "SHB", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("SHB", _REAL_SHB_ELIGIBLE_RESIDUAL))
        result = ctx["market_wide_current_liquidity_research"]
        self.assertEqual(_REAL_SHB_ELIGIBLE_RESIDUAL, result)
        self.assertEqual("OTHER", result["reconciliation_verdict"])
        self.assertEqual("OTHER", result["g1_v_reconciliation"]["verdict"])
        self.assertEqual(4.0, result["g1_v_reconciliation"]["delta"])
        self.assertFalse(result["g1_v_reconciliation"]["exact_match"])
        # Still descriptive-eligible: a reconciliation residual is a warning, not a rejection.
        self.assertEqual("CURRENT_SESSION_DESCRIPTIVE_ELIGIBLE", result["disposition"])

    def test_missing_disposition_passes_through_not_treated_as_malformed(self):
        ctx = {"ticker": "A32", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("A32", _REAL_A32_MISSING))
        result = ctx["market_wide_current_liquidity_research"]
        self.assertEqual(_REAL_A32_MISSING, result)
        self.assertEqual("MISSING", result["disposition"])
        self.assertEqual("not_available", result["status"])
        self.assertNotIn("board_composition", result)

    def test_provider_rejected_disposition_passes_through_not_treated_as_malformed(self):
        ctx = {"ticker": "CYC", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("CYC", _REAL_CYC_PROVIDER_REJECTED))
        result = ctx["market_wide_current_liquidity_research"]
        self.assertEqual(_REAL_CYC_PROVIDER_REJECTED, result)
        self.assertEqual("PROVIDER_REJECTED", result["disposition"])
        self.assertEqual("not_available", result["status"])

    def test_out_of_universe_ticker_has_no_key_distinct_from_missing(self):
        """A ticker the retained artifact never attempted is a fifth, separate case from an
        in-universe MISSING record -- no key at all, never a synthesized disposition."""
        ctx = {"ticker": "ZZZ_NOT_IN_UNIVERSE", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", _REAL_AAA_ELIGIBLE_EXACT_MATCH))
        self.assertNotIn("market_wide_current_liquidity_research", ctx)

    def test_absent_key_leaves_context_untouched(self):
        ctx = {"ticker": "FPT", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, {"tickers": {"FPT": {}}})
        self.assertNotIn("market_wide_current_liquidity_research", ctx)

    def test_none_bundle_remains_backward_compatible(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, None)
        self.assertNotIn("market_wide_current_liquidity_research", ctx)

    def test_no_recomputation_deepcopy_not_shared_reference(self):
        raw = copy.deepcopy(_REAL_AAA_ELIGIBLE_EXACT_MATCH)
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", raw))
        ctx["market_wide_current_liquidity_research"]["disposition"] = "MUTATED"
        self.assertEqual("CURRENT_SESSION_DESCRIPTIVE_ELIGIBLE", raw["disposition"])

    def test_provenance_entry_recorded(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", _REAL_AAA_ELIGIBLE_EXACT_MATCH))
        sources = [p.get("source_dataset") for p in ctx["provenance"]]
        self.assertIn("market_wide_current_liquidity_research", sources)

    def test_no_secret_or_credential_like_value(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", _REAL_AAA_ELIGIBLE_EXACT_MATCH))
        dumped = str(ctx["market_wide_current_liquidity_research"]).lower()
        for forbidden in ("token", "secret", "signature", "authorization", "x-api-key", "cookie", "password"):
            self.assertNotIn(forbidden, dumped)

    def test_no_turnover_adtv_adv_or_sizing_field_anywhere(self):
        """grossTradeAmount stays non-authoritative: Consumer must never see -- because
        Producer must never emit -- a derived traded-value/turnover/ADTV/ADV/sizing *field*
        alongside the real record. This checks dict KEYS only (not substrings of prose): the
        real record's own liquidity_research_contract legitimately mentions "turnover" in
        disclaimer text ("not a promoted liquidity/turnover authority"), which must not trip a
        naive substring search."""
        forbidden_keys = {"turnover", "adtv", "adv", "position_size", "traded_value",
                          "traded_value_vnd", "turnover_ratio", "adtv_vnd", "adv_shares"}

        def collect_keys(obj, found):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if str(k).lower() in forbidden_keys:
                        found.add(str(k))
                    collect_keys(v, found)
            elif isinstance(obj, list):
                for item in obj:
                    collect_keys(item, found)

        for raw in (_REAL_AAA_ELIGIBLE_EXACT_MATCH, _REAL_SHB_ELIGIBLE_RESIDUAL):
            ctx = {"ticker": raw["ticker"], "provenance": []}
            b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle(raw["ticker"], raw))
            found: set[str] = set()
            collect_keys(ctx["market_wide_current_liquidity_research"], found)
            self.assertEqual(set(), found, f"forbidden field(s) present: {found}")


class NeverWidensAProducerVerdict(unittest.TestCase):
    def test_is_actionable_true_is_refused(self):
        bad = {**_REAL_AAA_ELIGIBLE_EXACT_MATCH, "is_actionable": True}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", bad))
        result = ctx["market_wide_current_liquidity_research"]
        self.assertEqual("malformed", result["status"])
        self.assertFalse(result["is_actionable"])

    def test_available_missing_board_composition_is_refused(self):
        bad = {k: v for k, v in _REAL_AAA_ELIGIBLE_EXACT_MATCH.items() if k != "board_composition"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_available_missing_g1_v_reconciliation_is_refused(self):
        bad = {k: v for k, v in _REAL_AAA_ELIGIBLE_EXACT_MATCH.items() if k != "g1_v_reconciliation"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_available_missing_liquidity_research_contract_is_refused(self):
        bad = {k: v for k, v in _REAL_AAA_ELIGIBLE_EXACT_MATCH.items() if k != "liquidity_research_contract"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_ticker_mismatch_is_refused(self):
        bad = {**_REAL_AAA_ELIGIBLE_EXACT_MATCH, "ticker": "VNM"}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", bad))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_unknown_disposition_value_is_refused(self):
        bad = {**_REAL_A32_MISSING, "disposition": "DEFINITELY_FINE_TRUST_ME"}
        ctx = {"ticker": "A32", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("A32", bad))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_unknown_status_value_is_refused(self):
        bad = {**_REAL_A32_MISSING, "status": "definitely_available_trust_me"}
        ctx = {"ticker": "A32", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("A32", bad))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_non_exact_verdict_coerced_toward_exact_match_is_refused(self):
        """Even if a corrupted/tampered upstream payload tried to smuggle SHB's real residual
        board data under a claimed EXACT_MATCH verdict, the mismatch between the verdict and
        its own delta/exact_match fields must never be silently accepted as if genuine -- this
        contract only ever forwards what the Producer actually computed, never reinterprets it."""
        bad = copy.deepcopy(_REAL_SHB_ELIGIBLE_RESIDUAL)
        bad["g1_v_reconciliation"] = {}
        ctx = {"ticker": "SHB", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("SHB", bad))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_non_mapping_raw_is_refused(self):
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", ["not", "a", "mapping"]))
        self.assertEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])

    def test_malformed_result_is_still_non_actionable(self):
        bad = {**_REAL_AAA_ELIGIBLE_EXACT_MATCH, "is_actionable": True}
        ctx = {"ticker": "AAA", "provenance": []}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", bad))
        self.assertFalse(ctx["market_wide_current_liquidity_research"]["is_actionable"])

    def test_malformed_input_does_not_corrupt_other_context_fields(self):
        ctx = {"ticker": "AAA", "provenance": [], "some_other_field": "untouched"}
        b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle("AAA", "not-a-dict"))
        self.assertEqual("untouched", ctx["some_other_field"])

    def test_missing_and_provider_rejected_records_are_not_refused_for_lacking_board_composition(self):
        """A non-"available" status is itself a valid Producer answer -- the same principle
        qualified_market_observations already follows for its own "unavailable" verdict."""
        for raw in (_REAL_A32_MISSING, _REAL_CYC_PROVIDER_REJECTED):
            ctx = {"ticker": raw["ticker"], "provenance": []}
            b.apply_bundle_market_wide_current_liquidity_research_contract(ctx, _bundle(raw["ticker"], raw))
            self.assertNotEqual("malformed", ctx["market_wide_current_liquidity_research"]["status"])


if __name__ == "__main__":
    unittest.main()
