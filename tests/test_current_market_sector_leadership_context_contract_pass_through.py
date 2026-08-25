import copy

from builders.build_ticker_context import (
    apply_bundle_current_market_sector_leadership_context_contract,
    apply_bundle_market_wide_historical_research_context_contract,
    apply_bundle_market_wide_current_valuation_contract,
    current_market_sector_leadership_context_contract,
)

# TEST_FIXTURE_ONLY -- shape verified against stock-core-private commit 8eafa18
# (current_market_sector_leadership_context.py build_artifact() / export_ai_bundle.py
# build_current_market_sector_leadership_context_for_ticker_safe()), read via `git show`
# at that pinned revision, not the (concurrently writable) working tree.
_BLOCKED_OUTPUTS = {
    "global_or_ticker_ranking_score": "NOT_EMITTED", "strategy_eligibility": "NOT_MODIFIED",
    "research_priority": "NOT_MODIFIED", "entry_action": "NOT_MODIFIED", "daily_decision_queue": "NOT_MODIFIED",
    "value_valuation_target_price": "NOT_EMITTED", "sizing_execution": "NOT_EMITTED",
    "raw_as_traded_pit_backtest": "NOT_EMITTED",
}
_AUTHORITY_BOUNDARY = {
    "is_actionable": False, "current_research_only": True,
    "current_cross_sectional_relative_strength_not_historical_pit": True,
    "missing_current_session_bar_is_not_zero": True, "no_opaque_global_score": True,
    "no_strategy_priority_entry_or_sizing_mutation": True,
}


def _market(breadth_state="BROAD_PARTICIPATION"):
    return {
        "session": "2026-08-25", "official_universe_count": 500, "exact_session_observed_count": 480,
        "missing_current_session_count": 20, "breadth_coverage_ratio": 0.96,
        "advancing": 300, "declining": 150, "unchanged": 30,
        "advance_ratio": 0.625, "decline_ratio": 0.3125,
        "positive_momentum_count": 310, "positive_momentum_ratio": 0.6458,
        "negative_momentum_count": 140, "negative_momentum_ratio": 0.2917,
        "trend_participation": {
            "above_ma20_count": 320, "above_ma20_ratio": 0.6667,
            "at_or_below_ma20_count": 160, "at_or_below_ma20_ratio": 0.3333,
        },
        "median_momentum_20d": 0.021, "current_breadth_state": breadth_state,
        "breadth_state_rule": {"rule": "ADVANCE_POSITIVE_MOMENTUM_AND_ABOVE_MA20_ALL_AT_OR_ABOVE_THRESHOLD"},
        "warnings": [
            "CURRENT_SESSION_DESCRIPTIVE_ONLY",
            "MISSING_CURRENT_SESSION_BARS_ARE_COVERAGE_GAPS_NOT_UNCHANGED_OR_ZERO_RETURNS",
            "NO_PRIOR_SESSION_COMPARISON_SO_IMPROVING_BREADTH_IS_NOT_EMITTED",
        ],
    }


def _ticker_context_available(ticker):
    return {
        "ticker": ticker, "status": "AVAILABLE",
        "market_relative_momentum": {
            "status": "AVAILABLE", "momentum_20d": 0.045, "momentum_percentile_descriptive": 0.82,
            "momentum_bucket": "TOP_QUINTILE", "peer_median_momentum_20d": 0.021,
            "valid_observation_count": 480, "authority": "CURRENT_CROSS_SECTIONAL_DESCRIPTIVE_NOT_ORDINAL_RANKING",
        },
        "market_trend_participation_context": {"ticker_trend_state": "ABOVE_MA20", "market_above_ma20_ratio": 0.6667},
        "sector_relative_momentum": {
            "status": "AVAILABLE", "momentum_20d": 0.045, "momentum_percentile_descriptive": 0.9,
            "momentum_bucket": "TOP_QUINTILE", "peer_median_momentum_20d": 0.018, "valid_observation_count": 25,
        },
        "sector_trend_participation_context": {"ticker_trend_state": "ABOVE_MA20", "group_above_ma20_ratio": 0.72},
        "breadth_support_state": "MARKET_AND_GROUP_BREADTH_SUPPORT",
        "sector_leadership_context": {
            "status": "AVAILABLE", "group_key": "QUALIFIED_CLASSIFICATION|QUALIFIED_ENTITY_CLASS|Steel",
            "leadership_state": "LEADING", "group_coverage_ratio": 0.92,
        },
        "coverage_limitations": [],
    }


