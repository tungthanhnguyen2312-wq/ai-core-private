from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.prospective_learning_longitudinal_registry import empty_registry, query_registry
from builders.prospective_learning_registry_rollforward import rollforward_registry, write_rollforward_output
from builders.prospective_learning_review_product import build_learning_review_product
from builders.prospective_research_attribution import build_attribution_record
from builders.prospective_research_learning_review import build_learning_review


def snapshot(ticker="HPG", snapshot_id="prospective_research_snapshot:hpg-t"):
    return {"ticker": ticker, "research_session": "2026-08-20", "snapshot_identity": snapshot_id, "source_artifact_identity": f"daily_research_product:{ticker}", "research_state": {"deterministic_decision_state": {"entry_action": "WAIT"}}, "evidence_provenance": [{"identity": f"evidence:{ticker}-t"}], "authority_limitations": ["NOT_PIT", "NOT_RAW_AS_TRADED"]}


def outcome(source, ticker="HPG", observation="exact_session_observation:hpg-t1"):
    return {"ticker": ticker, "observation_session": "2026-08-21", "observation_identity": observation, "source_artifact_identity": f"exact_session_snapshot:{ticker}", "research_snapshot_identity": source["snapshot_identity"], "research_source_artifact_identity": source["source_artifact_identity"], "observed_fields": {"close": 21000}, "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": False, "pit_authority": False}, "evidence_provenance": [{"identity": f"evidence:{ticker}-t1"}]}


def product(ticker="HPG", snapshot_id="prospective_research_snapshot:hpg-t", *, pending=False, observation="exact_session_observation:hpg-t1"):
    source = snapshot(ticker, snapshot_id)
    attribution = build_attribution_record(source) if pending else build_attribution_record(source, outcome(source, ticker, observation))
    return build_learning_review_product([build_learning_review(attribution)])


def item(product_payload, reference):
    return {"product": product_payload, "reference": reference}


def test_empty_registry_first_product_and_existing_registry_new_product():
    first = rollforward_registry(empty_registry(), [item(product(), "a.json")])
    assert (first["status"], first["manifest"]["appended_registration_count"]) == ("COMPLETED", 1)
    second = rollforward_registry(first["registry"], [item(product("VCB", "prospective_research_snapshot:vcb-t", observation="exact_session_observation:vcb-t1"), "b.json")])
    assert (second["status"], len(second["registry"]["registrations"])) == ("COMPLETED", 2)


def test_duplicate_same_run_and_rerun_are_idempotent():
    source = product()
    first = rollforward_registry(empty_registry(), [item(source, "a.json"), item(source, "a-copy.json")])
    assert (first["manifest"]["appended_registration_count"], first["manifest"]["duplicate_identical_count"]) == (1, 1)
    repeat = rollforward_registry(first["registry"], [item(source, "a.json")])
    assert repeat["status"] == "NO_OP_DUPLICATE_IDENTICAL"
    assert repeat["registry"] == first["registry"]


def test_pending_to_reviewable_appends_lineage_and_preserves_original_pending():
    pending = rollforward_registry(empty_registry(), [item(product(pending=True), "pending.json")])
    pending_record = copy.deepcopy(pending["registry"]["registrations"][0])
    later = rollforward_registry(pending["registry"], [item(product(), "later.json")])
    assert later["manifest"]["pending_to_later_linked_count"] == 1
    assert pending_record in later["registry"]["registrations"]
    assert len(query_registry(later["registry"], reviewability_status="OUTCOME_PENDING")) == 1
    assert len(query_registry(later["registry"], reviewability_status="REVIEWABLE")) == 1


def test_conflict_isolated_while_unrelated_product_remains_eligible_and_input_unchanged():
    base = rollforward_registry(empty_registry(), [item(product(), "base.json")])
    input_registry = copy.deepcopy(base["registry"])
    conflict = product(); conflict["records"][0]["review_identity"] = "prospective_research_learning_review:conflict"
    valid = product("VCB", "prospective_research_snapshot:vcb-t", observation="exact_session_observation:vcb-t1")
    result = rollforward_registry(base["registry"], [item(conflict, "conflict.json"), item(valid, "valid.json")])
    assert result["status"] == "COMPLETED_WITH_REJECTIONS"
    assert result["manifest"]["blocked_or_conflict_count"] == 1
    assert len(result["registry"]["registrations"]) == 2
    assert base["registry"] == input_registry


def test_malformed_product_does_not_change_registry_and_manifest_is_deterministic_in_product_order():
    base = rollforward_registry(empty_registry(), [item(product(), "base.json")])
    unchanged = copy.deepcopy(base["registry"])
    malformed = {"broken": True}
    failed = rollforward_registry(base["registry"], [item(malformed, "broken.json")])
    assert failed["status"] == "COMPLETED_WITH_REJECTIONS"
    assert failed["registry"] == unchanged
    a, b = product("VCB", "prospective_research_snapshot:vcb-t", observation="exact_session_observation:vcb-t1"), product("SSI", "prospective_research_snapshot:ssi-t", observation="exact_session_observation:ssi-t1")
    forward = rollforward_registry(empty_registry(), [item(a, "a.json"), item(b, "b.json")])
    reverse = rollforward_registry(empty_registry(), [item(b, "b.json"), item(a, "a.json")])
    assert forward["registry"] == reverse["registry"]
    assert forward["manifest"] == reverse["manifest"]


def test_output_writer_and_query_cli_are_compatible(tmp_path):
    result = rollforward_registry(empty_registry(), [item(product(), "product.json")])
    paths = write_rollforward_output(tmp_path / "out", result)
    assert all(path.exists() for path in paths.values())
    query = subprocess.run([sys.executable, str(ROOT / "tools" / "query_prospective_learning_registry.py"), str(paths["registry"]), "--ticker", "HPG"], check=True, text=True, capture_output=True)
    assert len(json.loads(query.stdout)) == 1


def test_authority_and_not_comparable_status_survive_without_scoring_or_current_path_imports():
    result = rollforward_registry(empty_registry(), [item(product(), "product.json")])
    row = result["registry"]["registrations"][0]
    assert row["review"]["comparison_status"] == "NOT_COMPARABLE"
    assert "NOT_PIT" in row["authority_limitations"]
    assert not any("score" in key or "return" in key or "rate" in key for key in result["manifest"])
    for path in (ROOT / "builders" / "build_ticker_context.py", ROOT / "builders" / "structured_research_synthesis_boundary.py", ROOT / "builders" / "current_research_packet_shadow_parity.py"):
        assert "prospective_learning_registry_rollforward" not in path.read_text(encoding="utf-8")
