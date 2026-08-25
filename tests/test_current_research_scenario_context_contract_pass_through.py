"""Contract regressions for the current research scenario context pass-through."""
from __future__ import annotations

import copy

from builders.build_ticker_context import (
    apply_bundle_current_research_scenario_context_contract,
    current_research_scenario_context_contract,
)

# TEST_FIXTURE_ONLY -- shape verified against stock-core-private commit
# 244ac57e680dc9b76e5e8f83577078be79cc5c0d (current_research_scenario_context.py
# build_artifact()/_axis_record()/collect_evidence(), export_ai_bundle.py
# attach_current_research_scenario_context()), read via `git show` at that pinned
# revision, not the (concurrently writable) working tree.
_AXES = ("CONSERVATIVE", "BASE", "SPECULATIVE")
_FORBIDDEN_USES = (
    "probability", "expected_return", "target_price", "upside_pct", "downside_pct",
    "payoff_ratio", "intrinsic_value", "recommendation", "position_size", "sizing",
    "strategy_eligibility", "research_priority", "entry_action", "daily_decision_queue",
    "VALUE", "RAW_AS_TRADED", "PIT", "backtest",
)
_RISK_REGISTER_FORBIDDEN_USES = (
    "numeric_risk_score", "risk_adjusted_return", "expected_loss", "VaR", "probability",
    "position_size", "participation_cap", "recommendation", "strategy_eligibility",
    "research_priority", "entry_action", "VALUE", "daily_decision_queue",
)
_SOURCE_CONTEXTS = {
    "official_universe": {"artifact_identity": "current_official_market_universe:ou1", "as_of": None, "available": True},
    "tactical": {"artifact_identity": "watchlist_tactical_entry_classifier:t1", "as_of": "2026-08-25", "available": True},
    "opportunity": {"artifact_identity": "current_opportunity_prioritization:o1", "as_of": "2026-08-25", "available": True},
    "historical": {"artifact_identity": "market_wide_historical_research_context:h1", "as_of": "2026-08-24", "available": True},
    "leadership": {"artifact_identity": "current_market_sector_leadership_context:l1", "as_of": "2026-08-25", "available": True},
    "financial": {"artifact_identity": "current_financial_momentum_context:f1", "as_of": "2026-08-24", "available": True},
    "event": {"artifact_identity": "current_corporate_event_context:e1", "as_of": "2026-08-21", "available": True},
    "valuation": {"artifact_identity": "market_wide_current_valuation_input_scaleout:v1", "as_of": "2026-08-21", "available": True},
    "risk_register": {"artifact_identity": "current_research_risk_register:r1", "as_of": None, "available": True},
}
_AS_OF = {
    "tactical": "2026-08-25", "opportunity": "2026-08-25", "historical": "2026-08-24",
    "leadership": "2026-08-25", "financial": "2026-08-24", "event": "2026-08-21", "valuation": "2026-08-21",
}
_EVIDENCE_REFS = sorted(
    ({"source": name, "identity": ctx["artifact_identity"]} for name, ctx in _SOURCE_CONTEXTS.items()),
    key=lambda r: r["source"],
)
_BLOCKED_OUTPUTS = {use: "NOT_EMITTED_OR_MODIFIED" for use in _FORBIDDEN_USES}
_AUTHORITY_BOUNDARY = {
    "is_actionable": False, "research_only": True, "no_probability": True, "no_expected_return": True,
    "no_target_price": True, "no_sizing": True, "no_recommendation": True,
    "does_not_modify_research_priority": True, "does_not_modify_strategy_eligibility": True,
    "does_not_modify_entry_action": True, "does_not_modify_daily_decision_queue": True,
    "does_not_replace_evidence_bound_bear_base_bull": True, "data_limitation_is_not_economic_risk": True,
    "material_risk_rule": "MATERIAL_RISK_BLOCKS_CONSERVATIVE_SUPPORTED",
    "raw_as_traded": "NOT_PROMOTED", "pit": "BLOCKED", "backtest": "NOT_EMITTED",
}
_DEFAULT_STATUS_RULE = {
    "CONSERVATIVE": ("SUPPORTED", "CONSERVATIVE_CONFIRMED_TREND_NO_MATERIAL_RISK"),
    "BASE": ("SUPPORTED", "BASE_CURRENT_CLASSIFIED_STATE"),
    "SPECULATIVE": ("NOT_SUPPORTED", "NO_EXPLICIT_EARLY_OR_HIGHER_UNCERTAINTY_EVIDENCE"),
}


