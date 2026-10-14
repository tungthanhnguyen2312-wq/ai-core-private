"""Fail-closed Consumer projection for Producer ``financial_valuation_metric_research/v1``.

The Producer is the sole numerical owner of every ratio and multiple.  Unlike the
qualitative ``financial_analysis_consumer_context/v1`` this adapter carries Producer
values, but only verbatim: Consumer never recalculates ROE, ROA, P/E, P/B, P/S or
EV/EBITDA, never fills a blocked value, and never turns a missing or blocked metric
into investment evidence.  A metric id the Consumer does not know yet still passes
through, but it can never be labelled an exact method value.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from typing import Any, Mapping

CONSUMER_CONTRACT_VERSION = "financial_metric_research_consumer_context/v1"
PRODUCER_CONTRACT_VERSION = "financial_valuation_metric_research/v1"
AVAILABLE = "AVAILABLE"
ABSENT = "ABSENT"
VALUE_FITNESS = frozenset({"READY", "RESEARCH_PROXY", "STALE_BUT_RESEARCH_USABLE"})
NO_VALUE_FITNESS = frozenset({"BLOCKED_BY_EVIDENCE", "NOT_APPLICABLE"})
VALUATION_MULTIPLES = frozenset({
    "P/E", "P/E_TTM", "P/E_REPORTED_PERIOD", "P/B", "P/B_CURRENT_RESEARCH", "P/B_OFFICIAL_RESEARCH",
    "P/S", "P/S_TTM", "P/S_REPORTED_PERIOD", "EV/EBITDA", "EV/EBITDA_CALC_READY",
})
RETURN_RATIOS = frozenset({
    "ROE_AVERAGE_BALANCE", "ROA_AVERAGE_BALANCE", "ROE_END_PERIOD_PROXY", "ROA_END_PERIOD_PROXY",
    "ROA_CROSS_PROVIDER_PROXY", "ROE_REPORTED_PERIOD_END_EQUITY_PROXY",
})
# Methods whose identity is a research basis.  A READY fitness on one of these is
# still a research proxy; it never becomes an exact valuation.
RESEARCH_PROXY_METHODS = frozenset({
    "P/E_REPORTED_PERIOD", "P/B_CURRENT_RESEARCH", "P/B_OFFICIAL_RESEARCH", "P/S_REPORTED_PERIOD",
    "ROE_END_PERIOD_PROXY", "ROA_END_PERIOD_PROXY", "ROA_CROSS_PROVIDER_PROXY", "ROE_REPORTED_PERIOD_END_EQUITY_PROXY",
})
# Scalar Producer fields carried verbatim.  Operand/numerator/source lineage objects stay
# in the Producer artifact and are referenced by its identity, so a prompt cannot rebuild
# a ratio from its operands.
_PASS_THROUGH_FIELDS = (
    "method", "value", "fitness", "producer_fitness", "period_identity", "freshness", "statement_scope",
    "currency", "scale", "share_basis", "denominator_method", "earnings_definition", "equity_definition",
    "formula", "formula_owner", "observation_time", "knowledge_time", "source_context_identity",
    "reason_codes", "limitations", "peer_context", "peer_universe",
)
_LINEAGE_FIELDS = ("source_lineage", "numerator_lineage", "operand_lineage")
PROHIBITED_RECALCULATION = ("ROE", "ROA", "P/E", "P/B", "P/S", "EV/EBITDA")
RESEARCH_USE_RESTRICTIONS = (
    "CONSUMER_DOES_NOT_RECALCULATE_PRODUCER_METRICS",
    "RESEARCH_PROXY_IS_NOT_EXACT_VALUATION",
    "BLOCKED_OR_MISSING_METRIC_IS_NOT_EVIDENCE",
    "NO_INVESTMENT_CONCLUSION_FROM_METRIC_AVAILABILITY",
    "CURRENT_RESEARCH_ONLY_NOT_PIT_NOT_FOR_EXECUTION",
)


class FinancialMetricResearchConsumerContextError(ValueError):
    """Raised when a supplied Producer metric-research payload is not safe to consume."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise FinancialMetricResearchConsumerContextError(reason)


def _producer_digest(payload: Mapping[str, Any]) -> str:
    """Recompute the Producer's own content digest; this checks identity, not any ratio."""
    body = {key: value for key, value in payload.items() if key not in {"artifact_sha256", "artifact_identity"}}
    try:
        text = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise FinancialMetricResearchConsumerContextError("FINANCIAL_METRIC_RESEARCH_NOT_CANONICAL_JSON") from exc
    return hashlib.sha256(text.encode()).hexdigest()


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _metric_family(metric_id: str) -> str:
    if metric_id in VALUATION_MULTIPLES:
        return "VALUATION_MULTIPLE"
    if metric_id in RETURN_RATIOS:
        return "RETURN_RATIO"
    return "UNCLASSIFIED_PRODUCER_METRIC"


def _value_class(metric_id: str, fitness: str) -> str:
    if fitness in NO_VALUE_FITNESS:
        return "NO_VALUE"
    known = metric_id in VALUATION_MULTIPLES or metric_id in RETURN_RATIOS
    if fitness == "READY" and known and metric_id not in RESEARCH_PROXY_METHODS:
        return "EXACT_METHOD_VALUE"
    return "RESEARCH_PROXY"


