"""Consumer pass-through for the Producer's KBS trading-value coverage verdict.

WHAT THIS IS FOR
    Producer decides whether a KBS trading-value figure covers the interval it appears to
    describe. Consumer's job is to carry that decision intact and refuse to improve on it.
    So this module validates and passes through; it does not classify, does not recompute a
    count, and does not hold a copy of Producer's capability matrix.

    The distinction matters because the two repositories fail differently. A Consumer that
    re-derives coverage will eventually disagree with Producer, and the disagreement will
    surface as a number that looks fine. A Consumer that only checks and forwards can be
    wrong in exactly one way -- it can drop something -- and that is what the required-field
    list catches.

THE ONE ASYMMETRY
    Coverage may be narrowed here and never widened. Narrowing is safe: a Consumer that
    knows less than Producer should say so. Widening invents evidence.

NOTE ON THE CURRENT STATE
    No Producer artifact carries this block today -- Producer's trace found that KBS ``va``
    is dropped by the upstream adapter and never reaches the bundle. This contract is the
    receiving half of a seam, and its live behaviour today is the legacy path: a payload
    with no coverage block resolves to ``unknown`` and refuses aggregate claims.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

CONTRACT_VERSION = "1.0.0"

PROVIDER = "KBS"
SOURCE_FIELD = "va"

# --- Coverage vocabulary, pinned to Producer ---------------------------------------

COVERAGE_COMPLETE = "complete"
COVERAGE_PARTIAL_KNOWN = "partial_known"
COVERAGE_ABSENT = "absent"
COVERAGE_CONFLICTED = "conflicted"
COVERAGE_UNKNOWN = "unknown"

COVERAGE_STATES = (
    COVERAGE_COMPLETE,
    COVERAGE_PARTIAL_KNOWN,
    COVERAGE_ABSENT,
    COVERAGE_CONFLICTED,
    COVERAGE_UNKNOWN,
)

SCOPE_SINGLE_ROW = "single_observed_row"
SCOPE_COMPLETE_WINDOW = "complete_requested_window"
SCOPE_OBSERVED_ROWS_ONLY = "observed_rows_only"
SCOPE_NOT_APPLICABLE = "not_applicable"

STATISTIC_SCOPES = (
    SCOPE_SINGLE_ROW,
    SCOPE_COMPLETE_WINDOW,
    SCOPE_OBSERVED_ROWS_ONLY,
    SCOPE_NOT_APPLICABLE,
)

#: Coverage ordering, for the narrow-never-widen check. ``conflicted`` and ``unknown`` sit
#: at the bottom together: both mean "you may not aggregate on this".
_COVERAGE_RANK = {
    COVERAGE_UNKNOWN: 0,
    COVERAGE_CONFLICTED: 0,
    COVERAGE_ABSENT: 1,
    COVERAGE_PARTIAL_KNOWN: 2,
    COVERAGE_COMPLETE: 3,
}

#: Every coverage field Producer emits. Consumer must preserve all of them; a loader that
#: keeps only the fields it currently reads is how a warning quietly disappears.
REQUIRED_COVERAGE_FIELDS: tuple[str, ...] = (
    "coverage_state",
    "requested_session_count",
    "returned_row_count",
    "present_numeric_count",
    "present_zero_count",
    "present_null_count",
    "field_omitted_count",
    "malformed_count",
    "row_missing_count",
    "usable_count",
    "coverage_ratio",
    "covered_sessions",
    "missing_sessions",
    "excluded_sessions",
    "statistic_scope",
    "partial_coverage_warning",
    "coverage_generalization",
    "causal_explanation",
    "automatic_imputation_authorized",
    "missing_as_zero_authorized",
)

REQUIRED_BLOCK_FIELDS: tuple[str, ...] = (
    "export_block_version",
    "provider",
    "source_field",
    "source_field_identity",
    "trading_value_unit",
    "trading_value_unit_qualification",
    "coverage",
    "warning_tokens",
    "warnings",
)

# --- Canonical warning tokens, pinned to Producer -----------------------------------

TOKEN_PARTIAL_COVERAGE = "kbs_trading_value_partial_coverage"
TOKEN_PROVIDER_AUTHORITY = "kbs_trading_value_provider_authority"

#: A frozen copy of Producer's canonical table. Consumer does not compose these sentences;
#: it repeats them. ``assert_warnings_pinned`` compares the fingerprint against the shared
#: fixture, so a Producer edit that is not mirrored here fails a test rather than shipping
#: two different warnings for the same condition.
CANONICAL_WARNINGS: dict[str, str] = {
    TOKEN_PARTIAL_COVERAGE: (
        "KBS trading-value coverage is partial for the requested interval. "
        "Statistics are computed from observed rows only. "
        "Missing sessions were not imputed or treated as zero. "
        "The result is provider-scoped and is not official market turnover "
        "or qualified liquidity evidence."
    ),
    TOKEN_PROVIDER_AUTHORITY: (
        "This is a KBS provider observation with empirically deduced units. "
        "It is not an official exchange trading-value contract."
    ),
}

#: Aggregate claims a Consumer may never make from a KBS trading value, whatever the
#: coverage. Kept short and specific rather than mirroring Producer's whole matrix.
BLOCKED_AGGREGATE_CLAIMS: tuple[str, ...] = (
    "period_total_trading_value",
    "complete_window_mean",
    "trading_value_growth",
    "turnover_for_period",
    "official_vwap_claim",
    "official_market_turnover",
    "trading_value_liquidity_metric",
    "trading_value_capacity_metric",
    "cross_ticker_trading_value_ranking",
)

LEGACY_ROW_OBSERVATION = "legacy_row_observation"
LEGACY_AGGREGATE_WITHOUT_COVERAGE = "legacy_aggregate_without_coverage"
LEGACY_NO_TRADING_VALUE = "legacy_no_trading_value"


class TradingValueCoverageContractError(ValueError):
    """Fail-closed rejection in the Consumer trading-value coverage pass-through."""


def warnings_fingerprint() -> str:
    payload = json.dumps(CANONICAL_WARNINGS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def assert_warnings_pinned(producer_fingerprint: str) -> None:
    """Fail when Producer's warning text has moved and this copy has not."""
    if producer_fingerprint != warnings_fingerprint():
        raise TradingValueCoverageContractError(
            "canonical_warning_text_drifted_between_producer_and_consumer"
        )


