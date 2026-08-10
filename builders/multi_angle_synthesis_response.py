"""Fail-closed response validator for multi-angle AI synthesis outputs.

This module validates structured AI synthesis outputs across multiple analytical lanes
(historical fundamental, current_state_price_analytics, current_state_market_risk,
foreign_flow, corporate intelligence).

It enforces structural category isolation, guards against unauthorized investment
action claims, PIT/backtest proof claims, statistical robustness overclaims, correlation
causality, foreign flow accumulation/volume/room claims, and fabricated unavailable
indicators -- while safely accepting negated safety disclaimers without false positives.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Mapping

_CATEGORIES = (
    "facts",
    "data_warnings",
    "supported_inferences",
    "conflicting_evidence",
    "hypotheses",
    "missing_evidence",
    "invalidation_conditions",
)

_PROHIBITED_TOP_LEVEL_KEYS = {
    "recommendation",
    "rating",
    "score",
    "target_price",
    "position_size",
    "expected_return",
}

# Regexes for affirmative claims that violate safety boundaries (crafted to avoid false positives on negated statements)
_AFFIRMATIVE_RECOMMENDATION_RE = re.compile(
    r"\b(?:we|i)?\s*(?:recommend|issue|give)\s+(?:a\s+)?(?:buy|sell|hold)\b"
    r"|\b(?:is|becomes?)\s+(?:a\s+)?(?:buy|sell|hold)\b"
    r"|\b(?:buy|sell|hold)\s+recommendation\b(?!.*?\b(?:does\s+not|not|cannot|no)\b)"
    r"|\btarget\s+price\s+(?:of|is|\=|\:)\s*\d+"
    r"|\bposition\s+size\s+(?:of|is|\=|\:)\s*\d+%?"
    r"|\bportfolio\s+allocation\s+(?:of|is|\=|\:)\s*\d+%?",
    re.IGNORECASE,
)

_AFFIRMATIVE_PIT_PROOF_RE = re.compile(
    r"\b(?:is|provides?|serves?\s+as|constitutes?)\s+(?:point-in-time\s+)?backtest\s+(?:proof|evidence)\b"
    r"|\bbacktest\s+proof\b"
    r"|\bvalidated\s+trading\s+signal\s+history\b",
    re.IGNORECASE,
)

_AFFIRMATIVE_STATISTICAL_ROBUSTNESS_RE = re.compile(
    r"\b(?:establishes?|proves?|is)\s+statistically\s+robust\b"
    r"|\bstatistically\s+robust\s+beta\b"
    r"|\bstatistically\s+significant\s+beta\b",
    re.IGNORECASE,
)

_AFFIRMATIVE_CORRELATION_CAUSALITY_RE = re.compile(
    r"\bcorrelation\s+(?:proves|implies|causes)\b"
    r"|\bproved?\s+that\s+.*?\s+caused\b"
    r"|\bcorrelation\s+caused\b",
    re.IGNORECASE,
)

_AFFIRMATIVE_FOREIGN_FLOW_OVERCLAIM_RE = re.compile(
    r"\binstitutions?\s+accumulated\b"
    r"|\bforeign\s+(?:buying|flow)\s+caused\b"
    r"|\bforeign\s+volume\s+(?:was|is|\=|\:)\s*\d+"
    r"|\bforeign\s+room\s+(?:is|was|\=|\:)\s*\d+%?"
    r"|\bflow\s*(?:\/|to)\s*turnover\s+ratio\b",
    re.IGNORECASE,
)


def _reject(*reasons: str) -> dict[str, Any]:
    return {
        "status": "rejected",
        "accepted_output": None,
        "reasons": sorted(set(reasons)),
        "multi_angle_synthesis": True,
    }


def validate_multi_angle_synthesis_output(
    response: str | Mapping[str, Any],
    *,
    contract_metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate structured multi-angle AI synthesis output against safety boundaries."""
    if isinstance(response, str):
        try:
            output = json.loads(response)
        except json.JSONDecodeError:
            return _reject("response_not_valid_json")
    else:
        output = response

    if not isinstance(output, Mapping):
        return _reject("response_not_structured_object")

    reasons: list[str] = []

    # 0. Metadata Validation
    meta: dict[str, Any] = {}
    if contract_metadata is not None:
        if not isinstance(contract_metadata, Mapping):
            return _reject("contract_metadata_invalid")
        meta = dict(contract_metadata)
        allowed_meta_keys = {"unavailable_indicators", "requires_conflicting_evidence"}
        unknown_meta = set(meta) - allowed_meta_keys
        if unknown_meta:
            reasons.append("unexpected_contract_metadata_fields:" + ",".join(sorted(unknown_meta)))


        if "unavailable_indicators" in meta and meta["unavailable_indicators"] is not None:
            ind = meta["unavailable_indicators"]
            if not isinstance(ind, (list, tuple)) or any(not isinstance(x, str) or not x.strip() for x in ind):
                reasons.append("contract_metadata_invalid:unavailable_indicators")

        if "requires_conflicting_evidence" in meta and meta["requires_conflicting_evidence"] is not None:
            req = meta["requires_conflicting_evidence"]
            if not isinstance(req, bool):
                reasons.append("contract_metadata_invalid:requires_conflicting_evidence")

    # 1. Structure & Top-Level Key Checks
    unexpected_keys = set(output) - set(_CATEGORIES) - {"ticker", "synthesis_mode", "generated_at"}
    prohibited_keys = set(output) & _PROHIBITED_TOP_LEVEL_KEYS
    if prohibited_keys:
        reasons.append("prohibited_top_level_key:" + ",".join(sorted(prohibited_keys)))
    if unexpected_keys:
        reasons.append("unexpected_response_fields:" + ",".join(sorted(unexpected_keys)))

    for field in _CATEGORIES:
        if field not in output:
            reasons.append(f"missing_category:{field}")
        elif not isinstance(output[field], list):
            reasons.append(f"wrong_category_type:{field}")

    if reasons:
        return _reject(*reasons)

    # 2. Conflicting Evidence Guard
    if meta.get("requires_conflicting_evidence") is True and not output.get("conflicting_evidence"):
        reasons.append("conflicting_evidence_required_but_empty")

    # 3. Missing Indicator Guard (e.g. SMA20 unavailable)
    unavailable_indicators = set(meta.get("unavailable_indicators") or [])
    if "sma_20" in unavailable_indicators:
        rendered_facts = json.dumps(output.get("facts", []), ensure_ascii=False).lower()
        if re.search(r"\bsma20\s*=\s*\d+", rendered_facts) or re.search(r"\bprice\s+is\s+(?:above|below)\s+sma20\b", rendered_facts):
            reasons.append("fabricated_unavailable_sma20_indicator")


    # 4. Hypothesis Discipline in Facts
    facts_text = json.dumps(output.get("facts", []), ensure_ascii=False).lower()
    if "hypothesis:" in facts_text or "unconfirmed hypothesis" in facts_text:
        reasons.append("hypothesis_inserted_into_facts")

    # 5. Item-Level Text Safety Checks (Affirmative Claim vs Negated Disclaimer Detection)
    # Collect all text strings across category lists
    all_text_items: list[str] = []
    for cat in _CATEGORIES:
        for item in output.get(cat, []):
            if isinstance(item, str):
                all_text_items.append(item)

    for item in all_text_items:
        item_lower = item.lower()
        is_negated = any(neg in item_lower for neg in (
            "does not", "not ", "no ", "never", "cannot", "is not",
            "unsupported", "unqualified", "unavailable", "not qualified", "not justify"
        ))

        # A. Recommendation, Target Price, Position Sizing
        if any(kw in item_lower for kw in ("recommend", "buy", "sell", "hold", "target price", "position size", "portfolio allocation", "portfolio weight", "size the position")):
            has_action_claim = bool(re.search(
                r"\b(?:recommend|issue|give)\s+(?:a\s+)?(?:buy|sell|hold)\b"
                r"|\b(?:is|becomes?)\s+(?:a\s+)?(?:buy|sell|hold)\b"
                r"|\b(?:buy|sell|hold)\s+recommendation\b"
                r"|\btarget\s+price\b"
                r"|\bposition\s+size\b"
                r"|\bportfolio\s+allocation\b"
                r"|\bportfolio\s+weight\b"
                r"|\bsize\s+(?:the\s+)?position\b",
                item_lower
            ))
            if has_action_claim and not is_negated:
                reasons.append("prohibited_recommendation_or_action_claim")

        # B. PIT / Backtest Proof
        if any(kw in item_lower for kw in ("backtest", "trading signal history")):
            has_pit_claim = bool(re.search(
                r"\b(?:is|provides?|serves?\s+as|constitutes?)\s+(?:point-in-time\s+)?backtest\s+(?:proof|evidence)\b"
                r"|\bbacktest\s+(?:proof|evidence)\b"
                r"|\bvalidated\s+trading\s+signal\s+history\b",
                item_lower
            ))
            if has_pit_claim and not is_negated:
                reasons.append("prohibited_pit_backtest_proof_claim")

        # C. Statistical Robustness / Significance
        if any(kw in item_lower for kw in ("statistically robust", "statistically significant")):
            if not is_negated:
                reasons.append("prohibited_statistical_robustness_claim")

        # D. Correlation Causality
        if "correlation" in item_lower:
            has_causality = bool(re.search(r"\bcorrelation\s+(?:proves|implies|causes|caused)\b|\bproved?\s+that\s+.*?\s+caused\b", item_lower))
            if has_causality and not is_negated:
                reasons.append("prohibited_correlation_causality_claim")

        # E. Foreign Flow Overclaims (Accumulation, Causal Impact, Volume, Room, Turnover Ratio)
        if any(kw in item_lower for kw in ("accumulat", "foreign buying caused", "foreign flow caused", "causal price impact", "foreign volume", "foreign room", "turnover ratio", "flow to turnover", "flow-to-turnover")):
            has_foreign_overclaim = bool(re.search(
                r"\binstitutions?\s+accumulated\b"
                r"|\baccumulated\s+the\s+stock\b"
                r"|\bforeign\s+(?:buying|flow)\s+caused\b"
                r"|\bcausal\s+price\s+impact\b"
                r"|\bforeign\s+(?:buy\s+|sell\s+|net\s+)?volume\b"
                r"|\bforeign\s+(?:ownership\s+|remaining\s+)?room\b"
                r"|\bflow\s*(?:\/|to)\s*turnover\b",
                item_lower
            ))
            if has_foreign_overclaim and not is_negated:
                reasons.append("prohibited_foreign_flow_overclaim")

    if reasons:
        return _reject(*reasons)

    return {
        "status": "accepted",
        "accepted_output": copy.deepcopy(dict(output)),
        "reasons": [],
        "multi_angle_synthesis": True,
    }

