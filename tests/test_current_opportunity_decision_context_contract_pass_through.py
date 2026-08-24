import copy
import json
from pathlib import Path

from builders.build_ticker_context import (
    apply_bundle_current_opportunity_decision_context_contract,
    current_opportunity_decision_context_contract,
)


ARTIFACT = (Path(__file__).resolve().parents[2] / "stock-core-private" / "operations-review"
            / "daily-opportunity-decision-queue-v1-20260824" / "daily_opportunity_decision_queue_artifact.json")


def _queue():
    return json.loads(ARTIFACT.read_text(encoding="utf-8"))


def _context(ticker: str, queue: dict | None = None):
    context = {"ticker": ticker, "provenance": []}
    apply_bundle_current_opportunity_decision_context_contract(
        context, {"daily_opportunity_decision_queue": _queue() if queue is None else queue},
    )
    return context


def test_absent_queue_and_absent_ticker_remain_backward_compatible():
    context = {"ticker": "BKC", "provenance": []}
    apply_bundle_current_opportunity_decision_context_contract(context, None)
    assert "current_opportunity_decision_context" not in context
    queue = _queue(); queue["records"].pop("BKC")
    assert "current_opportunity_decision_context" not in _context("BKC", queue)


def test_priority_now_avoid_is_preserved_not_rewritten_as_an_entry_signal():
    result = _context("BKC")["current_opportunity_decision_context"]
    assert result["ticker_record"]["research_priority_tier"] == "PRIORITY_NOW"
    assert result["ticker_record"]["entry_action"] == "AVOID"
    assert result["ticker_record"]["entry_relevant"] is False
    assert result["ticker_record"]["is_actionable"] is False


def test_full_priority_now_and_legacy_human_review_queue_are_separate():
    queue = _queue()
    result = _context("BKC", queue)["current_opportunity_decision_context"]
    assert result["full_priority_now"] == queue["full_priority_now"]
    assert result["legacy_human_review_queue"] == queue["primary_review_candidates"]
    assert len(result["full_priority_now"]) == 190
    assert result["legacy_human_review_queue"]["count"] == 47
    assert result["legacy_human_review_queue"]["policy_kind"] == "EXISTING_EVIDENCE_GATED_ELIGIBILITY_NOT_A_FIXED_CAP"


def test_multi_strategy_lane_membership_is_preserved_without_a_best_strategy_choice():
    queue = _queue()
    result = _context("ACE", queue)["current_opportunity_decision_context"]
    assert result["ticker_record"]["eligible_strategies"] == ["TREND_MOMENTUM", "EVENT_DRIVEN"]
    assert result["ticker_record"]["lane_specific_priority"] == {
        "EVENT_DRIVEN": "PRIORITY_NOW", "TREND_MOMENTUM": "SETUP_WATCH",
    }
    assert result["multi_strategy"] == queue["multi_strategy"]
    assert result["lane_queues"] == queue["lane_queues"]


def test_context_is_deterministic_deep_copy_pass_through():
    queue = _queue()
    bundle = {"daily_opportunity_decision_queue": queue}
    first = current_opportunity_decision_context_contract(bundle, "BKC")
    second = current_opportunity_decision_context_contract(bundle, "BKC")
    assert first == second
    first["ticker_record"]["entry_action"] = "BUY_ON_CONFIRMATION"
    assert queue["records"]["BKC"]["entry_action"] == "AVOID"


def test_warnings_and_authority_boundary_pass_through_without_widening():
    queue = _queue()
    result = _context("BKC", queue)["current_opportunity_decision_context"]
    assert result["ticker_record"]["invalidation_or_context_warnings"] == queue["records"]["BKC"]["invalidation_or_context_warnings"]
    assert result["ticker_record"]["authority_note"] == queue["records"]["BKC"]["authority_note"]
    assert result["authority_boundary"] == queue["authority_boundary"]
    assert result["authority_boundary"]["research_priority_is_not_trade_readiness"] is True
    assert result["authority_boundary"]["priority_now_is_not_sizing_ready"] is True


def test_malformed_queue_fails_closed_without_creating_an_actionable_signal():
    queue = copy.deepcopy(_queue())
    queue["authority_boundary"]["no_global_score"] = False
    result = _context("BKC", queue)["current_opportunity_decision_context"]
    assert result == {
        "status": "malformed",
        "is_actionable": False,
        "reason_codes": ["daily_opportunity_decision_queue_malformed"],
    }
