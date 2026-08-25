"""Fail-closed structured AI explanation boundary for retrospective learning reviews."""
from __future__ import annotations

from typing import Any, Mapping


_CATEGORIES = (
    "original_research_summary", "later_observation_summary", "evidence_consistent_with_original_thesis",
    "evidence_against_original_thesis", "still_unresolved", "learning_takeaways", "authority_limitations",
)
_PROHIBITED = (
    "probability", "expected return", "target price", "intrinsic value", "recommend", "buy", "sell", "hold",
    "position size", "participation", "capacity", "leverage", "research score", "analyst score", "thesis score",
    "strategy score", "win rate", "hit rate", "sharpe", "alpha", "backtest", "statistical significance",
    "model accuracy", "good call", "bad call", "correct", "wrong", " win", " loss", "success", "failure",
)


def validate_retrospective_learning_synthesis_output(output: Any, review: Mapping[str, Any]) -> dict[str, Any]:
    """Accept explanations only when every statement cites allowed, temporally valid refs."""
    reasons: list[str] = []
    if not isinstance(output, Mapping):
        return {"status": "rejected", "reasons": ["response_not_mapping"]}
    if not isinstance(review, Mapping) or not isinstance(review.get("provenance"), Mapping):
        return {"status": "rejected", "reasons": ["learning_review_provenance_malformed"]}
    required = {"ticker", *_CATEGORIES}
    reasons.extend(f"missing_response_field:{field}" for field in sorted(required - set(output)))
    allowed_fields = required | {"schema_version"}
    reasons.extend(f"unexpected_response_field:{field}" for field in sorted(set(output) - allowed_fields))
    known = set(review["provenance"].get("known_at_t_references") or [])
    later = set(review["provenance"].get("new_after_t_references") or [])
    if output.get("ticker") != ((review.get("original_research_state") or {}).get("ticker")):
        reasons.append("response_ticker_mismatch")
    for category in _CATEGORIES:
        statements = output.get(category)
        if not isinstance(statements, list):
            reasons.append(f"response_category_not_list:{category}")
            continue
        for item in statements:
            if not isinstance(item, Mapping) or set(item) != {"statement", "evidence_references"}:
                reasons.append(f"response_statement_shape_malformed:{category}")
                continue
            text, refs = item.get("statement"), item.get("evidence_references")
            if not isinstance(text, str) or not text.strip() or not isinstance(refs, list) or not refs or not all(isinstance(ref, str) for ref in refs):
                reasons.append(f"response_statement_content_malformed:{category}")
                continue
            lowered = text.lower()
            if any(term in lowered for term in _PROHIBITED):
                reasons.append("prohibited_retrospective_claim")
            for ref in refs:
                if ref not in known | later:
                    reasons.append(f"unknown_evidence_reference:{ref}")
                if category == "original_research_summary" and ref not in known:
                    reasons.append("later_evidence_in_original_research_summary")
                if category == "later_observation_summary" and ref not in later:
                    reasons.append("known_at_t_evidence_in_later_observation_summary")
    return {"status": "accepted", "accepted_output": dict(output)} if not reasons else {"status": "rejected", "reasons": sorted(set(reasons))}
