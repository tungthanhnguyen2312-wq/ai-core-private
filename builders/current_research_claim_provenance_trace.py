"""Deterministic, read-only provenance traces for current research claims.

This product deliberately consumes the existing structured-research acceptance boundary.
It does not validate evidence references itself, recompute current research, or turn a
trace into a decision input.  A structured synthesis currently has package-wide
``provenance_references`` rather than per-field references; callers can optionally
provide a claim-evidence map when they have an already structured claim-level link.  In
the former case the trace says so explicitly instead of pretending an exact linkage.
"""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Iterable, Mapping

from builders.structured_research_synthesis_boundary import (
    LEGACY_DIRECT,
    PACKET_SHADOW,
    accept_structured_research_synthesis,
)

SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "current_research_claim_provenance_trace/v1"

SUPPORTED = "SUPPORTED"
SUPPORTED_WITH_LIMITATION = "SUPPORTED_WITH_LIMITATION"
UNRESOLVED = "UNRESOLVED"
UNSUPPORTED_REFERENCE = "UNSUPPORTED_REFERENCE"
COMPONENT_UNAVAILABLE = "COMPONENT_UNAVAILABLE"
CONFLICT_FAIL_CLOSED = "CONFLICT_FAIL_CLOSED"
MALFORMED = "MALFORMED"
AUTHORITY_BLOCKED = "AUTHORITY_BLOCKED"
_TRACE_STATUSES = {
    SUPPORTED, SUPPORTED_WITH_LIMITATION, UNRESOLVED, UNSUPPORTED_REFERENCE,
    COMPONENT_UNAVAILABLE, CONFLICT_FAIL_CLOSED, MALFORMED, AUTHORITY_BLOCKED,
}

