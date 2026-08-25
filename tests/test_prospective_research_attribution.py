from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.prospective_research_attribution import (
    build_attribution_record,
    summarize_attribution_cohort,
)


def snapshot(**changes):
    value = {
        "schema_version": "1.0.0",
        "ticker": "HPG",
        "research_session": "2026-08-18",
        "snapshot_identity": "prospective_research_snapshot:hpg-t",
        "source_artifact_identity": "daily_research_session_operation:hpg-t",
        "research_state": {
            "deterministic_decision_state": {"research_priority": "MONITOR", "entry_action": "WAIT"},
            "packet_scenarios": ["BEAR", "BASE", "BULL"],
            "research_scenarios": ["CONSERVATIVE", "BASE", "SPECULATIVE"],
            "known_risks": ["evidence_limited"],
        },
        "evidence_provenance": [{"identity": "evidence:hpg-t"}],
        "authority_limitations": ["NOT_PIT", "NOT_RAW_AS_TRADED"],
        "price_observation": {"observed_fields": {"close": 20000}, "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True}},
    }
    value.update(changes)
    return value


def outcome(**changes):
    value = {
        "schema_version": "1.0.0",
        "ticker": "HPG",
        "observation_session": "2026-08-19",
        "observation_identity": "exact_session_observation:hpg-t1",
        "source_artifact_identity": "exact_session_scaleout:hpg-t1",
        "research_snapshot_identity": "prospective_research_snapshot:hpg-t",
        "research_source_artifact_identity": "daily_research_session_operation:hpg-t",
        "observed_fields": {"close": 21000, "volume": 100},
        "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True, "pit_authority": False},
        "evidence_provenance": [{"identity": "evidence:hpg-t1"}],
        "knowledge_availability": {"known_at": "2026-08-19T15:00:00Z"},
    }
    value.update(changes)
    return value


def test_valid_later_observation_preserves_separate_temporal_states_and_calculates_only_observed_metric():
    original = snapshot()
    later = outcome()
    record = build_attribution_record(original, later)
    assert record["attribution_status"] == "ATTRIBUTABLE"
    assert record["observed_outcome"]["simple_price_return"] == pytest.approx(0.05)
    assert record["research_at_t"]["research_state"] == original["research_state"]
    assert record["what_was_observed_later"]["observed_fields"] == later["observed_fields"]
    assert record["research_at_t"] is not original
    assert "probability" not in record["observed_outcome"]
    assert "expected_return" not in record["observed_outcome"]
    assert "recommendation" not in record["observed_outcome"]
    assert "NOT_RAW_AS_TRADED" in record["research_at_t"]["authority_limitations"]


def test_pending_is_not_research_failure_and_is_deterministic():
    first = build_attribution_record(snapshot())
    assert first == build_attribution_record(snapshot())
    assert first["attribution_status"] == "OUTCOME_PENDING"


@pytest.mark.parametrize(("mutate", "status", "reason"), [
    (lambda value: value.update(ticker="VCB"), "IDENTITY_MISMATCH", "ticker_identity_mismatch"),
    (lambda value: value.update(observation_session="2026-08-18"), "TEMPORAL_VIOLATION", "outcome_session_not_strictly_later"),
    (lambda value: value.update(research_snapshot_identity="prospective_research_snapshot:wrong"), "IDENTITY_MISMATCH", "research_snapshot_identity_mismatch"),
    (lambda value: value.update(research_source_artifact_identity="daily_research_session_operation:wrong"), "IDENTITY_MISMATCH", "research_source_artifact_identity_mismatch"),
])
def test_identity_and_temporal_violations_fail_closed(mutate, status, reason):
    later = outcome()
    mutate(later)
    record = build_attribution_record(snapshot(), later)
    assert record["attribution_status"] == status
    assert reason in record["reason_codes"]


def test_malformed_research_and_later_observation_fail_closed():
    assert build_attribution_record(snapshot(evidence_provenance=[]), outcome())["attribution_status"] == "MALFORMED"
    assert build_attribution_record(snapshot(), outcome(evidence_provenance=[]))["attribution_status"] == "MALFORMED"


def test_incompatible_or_unqualified_basis_blocks_only_the_price_comparison():
    incompatible = build_attribution_record(snapshot(), outcome(basis={"price_basis": "RAW_AS_TRADED", "qualified": True, "pit_authority": False}))
    assert incompatible["attribution_status"] == "UNSUPPORTED_COMPARISON"
    assert incompatible["observed_outcome"]["metric_status"] == "PRICE_COMPARISON_UNSUPPORTED"
    unqualified = build_attribution_record(snapshot(), outcome(basis={"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": False}))
    assert unqualified["attribution_status"] == "INPUT_UNQUALIFIED"
    pit_claim = build_attribution_record(snapshot(), outcome(basis={"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True, "pit_authority": True}))
    assert pit_claim["attribution_status"] == "INPUT_UNQUALIFIED"


def test_optional_research_components_are_not_required():
    minimal = snapshot()
    del minimal["price_observation"]
    minimal["research_state"] = {"deterministic_decision_state": {"research_priority": "MONITOR"}}
    record = build_attribution_record(minimal, outcome())
    assert record["attribution_status"] == "ATTRIBUTABLE"
    assert record["observed_outcome"]["metric_status"] == "NO_FORMAL_PRICE_COMPARISON_REQUESTED"


def test_later_outcome_never_mutates_or_rewrites_the_original_decision():
    original = snapshot()
    expected = copy.deepcopy(original)
    record = build_attribution_record(original, outcome())
    record["research_at_t"]["research_state"]["deterministic_decision_state"]["entry_action"] = "MUTATED"
    assert original == expected


def test_transport_duplicates_are_deduplicated_without_collapsing_distinct_scenario_families():
    direct = build_attribution_record(snapshot(), outcome())
    packet_snapshot = snapshot(transport="PACKET_SHADOW")
    packet = build_attribution_record(packet_snapshot, outcome())
    assert direct["attribution_identity"] != packet["attribution_identity"]
    assert direct["temporal_link_identity"] == packet["temporal_link_identity"]
    assert direct["research_at_t"]["research_state"]["packet_scenarios"] == ["BEAR", "BASE", "BULL"]
    assert direct["research_at_t"]["research_state"]["research_scenarios"] == ["CONSERVATIVE", "BASE", "SPECULATIVE"]
    summary = summarize_attribution_cohort([direct, packet])
    assert summary["snapshots_considered"] == 1
    assert summary["duplicate_transport_records_excluded"] == 1


def test_summary_is_transparent_and_has_no_scoring_or_unexplained_residual():
    valid = build_attribution_record(snapshot(), outcome())
    pending = build_attribution_record(snapshot(ticker="VCB", snapshot_identity="prospective_research_snapshot:vcb-t", source_artifact_identity="daily_research_session_operation:vcb-t"))
    broken = build_attribution_record(snapshot(ticker="SSI", snapshot_identity="prospective_research_snapshot:ssi-t", source_artifact_identity="daily_research_session_operation:ssi-t"), outcome(ticker="SSI", research_snapshot_identity="prospective_research_snapshot:ssi-t", research_source_artifact_identity="daily_research_session_operation:ssi-t", observation_session="2026-08-18"))
    summary = summarize_attribution_cohort([valid, pending, broken])
    assert (summary["snapshots_considered"], summary["later_observations"], summary["pending"], summary["blocked"]) == (3, 1, 1, 1)
    assert summary["temporal_integrity_violations"] == 1
    assert summary["unexplained_residual"] == 0
    assert "win" not in str(summary).lower()
    assert not any("strategy" in key for key in summary if key != "authority_boundary")
