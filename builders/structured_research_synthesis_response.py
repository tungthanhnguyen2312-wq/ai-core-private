"""Fail-closed response validator for the structured AI research-synthesis output.

This module validates a structured AI research-synthesis output that explains the
investment case for one ticker (thesis, counter-thesis, historical/valuation context,
catalysts, risks, invalidation, unresolved questions, authority limitations) built from
the qualified context already present in a ticker context package.

This is AI RESEARCH NARRATIVE. It is not a new numerical authority, strategy engine,
ranking engine, probability engine, target-price engine, sizing engine, or replacement
for deterministic Producer decisions -- it may explain an upstream deterministic state,
never mint or upgrade one. Context-aware truth checks (upstream decision quoting,
evidence-reference traceability) require the real ticker context and live in
structured_research_synthesis_boundary.py; this module enforces structure, required
categories, and textual safety independent of context.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Mapping

_STRING_FIELDS = (
    "ticker",
    "analysis_session",
    "synthesis_status",
    "thesis",
    "counter_thesis",
    "historical_context_summary",
    "valuation_context_summary",
)
_LIST_FIELDS = (
    "supporting_evidence",
    "counter_evidence",
    "catalyst_context",
    "risk_context",
    "invalidation_conditions",
    "unresolved_questions",
    "authority_limitations",
    "provenance_references",
)
_REQUIRED_NON_EMPTY_STRING_FIELDS = (
    "ticker", "analysis_session", "thesis", "counter_thesis",
    "historical_context_summary", "valuation_context_summary",
)
_REQUIRED_NON_EMPTY_LIST_FIELDS = ("supporting_evidence", "counter_evidence", "provenance_references")

_ALLOWED_TOP_LEVEL_KEYS = set(_STRING_FIELDS) | set(_LIST_FIELDS) | {"upstream_decision_context", "is_actionable"}

# Deterministic/qualitative uncertainty vocabulary only -- never a synthetic confidence score.
_SYNTHESIS_STATUSES = {
    "EVIDENCE_COMPLETE", "PARTIAL_EVIDENCE", "MATERIAL_UNRESOLVED_DATA",
    "CONFLICTING_EVIDENCE", "AUTHORITY_LIMITED",
}

# Fields the AI may never mint at the top level: these concepts may only appear, quoted
# verbatim from Producer's own deterministic output, inside upstream_decision_context.
_PROHIBITED_TOP_LEVEL_KEYS = {
    "research_priority", "strategy_eligibility", "value_eligibility", "entry_action", "action",
    "probability", "confidence", "confidence_score", "expected_return", "target_price",
    "intrinsic_value", "dcf", "position_size", "position_sizing", "recommendation", "rating",
    "score", "buy_sell",
}

_ALLOWED_CONTRACT_METADATA_KEYS = {
    "expected_ticker",
    "expected_upstream_decision_context",
    "known_evidence_refs",
    "tactical_entry_classifier_status",
    "opportunity_decision_queue_status",
    "historical_context_session",
    "historical_context_status",
    "valuation_context_session",
    "valuation_context_status",
}

_NEGATION_MARKERS = (
    "does not", "not ", "no ", "never", "cannot", "is not",
    "unsupported", "unqualified", "unavailable", "not qualified", "not justify",
)

# Reused/adapted from the proven multi_angle_synthesis_response.py patterns.
_AFFIRMATIVE_RECOMMENDATION_RE = re.compile(
    r"\b(?:we|i)?\s*(?:recommend|issue|give)\s+(?:a\s+)?(?:buy|sell|hold)\b"
    r"|\b(?:is|becomes?)\s+(?:a\s+)?(?:buy|sell|hold)\b"
    r"|\b(?:buy|sell|hold)\s+recommendation\b"
    r"|\btarget\s+price\s+(?:of|is|\=|\:)\s*\d+"
    r"|\bposition\s+size\s+(?:of|is|\=|\:)\s*\d+%?"
    r"|\bportfolio\s+allocation\s+(?:of|is|\=|\:)\s*\d+%?",
    re.IGNORECASE,
)
_AFFIRMATIVE_PROBABILITY_OR_RETURN_RE = re.compile(
    r"\d+(?:\.\d+)?%\s*(?:probability|chance|likelihood|confidence)\b"
    r"|\bprobability\s+of\s+(?:success|profit|a\s+(?:gain|loss))\b"
    r"|\bexpected\s+return\s+(?:of|is|\=|\:)\s*\d"
    r"|\bexpected\s+(?:gain|upside|downside)\s+(?:of|is|\=|\:)\s*\d",
    re.IGNORECASE,
)
_AFFIRMATIVE_VALUATION_OVERCLAIM_RE = re.compile(
    r"\bis\s+(?:currently\s+)?(?:undervalued|overvalued|cheap|expensive|fairly\s+valued)\b"
    r"|\bintrinsic\s+value\s+(?:of|is|\=|\:)\s*\d"
    r"|\bvalue\s+eligib(?:le|ility)\b",
    re.IGNORECASE,
)
# Liquidity/execution-capacity claims are out of scope for this contract entirely (no
# liquidity or traded-value lane is consumed here); guard against the AI inferring one
# anyway, e.g. from price/volume prose it was never given authority over.
_AFFIRMATIVE_CAPACITY_OR_PARTICIPATION_RE = re.compile(
    r"\b(?:sufficient|adequate|enough|strong|limited|weak)\s+(?:liquidity|participation)\s+(?:for|to)\b"
    r"|\bposition(?:[- ]sizing)?\s+capacity\b"
    r"|\bparticipation\s+capacity\b"
    r"|\bcan\s+(?:absorb|support)\s+(?:a\s+)?(?:large\s+)?(?:order|position|size)\b"
    r"|\bexecution\s+capacity\b",
    re.IGNORECASE,
)


def _reject(*reasons: str) -> dict[str, Any]:
    return {
        "status": "rejected",
        "accepted_output": None,
        "reasons": sorted(set(reasons)),
        "structured_research_synthesis": True,
    }


def _collect_all_text(output: Mapping[str, Any]) -> list[str]:
    items: list[str] = []
    for field in _STRING_FIELDS:
        value = output.get(field)
        if isinstance(value, str):
            items.append(value)
    for field in _LIST_FIELDS:
        for item in output.get(field) or []:
            if isinstance(item, str):
                items.append(item)
    return items


def validate_structured_research_synthesis_output(
    response: str | Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a structured AI research-synthesis output against safety boundaries."""
    if isinstance(response, str):
        try:
            output = json.loads(response)
        except json.JSONDecodeError:
            return _reject("response_not_valid_json")
    else:
        output = response

    if not isinstance(output, Mapping):
        return _reject("response_not_structured_object")

    meta: dict[str, Any] = {}
    if contract_metadata is not None:
        if not isinstance(contract_metadata, Mapping):
            return _reject("contract_metadata_invalid")
        meta = dict(contract_metadata)
        unexpected_meta = set(meta) - _ALLOWED_CONTRACT_METADATA_KEYS
        if unexpected_meta:
            return _reject("unexpected_contract_metadata_fields:" + ",".join(sorted(unexpected_meta)))

    reasons: list[str] = []

    # 1. Structure & top-level key checks
    prohibited_present = set(output) & _PROHIBITED_TOP_LEVEL_KEYS
    if prohibited_present:
        reasons.append("prohibited_top_level_key:" + ",".join(sorted(prohibited_present)))
    unexpected = set(output) - _ALLOWED_TOP_LEVEL_KEYS
    if unexpected:
        reasons.append("unexpected_response_fields:" + ",".join(sorted(unexpected)))

    for field in _STRING_FIELDS:
        if field not in output:
            reasons.append(f"missing_field:{field}")
        elif not isinstance(output[field], str):
            reasons.append(f"wrong_field_type:{field}")

    for field in _LIST_FIELDS:
        if field not in output:
            reasons.append(f"missing_category:{field}")
        elif not isinstance(output[field], list) or not all(isinstance(x, str) for x in output[field]):
            reasons.append(f"wrong_category_type:{field}")

    if "upstream_decision_context" not in output:
        reasons.append("missing_field:upstream_decision_context")
    elif not isinstance(output["upstream_decision_context"], Mapping):
        reasons.append("wrong_field_type:upstream_decision_context")

    if "is_actionable" not in output:
        reasons.append("missing_field:is_actionable")
    elif output["is_actionable"] is not False:
        reasons.append("is_actionable_must_be_false")

    if reasons:
        return _reject(*reasons)

    # 2. Required-content checks (counter-thesis is mandatory, not optional boilerplate)
    for field in _REQUIRED_NON_EMPTY_STRING_FIELDS:
        if not output[field].strip():
            reasons.append(f"empty_required_field:{field}")
    for field in _REQUIRED_NON_EMPTY_LIST_FIELDS:
        if not output[field]:
            reasons.append(f"empty_required_category:{field}")
    if output.get("synthesis_status") not in _SYNTHESIS_STATUSES:
        reasons.append("invalid_synthesis_status")

    if reasons:
        return _reject(*reasons)

    # 3. Context-derived truth checks (only run when the boundary supplied the truth)
    expected_ticker = meta.get("expected_ticker")
    if isinstance(expected_ticker, str) and output["ticker"] != expected_ticker:
        reasons.append("ticker_mismatch")

    if "expected_upstream_decision_context" in meta:
        if output["upstream_decision_context"] != meta["expected_upstream_decision_context"]:
            reasons.append("upstream_decision_context_mismatch")

    known_refs = meta.get("known_evidence_refs")
    if isinstance(known_refs, (list, set, tuple)):
        unknown = set(output["provenance_references"]) - set(known_refs)
        if unknown:
            reasons.append("unknown_evidence_reference:" + ",".join(sorted(unknown)))

    if reasons:
        return _reject(*reasons)

    # 4. Item-level textual safety checks (affirmative claim vs. negated disclaimer)
    for item in _collect_all_text(output):
        item_lower = item.lower()
        is_negated = any(neg in item_lower for neg in _NEGATION_MARKERS)

        if any(kw in item_lower for kw in (
            "recommend", "buy", "sell", "hold", "target price", "position size", "portfolio allocation",
        )):
            if _AFFIRMATIVE_RECOMMENDATION_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_recommendation_or_action_claim")

        if any(kw in item_lower for kw in (
            "probability", "chance", "likelihood", "confidence",
            "expected return", "expected gain", "expected upside", "expected downside",
        )):
            if _AFFIRMATIVE_PROBABILITY_OR_RETURN_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_probability_or_expected_return_claim")

        if any(kw in item_lower for kw in (
            "undervalued", "overvalued", "cheap", "expensive", "fairly valued",
            "intrinsic value", "value eligib",
        )):
            if _AFFIRMATIVE_VALUATION_OVERCLAIM_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_valuation_overclaim")

        if any(kw in item_lower for kw in (
            "participation", "capacity", "absorb", "liquidity",
        )):
            if _AFFIRMATIVE_CAPACITY_OR_PARTICIPATION_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_capacity_or_participation_claim")

    if reasons:
        return _reject(*reasons)

    return {
        "status": "accepted",
        "accepted_output": copy.deepcopy(dict(output)),
        "reasons": [],
        "structured_research_synthesis": True,
    }