def normalize_trading_value_contract(block: Mapping[str, Any] | None) -> dict[str, Any]:
    """Read a Producer coverage block, or fail closed with an explicit unknown.

    The ``None`` branch is the one that runs today, and it is deliberately not an error:
    a bundle without the block is a legacy bundle, not a broken one. It simply cannot
    support an aggregate.
    """
    if not isinstance(block, Mapping) or not block:
        return {
            "contract_version": CONTRACT_VERSION,
            "present": False,
            "provider": PROVIDER,
            "coverage_state": COVERAGE_UNKNOWN,
            "statistic_scope": SCOPE_NOT_APPLICABLE,
            "aggregate_claims_allowed": False,
            "row_display_allowed": False,
            "reason": "no_producer_coverage_block",
            "warning_tokens": [TOKEN_PROVIDER_AUTHORITY],
            "warnings": [CANONICAL_WARNINGS[TOKEN_PROVIDER_AUTHORITY]],
        }

    missing = [field for field in REQUIRED_BLOCK_FIELDS if field not in block]
    if missing:
        raise TradingValueCoverageContractError(
            f"producer_coverage_block_incomplete:{','.join(sorted(missing))}"
        )
    if block.get("provider") != PROVIDER:
        raise TradingValueCoverageContractError(
            f"coverage_block_is_not_kbs:{block.get('provider')}"
        )
    if block.get("source_field") != SOURCE_FIELD:
        raise TradingValueCoverageContractError("coverage_block_source_field_must_be_va")

    coverage = block["coverage"]
    absent = [field for field in REQUIRED_COVERAGE_FIELDS if field not in coverage]
    if absent:
        raise TradingValueCoverageContractError(
            f"coverage_fields_dropped_in_transit:{','.join(sorted(absent))}"
        )
    assert_labels_agree_with_counts(coverage)

    state = str(coverage["coverage_state"])
    scope = str(coverage["statistic_scope"])
    tokens = list(block.get("warning_tokens") or [])
    if TOKEN_PROVIDER_AUTHORITY not in tokens:
        raise TradingValueCoverageContractError("provider_authority_warning_missing")
    if state == COVERAGE_PARTIAL_KNOWN and TOKEN_PARTIAL_COVERAGE not in tokens:
        raise TradingValueCoverageContractError("partial_coverage_warning_missing")

    return {
        "contract_version": CONTRACT_VERSION,
        "present": True,
        "provider": PROVIDER,
        "source_field": SOURCE_FIELD,
        "trading_value_unit": block["trading_value_unit"],
        "trading_value_unit_qualification": block["trading_value_unit_qualification"],
        "coverage_state": state,
        "statistic_scope": scope,
        # Producer's counts are copied verbatim. Consumer recomputes nothing.
        "coverage": {field: coverage[field] for field in REQUIRED_COVERAGE_FIELDS},
        "aggregate_claims_allowed": state == COVERAGE_COMPLETE
        and scope == SCOPE_COMPLETE_WINDOW,
        "row_display_allowed": True,
        "not_comparable_to_complete_period_total": bool(
            block.get("not_comparable_to_complete_period_total")
        ),
        "warning_tokens": tokens,
        "warnings": list(block.get("warnings") or []),
    }


