import copy

from builders.build_ticker_context import (
    apply_bundle_current_financial_momentum_context_contract,
    apply_bundle_current_market_sector_leadership_context_contract,
    current_financial_momentum_context_contract,
)

# TEST_FIXTURE_ONLY -- shape verified against stock-core-private commit 61c8a1c
# (current_financial_momentum_context.py build_artifact()/_record_for_ticker(),
# export_ai_bundle.py build_current_financial_momentum_context_for_ticker_safe()),
# read via `git show` at that pinned revision, not the (concurrently writable) working tree.
_BLOCKED_OUTPUTS = {
    "strategy_eligibility": "NOT_MODIFIED", "research_priority": "NOT_MODIFIED",
    "entry_action": "NOT_MODIFIED", "fundamental_improvement_strategy": "NOT_ENABLED_BY_THIS_CONTEXT",
}
_AUTHORITY_BOUNDARY = {
    "is_actionable": False,
    "financial_momentum_is_not_cheapness": True, "financial_momentum_is_not_value": True,
    "financial_momentum_is_not_target_price": True, "financial_momentum_is_not_forecast": True,
    "financial_momentum_is_not_probability": True, "financial_momentum_is_not_strategy_eligibility": True,
    "financial_momentum_is_not_research_priority": True, "financial_momentum_is_not_entry_action": True,
    "financial_momentum_is_not_recommendation": True, "financial_momentum_is_not_sizing": True,
    "financial_momentum_is_not_price_momentum": True, "official_and_provider_remain_separated": True,
    "provider_not_upgraded_to_official": True, "adjacent_period_not_substituted_for_missing_comparable": True,
    "missing_is_not_zero": True, "industrial_metrics_not_forced_onto_bank_or_securities": True,
    "one_missing_metric_does_not_globally_block_ticker": True,
    "raw_as_traded": "NOT_PROMOTED", "pit": "BLOCKED", "backtesting": "BLOCKED",
    "frozen_sessions_not_regenerated": ["2026-08-21", "2026-08-24"],
}
_PROHIBITED_USES = [
    "cheapness", "VALUE", "target_price", "forecast", "probability",
    "strategy_eligibility", "research_priority", "entry_action",
    "recommendation", "sizing", "dcf", "earnings_surprise",
]


def _empty_component(component_id, *, status, reason, tier=None):
    return {
        "component_id": component_id, "status": status, "authority_tier": tier,
        "comparison_type": None, "current_value": None, "comparison_value": None,
        "change": None, "direction": None, "periods": [], "lineage": [],
        "blocked_reason": reason, "warnings": [],
    }


def _official_growth_component(component_id, *, value, direction, periods):
    return {
        "component_id": component_id, "status": "AVAILABLE", "authority_tier": "OFFICIAL_QUALIFIED",
        "comparison_type": "FY_YOY", "current_value": value, "comparison_value": None,
        "change": value, "direction": direction, "periods": periods, "lineage": ["evidence:doc1"],
        "blocked_reason": None, "warnings": [], "statement_scope": "consolidated", "currency": "VND",
        "method": "reported_yoy", "earnings_identity": "net_income" if component_id == "earnings_growth" else None,
    }


def _official_margin_component(*, current, previous, direction, periods):
    change = current - previous
    return {
        "component_id": "net_margin_change", "status": "AVAILABLE", "authority_tier": "OFFICIAL_QUALIFIED",
        "comparison_type": "FY_YOY", "current_value": current, "comparison_value": previous,
        "change": change, "direction": direction, "periods": periods, "lineage": ["evidence:doc1", "evidence:doc2"],
        "blocked_reason": None, "warnings": [], "statement_scope": "consolidated", "currency": "VND",
    }


def _price_context_available(price, contrast, reason):
    return {
        "status": "AVAILABLE", "price_momentum_20d": price, "current_session": True,
        "contrast": contrast, "reason": reason, "financial_momentum_is_not_price_momentum": True,
    }


def _price_context_unavailable():
    return {
        "status": "UNAVAILABLE", "price_momentum_20d": None, "current_session": False,
        "contrast": "PRICE_CONTEXT_UNAVAILABLE", "reason": "NO_CURRENT_SESSION_TECHNICAL_FEATURES",
        "financial_momentum_is_not_price_momentum": True,
    }