def _artifact(ticker="AAA"):
    return {
        "ticker": ticker, "session": "2026-08-25", "status": "available", "is_actionable": False,
        "source_artifact_identity": "current_market_sector_leadership_context:abc123",
        "research_mode": "CURRENT_SESSION_DESCRIPTIVE_MARKET_AND_SECTOR_CONTEXT",
        "market": _market(), "ticker_context": _ticker_context_available(ticker),
        "coverage": {
            "official_universe_count": 500, "exact_session_observed_count": 480,
            "missing_current_session_count": 20, "unknown_sector_identity_count": 5,
            "ticker_sector_context_available_count": 420, "ticker_data_limited_count": 40,
        },
        "blocked_outputs": copy.deepcopy(_BLOCKED_OUTPUTS),
        "authority_boundary": copy.deepcopy(_AUTHORITY_BOUNDARY),
    }


def test_available_context_preserves_market_and_ticker_relative_context_without_action():
    raw = _artifact()
    bundle = {"tickers": {"AAA": {"current_market_sector_leadership_context": raw}}}
    assert current_market_sector_leadership_context_contract(bundle, "AAA") == raw
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_market_sector_leadership_context_contract(context, bundle)
    result = context["current_market_sector_leadership_context"]
    assert result["market"]["current_breadth_state"] == "BROAD_PARTICIPATION"
    assert result["ticker_context"]["breadth_support_state"] == "MARKET_AND_GROUP_BREADTH_SUPPORT"
    assert result["ticker_context"]["sector_leadership_context"]["leadership_state"] == "LEADING"
    assert "entry_action" not in result
    assert "research_priority" not in result
    assert "score" not in result


def test_data_limited_ticker_context_with_no_current_technical_bar_remains_explicit():
    """Producer's real shape for a ticker with no current-session technical bar carries no
    market_trend_participation_context/sector_trend_participation_context keys at all --
    verify Consumer preserves that asymmetric shape rather than filling in a default."""
    raw = _artifact()
    raw["status"] = "data_limited"
    raw["ticker_context"] = {
        "ticker": "AAA", "status": "DATA_LIMITED",
        "coverage_limitations": ["NO_CURRENT_EXACT_SESSION_TECHNICAL_CONTEXT"],
        "market_relative_momentum": {"status": "UNAVAILABLE", "reason": "NO_CURRENT_EXACT_SESSION_TECHNICAL_CONTEXT"},
        "sector_relative_momentum": {"status": "UNAVAILABLE", "reason": "NO_CURRENT_EXACT_SESSION_TECHNICAL_CONTEXT"},
        "breadth_support_state": "DATA_LIMITED",
        "sector_leadership_context": {"status": "UNAVAILABLE", "reason": "NO_CURRENT_EXACT_SESSION_TECHNICAL_CONTEXT"},
    }
    bundle = {"tickers": {"AAA": {"current_market_sector_leadership_context": raw}}}
    result = current_market_sector_leadership_context_contract(bundle, "AAA")
    assert result["status"] == "data_limited"
    assert "market_trend_participation_context" not in result["ticker_context"]
    assert result["ticker_context"]["market_relative_momentum"]["status"] == "UNAVAILABLE"


def test_unknown_sector_ticker_relative_context_remains_unavailable_not_inferred():
    raw = _artifact()
    raw["ticker_context"]["sector_relative_momentum"] = {"status": "UNAVAILABLE", "reason": "SECTOR_IDENTITY_UNKNOWN"}
    raw["ticker_context"]["sector_leadership_context"] = {"status": "UNAVAILABLE", "reason": "SECTOR_IDENTITY_UNKNOWN"}
    raw["ticker_context"]["sector_trend_participation_context"] = None
    raw["ticker_context"]["breadth_support_state"] = "MARKET_ONLY_SUPPORT_GROUP_NOT_BROAD"
    bundle = {"tickers": {"AAA": {"current_market_sector_leadership_context": raw}}}
    result = current_market_sector_leadership_context_contract(bundle, "AAA")
    assert result["ticker_context"]["sector_leadership_context"]["status"] == "UNAVAILABLE"
    assert result["ticker_context"]["sector_leadership_context"]["reason"] == "SECTOR_IDENTITY_UNKNOWN"


def test_market_breadth_state_enum_preserved_across_states():
    for state in ("BROAD_PARTICIPATION", "MIXED_BREADTH", "DETERIORATING_BREADTH", "NARROW_LEADERSHIP", "DATA_LIMITED"):
        raw = _artifact()
        raw["market"] = _market(breadth_state=state)
        bundle = {"tickers": {"AAA": {"current_market_sector_leadership_context": raw}}}
        assert current_market_sector_leadership_context_contract(bundle, "AAA")["market"]["current_breadth_state"] == state


