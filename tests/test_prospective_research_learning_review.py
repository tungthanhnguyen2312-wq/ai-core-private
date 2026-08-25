from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.prospective_research_attribution import build_attribution_record
from builders.prospective_research_learning_review import build_learning_review, summarize_learning_reviews
from builders.retrospective_learning_synthesis_response import validate_retrospective_learning_synthesis_output


def snapshot(**changes):
    value = {
        "ticker": "HPG", "research_session": "2026-08-20",
        "snapshot_identity": "prospective_research_snapshot:hpg-t",
        "source_artifact_identity": "daily_research_product:hpg-t",
        "research_state": {
            "deterministic_decision_state": {"research_priority": "MONITOR", "entry_action": "WAIT"},
            "packet_scenarios": ["BEAR", "BASE", "BULL"],
            "research_scenarios": ["CONSERVATIVE", "BASE", "SPECULATIVE"],
            "risk_register_status": "NO_MATERIAL_RISK_ESTABLISHED",
            "event_state": {"record_date": "2026-08-18", "execution_state": "PLANNED_NOT_EXECUTED"},
        },
        "evidence_provenance": [{"identity": "evidence:hpg-t"}],
        "authority_limitations": ["NOT_PIT", "NOT_RAW_AS_TRADED"],
    }
    value.update(changes)
    return value


def outcome(**changes):
    value = {
        "ticker": "HPG", "observation_session": "2026-08-21",
        "observation_identity": "exact_session_observation:hpg-t1",
        "source_artifact_identity": "exact_session_snapshot:hpg-t1",
        "research_snapshot_identity": "prospective_research_snapshot:hpg-t",
        "research_source_artifact_identity": "daily_research_product:hpg-t",
        "observed_fields": {"close": 21000},
        "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": False, "pit_authority": False},
        "evidence_provenance": [{"identity": "evidence:hpg-t1"}],
        "knowledge_availability": {"known_at": "2026-08-21T15:00:00Z"},
    }
    value.update(changes)
    return value


def attributable():
    return build_attribution_record(snapshot(), outcome())


def ai_response(review):
    known = review["provenance"]["known_at_t_references"][0]
    later = review["provenance"]["new_after_t_references"][0]
    item = lambda statement, refs: {"statement": statement, "evidence_references": refs}
    return {
        "ticker": "HPG",
        "original_research_summary": [item("The original deterministic state is retained.", [known])],
        "later_observation_summary": [item("A later governed observation is retained.", [later])],
        "evidence_consistent_with_original_thesis": [],
        "evidence_against_original_thesis": [],
        "still_unresolved": [item("The thesis remains interpretive.", [known, later])],
        "learning_takeaways": [item("Keep the two temporal evidence sets separate.", [known, later])],
        "authority_limitations": [item("The retained basis has no PIT authority.", [known])],
    }


def test_attributable_record_builds_reviewable_envelope_without_rejoining_inputs():
    record = attributable()
    review = build_learning_review(record)
    assert review["reviewability"]["status"] == "REVIEWABLE"
    assert review["original_research_state"] == record["research_at_t"]
    assert review["later_observation"] == record["what_was_observed_later"]
    assert review["qualified_observed_comparison"]["status"] == "NOT_COMPARABLE"
    assert review == build_learning_review(record)


