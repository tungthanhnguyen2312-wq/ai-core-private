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


def test_invalid_claim_or_human_review_boundary_fails_closed():
    raw = _raw(); raw["thesis_counter_thesis"]["thesis"][0]["type"] = "BUY"
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"
    raw = _raw(); raw["current_decision_state"]["requires_human_review"] = False
    assert current_daily_decision_research_contract({"tickers": {"ABB": {"current_daily_decision_research": raw}}}, "ABB")["status"] == "malformed"
