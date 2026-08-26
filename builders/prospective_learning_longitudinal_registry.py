"""Append-only, content-addressed index for retrospective learning-review products."""
from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence


SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "prospective_learning_longitudinal_registry/v1"
PRODUCT_CONTRACT_VERSION = "prospective_learning_review_product/v1"
_AUTHORITY_BOUNDARY = [
    "REGISTRY_IS_LINEAGE_AND_RETRIEVAL_ONLY",
    "APPEND_ONLY_NO_LATEST_TRUTH_REWRITE",
    "NOT_WIN_LOSS_SCORE_OR_PERFORMANCE_INDEX",
    "NOT_BACKTEST_PROBABILITY_EXPECTED_RETURN_OR_MODEL_LEARNING",
    "NOT_CURRENT_RESEARCH_DECISION_INPUT",
    "NOT_PIT_OR_RAW_AS_TRADED_AUTHORITY",
]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identity_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and ":" in value


def empty_registry() -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
        "registrations": [], "authority_boundary": list(_AUTHORITY_BOUNDARY), "is_actionable": False,
    }
    payload["registry_identity"] = _identity("prospective_learning_longitudinal_registry:", payload)
    return payload


def _registry_errors(registry: Any) -> list[str]:
    if not isinstance(registry, Mapping):
        return ["registry_not_mapping"]
    required = {"schema_version", "contract_version", "registry_identity", "registrations", "authority_boundary", "is_actionable"}
    errors = [f"registry_missing:{item}" for item in sorted(required - set(registry))]
    if errors:
        return errors
    if registry.get("contract_version") != CONTRACT_VERSION:
        errors.append("registry_contract_version_unsupported")
    body = dict(registry); supplied = body.pop("registry_identity", None)
    if supplied != _identity("prospective_learning_longitudinal_registry:", body):
        errors.append("registry_identity_mismatch")
    if not isinstance(registry.get("registrations"), list) or not isinstance(registry.get("authority_boundary"), list) or registry.get("is_actionable") is not False:
        errors.append("registry_structure_malformed")
    return errors


def _product_errors(product: Any) -> list[str]:
    if not isinstance(product, Mapping):
        return ["product_not_mapping"]
    required = {"contract_version", "product_identity", "records", "authority_boundary", "is_actionable"}
    errors = [f"product_missing:{item}" for item in sorted(required - set(product))]
    if errors:
        return errors
    if product.get("contract_version") != PRODUCT_CONTRACT_VERSION:
        errors.append("product_contract_version_unsupported")
    if not _identity_string(product.get("product_identity")):
        errors.append("product_identity_malformed")
    if not isinstance(product.get("records"), list) or not isinstance(product.get("authority_boundary"), list) or product.get("is_actionable") is not False:
        errors.append("product_structure_malformed")
    return errors


def _case_identity(ticker: str, snapshot: str, outcome: str | None) -> tuple[str, str]:
    research_lineage = _identity("prospective_learning_research_origin:", {"ticker": ticker, "research_snapshot_identity": snapshot})
    return research_lineage, _identity("prospective_learning_logical_case:", {"research_origin_identity": research_lineage, "outcome_observation_identity": outcome})


