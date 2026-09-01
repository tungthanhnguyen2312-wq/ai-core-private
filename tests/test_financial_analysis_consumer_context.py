from __future__ import annotations

import copy

import pytest

from builders.financial_analysis_consumer_context import (
    FinancialAnalysisConsumerContextError,
    apply_bundle_financial_analysis_v2_contract,
    build_financial_analysis_consumer_context,
    compact_from_ndjson,
    compact_from_named_ticker,
)


def _compact(**changes):
    base = {
        "contract_version": "financial_analysis_compact/v1", "ticker": "AAA", "status": "AVAILABLE",
        "is_actionable": False, "issuer_type": "corporate", "analysis_family": "INDUSTRIAL_FINANCIAL_ANALYSIS",
        "as_of_financial_period": "2026-Q1", "current_research_ready": True,
        "source_context_identity": "financial_analysis_context/v2:source",
        "financial_content_identity": "content", "lineage_ref": "financial_analysis_lineage/v1:source",
        "pit_authority": "NOT_GRANTED", "profitability_state": "PROFITABLE", "margin_state": "UNAVAILABLE",
        "growth_state": "UNAVAILABLE", "cash_conversion_state": "UNAVAILABLE", "balance_sheet_state": "DETERIORATING",
        "capital_efficiency_state": "UNAVAILABLE", "leverage_state": "WORSENING", "resilience_state": "UNAVAILABLE",
        "feature_fitness": {
            "mixed_provider_roa_proxy": {"fitness": "RESEARCH_PROXY", "reason_codes": ["CROSS_PROVIDER_UNRESOLVED_SCALE"]},
            "net_income_sign": {"fitness": "READY", "reason_codes": []},
        },
        "deterministic_positive_evidence": ["AAA: profitable retained net income"], "negative_evidence": [],
        "conflicting_evidence": [], "missing_dimensions": ["fcf:BLOCKED"], "warnings": ["PIT_AUTHORITY_NOT_GRANTED"],
        "valuation_hints": [],
    }
    return base | changes


def test_available_compact_is_qualitative_and_preserves_proxy_boundary():
    context = build_financial_analysis_consumer_context(_compact())
    assert context["availability"] == "AVAILABLE"
    assert context["profitability"]["state"] == "PROFITABLE"
    assert context["research_proxy_features"] == ["mixed_provider_roa_proxy"]
    assert context["is_actionable"] is False
    assert all("reported_value" not in str(value) for value in context.values())
    assert any("RESEARCH_PROXY" in note for note in context["authority_notes"])


def test_absent_is_explicit_coverage_not_financial_weakness():
    context = build_financial_analysis_consumer_context(_compact(status="ABSENT", current_research_ready=False))
    assert context["availability"] == "ABSENT"
    assert context["financial_readiness"] == "UNAVAILABLE"
    assert context["current_financial_weakness"] == []
    assert any("must never be narrated as weak" in note for note in context["authority_notes"])


def test_growth_basis_and_not_applicable_state_are_preserved_without_interpretation():
    context = build_financial_analysis_consumer_context(_compact(
        issuer_type="bank", analysis_family="OTHER_FINANCIAL_LIMITED_ANALYSIS",
        growth_state="UNAVAILABLE", growth_basis="GROWTH_BASE_NON_POSITIVE",
        capital_efficiency_state="NOT_APPLICABLE", resilience_state="UNAVAILABLE",
    ))
    assert context["growth"] == {"state": "UNAVAILABLE", "basis": "GROWTH_BASE_NON_POSITIVE", "reason_codes": []}
    assert context["capital_efficiency"]["state"] == "NOT_APPLICABLE"
    assert context["resilience"]["state"] == "UNAVAILABLE"
    assert "not negative evidence" in context["authority_notes"][1]

    unavailable_basis = build_financial_analysis_consumer_context(_compact(growth_basis=None))
    assert unavailable_basis["growth"]["basis"] is None


def test_malformed_or_raw_financial_input_fails_closed():
    with pytest.raises(FinancialAnalysisConsumerContextError, match="VERSION_UNSUPPORTED"):
        build_financial_analysis_consumer_context(_compact(contract_version="financial_analysis_compact/v99"))
    with pytest.raises(FinancialAnalysisConsumerContextError, match="RAW_VALUES_FORBIDDEN"):
        build_financial_analysis_consumer_context(_compact(features={"reported_value": 10}))


def test_named_bundle_and_ndjson_extractors_preserve_only_requested_ticker():
    aaa, bbb = _compact(), _compact(ticker="BBB", profitability_state="LOSS_MAKING")
    bundle = {"tickers": {"AAA": {"financial_analysis": aaa}, "BBB": {"financial_analysis": bbb}}}
    assert compact_from_named_ticker(bundle, "AAA") == aaa
    assert compact_from_ndjson([{"ticker": "BBB", "financial_analysis": bbb}, {"ticker": "AAA", "financial_analysis": aaa}], "AAA") == aaa
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_financial_analysis_v2_contract(context, copy.deepcopy(bundle))
    assert context["financial_analysis_consumer_context"]["ticker"] == "AAA"
    assert context["financial_analysis_consumer_context"]["profitability"]["state"] == "PROFITABLE"
    primary_session = {"ticker_research_contexts": {"AAA": {"financial_analysis": aaa}}}
    assert compact_from_named_ticker(primary_session, "AAA") == aaa


def test_security_decision_wrapper_preserves_producer_weakness_and_watch_labels():
    compact = _compact()
    bundle = {"tickers": {"AAA": {"financial_analysis": {
        "compact": compact,
        "current_financial_weakness": ["OBSERVED_EQUITY_ASSETS_DETERIORATING"],
        "future_financial_invalidation_watch": ["EQUITY_ASSETS_DETERIORATION_WATCH"],
        "is_actionable": False,
    }}}}
    projected = build_financial_analysis_consumer_context(compact_from_named_ticker(bundle, "AAA"))
    assert projected["current_financial_weakness"] == ["OBSERVED_EQUITY_ASSETS_DETERIORATING"]
    assert projected["future_financial_invalidation_watch"] == ["EQUITY_ASSETS_DETERIORATION_WATCH"]
