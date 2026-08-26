from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.prospective_learning_longitudinal_registry import (
    empty_registry,
    query_registry,
    render_registry_inventory,
    register_review_product,
    summarize_registry,
    write_registry,
)
from builders.prospective_learning_review_product import build_learning_review_product
from builders.prospective_research_attribution import build_attribution_record
from builders.prospective_research_learning_review import build_learning_review


def snapshot(ticker="HPG", snapshot_id="prospective_research_snapshot:hpg-t", session="2026-08-20"):
    return {"ticker": ticker, "research_session": session, "snapshot_identity": snapshot_id, "source_artifact_identity": f"daily_research_product:{ticker}-{session}", "research_state": {"deterministic_decision_state": {"entry_action": "WAIT"}}, "evidence_provenance": [{"identity": f"evidence:{ticker}-{session}"}], "authority_limitations": ["NOT_PIT", "NOT_RAW_AS_TRADED"]}


def outcome(source, ticker="HPG", session="2026-08-21", observation="exact_session_observation:hpg-t1"):
    return {"ticker": ticker, "observation_session": session, "observation_identity": observation, "source_artifact_identity": f"exact_session_snapshot:{ticker}-{session}", "research_snapshot_identity": source["snapshot_identity"], "research_source_artifact_identity": source["source_artifact_identity"], "observed_fields": {"close": 21000}, "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": False, "pit_authority": False}, "evidence_provenance": [{"identity": f"evidence:{ticker}-{session}"}]}


def product_for(*reviews):
    return build_learning_review_product(list(reviews))


def observed_review(ticker="HPG", snapshot_id="prospective_research_snapshot:hpg-t", observation="exact_session_observation:hpg-t1"):
    source = snapshot(ticker, snapshot_id)
    return build_learning_review(build_attribution_record(source, outcome(source, ticker, observation=observation)))


def pending_review(ticker="HPG", snapshot_id="prospective_research_snapshot:hpg-t"):
    return build_learning_review(build_attribution_record(snapshot(ticker, snapshot_id)))


def register(registry, product):
    return register_review_product(registry, product, retained_product_reference="operations-review/test-product.json")


def test_first_registration_and_exact_duplicate_are_idempotent():
    product = product_for(observed_review())
    first = register(empty_registry(), product)
    assert first["status"] == "REGISTERED"
    assert len(first["registry"]["registrations"]) == 1
    repeated = register(first["registry"], product)
    assert repeated["status"] == "DUPLICATE_IDENTICAL"
    assert repeated["registry"] == first["registry"]


def test_conflicting_immutable_duplicate_fails_closed_without_corrupting_registry():
    first = register(empty_registry(), product_for(observed_review(), observed_review("VCB", "prospective_research_snapshot:vcb-t", "exact_session_observation:vcb-t1")))
    conflicting = product_for(observed_review())
    conflicting["records"][0]["review_identity"] = "prospective_research_learning_review:conflict"
    rejected = register(first["registry"], conflicting)
    assert rejected["status"] == "CONFLICT_FAIL_CLOSED"
    assert rejected["registry"] == first["registry"]


def test_two_tickers_and_same_ticker_two_research_snapshots_are_separate_cases():
    hpg = observed_review()
    vcb = observed_review("VCB", "prospective_research_snapshot:vcb-t", "exact_session_observation:vcb-t1")
    hpg_second = observed_review("HPG", "prospective_research_snapshot:hpg-t2", "exact_session_observation:hpg-t2")
    result = register(empty_registry(), product_for(hpg, vcb, hpg_second))
    summary = summarize_registry(result["registry"])
    assert (summary["total_registered_learning_cases"], summary["unique_tickers"], summary["unique_research_snapshots"]) == (3, 2, 3)


def test_pending_entry_remains_immutable_when_later_observed_case_links_to_it():
    pending_product = product_for(pending_review())
    pending = register(empty_registry(), pending_product)
    old = copy.deepcopy(pending["registry"]["registrations"][0])
    later = register(pending["registry"], product_for(observed_review()))
    assert later["status"] == "REGISTERED"
    assert len(later["registry"]["registrations"]) == 2
    assert old in later["registry"]["registrations"]
    observed = next(row for row in later["registry"]["registrations"] if row["later_observation"]["outcome_observation_identity"] is not None)
    assert observed["lineage"]["prior_pending_registration_identities"] == [old["registration_identity"]]


@pytest.mark.parametrize("filter_name", ["ticker", "research_session", "outcome_session", "research_snapshot_identity", "attribution_identity", "learning_review_identity", "review_product_identity", "reviewability_status"])
def test_exact_match_query_surface(filter_name):
    result = register(empty_registry(), product_for(observed_review()))
    row = result["registry"]["registrations"][0]
    values = {"ticker": row["research_origin"]["ticker"], "research_session": row["research_origin"]["research_session"], "outcome_session": row["later_observation"]["outcome_session"], "research_snapshot_identity": row["research_origin"]["research_snapshot_identity"], "attribution_identity": row["review"]["attribution_identity"], "learning_review_identity": row["review"]["learning_review_identity"], "review_product_identity": row["registered_product_identity"], "reviewability_status": row["review"]["reviewability_status"]}
    assert query_registry(result["registry"], **{filter_name: values[filter_name]}) == [row]


def test_packet_direct_transport_product_does_not_double_count_and_order_is_deterministic():
    direct = observed_review()
    packet_source = snapshot(); packet_source["transport"] = "PACKET_SHADOW"
    packet = build_learning_review(build_attribution_record(packet_source, outcome(packet_source)))
    product = product_for(direct, packet)
    assert len(product["records"]) == 1
    independent = product_for(observed_review(), observed_review("VCB", "prospective_research_snapshot:vcb-t", "exact_session_observation:vcb-t1"))
    forward = register(empty_registry(), independent)["registry"]
    reversed_product = copy.deepcopy(independent); reversed_product["records"].reverse()
    reverse = register(empty_registry(), reversed_product)["registry"]
    assert forward == reverse


def test_malformed_product_and_missing_provenance_are_rejected():
    malformed = register_review_product(empty_registry(), {"broken": True}, retained_product_reference="x")
    assert malformed["status"] == "MALFORMED"
    product = product_for(observed_review())
    product["records"][0]["provenance"] = {}
    missing = register(empty_registry(), product)
    assert missing["status"] == "MALFORMED"


def test_summary_has_no_scoring_or_performance_metrics_and_write_is_immutable(tmp_path):
    result = register(empty_registry(), product_for(observed_review(), pending_review("VCB", "prospective_research_snapshot:vcb-pending")))
    summary = summarize_registry(result["registry"])
    assert (summary["reviewable"], summary["pending"], summary["unexplained_residual"]) == (1, 1, 0)
    assert not any("score" in key or "return" in key or "rate" in key for key in summary)
    assert "## Inventory" in render_registry_inventory(result["registry"])
    path = tmp_path / "registry.json"
    write_registry(path, result["registry"])
    write_registry(path, result["registry"])
    with pytest.raises(ValueError, match="IMMUTABLE_LONGITUDINAL_REGISTRY_CONFLICT"):
        write_registry(path, empty_registry())


def test_registry_is_not_connected_to_current_research_paths():
    for path in (ROOT / "builders" / "build_ticker_context.py", ROOT / "builders" / "structured_research_synthesis_boundary.py", ROOT / "builders" / "current_research_packet_shadow_parity.py"):
        assert "prospective_learning_longitudinal_registry" not in path.read_text(encoding="utf-8")
