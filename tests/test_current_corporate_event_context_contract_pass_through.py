"""Contract regressions for the current corporate event context pass-through."""
from __future__ import annotations

import copy

from builders.build_ticker_context import (
    apply_bundle_current_corporate_event_context_contract,
    current_corporate_event_context_contract,
)

# TEST_FIXTURE_ONLY -- shape verified against stock-core-private commit 4e79c61
# (current_corporate_event_context.py build_artifact()/_ticker_summary()/
# _normalize_official_event()/_normalize_supplemental(), export_ai_bundle.py
# build_current_corporate_event_context_for_ticker_safe()), read via `git show` at that
# pinned revision, not the (concurrently writable) working tree.
_FORBIDDEN_USES = (
    "EVENT_DRIVEN_eligibility", "price_impact", "probability", "target",
    "research_priority", "entry_action", "recommendation", "sizing",
)
_BLOCKED_OUTPUTS = {
    "strategy_eligibility": "NOT_MODIFIED", "event_driven_strategy": "NOT_ENABLED_BY_THIS_CONTEXT",
    "research_priority": "NOT_MODIFIED", "entry_action": "NOT_MODIFIED",
}
_AUTHORITY_BOUNDARY = {
    "is_actionable": False,
    "corporate_event_context_is_not_event_driven_eligibility": True,
    "corporate_event_context_is_not_price_impact": True,
    "corporate_event_context_is_not_probability": True,
    "corporate_event_context_is_not_target": True,
    "corporate_event_context_is_not_research_priority": True,
    "corporate_event_context_is_not_entry_action": True,
    "corporate_event_context_is_not_recommendation": True,
    "corporate_event_context_is_not_sizing": True,
    "record_date_is_not_ex_date": True,
    "planned_is_not_executed": True,
    "announcement_is_not_execution": True,
    "ex_date_not_inferred": True,
    "execution_date_not_inferred": True,
    "resulting_shares_not_inferred": True,
    "no_look_ahead": True,
    "no_synthetic_price_adjustment": True,
    "raw_as_traded": "NOT_PROMOTED",
    "pit": "BLOCKED",
    "backtesting": "BLOCKED",
    "frozen_sessions_not_regenerated": ["2026-08-21", "2026-08-24"],
}


def _event(*, ticker="AAA", event_status="CONFIRMED_UPCOMING", status_reason="EX_DATE_ON_OR_AFTER_AS_OF",
           evidence_tier="OFFICIAL_QUALIFIED", event_type="CASH_DIVIDEND",
           record_date="2026-09-03", ex_date="2026-08-28", execution_date=None, effective_date=None,
           published_at="2026-08-10", known_at="2026-08-10", observed_at="2026-08-20",
           announcement_date="2026-08-10", temporal_completeness="COMPLETE",
           conflicts=None, warnings=None, blockers=None,
           materiality_status="PRICE_SHARE_AFFECTING", qualification="EX_DATE_OFFICIAL_QUALIFIED",
           insufficient_for_event_driven=True, event_id="current_corporate_event:test-a"):
    return {
        "ticker": ticker, "event_type": event_type, "event_status": event_status,
        "status_reason": status_reason, "evidence_tier": evidence_tier,
        "source": "hnx_official_rights_event_index/v1", "source_identities": ["src-a"],
        "supporting_evidence": [{"event_id": "official-a", "source": "hnx_official_rights_event_index/v1", "source_identity": "src-a"}],
        "published_at": published_at, "observed_at": observed_at, "known_at": known_at,
        "announcement_date": announcement_date, "record_date": record_date, "ex_date": ex_date,
        "effective_date": effective_date, "execution_date": execution_date,
        "temporal_completeness": temporal_completeness,
        "conflicts": conflicts if conflicts is not None else [],
        "warnings": warnings if warnings is not None else [],
        "blockers": blockers if blockers is not None else [],
        "materiality_status": materiality_status, "qualification": qualification,
        "source_event_id": "official-a", "source_record_identity": "src-a:AAA:CASH_DIVIDEND:1",
        "insufficient_for_event_driven": insufficient_for_event_driven,
        "allowed_uses": ["current_research_context"], "prohibited_uses": list(_FORBIDDEN_USES),
        "event_id": event_id,
    }


