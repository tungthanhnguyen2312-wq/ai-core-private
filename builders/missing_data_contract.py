"""Shared missing-data metadata contract for ticker context builders."""

from __future__ import annotations

from enum import Enum
from typing import Any, Mapping


CONTRACT_VERSION = "1.0.0"


class MetricStatus(str, Enum):
    REPORTED = "reported"
    DERIVED = "derived"
    PROXY = "proxy"
    SOURCE_EMPTY = "source_empty"
    MAPPING_MISSING = "mapping_missing"
    INSUFFICIENT_PERIODS = "insufficient_periods"
    PARSE_FAILED = "parse_failed"
    STALE = "stale"
    NOT_APPLICABLE = "not_applicable"
    NOT_QUERIED = "not_queried"
    NETWORK_FAILED = "network_failed"
    UNSUPPORTED = "unsupported"
    DERIVATION_NOT_IMPLEMENTED = "derivation_not_implemented"
    UNIT_UNKNOWN = "unit_unknown"
    PERIOD_BASIS_UNKNOWN = "period_basis_unknown"


AVAILABLE_STATUSES = {
    MetricStatus.REPORTED.value,
    MetricStatus.DERIVED.value,
    MetricStatus.PROXY.value,
}


def _status_value(status: MetricStatus | str) -> str:
    try:
        return status.value if isinstance(status, MetricStatus) else MetricStatus(status).value
    except ValueError as exc:
        raise ValueError(f"Unsupported metric status: {status!r}") from exc


def build_metric_meta(
    value: Any,
    status: MetricStatus | str,
    reason: str | None = None,
    source: str | None = None,
    period: str | None = None,
    basis: str | None = None,
    raw_item_id: str | None = None,
    raw_label: str | None = None,
    confidence: float | None = None,
    formula: str | None = None,
    inputs: list[str] | None = None,
    details: Mapping[str, Any] | None = None,
    unit: str | None = None,
    period_calendar_end: str | None = None,
    annualization: str | None = None,
) -> dict[str, Any]:
    """Build JSON-safe provenance metadata without inventing a replacement value."""
    normalized_status = _status_value(status)
    if normalized_status in AVAILABLE_STATUSES and value is None:
        raise ValueError(f"Status {normalized_status!r} requires a non-missing value")
    if normalized_status == MetricStatus.NOT_APPLICABLE.value and value is not None:
        raise ValueError("not_applicable must not carry a value")
    if normalized_status == MetricStatus.DERIVED.value and (not formula or not inputs):
        raise ValueError("derived metrics require formula and inputs")
    if confidence is not None and not 0.0 <= float(confidence) <= 1.0:
        raise ValueError("confidence must be between 0 and 1")

    meta: dict[str, Any] = {
        "value": value,
        "status": normalized_status,
        "reason": reason,
        "source": source,
        "period": period,
        "basis": basis,
        "raw_item_id": raw_item_id,
        "raw_label": raw_label,
        "confidence": confidence,
    }
    if formula is not None:
        meta["formula"] = formula
    if inputs is not None:
        meta["inputs"] = list(inputs)
    if details:
        meta["details"] = dict(details)
    # item A (Data Contract Hardening v1.1): optional, additive-only fields so ROE (and any
    # future annualized/unit-bearing metric) can be self-describing without ambiguity between
    # a decimal ratio and a percentage, or between a quarter/fiscal-year/TTM basis. Absent
    # unless explicitly passed, so every existing call site's output dict is unchanged.
    if unit is not None:
        meta["unit"] = unit
    if period_calendar_end is not None:
        meta["period_calendar_end"] = period_calendar_end
    if annualization is not None:
        meta["annualization"] = annualization
    return meta


def set_metric_with_meta(container: dict[str, Any], metric: str, meta: Mapping[str, Any]) -> None:
    """Keep the legacy scalar while adding the parallel metadata field."""
    if "value" not in meta or "status" not in meta:
        raise ValueError("Metric metadata requires value and status")
    container[metric] = meta["value"]
    container[f"{metric}_meta"] = dict(meta)


def is_metric_available(meta: Mapping[str, Any] | None) -> bool:
    return bool(meta and meta.get("status") in AVAILABLE_STATUSES and meta.get("value") is not None)


def build_section_coverage(metrics: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Calculate coverage without counting not_applicable metrics as missing."""
    not_applicable = sorted(
        name for name, meta in metrics.items()
        if meta.get("status") == MetricStatus.NOT_APPLICABLE.value
    )
    applicable = {name: meta for name, meta in metrics.items() if name not in not_applicable}
    available = sorted(name for name, meta in applicable.items() if is_metric_available(meta))
    missing = sorted(name for name in applicable if name not in available)
    expected_count = len(applicable)
    coverage = len(available) / expected_count if expected_count else 1.0
    if not expected_count:
        status = "not_applicable"
    elif not missing:
        status = "complete"
    elif available:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "coverage": round(coverage, 6),
        "available_metrics": len(available),
        "expected_metrics": expected_count,
        "missing_metrics": missing,
        "available_metric_names": available,
        "not_applicable_metrics": not_applicable,
    }