def _ticker_context_official_broad_improvement(ticker):
    components = {
        "revenue_growth": _official_growth_component("revenue_growth", value=0.12, direction="EXPANDING", periods=["2025", "2026"]),
        "earnings_growth": _official_growth_component("earnings_growth", value=0.15, direction="EXPANDING", periods=["2025", "2026"]),
        "net_margin_change": _official_margin_component(current=0.18, previous=0.15, direction="IMPROVING", periods=["2025", "2026"]),
        "operating_cash_flow": _official_growth_component("operating_cash_flow", value=0.08, direction="EXPANDING", periods=["2025", "2026"]),
    }
    return {
        "ticker": ticker, "as_of_financial_period": "2026", "entity_class": "corporate",
        "evidence_tier": "OFFICIAL_QUALIFIED", "coverage_status": "FULL",
        "financial_momentum_state": "BROAD_IMPROVEMENT",
        "state_rule": "REVENUE_UP_EARNINGS_UP_MARGIN_IMPROVING",
        "comparable_period_identities": [
            {"component_id": "revenue_growth", "comparison_type": "FY_YOY", "periods": ["2025", "2026"]},
        ],
        "components": components,
        "supporting_dimensions": ["revenue_growth", "earnings_growth", "operating_cash_flow"],
        "weakening_dimensions": [],
        "blockers": [], "warnings": [],
        "price_momentum_context": _price_context_available(-0.03, "FINANCIAL_IMPROVEMENT_WITHOUT_PRICE_MOMENTUM",
                                                            "COMPARABLE_FINANCIALS_IMPROVE_WHILE_CURRENT_SESSION_PRICE_MOMENTUM_IS_NOT_POSITIVE"),
        "allowed_uses": ["current_research_context"], "prohibited_uses": list(_PROHIBITED_USES),
        "does_not_enable_fundamental_improvement_strategy": True,
    }


def _artifact(ticker, ticker_context, *, status="available"):
    return {
        "ticker": ticker, "session": "2026-08-25", "status": status, "is_actionable": False,
        "source_artifact_identity": "current_financial_momentum_context:abc123",
        "research_mode": "CURRENT_RESEARCH_ONLY",
        "ticker_context": ticker_context,
        "coverage": {
            "universe_denominator": 500, "fundamental_cohort_present": 420,
            "tickers_with_comparable_dimension": 380,
            "coverage_status_distribution": {"FULL": 200, "PARTIAL": 180, "INSUFFICIENT": 100, "NOT_APPLICABLE": 20},
            "momentum_state_distribution": {"BROAD_IMPROVEMENT": 60},
            "evidence_tier_distribution": {"OFFICIAL_QUALIFIED": 13, "PROVIDER_RESEARCH": 407, "UNAVAILABLE": 80},
            "archetype_distribution": {"corporate": 450, "bank": 30, "securities": 20},
            "component_availability": {"revenue_growth": {"AVAILABLE": 300}},
            "unexplained_count": 0, "denominator_reconciles": True,
        },
        "blocked_outputs": copy.deepcopy(_BLOCKED_OUTPUTS),
        "authority_boundary": copy.deepcopy(_AUTHORITY_BOUNDARY),
    }


def test_official_qualified_broad_improvement_preserves_tiers_and_components_without_action():
    raw = _artifact("AAA", _ticker_context_official_broad_improvement("AAA"))
    bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
    assert current_financial_momentum_context_contract(bundle, "AAA") == raw
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_financial_momentum_context_contract(context, bundle)
    result = context["current_financial_momentum_context"]
    assert result["ticker_context"]["evidence_tier"] == "OFFICIAL_QUALIFIED"
    assert result["ticker_context"]["financial_momentum_state"] == "BROAD_IMPROVEMENT"
    assert result["ticker_context"]["components"]["revenue_growth"]["current_value"] == 0.12
    assert "entry_action" not in result
    assert "research_priority" not in result
    assert "target_price" not in result


def test_provider_research_tier_preserved_and_not_upgraded_to_official():
    ticker_context = _ticker_context_official_broad_improvement("AAA")
    ticker_context["evidence_tier"] = "PROVIDER_RESEARCH"
    ticker_context["financial_momentum_state"] = "EARNINGS_IMPROVING"
    ticker_context["warnings"] = ["provider_research_is_not_official_qualified"]
    for component in ticker_context["components"].values():
        component["authority_tier"] = "PROVIDER_RESEARCH"
        component["current_value"] = None  # provider tier never carries an absolute level, only change/direction
    raw = _artifact("AAA", ticker_context)
    bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
    result = current_financial_momentum_context_contract(bundle, "AAA")
    assert result["ticker_context"]["evidence_tier"] == "PROVIDER_RESEARCH"
    assert "provider_research_is_not_official_qualified" in result["ticker_context"]["warnings"]
    assert result["ticker_context"]["components"]["revenue_growth"]["current_value"] is None