def _ticker_context(*, ticker="AAA", events=None, research_session="2026-08-21"):
    events = events if events is not None else [_event(ticker=ticker)]
    return {
        "ticker": ticker, "research_session": research_session, "events": events,
        "confirmed_upcoming_count": sum(e["event_status"] == "CONFIRMED_UPCOMING" for e in events),
        "recent_confirmed_count": sum(e["event_status"] == "CONFIRMED_RECENT" for e in events),
        "executed_count": sum(e["event_status"] == "EXECUTED" for e in events),
        "recent_confirmed_or_executed_count": sum(e["event_status"] in {"CONFIRMED_RECENT", "EXECUTED"} for e in events),
        "planned_unresolved_count": sum(e["event_status"] in {"PLANNED_NOT_EXECUTED", "TEMPORAL_DETAILS_INCOMPLETE"} for e in events),
        "conflicting_count": sum(e["event_status"] == "CONFLICTING_EVIDENCE" for e in events),
        "data_limited_count": sum(e["event_status"] == "DATA_LIMITED" for e in events),
        "temporal_incomplete_count": sum(e["event_status"] == "TEMPORAL_DETAILS_INCOMPLETE" for e in events),
        "qualified_event_count": sum(e["evidence_tier"] == "OFFICIAL_QUALIFIED" for e in events),
        "has_qualified_event": bool(events),
        "does_not_enable_event_driven": True,
        "allowed_uses": ["current_research_context"], "prohibited_uses": list(_FORBIDDEN_USES),
    }


def _artifact(*, ticker="AAA", ticker_context=None, status="available", research_session="2026-08-21"):
    ticker_context = ticker_context if ticker_context is not None else _ticker_context(ticker=ticker, research_session=research_session)
    return {
        "ticker": ticker, "research_session": research_session, "status": status, "is_actionable": False,
        "source_artifact_identity": "current_corporate_event_context:abc123",
        "research_mode": "CURRENT_RESEARCH_ONLY",
        "ticker_context": ticker_context,
        "coverage": {
            "universe_denominator": 1512, "tickers_with_qualified_event": 1,
            "tickers_with_no_qualified_event": 1511, "deduplicated_event_count": 1,
            "event_type_distribution": {"CASH_DIVIDEND": 1}, "status_distribution": {"CONFIRMED_UPCOMING": 1},
            "evidence_tier_distribution": {"OFFICIAL_QUALIFIED": 1}, "temporal_completeness_distribution": {"COMPLETE": 1},
            "conflict_count": 0, "unresolved_planned_count": 0, "recent_window_days": 30,
            "unexplained_count": 0, "denominator_reconciles": True,
        },
        "blocked_outputs": copy.deepcopy(_BLOCKED_OUTPUTS),
        "authority_boundary": copy.deepcopy(_AUTHORITY_BOUNDARY),
    }


def _bundle(ticker, raw):
    return {"tickers": {ticker: {"current_corporate_event_context": raw}}}


def test_valid_confirmed_upcoming_event_passes():
    """1. valid confirmed-upcoming event passes."""
    raw = _artifact()
    bundle = _bundle("AAA", raw)
    assert current_corporate_event_context_contract(bundle, "AAA") == raw
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, bundle)
    result = context["current_corporate_event_context"]
    assert result["ticker_context"]["events"][0]["event_status"] == "CONFIRMED_UPCOMING"
    assert result["ticker_context"]["events"][0]["ex_date"] == "2026-08-28"
    assert "entry_action" not in result
    assert "research_priority" not in result


