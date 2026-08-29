"""Read-only Consumer adapter for serialized Producer C2 research context.

This adapter validates the Producer artifact's serialized result.  It never
calculates returns, correlations, threshold crossings, components, or a
recommendation.  The small consistency checks below only fail closed when a
purported Producer result contradicts its own serialized metadata.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Mapping


CONSUMER_CONTRACT_VERSION = "correlation_concentration_consumer_context/v1"
PRODUCER_CONTRACT_VERSION = "correlation_concentration_guard/v1"
SUPPORTED_LOOKBACKS = frozenset({20, 60, 120, 250})
THRESHOLD = 0.80
THRESHOLD_COMPARISON = "STRICTLY_GREATER_THAN"
_READY = "PAIRWISE_CORRELATION_READY"
_NON_ACTIONABLE = {
    "portfolio_weights": "NOT_EMITTED", "position_sizing": "NOT_EMITTED", "risk_budget": "NOT_EMITTED",
    "allocation": "NOT_EMITTED", "execution": "NOT_EMITTED", "raw_as_traded": "NOT_PROMOTED",
    "historical_price_pit": "BLOCKED", "historical_backtest": "BLOCKED", "same_close_execution": "NOT_ESTABLISHED",
}


def _result(status: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, **extra}


def content_identity(value: Mapping[str, Any]) -> dict[str, str]:
    payload = {key: item for key, item in value.items() if key not in {"artifact_sha256", "artifact_identity"}}
    digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
    return {"artifact_sha256": digest, "artifact_identity": f"correlation_concentration_consumer_context:{digest}"}


def _finite_correlation(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value)) and abs(float(value)) <= 1.0


def _pair_key(row: Mapping[str, Any]) -> tuple[str, str] | None:
    first, second = row.get("ticker_i"), row.get("ticker_j")
    if not isinstance(first, str) or not isinstance(second, str) or not first or not second or first >= second:
        return None
    return first, second


def parse_correlation_concentration_context(
    artifact: Mapping[str, Any] | None, *, ticker: str, recommendation_label: str, recommendation_readiness: str,
) -> dict[str, Any]:
    """Validate and select C2's serialized per-security context, fail closed."""
    if artifact is None:
        return _result("CORRELATION_CONCENTRATION_NOT_ATTACHED")
    if not isinstance(artifact, Mapping) or artifact.get("contract_version") != PRODUCER_CONTRACT_VERSION:
        return _result("UNSUPPORTED_CORRELATION_CONCENTRATION_CONTRACT")
    identity = artifact.get("artifact_identity")
    metadata, cohort, guard, validation, boundaries = (artifact.get(name) for name in (
        "metadata", "input_cohort", "guard_context", "validation", "authority_boundaries"))
    if not isinstance(identity, str) or not identity.startswith("correlation_concentration_guard:") or not all(
        isinstance(value, Mapping) for value in (metadata, cohort, guard, validation, boundaries)
    ):
        return _result("CORRELATION_CONCENTRATION_MALFORMED")
    threshold = metadata.get("threshold_contract")
    lookback = metadata.get("selected_lookback_sessions")
    securities = cohort.get("security_identifiers")
    if not isinstance(threshold, Mapping) or threshold.get("metric") != "PEARSON_CORRELATION_FROM_C1" or threshold.get("threshold") != THRESHOLD or threshold.get("comparison") != THRESHOLD_COMPARISON or threshold.get("status") != "V1_DETERMINISTIC_RESEARCH_HEURISTIC_NOT_STATISTICALLY_CALIBRATED" or lookback not in SUPPORTED_LOOKBACKS or not isinstance(securities, list) or securities != sorted(securities) or ticker not in securities:
        return _result("CORRELATION_CONCENTRATION_MALFORMED")
    if boundaries.get("research_context_only") is not True or any(boundaries.get(key) != value for key, value in _NON_ACTIONABLE.items()):
        return _result("CORRELATION_CONCENTRATION_AUTHORITY_VIOLATION")
    upstream = artifact.get("upstream_recommendation_context")
    recommendation = upstream.get(ticker) if isinstance(upstream, Mapping) else None
    if not isinstance(recommendation, Mapping) or recommendation.get("status") != "UPSTREAM_RECOMMENDATION_PASSTHROUGH" or recommendation.get("recommendation_label") != recommendation_label or recommendation.get("recommendation_readiness") != recommendation_readiness:
        return _result("CORRELATION_CONCENTRATION_RECOMMENDATION_CONFLICT")
    rows = artifact.get("pairwise_correlation_context")
    groups = artifact.get("concentration_groups")
    if not isinstance(rows, list) or not isinstance(groups, list):
        return _result("CORRELATION_CONCENTRATION_MALFORMED")
    pair_index: dict[tuple[str, str], Mapping[str, Any]] = {}
    selected_pairs: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, Mapping) or row.get("lookback_sessions") != lookback:
            return _result("CORRELATION_CONCENTRATION_MALFORMED")
        key = _pair_key(row)
        if key is None or key in pair_index:
            return _result("CORRELATION_CONCENTRATION_MALFORMED")
        if row.get("status") == _READY:
            if not _finite_correlation(row.get("correlation")) or not isinstance(row.get("return_observations"), int) or row["return_observations"] <= 0:
                return _result("CORRELATION_CONCENTRATION_MALFORMED")
        elif row.get("correlation") is not None:
            return _result("CORRELATION_CONCENTRATION_MALFORMED")
        pair_index[key] = row
        if ticker in key:
            selected_pairs.append(copy.deepcopy(dict(row)))
    ready_count = sum(row.get("status") == _READY for row in rows)
    if validation.get("pair_count") != len(rows) or validation.get("pairwise_ready_count") != ready_count or validation.get("pairwise_insufficient_or_unavailable_count") != len(rows) - ready_count:
        return _result("CORRELATION_CONCENTRATION_INTERNAL_INCONSISTENCY")
    group_edges: set[tuple[str, str]] = set()
    selected_groups: list[dict[str, Any]] = []
    prior_group_id = ""
    for group in groups:
        if not isinstance(group, Mapping) or not isinstance(group.get("group_id"), str) or group["group_id"] <= prior_group_id:
            return _result("CORRELATION_CONCENTRATION_MALFORMED")
        prior_group_id = group["group_id"]
        members, edges = group.get("tickers"), group.get("triggered_edges")
        if not isinstance(members, list) or members != sorted(members) or not isinstance(edges, list) or group.get("security_count") != len(members) or group.get("edge_count") != len(edges):
            return _result("CORRELATION_CONCENTRATION_MALFORMED")
        expected_group_status = "CONCENTRATED_CORRELATED_GROUP" if len(members) >= 3 else "CORRELATED_PAIR_CONTEXT"
        if group.get("group_status") != expected_group_status:
            return _result("CORRELATION_CONCENTRATION_INTERNAL_INCONSISTENCY")
        for edge in edges:
            if not isinstance(edge, Mapping) or _pair_key(edge) is None:
                return _result("CORRELATION_CONCENTRATION_MALFORMED")
            key = _pair_key(edge)
            source = pair_index.get(key)
            if source != edge or edge.get("status") != _READY or not _finite_correlation(edge.get("correlation")) or edge["correlation"] <= THRESHOLD or not set(key).issubset(set(members)):
                return _result("CORRELATION_CONCENTRATION_INTERNAL_INCONSISTENCY")
            group_edges.add(key)
        if ticker in members:
            selected_groups.append(copy.deepcopy(dict(group)))
    expected_edges = {key for key, row in pair_index.items() if row.get("status") == _READY and row.get("correlation") > THRESHOLD}
    if group_edges != expected_edges or validation.get("triggered_edge_count") != len(group_edges) or validation.get("triggered_group_count") != len(groups) or validation.get("concentrated_group_count") != sum(group.get("security_count", 0) >= 3 for group in groups):
        return _result("CORRELATION_CONCENTRATION_INTERNAL_INCONSISTENCY")
    joint = guard.get("joint_matrix_source_context")
    if not isinstance(joint, Mapping) or guard.get("joint_matrix_status") != joint.get("status") or guard.get("pairwise_context_is_independent_of_joint_matrix_readiness") is not True:
        return _result("CORRELATION_CONCENTRATION_MALFORMED")
    return _result("CORRELATION_CONCENTRATION_READY", context={
        "consumer_contract_version": CONSUMER_CONTRACT_VERSION, "producer_contract_version": PRODUCER_CONTRACT_VERSION,
        "producer_artifact_identity": identity, "as_of_session": metadata.get("as_of_session"),
        "selected_lookback_sessions": lookback, "threshold_contract": copy.deepcopy(dict(threshold)),
        "guard_status": guard.get("status"), "reason_codes": copy.deepcopy(list(guard.get("reason_codes") or [])),
        "joint_matrix_status": guard.get("joint_matrix_status"), "pairwise_ready_count": ready_count,
        "pairwise_insufficient_or_unavailable_count": len(rows) - ready_count,
        "pairs_for_security": selected_pairs, "concentration_groups_for_security": selected_groups,
        "warnings": copy.deepcopy(list(artifact.get("warnings") or [])),
        "recommendation_label": recommendation_label, "recommendation_readiness": recommendation_readiness,
        "recommendation_mutation_count": validation.get("recommendation_mutation_count"),
    })