def test_not_in_fundamental_cohort_remains_insufficient_not_zero():
    ticker_context = {
        "ticker": "AAA", "as_of_financial_period": None, "entity_class": "unknown",
        "evidence_tier": "UNAVAILABLE", "coverage_status": "INSUFFICIENT",
        "financial_momentum_state": "INSUFFICIENT_COMPARABLE_DATA", "state_rule": "NOT_IN_FUNDAMENTAL_COHORT",
        "comparable_period_identities": [],
        "components": {
            name: _empty_component(name, status="UNAVAILABLE", reason="NOT_IN_FUNDAMENTAL_COHORT")
            for name in ("revenue_growth", "earnings_growth", "net_margin_change", "operating_cash_flow")
        },
        "supporting_dimensions": [], "weakening_dimensions": [],
        "blockers": ["NOT_IN_FUNDAMENTAL_COHORT"],
        "warnings": ["absence_from_fundamental_cohort_is_not_zero_or_deterioration"],
        "price_momentum_context": _price_context_unavailable(),
        "allowed_uses": ["current_research_context"], "prohibited_uses": list(_PROHIBITED_USES),
        # Note: no does_not_enable_fundamental_improvement_strategy key in this real branch shape.
    }
    raw = _artifact("AAA", ticker_context, status="data_limited")
    bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
    result = current_financial_momentum_context_contract(bundle, "AAA")
    assert result["ticker_context"]["financial_momentum_state"] == "INSUFFICIENT_COMPARABLE_DATA"
    assert "absence_from_fundamental_cohort_is_not_zero_or_deterioration" in result["ticker_context"]["warnings"]
    assert "does_not_enable_fundamental_improvement_strategy" not in result["ticker_context"]


def test_bank_industrial_metrics_remain_not_applicable():
    ticker_context = _ticker_context_official_broad_improvement("VCB")
    ticker_context["ticker"] = "VCB"
    ticker_context["entity_class"] = "bank"
    ticker_context["financial_momentum_state"] = "EARNINGS_IMPROVING"
    ticker_context["state_rule"] = "PARENT_OR_APPLICABLE_EARNINGS_EXPANDING_INDUSTRIAL_METRICS_NOT_FORCED"
    ticker_context["components"]["revenue_growth"] = _empty_component(
        "revenue_growth", status="NOT_APPLICABLE", reason="INDUSTRIAL_METRIC_NOT_APPLICABLE_TO_ENTITY_CLASS", tier="OFFICIAL_QUALIFIED",
    )
    ticker_context["components"]["net_margin_change"] = _empty_component(
        "net_margin_change", status="NOT_APPLICABLE", reason="INDUSTRIAL_METRIC_NOT_APPLICABLE_TO_ENTITY_CLASS", tier="OFFICIAL_QUALIFIED",
    )
    ticker_context["components"]["operating_cash_flow"] = _empty_component(
        "operating_cash_flow", status="NOT_APPLICABLE", reason="INDUSTRIAL_METRIC_NOT_APPLICABLE_TO_ENTITY_CLASS", tier="OFFICIAL_QUALIFIED",
    )
    ticker_context["supporting_dimensions"] = ["earnings_growth"]
    raw = _artifact("VCB", ticker_context)
    bundle = {"tickers": {"VCB": {"current_financial_momentum_context": raw}}}
    result = current_financial_momentum_context_contract(bundle, "VCB")
    assert result["ticker_context"]["components"]["revenue_growth"]["status"] == "NOT_APPLICABLE"
    assert result["ticker_context"]["components"]["net_margin_change"]["status"] == "NOT_APPLICABLE"


def test_loss_making_state_preserved():
    ticker_context = _ticker_context_official_broad_improvement("AAA")
    ticker_context["financial_momentum_state"] = "LOSS_MAKING_OR_STRESSED"
    ticker_context["state_rule"] = "NEGATIVE_EARNINGS_OR_NON_POSITIVE_GROWTH_BASE"
    ticker_context["components"]["earnings_growth"] = _empty_component(
        "earnings_growth", status="BLOCKED", reason="GROWTH_BASE_NON_POSITIVE", tier="OFFICIAL_QUALIFIED",
    )
    ticker_context["blockers"] = ["GROWTH_BASE_NON_POSITIVE"]
    ticker_context["supporting_dimensions"] = []
    ticker_context["weakening_dimensions"] = ["revenue_growth"]
    raw = _artifact("AAA", ticker_context)
    bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
    result = current_financial_momentum_context_contract(bundle, "AAA")
    assert result["ticker_context"]["financial_momentum_state"] == "LOSS_MAKING_OR_STRESSED"
    assert "GROWTH_BASE_NON_POSITIVE" in result["ticker_context"]["blockers"]