def assert_labels_agree_with_counts(coverage: Mapping[str, Any]) -> None:
    """Validate Producer's label against Producer's own numbers.

    Not a recomputation -- it compares two things Producer already sent. A block whose state
    contradicts its counts was corrupted somewhere between the two repositories, and the
    safe response is to refuse it rather than to trust whichever field looks friendlier.
    """
    state = coverage.get("coverage_state")
    if state not in COVERAGE_STATES:
        raise TradingValueCoverageContractError(f"coverage_state_invalid:{state}")
    if coverage.get("statistic_scope") not in STATISTIC_SCOPES:
        raise TradingValueCoverageContractError(
            f"statistic_scope_invalid:{coverage.get('statistic_scope')}"
        )
    usable = coverage.get("usable_count")
    requested = coverage.get("requested_session_count")
    if isinstance(usable, int) and isinstance(requested, int):
        if state == COVERAGE_COMPLETE and usable < requested:
            raise TradingValueCoverageContractError(
                f"coverage_label_contradicts_counts:complete_but_{usable}_of_{requested}"
            )
        if state == COVERAGE_ABSENT and usable:
            raise TradingValueCoverageContractError("absent_coverage_reports_usable_rows")
        if usable > requested:
            raise TradingValueCoverageContractError("usable_exceeds_requested")
    if state != COVERAGE_COMPLETE and coverage.get("statistic_scope") == SCOPE_COMPLETE_WINDOW:
        raise TradingValueCoverageContractError(
            "only_complete_coverage_may_claim_the_requested_window"
        )
    if coverage.get("automatic_imputation_authorized") or coverage.get("missing_as_zero_authorized"):
        raise TradingValueCoverageContractError("consumer_must_not_accept_authorized_imputation")


def assert_not_upgraded(
    *, producer: Mapping[str, Any], consumer: Mapping[str, Any]
) -> None:
    """Coverage may be narrowed downstream, never widened."""
    produced = _COVERAGE_RANK.get(str(producer.get("coverage_state")), 0)
    consumed = _COVERAGE_RANK.get(str(consumer.get("coverage_state")), 0)
    if consumed > produced:
        raise TradingValueCoverageContractError(
            f"consumer_upgraded_coverage:"
            f"{producer.get('coverage_state')}->{consumer.get('coverage_state')}"
        )
    produced_usable = (producer.get("coverage") or {}).get("usable_count")
    consumed_usable = (consumer.get("coverage") or {}).get("usable_count")
    if isinstance(produced_usable, int) and isinstance(consumed_usable, int):
        if consumed_usable > produced_usable:
            raise TradingValueCoverageContractError("consumer_reported_more_covered_sessions")