_CLAIM_FIELDS = (
    "thesis", "supporting_evidence", "counter_thesis", "counter_evidence",
    "historical_context_summary", "valuation_context_summary", "market_context_summary",
    "sector_context_summary", "relative_strength_context", "catalyst_context",
    "risk_context", "invalidation_conditions", "unresolved_questions",
    "authority_limitations",
)
_DIRECT_TO_PACKET = {
    "current_research_risk_register": "risk_register",
    "current_market_sector_leadership_context": "market_sector",
    "current_financial_momentum_context": "financial_momentum",
    "current_corporate_event_context": "corporate_event",
    "market_wide_current_valuation": "valuation",
    "market_wide_historical_research_context": "historical",
}
_PACKET_TO_DIRECT = {value: key for key, value in _DIRECT_TO_PACKET.items()}
_PACKET_COMPONENT_KEY = {
    "scenario": "scenario_context", "risk_register": "risk_register",
    "market_sector": "market_sector_context", "financial_momentum": "financial_momentum_context",
    "corporate_event": "corporate_event_context", "valuation": "valuation_context",
    "historical": "historical_research_context",
}
_TEMPORAL_KEYS = {
    "analysis_session", "session", "research_session", "source_session", "source_as_of",
    "as_of", "as_of_session", "as_of_financial_period", "valuation_session", "price_session",
    "knowledge_available_at", "known_at", "published_at", "reporting_period", "period",
    "periods",
    "record_date", "ex_date", "effective_date", "execution_date", "announcement_date",
}
_LIMITATION_KEYS = {
    "authority_limitations", "authority_boundary", "prohibited_uses", "blocked_reasons",
    "reason_codes", "warnings", "limitations", "allowed_uses", "status", "context_status",
    "event_status", "temporal_completeness", "probability_status", "share_basis_status",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _parse_response(response: str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(response, Mapping):
        return response
    if isinstance(response, str):
        try:
            candidate = json.loads(response)
        except json.JSONDecodeError:
            return {}
        return candidate if isinstance(candidate, Mapping) else {}
    return {}


def _walk(value: Any, path: Iterable[str]) -> Any:
    current = value
    for part in path:
        if isinstance(current, list):
            current = next(
                (
                    row for row in current
                    if isinstance(row, Mapping)
                    and part in {row.get("event_id"), row.get("risk_id"), row.get("condition_id")}
                ),
                None,
            )
            continue
        if not isinstance(current, Mapping):
            return None
        current = current.get(part)
    return current


def _root(ref: str) -> str:
    return ref.split(".", 1)[0]


def _packet_component(ref: str) -> str | None:
    parts = ref.split(".")
    if len(parts) >= 2 and parts[0] == "current_research_decision_packet":
        return parts[1]
    if parts[0] == "current_research_scenario_context":
        return "scenario"
    return _DIRECT_TO_PACKET.get(parts[0])


def _resolve_reference(context: Mapping[str, Any], ref: str) -> Any:
    """Resolve only the small referenced node; never duplicate a whole source artifact."""
    parts = ref.split(".")
    if not parts:
        return None
    root = parts[0]
    tail = parts[1:]
    if root == "current_research_decision_packet":
        if not tail:
            return context.get(root)
        component = tail[0]
        key = _PACKET_COMPONENT_KEY.get(component)
        packet = _walk(context, (root, "packet", "components", key)) if key else None
        return _walk(packet, tail[1:]) if tail[1:] else packet
    source = context.get(root)
    if not tail:
        return source
    # These direct contracts keep their citable rows below a named body, unlike their
    # flat evidence-ref spelling.  This mirrors the accepted boundary's derivation.
    inserted: tuple[str, ...] = ()
    if root == "current_financial_momentum_context" and tail[0] == "components":
        inserted = ("ticker_context",)
    elif root == "current_corporate_event_context" and tail[0] == "events":
        inserted = ("ticker_context",)
    elif root == "current_research_risk_register" and tail[0] in {
        "material_risks", "watch_risks", "data_authority_limitations", "unresolved_conflicts",
    }:
        inserted = ("risk_register",)
    elif root == "current_research_scenario_context" and len(tail) >= 3:
        inserted, tail = ("scenario_context", "axes"), tail
    return _walk(source, inserted + tuple(tail))


def _collect_named(value: Any, keys: set[str], *, limit: int = 24) -> dict[str, list[Any]]:
    collected: dict[str, list[Any]] = {}
    def visit(item: Any) -> None:
        if sum(len(values) for values in collected.values()) >= limit:
            return
        if isinstance(item, Mapping):
            for key in sorted(item):
                child = item[key]
                if key in keys and isinstance(child, (str, int, float, bool, type(None), list, Mapping)):
                    collected.setdefault(key, []).append(copy.deepcopy(child))
                if isinstance(child, (Mapping, list)):
                    visit(child)
        elif isinstance(item, list):
            for child in item:
                visit(child)
    visit(value)
    return {key: values for key, values in sorted(collected.items())}


def _artifact_identity(context: Mapping[str, Any], ref: str, payload: Any) -> str | None:
    root = _root(ref)
    if root == "current_research_decision_packet":
        component = _packet_component(ref)
        entry = _walk(context, (root, "component_manifest", component))
        if isinstance(entry, Mapping) and isinstance(entry.get("source_artifact_identity"), str):
            return entry["source_artifact_identity"]
    source = context.get(root)
    if isinstance(source, Mapping) and isinstance(source.get("source_artifact_identity"), str):
        return source["source_artifact_identity"]
    if isinstance(payload, Mapping) and isinstance(payload.get("source_artifact_identity"), str):
        return payload["source_artifact_identity"]
    return None


def _transports(context: Mapping[str, Any], ref: str, metadata: Mapping[str, Any]) -> tuple[list[str], str]:
    component = _packet_component(ref)
    root = _root(ref)
    if component == "scenario":
        if root == "current_research_decision_packet" and isinstance(context.get("current_research_scenario_context"), Mapping):
            return ["packet"], "SEPARATE_NONCOMPARABLE_SCENARIO_CONTRACT"
        if root == "current_research_scenario_context" and isinstance(context.get("current_research_decision_packet"), Mapping):
            return ["direct"], "SEPARATE_NONCOMPARABLE_SCENARIO_CONTRACT"
    if component is None:
        return (["packet"] if root == "current_research_decision_packet" else ["direct"], "SINGLE_TRANSPORT")
    direct_root = _PACKET_TO_DIRECT.get(component)
    packet = context.get("current_research_decision_packet")
    packet_identity = _artifact_identity(context, f"current_research_decision_packet.{component}", None)
    direct_identity = _artifact_identity(context, direct_root or "", None) if direct_root else None
    conflicts = set(metadata.get("current_research_decision_packet_component_conflicts") or [])
    if component in conflicts:
        return ["direct", "packet"], "CONFLICT_FAIL_CLOSED"
    if (direct_root and isinstance(context.get(direct_root), Mapping) and isinstance(packet, Mapping)
            and metadata.get("current_research_decision_packet_status") == "available"):
        if packet_identity and direct_identity and packet_identity == direct_identity:
            return ["direct", "packet"], "DEDUPLICATED_SAME_LOGICAL_EVIDENCE"
    return (["packet"] if root == "current_research_decision_packet" else ["direct"], "SINGLE_TRANSPORT")


def _status_for_ref(
    context: Mapping[str, Any], ref: str, known_refs: set[str], metadata: Mapping[str, Any],
) -> tuple[str, list[str]]:
    component = _packet_component(ref)
    conflicts = set(metadata.get("current_research_decision_packet_component_conflicts") or [])
    if component in conflicts:
        return CONFLICT_FAIL_CLOSED, ["packet_direct_component_conflict_fail_closed"]
    if ref not in known_refs:
        root_value = context.get(_root(ref))
        if isinstance(root_value, Mapping) and root_value.get("status") == "malformed":
            return MALFORMED, ["referenced_component_malformed"]
        if root_value is None:
            if _root(ref).startswith(("current_", "market_wide_", "watchlist_", "daily_")):
                return COMPONENT_UNAVAILABLE, ["referenced_component_unavailable"]
            return UNSUPPORTED_REFERENCE, ["unknown_or_unallowed_evidence_reference"]
        return UNSUPPORTED_REFERENCE, ["unknown_or_unallowed_evidence_reference"]
    payload = _resolve_reference(context, ref)
    if isinstance(payload, Mapping) and str(payload.get("status", "")).upper() == "BLOCKED":
        return AUTHORITY_BLOCKED, ["referenced_state_blocked"]
    if isinstance(payload, Mapping) and isinstance(payload.get("metrics"), Mapping):
        metric_statuses = [str(row.get("status")) for row in payload["metrics"].values() if isinstance(row, Mapping)]
        if metric_statuses and all(status == "BLOCKED" for status in metric_statuses):
            return AUTHORITY_BLOCKED, ["valuation_metrics_blocked"]
    reasons: list[str] = []
    if isinstance(payload, Mapping):
        boundary = payload.get("authority_boundary")
        if isinstance(boundary, Mapping) and (boundary.get("PIT") == "BLOCKED" or boundary.get("RAW_AS_TRADED") == "NOT_PROMOTED"):
            reasons.append("historical_adjusted_retrospective_not_pit_or_raw_as_traded")
        if payload.get("event_status") in {"PLANNED", "APPROVED", "CONFIRMED_UPCOMING"}:
            reasons.append("event_status_does_not_prove_execution")
        if payload.get("risk_register_status") == "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE":
            reasons.append("no_material_risk_established_is_not_low_risk")
        register = payload.get("risk_register")
        if isinstance(register, Mapping) and register.get("risk_register_status") == "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE":
            reasons.append("no_material_risk_established_is_not_low_risk")
        if payload.get("probability_status") == "UNKNOWN_UNCALIBRATED":
            reasons.append("scenario_case_is_not_probability_authority")
    return (SUPPORTED_WITH_LIMITATION if reasons else SUPPORTED), reasons


def _claim_rows(response: Mapping[str, Any]) -> list[tuple[str, str, str, Any]]:
    rows: list[tuple[str, str, str, Any]] = []
    for field in _CLAIM_FIELDS:
        value = response.get(field)
        claim_type = field.replace("_summary", "")
        if isinstance(value, str) and value.strip():
            rows.append((field, claim_type, "structured_research_synthesis", value))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, str) and item.strip():
                    rows.append((f"{field}.{index}", claim_type, "structured_research_synthesis", item))
    return rows


def _claim_refs(claim_id: str, response: Mapping[str, Any], claim_evidence_map: Mapping[str, Any] | None) -> tuple[list[str], bool, list[str]]:
    if claim_evidence_map is None:
        refs = response.get("provenance_references")
        return (sorted(set(refs)) if isinstance(refs, list) and all(isinstance(x, str) for x in refs) else [], False, [])
    supplied = claim_evidence_map.get(claim_id, claim_evidence_map.get(claim_id.split(".", 1)[0]))
    if not isinstance(supplied, list) or not all(isinstance(item, str) for item in supplied):
        return [], True, ["claim_evidence_map_missing_or_malformed"]
    return sorted(set(supplied)), True, []


def build_current_research_claim_provenance_trace(
    ticker_context: Mapping[str, Any],
    ai_response: str | Mapping[str, Any],
    *,
    claim_evidence_map: Mapping[str, Any] | None = None,
    packet_consumption_mode: str = LEGACY_DIRECT,
) -> dict[str, Any]:
    """Build a deterministic trace from existing current context and AI response.

    The existing acceptance boundary remains the sole authority for which references are
    allowed.  Rejected response data is retained only as untraceable audit input; it
    cannot receive a supported disposition.
    """
    response = _parse_response(ai_response)
    boundary = accept_structured_research_synthesis(
        ticker_context, ai_response, packet_consumption_mode=packet_consumption_mode,
    )
    metadata = boundary.get("derived_contract_metadata") if isinstance(boundary.get("derived_contract_metadata"), Mapping) else {}
    known_refs = set(metadata.get("known_evidence_refs") or [])
    boundary_reasons = sorted(set(boundary.get("reasons") or []))
    prohibited = [reason for reason in boundary_reasons if reason.startswith("prohibited_")]
    entries: list[dict[str, Any]] = []
    for claim_id, claim_type, surface, payload in _claim_rows(response):
        refs, exact_map, map_reasons = _claim_refs(claim_id, response, claim_evidence_map)
        evidence: list[dict[str, Any]] = []
        statuses: list[str] = []
        reasons = list(map_reasons)
        for ref in refs:
            status, ref_reasons = _status_for_ref(ticker_context, ref, known_refs, metadata)
            source = _resolve_reference(ticker_context, ref)
            transports, transport_disposition = _transports(ticker_context, ref, metadata)
            evidence.append({
                "logical_evidence_identity": _identity("current_research_logical_evidence:", {"ref": ref, "identity": _artifact_identity(ticker_context, ref, source)}),
                "evidence_ref": ref,
                "component": _packet_component(ref) or _root(ref),
                "source_contract": _root(ref),
                "source_artifact_identity": _artifact_identity(ticker_context, ref, source),
                "source_ticker": ticker_context.get("ticker"),
                "transports": transports,
                "duplicate_transport_disposition": transport_disposition,
                "temporal": _collect_named(source, _TEMPORAL_KEYS),
                "qualification": _collect_named(source, _LIMITATION_KEYS),
                "reason_codes": ref_reasons,
            })
            statuses.append(status)
            reasons.extend(ref_reasons)
        if prohibited:
            disposition = AUTHORITY_BLOCKED
            reasons.extend(prohibited)
        elif not refs:
            disposition = UNRESOLVED
            reasons.append("no_claim_level_evidence_reference")
        elif any(status == CONFLICT_FAIL_CLOSED for status in statuses):
            disposition = CONFLICT_FAIL_CLOSED
        elif any(status in {UNSUPPORTED_REFERENCE, COMPONENT_UNAVAILABLE, MALFORMED} for status in statuses):
            disposition = next(status for status in statuses if status in {UNSUPPORTED_REFERENCE, COMPONENT_UNAVAILABLE, MALFORMED})
        elif any(status == AUTHORITY_BLOCKED for status in statuses):
            disposition = AUTHORITY_BLOCKED
        elif boundary.get("status") != "accepted":
            disposition = UNSUPPORTED_REFERENCE
            reasons.append("structured_response_not_accepted")
        elif not exact_map:
            disposition = SUPPORTED_WITH_LIMITATION
            reasons.append("package_wide_provenance_references_not_claim_level_linkage")
        elif any(status == SUPPORTED_WITH_LIMITATION for status in statuses):
            disposition = SUPPORTED_WITH_LIMITATION
        else:
            disposition = SUPPORTED
        entries.append({
            "claim_id": claim_id, "claim_type": claim_type, "claim_source_surface": surface,
            "claim_payload": payload, "evidence": evidence, "disposition": disposition,
            "reason_codes": sorted(set(reasons)),
            "provenance_chain": ["current_ticker_context", "structured_research_synthesis_boundary", *sorted(refs)],
        })
    artifact = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "ticker": ticker_context.get("ticker") if isinstance(ticker_context, Mapping) else None,
        "packet_consumption_mode": packet_consumption_mode,
        "structured_response_status": boundary.get("status"),
        "structured_response_reasons": boundary_reasons,
        "known_evidence_refs": sorted(known_refs),
        "claim_entries": entries,
        "authority_boundary": {
            "is_actionable": False,
            "read_only_consumer_of_current_research": True,
            "does_not_change_current_decisions_or_packet_default": True,
            "prohibited_interpretations": ["probability", "expected_return", "target_price", "intrinsic_value", "BUY_SELL_HOLD", "risk_score", "position_size", "participation", "capacity", "leverage", "PIT", "RAW_AS_TRADED", "backtest"],
        },
    }
    artifact["trace_identity"] = _identity("current_research_claim_provenance_trace:", artifact)
    return artifact