@pytest.mark.parametrize(("record", "expected"), [
    (lambda: build_attribution_record(snapshot()), "OUTCOME_PENDING"),
    (lambda: build_attribution_record(snapshot(price_observation={"observed_fields": {"close": 20000}, "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True}}), outcome(basis={"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": False})), "UNQUALIFIED"),
    (lambda: {"bad": "attribution"}, "MALFORMED"),
])
def test_pending_unqualified_and_malformed_attribution_remain_explicit(record, expected):
    assert build_learning_review(record())["reviewability"]["status"] == expected


def test_original_state_is_immutable_and_later_evidence_cannot_enter_known_at_t():
    original = attributable()
    expected = copy.deepcopy(original["research_at_t"])
    review = build_learning_review(original)
    review["original_research_state"]["research_state"]["deterministic_decision_state"]["entry_action"] = "MUTATED"
    assert original["research_at_t"] == expected
    known = set(review["provenance"]["known_at_t_references"])
    later = set(review["provenance"]["new_after_t_references"])
    assert known.isdisjoint(later)
    assert original["what_was_observed_later"]["observation_identity"] not in known


def test_no_formal_metric_is_not_invented_but_explicit_qualified_metric_passes_through_unchanged():
    no_metric = build_learning_review(attributable())
    assert no_metric["qualified_observed_comparison"]["reason_codes"] == ["attribution_did_not_emit_formal_price_metric"]
    qualified_snapshot = snapshot(price_observation={"observed_fields": {"close": 20000}, "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True}})
    qualified_outcome = outcome(basis={"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True, "pit_authority": False})
    metric = build_attribution_record(qualified_snapshot, qualified_outcome)["observed_outcome"]
    review = build_learning_review(build_attribution_record(qualified_snapshot, qualified_outcome))
    assert review["qualified_observed_comparison"]["observed_metric"] == metric


def test_scenarios_decision_risk_and_event_semantics_are_quoted_not_rewritten():
    review = build_learning_review(attributable())
    state = review["original_research_state"]["research_state"]
    assert state["packet_scenarios"] == ["BEAR", "BASE", "BULL"]
    assert state["research_scenarios"] == ["CONSERVATIVE", "BASE", "SPECULATIVE"]
    assert state["deterministic_decision_state"]["entry_action"] == "WAIT"
    assert state["risk_register_status"] == "NO_MATERIAL_RISK_ESTABLISHED"
    assert state["event_state"] == {"record_date": "2026-08-18", "execution_state": "PLANNED_NOT_EXECUTED"}


def test_duplicate_packet_transport_is_not_independent_review_confirmation():
    direct = build_learning_review(attributable())
    packet = build_learning_review(build_attribution_record(snapshot(transport="PACKET_SHADOW"), outcome()))
    summary = summarize_learning_reviews([direct, packet])
    assert summary["total_attribution_records"] == 1
    assert summary["duplicate_transport_records_excluded"] == 1


def test_cohort_summary_has_transparent_counts_without_scores_or_wins():
    reviewable = build_learning_review(attributable())
    pending = build_learning_review(build_attribution_record(snapshot(ticker="VCB", snapshot_identity="prospective_research_snapshot:vcb-t", source_artifact_identity="daily_research_product:vcb-t")))
    temporal = build_learning_review(build_attribution_record(snapshot(ticker="SSI", snapshot_identity="prospective_research_snapshot:ssi-t", source_artifact_identity="daily_research_product:ssi-t"), outcome(ticker="SSI", research_snapshot_identity="prospective_research_snapshot:ssi-t", research_source_artifact_identity="daily_research_product:ssi-t", observation_session="2026-08-20")))
    summary = summarize_learning_reviews([reviewable, pending, temporal])
    assert (summary["total_attribution_records"], summary["reviewable"], summary["pending"], summary["blocked_or_unqualified"]) == (3, 1, 1, 1)
    assert summary["temporal_integrity_failures"] == 1
    assert summary["unexplained_residual"] == 0
    assert summary["comparison_not_comparable"] == 3
    assert not any("win" in key or "score" in key for key in summary)


def test_ai_boundary_accepts_evidence_bound_explanation_and_rejects_unknown_or_prohibited_claims():
    review = build_learning_review(attributable())
    response = ai_response(review)
    assert validate_retrospective_learning_synthesis_output(response, review)["status"] == "accepted"
    unknown = copy.deepcopy(response)
    unknown["original_research_summary"][0]["evidence_references"] = ["unknown:evidence"]
    assert "unknown_evidence_reference:unknown:evidence" in validate_retrospective_learning_synthesis_output(unknown, review)["reasons"]
    prohibited = copy.deepcopy(response)
    prohibited["learning_takeaways"][0]["statement"] = "This was a correct call with a 70% probability."
    assert "prohibited_retrospective_claim" in validate_retrospective_learning_synthesis_output(prohibited, review)["reasons"]


def test_ai_boundary_rejects_later_evidence_inside_original_research_summary():
    review = build_learning_review(attributable())
    response = ai_response(review)
    response["original_research_summary"][0]["evidence_references"] = [review["provenance"]["new_after_t_references"][0]]
    assert "later_evidence_in_original_research_summary" in validate_retrospective_learning_synthesis_output(response, review)["reasons"]


def test_review_surface_is_not_connected_to_current_research_builder():
    current_builder = (ROOT / "builders" / "build_ticker_context.py").read_text(encoding="utf-8")
    assert "prospective_research_learning_review" not in current_builder
    assert "retrospective_learning_synthesis_response" not in current_builder