def test_research_priority_or_entry_action_mutation_fails_closed():
    raw = _artifact()
    raw["blocked_outputs"]["research_priority"] = "MODIFIED"
    bundle = {"tickers": {"AAA": {"current_market_sector_leadership_context": raw}}}
    assert current_market_sector_leadership_context_contract(bundle, "AAA")["status"] == "malformed"

    raw = _artifact()
    raw["blocked_outputs"]["entry_action"] = "MODIFIED"
    bundle = {"tickers": {"AAA": {"current_market_sector_leadership_context": raw}}}
    assert current_market_sector_leadership_context_contract(bundle, "AAA")["status"] == "malformed"


def test_opaque_score_authority_violation_fails_closed():
    raw = _artifact()
    raw["authority_boundary"]["no_opaque_global_score"] = False
    bundle = {"tickers": {"AAA": {"current_market_sector_leadership_context": raw}}}
    assert current_market_sector_leadership_context_contract(bundle, "AAA")["status"] == "malformed"


def test_absent_optional_layer_fails_closed_without_invalidating_context():
    assert current_market_sector_leadership_context_contract({"tickers": {"AAA": {}}}, "AAA") is None
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_market_sector_leadership_context_contract(context, {"tickers": {"AAA": {}}})
    assert "current_market_sector_leadership_context" not in context


def test_can_coexist_with_historical_and_valuation_without_joint_signal():
    sector = _artifact()
    historical = {
        "ticker": "AAA", "status": "available", "is_actionable": False, "session": "2026-08-24",
        "source_artifact_identity": "market_wide_historical_research_context:abc123",
        "research_mode": "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER",
        "coverage": {"in_scope_count": 1}, "blocked_outputs": {"historical_performance_backtest_alpha": "NOT_EMITTED"},
        "authority_boundary": {
            "research_mode": "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER",
            "price_basis": "ADJUSTED_RETROSPECTIVE", "RAW_AS_TRADED": "NOT_PROMOTED", "PIT": "BLOCKED",
        },
        "in_current_descriptive_scope": True, "context_status": "AVAILABLE",
        "as_of_session": "2026-08-24", "is_current_session": True,
        "history": {
            "observation_count": 40, "last_session": "2026-08-24", "price_basis": "ADJUSTED_RETROSPECTIVE",
            "raw_as_traded": "NOT_PROMOTED", "historical_pit_eligible": False,
        },
        "trailing_range": {"status": "AVAILABLE", "value": "retained"},
        "fifty_two_week_range": {"status": "AVAILABLE", "value": "retained"},
        "drawdown": {"status": "AVAILABLE", "value": "retained"},
        "volatility_regime": {"status": "AVAILABLE", "value": "retained"},
        "momentum": {"status": "AVAILABLE", "value": "retained"},
        "ma_alignment": {"status": "AVAILABLE", "value": "retained"},
        "relative_volume": {"status": "AVAILABLE", "value": "retained"},
        "technical_state_frequency": {"status": "AVAILABLE", "value": "retained"},
        "structural_state": {"status": "AVAILABLE", "value": "BASE", "not_entry_state": True, "not_strategy_eligibility": True},
    }
    valuation = {
        "ticker": "AAA", "status": "current_valuation_snapshot", "is_actionable": False,
        "entity_class": "corporate", "price_input": {"status": "PRICE_READY", "session": "2026-08-24"},
        "share_basis_input": {"status": "PROVIDER_REPORTED_LAGGED"},
        "financial_input": {"authority": "OFFICIAL_QUALIFIED"},
        "metrics": {"P/E": {"status": "BLOCKED", "value": None, "price_session": "2026-08-24"}},
    }
    bundle = {"tickers": {"AAA": {
        "current_market_sector_leadership_context": sector,
        "market_wide_historical_research_context": historical,
        "market_wide_current_valuation": valuation,
    }}}
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_market_sector_leadership_context_contract(context, bundle)
    apply_bundle_market_wide_historical_research_context_contract(context, bundle)
    apply_bundle_market_wide_current_valuation_contract(context, bundle)
    assert context["current_market_sector_leadership_context"] == sector
    assert context["market_wide_historical_research_context"] == historical
    assert context["market_wide_current_valuation"] == valuation
    assert "entry_action" not in context
    assert "research_priority" not in context
    assert "combined_score" not in context
