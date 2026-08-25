"""Retrospective learning-review envelopes over validated prospective attribution.

This module is intentionally not imported by the current research/product builders.
It reviews a previously constructed attribution record and never re-joins raw T and
later inputs, thereby preserving the attribution boundary as the temporal authority.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence

from builders.prospective_research_attribution import ATTRIBUTION_STATUSES


SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "prospective_research_learning_review/v1"
REVIEWABILITY_STATUSES = frozenset({
    "REVIEWABLE", "OUTCOME_PENDING", "NOT_COMPARABLE", "INSUFFICIENT_EVIDENCE",
    "UNQUALIFIED", "TEMPORAL_BLOCKED", "MALFORMED",
})

_AUTHORITY_BOUNDARY = [
    "RETROSPECTIVE_REVIEW_IS_SEPARATE_FROM_CURRENT_RESEARCH",
    "KNOWN_AT_T_AND_NEW_AFTER_T_REMAIN_SEPARATE",
    "OBSERVED_OUTCOME_IS_NOT_THESIS_OR_SCENARIO_VALIDATION",
    "NOT_WIN_LOSS_CORRECT_WRONG_OR_RESEARCH_SCORE",
    "NOT_PROBABILITY_EXPECTED_RETURN_BACKTEST_OR_MODEL_ACCURACY",
    "NOT_RECOMMENDATION_ENTRY_ACTION_SIZING_OR_STRATEGY_OPTIMIZATION",
    "NOT_HISTORICAL_PIT_OR_RAW_AS_TRADED_AUTHORITY",
]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identity_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and ":" in value


def _reference_values(value: Any) -> list[str]:
    """Extract explicit identifiers only; arbitrary prose never becomes a reference."""
    values: list[str] = []
    if isinstance(value, Mapping):
        for key in ("identity", "source_artifact_identity", "snapshot_identity", "observation_identity"):
            candidate = value.get(key)
            if _identity_string(candidate):
                values.append(candidate)
    return values


def _attribution_errors(attribution: Any) -> list[str]:
    if not isinstance(attribution, Mapping):
        return ["attribution_not_mapping"]
    errors: list[str] = []
    required = {
        "schema_version", "contract_version", "attribution_identity", "temporal_link_identity",
        "attribution_status", "reason_codes", "research_at_t", "what_was_observed_later",
        "authority_boundary", "is_actionable",
    }
    for field in sorted(required - set(attribution)):
        errors.append(f"attribution_missing:{field}")
    if errors:
        return errors
    if attribution.get("contract_version") != "prospective_research_attribution/v1":
        errors.append("attribution_contract_version_unsupported")
    for field in ("attribution_identity", "temporal_link_identity"):
        if not _identity_string(attribution.get(field)):
            errors.append(f"attribution_{field}_malformed")
    if attribution.get("attribution_status") not in ATTRIBUTION_STATUSES:
        errors.append("attribution_status_malformed")
    if not isinstance(attribution.get("reason_codes"), list):
        errors.append("attribution_reason_codes_malformed")
    if attribution.get("research_at_t") is not None and not isinstance(attribution.get("research_at_t"), Mapping):
        errors.append("attribution_research_at_t_malformed")
    if attribution.get("what_was_observed_later") is not None and not isinstance(attribution.get("what_was_observed_later"), Mapping):
        errors.append("attribution_later_observation_malformed")
    if not isinstance(attribution.get("authority_boundary"), list) or attribution.get("is_actionable") is not False:
        errors.append("attribution_authority_boundary_malformed")
    return errors


def _reviewability(attribution: Mapping[str, Any]) -> tuple[str, list[str]]:
    status = attribution["attribution_status"]
    if status == "ATTRIBUTABLE":
        return "REVIEWABLE", []
    if status == "OUTCOME_PENDING":
        return "OUTCOME_PENDING", list(attribution["reason_codes"])
    if status == "UNSUPPORTED_COMPARISON":
        return "NOT_COMPARABLE", list(attribution["reason_codes"])
    if status == "INPUT_UNQUALIFIED":
        return "UNQUALIFIED", list(attribution["reason_codes"])
    if status == "TEMPORAL_VIOLATION":
        return "TEMPORAL_BLOCKED", list(attribution["reason_codes"])
    if status == "MALFORMED":
        return "MALFORMED", list(attribution["reason_codes"])
    return "INSUFFICIENT_EVIDENCE", list(attribution["reason_codes"])


def _provenance(attribution: Mapping[str, Any]) -> dict[str, list[str] | str]:
    research = attribution.get("research_at_t") or {}
    later = attribution.get("what_was_observed_later") or {}
    known = [research.get("snapshot_identity"), research.get("source_artifact_identity")]
    known.extend(ref for item in research.get("evidence_provenance", []) for ref in _reference_values(item))
    new = [later.get("observation_identity"), later.get("source_artifact_identity")]
    new.extend(ref for item in later.get("evidence_provenance", []) for ref in _reference_values(item))
    return {
        "attribution_identity": attribution["attribution_identity"],
        "temporal_link_identity": attribution["temporal_link_identity"],
        "known_at_t_references": sorted({item for item in known if _identity_string(item)}),
        "new_after_t_references": sorted({item for item in new if _identity_string(item)}),
    }


def _comparison_review(attribution: Mapping[str, Any]) -> dict[str, Any]:
    observed = attribution.get("observed_outcome")
    if not isinstance(observed, Mapping):
        return {"status": "NOT_COMPARABLE", "reason_codes": ["attribution_has_no_observed_outcome"]}
    metric_status = observed.get("metric_status")
    if metric_status == "OBSERVED_REALIZED_PRICE_CHANGE":
        return {"status": "REVIEWABLE_QUALIFIED_OBSERVED_METRIC", "observed_metric": copy.deepcopy(dict(observed))}
    if metric_status == "NO_FORMAL_PRICE_COMPARISON_REQUESTED":
        return {"status": "NOT_COMPARABLE", "reason_codes": ["attribution_did_not_emit_formal_price_metric"]}
    return {"status": "NOT_COMPARABLE", "reason_codes": [f"attribution_metric_status:{metric_status or 'missing'}"]}


def build_learning_review(attribution: Mapping[str, Any] | Any) -> dict[str, Any]:
    """Build one review envelope from attribution only, preserving both time slices."""
    errors = _attribution_errors(attribution)
    if errors:
        return {
            "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
            "review_identity": _identity("prospective_research_learning_review:", {"attribution": attribution}),
            "reviewability": {"status": "MALFORMED", "reason_codes": errors},
            "original_research_state": None, "later_observation": None,
            "learning_limitations": list(_AUTHORITY_BOUNDARY), "provenance": None,
            "is_actionable": False,
        }
    reviewability, reasons = _reviewability(attribution)
    research = copy.deepcopy(dict(attribution["research_at_t"])) if isinstance(attribution["research_at_t"], Mapping) else None
    later = copy.deepcopy(dict(attribution["what_was_observed_later"])) if isinstance(attribution["what_was_observed_later"], Mapping) else None
    declared_conditions = ((research or {}).get("research_state") or {}).get("machine_evaluable_conditions")
    conditions = copy.deepcopy(declared_conditions) if isinstance(declared_conditions, list) else []
    payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "reviewability": {"status": reviewability, "reason_codes": sorted(set(reasons))},
        "original_research_state": research,
        "later_observation": later,
        "qualified_observed_comparison": _comparison_review(attribution),
        "machine_condition_review": {
            "status": "NOT_EVALUATED_NO_DETERMINISTIC_CONDITION_ENGINE",
            "declared_conditions": conditions,
            "reason_codes": ["free_form_thesis_and_narrative_are_not_machine_evaluated"],
        },
        "learning_limitations": list(_AUTHORITY_BOUNDARY) + copy.deepcopy(list((research or {}).get("authority_limitations") or [])),
        "provenance": _provenance(attribution),
        "is_actionable": False,
    }
    payload["review_identity"] = _identity("prospective_research_learning_review:", payload)
    return payload


def summarize_learning_reviews(reviews: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Count transparent reviewability states, never outcomes as wins or scores."""
    unique: dict[str, Mapping[str, Any]] = {}
    duplicate_count = 0
    for review in reviews:
        if not isinstance(review, Mapping):
            raise ValueError("LEARNING_REVIEW_NOT_MAPPING")
        provenance = review.get("provenance") or {}
        key = provenance.get("temporal_link_identity") if isinstance(provenance, Mapping) else None
        if not _identity_string(key):
            key = review.get("review_identity")
        if not _identity_string(key):
            raise ValueError("LEARNING_REVIEW_IDENTITY_MALFORMED")
        if key in unique:
            duplicate_count += 1
            continue
        unique[key] = review
    states = Counter(str((review.get("reviewability") or {}).get("status")) for review in unique.values())
    reasons = Counter(reason for review in unique.values() for reason in ((review.get("reviewability") or {}).get("reason_codes") or []) if isinstance(reason, str))
    comparison_not_comparable = sum(
        (review.get("qualified_observed_comparison") or {}).get("status") == "NOT_COMPARABLE"
        for review in unique.values()
    )
    distribution = {status: states.get(status, 0) for status in sorted(REVIEWABILITY_STATUSES)}
    total = len(unique)
    reviewable, pending = distribution["REVIEWABLE"], distribution["OUTCOME_PENDING"]
    blocked = total - reviewable - pending
    return {
        "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
        "cohort_identity": _identity("prospective_research_learning_review_cohort:", sorted(unique)),
        "total_attribution_records": total, "reviewable": reviewable, "pending": pending,
        "blocked_or_unqualified": blocked,
        "non_comparable": distribution["NOT_COMPARABLE"], "malformed": distribution["MALFORMED"],
        "comparison_not_comparable": comparison_not_comparable,
        "reviewability_distribution": distribution,
        "reason_code_distribution": dict(sorted(reasons.items())),
        "temporal_integrity_failures": distribution["TEMPORAL_BLOCKED"],
        "duplicate_transport_records_excluded": duplicate_count,
        "unexplained_residual": total - reviewable - pending - blocked,
        "authority_boundary": list(_AUTHORITY_BOUNDARY), "is_actionable": False,
    }