def query_current_research_claim_provenance_trace(trace: Mapping[str, Any], **filters: str) -> list[dict[str, Any]]:
    """Return exact-match claim rows for a small deterministic audit query surface."""
    allowed = {"ticker", "claim_type", "component", "support_status", "source_contract", "reason_code"}
    if set(filters) - allowed or not all(isinstance(value, str) for value in filters.values()):
        raise ValueError("INVALID_TRACE_QUERY_FILTER")
    matches: list[dict[str, Any]] = []
    for entry in trace.get("claim_entries") or []:
        if not isinstance(entry, Mapping):
            continue
        evidence = entry.get("evidence") or []
        values = {
            "ticker": trace.get("ticker"), "claim_type": entry.get("claim_type"),
            "support_status": entry.get("disposition"), "reason_code": entry.get("reason_codes") or [],
            "component": [row.get("component") for row in evidence if isinstance(row, Mapping)],
            "source_contract": [row.get("source_contract") for row in evidence if isinstance(row, Mapping)],
        }
        if all((expected in values[name] if isinstance(values[name], list) else values[name] == expected) for name, expected in filters.items()):
            matches.append(copy.deepcopy(dict(entry)))
    return matches


def render_current_research_claim_provenance_trace_markdown(trace: Mapping[str, Any]) -> str:
    lines = ["# Current Research Claim Provenance Trace", "", f"Ticker: `{trace.get('ticker')}`", f"Trace identity: `{trace.get('trace_identity')}`", ""]
    for entry in trace.get("claim_entries") or []:
        if not isinstance(entry, Mapping):
            continue
        lines.extend([f"## {entry.get('claim_id')}", "", "### CLAIM", str(entry.get("claim_payload")), "", "### SUPPORTED BY"])
        evidence = entry.get("evidence") or []
        if evidence:
            for row in evidence:
                lines.append(f"- `{row.get('evidence_ref')}` — {row.get('source_contract')} ({row.get('duplicate_transport_disposition')})")
        else:
            lines.append("- No permitted claim-level evidence reference supplied.")
        lines.extend(["", "### SOURCE / AS-OF"])
        for row in evidence:
            lines.append(f"- `{row.get('source_artifact_identity')}`; {json.dumps(row.get('temporal'), sort_keys=True)}")
        lines.extend(["", "### AUTHORITY / LIMITATIONS", f"- {entry.get('disposition')}: {', '.join(entry.get('reason_codes') or []) or 'none'}", "", "### WHAT THIS EVIDENCE DOES NOT PROVE", "- It does not authorize probability, return, valuation, recommendation, sizing, execution, PIT, RAW_AS_TRADED, or backtest conclusions.", ""])
    return "\n".join(lines)


def replay_current_research_claim_provenance_trace(trace: Mapping[str, Any]) -> None:
    if trace.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("TRACE_CONTRACT_VERSION_MISMATCH")
    expected = dict(trace)
    actual = expected.pop("trace_identity", None)
    if _identity("current_research_claim_provenance_trace:", expected) != actual:
        raise ValueError("TRACE_IDENTITY_MISMATCH")
    for entry in trace.get("claim_entries") or []:
        if not isinstance(entry, Mapping) or entry.get("disposition") not in _TRACE_STATUSES:
            raise ValueError("TRACE_ENTRY_MALFORMED")