def _candidate(product: Mapping[str, Any], record: Mapping[str, Any], product_reference: str) -> tuple[dict[str, Any] | None, list[str]]:
    original, later, provenance = record.get("original_research_known_at_t"), record.get("later_governed_observation"), record.get("provenance")
    reviewability, comparison, limitations = record.get("reviewability"), record.get("qualified_observed_comparison"), record.get("authority_limitations")
    errors: list[str] = []
    if not isinstance(original, Mapping) or not isinstance(provenance, Mapping):
        return None, ["product_record_origin_or_provenance_malformed"]
    ticker, snapshot, research_session = original.get("ticker"), original.get("snapshot_identity"), original.get("research_session")
    attribution, review = provenance.get("attribution_identity"), record.get("review_identity")
    for name, value in (("ticker", ticker), ("research_snapshot_identity", snapshot), ("research_session", research_session), ("attribution_identity", attribution), ("learning_review_identity", review)):
        if not (isinstance(value, str) and value.strip()):
            errors.append(f"product_record_missing:{name}")
    if not isinstance(reviewability, Mapping) or not isinstance(reviewability.get("status"), str):
        errors.append("product_record_reviewability_malformed")
    if not isinstance(comparison, Mapping) or not isinstance(comparison.get("status"), str):
        errors.append("product_record_comparison_malformed")
    if not isinstance(limitations, list):
        errors.append("product_record_authority_limitations_malformed")
    outcome_identity = outcome_session = None
    if later is not None:
        if not isinstance(later, Mapping):
            errors.append("product_record_later_observation_malformed")
        else:
            outcome_identity, outcome_session = later.get("observation_identity"), later.get("observation_session")
            if not _identity_string(outcome_identity) or not isinstance(outcome_session, str) or outcome_session <= research_session:
                errors.append("product_record_later_observation_temporal_or_identity_malformed")
    if errors:
        return None, errors
    origin_identity, logical_case = _case_identity(ticker, snapshot, outcome_identity)
    immutable = {
        "ticker": ticker, "research_snapshot_identity": snapshot, "research_session": research_session,
        "outcome_observation_identity": outcome_identity, "outcome_session": outcome_session,
        "attribution_identity": attribution, "learning_review_identity": review,
        "reviewability_status": reviewability["status"], "comparison_status": comparison["status"],
    }
    payload = {
        "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
        "registration_status": "REGISTERED", "registered_product_identity": product["product_identity"],
        "retained_product_reference": product_reference,
        "research_origin": {"ticker": ticker, "research_snapshot_identity": snapshot, "research_session": research_session},
        "later_observation": {"outcome_observation_identity": outcome_identity, "outcome_session": outcome_session},
        "review": {"attribution_identity": attribution, "learning_review_identity": review, "reviewability_status": reviewability["status"], "comparison_status": comparison["status"], "reason_codes": sorted(set(reviewability.get("reason_codes") or []) | set(comparison.get("reason_codes") or []))},
        "authority_limitations": copy.deepcopy(limitations),
        "lineage": {"research_origin_identity": origin_identity, "logical_learning_case_identity": logical_case, "prior_pending_registration_identities": []},
        "immutable_case_signature": immutable,
    }
    payload["registration_identity"] = _identity("prospective_learning_registration:", payload)
    return payload, []


