"""Read-only auditable presentation of validated current research and its trace."""
from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping

from builders.current_research_claim_provenance_trace import (
    LEGACY_DIRECT,
    build_current_research_claim_provenance_trace,
    replay_current_research_claim_provenance_trace,
)

SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "current_research_auditable_dossier/v1"


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _response_object(value: str | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError:
            return {}
    return value if isinstance(value, Mapping) else {}


def _mapping(value: Any, *keys: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        return {}
    return {key: copy.deepcopy(value[key]) for key in keys if key in value}


def _component_state(context: Mapping[str, Any]) -> dict[str, Any]:
    """Select state already established upstream; do not recalculate any component."""
    packet = context.get("current_research_decision_packet")
    packet_record = packet.get("packet") if isinstance(packet, Mapping) else None
    packet_components = packet_record.get("components") if isinstance(packet_record, Mapping) else {}
    scenario = packet_components.get("scenario_context") if isinstance(packet_components, Mapping) else None
    scenario_context = context.get("current_research_scenario_context")
    scenario_record = scenario_context.get("scenario_context") if isinstance(scenario_context, Mapping) else None
    scenario_axes = scenario_record.get("axes") if isinstance(scenario_record, Mapping) else None
    valuation = context.get("market_wide_current_valuation")
    valuation_metrics = valuation.get("metrics") if isinstance(valuation, Mapping) else None
    risk = context.get("current_research_risk_register")
    risk_body = risk.get("risk_register") if isinstance(risk, Mapping) else None
    financial = context.get("current_financial_momentum_context")
    events = context.get("current_corporate_event_context")
    market_sector = context.get("current_market_sector_leadership_context")
    historical = context.get("market_wide_historical_research_context")
    return {
        "upstream_source_contracts": {
            "tactical_entry_classifier": _mapping(context.get("watchlist_tactical_entry_classifier"), "entry_state", "entry_action", "action", "horizon", "is_full_position_ready", "position_sizing_status"),
            "opportunity_decision_queue": _mapping((context.get("current_opportunity_decision_context") or {}).get("ticker_record"), "research_priority_tier", "entry_action", "entry_relevant"),
        },
        "evidence_bound_scenario": _mapping(scenario, "scenario_disposition", "current_state", "bear_case", "base_case", "bull_case", "authority_limitations"),
        "research_scenario_axis": {
            axis: _mapping(row, "scenario_axis", "scenario_status", "status_rule")
            for axis, row in sorted((scenario_axes if isinstance(scenario_axes, Mapping) else {}).items())
            if isinstance(row, Mapping)
        },
        "risk_state": {
            **_mapping(risk_body, "risk_register_status"),
            "material_risk_count": len(risk_body.get("material_risks") or []) if isinstance(risk_body, Mapping) else None,
            "watch_risk_count": len(risk_body.get("watch_risks") or []) if isinstance(risk_body, Mapping) else None,
            "authority_limitation_count": len(risk_body.get("data_authority_limitations") or []) if isinstance(risk_body, Mapping) else None,
            "unresolved_conflict_count": len(risk_body.get("unresolved_conflicts") or []) if isinstance(risk_body, Mapping) else None,
        },
        "market_sector_context": _mapping(market_sector, "status", "session", "source_artifact_identity"),
        "financial_context": _mapping(financial, "status", "session", "source_artifact_identity"),
        "event_context": _mapping(events, "status", "research_session", "source_artifact_identity", "qualified_event_count", "planned_unresolved_count", "temporal_incomplete_count", "data_limited_count", "conflicting_count"),
        "valuation_state": {
            **_mapping(valuation, "source_artifact_identity"),
            "metric_statuses": {
                name: _mapping(metric, "status", "price_session", "authority_tier", "blocked_reasons")
                for name, metric in sorted((valuation_metrics or {}).items()) if isinstance(metric, Mapping)
            },
        },
        "historical_context": _mapping(historical, "context_status", "status", "session", "source_artifact_identity", "authority_boundary"),
    }


def _important_claims(trace: Mapping[str, Any]) -> list[dict[str, Any]]:
    important = {"thesis", "counter_thesis", "supporting_evidence", "counter_evidence", "catalyst_context", "risk_context", "invalidation_conditions", "unresolved_questions", "authority_limitations"}
    return [copy.deepcopy(dict(entry)) for entry in trace.get("claim_entries") or [] if isinstance(entry, Mapping) and entry.get("claim_type") in important]


def build_current_research_auditable_dossier(
    ticker_context: Mapping[str, Any],
    ai_response: str | Mapping[str, Any],
    *,
    claim_evidence_map: Mapping[str, Any] | None = None,
    packet_consumption_mode: str = LEGACY_DIRECT,
) -> dict[str, Any]:
    """Package accepted synthesis and a provenance trace; make no analytical judgement."""
    response = _response_object(ai_response)
    trace = build_current_research_claim_provenance_trace(
        ticker_context, ai_response, claim_evidence_map=claim_evidence_map,
        packet_consumption_mode=packet_consumption_mode,
    )
    replay_current_research_claim_provenance_trace(trace)
    if trace.get("structured_response_status") != "accepted":
        return {
            "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
            "status": "REJECTED_UNTRACEABLE", "ticker": ticker_context.get("ticker"),
            "trace_identity": trace.get("trace_identity"),
            "reason_codes": list(trace.get("structured_response_reasons") or ["structured_response_not_accepted"]),
            "authority_boundary": {"is_actionable": False, "does_not_display_unaccepted_claims_as_supported": True},
        }
    source_identities = sorted({
        item.get("source_artifact_identity") for entry in trace.get("claim_entries") or []
        if isinstance(entry, Mapping) for item in entry.get("evidence") or []
        if isinstance(item, Mapping) and isinstance(item.get("source_artifact_identity"), str)
    })
    packet = ticker_context.get("current_research_decision_packet")
    current_research_source_identity = packet.get("source_artifact_identity") if isinstance(packet, Mapping) else None
    dossier = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "status": "READY_FOR_AUDIT",
        "research_identity": {
            "ticker": response.get("ticker"), "research_session": response.get("analysis_session"),
            "structured_synthesis_identity": _identity("structured_research_synthesis:", response),
            "trace_identity": trace["trace_identity"],
            "current_research_source_identity": current_research_source_identity,
            "source_artifact_identities": source_identities,
            "packet_consumption_mode": packet_consumption_mode,
        },
        "current_research_thesis": response.get("thesis"),
        "strongest_counter_thesis": response.get("counter_thesis"),
        "current_deterministic_state": _component_state(ticker_context),
        "catalysts": copy.deepcopy(response.get("catalyst_context") or []),
        "risks": copy.deepcopy(response.get("risk_context") or []),
        "invalidation_conditions": copy.deepcopy(response.get("invalidation_conditions") or []),
        "unresolved_questions": copy.deepcopy(response.get("unresolved_questions") or []),
        "authority_limitations": copy.deepcopy(response.get("authority_limitations") or []),
        "claim_provenance": _important_claims(trace),
        "authority_summary": {
            "synthesis_is_actionable": response.get("is_actionable"),
            "trace_authority_boundary": copy.deepcopy(trace.get("authority_boundary")),
            "packet_default_unchanged": "LEGACY_DIRECT",
            "prohibited_interpretations": ["probability", "expected_return", "target_price", "intrinsic_value", "BUY_SELL_HOLD", "position_size", "participation", "capacity", "leverage", "PIT", "RAW_AS_TRADED", "backtest"],
        },
    }
    dossier["dossier_identity"] = _identity("current_research_auditable_dossier:", dossier)
    return dossier


def render_current_research_auditable_dossier_markdown(dossier: Mapping[str, Any]) -> str:
    if dossier.get("status") != "READY_FOR_AUDIT":
        return "# Current Research Auditable Dossier\n\nStatus: `REJECTED_UNTRACEABLE`\n\n" + "\n".join(f"- {reason}" for reason in dossier.get("reason_codes") or []) + "\n"
    identity = dossier["research_identity"]
    state = dossier["current_deterministic_state"]
    lines = ["# Current Research Auditable Dossier", "", "## RESEARCH IDENTITY", f"- Ticker: `{identity.get('ticker')}`", f"- Research session: `{identity.get('research_session')}`", f"- Dossier identity: `{dossier.get('dossier_identity')}`", f"- Structured synthesis identity: `{identity.get('structured_synthesis_identity')}`", f"- Trace identity: `{identity.get('trace_identity')}`", "", "## CURRENT RESEARCH THESIS", str(dossier.get("current_research_thesis")), "", "## STRONGEST COUNTER-THESIS", str(dossier.get("strongest_counter_thesis")), "", "## CURRENT DETERMINISTIC STATE"]
    for name, value in state.get("upstream_source_contracts", {}).items():
        lines.append(f"- `{name}`: {json.dumps(value, sort_keys=True)}")
    lines.extend(["", "### Evidence-Bound Scenario", json.dumps(state.get("evidence_bound_scenario"), sort_keys=True), "", "### Research Scenario Axis", json.dumps(state.get("research_scenario_axis"), sort_keys=True), "", "### Risk / Context State", json.dumps({key: value for key, value in state.items() if key not in {"upstream_source_contracts", "evidence_bound_scenario", "research_scenario_axis"}}, sort_keys=True), "", "## CATALYSTS / RISKS / INVALIDATION"])
    for label, values in (("Catalysts", dossier.get("catalysts")), ("Risks", dossier.get("risks")), ("Invalidation", dossier.get("invalidation_conditions")), ("Unresolved", dossier.get("unresolved_questions"))):
        lines.append(f"### {label}")
        lines.extend(f"- {value}" for value in values) if values else lines.append("- None supplied by the accepted synthesis.")
    lines.extend(["", "## CLAIM PROVENANCE"])
    for claim in dossier.get("claim_provenance") or []:
        lines.extend([f"### {claim.get('claim_id')}", f"**Claim:** {claim.get('claim_payload')}", f"**Disposition:** `{claim.get('disposition')}`"])
        evidence = claim.get("evidence") or []
        lines.extend(f"- `{row.get('evidence_ref')}` — {row.get('source_contract')} — `{row.get('source_artifact_identity')}` — {json.dumps(row.get('temporal'), sort_keys=True)}" for row in evidence)
        if not evidence:
            lines.append("- No permitted claim-level evidence reference supplied.")
        lines.append("**Does not prove:** probability, return, target price, intrinsic value, recommendation, sizing, execution, PIT, RAW_AS_TRADED, or backtest conclusions.")
    lines.extend(["", "## AUTHORITY SUMMARY", "- This dossier is presentation-only and non-actionable.", "- `research_priority`, `entry_action`, human selection, and sizing authority remain distinct source-contract concepts.", "- `NO_MATERIAL_RISK_ESTABLISHED` is not LOW_RISK; `RESEARCH_USABLE` valuation is not authoritative fair value; adjusted retrospective history is not PIT or RAW_AS_TRADED.", "- Record date is not ex-date; planned/approved is not executed; neither scenario family is probability.", ""])
    return "\n".join(lines)


def replay_current_research_auditable_dossier(dossier: Mapping[str, Any]) -> None:
    if dossier.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("DOSSIER_CONTRACT_VERSION_MISMATCH")
    if dossier.get("status") != "READY_FOR_AUDIT":
        return
    expected = dict(dossier)
    identity = expected.pop("dossier_identity", None)
    if _identity("current_research_auditable_dossier:", expected) != identity:
        raise ValueError("DOSSIER_IDENTITY_MISMATCH")
