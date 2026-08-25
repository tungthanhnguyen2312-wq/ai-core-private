"""Deterministic market-wide shadow parity gate: LEGACY_DIRECT vs PACKET_SHADOW.

This module answers one question over the official current research universe: for each
packet component that is genuinely expected to encode the same underlying Producer fact
as an already-integrated direct sibling, do the two transport paths agree, conflict, or
does only one of them carry usable data? It is promotion-readiness EVIDENCE, not a
promotion mechanism -- it never flips the production default away from LEGACY_DIRECT and
never emits an investment authority (probability, target, BUY/SELL/HOLD, sizing, ranking).

Design choice: this module does not re-derive packet-vs-sibling agreement/conflict itself.
structured_research_synthesis_boundary.accept_structured_research_synthesis(...,
packet_consumption_mode=PACKET_SHADOW) already computes that per-ticker comparison --
including the safety-critical fail-closed conflict detection and the scenario/
opportunity-priority semantic non-conflation rules -- and is covered by an extensive
existing test suite. Calling it with an empty ai_response={} deliberately produces a
"rejected" acceptance (the empty response fails structural validation), but
derived_contract_metadata (which carries packet_legacy_parity) is populated and returned
regardless of acceptance outcome, because the boundary derives it before it ever looks at
the AI response content. Reusing that single implementation -- rather than a second copy
of the comparison rule -- is what keeps this gate from becoming "another parallel
analyst-product abstraction."

The one real gap in the boundary's own per-component loop is intentional there but
incomplete for a market-wide audit: it never emits a value for a component whose packet
side is absent/malformed but whose direct sibling IS usable (it just omits the key,
since a single-ticker AI response never needs to enumerate what it cannot cite). This
module fills that symmetric gap (-> LEGACY_ONLY) and the "neither side usable" gap (->
UNRESOLVED) using the exact same usability formula the boundary already applies
elsewhere (isinstance(sibling, Mapping) and derived_meta.get(malformed_meta_key) !=
"malformed"), imported from the boundary rather than retyped, so there is exactly one
definition of "is this sibling usable" in the codebase.
"""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from builders.structured_research_synthesis_boundary import (
    PACKET_SHADOW,
    _PACKET_COMPONENT_NAMES,
    _PACKET_DIRECT_SIBLING_KEY,
    _PACKET_DIRECT_SIBLING_MALFORMED_META_KEY,
    accept_structured_research_synthesis,
)

CONTRACT_VERSION = "current_research_packet_shadow_parity/v1"

# The five classifications the milestone specifies as "established". Component-level
# values below are normalized into exactly this vocabulary (never the boundary's shorter
# unprefixed component-local spelling) so a reader never has to hold two vocabularies in
# their head at once.
PACKET_ONLY = "PACKET_ONLY"
LEGACY_ONLY = "LEGACY_ONLY"
DUAL_EQUIVALENT = "DUAL_EQUIVALENT"
DUAL_NONCOMPARABLE_SEMANTICS = "DUAL_NONCOMPARABLE_SEMANTICS"
DUAL_CONFLICT_FAIL_CLOSED = "DUAL_CONFLICT_FAIL_CLOSED"
# Two additional, narrower buckets a genuine market-wide sweep needs beyond the five
# per-ticker names above (both roll up into "malformed / local fail-closed" or
# "unresolved" at the report level -- see build_market_wide_parity_report):
IDENTITY_UNAVAILABLE_FAIL_CLOSED = "IDENTITY_UNAVAILABLE_FAIL_CLOSED"
UNRESOLVED_NO_USABLE_REPRESENTATION = "UNRESOLVED_NO_USABLE_REPRESENTATION"
MALFORMED_CONTEXT = "MALFORMED_CONTEXT"

# Maps the boundary's own component-local classification spelling onto this module's
# standardized vocabulary. Deliberately a closed map: an unrecognized value from the
# boundary must raise rather than silently pass through under a fabricated label.
_RAW_TO_STANDARD = {
    "PACKET_ONLY": PACKET_ONLY,
    "EQUIVALENT": DUAL_EQUIVALENT,
    "NONCOMPARABLE_SEMANTICS": DUAL_NONCOMPARABLE_SEMANTICS,
    "CONFLICT_FAIL_CLOSED": DUAL_CONFLICT_FAIL_CLOSED,
    "IDENTITY_UNAVAILABLE": IDENTITY_UNAVAILABLE_FAIL_CLOSED,
}

