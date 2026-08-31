"""Fail-closed Consumer projection of Producer financial qualification-review packets.

This is a read-only research boundary.  It accepts only the pinned Producer
qualification-review contract and never turns candidate evidence into canonical
financial facts, a recommendation input, or an owner-promotion decision.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping


CONSUMER_CONTRACT_VERSION = "official_financial_candidate_evidence_consumer/v1"
PRODUCER_CONTRACT_VERSION = "deterministic_official_financial_candidate_qualification_prep/v1"
PRODUCER_ARTIFACT_TYPE = "DETERMINISTIC_FINANCIAL_CANDIDATE_QUALIFICATION_REVIEW_V1"
PRODUCER_SCHEMA_VERSION = "1.0.0"
PACKET_KEY = "official_financial_candidate_evidence"
UNSUPPORTED_PACKET = "UNSUPPORTED_FINANCIAL_REVIEW_PACKET"
INCOMPLETE_LINEAGE = "FINANCIAL_REVIEW_LINEAGE_INCOMPLETE"
READY = "QUALIFICATION_READY"
CONFLICT = "BLOCKED_CONFLICTING_CANDIDATES"

_REQUIRED_MUTATION_FLAGS = {
    "registry", "facts_registered", "production_db", "scoring", "recommendations", "valuation", "ranking",
}
_REQUIRED_RECORD_FIELDS = {
    "candidate_identity", "candidate_semantic_identity", "ticker", "issuer_identity", "taxonomy_field",
    "reporting_period", "scope", "reported_value", "reported_unit", "normalized_value", "normalized_unit",
    "currency", "source_document_identity", "source_sha256", "source_locator", "article_id",
    "attachment_locator", "route_artifact_identity", "route_record_identity", "raw_acquisition_identity",
    "document_candidate_class", "qualification_state", "blocker_codes", "existing_authority_comparison",
    "proposed_authority_action", "equivalent_candidate_identities", "processing_state",
}
_REQUIRED_STRING_FIELDS = {
    "candidate_identity", "candidate_semantic_identity", "ticker", "issuer_identity", "taxonomy_field",
    "reporting_period", "scope", "reported_unit", "normalized_unit", "currency", "source_document_identity",
    "article_id", "attachment_locator", "route_artifact_identity", "route_record_identity",
    "raw_acquisition_identity", "document_candidate_class", "qualification_state",
    "proposed_authority_action", "processing_state",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _blocked(reason: str) -> dict[str, Any]:
    return {
        "consumer_contract_version": CONSUMER_CONTRACT_VERSION,
        "status": "blocked",
        "is_actionable": False,
        "reason_codes": [reason],
        "authority_boundary": {
            "financial_fact_authority": "NOT_AUTHORITY_PROMOTED",
            "owner_promotion_decision": "NOT_EMITTED",
            "recommendation_ranking_valuation": "NOT_EMITTED",
        },
    }


def _packet_identity_valid(packet: Mapping[str, Any]) -> bool:
    artifact_sha = packet.get("artifact_sha256")
    artifact_identity = packet.get("artifact_identity")
    if not isinstance(artifact_sha, str) or not re.fullmatch(r"[0-9a-f]{64}", artifact_sha):
        return False
    if artifact_identity != f"deterministic_financial_candidate_qualification_review:{artifact_sha}":
        return False
    semantic = {
        key: value for key, value in packet.items()
        if key not in {"artifact_sha256", "artifact_identity"}
    }
    records = semantic.get("records")
    if not isinstance(records, list):
        return False
    semantic["records"] = [
        {key: value for key, value in row.items() if key != "processing_state"}
        if isinstance(row, Mapping) else row
        for row in records
    ]
    return _digest(semantic) == artifact_sha


def _packet_supported(packet: Any) -> bool:
    if not isinstance(packet, Mapping):
        return False
    if (
        packet.get("schema_version") != PRODUCER_SCHEMA_VERSION
        or packet.get("contract_version") != PRODUCER_CONTRACT_VERSION
        or packet.get("artifact_type") != PRODUCER_ARTIFACT_TYPE
        or packet.get("authority_effect") != "NONE"
        or packet.get("zero_silent_drop") is not True
        or not isinstance(packet.get("records"), list)
        or not isinstance(packet.get("input_extraction_identity"), str)
        or not packet["input_extraction_identity"]
    ):
        return False
    mutations = packet.get("authority_mutations")
    return (
        isinstance(mutations, Mapping)
        and set(mutations) == _REQUIRED_MUTATION_FLAGS
        and all(mutations[name] is False for name in _REQUIRED_MUTATION_FLAGS)
        and _packet_identity_valid(packet)
    )


def _record_lineage_complete(record: Any) -> bool:
    if not isinstance(record, Mapping) or not _REQUIRED_RECORD_FIELDS <= set(record):
        return False
    if not all(isinstance(record.get(name), str) and record[name] for name in _REQUIRED_STRING_FIELDS):
        return False
    if not re.fullmatch(r"[0-9a-f]{64}", str(record.get("source_sha256") or "")):
        return False
    if not isinstance(record.get("blocker_codes"), list) or not all(isinstance(item, str) for item in record["blocker_codes"]):
        return False
    if not isinstance(record.get("equivalent_candidate_identities"), list) or not all(isinstance(item, str) for item in record["equivalent_candidate_identities"]):
        return False
    locator = record.get("source_locator")
    comparison = record.get("existing_authority_comparison")
    return (
        isinstance(locator, Mapping)
        and isinstance(locator.get("page"), int)
        and locator["page"] > 0
        and isinstance(locator.get("label"), str)
        and bool(locator["label"])
        and isinstance(locator.get("period_column"), str)
        and bool(locator["period_column"])
        and isinstance(comparison, Mapping)
        and isinstance(comparison.get("state"), str)
        and isinstance(comparison.get("authority_fact_ids"), list)
        and all(isinstance(item, str) for item in comparison["authority_fact_ids"])
    )


def official_financial_candidate_evidence_contract(
    bundle: Mapping[str, Any] | None, ticker: str,
) -> dict[str, Any] | None:
    """Return a research-only, per-ticker projection of an opt-in review packet.

    The Producer packet belongs at ``bundle[PACKET_KEY]``.  Absence preserves
    existing bundles exactly.  Any unknown version or identity failure is blocked;
    any missing row lineage blocks the complete packet rather than guessing a
    source/document relationship.
    """
    packet = (bundle or {}).get(PACKET_KEY) if isinstance(bundle, Mapping) else None
    if packet is None:
        return None
    if not _packet_supported(packet):
        return _blocked(UNSUPPORTED_PACKET)
    if not all(_record_lineage_complete(record) for record in packet["records"]):
        return _blocked(INCOMPLETE_LINEAGE)

    records = [copy.deepcopy(dict(record)) for record in packet["records"] if record["ticker"] == ticker]
    ready_ids = [record["candidate_identity"] for record in records if record["qualification_state"] == READY]
    blocked_ids = [record["candidate_identity"] for record in records if record["qualification_state"] != READY]
    conflict_ids = [
        record["candidate_identity"] for record in records
        if CONFLICT in record["blocker_codes"]
        or record["existing_authority_comparison"].get("state") == "EXISTING_AUTHORITY_CONFLICT"
    ]
    owner_review_ids = [
        record["candidate_identity"] for record in records
        if record["proposed_authority_action"] == "OWNER_PROMOTION_CANDIDATE"
    ]
    return {
        "consumer_contract_version": CONSUMER_CONTRACT_VERSION,
        "status": "available",
        "is_actionable": False,
        "producer_contract_version": PRODUCER_CONTRACT_VERSION,
        "producer_artifact_type": PRODUCER_ARTIFACT_TYPE,
        "producer_artifact_identity": packet["artifact_identity"],
        "input_extraction_identity": packet["input_extraction_identity"],
        "records": records,
        "classification": {
            "authoritative_facts": "USE_SEPARATE_CANONICAL_FINANCIAL_FACTS_NAMESPACE",
            "qualification_ready_candidate_ids": ready_ids,
            "blocked_candidate_ids": blocked_ids,
            "conflict_candidate_ids": conflict_ids,
            "evidence_pending_owner_promotion_ids": owner_review_ids,
        },
        "authority_boundary": {
            "financial_fact_authority": "NOT_AUTHORITY_PROMOTED",
            "producer_authority_effect": "NONE",
            "owner_promotion_decision": "NOT_EMITTED",
            "recommendation_ranking_valuation": "NOT_EMITTED",
            "conflicts_are_not_resolved": True,
        },
    }


def apply_bundle_official_financial_candidate_evidence_contract(
    context: dict[str, Any], bundle: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Attach the opt-in research section without touching canonical facts."""
    contract = official_financial_candidate_evidence_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context[PACKET_KEY] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json",
            "source_dataset": PACKET_KEY,
            "transformation": "Validate the versioned Producer qualification-review packet and pass through only same-ticker candidate evidence, qualification states, blockers, conflict state, existing-authority comparisons, and source/document citation lineage. Consumer does not select a value or promote a fact.",
            "limitations": [
                "Opt-in field: absent unless the input bundle supplies official_financial_candidate_evidence.",
                "Candidate evidence is not authoritative financial fact data; use canonical_financial_facts separately for already-authoritative facts.",
                "QUALIFICATION_READY and OWNER_PROMOTION_CANDIDATE remain non-authoritative and require a separate owner decision.",
                "Blocked and conflicting candidates remain blocked/conflicting; Consumer never resolves them or synthesizes a fallback value.",
                "This section is not actionable and cannot change recommendation, ranking, valuation, strategy eligibility, entry action, or sizing.",
            ],
        })
    return context