def _decision_context(*, priority="MONITOR", action="WAIT", entry_state="UPTREND_CONFIRMED",
                       lanes=None, disposition="SCENARIO_READY"):
    return {
        "research_priority": priority, "entry_action": action, "entry_state": entry_state,
        "eligible_strategy_lanes": list(lanes if lanes is not None else ["TREND_MOMENTUM"]),
        "existing_evidence_bound_scenario_disposition": disposition,
        "quoted_not_modified": True,
    }


def _condition(*, condition_id, domain, polarity, code, source_context="current_financial_momentum_context:f1",
               authority_tier="CURRENT_SESSION_DESCRIPTIVE", facts=None):
    return {
        "condition_id": condition_id, "domain": domain, "polarity": polarity, "code": code,
        "facts": facts if facts is not None else {}, "authority_tier": authority_tier,
        "source_context": source_context,
    }


def _gate(*, status="UNAVAILABLE", reason="QUALIFIED_CONFIRMATION_CONDITION_UNAVAILABLE", text=None, invented=False):
    return {"status": status, "reason": reason, "text": text, "invented": invented}


def _risk_item(*, ticker="AAA", domain="FINANCIAL", risk_type="FINANCIAL_STRESS", status="ESTABLISHED",
               severity="MATERIAL", source_context="current_financial_momentum_context:f1",
               source_as_of="2026-08-24", facts=None, reasons=None, authority_tier="OFFICIAL_QUALIFIED"):
    return {
        "risk_id": f"{ticker}:{domain}:{risk_type}",
        "risk_domain": domain, "risk_type": risk_type, "status": status, "severity_band": severity,
        "source_context": source_context, "source_as_of": source_as_of,
        "observed_facts": facts if facts is not None else {"financial_momentum_state": "LOSS_MAKING_OR_STRESSED"},
        "reason_codes": reasons if reasons is not None else ["LOSS"],
        "authority_tier": authority_tier,
        "allowed_uses": ["CURRENT_RESEARCH_CONTEXT"], "prohibited_uses": list(_RISK_REGISTER_FORBIDDEN_USES),
    }


def _axis_row(*, ticker="AAA", axis="CONSERVATIVE", status=None, status_rule=None, reasons=None,
              decision_context=None, supporting=None, opposing=None, confirmation=None, invalidation=None,
              material_risks=None, limitations=None, unresolved=None, evidence_refs=None):
    decision_context = decision_context if decision_context is not None else _decision_context()
    default_status, default_rule = _DEFAULT_STATUS_RULE[axis]
    status = status if status is not None else default_status
    status_rule = status_rule if status_rule is not None else default_rule
    return {
        "ticker": ticker, "scenario_axis": axis, "scenario_status": status, "status_rule": status_rule,
        "status_reasons": reasons if reasons is not None else [status_rule],
        "source_as_of": copy.deepcopy(_AS_OF),
        "current_decision_context": copy.deepcopy(decision_context),
        "eligible_strategy_lanes": list(decision_context["eligible_strategy_lanes"]),
        "supporting_conditions": supporting if supporting is not None else [],
        "opposing_conditions": opposing if opposing is not None else [],
        "confirmation_conditions": [confirmation if confirmation is not None else _gate()],
        "invalidation_conditions": [invalidation if invalidation is not None else _gate()],
        "material_risks": material_risks if material_risks is not None else [],
        "authority_limitations": limitations if limitations is not None else [],
        "unresolved_questions": unresolved if unresolved is not None else [],
        "evidence_references": copy.deepcopy(evidence_refs if evidence_refs is not None else _EVIDENCE_REFS),
        "allowed_uses": ["CURRENT_RESEARCH_CONTEXT"],
        "prohibited_uses": list(_FORBIDDEN_USES),
        "base_is_not_most_likely": True if axis == "BASE" else None,
        "evidence_standard_lowered": False,
        "material_risk_rule": "MATERIAL_RISK_BLOCKS_CONSERVATIVE_SUPPORTED" if axis == "CONSERVATIVE" else "MATERIAL_RISK_LISTED_NOT_SCORED",
        "does_not_modify_research_priority": True,
        "does_not_modify_strategy_eligibility": True,
        "does_not_modify_entry_action": True,
    }


