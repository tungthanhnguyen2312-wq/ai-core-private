import copy

from builders.build_ticker_context import (
    apply_bundle_market_wide_historical_research_context_contract,
    market_wide_historical_research_context_contract,
)


def _available():
    session = "2026-08-24"
    field = {"status": "AVAILABLE", "value": "retained"}
    return {
        "ticker": "AAA", "status": "available", "is_actionable": False,
        "session": session,
        "source_artifact_identity": "market_wide_historical_research_context:abc123",
        "research_mode": "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER",
        "coverage": {"in_scope_count": 1},
        "blocked_outputs": {"historical_performance_backtest_alpha": "NOT_EMITTED"},
        "authority_boundary": {
            "research_mode": "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER",
            "price_basis": "ADJUSTED_RETROSPECTIVE", "RAW_AS_TRADED": "NOT_PROMOTED", "PIT": "BLOCKED",
        },
        "in_current_descriptive_scope": True, "context_status": "AVAILABLE",
        "as_of_session": session, "is_current_session": True,
        "history": {
            "observation_count": 40, "last_session": session,
            "price_basis": "ADJUSTED_RETROSPECTIVE", "raw_as_traded": "NOT_PROMOTED",
            "historical_pit_eligible": False,
        },
        "trailing_range": copy.deepcopy(field), "fifty_two_week_range": copy.deepcopy(field),
        "drawdown": copy.deepcopy(field), "volatility_regime": copy.deepcopy(field),
        "momentum": copy.deepcopy(field), "ma_alignment": copy.deepcopy(field),
        "relative_volume": copy.deepcopy(field), "technical_state_frequency": copy.deepcopy(field),
        "structural_state": {
            "status": "AVAILABLE", "value": "BASE", "not_entry_state": True,
            "not_strategy_eligibility": True,
        },
        "current_feature_window": {
            "status": "SHADOW_ONLY", "price_basis": "ADJUSTED_RETROSPECTIVE",
            "historical_pit_eligible": False,
        },
    }


def test_available_context_preserves_retrospective_identity_and_structure_without_action():
    raw = _available()
    bundle = {"tickers": {"AAA": {"market_wide_historical_research_context": raw}}}
    assert market_wide_historical_research_context_contract(bundle, "AAA") == raw
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_market_wide_historical_research_context_contract(context, bundle)
    result = context["market_wide_historical_research_context"]
    assert result["research_mode"] == "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER"
    assert result["history"]["price_basis"] == "ADJUSTED_RETROSPECTIVE"
    assert result["structural_state"]["value"] == "BASE"
    assert "entry_action" not in result


def test_partial_and_insufficient_or_missing_contexts_remain_explicit():
    raw = _available()
    raw["context_status"] = "PARTIAL"
    raw["relative_volume"] = {"status": "PARTIAL", "value": None, "reason": "SHORT_RETAINED_HISTORY"}
    assert market_wide_historical_research_context_contract(
        {"tickers": {"AAA": {"market_wide_historical_research_context": raw}}}, "AAA"
    )["context_status"] == "PARTIAL"

    raw = _available()
    raw["context_status"] = "INSUFFICIENT_HISTORY"
    raw["as_of_session"] = None
    raw["is_current_session"] = False
    raw["history"]["last_session"] = None
    raw["structural_state"] = {"status": "INSUFFICIENT_HISTORY", "value": None}
    assert market_wide_historical_research_context_contract(
        {"tickers": {"AAA": {"market_wide_historical_research_context": raw}}}, "AAA"
    )["context_status"] == "INSUFFICIENT_HISTORY"

    raw = _available()
    raw["context_status"] = "MISSING"
    raw["as_of_session"] = None
    raw["is_current_session"] = False
    raw["history"]["last_session"] = None
    raw["structural_state"] = {"status": "MISSING", "value": None}
    assert market_wide_historical_research_context_contract(
        {"tickers": {"AAA": {"market_wide_historical_research_context": raw}}}, "AAA"
    )["context_status"] == "MISSING"


def test_adjusted_history_cannot_be_promoted_to_raw_pit_or_entry_state():
    raw = _available()
    raw["history"]["raw_as_traded"] = "RAW_AS_TRADED"
    assert market_wide_historical_research_context_contract(
        {"tickers": {"AAA": {"market_wide_historical_research_context": raw}}}, "AAA"
    )["status"] == "malformed"

    raw = _available()
    raw["structural_state"]["not_entry_state"] = False
    assert market_wide_historical_research_context_contract(
        {"tickers": {"AAA": {"market_wide_historical_research_context": raw}}}, "AAA"
    )["status"] == "malformed"


def test_absent_malformed_and_session_incoherent_optional_layer_fail_closed_without_invalidating_context():
    assert market_wide_historical_research_context_contract({"tickers": {"AAA": {}}}, "AAA") is None
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_market_wide_historical_research_context_contract(context, {"tickers": {"AAA": {}}})
    assert "market_wide_historical_research_context" not in context

    raw = _available()
    raw["as_of_session"] = "2026-08-21"
    result = market_wide_historical_research_context_contract(
        {"tickers": {"AAA": {"market_wide_historical_research_context": raw}}}, "AAA"
    )
    assert result["status"] == "malformed"