def _metric(ticker: str, metric_id: str, metric: Any, artifact_identity: str) -> dict[str, Any]:
    _require(isinstance(metric, Mapping), "FINANCIAL_METRIC_NOT_OBJECT:" + metric_id)
    _require(metric.get("metric_id") == metric_id and metric.get("ticker") == ticker, "FINANCIAL_METRIC_IDENTITY_MISMATCH:" + metric_id)
    _require(metric.get("is_actionable") is False, "FINANCIAL_METRIC_ACTIONABILITY_MUST_BE_FALSE:" + metric_id)
    fitness = metric.get("fitness")
    _require(fitness in VALUE_FITNESS | NO_VALUE_FITNESS, "FINANCIAL_METRIC_FITNESS_UNSUPPORTED:" + metric_id)
    value = metric.get("value")
    if fitness in VALUE_FITNESS:
        _require(_finite_number(value), "FINANCIAL_METRIC_VALUE_NOT_FINITE:" + metric_id)
        _require(isinstance(metric.get("period_identity"), list) and isinstance(metric.get("freshness"), Mapping),
                 "FINANCIAL_METRIC_TEMPORAL_FITNESS_MISSING:" + metric_id)
    else:
        # A value beside a blocked fitness is a Producer contract violation; refusing it
        # keeps a blocked number out of any prompt.
        _require(value is None, "FINANCIAL_METRIC_INELIGIBLE_VALUE_PRESENT:" + metric_id)
    out: dict[str, Any] = {"metric_id": metric_id, "metric_family": _metric_family(metric_id),
                           "value_class": _value_class(metric_id, fitness)}
    for field in _PASS_THROUGH_FIELDS:
        if field in metric:
            out[field] = copy.deepcopy(metric[field])
    if fitness in NO_VALUE_FITNESS and not out.get("reason_codes"):
        out["reason_codes"] = ["PRODUCER_BLOCKER_REASON_NOT_SUPPLIED"]
    out["lineage_ref"] = {"artifact_identity": artifact_identity, "ticker": ticker, "metric_id": metric_id,
                          "retained_fields": [name for name in _LINEAGE_FIELDS if name in metric]}
    out["is_actionable"] = False
    return out


def build_financial_metric_research_consumer_context(payload: Mapping[str, Any] | None, ticker: str, *,
                                                     session: str | None = None) -> dict[str, Any]:
    """Project one ticker from a Producer metric-research payload, values unchanged.

    ``None`` (the Producer did not publish the opt-in member) and a ticker outside the
    supplied records are first-class ``ABSENT`` states, never weak or negative evidence.
    """
    _require(isinstance(ticker, str) and bool(ticker), "FINANCIAL_METRIC_RESEARCH_TICKER_REQUIRED")
    base: dict[str, Any] = {
        "contract_version": CONSUMER_CONTRACT_VERSION,
        "producer_contract_version": PRODUCER_CONTRACT_VERSION,
        "ticker": ticker,
        "is_actionable": False,
        "prohibited_recalculation": list(PROHIBITED_RECALCULATION),
        "research_use_restrictions": list(RESEARCH_USE_RESTRICTIONS),
    }
    if payload is None:
        return {**base, "availability": ABSENT, "reason_codes": ["PRODUCER_METRIC_RESEARCH_CONTEXT_NOT_PUBLISHED"]}
    _require(isinstance(payload, Mapping), "FINANCIAL_METRIC_RESEARCH_NOT_OBJECT")
    _require(payload.get("contract_version") == PRODUCER_CONTRACT_VERSION, "FINANCIAL_METRIC_RESEARCH_VERSION_UNSUPPORTED")
    digest = _producer_digest(payload)
    _require(payload.get("artifact_sha256") == digest and payload.get("artifact_identity") == PRODUCER_CONTRACT_VERSION + ":" + digest,
             "FINANCIAL_METRIC_RESEARCH_IDENTITY_MISMATCH")
    boundary = payload.get("authority_boundary")
    _require(isinstance(boundary, Mapping) and boundary.get("is_actionable") is False
             and boundary.get("authority_promoted") is False and boundary.get("numerical_owner") == "Producer",
             "FINANCIAL_METRIC_RESEARCH_AUTHORITY_BOUNDARY_INVALID")
    decision_session = payload.get("decision_session")
    _require(isinstance(decision_session, str) and bool(decision_session), "FINANCIAL_METRIC_RESEARCH_SESSION_MISSING")
    _require(session is None or session == decision_session, "FINANCIAL_METRIC_RESEARCH_SESSION_MISMATCH")
    records = payload.get("records")
    _require(isinstance(records, Mapping), "FINANCIAL_METRIC_RESEARCH_RECORDS_INVALID")
    base["source_identity"] = {
        "artifact_identity": payload["artifact_identity"],
        "source_financial_v2_identity": payload.get("source_financial_v2_identity"),
        "source_valuation_identity": payload.get("source_valuation_identity"),
        "decision_session": decision_session,
    }
    record = records.get(ticker)
    if record is None:
        return {**base, "availability": ABSENT, "reason_codes": ["PRODUCER_METRIC_RESEARCH_TICKER_NOT_IN_RECORDS"]}
    _require(isinstance(record, Mapping) and record.get("ticker") == ticker and record.get("is_actionable") is False
             and isinstance(record.get("metrics"), Mapping), "FINANCIAL_METRIC_RESEARCH_RECORD_INVALID")
    metrics = {mid: _metric(ticker, mid, item, payload["artifact_identity"]) for mid, item in sorted(record["metrics"].items())}
    return {
        **base,
        "availability": AVAILABLE,
        "entity_class": record.get("entity_class"),
        "metrics": metrics,
        "value_metric_ids": [mid for mid, item in metrics.items() if item["value_class"] != "NO_VALUE"],
        "no_value_metric_ids": [mid for mid, item in metrics.items() if item["value_class"] == "NO_VALUE"],
    }