def _scenario_record(*, ticker="AAA", decision_context=None, axes_overrides=None):
    decision_context = decision_context if decision_context is not None else _decision_context()
    axes = {
        axis: _axis_row(ticker=ticker, axis=axis, decision_context=decision_context, **(axes_overrides or {}).get(axis, {}))
        for axis in _AXES
    }
    return {
        "ticker": ticker,
        "current_decision_context": copy.deepcopy(decision_context),
        "axes": axes,
        "source_as_of": copy.deepcopy(_AS_OF),
        "blocked_outputs": copy.deepcopy(_BLOCKED_OUTPUTS),
    }


def _artifact(*, ticker="AAA", decision_context=None, axes_overrides=None, source_contexts=None):
    return {
        "ticker": ticker,
        "source_artifact_identity": "current_research_scenario_context:abc123",
        "source_contexts": copy.deepcopy(source_contexts if source_contexts is not None else _SOURCE_CONTEXTS),
        "scenario_context": _scenario_record(ticker=ticker, decision_context=decision_context, axes_overrides=axes_overrides),
        "authority_boundary": copy.deepcopy(_AUTHORITY_BOUNDARY),
        "blocked_outputs": copy.deepcopy(_BLOCKED_OUTPUTS),
        "is_actionable": False,
    }


def _bundle(ticker, raw):
    return {"tickers": {ticker: {"current_research_scenario_context": raw}}}


def test_valid_conservative_supported_passes():
    """1. valid CONSERVATIVE passes."""
    raw = _artifact()
    bundle = _bundle("AAA", raw)
    assert current_research_scenario_context_contract(bundle, "AAA") == raw
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, bundle)
    axes = context["current_research_scenario_context"]["scenario_context"]["axes"]
    assert axes["CONSERVATIVE"]["scenario_status"] == "SUPPORTED"
    assert "probability" not in axes["CONSERVATIVE"]
    assert "entry_action" not in axes["CONSERVATIVE"]


def test_valid_base_supported_passes():
    """2. valid BASE passes."""
    raw = _artifact()
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, _bundle("AAA", raw))
    axes = context["current_research_scenario_context"]["scenario_context"]["axes"]
    assert axes["BASE"]["scenario_status"] == "SUPPORTED"
    assert axes["BASE"]["base_is_not_most_likely"] is True


def test_valid_speculative_supported_passes():
    """3. valid SPECULATIVE passes, including a SUPPORTED (not just NOT_SUPPORTED) case."""
    raw = _artifact(axes_overrides={
        "SPECULATIVE": {
            "status": "SUPPORTED", "status_rule": "SPECULATIVE_EXPLICIT_EARLY_OR_HIGHER_UNCERTAINTY_EVIDENCE",
            "reasons": ["SPECULATIVE_EXPLICIT_EARLY_OR_HIGHER_UNCERTAINTY_EVIDENCE", "SPECULATIVE_DOES_NOT_LOWER_EVIDENCE_AUTHORITY"],
            "supporting": [_condition(
                condition_id="TECHNICAL_UNCONFIRMED_EARLY_STATE", domain="TECHNICAL", polarity="SUPPORT",
                code="EXPLICIT_EARLY_OR_UNCONFIRMED_STATE", source_context="watchlist_tactical_entry_classifier:t1",
                facts={"entry_state": "EARLY_REVERSAL_CANDIDATE"},
            )],
        },
    })
    bundle = _bundle("AAA", raw)
    result = current_research_scenario_context_contract(bundle, "AAA")
    axes = result["scenario_context"]["axes"]
    assert axes["SPECULATIVE"]["scenario_status"] == "SUPPORTED"
    assert axes["SPECULATIVE"]["evidence_standard_lowered"] is False


def test_axis_identity_swap_fails_closed():
    """4. axis identity preserved -- a swapped scenario_axis label fails closed."""
    raw = _artifact()
    raw["scenario_context"]["axes"]["CONSERVATIVE"]["scenario_axis"] = "BASE"
    bundle = _bundle("AAA", raw)
    assert current_research_scenario_context_contract(bundle, "AAA")["status"] == "malformed"


