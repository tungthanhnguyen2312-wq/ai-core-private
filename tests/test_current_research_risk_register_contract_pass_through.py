"""Contract regressions for the current research risk register pass-through."""
from __future__ import annotations

import copy

from builders.build_ticker_context import (
    apply_bundle_current_research_risk_register_contract,
    current_research_risk_register_contract,
)

# TEST_FIXTURE_ONLY -- shape verified against stock-core-private commit 188b5ce
# (current_research_risk_register.py build_artifact()/_item()/_financial_items()/
# _leadership_items()/_valuation_items()/_event_items(), export_ai_bundle.py
# attach_current_research_risk_register()), read via `git show` at that pinned
# revision, not the (concurrently writable) working tree.
_FORBIDDEN_USES = (
    "numeric_risk_score", "risk_adjusted_return", "expected_loss", "VaR", "probability",
    "position_size", "participation_cap", "recommendation", "strategy_eligibility",
    "research_priority", "entry_action", "VALUE", "daily_decision_queue",
)
_SOURCE_CONTEXTS = {
    "historical": {"artifact_identity": "market_wide_historical_research_context:h1", "as_of": "2026-08-24", "available": True},
    "leadership": {"artifact_identity": "current_market_sector_leadership_context:l1", "as_of": "2026-08-25", "available": True},
    "financial": {"artifact_identity": "current_financial_momentum_context:f1", "as_of": "2026-08-24", "available": True},
    "event": {"artifact_identity": "current_corporate_event_context:e1", "as_of": "2026-08-21", "available": True},
    "valuation": {"artifact_identity": "market_wide_current_valuation_input_scaleout:v1", "as_of": "2026-08-21", "available": True},
}
_BLOCKED_OUTPUTS = {use: "NOT_EMITTED_OR_MODIFIED" for use in _FORBIDDEN_USES}
_AUTHORITY_BOUNDARY = {
    "is_actionable": False, "no_numeric_risk_score": True, "absence_is_not_low_risk": True,
    "data_limitation_is_not_economic_risk": True, "source_sessions_preserved_independently": True,
    "no_upstream_decision_mutation": True, "no_sizing_or_participation": True,
    "raw_as_traded": "NOT_PROMOTED", "pit": "BLOCKED",
}


def _item(*, ticker="AAA", domain="FINANCIAL", risk_type="FINANCIAL_STRESS", status="ESTABLISHED",
          severity="MATERIAL", source_context="current_financial_momentum_context:f1",
          source_as_of="2026-08-24", facts=None, reasons=None, authority_tier="OFFICIAL_QUALIFIED"):
    return {
        "risk_id": f"{ticker}:{domain}:{risk_type}",
        "risk_domain": domain, "risk_type": risk_type, "status": status, "severity_band": severity,
        "source_context": source_context, "source_as_of": source_as_of,
        "observed_facts": facts if facts is not None else {"financial_momentum_state": "LOSS_MAKING_OR_STRESSED"},
        "reason_codes": reasons if reasons is not None else ["LOSS"],
        "authority_tier": authority_tier,
        "allowed_uses": ["CURRENT_RESEARCH_CONTEXT"], "prohibited_uses": list(_FORBIDDEN_USES),
    }


def _risk_register(*, ticker="AAA", material=None, watch=None, limitations=None, conflicts=None):
    material = material if material is not None else []
    watch = watch if watch is not None else []
    limitations = limitations if limitations is not None else []
    conflicts = conflicts if conflicts is not None else []
    return {
        "ticker": ticker, "material_risks": material, "watch_risks": watch,
        "data_authority_limitations": limitations, "unresolved_conflicts": conflicts,
        "risk_register_status": "MATERIAL_RISKS_ESTABLISHED" if material else "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE",
    }


def _artifact(*, ticker="AAA", risk_register=None, source_contexts=None):
    risk_register = risk_register if risk_register is not None else _risk_register(ticker=ticker)
    return {
        "ticker": ticker,
        "source_artifact_identity": "current_research_risk_register:abc123",
        "source_contexts": copy.deepcopy(source_contexts if source_contexts is not None else _SOURCE_CONTEXTS),
        "risk_register": risk_register,
        "authority_boundary": copy.deepcopy(_AUTHORITY_BOUNDARY),
        "blocked_outputs": copy.deepcopy(_BLOCKED_OUTPUTS),
        "is_actionable": False,
    }


def _bundle(ticker, raw):
    return {"tickers": {ticker: {"current_research_risk_register": raw}}}