def test_valid_executed_event_passes():
    """2. valid executed event passes."""
    event = _event(event_status="EXECUTED", status_reason="EXECUTION_DATE_ON_OR_BEFORE_AS_OF",
                    execution_date="2026-06-20", ex_date="2026-06-01", record_date="2026-06-02")
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    bundle = _bundle("AAA", raw)
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, bundle)
    result = context["current_corporate_event_context"]["ticker_context"]
    assert result["events"][0]["event_status"] == "EXECUTED"
    assert result["events"][0]["execution_date"] == "2026-06-20"
    assert result["executed_count"] == 1


def test_planned_not_executed_stays_planned():
    """3. planned-not-executed stays planned -- Consumer never upgrades it to EXECUTED."""
    event = _event(event_status="PLANNED_NOT_EXECUTED", status_reason="PLANNED_OR_APPROVED_WITHOUT_EXECUTION_EVIDENCE",
                    ex_date=None, execution_date=None, record_date="2026-07-15", temporal_completeness="INCOMPLETE",
                    warnings=["RECORD_DATE_IS_NOT_EX_DATE"])
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, _bundle("AAA", raw))
    result = context["current_corporate_event_context"]["ticker_context"]["events"][0]
    assert result["event_status"] == "PLANNED_NOT_EXECUTED"
    assert result["execution_date"] is None


def test_record_date_only_event_retains_no_ex_date():
    """4. record-date-only event retains no ex-date -- never synthesized."""
    event = _event(event_status="TEMPORAL_DETAILS_INCOMPLETE",
                    status_reason="RECORD_DATE_PRESENT_EX_DATE_ABSENT_NOT_INFERRED",
                    ex_date=None, record_date="2026-07-21", temporal_completeness="INCOMPLETE",
                    warnings=["RECORD_DATE_IS_NOT_EX_DATE"], blockers=["EX_DATE_NOT_INFERRED"])
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, _bundle("AAA", raw))
    result = context["current_corporate_event_context"]["ticker_context"]["events"][0]
    assert result["record_date"] == "2026-07-21"
    assert result["ex_date"] is None
    assert "EX_DATE_NOT_INFERRED" in result["blockers"]


def test_temporal_incomplete_remains_incomplete():
    """5. temporal-incomplete remains incomplete."""
    event = _event(event_status="TEMPORAL_DETAILS_INCOMPLETE", ex_date=None, temporal_completeness="INCOMPLETE")
    ticker_context = _ticker_context(events=[event])
    raw = _artifact(ticker_context=ticker_context)
    bundle = _bundle("AAA", raw)
    assert current_corporate_event_context_contract(bundle, "AAA")["ticker_context"]["temporal_incomplete_count"] == 1
    assert current_corporate_event_context_contract(bundle, "AAA")["ticker_context"]["events"][0]["temporal_completeness"] == "INCOMPLETE"


def test_conflicting_evidence_remains_conflict():
    """6. conflicting evidence remains conflict -- not silently resolved to one date."""
    event = _event(event_status="CONFLICTING_EVIDENCE", ex_date="2026-08-28", record_date="2026-09-03",
                    conflicts=["ex_date"], warnings=["CONFLICTING_QUALIFIED_DATES_NOT_RESOLVED_BY_PREFERENCE"])
    event["source_identities"] = ["hnx-1", "hose-1"]
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, _bundle("AAA", raw))
    result = context["current_corporate_event_context"]["ticker_context"]["events"][0]
    assert result["event_status"] == "CONFLICTING_EVIDENCE"
    assert result["conflicts"] == ["ex_date"]
    assert context["current_corporate_event_context"]["ticker_context"]["conflicting_count"] == 1


def test_cancelled_event_preserved():
    event = _event(event_status="CANCELLED", status_reason="SOURCE_STATUS_CANCELLED", ex_date=None,
                    execution_date=None)
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    bundle = _bundle("AAA", raw)
    assert current_corporate_event_context_contract(bundle, "AAA")["ticker_context"]["events"][0]["event_status"] == "CANCELLED"


