"""Fail-closed acceptance boundary for historical-only AI structured output.

This module deliberately accepts no free-form response. A valid response is an exact,
typed restatement of the already-qualified brief from the final ticker context; it never
recomputes financial metrics or changes readiness/lane state.
"""

from __future__ import annotations

import copy
import json
import re
from typing import Any, Mapping


_CATEGORIES = (
    "facts", "data_warnings", "supported_inferences", "hypotheses",
    "missing_evidence", "invalidation_conditions",
)
_REQUIRED_WARNINGS = {
    "price_basis_unknown_or_unverified",
    "volume_basis_unknown_or_unverified",
    "current_shares_unqualified",
}
_PROHIBITED = re.compile(
    r"\b(?:buy|sell|hold|recommend(?:ation)?|rank(?:ing)?|target\s+price|valuation|"
    r"market\s*cap(?:italization)?|enterprise\s+value|adjusted[ -]?return|backtest|"
    r"portfolio\s+sizing|momentum|technical\s+claim|catalyst|forecast|management\s+explanation)\b",
    re.IGNORECASE,
)


def _reject(*reasons: str) -> dict[str, Any]:
    return {"status": "rejected", "accepted_output": None, "reasons": sorted(set(reasons)), "historical_only": True}


def validate_historical_only_output(response: str | Mapping[str, Any], canonical_brief: Mapping[str, Any] | None) -> dict[str, Any]:
    """Accept only complete, typed, canonical-brief-equivalent historical output."""
    if not isinstance(canonical_brief, Mapping):
        return _reject("canonical_brief_missing_or_malformed")
    canonical = dict(canonical_brief)
    if canonical.get("historical_only") is not True or not _REQUIRED_WARNINGS <= set(canonical.get("data_warnings") or []):
        return _reject("canonical_brief_not_historical_only_or_missing_persistent_warnings")
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
    for field in _CATEGORIES:
        if field not in output:
            reasons.append(f"missing_category:{field}")
        elif not isinstance(output[field], list):
            reasons.append(f"wrong_category_type:{field}")
    for field in ("ticker", "reporting_period", "statement_scope", "publication_timestamp", "currency", "scale", "provenance_references"):
        if not output.get(field):
            reasons.append(f"missing_historical_metadata:{field}")
        elif output.get(field) != canonical.get(field):
            reasons.append(f"historical_metadata_mismatch:{field}")
    if output.get("historical_only") is not True:
        reasons.append("historical_only_required")
    if output.get("market_dependent") is not False:
        reasons.append("market_dependent_must_be_false")
    unexpected = set(output) - set(canonical)
    if unexpected:
        reasons.append("unexpected_response_fields:" + ",".join(sorted(unexpected)))
    if reasons:
        return _reject(*reasons)
    for field in ("facts", "data_warnings", "supported_inferences", "hypotheses", "missing_evidence", "invalidation_conditions"):
        if output[field] != canonical.get(field):
            reasons.append(f"canonical_mismatch:{field}")
    if not _REQUIRED_WARNINGS <= set(output["data_warnings"]):
        reasons.append("persistent_market_data_warnings_removed")
    rendered = json.dumps(output, ensure_ascii=False, sort_keys=True)
    if _PROHIBITED.search(rendered):
        reasons.append("prohibited_market_or_recommendation_claim")
    if reasons:
        return _reject(*reasons)
    return {"status": "accepted", "accepted_output": copy.deepcopy(dict(output)), "reasons": [], "historical_only": True}
