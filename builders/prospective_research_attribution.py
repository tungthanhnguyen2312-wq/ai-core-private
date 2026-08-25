"""Fail-closed, prospective-only research/outcome attribution boundary.

The boundary links an immutable research state to a separately retained, strictly
later observation.  It deliberately records neither a verdict on the research nor
a prediction: an observed price move is only an observation on an explicit basis.
"""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "prospective_research_attribution/v1"

ATTRIBUTION_STATUSES = frozenset({
    "ATTRIBUTABLE", "OUTCOME_PENDING", "INPUT_UNQUALIFIED", "IDENTITY_MISMATCH",
    "TEMPORAL_VIOLATION", "MALFORMED", "UNSUPPORTED_COMPARISON",
})

_REQUIRED_SNAPSHOT = frozenset({
    "ticker", "research_session", "snapshot_identity", "source_artifact_identity",
    "research_state", "evidence_provenance", "authority_limitations",
})
_REQUIRED_OUTCOME = frozenset({
    "ticker", "observation_session", "observation_identity", "source_artifact_identity",
    "research_snapshot_identity", "research_source_artifact_identity", "observed_fields",
    "basis", "evidence_provenance",
})

_AUTHORITY_BOUNDARY = [
    "OBSERVED_OUTCOME_IS_NOT_A_RESEARCH_THESIS_VERDICT",
    "OBSERVED_OUTCOME_IS_NOT_SCENARIO_VALIDATION",
    "NOT_HISTORICAL_PIT_AUTHORITY",
    "NOT_RAW_AS_TRADED_AUTHORITY",
    "NOT_BACKTEST_NOT_EXPECTED_RETURN_NOT_PROBABILITY",
    "NOT_RECOMMENDATION_NOT_SIZING_NOT_STRATEGY_RANKING",
]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _identity_string(value: Any) -> bool:
    return _nonempty_string(value) and ":" in value


def _session(value: Any) -> str | None:
    """Accept only canonical ISO calendar sessions; lexical comparison is then safe."""
    if not isinstance(value, str) or len(value) != 10:
        return None
    try:
        from datetime import date
        date.fromisoformat(value)
    except ValueError:
        return None
    return value