def test_absent_sibling_returns_none():
    """Opt-in field: absent from any bundle that did not request it."""
    assert current_corporate_event_context_contract({"tickers": {"AAA": {}}}, "AAA") is None
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, {"tickers": {"AAA": {}}})
    assert "current_corporate_event_context" not in context


def test_session_inconsistent_artifact_fails_closed():
    """8. an artifact whose ticker-level and outer research_session disagree is a
    tampered/inconsistent artifact (Producer always sets both from the same value) --
    fails closed like every other structural inconsistency in this contract, since
    Consumer never parses dates itself to independently verify a look-ahead boundary."""
    raw = _artifact(research_session="2026-08-21")
    raw["ticker_context"]["research_session"] = "2026-08-22"
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, _bundle("AAA", raw))
    assert context["current_corporate_event_context"]["status"] == "malformed"


def test_event_provenance_survives_exactly():
    """9. exact event provenance survives: source, source_identities, supporting_evidence,
    source_event_id, source_record_identity, and event_id are untouched."""
    event = _event()
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, _bundle("AAA", raw))
    result = context["current_corporate_event_context"]["ticker_context"]["events"][0]
    assert result["source"] == "hnx_official_rights_event_index/v1"
    assert result["source_identities"] == ["src-a"]
    assert result["supporting_evidence"] == [{"event_id": "official-a", "source": "hnx_official_rights_event_index/v1", "source_identity": "src-a"}]
    assert result["source_event_id"] == "official-a"
    assert result["source_record_identity"] == "src-a:AAA:CASH_DIVIDEND:1"
    assert result["event_id"] == "current_corporate_event:test-a"
    provenance_entry = context["provenance"][0]
    assert provenance_entry["source_dataset"] == "current_corporate_event_context"


def test_malformed_missing_field_fails_closed():
    raw = _artifact()
    del raw["research_mode"]
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_current_corporate_event_context_contract(context, _bundle("AAA", raw))
    assert context["current_corporate_event_context"] == {
        "status": "malformed", "is_actionable": False,
        "reason_codes": ["current_corporate_event_context_malformed"],
    }


def test_malformed_event_missing_prohibited_use_fails_closed():
    """A sibling that tries to narrow its own prohibited_uses list (e.g. dropping
    EVENT_DRIVEN_eligibility) is malformed, not a valid weaker contract."""
    event = _event()
    event["prohibited_uses"] = [u for u in event["prohibited_uses"] if u != "EVENT_DRIVEN_eligibility"]
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    bundle = _bundle("AAA", raw)
    assert current_corporate_event_context_contract(bundle, "AAA")["status"] == "malformed"


def test_malformed_blocked_outputs_tampered_fails_closed():
    raw = _artifact()
    raw["blocked_outputs"]["entry_action"] = "MODIFIED"
    bundle = _bundle("AAA", raw)
    assert current_corporate_event_context_contract(bundle, "AAA")["status"] == "malformed"


def test_event_ticker_mismatch_fails_closed():
    event = _event(ticker="BBB")
    raw = _artifact(ticker_context=_ticker_context(events=[event]))
    bundle = _bundle("AAA", raw)
    assert current_corporate_event_context_contract(bundle, "AAA")["status"] == "malformed"


def test_data_limited_status_with_no_events_preserved():
    raw = _artifact(ticker="ZZZ", ticker_context=_ticker_context(ticker="ZZZ", events=[]), status="data_limited")
    raw["ticker_context"]["has_qualified_event"] = False
    bundle = _bundle("ZZZ", raw)
    result = current_corporate_event_context_contract(bundle, "ZZZ")
    assert result["status"] == "data_limited"
    assert result["ticker_context"]["events"] == []