def test_base_most_likely_flag_cannot_be_stripped_or_borrowed():
    """5. BASE cannot become most-likely -- base_is_not_most_likely must be True only
    on BASE and None everywhere else; either direction of tampering fails closed."""
    stripped = _artifact()
    stripped["scenario_context"]["axes"]["BASE"]["base_is_not_most_likely"] = None
    assert current_research_scenario_context_contract(_bundle("AAA", stripped), "AAA")["status"] == "malformed"

    borrowed = _artifact()
    borrowed["scenario_context"]["axes"]["CONSERVATIVE"]["base_is_not_most_likely"] = True
    assert current_research_scenario_context_contract(_bundle("AAA", borrowed), "AAA")["status"] == "malformed"


def test_speculative_evidence_standard_cannot_be_silently_lowered():
    """6. SPECULATIVE cannot silently lower its evidence standard (the structural
    guardrail underneath 'SPECULATIVE is not a bullish/high-return shortcut')."""
    raw = _artifact()
    raw["scenario_context"]["axes"]["SPECULATIVE"]["evidence_standard_lowered"] = True
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_conservative_material_risk_rule_cannot_be_swapped():
    """7. CONSERVATIVE's material_risk_rule cannot be swapped for the generic
    not-scored rule -- material risk blocking CONSERVATIVE SUPPORTED is structural."""
    raw = _artifact()
    raw["scenario_context"]["axes"]["CONSERVATIVE"]["material_risk_rule"] = "MATERIAL_RISK_LISTED_NOT_SCORED"
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_confirmation_unavailable_remains_unavailable():
    """11. confirmation unavailable remains unavailable -- text stays None; injecting
    text while claiming UNAVAILABLE fails closed."""
    raw = _artifact()
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, _bundle("AAA", raw))
    gate = context["current_research_scenario_context"]["scenario_context"]["axes"]["CONSERVATIVE"]["confirmation_conditions"][0]
    assert gate["status"] == "UNAVAILABLE"
    assert gate["text"] is None

    tampered = _artifact()
    tampered["scenario_context"]["axes"]["CONSERVATIVE"]["confirmation_conditions"] = [
        _gate(status="UNAVAILABLE", text="fabricated confirmation level"),
    ]
    assert current_research_scenario_context_contract(_bundle("AAA", tampered), "AAA")["status"] == "malformed"


def test_invalidation_unavailable_remains_unavailable():
    """12. invalidation unavailable remains unavailable, independent of confirmation."""
    raw = _artifact()
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, _bundle("AAA", raw))
    gate = context["current_research_scenario_context"]["scenario_context"]["axes"]["BASE"]["invalidation_conditions"][0]
    assert gate["status"] == "UNAVAILABLE"
    assert gate["text"] is None

    tampered = _artifact()
    tampered["scenario_context"]["axes"]["BASE"]["invalidation_conditions"] = [
        _gate(status="UNAVAILABLE", text="fabricated invalidation level"),
    ]
    assert current_research_scenario_context_contract(_bundle("AAA", tampered), "AAA")["status"] == "malformed"


def test_invented_gate_fails_closed():
    """A gate ever marked invented=True is a contradiction of the framework's own
    'never invent a confirmation/invalidation condition' rule -- fails closed."""
    raw = _artifact()
    raw["scenario_context"]["axes"]["SPECULATIVE"]["confirmation_conditions"] = [
        _gate(status="AVAILABLE", text="fabricated", invented=True),
    ]
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_evidence_references_independent_source_identities():
    """Evidence references cover all nine independent source identities, each citable
    on its own -- never collapsed into one combined reference."""
    raw = _artifact()
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, _bundle("AAA", raw))
    refs = context["current_research_scenario_context"]["scenario_context"]["axes"]["BASE"]["evidence_references"]
    sources = {ref["source"] for ref in refs}
    assert sources == {
        "official_universe", "tactical", "opportunity", "historical",
        "leadership", "financial", "event", "valuation", "risk_register",
    }
    assert len({ref["identity"] for ref in refs}) == 9


def test_absent_sibling_returns_none():
    """Opt-in field: absent from any bundle that did not request it."""
    assert current_research_scenario_context_contract({"tickers": {"AAA": {}}}, "AAA") is None
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, {"tickers": {"AAA": {}}})
    assert "current_research_scenario_context" not in context


def test_malformed_missing_field_fails_closed():
    raw = _artifact()
    del raw["authority_boundary"]
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, _bundle("AAA", raw))
    assert context["current_research_scenario_context"] == {
        "status": "malformed", "is_actionable": False,
        "reason_codes": ["current_research_scenario_context_malformed"],
    }