def _finish(registrations: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    payload = {
        "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
        "registrations": sorted((copy.deepcopy(dict(item)) for item in registrations), key=lambda item: item["registration_identity"]),
        "authority_boundary": list(_AUTHORITY_BOUNDARY), "is_actionable": False,
    }
    payload["registry_identity"] = _identity("prospective_learning_longitudinal_registry:", payload)
    return payload


def register_review_product(registry: Mapping[str, Any], product: Mapping[str, Any], *, retained_product_reference: str) -> dict[str, Any]:
    """Append product records, retaining pending ancestors and failing closed on conflicts."""
    errors = _registry_errors(registry) + _product_errors(product)
    if not isinstance(retained_product_reference, str) or not retained_product_reference.strip():
        errors.append("retained_product_reference_missing")
    if errors:
        return {"status": "MALFORMED", "reason_codes": sorted(set(errors)), "registry": copy.deepcopy(dict(registry)) if isinstance(registry, Mapping) else None}
    candidates: list[dict[str, Any]] = []
    for record in product["records"]:
        candidate, candidate_errors = _candidate(product, record, retained_product_reference)
        if candidate_errors:
            return {"status": "MALFORMED", "reason_codes": sorted(set(candidate_errors)), "registry": copy.deepcopy(dict(registry))}
        candidates.append(candidate)
    existing = {item["lineage"]["logical_learning_case_identity"]: item for item in registry["registrations"] if isinstance(item, Mapping) and isinstance(item.get("lineage"), Mapping)}
    result_rows: list[dict[str, Any]] = []
    additions: list[dict[str, Any]] = []
    for candidate in sorted(candidates, key=lambda item: item["registration_identity"]):
        logical = candidate["lineage"]["logical_learning_case_identity"]
        prior = existing.get(logical)
        if prior is not None:
            if prior.get("immutable_case_signature") == candidate["immutable_case_signature"]:
                result_rows.append({"registration_identity": prior.get("registration_identity"), "status": "DUPLICATE_IDENTICAL", "reason_codes": []})
                continue
            return {"status": "CONFLICT_FAIL_CLOSED", "reason_codes": ["logical_case_immutable_identity_conflict"], "registry": copy.deepcopy(dict(registry)), "results": result_rows + [{"registration_identity": candidate["registration_identity"], "status": "CONFLICT_FAIL_CLOSED", "reason_codes": ["logical_case_immutable_identity_conflict"]}]}
        origin = candidate["lineage"]["research_origin_identity"]
        if candidate["later_observation"]["outcome_observation_identity"] is not None:
            candidate["lineage"]["prior_pending_registration_identities"] = sorted(
                item["registration_identity"] for item in registry["registrations"]
                if item.get("lineage", {}).get("research_origin_identity") == origin and item.get("later_observation", {}).get("outcome_observation_identity") is None
            )
            candidate["registration_identity"] = _identity("prospective_learning_registration:", {key: value for key, value in candidate.items() if key != "registration_identity"})
        additions.append(candidate)
        existing[logical] = candidate
        result_rows.append({"registration_identity": candidate["registration_identity"], "status": "REGISTERED", "reason_codes": []})
    new_registry = _finish([*registry["registrations"], *additions])
    operation_status = "DUPLICATE_IDENTICAL" if additions == [] else "REGISTERED"
    return {"status": operation_status, "reason_codes": [], "registry": new_registry, "results": result_rows}


def query_registry(registry: Mapping[str, Any], **filters: str) -> list[dict[str, Any]]:
    """Retrieve exact indexed metadata; no scoring, inference, or raw-artifact loading."""
    errors = _registry_errors(registry)
    allowed = {"ticker", "research_session", "outcome_session", "research_snapshot_identity", "attribution_identity", "learning_review_identity", "review_product_identity", "reviewability_status"}
    if errors:
        raise ValueError("REGISTRY_INVALID:" + ",".join(errors))
    if set(filters) - allowed or any(not isinstance(value, str) for value in filters.values()):
        raise ValueError("REGISTRY_QUERY_FILTER_INVALID")
    def matches(record: Mapping[str, Any]) -> bool:
        values = {
            "ticker": record.get("research_origin", {}).get("ticker"), "research_session": record.get("research_origin", {}).get("research_session"),
            "outcome_session": record.get("later_observation", {}).get("outcome_session"), "research_snapshot_identity": record.get("research_origin", {}).get("research_snapshot_identity"),
            "attribution_identity": record.get("review", {}).get("attribution_identity"), "learning_review_identity": record.get("review", {}).get("learning_review_identity"),
            "review_product_identity": record.get("registered_product_identity"), "reviewability_status": record.get("review", {}).get("reviewability_status"),
        }
        return all(values[key] == value for key, value in filters.items())
    return [copy.deepcopy(record) for record in registry["registrations"] if matches(record)]


def summarize_registry(registry: Mapping[str, Any]) -> dict[str, Any]:
    errors = _registry_errors(registry)
    if errors:
        raise ValueError("REGISTRY_INVALID:" + ",".join(errors))
    records = registry["registrations"]
    statuses = Counter(record.get("review", {}).get("reviewability_status") for record in records)
    reasons = Counter(reason for record in records for reason in record.get("review", {}).get("reason_codes", []) if isinstance(reason, str))
    total = len(records); pending = statuses.get("OUTCOME_PENDING", 0); reviewable = statuses.get("REVIEWABLE", 0)
    blocked = total - pending - reviewable
    return {"total_registered_learning_cases": total, "unique_research_snapshots": len({record["research_origin"]["research_snapshot_identity"] for record in records}), "unique_tickers": len({record["research_origin"]["ticker"] for record in records}), "pending": pending, "reviewable": reviewable, "blocked_or_unqualified": blocked, "reason_code_distribution": dict(sorted(reasons.items())), "temporal_violation_count": statuses.get("TEMPORAL_BLOCKED", 0), "identity_conflict_count": 0, "unexplained_residual": total - pending - reviewable - blocked, "authority_boundary": list(_AUTHORITY_BOUNDARY), "is_actionable": False}


def write_registry(path: Path, registry: Mapping[str, Any]) -> None:
    text = _canonical(registry) + "\n"
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError("IMMUTABLE_LONGITUDINAL_REGISTRY_CONFLICT:" + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def render_registry_inventory(registry: Mapping[str, Any]) -> str:
    """Render a compact inventory without interpreting registrations as performance."""
    summary = summarize_registry(registry)
    lines = [
        "# Prospective Learning Longitudinal Registry",
        "",
        f"Registry identity: `{registry['registry_identity']}`",
        "",
        "## Inventory",
        "",
        f"- Registered learning cases: {summary['total_registered_learning_cases']}",
        f"- Unique research snapshots: {summary['unique_research_snapshots']}",
        f"- Unique tickers: {summary['unique_tickers']}",
        f"- Pending: {summary['pending']}",
        f"- Reviewable: {summary['reviewable']}",
        f"- Blocked or unqualified: {summary['blocked_or_unqualified']}",
        "",
        "Registrations are lineage indexes for retrospective review, not performance or correctness judgments.",
        "",
        "## Registrations",
        "",
    ]
    for record in registry["registrations"]:
        origin, later, review = record["research_origin"], record["later_observation"], record["review"]
        lines.extend([
            f"- `{origin['ticker']}` | research `{origin['research_session']}` | outcome `{later['outcome_session'] or 'PENDING'}` | reviewability `{review['reviewability_status']}` | registration `{record['registration_identity']}`",
        ])
    return "\n".join(lines) + "\n"


def write_registry_inventory(path: Path, registry: Mapping[str, Any]) -> None:
    text = render_registry_inventory(registry)
    if path.exists() and path.read_text(encoding="utf-8") != text:
        raise ValueError("IMMUTABLE_LONGITUDINAL_REGISTRY_INVENTORY_CONFLICT:" + str(path))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
