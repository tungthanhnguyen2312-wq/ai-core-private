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
    "market_context_summary",
    "sector_context_summary",
)
_LIST_FIELDS = (
    "supporting_evidence",
    "counter_evidence",
    "relative_strength_context",
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
    "market_context_summary", "sector_context_summary",
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
    "market_sector_context_session",
    "market_sector_context_status",
    "financial_momentum_context_session",
    "financial_momentum_context_status",
    "corporate_event_context_session",
    "corporate_event_context_status",
    "risk_register_status",
    "risk_register_source_sessions",
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
    r"|\bportfolio\s+allocation\s+(?:of|is|\=|\:)\s*\d+%?"
    # Event-based imperative timing action (e.g. "Buy before the record date."): the
    # declarative "is a buy" alternative above does not catch an imperative verb.
    r"|\b(?:buy|sell)\s+(?:before|ahead\s+of|prior\s+to)\s+(?:the\s+)?(?:record\s+date|ex[- ]?date)\b",
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
# Nothing in this schema computes a single number across lanes (market breadth, sector
# leadership, technical, valuation); guard against the AI inventing one in prose even
# though no numeric score field exists anywhere in the structured output.
_AFFIRMATIVE_COMBINED_SCORE_RE = re.compile(
    r"\b(?:combined|composite|overall|aggregate|blended)\s+(?:score|rating)\b"
    r"|\bscore\s+of\s+\d"
    r"|\b\d+(?:\.\d+)?\s*(?:/|out of)\s*\d+\s*(?:score|rating)\b",
    re.IGNORECASE,
)
# Comparable-period financial momentum (and any other current-research evidence lane) is
# retrospective/current, never forward-looking; guard against the AI projecting it into a
# forecast even though no forecast field exists anywhere in the structured output.
_AFFIRMATIVE_FORECAST_RE = re.compile(
    r"\bwe\s+forecast\b"
    r"|\bis\s+forecast(?:ed)?\s+to\b"
    r"|\bwill\s+likely\s+(?:grow|improve|increase|earn|expand|decline)\b"
    r"|\bproject(?:ed|s)?\s+to\s+(?:grow|improve|increase|earn|expand|decline)\b"
    r"|\bnext\s+(?:year|quarter)(?:'s)?\s+(?:earnings|revenue|margin)\s+(?:will|are\s+expected|is\s+expected)\b",
    re.IGNORECASE,
)
# A corporate event's existence/status is a temporal/evidentiary fact, never a price-
# direction claim; guard against the AI turning a retained event into an implied market
# reaction even though no price-impact field exists anywhere in the structured output.
_AFFIRMATIVE_EVENT_IMPACT_RE = re.compile(
    r"\bbullish\b|\bbearish\b"
    r"|\b(?:positive|negative)\s+(?:price\s+)?reaction\b"
    r"|\bpositive\s+price\s+impact\b|\bnegative\s+price\s+impact\b"
    r"|\b(?:should|will|is\s+(?:likely|expected)\s+to)\s+(?:lift|boost|support|pressure|depress|weigh\s+on|drag\s+down|push\s+up|push\s+down)\s+(?:the\s+)?(?:share\s+)?price\b"
    r"|\b(?:react|reacts|reacted|reacting)\s+(?:positively|negatively)\b",
    re.IGNORECASE,
)
# EVENT_DRIVEN eligibility is a separate deterministic strategy-classification authority
# this contract never consumes; a retained corporate event can never mint or upgrade it.
_AFFIRMATIVE_EVENT_DRIVEN_ELIGIBILITY_RE = re.compile(
    r"\bconfirms?\s+event[_ ]driven\s+eligib\w*\b"
    r"|\bevent[_ ]driven\s+eligib\w*\s+(?:is\s+)?confirmed\b"
    r"|\bqualif(?:y|ies|ied)\s+for\s+event[_ ]driven\b"
    r"|\bevent[_ ]driven\s+strategy\s+eligib\w*\b"
    r"|\b(?:is|becomes?)\s+event[_ ]driven[- ]eligible\b"
    r"|\benables?\s+event[_ ]driven\b",
    re.IGNORECASE,
)
# record_date != ex_date is a binding authority-boundary fact; guard against the AI
# reconstructing a missing ex_date with the "record_date minus one trading day" heuristic
# (or any equivalent inference) that the boundary explicitly forbids.
_AFFIRMATIVE_INFERRED_EX_DATE_RE = re.compile(
    r"\bex[- ]?date\s+(?:is\s+|can\s+be\s+|should\s+be\s+)?(?:estimated|assumed|inferred|likely|probably|approximat\w*|calculated)\b"
    r"|\bex[- ]?date\s*(?:=|is\s+equal\s+to|equals)\s*record[- ]?date\b"
    r"|\b(?:one|1)\s+trading\s+day\s+(?:before|prior\s+to)\s+(?:the\s+)?record\s+date\b"
    r"|\bassum\w*\s+the\s+ex[- ]?date\b",
    re.IGNORECASE,
)
# planned/approved != executed; guard against the AI self-inferring completion from a
# planned/approved record that carries no retained execution evidence.
_AFFIRMATIVE_EVENT_STATUS_INFERENCE_RE = re.compile(
    r"\b(?:should\s+be\s+treated\s+as|can\s+be\s+(?:considered|treated\s+as)|effectively|assume[ds]?\s+(?:to\s+be\s+)?)\s+(?:already\s+)?executed\b"
    r"|\btreat\w*\s+(?:it|this)\s+as\s+executed\b"
    r"|\bassum\w*\s+execution\s+(?:has\s+)?occurr\w*\b",
    re.IGNORECASE,
)
# No numeric/global risk score exists anywhere in this schema (the register keeps
# material/watch/limitation/conflict as separate lists, never an aggregate); guard
# against the AI inventing risk_score/risk_grade/overall_risk-shaped prose.
_AFFIRMATIVE_RISK_SCORE_RE = re.compile(
    r"\brisk\s+score\b"
    r"|\brisk[- ]grade\b"
    r"|\boverall\s+risk\b"
    r"|\brisk\s+rating\b"
    r"|\brisk[- ]adjusted\b",
    re.IGNORECASE,
)
# absence_is_not_low_risk is a binding authority-boundary fact: an empty material_risks
# list means only NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE, never LOW_RISK or
# SAFE -- guard against the AI collapsing "no material risk found" into a safety verdict.
_AFFIRMATIVE_LOW_RISK_OR_SAFE_RE = re.compile(
    r"\blow[- ]risk\b"
    r"|\b(?:is|remains?|considered)\s+safe\b"
    r"|\bsafer\b"
    r"|\bfew(?:er)?\s+risk\s+flags?\s+(?:mean|means|imply|implies|suggest|suggests)\b",
    re.IGNORECASE,
)
# The register never computes a probability, expected loss, or VaR; guard against risk
# evidence being turned into a quantified downside/upside claim (a shape the existing
# probability/expected-return regex does not fully cover, e.g. "N% downside probability").
_AFFIRMATIVE_RISK_QUANTIFICATION_RE = re.compile(
    r"\d+(?:\.\d+)?%\s*(?:downside|upside|probability|chance|likelihood)\b"
    r"|\bprobability\s+of\s+(?:a\s+)?(?:downside|loss|decline|drop)\b"
    r"|\bexpected\s+loss\b"
    r"|\bvalue[- ]at[- ]risk\b|\bVaR\b"
    r"|\brisk[- ]adjusted\s+return\b",
    re.IGNORECASE,
)
# no_upstream_decision_mutation is binding: risk evidence may explain an existing
# deterministic action/priority/eligibility, never claim to override, upgrade, or
# downgrade it -- that claim is prohibited even when the upstream_decision_context field
# itself is untouched, since the false authority claim is the harm.
_AFFIRMATIVE_RISK_OVERRIDE_CLAIM_RE = re.compile(
    r"\brisk\w*\s+(?:register|evidence|context)\s+(?:overrides?|upgrades?|downgrades?|changes?|alters?)\b"
    r"|\boverrides?\s+(?:entry[_ ]action|research[_ ]priority|strategy\s+eligib\w*)\b",
    re.IGNORECASE,
)
# position_size/participation_cap are explicit FORBIDDEN_USES the register never
# authorizes; guard against risk evidence being turned into a sizing/participation
# instruction even when phrased as an inference rather than a bare position_size figure.
_AFFIRMATIVE_RISK_SIZING_INFERENCE_RE = re.compile(
    r"\brisk\w*\s+(?:register|evidence|context)\s+(?:means?|implies?|suggests?|justif(?:y|ies))\s+(?:position\s+siz\w*|sizing|participation)\b"
    r"|\bposition\s+size\s+should\s+be\s+(?:reduced|cut|increased|raised)\b"
    r"|\breduce\s+position\s+size\s+to\s+\d",
    re.IGNORECASE,
)


def _reject(*reasons: str) -> dict[str, Any]:
    return {
        "status": "rejected",
        "accepted_output": None,
        "reasons": sorted(set(reasons)),
        "structured_research_synthesis": True,
    }


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _collect_all_text(output: Mapping[str, Any]) -> list[str]:
    """Split multi-sentence summary strings into sentences before safety scanning.

    A negation earlier in a long summary field (e.g. "...not a trade signal.") must not
    shield an unrelated affirmative claim later in the same field ("...we recommend BUY.")
    -- negation is scoped per sentence, not per field. List-field items are already
    atomic short claims and are used as-is.
    """
    items: list[str] = []
    for field in _STRING_FIELDS:
        value = output.get(field)
        if isinstance(value, str) and value.strip():
            items.extend(sentence for sentence in _SENTENCE_SPLIT_RE.split(value.strip()) if sentence.strip())
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

        if any(kw in item_lower for kw in ("score", "composite", "aggregate", "blended rating")):
            if _AFFIRMATIVE_COMBINED_SCORE_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_combined_score_claim")

        if any(kw in item_lower for kw in ("forecast", "project", "will likely", "next year", "next quarter")):
            if _AFFIRMATIVE_FORECAST_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_forecast_claim")

        if any(kw in item_lower for kw in (
            "bullish", "bearish", "reaction", "price impact", "react",
        )):
            if _AFFIRMATIVE_EVENT_IMPACT_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_event_impact_claim")

        if "event_driven" in item_lower or "event driven" in item_lower:
            if _AFFIRMATIVE_EVENT_DRIVEN_ELIGIBILITY_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_event_driven_eligibility_claim")

        if any(kw in item_lower for kw in ("ex-date", "ex date", "ex_date")):
            if _AFFIRMATIVE_INFERRED_EX_DATE_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_inferred_ex_date_claim")

        if any(kw in item_lower for kw in ("executed", "execution")):
            if _AFFIRMATIVE_EVENT_STATUS_INFERENCE_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_event_status_inference_claim")

        if any(kw in item_lower for kw in ("risk score", "risk grade", "overall risk", "risk rating", "risk-adjusted", "risk adjusted")):
            if _AFFIRMATIVE_RISK_SCORE_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_risk_score_claim")

        if any(kw in item_lower for kw in ("low risk", "low-risk", "safe", "safer")):
            if _AFFIRMATIVE_LOW_RISK_OR_SAFE_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_low_risk_or_safe_claim")

        if any(kw in item_lower for kw in ("downside", "upside", "expected loss", "value at risk", "var", "risk-adjusted", "risk adjusted")):
            if _AFFIRMATIVE_RISK_QUANTIFICATION_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_risk_quantification_claim")

        if any(kw in item_lower for kw in ("overrides", "override", "upgrades", "downgrades")):
            if _AFFIRMATIVE_RISK_OVERRIDE_CLAIM_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_risk_override_claim")

        if any(kw in item_lower for kw in ("position size", "sizing", "participation")):
            if _AFFIRMATIVE_RISK_SIZING_INFERENCE_RE.search(item_lower) and not is_negated:
                reasons.append("prohibited_risk_sizing_inference_claim")

    if reasons:
        return _reject(*reasons)

    return {
        "status": "accepted",
        "accepted_output": copy.deepcopy(dict(output)),
        "reasons": [],
        "structured_research_synthesis": True,
    }
