"""Fail-closed Consumer projection for Producer Financial Analysis V2.

The Producer owns all financial calculations and classifications.  This adapter accepts
only its compact, qualitative ``financial_analysis_compact/v1`` contract and exposes it
to Consumer prompts without values, ratios, scoring, or a new recommendation signal.
"""
from __future__ import annotations

import copy
from typing import Any, Iterable, Mapping

CONSUMER_CONTRACT_VERSION = "financial_analysis_consumer_context/v1"
COMPACT_CONTRACT_VERSION = "financial_analysis_compact/v1"
AVAILABLE = "AVAILABLE"
ABSENT = "ABSENT"
_RAW_FINANCIAL_KEYS = frozenset({"features", "reported_value", "value", "numerator", "denominator"})


class FinancialAnalysisConsumerContextError(ValueError):
    """Raised when an explicitly supplied financial V2 record is not safe to consume."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise FinancialAnalysisConsumerContextError(reason)


def _copy_list(value: Any) -> list[Any]:
    return copy.deepcopy(list(value)) if isinstance(value, (list, tuple)) else ([copy.deepcopy(value)] if isinstance(value, str) else [])


def _contains_raw_values(value: Any) -> bool:
    if isinstance(value, Mapping):
        return any(str(key).lower() in _RAW_FINANCIAL_KEYS or _contains_raw_values(item) for key, item in value.items())
    if isinstance(value, list):
        return any(_contains_raw_values(item) for item in value)
    return False


def _state(value: Any, *, fallback_basis: Any = None) -> dict[str, Any]:
    """Preserve a Producer state/basis pair without inferring an economic direction."""
    if not isinstance(value, Mapping):
        return {
            "state": value if isinstance(value, str) else "UNAVAILABLE",
            "basis": fallback_basis if isinstance(fallback_basis, str) else "NOT_SUPPLIED",
            "reason_codes": [],
        }
    return {
        "state": value.get("state", "UNAVAILABLE"),
        "basis": value.get("basis", fallback_basis if isinstance(fallback_basis, str) else "NOT_SUPPLIED"),
        "reason_codes": _copy_list(value.get("reason_codes")),
    }


def _annotation(compact: Mapping[str, Any]) -> Mapping[str, Any]:
    for key in ("decision_financial_annotation", "financial_decision_annotation"):
        value = compact.get(key)
        if isinstance(value, Mapping):
            return value
    return {}


def build_financial_analysis_consumer_context(compact: Mapping[str, Any]) -> dict[str, Any]:
    """Project one compact V2 record, preserving its state and authority boundaries.

    ``ABSENT`` is a first-class coverage state.  It is intentionally not translated into
    weak, neutral, negative, or zero financial evidence.
    """
    _require(isinstance(compact, Mapping), "FINANCIAL_ANALYSIS_COMPACT_NOT_OBJECT")
    _require(compact.get("contract_version") == COMPACT_CONTRACT_VERSION, "FINANCIAL_ANALYSIS_COMPACT_VERSION_UNSUPPORTED")
    _require(isinstance(compact.get("ticker"), str) and bool(compact["ticker"]), "FINANCIAL_ANALYSIS_TICKER_MISSING")
    _require(compact.get("is_actionable") is False, "FINANCIAL_ANALYSIS_ACTIONABILITY_MUST_BE_FALSE")
    _require(not _contains_raw_values(compact), "FINANCIAL_ANALYSIS_RAW_VALUES_FORBIDDEN")

    status = compact.get("status")
    _require(status in {AVAILABLE, ABSENT}, "FINANCIAL_ANALYSIS_STATUS_UNSUPPORTED:" + str(status))
    identity = {
        "source_context_identity": compact.get("source_context_identity"),
        "financial_content_identity": compact.get("financial_content_identity"),
        "lineage_ref": compact.get("lineage_ref"),
        "pit_authority": compact.get("pit_authority"),
    }
    base: dict[str, Any] = {
        "contract_version": CONSUMER_CONTRACT_VERSION,
        "producer_contract_version": COMPACT_CONTRACT_VERSION,
        "ticker": compact["ticker"],
        "availability": status,
        "issuer_type": compact.get("issuer_type"),
        "analysis_family": compact.get("analysis_family"),
        "as_of_financial_period": compact.get("as_of_financial_period"),
        "source_identity": identity,
        "is_actionable": False,
        "authority_notes": [
            "Producer Financial Analysis V2 is the sole authority for every retained state; Consumer performs no ratio calculation, score, ranking, forecast, valuation, or recommendation derivation.",
            "NOT_APPLICABLE is an issuer/business-model applicability boundary, not negative evidence; UNAVAILABLE/BLOCKED are coverage or authority limitations, not zero or weakness.",
        ],
    }
    if status == ABSENT:
        base.update({
            "financial_readiness": "UNAVAILABLE",
            "reason_codes": _copy_list(compact.get("reason_codes") or ["FA_V2_CONTEXT_ABSENT"]),
            "missing_dimensions": _copy_list(compact.get("missing_dimensions")),
            "warnings": _copy_list(compact.get("warnings")),
            "current_financial_weakness": [],
            "future_financial_invalidation_watch": [],
        })
        base["authority_notes"].append("ABSENT means the Producer did not supply Financial Analysis V2 for this ticker; it must never be narrated as weak financial evidence.")
        return base

    fitness = copy.deepcopy(dict(compact.get("feature_fitness") or {}))
    proxy_features = sorted(
        key for key, item in fitness.items()
        if isinstance(item, Mapping) and item.get("fitness") == "RESEARCH_PROXY"
    )
    annotation = _annotation(compact)
    base.update({
        "financial_readiness": "READY" if compact.get("current_research_ready") is True else "NOT_READY",
        "profitability": _state(compact.get("profitability") or compact.get("profitability_state")),
        "margin": _state(compact.get("margin") or compact.get("margin_state")),
        "growth": _state(compact.get("growth") or compact.get("growth_state"), fallback_basis=compact.get("growth_basis")),
        "cash_quality": _state(compact.get("cash_quality") or compact.get("cash_conversion_state")),
        "earnings_turnaround": _state(compact.get("earnings_turnaround") or compact.get("earnings_turnaround_state")),
        "balance_sheet": _state(compact.get("balance_sheet") or compact.get("balance_sheet_state")),
        "capital_efficiency": _state(compact.get("capital_efficiency") or compact.get("capital_efficiency_state")),
        "leverage": _state(compact.get("leverage") or compact.get("leverage_state")),
        "resilience": _state(compact.get("resilience") or compact.get("resilience_state")),
        "feature_fitness": fitness,
        "research_proxy_features": proxy_features,
        "strongest_supporting_evidence": _copy_list(compact.get("deterministic_positive_evidence")),
        "strongest_counter_thesis": _copy_list(compact.get("deterministic_negative_evidence")),
        "unresolved_conflicts": _copy_list(compact.get("unresolved_conflicts") or compact.get("conflicting_evidence")),
        "missing_dimensions": _copy_list(compact.get("missing_dimensions")),
        "warnings": _copy_list(compact.get("warnings")),
        "valuation_interpretation": copy.deepcopy(compact.get("valuation_interpretation") or compact.get("valuation_hints")),
        "current_financial_weakness": _copy_list(annotation.get("current_financial_weakness")),
        "future_financial_invalidation_watch": _copy_list(
            annotation.get("future_financial_invalidation_watch")
            or annotation.get("future_financial_invalidation_condition")
        ),
        "turnaround_context": annotation.get("turnaround_state"),
    })
    # ``null`` is meaningful here: preserve the Producer's missing/unsupported growth
    # basis rather than fabricating a generic period or an implied growth claim.
    if "growth_basis" in compact:
        base["growth"]["basis"] = copy.deepcopy(compact.get("growth_basis"))
    if proxy_features:
        base["authority_notes"].append(
            "RESEARCH_PROXY features are directional research context only; they are not authoritative financial facts, especially when cross-provider scale is unresolved."
        )
    return base


def compact_from_named_ticker(payload: Mapping[str, Any], ticker: str) -> Mapping[str, Any] | None:
    """Extract a compact record from an analysis bundle, session bundle, or direct record."""
    _require(isinstance(payload, Mapping), "FINANCIAL_ANALYSIS_PAYLOAD_NOT_OBJECT")
    if payload.get("contract_version") == COMPACT_CONTRACT_VERSION:
        _require(payload.get("ticker") == ticker, "FINANCIAL_ANALYSIS_TICKER_MISMATCH")
        return payload
    for container_key in ("tickers", "ticker_research_contexts"):
        entries = payload.get(container_key)
        entry = entries.get(ticker) if isinstance(entries, Mapping) else None
        if isinstance(entry, Mapping) and entry.get("financial_analysis") is not None:
            candidate = entry["financial_analysis"]
            _require(isinstance(candidate, Mapping), "FINANCIAL_ANALYSIS_COMPACT_NOT_OBJECT")
            # Security-decision cards retain the exact compact record under ``compact`` and
            # add only Producer-authored explanatory weakness/watch labels beside it.
            if isinstance(candidate.get("compact"), Mapping):
                compact = copy.deepcopy(dict(candidate["compact"]))
                compact["decision_financial_annotation"] = {
                    "current_financial_weakness": _copy_list(candidate.get("current_financial_weakness")),
                    "future_financial_invalidation_watch": _copy_list(
                        candidate.get("future_financial_invalidation_watch")
                        or candidate.get("future_financial_invalidation_condition")
                    ),
                    "turnaround_state": candidate.get("turnaround_state"),
                }
                return compact
            return candidate
    return None


def compact_from_ndjson(records: Iterable[Mapping[str, Any]], ticker: str) -> Mapping[str, Any] | None:
    """Extract a named ticker compact record from existing NDJSON-style records."""
    for record in records:
        if not isinstance(record, Mapping) or record.get("ticker") != ticker:
            continue
        candidate = record.get("financial_analysis")
        if candidate is not None:
            _require(isinstance(candidate, Mapping), "FINANCIAL_ANALYSIS_COMPACT_NOT_OBJECT")
            return candidate
    return None


def apply_bundle_financial_analysis_v2_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Attach the named compact projection to the ordinary per-ticker Consumer context."""
    if not isinstance(bundle, Mapping):
        return context
    ticker = str(context.get("ticker") or "")
    compact = compact_from_named_ticker(bundle, ticker)
    if compact is None:
        return context
    context["financial_analysis_consumer_context"] = build_financial_analysis_consumer_context(compact)
    context.setdefault("provenance", []).append({
        "source_file": "analysis_bundle.json",
        "source_dataset": "financial_analysis_compact/v1",
        "transformation": "Strict qualitative projection into financial_analysis_consumer_context/v1; no raw financial values, ratio recomputation, scoring, ranking, forecast, valuation, or recommendation derivation.",
        "limitations": [
            "Producer Financial Analysis V2 remains the sole authority for all states and source identities.",
            "RESEARCH_PROXY remains directional only; ABSENT, BLOCKED, UNAVAILABLE, and NOT_APPLICABLE remain explicit non-positive coverage/applicability states.",
        ],
    })
    return context
