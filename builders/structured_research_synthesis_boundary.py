"""Consumer acceptance and orchestration boundary for structured AI research synthesis.

This module is the deterministic bridge between a canonical ticker context package and
an AI-produced structured research-synthesis output. It is the only layer that sees the
real ticker context, so it alone can:

1. Derive the true, currently-present upstream deterministic decision fields (tactical
   entry classifier, all-lane opportunity/research-priority queue) the AI must quote
   verbatim and never mint or upgrade -- this is the concrete enforcement of the CORE
   AUTHORITY RULE: the AI may explain an upstream deterministic state, never change it.
2. Derive which evidence sections/metrics are actually present and usable, so cited
   provenance is traceable to real supplied context and a malformed or absent sibling
   cannot be cited as if it were legitimate evidence.
3. Keep each sibling's own session identity separate (historical, valuation, and current
   market/sector leadership context), never unifying them into one synthesized "current"
   timestamp.
4. Delegate structural and textual safety checks to structured_research_synthesis_response.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from builders.structured_research_synthesis_response import validate_structured_research_synthesis_output

_TACTICAL_TRUTH_FIELDS = (
    "entry_state", "entry_action", "action", "horizon",
    "is_full_position_ready", "position_sizing_status",
)
_OPPORTUNITY_TRUTH_FIELDS = ("research_priority_tier", "entry_action", "entry_relevant")

_SIBLING_KEYS = (
    "watchlist_tactical_entry_classifier",
    "current_opportunity_decision_context",
    "market_wide_historical_research_context",
    "market_wide_current_valuation",
    "current_market_sector_leadership_context",
    "current_financial_momentum_context",
    "current_corporate_event_context",
    "current_research_risk_register",
)

_VALUATION_USABLE_STATUSES = {"READY", "RESEARCH_USABLE"}
_FINANCIAL_MOMENTUM_COMPONENT_USABLE_STATUSES = {"AVAILABLE", "PARTIAL"}
_RISK_REGISTER_CATEGORIES = ("material_risks", "watch_risks", "data_authority_limitations", "unresolved_conflicts")


def _reject_boundary(*reasons: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "rejected",
        "accepted_output": None,
        "reasons": sorted(set(reasons)),
        "derived_contract_metadata": copy.deepcopy(metadata or {}),
        "structured_research_synthesis_boundary": True,
    }


def accept_structured_research_synthesis(
    ticker_context: Mapping[str, Any],
    ai_response: str | Mapping[str, Any],
) -> dict[str, Any]:
    """Accept and validate a structured AI research-synthesis output using canonical ticker context."""
    if not isinstance(ticker_context, Mapping):
        return _reject_boundary("ticker_context_invalid_type")

    ticker = ticker_context.get("ticker")
    if ticker is not None and not isinstance(ticker, str):
        return _reject_boundary("ticker_context_malformed:ticker")

    shape_reasons = [
        f"ticker_context_malformed:{key}"
        for key in _SIBLING_KEYS
        if key in ticker_context and ticker_context[key] is not None and not isinstance(ticker_context[key], Mapping)
    ]
    if shape_reasons:
        return _reject_boundary(*shape_reasons)

    derived_meta: dict[str, Any] = {}
    if isinstance(ticker, str):
        derived_meta["expected_ticker"] = ticker

    # --- 1. Derive upstream_decision_context truth: exact quoting only, never inferred ---
    expected_upstream: dict[str, Any] = {}

    tactical = ticker_context.get("watchlist_tactical_entry_classifier")
    if isinstance(tactical, Mapping):
        if tactical.get("status") in {"classified", "insufficient_data"}:
            expected_upstream["tactical_entry_classifier"] = {
                field: tactical[field] for field in _TACTICAL_TRUTH_FIELDS if field in tactical
            }
        else:
            derived_meta["tactical_entry_classifier_status"] = "malformed"

    opportunity = ticker_context.get("current_opportunity_decision_context")
    if isinstance(opportunity, Mapping):
        record = opportunity.get("ticker_record")
        if isinstance(record, Mapping):
            expected_upstream["opportunity_decision_queue"] = {
                field: record[field] for field in _OPPORTUNITY_TRUTH_FIELDS if field in record
            }
        else:
            derived_meta["opportunity_decision_queue_status"] = "malformed"

    derived_meta["expected_upstream_decision_context"] = expected_upstream

    # --- 2. Derive each sibling's own session identity separately; never unify them ---
    historical = ticker_context.get("market_wide_historical_research_context")
    if isinstance(historical, Mapping):
        if isinstance(historical.get("session"), str):
            derived_meta["historical_context_session"] = historical["session"]
            derived_meta["historical_context_status"] = historical.get("context_status") or historical.get("status")
        else:
            derived_meta["historical_context_status"] = "malformed"

    valuation = ticker_context.get("market_wide_current_valuation")
    if isinstance(valuation, Mapping):
        price_input = valuation.get("price_input")
        price_session = price_input.get("session") if isinstance(price_input, Mapping) else None
        if isinstance(price_session, str):
            derived_meta["valuation_context_session"] = price_session
        else:
            derived_meta["valuation_context_status"] = "malformed"

    market_sector = ticker_context.get("current_market_sector_leadership_context")
    if isinstance(market_sector, Mapping):
        if isinstance(market_sector.get("session"), str) and market_sector.get("status") in {"available", "data_limited"}:
            derived_meta["market_sector_context_session"] = market_sector["session"]
            derived_meta["market_sector_context_status"] = market_sector["status"]
        else:
            derived_meta["market_sector_context_status"] = "malformed"

    # Financial momentum's own session may legitimately be None (Producer omits it when no
    # current_descriptive sibling was available at artifact-build time) -- that is distinct
    # from malformed, so only treat an unrecognized status as malformed.
    financial_momentum = ticker_context.get("current_financial_momentum_context")
    if isinstance(financial_momentum, Mapping):
        fm_session = financial_momentum.get("session")
        if (fm_session is None or isinstance(fm_session, str)) and financial_momentum.get("status") in {"available", "data_limited"}:
            if isinstance(fm_session, str):
                derived_meta["financial_momentum_context_session"] = fm_session
            derived_meta["financial_momentum_context_status"] = financial_momentum["status"]
        else:
            derived_meta["financial_momentum_context_status"] = "malformed"

    # Corporate events' own research_session is Producer-required (never legitimately
    # absent, unlike financial momentum's) -- track it independently of every other
    # session, never unified with historical/valuation/market-sector/financial-momentum.
    corporate_events = ticker_context.get("current_corporate_event_context")
    if isinstance(corporate_events, Mapping):
        ce_session = corporate_events.get("research_session")
        if isinstance(ce_session, str) and ce_session and corporate_events.get("status") in {"available", "data_limited"}:
            derived_meta["corporate_event_context_session"] = ce_session
            derived_meta["corporate_event_context_status"] = corporate_events["status"]
        else:
            derived_meta["corporate_event_context_status"] = "malformed"

    # The risk register carries no single unified session -- it has five independent
    # source-context as-of identities instead (historical/leadership/financial/event/
    # valuation), so track its own content status plus that per-source map, never
    # collapsing them into one synthesized "session" the way every other sibling has one.
    risk_register = ticker_context.get("current_research_risk_register")
    if isinstance(risk_register, Mapping):
        register_body = risk_register.get("risk_register")
        source_contexts = risk_register.get("source_contexts")
        register_status = register_body.get("risk_register_status") if isinstance(register_body, Mapping) else None
        if (
            isinstance(register_body, Mapping)
            and register_status in {"MATERIAL_RISKS_ESTABLISHED", "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE"}
            and isinstance(source_contexts, Mapping)
        ):
            derived_meta["risk_register_status"] = register_status
            derived_meta["risk_register_source_sessions"] = {
                name: entry.get("as_of") for name, entry in source_contexts.items() if isinstance(entry, Mapping)
            }
        else:
            derived_meta["risk_register_status"] = "malformed"

    # --- 3. Derive known, citable evidence references from the context's own provenance ---
    known_refs: set[str] = set()
    provenance = ticker_context.get("provenance")
    if isinstance(provenance, list):
        for entry in provenance:
            if isinstance(entry, Mapping) and isinstance(entry.get("source_dataset"), str):
                known_refs.add(entry["source_dataset"])

    if isinstance(valuation, Mapping) and isinstance(valuation.get("metrics"), Mapping):
        for metric_name, metric in valuation["metrics"].items():
            if isinstance(metric, Mapping) and metric.get("status") in _VALUATION_USABLE_STATUSES:
                known_refs.add(f"market_wide_current_valuation.metrics.{metric_name}")

    if isinstance(financial_momentum, Mapping):
        fm_ticker_context = financial_momentum.get("ticker_context")
        components = fm_ticker_context.get("components") if isinstance(fm_ticker_context, Mapping) else None
        if isinstance(components, Mapping):
            for component_name, component in components.items():
                if isinstance(component, Mapping) and component.get("status") in _FINANCIAL_MOMENTUM_COMPONENT_USABLE_STATUSES:
                    known_refs.add(f"current_financial_momentum_context.components.{component_name}")

    # Every retained event (any event_status, including CONFLICTING_EVIDENCE/DATA_LIMITED/
    # CANCELLED) is a real record, unlike a financial-momentum BLOCKED/UNAVAILABLE component
    # which means no data exists -- so each event_id is independently citable, letting the
    # synthesis explain temporal gaps and conflicts as evidence rather than only clean facts.
    if isinstance(corporate_events, Mapping):
        ce_ticker_context = corporate_events.get("ticker_context")
        events = ce_ticker_context.get("events") if isinstance(ce_ticker_context, Mapping) else None
        if isinstance(events, list):
            for event in events:
                if isinstance(event, Mapping) and isinstance(event.get("event_id"), str):
                    known_refs.add(f"current_corporate_event_context.events.{event['event_id']}")

    # Every risk-register item (material, watch, data-authority limitation, or unresolved
    # conflict alike) is a real Producer-computed record, never a placeholder for absent
    # data -- so each is independently citable, keeping the four categories distinct in the
    # reference path itself (never collapsed into one undifferentiated "risk item" ref).
    if isinstance(risk_register, Mapping) and isinstance(register_body, Mapping):
        for category in _RISK_REGISTER_CATEGORIES:
            for item in register_body.get(category) or []:
                if isinstance(item, Mapping) and isinstance(item.get("risk_id"), str):
                    known_refs.add(f"current_research_risk_register.{category}.{item['risk_id']}")

    # A malformed sibling is recorded (processed) in provenance, but must never be
    # citable as if its content were usable evidence -- strip it back out here.
    if derived_meta.get("tactical_entry_classifier_status") == "malformed":
        known_refs.discard("watchlist_tactical_entry_classifier")
    if derived_meta.get("opportunity_decision_queue_status") == "malformed":
        known_refs.discard("current_opportunity_decision_context")
        known_refs.discard("daily_opportunity_decision_queue")
    if derived_meta.get("historical_context_status") == "malformed":
        known_refs.discard("market_wide_historical_research_context")
    if derived_meta.get("valuation_context_status") == "malformed":
        known_refs.discard("market_wide_current_valuation")
        known_refs = {ref for ref in known_refs if not ref.startswith("market_wide_current_valuation.")}
    if derived_meta.get("market_sector_context_status") == "malformed":
        known_refs.discard("current_market_sector_leadership_context")
    if derived_meta.get("financial_momentum_context_status") == "malformed":
        known_refs.discard("current_financial_momentum_context")
        known_refs = {ref for ref in known_refs if not ref.startswith("current_financial_momentum_context.")}
    if derived_meta.get("corporate_event_context_status") == "malformed":
        known_refs.discard("current_corporate_event_context")
        known_refs = {ref for ref in known_refs if not ref.startswith("current_corporate_event_context.")}
    if derived_meta.get("risk_register_status") == "malformed":
        known_refs.discard("current_research_risk_register")
        known_refs = {ref for ref in known_refs if not ref.startswith("current_research_risk_register.")}

    derived_meta["known_evidence_refs"] = sorted(known_refs)

    # --- 4. Delegate to the response validator ---
    validator_result = validate_structured_research_synthesis_output(ai_response, contract_metadata=derived_meta)

    if validator_result["status"] == "rejected":
        return _reject_boundary(*validator_result["reasons"], metadata=derived_meta)

    return {
        "status": "accepted",
        "accepted_output": copy.deepcopy(validator_result["accepted_output"]),
        "reasons": [],
        "derived_contract_metadata": copy.deepcopy(derived_meta),
        "structured_research_synthesis_boundary": True,
    }