def test_price_momentum_contrast_variants_preserved():
    for contrast in (
        "ALIGNED_NOT_DISTINGUISHED", "FINANCIAL_IMPROVEMENT_WITHOUT_PRICE_MOMENTUM",
        "PRICE_MOMENTUM_WITHOUT_FINANCIAL_IMPROVEMENT", "NO_CLEAR_OPERATIONAL_PRICE_CONTRAST",
    ):
        ticker_context = _ticker_context_official_broad_improvement("AAA")
        ticker_context["price_momentum_context"] = _price_context_available(0.01, contrast, "some_reason")
        raw = _artifact("AAA", ticker_context)
        bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
        result = current_financial_momentum_context_contract(bundle, "AAA")
        assert result["ticker_context"]["price_momentum_context"]["contrast"] == contrast


def test_strategy_or_entry_action_mutation_fails_closed():
    raw = _artifact("AAA", _ticker_context_official_broad_improvement("AAA"))
    raw["blocked_outputs"]["research_priority"] = "MODIFIED"
    bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
    assert current_financial_momentum_context_contract(bundle, "AAA")["status"] == "malformed"

    raw = _artifact("AAA", _ticker_context_official_broad_improvement("AAA"))
    raw["blocked_outputs"]["fundamental_improvement_strategy"] = "ENABLED"
    bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
    assert current_financial_momentum_context_contract(bundle, "AAA")["status"] == "malformed"

    raw = _artifact("AAA", _ticker_context_official_broad_improvement("AAA"))
    raw["authority_boundary"]["provider_not_upgraded_to_official"] = False
    bundle = {"tickers": {"AAA": {"current_financial_momentum_context": raw}}}
    assert current_financial_momentum_context_contract(bundle, "AAA")["status"] == "malformed"


def test_absent_optional_layer_fails_closed_without_invalidating_context():
    assert current_financial_momentum_context_contract({"tickers": {"AAA": {}}}, "AAA") is None
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_financial_momentum_context_contract(context, {"tickers": {"AAA": {}}})
    assert "current_financial_momentum_context" not in context


def test_can_coexist_with_sector_leadership_context_without_joint_signal():
    financial = _artifact("AAA", _ticker_context_official_broad_improvement("AAA"))
    sector = {
        "ticker": "AAA", "session": "2026-08-25", "status": "available", "is_actionable": False,
        "source_artifact_identity": "current_market_sector_leadership_context:abc123",
        "research_mode": "CURRENT_SESSION_DESCRIPTIVE_MARKET_AND_SECTOR_CONTEXT",
        "market": {
            "session": "2026-08-25", "official_universe_count": 500, "exact_session_observed_count": 480,
            "missing_current_session_count": 20, "current_breadth_state": "MIXED_BREADTH", "warnings": [],
        },
        "ticker_context": {
            "ticker": "AAA", "status": "AVAILABLE",
            "market_relative_momentum": {"status": "AVAILABLE"}, "sector_relative_momentum": {"status": "AVAILABLE"},
            "sector_leadership_context": {"status": "AVAILABLE", "leadership_state": "LEADING"},
            "breadth_support_state": "MARKET_AND_GROUP_BREADTH_SUPPORT", "coverage_limitations": [],
        },
        "coverage": {
            "official_universe_count": 500, "exact_session_observed_count": 480, "missing_current_session_count": 20,
            "unknown_sector_identity_count": 5, "ticker_sector_context_available_count": 420, "ticker_data_limited_count": 40,
        },
        "blocked_outputs": {
            "global_or_ticker_ranking_score": "NOT_EMITTED", "strategy_eligibility": "NOT_MODIFIED",
            "research_priority": "NOT_MODIFIED", "entry_action": "NOT_MODIFIED", "daily_decision_queue": "NOT_MODIFIED",
            "value_valuation_target_price": "NOT_EMITTED", "sizing_execution": "NOT_EMITTED", "raw_as_traded_pit_backtest": "NOT_EMITTED",
        },
        "authority_boundary": {
            "is_actionable": False, "current_research_only": True,
            "current_cross_sectional_relative_strength_not_historical_pit": True,
            "missing_current_session_bar_is_not_zero": True, "no_opaque_global_score": True,
            "no_strategy_priority_entry_or_sizing_mutation": True,
        },
    }
    bundle = {"tickers": {"AAA": {
        "current_financial_momentum_context": financial,
        "current_market_sector_leadership_context": sector,
    }}}
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_financial_momentum_context_contract(context, bundle)
    apply_bundle_current_market_sector_leadership_context_contract(context, bundle)
    assert context["current_financial_momentum_context"] == financial
    assert context["current_market_sector_leadership_context"] == sector
    assert "entry_action" not in context
    assert "research_priority" not in context
    assert "combined_score" not in context
