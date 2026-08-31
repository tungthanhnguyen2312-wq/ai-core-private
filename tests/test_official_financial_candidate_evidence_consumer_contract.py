"""Fail-closed Consumer tests for official financial qualification-review evidence."""
from __future__ import annotations

import copy
import hashlib
import json

from builders.official_financial_candidate_evidence import (
    CONFLICT,
    INCOMPLETE_LINEAGE,
    PACKET_KEY,
    PRODUCER_ARTIFACT_TYPE,
    PRODUCER_CONTRACT_VERSION,
    READY,
    UNSUPPORTED_PACKET,
    apply_bundle_official_financial_candidate_evidence_contract,
    official_financial_candidate_evidence_contract,
)


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()


def _record(**changes):
    base = {
        "candidate_identity": "candidate:aaa", "candidate_semantic_identity": "semantic:aaa",
        "ticker": "AAA", "issuer_identity": "AAA issuer", "taxonomy_field": "revenue",
        "reporting_period": "2025", "scope": "CONSOLIDATED", "reported_value": "100",
        "reported_unit": "triệu VND", "normalized_value": 100_000_000, "normalized_unit": "VND",
        "currency": "VND", "source_document_identity": "hnx_financial_document:aaa",
        "source_sha256": "a" * 64,
        "source_locator": {"page": 12, "label": "Doanh thu thuần", "period_column": "Năm 2025"},
        "article_id": "101", "attachment_locator": "https://owa.hnx.vn/ftp/aaa.pdf",
        "route_artifact_identity": "route:aaa", "route_record_identity": "route-record:aaa",
        "raw_acquisition_identity": "raw:aaa", "document_candidate_class": "PRIMARY_FINANCIAL_STATEMENT",
        "qualification_state": READY, "blocker_codes": [],
        "existing_authority_comparison": {"state": "NO_EXISTING_AUTHORITY_RECORD", "authority_fact_ids": []},
        "proposed_authority_action": "OWNER_PROMOTION_CANDIDATE",
        "equivalent_candidate_identities": ["candidate:aaa"], "processing_state": "EVALUATED",
    }
    return base | changes


def _packet(*records):
    packet = {
        "schema_version": "1.0.0", "contract_version": PRODUCER_CONTRACT_VERSION,
        "artifact_type": PRODUCER_ARTIFACT_TYPE, "input_extraction_identity": "extraction:fixture",
        "existing_authority_input_identity": None, "records": list(records),
        "input_candidate_count": len(records),
        "qualification_ready_count": sum(row["qualification_state"] == READY for row in records),
        "blocked_counts_by_reason": {}, "zero_silent_drop": True, "authority_effect": "NONE",
        "authority_mutations": {
            "registry": False, "facts_registered": False, "production_db": False, "scoring": False,
            "recommendations": False, "valuation": False, "ranking": False,
        },
    }
    semantic = {**packet, "records": [{key: value for key, value in row.items() if key != "processing_state"} for row in records]}
    digest = _digest(semantic)
    return packet | {"artifact_sha256": digest, "artifact_identity": f"deterministic_financial_candidate_qualification_review:{digest}"}


def _bundle(packet):
    return {PACKET_KEY: packet}


def test_exact_supported_packet_is_projected_deterministically_as_research_only():
    packet = _packet(_record())
    first = official_financial_candidate_evidence_contract(_bundle(packet), "AAA")
    second = official_financial_candidate_evidence_contract(_bundle(copy.deepcopy(packet)), "AAA")
    assert first == second
    assert first["records"] == [packet["records"][0]]
    assert first["records"][0]["source_locator"]["page"] == 12
    assert first["classification"]["qualification_ready_candidate_ids"] == ["candidate:aaa"]
    assert first["classification"]["evidence_pending_owner_promotion_ids"] == ["candidate:aaa"]
    assert first["authority_boundary"]["financial_fact_authority"] == "NOT_AUTHORITY_PROMOTED"
    assert first["is_actionable"] is False


def test_unsupported_version_fails_closed():
    packet = _packet(_record())
    packet["contract_version"] = "unknown/v999"
    result = official_financial_candidate_evidence_contract(_bundle(packet), "AAA")
    assert result["status"] == "blocked"
    assert result["reason_codes"] == [UNSUPPORTED_PACKET]


def test_incomplete_lineage_fails_closed_even_with_an_internally_consistent_packet():
    packet = _packet(_record(route_record_identity=""))
    result = official_financial_candidate_evidence_contract(_bundle(packet), "AAA")
    assert result["status"] == "blocked"
    assert result["reason_codes"] == [INCOMPLETE_LINEAGE]


def test_ready_candidate_remains_non_authoritative_and_does_not_overwrite_canonical_namespace():
    context = {"ticker": "AAA", "provenance": [], "canonical_financial_facts": {"facts": ["existing"]}}
    apply_bundle_official_financial_candidate_evidence_contract(context, _bundle(_packet(_record())))
    assert context["canonical_financial_facts"] == {"facts": ["existing"]}
    evidence = context[PACKET_KEY]
    assert evidence["records"][0]["qualification_state"] == READY
    assert evidence["authority_boundary"]["owner_promotion_decision"] == "NOT_EMITTED"


def test_blocked_candidate_and_conflict_are_preserved_without_value_selection():
    blocked = _record(
        candidate_identity="candidate:blocked", qualification_state="BLOCKED_UNIT_UNKNOWN",
        blocker_codes=["BLOCKED_UNIT_UNKNOWN"], proposed_authority_action="NOT_ELIGIBLE",
    )
    conflict = _record(
        candidate_identity="candidate:conflict", qualification_state=CONFLICT,
        blocker_codes=[CONFLICT], proposed_authority_action="OWNER_CONFLICT_REVIEW_REQUIRED",
        existing_authority_comparison={"state": "EXISTING_AUTHORITY_CONFLICT", "authority_fact_ids": ["fact:one"]},
    )
    result = official_financial_candidate_evidence_contract(_bundle(_packet(blocked, conflict)), "AAA")
    assert result["classification"]["blocked_candidate_ids"] == ["candidate:blocked", "candidate:conflict"]
    assert result["classification"]["conflict_candidate_ids"] == ["candidate:conflict"]
    assert result["records"][1]["normalized_value"] == 100_000_000
    assert "selected_value" not in result


def test_missing_opt_in_packet_keeps_existing_bundles_and_contexts_unchanged():
    context = {"ticker": "AAA", "provenance": []}
    assert official_financial_candidate_evidence_contract({}, "AAA") is None
    assert apply_bundle_official_financial_candidate_evidence_contract(context, {}) == context
    assert PACKET_KEY not in context