_DUAL_TICKER_STATUSES = {"DUAL_EQUIVALENT", "DUAL_NONCOMPARABLE_SEMANTICS", "DUAL_CONFLICT_FAIL_CLOSED"}


class CurrentResearchPacketShadowParityError(ValueError):
    pass


def _canon(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def content_identity(artifact: Mapping[str, Any]) -> dict[str, str]:
    payload = copy.deepcopy(dict(artifact))
    payload.pop("artifact_sha256", None)
    payload.pop("artifact_identity", None)
    digest = hashlib.sha256(_canon(payload)).hexdigest()
    return {"artifact_sha256": digest, "artifact_identity": "current_research_packet_shadow_parity:" + digest}


def _sibling_usable(ticker_context: Mapping[str, Any], meta: Mapping[str, Any], name: str) -> bool:
    """Exact reuse of the boundary's own "is this direct sibling citable" formula."""
    if name == "scenario":
        sibling = ticker_context.get("current_research_scenario_context")
        meta_key = "scenario_context_status"
    else:
        sibling = ticker_context.get(_PACKET_DIRECT_SIBLING_KEY[name])
        meta_key = _PACKET_DIRECT_SIBLING_MALFORMED_META_KEY[name]
    return isinstance(sibling, Mapping) and meta.get(meta_key) != "malformed"


def compute_ticker_parity(ticker_context: Mapping[str, Any]) -> dict[str, Any]:
    """Classify one ticker's packet-vs-legacy parity across all 7 packet components.

    Always evaluates as if packet_consumption_mode=PACKET_SHADOW, regardless of what the
    production default routes -- this is a diagnostic over what WOULD be citable under
    shadow mode, never a claim about what today's default LEGACY_DIRECT path serves.
    """
    ticker = ticker_context.get("ticker") if isinstance(ticker_context, Mapping) else None
    result = accept_structured_research_synthesis(ticker_context, {}, packet_consumption_mode=PACKET_SHADOW)
    meta = result.get("derived_contract_metadata") or {}

    if not meta:
        # ticker_context itself failed the boundary's basic shape checks (e.g. a sibling
        # key held a non-Mapping value) before any derivation could run at all -- nothing
        # about this ticker is safely classifiable, for any component.
        return {
            "ticker": ticker,
            "context_malformed": True,
            "packet_present": False,
            "legacy_present": False,
            "overall_status": MALFORMED_CONTEXT,
            "components": {name: MALFORMED_CONTEXT for name in _PACKET_COMPONENT_NAMES},
            "decision_context_parity": None,
            "opportunity_priority_metadata_parity": None,
            "reasons": list(result.get("reasons") or []),
        }

    packet_present = meta.get("current_research_decision_packet_status") == "available"
    component_local_status = (
        (meta.get("current_research_decision_packet_product_metadata") or {}).get("component_local_status") or {}
    )
    existing_components = (meta.get("packet_legacy_parity") or {}).get("components", {})

    components: dict[str, str] = {}
    legacy_present = False
    unreachable_both_usable: list[str] = []
    for name in _PACKET_COMPONENT_NAMES:
        sibling_usable = _sibling_usable(ticker_context, meta, name)
        legacy_present = legacy_present or sibling_usable

        if name in existing_components:
            raw = existing_components[name]
            if raw not in _RAW_TO_STANDARD:
                raise CurrentResearchPacketShadowParityError(f"UNRECOGNIZED_COMPONENT_CLASSIFICATION:{name}:{raw}")
            components[name] = _RAW_TO_STANDARD[raw]
            continue

        # The boundary always classifies a component once its packet side is usable, so
        # reaching here with a usable packet side would mean the two derivations
        # disagree about "usable" -- fail closed onto the same locally-unverifiable
        # label used for identity ambiguity, rather than silently asserting equivalence
        # or a one-sided count, and record it for the caller to audit (see
        # unreachable_both_usable_component_names below); this has never been observed
        # against retained data as of this milestone.
        packet_side_usable = component_local_status.get(name) not in (None, "UNRESOLVED", "malformed")
        if packet_side_usable and sibling_usable:
            components[name] = IDENTITY_UNAVAILABLE_FAIL_CLOSED
            unreachable_both_usable.append(name)
        elif sibling_usable:
            components[name] = LEGACY_ONLY
        elif packet_side_usable:
            components[name] = PACKET_ONLY
        else:
            components[name] = UNRESOLVED_NO_USABLE_REPRESENTATION

    decision_raw = existing_components.get("current_decision_context")
    opportunity_raw = existing_components.get("opportunity_priority_metadata")

    return {
        "ticker": ticker,
        "context_malformed": False,
        "packet_present": packet_present,
        "legacy_present": legacy_present,
        "overall_status": (meta.get("packet_legacy_parity") or {}).get("status"),
        "components": components,
        "decision_context_parity": _RAW_TO_STANDARD.get(decision_raw, decision_raw) if decision_raw else None,
        "opportunity_priority_metadata_parity": (
            _RAW_TO_STANDARD.get(opportunity_raw, opportunity_raw) if opportunity_raw else None
        ),
        "unreachable_both_usable_component_names": unreachable_both_usable,
        "reasons": [],
    }


_REPRESENTATIVE_CATEGORY_CAP = 3


def _add_representative(bucket: dict[str, list], category: str, ticker: str, detail: dict[str, Any]) -> None:
    examples = bucket.setdefault(category, [])
    if len(examples) < _REPRESENTATIVE_CATEGORY_CAP:
        examples.append({"ticker": ticker, **detail})


def _collect_representative_evidence(
    per_ticker: Mapping[str, dict[str, Any]], ticker_contexts: Mapping[str, Mapping[str, Any]]
) -> dict[str, list]:
    evidence: dict[str, list] = {name: [] for name in (
        "packet_only", "legacy_only", "dual_equivalent", "material_comparable_conflict",
        "noncomparable_scenario_coexistence", "noncomparable_prioritization_metadata",
        "malformed_component_with_unaffected_siblings", "blocked_valuation_preserved",
        "technical_coverage_gap_without_whole_ticker_invalidation", "authority_limitation_and_provenance_preservation",
    )}

    for ticker in sorted(per_ticker):
        row = per_ticker[ticker]
        components = row["components"]
        ctx = ticker_contexts.get(ticker) or {}

        for name, status in components.items():
            if status == PACKET_ONLY:
                _add_representative(evidence, "packet_only", ticker, {"component": name})
            elif status == LEGACY_ONLY:
                _add_representative(evidence, "legacy_only", ticker, {"component": name})
            elif status == DUAL_EQUIVALENT:
                _add_representative(evidence, "dual_equivalent", ticker, {"component": name})
            elif status == DUAL_CONFLICT_FAIL_CLOSED:
                _add_representative(evidence, "material_comparable_conflict", ticker, {"component": name})
            elif status == DUAL_NONCOMPARABLE_SEMANTICS and name == "scenario":
                _add_representative(
                    evidence, "noncomparable_scenario_coexistence", ticker,
                    {"component": name, "note": "packet current_evidence_bound_scenario (Bear/Base/Bull) vs direct "
                                                 "current_research_scenario_context (CONSERVATIVE/BASE/SPECULATIVE)"},
                )

        if row.get("opportunity_priority_metadata_parity") == DUAL_NONCOMPARABLE_SEMANTICS:
            _add_representative(
                evidence, "noncomparable_prioritization_metadata", ticker,
                {"note": "packet priority_tier/eligible_strategies vs daily_opportunity_decision_queue fields kept separate"},
            )

        # A mixed-status ticker (>=1 component locally unusable alongside >=1 component
        # still independently resolvable) is direct proof one bad component does not
        # invalidate its siblings -- exactly what
        # apply_bundle_current_research_decision_packet_contract's per-component
        # malformed-sentinel design guarantees structurally.
        degraded = {n for n, s in components.items() if s in (IDENTITY_UNAVAILABLE_FAIL_CLOSED, UNRESOLVED_NO_USABLE_REPRESENTATION)}
        resolvable = {n for n, s in components.items() if s in (PACKET_ONLY, LEGACY_ONLY, DUAL_EQUIVALENT, DUAL_CONFLICT_FAIL_CLOSED, DUAL_NONCOMPARABLE_SEMANTICS)}
        if degraded and resolvable:
            _add_representative(
                evidence, "malformed_component_with_unaffected_siblings", ticker,
                {"degraded_components": sorted(degraded), "unaffected_components": sorted(resolvable)},
            )

        valuation = ctx.get("market_wide_current_valuation")
        if isinstance(valuation, Mapping) and isinstance(valuation.get("metrics"), Mapping):
            blocked = sorted(
                m for m, v in valuation["metrics"].items() if isinstance(v, Mapping) and v.get("status") == "BLOCKED"
            )
            if blocked and "valuation" in components:
                _add_representative(
                    evidence, "blocked_valuation_preserved", ticker,
                    {"component": "valuation", "parity_status": components["valuation"], "blocked_metrics": blocked[:5]},
                )

        historical = ctx.get("market_wide_historical_research_context")
        historical_status = historical.get("context_status") if isinstance(historical, Mapping) else None
        market_sector = ctx.get("current_market_sector_leadership_context")
        sector_status = market_sector.get("status") if isinstance(market_sector, Mapping) else None
        gap_component, gap_status = (
            ("historical", historical_status) if historical_status not in (None, "AVAILABLE")
            else ("market_sector", sector_status) if sector_status == "data_limited" else (None, None)
        )
        # A real coverage gap (insufficient history / data-limited sector) whose ticker
        # still has other resolvable components proves the gap did not invalidate the
        # whole ticker's parity evaluation.
        if gap_component and (resolvable - {gap_component}):
            _add_representative(
                evidence, "technical_coverage_gap_without_whole_ticker_invalidation", ticker,
                {"component": gap_component, "coverage_status": gap_status, "other_resolvable_components": sorted(resolvable - {gap_component})},
            )

        packet_ctx = ctx.get("current_research_decision_packet")
        product_meta = None
        if isinstance(packet_ctx, Mapping):
            product_meta = packet_ctx.get("authority_boundary")
        if product_meta and not evidence["authority_limitation_and_provenance_preservation"]:
            _add_representative(
                evidence, "authority_limitation_and_provenance_preservation", ticker,
                {"authority_boundary": product_meta, "source_artifact_identity": packet_ctx.get("source_artifact_identity")},
            )

    return evidence


def _build_promotion_readiness(
    *, denominator: int, packet_present_count: int, legacy_present_count: int,
    totals: Mapping[str, int], component_breakdown: Mapping[str, Mapping[str, int]],
) -> dict[str, Any]:
    dual_total = sum(totals.get(k, 0) for k in _DUAL_TICKER_STATUSES)
    conflicts = totals.get(DUAL_CONFLICT_FAIL_CLOSED, 0)
    scenario_breakdown = component_breakdown.get("scenario", {})
    scenario_never_equated = (
        scenario_breakdown.get(DUAL_EQUIVALENT, 0) == 0 and scenario_breakdown.get(DUAL_CONFLICT_FAIL_CLOSED, 0) == 0
    )
    return {
        "schema_version": "1.0.0",
        "is_packet_shadow_transport_functioning_market_wide": {
            "answer": packet_present_count == denominator,
            "packet_present_count": packet_present_count,
            "denominator": denominator,
        },
        "are_comparable_representations_materially_equivalent": {
            "answer": (dual_total > 0) and (conflicts == 0),
            "dual_comparable_count": dual_total,
            "dual_equivalent_count": totals.get(DUAL_EQUIVALENT, 0),
            "dual_conflict_count": conflicts,
        },
        "are_conflicts_present": {"answer": conflicts > 0, "count": conflicts},
        "are_all_conflicts_explained_or_fail_closed": {
            "answer": True,
            "note": "DUAL_CONFLICT_FAIL_CLOSED is, by construction of this gate, always the fail-closed "
                    "disposition (see structured_research_synthesis_boundary's known_refs stripping on "
                    "packet_component_conflicts) -- a conflict is never left ambiguous or silently resolved.",
        },
        "are_noncomparable_semantic_families_kept_separate": {
            "answer": scenario_never_equated,
            "scenario_component_breakdown": dict(scenario_breakdown),
            "note": "current_evidence_bound_scenario (packet) and current_research_scenario_context (direct) "
                    "must never reach DUAL_EQUIVALENT or DUAL_CONFLICT_FAIL_CLOSED; only PACKET_ONLY, LEGACY_ONLY, "
                    "DUAL_NONCOMPARABLE_SEMANTICS, or unresolved/malformed are structurally reachable for it.",
        },
        "known_blockers_for_a_future_default_path_promotion": {
            "malformed_or_local_fail_closed_count": totals.get("malformed_or_local_fail_closed", 0),
            "unresolved_component_count": totals.get("unresolved_component", 0),
            "conflict_count": conflicts,
            "legacy_present_count": legacy_present_count,
            "denominator": denominator,
            "note": "A non-zero count in any field above is evidence to weigh, not a blocking gate this tool "
                    "enforces; owner review decides whether it is acceptable for promotion.",
        },
        "promotion_decision": "NOT_MADE_BY_THIS_GATE_OWNER_REVIEW_REQUIRED",
        "default_path_unchanged": "LEGACY_DIRECT",
    }


def build_market_wide_parity_report(ticker_contexts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Aggregate compute_ticker_parity across the supplied universe into one deterministic,
    content-identified artifact. ticker_contexts must be keyed by ticker, one fully-built
    (lightweight) ticker_context Mapping per ticker -- see
    load_market_wide_ticker_contexts_from_retained_artifacts for how the real 1,507-ticker
    universe is assembled from retained Producer artifacts.
    """
    tickers = sorted(ticker_contexts)
    per_ticker = {ticker: compute_ticker_parity(ticker_contexts[ticker]) for ticker in tickers}

    denominator = len(tickers)
    packet_present_count = sum(1 for row in per_ticker.values() if row["packet_present"])
    legacy_present_count = sum(1 for row in per_ticker.values() if row["legacy_present"])
    malformed_context_count = sum(1 for row in per_ticker.values() if row["context_malformed"])

    overall_status_counts = dict(Counter(row["overall_status"] for row in per_ticker.values()))

    component_breakdown: dict[str, dict[str, int]] = {name: {} for name in _PACKET_COMPONENT_NAMES}
    for row in per_ticker.values():
        for name, status in row["components"].items():
            component_breakdown[name][status] = component_breakdown[name].get(status, 0) + 1

    totals = {
        PACKET_ONLY: 0, LEGACY_ONLY: 0, DUAL_EQUIVALENT: 0,
        DUAL_NONCOMPARABLE_SEMANTICS: 0, DUAL_CONFLICT_FAIL_CLOSED: 0,
        "malformed_or_local_fail_closed": 0, "unresolved_component": 0,
    }
    for name in _PACKET_COMPONENT_NAMES:
        for status, count in component_breakdown[name].items():
            if status in (PACKET_ONLY, LEGACY_ONLY, DUAL_EQUIVALENT, DUAL_NONCOMPARABLE_SEMANTICS, DUAL_CONFLICT_FAIL_CLOSED):
                totals[status] += count
            elif status == IDENTITY_UNAVAILABLE_FAIL_CLOSED:
                totals["malformed_or_local_fail_closed"] += count
            elif status == UNRESOLVED_NO_USABLE_REPRESENTATION:
                totals["unresolved_component"] += count
            elif status == MALFORMED_CONTEXT:
                totals["malformed_or_local_fail_closed"] += count
            else:
                raise CurrentResearchPacketShadowParityError(f"UNRECOGNIZED_COMPONENT_STATUS:{name}:{status}")

    total_component_cells = denominator * len(_PACKET_COMPONENT_NAMES)
    accounted_cells = sum(totals.values())
    unexplained_residual_count = total_component_cells - accounted_cells

    opportunity_priority_counts = dict(Counter(
        row["opportunity_priority_metadata_parity"] for row in per_ticker.values()
        if row["opportunity_priority_metadata_parity"] is not None
    ))
    decision_context_counts = dict(Counter(
        row["decision_context_parity"] for row in per_ticker.values() if row["decision_context_parity"] is not None
    ))

    representative_evidence = _collect_representative_evidence(per_ticker, ticker_contexts)
    promotion_readiness = _build_promotion_readiness(
        denominator=denominator, packet_present_count=packet_present_count,
        legacy_present_count=legacy_present_count, totals=totals, component_breakdown=component_breakdown,
    )

    artifact: dict[str, Any] = {
        "schema_version": "1.0.0",
        "contract_version": CONTRACT_VERSION,
        "denominator": denominator,
        "packet_present_count": packet_present_count,
        "legacy_present_count": legacy_present_count,
        "malformed_context_count": malformed_context_count,
        "component_names": list(_PACKET_COMPONENT_NAMES),
        "component_breakdown": component_breakdown,
        "totals": totals,
        "unexplained_residual_count": unexplained_residual_count,
        "total_component_cells": total_component_cells,
        "overall_ticker_status_counts": overall_status_counts,
        "decision_context_parity_counts": decision_context_counts,
        "opportunity_priority_metadata_parity_counts": opportunity_priority_counts,
        "representative_evidence": representative_evidence,
        "promotion_readiness": promotion_readiness,
        "authority_boundary": {
            "is_actionable": False,
            "creates_no_recommendation_probability_expected_return_target_or_sizing": True,
            "does_not_perform_promotion_or_cutover": True,
            "default_path_unchanged": "LEGACY_DIRECT",
        },
        "tickers_evaluated": tickers,
    }
    artifact.update(content_identity(artifact))
    return artifact


def replay(artifact: Mapping[str, Any]) -> None:
    """Self-verification mirroring current_research_decision_packet.py's own replay()."""
    if artifact.get("contract_version") != CONTRACT_VERSION:
        raise CurrentResearchPacketShadowParityError("PARITY_CONTRACT_VERSION_MISMATCH")
    if content_identity(artifact).get("artifact_sha256") != artifact.get("artifact_sha256"):
        raise CurrentResearchPacketShadowParityError("PARITY_IDENTITY_MISMATCH")
    if artifact.get("denominator") != len(artifact.get("tickers_evaluated") or []):
        raise CurrentResearchPacketShadowParityError("PARITY_DENOMINATOR_MISMATCH")
    if artifact.get("unexplained_residual_count") != 0:
        raise CurrentResearchPacketShadowParityError("PARITY_UNEXPLAINED_RESIDUAL")
    totals = artifact.get("totals") or {}
    total_cells = artifact.get("total_component_cells")
    if sum(totals.values()) != total_cells:
        raise CurrentResearchPacketShadowParityError("PARITY_TOTALS_DO_NOT_RECONCILE_TO_CELL_COUNT")
    scenario_breakdown = (artifact.get("component_breakdown") or {}).get("scenario", {})
    if scenario_breakdown.get(DUAL_EQUIVALENT, 0) != 0 or scenario_breakdown.get(DUAL_CONFLICT_FAIL_CLOSED, 0) != 0:
        raise CurrentResearchPacketShadowParityError("PARITY_SCENARIO_FAMILIES_WERE_EQUATED")


# --- Real-data loader: assembles the official 1,507-ticker universe from retained,
# already-committed Producer artifacts. No network acquisition; Producer read-only. ---

_PRODUCER_ATTACH_ARTIFACTS = (
    # (attach_function_name, artifact_relative_path)
    ("attach_watchlist_tactical_entry_classifier",
     "watchlist-tactical-entry-decision-v1-20260823/watchlist_tactical_entry_classifier_artifact.json"),
    ("attach_market_wide_historical_research_context",
     "market-wide-historical-research-context-v1-20260824/market_wide_historical_research_context_artifact.json"),
    ("attach_market_wide_current_valuation",
     "market-wide-current-valuation-research-scaleout-v1/market_wide_current_valuation_artifact.json"),
    ("attach_current_market_sector_leadership_context",
     "current-market-sector-leadership-context-v1-20260825/current_market_sector_leadership_context_artifact.json"),
    ("attach_current_financial_momentum_context",
     "current-financial-momentum-context-v1/current_financial_momentum_context_artifact.json"),
    ("attach_current_corporate_event_context",
     "current-corporate-event-context-v1/current_corporate_event_context_artifact.json"),
    ("attach_current_research_risk_register",
     "current-research-risk-register-v1/current_research_risk_register_artifact.json"),
    ("attach_current_research_scenario_context",
     "current-research-scenario-framework-v1/current_research_scenario_context_artifact.json"),
    ("attach_current_research_decision_packet",
     "current-research-decision-packet-v1/current_research_decision_packet_artifact.json"),
)
_DAILY_OPPORTUNITY_DECISION_QUEUE_ARTIFACT = (
    "daily-opportunity-decision-queue-v1-20260824/daily_opportunity_decision_queue_artifact.json"
)
_PACKET_ARTIFACT_RELATIVE_PATH = "current-research-decision-packet-v1/current_research_decision_packet_artifact.json"

_CONSUMER_APPLY_CONTRACTS = (
    "apply_bundle_watchlist_tactical_entry_classifier_contract",
    "apply_bundle_current_opportunity_decision_context_contract",
    "apply_bundle_market_wide_historical_research_context_contract",
    "apply_bundle_market_wide_current_valuation_contract",
    "apply_bundle_current_market_sector_leadership_context_contract",
    "apply_bundle_current_financial_momentum_context_contract",
    "apply_bundle_current_corporate_event_context_contract",
    "apply_bundle_current_research_risk_register_contract",
    "apply_bundle_current_research_scenario_context_contract",
    "apply_bundle_current_research_decision_packet_contract",
)


def load_market_wide_ticker_contexts_from_retained_artifacts(
    producer_root: Path, *, tickers: list[str] | None = None,
) -> dict[str, dict[str, Any]]:
    """Build lightweight ticker_context dicts for the real official research universe.

    Mirrors the established frozen-time E2E convention exactly (e.g.
    test_market_wide_current_descriptive_research_frozen_time_e2e.py): imports Producer's
    already-committed export_ai_bundle.py read-only, attaches each retained sibling
    artifact via its own content-hash-gated attach_* function, then runs every ticker
    through this repository's own apply_bundle_*_contract functions -- offline,
    single-threaded, no DNSE/network reacquisition, no runtime or production write.

    The universe defaults to the retained packet artifact's own 1,507 ticker keys (the
    packet is itself built from current_opportunity_prioritization/v1, the official
    current research universe) rather than a second, independently-sourced ticker list.
    """
    operations_review = producer_root / "operations-review"
    packet_path = operations_review / _PACKET_ARTIFACT_RELATIVE_PATH
    packet_artifact = json.loads(packet_path.read_text(encoding="utf-8"))
    universe = tickers if tickers is not None else sorted(packet_artifact.get("records") or {})

    if str(producer_root) not in sys.path:
        sys.path.insert(0, str(producer_root))
    import export_ai_bundle  # noqa: E402  (Producer module, imported read-only)

    from builders import build_ticker_context as consumer

    entries: dict[str, dict[str, Any]] = {ticker: {"ticker": ticker} for ticker in universe}
    for attach_name, relative_path in _PRODUCER_ATTACH_ARTIFACTS:
        attach_fn = getattr(export_ai_bundle, attach_name)
        attach_fn(entries, include=True, artifact_path=str(operations_review / relative_path))

    queue_path = operations_review / _DAILY_OPPORTUNITY_DECISION_QUEUE_ARTIFACT
    daily_queue = json.loads(queue_path.read_text(encoding="utf-8"))
    bundle: dict[str, Any] = {"tickers": entries, "daily_opportunity_decision_queue": daily_queue}

    ticker_contexts: dict[str, dict[str, Any]] = {}
    for ticker in universe:
        ctx: dict[str, Any] = {"ticker": ticker, "provenance": []}
        for apply_name in _CONSUMER_APPLY_CONTRACTS:
            getattr(consumer, apply_name)(ctx, bundle)
        ticker_contexts[ticker] = ctx
    return ticker_contexts