def _ticker(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    result = value.strip().upper()
    return result if result and result.isalnum() else None


def _snapshot_errors(snapshot: Any) -> list[str]:
    if not isinstance(snapshot, Mapping):
        return ["research_snapshot_not_mapping"]
    errors: list[str] = []
    missing = _REQUIRED_SNAPSHOT - set(snapshot)
    if missing:
        errors.extend(f"research_snapshot_missing:{field}" for field in sorted(missing))
        return errors
    if _ticker(snapshot.get("ticker")) is None:
        errors.append("research_snapshot_ticker_malformed")
    if _session(snapshot.get("research_session")) is None:
        errors.append("research_session_malformed")
    for field in ("snapshot_identity", "source_artifact_identity"):
        if not _identity_string(snapshot.get(field)):
            errors.append(f"research_snapshot_{field}_malformed")
    if not isinstance(snapshot.get("research_state"), Mapping):
        errors.append("research_state_malformed")
    if not isinstance(snapshot.get("evidence_provenance"), list) or not snapshot["evidence_provenance"]:
        errors.append("research_evidence_provenance_missing")
    if not isinstance(snapshot.get("authority_limitations"), list):
        errors.append("research_authority_limitations_malformed")
    return errors


def _outcome_errors(outcome: Any) -> list[str]:
    if not isinstance(outcome, Mapping):
        return ["outcome_observation_not_mapping"]
    errors: list[str] = []
    missing = _REQUIRED_OUTCOME - set(outcome)
    if missing:
        errors.extend(f"outcome_observation_missing:{field}" for field in sorted(missing))
        return errors
    if _ticker(outcome.get("ticker")) is None:
        errors.append("outcome_ticker_malformed")
    if _session(outcome.get("observation_session")) is None:
        errors.append("outcome_session_malformed")
    for field in ("observation_identity", "source_artifact_identity", "research_snapshot_identity", "research_source_artifact_identity"):
        if not _identity_string(outcome.get(field)):
            errors.append(f"outcome_{field}_malformed")
    if not isinstance(outcome.get("observed_fields"), Mapping):
        errors.append("observed_fields_malformed")
    if not isinstance(outcome.get("basis"), Mapping):
        errors.append("outcome_basis_malformed")
    if not isinstance(outcome.get("evidence_provenance"), list) or not outcome["evidence_provenance"]:
        errors.append("outcome_evidence_provenance_missing")
    return errors


def _result_identity(snapshot: Any, outcome: Any | None) -> str:
    return _identity("prospective_research_attribution:", {
        "contract_version": CONTRACT_VERSION,
        "research_snapshot": snapshot,
        "outcome_observation": outcome,
    })


def _record(snapshot: Any, outcome: Any | None, status: str, reason_codes: Sequence[str], *, observed_outcome: Mapping[str, Any] | None = None) -> dict[str, Any]:
    temporal_link_identity = _identity("prospective_research_attribution_link:", {
        "research_snapshot_identity": snapshot.get("snapshot_identity") if isinstance(snapshot, Mapping) else None,
        "research_source_artifact_identity": snapshot.get("source_artifact_identity") if isinstance(snapshot, Mapping) else None,
        "outcome_observation_identity": outcome.get("observation_identity") if isinstance(outcome, Mapping) else None,
        "outcome_source_artifact_identity": outcome.get("source_artifact_identity") if isinstance(outcome, Mapping) else None,
    })
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "attribution_identity": _result_identity(snapshot, outcome),
        "temporal_link_identity": temporal_link_identity,
        "attribution_status": status,
        "reason_codes": sorted(set(reason_codes)),
        "research_at_t": copy.deepcopy(dict(snapshot)) if isinstance(snapshot, Mapping) else None,
        "what_was_observed_later": copy.deepcopy(dict(outcome)) if isinstance(outcome, Mapping) else None,
        "observed_outcome": copy.deepcopy(dict(observed_outcome)) if observed_outcome else None,
        "authority_boundary": list(_AUTHORITY_BOUNDARY),
        "is_actionable": False,
    }


def _qualified_price(observation: Mapping[str, Any], *, field: str) -> tuple[float | None, str | None]:
    fields = observation.get("observed_fields")
    basis = observation.get("basis")
    if not isinstance(fields, Mapping) or not isinstance(basis, Mapping):
        return None, "price_comparison_inputs_malformed"
    value = fields.get(field)
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        return None, f"{field}_not_qualified_positive_number"
    basis_name = basis.get("price_basis")
    if not _nonempty_string(basis_name) or basis.get("qualified") is not True:
        return None, "price_basis_unqualified"
    if basis.get("pit_authority") is True:
        return None, "pit_authority_claim_not_permitted"
    return float(value), None