def test_valid_material_risk_passes():
    """1. valid material risk survives."""
    item = _item(domain="FINANCIAL", risk_type="FINANCIAL_STRESS", status="ESTABLISHED", severity="MATERIAL")
    raw = _artifact(risk_register=_risk_register(material=[item]))
    bundle = _bundle("AAA", raw)
    assert current_research_risk_register_contract(bundle, "AAA") == raw
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_risk_register_contract(context, bundle)
    result = context["current_research_risk_register"]
    assert result["risk_register"]["material_risks"][0]["risk_type"] == "FINANCIAL_STRESS"
    assert result["risk_register"]["risk_register_status"] == "MATERIAL_RISKS_ESTABLISHED"
    assert "entry_action" not in result
    assert "research_priority" not in result


def test_valid_watch_risk_passes():
    """2. valid watch risk survives."""
    item = _item(domain="PRICE_TECHNICAL", risk_type="ELEVATED_HISTORICAL_VOLATILITY_REGIME", status="WATCH",
                 severity="WATCH", source_context="market_wide_historical_research_context:h1")
    raw = _artifact(risk_register=_risk_register(watch=[item]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_risk_register_contract(context, _bundle("AAA", raw))
    result = context["current_research_risk_register"]["risk_register"]
    assert result["watch_risks"][0]["status"] == "WATCH"
    assert result["risk_register_status"] == "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE"


def test_data_limitation_remains_limitation():
    """3. data limitation remains limitation, distinct list from risks."""
    item = _item(domain="DATA_AUTHORITY", risk_type="SECTOR_CONTEXT_UNAVAILABLE", status="DATA_LIMITATION",
                 severity="DATA_LIMITATION", source_context="current_market_sector_leadership_context:l1",
                 facts={"sector_status": "UNAVAILABLE", "reason": "SECTOR_IDENTITY_UNKNOWN"},
                 reasons=["SECTOR_IDENTITY_UNKNOWN"])
    raw = _artifact(risk_register=_risk_register(limitations=[item]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_risk_register_contract(context, _bundle("AAA", raw))
    result = context["current_research_risk_register"]["risk_register"]
    assert result["data_authority_limitations"][0]["risk_type"] == "SECTOR_CONTEXT_UNAVAILABLE"
    assert result["material_risks"] == []
    assert result["watch_risks"] == []


def test_conflict_remains_conflict():
    """4. conflict remains conflict -- severity_band is legitimately None for conflicts."""
    item = _item(domain="CORPORATE_EVENT", risk_type="EVENT_EVIDENCE_CONFLICT", status="UNRESOLVED_CONFLICT",
                 severity=None, source_context="current_corporate_event_context:e1",
                 facts={"conflicting_count": 1}, reasons=["CONFLICTING_EVIDENCE"],
                 authority_tier="CONFLICTING_EVIDENCE")
    raw = _artifact(risk_register=_risk_register(conflicts=[item]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_risk_register_contract(context, _bundle("AAA", raw))
    result = context["current_research_risk_register"]["risk_register"]["unresolved_conflicts"][0]
    assert result["status"] == "UNRESOLVED_CONFLICT"
    assert result["severity_band"] is None


def test_no_material_risk_established_status_preserved():
    """5. no-material-risk-established status is preserved exactly, distinct from any
    'low risk' claim -- Consumer never invents or renames this status."""
    raw = _artifact(risk_register=_risk_register())
    bundle = _bundle("AAA", raw)
    result = current_research_risk_register_contract(bundle, "AAA")
    assert result["risk_register"]["risk_register_status"] == "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE"
    assert result["risk_register"]["material_risks"] == []


def test_blocked_valuation_authority_is_limitation():
    """6. blocked valuation authority is a data limitation, not an expensive/cheap claim."""
    item = _item(domain="VALUATION_AUTHORITY", risk_type="VALUATION_METRICS_BLOCKED", status="DATA_LIMITATION",
                 severity="DATA_LIMITATION", source_context="market_wide_current_valuation_input_scaleout:v1",
                 facts={"metric_status_counts": {"BLOCKED": 2}}, reasons=["PER_METRIC_BLOCKED_STATUS_PRESERVED"],
                 authority_tier="CURRENT_VALUATION_RESEARCH")
    raw = _artifact(risk_register=_risk_register(limitations=[item]))
    bundle = _bundle("AAA", raw)
    result = current_research_risk_register_contract(bundle, "AAA")
    assert result["risk_register"]["data_authority_limitations"][0]["risk_domain"] == "VALUATION_AUTHORITY"


def test_unknown_sector_is_data_limitation_not_sector_risk():
    """7. unknown sector is a data/authority limitation, not an economic sector risk."""
    item = _item(domain="DATA_AUTHORITY", risk_type="SECTOR_CONTEXT_UNAVAILABLE", status="DATA_LIMITATION",
                 severity="DATA_LIMITATION", source_context="current_market_sector_leadership_context:l1",
                 facts={"sector_status": "UNAVAILABLE", "reason": "SECTOR_IDENTITY_UNKNOWN"},
                 reasons=["SECTOR_IDENTITY_UNKNOWN"])
    raw = _artifact(risk_register=_risk_register(limitations=[item]))
    bundle = _bundle("AAA", raw)
    result = current_research_risk_register_contract(bundle, "AAA")
    assert result["risk_register"]["data_authority_limitations"][0]["risk_domain"] == "DATA_AUTHORITY"
    assert result["risk_register"]["watch_risks"] == []
    assert result["risk_register"]["material_risks"] == []


def test_absent_sibling_returns_none():
    """Opt-in field: absent from any bundle that did not request it."""
    assert current_research_risk_register_contract({"tickers": {"AAA": {}}}, "AAA") is None
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_risk_register_contract(context, {"tickers": {"AAA": {}}})
    assert "current_research_risk_register" not in context


def test_malformed_missing_field_fails_closed():
    raw = _artifact()
    del raw["authority_boundary"]
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_risk_register_contract(context, _bundle("AAA", raw))
    assert context["current_research_risk_register"] == {
        "status": "malformed", "is_actionable": False,
        "reason_codes": ["current_research_risk_register_malformed"],
    }


def test_category_status_mismatch_fails_closed():
    """A WATCH-status item placed inside material_risks (or any other category/status
    mismatch) is a tampered/inconsistent artifact -- fails closed."""
    item = _item(status="WATCH", severity="WATCH")
    raw = _artifact(risk_register=_risk_register(material=[item]))
    bundle = _bundle("AAA", raw)
    assert current_research_risk_register_contract(bundle, "AAA")["status"] == "malformed"


def test_risk_register_status_mismatch_fails_closed():
    """Absence of material_risks must exactly match
    NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE; a mismatched status sentinel
    (e.g. claiming MATERIAL_RISKS_ESTABLISHED with an empty list) fails closed --
    the critical absence-is-not-low-risk semantic must never be silently inverted."""
    raw = _artifact(risk_register=_risk_register())
    raw["risk_register"]["risk_register_status"] = "MATERIAL_RISKS_ESTABLISHED"
    bundle = _bundle("AAA", raw)
    assert current_research_risk_register_contract(bundle, "AAA")["status"] == "malformed"


def test_blocked_outputs_tampered_fails_closed():
    raw = _artifact()
    raw["blocked_outputs"]["research_priority"] = "MODIFIED"
    bundle = _bundle("AAA", raw)
    assert current_research_risk_register_contract(bundle, "AAA")["status"] == "malformed"


def test_item_provenance_survives_exactly():
    """12. exact item provenance survives."""
    item = _item(source_context="current_financial_momentum_context:f1", source_as_of="2026-08-24",
                 reasons=["LOSS_MAKING_OR_STRESSED_STATE"])
    raw = _artifact(risk_register=_risk_register(material=[item]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_research_risk_register_contract(context, _bundle("AAA", raw))
    result = context["current_research_risk_register"]["risk_register"]["material_risks"][0]
    assert result["risk_id"] == "AAA:FINANCIAL:FINANCIAL_STRESS"
    assert result["source_context"] == "current_financial_momentum_context:f1"
    assert result["source_as_of"] == "2026-08-24"
    assert result["reason_codes"] == ["LOSS_MAKING_OR_STRESSED_STATE"]
    provenance_entry = context["provenance"][0]
    assert provenance_entry["source_dataset"] == "current_research_risk_register"


def test_source_sessions_independent():
    """13. source sessions remain independent -- historical/valuation as_of differ and
    both are preserved exactly, never unified into one session."""
    raw = _artifact()
    bundle = _bundle("AAA", raw)
    result = current_research_risk_register_contract(bundle, "AAA")
    assert result["source_contexts"]["historical"]["as_of"] == "2026-08-24"
    assert result["source_contexts"]["valuation"]["as_of"] == "2026-08-21"
    assert result["source_contexts"]["historical"]["as_of"] != result["source_contexts"]["valuation"]["as_of"]


def test_risk_id_ticker_mismatch_fails_closed():
    item = _item(ticker="BBB")
    raw = _artifact(risk_register=_risk_register(material=[item]))
    bundle = _bundle("AAA", raw)
    assert current_research_risk_register_contract(bundle, "AAA")["status"] == "malformed"
