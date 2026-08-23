import copy
import json
from pathlib import Path

from builders.build_ticker_context import (
    apply_bundle_current_daily_decision_research_contract,
    current_daily_decision_research_contract,
)


ARTIFACT = (Path(__file__).resolve().parents[2] / "stock-core-private" / "operations-review"
            / "current-daily-decision-research-product-v2-20260824" / "current_daily_decision_research_product_artifact.json")


def _raw():
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    raw = copy.deepcopy(artifact["detailed_research_cards"]["ABB"])
    raw.update({"source_artifact_identity": artifact["artifact_identity"], "source_session": artifact["session"], "market_brief": artifact["market_brief"], "authority_boundary": artifact["authority_boundary"], "is_actionable": False})
    return raw


def test_daily_card_passes_through_with_tactical_and_unknown_probability_boundary():
    raw = _raw(); bundle = {"tickers": {"ABB": {"current_daily_decision_research": raw}}}
    assert current_daily_decision_research_contract(bundle, "ABB") == raw
    context = {"ticker": "ABB", "provenance": []}
    apply_bundle_current_daily_decision_research_contract(context, bundle)
    assert context["current_daily_decision_research"]["current_decision_state"] == raw["current_decision_state"]
    assert context["current_daily_decision_research"]["scenario"]["probability_status"] == "UNKNOWN_UNCALIBRATED"


def test_corporate_context_must_preserve_non_actionable_verified_lists():
    raw = _raw(); raw["corporate_intelligence_context"] = {"status": "CURRENT_INTELLIGENCE_AVAILABLE", "confirmed": [], "planned_or_pending": [], "is_actionable": False}
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["corporate_intelligence_context"]["status"] == "CURRENT_INTELLIGENCE_AVAILABLE"
    raw["corporate_intelligence_context"]["is_actionable"] = True
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"


def test_strategy_fit_requires_declared_non_actionable_strategy_statuses():
    raw = _raw(); raw["strategy_fit"] = {"status": "SINGLE_STRATEGY_ELIGIBLE", "eligible_strategy_ids": ["BREAKOUT"], "strategies": [{"strategy_id": "BREAKOUT", "status": "ELIGIBLE"}], "is_actionable": False}
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["strategy_fit"]["strategies"][0]["strategy_id"] == "BREAKOUT"
    raw["strategy_fit"]["strategies"][0]["status"] = "BUY"
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"


def test_optional_portfolio_envelope_is_non_actionable_and_fail_closed():
    raw = _raw(); raw["portfolio_risk"] = {"contract_version": "current_portfolio_risk_envelope/v1", "portfolio_id": "DEMONSTRATION_ONLY", "is_actionable": False, "position_sizing_status": "BLOCKED", "blocked_risk_dimensions": {"VaR": {"status": "BLOCKED"}}}
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["portfolio_risk"]["portfolio_id"] == "DEMONSTRATION_ONLY"
    raw["portfolio_risk"]["position_sizing_status"] = "READY"
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"


def test_optional_macro_context_is_descriptive_and_fail_closed():
    raw = _raw(); raw["macro_context"] = {"status": "UNAVAILABLE", "reason": "NOT_KNOWN_BY_SESSION", "is_actionable": False}
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["macro_context"]["status"] == "UNAVAILABLE"
    raw["macro_context"]["is_actionable"] = True
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"


def test_invalid_claim_or_human_review_boundary_fails_closed():
    raw = _raw(); raw["thesis_counter_thesis"]["thesis"][0]["type"] = "BUY"
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"
    raw = _raw(); raw["current_decision_state"]["requires_human_review"] = False
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"
    raw = _raw(); raw["market_brief"]["source_market_session"] = "2026-08-20"
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"