def build_attribution_record(research_snapshot: Mapping[str, Any] | Any, outcome_observation: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build one deterministic record without mutating either temporal input.

    ``outcome_observation=None`` is the normal pending state.  A supplied outcome must
    bind itself to both frozen snapshot identities; it is never selected by proximity or
    silently substituted for the T-state.
    """
    snapshot_errors = _snapshot_errors(research_snapshot)
    if snapshot_errors:
        return _record(research_snapshot, outcome_observation, "MALFORMED", snapshot_errors)
    if outcome_observation is None:
        return _record(research_snapshot, None, "OUTCOME_PENDING", ["outcome_observation_not_supplied"])
    outcome_errors = _outcome_errors(outcome_observation)
    if outcome_errors:
        return _record(research_snapshot, outcome_observation, "MALFORMED", outcome_errors)

    snapshot_ticker = _ticker(research_snapshot["ticker"])
    outcome_ticker = _ticker(outcome_observation["ticker"])
    if snapshot_ticker != outcome_ticker:
        return _record(research_snapshot, outcome_observation, "IDENTITY_MISMATCH", ["ticker_identity_mismatch"])
    if outcome_observation["research_snapshot_identity"] != research_snapshot["snapshot_identity"]:
        return _record(research_snapshot, outcome_observation, "IDENTITY_MISMATCH", ["research_snapshot_identity_mismatch"])
    if outcome_observation["research_source_artifact_identity"] != research_snapshot["source_artifact_identity"]:
        return _record(research_snapshot, outcome_observation, "IDENTITY_MISMATCH", ["research_source_artifact_identity_mismatch"])
    if outcome_observation["observation_session"] <= research_snapshot["research_session"]:
        return _record(research_snapshot, outcome_observation, "TEMPORAL_VIOLATION", ["outcome_session_not_strictly_later"])

    observed: dict[str, Any] = {
        "observation_session": outcome_observation["observation_session"],
        "observation_identity": outcome_observation["observation_identity"],
        "source_artifact_identity": outcome_observation["source_artifact_identity"],
        "basis": copy.deepcopy(dict(outcome_observation["basis"])),
        "qualified_fields": copy.deepcopy(dict(outcome_observation["observed_fields"])),
        "metric_status": "NO_FORMAL_PRICE_COMPARISON_REQUESTED",
    }
    research_price = research_snapshot.get("price_observation")
    if research_price is None:
        return _record(research_snapshot, outcome_observation, "ATTRIBUTABLE", [], observed_outcome=observed)
    if not isinstance(research_price, Mapping):
        return _record(research_snapshot, outcome_observation, "INPUT_UNQUALIFIED", ["research_price_observation_malformed"], observed_outcome=observed)
    start, start_error = _qualified_price(research_price, field="close")
    end, end_error = _qualified_price(outcome_observation, field="close")
    if start_error or end_error:
        observed["metric_status"] = "PRICE_COMPARISON_UNQUALIFIED"
        return _record(research_snapshot, outcome_observation, "INPUT_UNQUALIFIED", [x for x in (start_error, end_error) if x], observed_outcome=observed)
    if research_price["basis"].get("price_basis") != outcome_observation["basis"].get("price_basis"):
        observed["metric_status"] = "PRICE_COMPARISON_UNSUPPORTED"
        return _record(research_snapshot, outcome_observation, "UNSUPPORTED_COMPARISON", ["incompatible_price_basis"], observed_outcome=observed)
    change = end - start
    observed.update({
        "metric_status": "OBSERVED_REALIZED_PRICE_CHANGE",
        "price_change": change,
        "simple_price_return": change / start,
        "formula": "(later_close - research_close) / research_close",
    })
    return _record(research_snapshot, outcome_observation, "ATTRIBUTABLE", [], observed_outcome=observed)


def summarize_attribution_cohort(records: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Summarize unique attribution records without strategy, scenario, or win-rate scoring."""
    unique: dict[str, Mapping[str, Any]] = {}
    duplicate_count = 0
    for record in records:
        identity = record.get("temporal_link_identity") if isinstance(record, Mapping) else None
        if not _identity_string(identity):
            raise ValueError("ATTRIBUTION_RECORD_TEMPORAL_LINK_IDENTITY_MALFORMED")
        if identity in unique:
            duplicate_count += 1
            continue
        unique[identity] = record
    status_counts = Counter(str(row.get("attribution_status")) for row in unique.values())
    reason_counts = Counter(
        reason for row in unique.values() for reason in row.get("reason_codes", []) if isinstance(reason, str)
    )
    known_statuses = {status: status_counts.get(status, 0) for status in sorted(ATTRIBUTION_STATUSES)}
    considered = len(unique)
    observed = known_statuses["ATTRIBUTABLE"]
    pending = known_statuses["OUTCOME_PENDING"]
    blocked = considered - observed - pending
    return {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "cohort_identity": _identity("prospective_research_attribution_cohort:", sorted(unique)),
        "snapshots_considered": considered,
        "later_observations": observed,
        "pending": pending,
        "blocked": blocked,
        "status_distribution": known_statuses,
        "reason_code_distribution": dict(sorted(reason_counts.items())),
        "temporal_integrity_violations": known_statuses["TEMPORAL_VIOLATION"],
        "duplicate_transport_records_excluded": duplicate_count,
        "unexplained_residual": considered - observed - pending - blocked,
        "authority_boundary": list(_AUTHORITY_BOUNDARY),
        "is_actionable": False,
    }