def assert_warnings_preserved(contract: Mapping[str, Any]) -> None:
    """A downstream context may add warnings. It may not drop the required ones."""
    tokens = list(contract.get("warning_tokens") or [])
    if TOKEN_PROVIDER_AUTHORITY not in tokens:
        raise TradingValueCoverageContractError("provider_authority_warning_removed")
    if contract.get("coverage_state") == COVERAGE_PARTIAL_KNOWN:
        if TOKEN_PARTIAL_COVERAGE not in tokens:
            raise TradingValueCoverageContractError("partial_coverage_warning_removed")
        if not contract.get("not_comparable_to_complete_period_total"):
            raise TradingValueCoverageContractError("partial_incomparability_flag_removed")


def evaluate_aggregate_claim(contract: Mapping[str, Any], *, claim: str) -> dict[str, Any]:
    """Decide one aggregate claim against a passed-through verdict."""
    if claim in BLOCKED_AGGREGATE_CLAIMS and claim != "period_total_trading_value":
        return {"claim": claim, "allowed": False,
                "reason": "claim_unavailable_by_producer_contract"}
    if not contract.get("aggregate_claims_allowed"):
        return {
            "claim": claim,
            "allowed": False,
            "reason": "coverage_is_not_complete_for_the_requested_window",
            "coverage_state": contract.get("coverage_state"),
        }
    return {"claim": claim, "allowed": True, "coverage_state": contract.get("coverage_state")}


def classify_legacy_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Classify a bundle payload written before the coverage block existed.

    Absence of metadata never defaults to complete. A legacy bundle has not told us its
    coverage is full; it has told us nothing.
    """
    if isinstance(payload.get("kbs_trading_value"), Mapping):
        return {"legacy": False, "legacy_class": None}
    has_value = any(
        payload.get(key) is not None
        for key in ("trading_value", "trading_value_value", "va",
                    "kbs.observed_daily_trading_value")
    )
    if not has_value:
        return {"legacy": True, "legacy_class": LEGACY_NO_TRADING_VALUE,
                "coverage_state": COVERAGE_UNKNOWN, "unaffected": True}
    if str(payload.get("session_date") or payload.get("date") or "").strip():
        return {
            "legacy": True,
            "legacy_class": LEGACY_ROW_OBSERVATION,
            "coverage_state": COVERAGE_UNKNOWN,
            "row_display_allowed": True,
            "aggregate_claims_allowed": False,
            "warning_tokens": [TOKEN_PROVIDER_AUTHORITY],
        }
    return {
        "legacy": True,
        "legacy_class": LEGACY_AGGREGATE_WITHOUT_COVERAGE,
        "coverage_state": COVERAGE_UNKNOWN,
        "row_display_allowed": False,
        "aggregate_claims_allowed": False,
    }


def ai_context_block(contract: Mapping[str, Any]) -> dict[str, Any]:
    """What an AI context may say about a KBS trading value.

    The label is the point. ``provider_observation`` and ``official_market_turnover`` are
    different claims, and the second is never available from this source at any coverage.
    """
    assert_warnings_preserved(contract)
    state = contract.get("coverage_state")
    return {
        "provider": PROVIDER,
        "field_label": "kbs_provider_observed_trading_value",
        "is_official_market_turnover": False,
        "is_qualified_liquidity_evidence": False,
        "supports_market_scope_claim": False,
        "supports_actionability": False,
        "coverage_state": state,
        "statistic_scope": contract.get("statistic_scope"),
        "warning_tokens": list(contract.get("warning_tokens") or []),
        "warnings": [CANONICAL_WARNINGS[token] for token in contract.get("warning_tokens") or []],
        "aggregate_claims_allowed": bool(contract.get("aggregate_claims_allowed")),
    }