def test_polarity_category_mismatch_fails_closed():
    """An OPPOSE-polarity condition placed inside supporting_conditions (or any other
    category/polarity mismatch) is a tampered artifact -- fails closed, mirroring the
    risk register's own category/status cross-check."""
    raw = _artifact()
    raw["scenario_context"]["axes"]["CONSERVATIVE"]["supporting_conditions"] = [
        _condition(condition_id="SECTOR_NOT_LEADING", domain="SECTOR_RELATIVE", polarity="OPPOSE", code="SECTOR_WEAKENING"),
    ]
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_missing_axis_fails_closed():
    """13. axis set must be exactly CONSERVATIVE/BASE/SPECULATIVE -- a dropped axis
    fails closed rather than silently degrading to two."""
    raw = _artifact()
    del raw["scenario_context"]["axes"]["SPECULATIVE"]
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_cross_axis_decision_context_divergence_fails_closed():
    """AXIS ORTHOGONALITY, structurally enforced: every axis must quote the identical
    current_decision_context -- a scenario axis can never carry its own private
    entry_action. A per-axis divergence (e.g. BASE alone claiming a different
    entry_action) fails closed rather than being merged or averaged."""
    raw = _artifact()
    raw["scenario_context"]["axes"]["BASE"]["current_decision_context"] = {
        **raw["scenario_context"]["axes"]["BASE"]["current_decision_context"],
        "entry_action": "BUY_ON_CONFIRMATION",
    }
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_material_risk_item_wrong_status_fails_closed():
    """A WATCH-status item quoted inside an axis's material_risks (which must be
    ESTABLISHED-only, matching the risk register's own material_risks category) fails
    closed -- the same category/status cross-check the risk register enforces."""
    raw = _artifact(axes_overrides={
        "CONSERVATIVE": {"material_risks": [_risk_item(status="WATCH", severity="WATCH")]},
    })
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_blocked_outputs_tampered_fails_closed():
    raw = _artifact()
    raw["blocked_outputs"]["research_priority"] = "MODIFIED"
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"


def test_provenance_and_limitations_recorded():
    """Provenance entry documents the pass-through and its orthogonality limitations."""
    raw = _artifact()
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_scenario_context_contract(context, _bundle("AAA", raw))
    entry = context["provenance"][0]
    assert entry["source_dataset"] == "current_research_scenario_context"
    assert any("never bearish/neutral/bullish" in item for item in entry["limitations"])
    assert any("stays WAIT regardless of any axis's status" in item for item in entry["limitations"])


def test_source_sessions_independent():
    """Source as-of identities remain independent -- historical/valuation differ and
    both are preserved exactly, never unified into one session."""
    raw = _artifact()
    result = current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")
    as_of = result["scenario_context"]["source_as_of"]
    assert as_of["historical"] == "2026-08-24"
    assert as_of["valuation"] == "2026-08-21"
    assert as_of["historical"] != as_of["valuation"]


def test_data_limitation_and_condition_limitation_coexist():
    """15. data limitation remains limitation: authority_limitations legitimately mixes
    Producer's own DATA_AUTHORITY conditions with quoted risk-register data-limitation
    items -- both shapes are valid and neither collapses into the other."""
    raw = _artifact(axes_overrides={
        "BASE": {
            "limitations": [
                _condition(condition_id="SECTOR_CONTEXT_LIMITED", domain="DATA_AUTHORITY", polarity="LIMITATION",
                           code="SECTOR_IDENTITY_UNKNOWN", source_context="current_market_sector_leadership_context:l1"),
                _risk_item(domain="VALUATION_AUTHORITY", risk_type="VALUATION_METRICS_BLOCKED", status="DATA_LIMITATION",
                           severity="DATA_LIMITATION", source_context="market_wide_current_valuation_input_scaleout:v1",
                           authority_tier="CURRENT_VALUATION_RESEARCH"),
            ],
        },
    })
    result = current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")
    limitations = result["scenario_context"]["axes"]["BASE"]["authority_limitations"]
    assert len(limitations) == 2
    assert {item.get("risk_domain") or item.get("domain") for item in limitations} == {"DATA_AUTHORITY", "VALUATION_AUTHORITY"}


def test_ticker_mismatch_in_evidence_fails_closed():
    raw = _artifact(axes_overrides={
        "CONSERVATIVE": {"material_risks": [_risk_item(ticker="BBB")]},
    })
    assert current_research_scenario_context_contract(_bundle("AAA", raw), "AAA")["status"] == "malformed"
