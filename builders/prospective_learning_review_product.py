"""Reusable retrospective-only product over prospective learning-review envelopes."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from builders.prospective_research_learning_review import (
    CONTRACT_VERSION as REVIEW_CONTRACT_VERSION,
    summarize_learning_reviews,
)
from builders.retrospective_learning_synthesis_response import (
    validate_retrospective_learning_synthesis_output,
)


SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "prospective_learning_review_product/v1"
_AUTHORITY_BOUNDARY = [
    "RETROSPECTIVE_PRODUCT_NOT_CONNECTED_TO_CURRENT_RESEARCH",
    "PRODUCT_CONSUMES_VALIDATED_ATTRIBUTION_AND_REVIEW_ONLY",
    "REVIEWABLE_MEANS_EVIDENCE_PACKAGE_REVIEWABLE_NOT_THESIS_VALIDATED",
    "NOT_WIN_LOSS_CORRECT_WRONG_OR_SCORE",
    "NOT_PROBABILITY_EXPECTED_RETURN_BACKTEST_OR_RECOMMENDATION",
    "NOT_SIZING_STRATEGY_OPTIMIZATION_PIT_OR_RAW_AS_TRADED_AUTHORITY",
]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _identity_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and ":" in value


def _review_errors(review: Any) -> list[str]:
    if not isinstance(review, Mapping):
        return ["review_not_mapping"]
    required = {
        "schema_version", "contract_version", "review_identity", "reviewability",
        "original_research_state", "later_observation", "qualified_observed_comparison",
        "machine_condition_review", "learning_limitations", "provenance", "is_actionable",
    }
    errors = [f"review_missing:{key}" for key in sorted(required - set(review))]
    if errors:
        return errors
    if review.get("contract_version") != REVIEW_CONTRACT_VERSION:
        errors.append("review_contract_version_unsupported")
    if not _identity_string(review.get("review_identity")):
        errors.append("review_identity_malformed")
    if not isinstance(review.get("reviewability"), Mapping) or not isinstance(review["reviewability"].get("status"), str):
        errors.append("review_reviewability_malformed")
    if review.get("original_research_state") is not None and not isinstance(review.get("original_research_state"), Mapping):
        errors.append("review_original_research_state_malformed")
    if review.get("later_observation") is not None and not isinstance(review.get("later_observation"), Mapping):
        errors.append("review_later_observation_malformed")
    if not isinstance(review.get("provenance"), Mapping) or review.get("is_actionable") is not False:
        errors.append("review_provenance_or_authority_malformed")
    return errors


def build_retrospective_ai_input(review: Mapping[str, Any]) -> dict[str, Any]:
    """Provide only review-bound evidence for a future, separately invoked AI call."""
    provenance = review["provenance"]
    return {
        "review_identity": review["review_identity"],
        "ticker": (review.get("original_research_state") or {}).get("ticker"),
        "original_research_state": copy.deepcopy(review.get("original_research_state")),
        "later_observation": copy.deepcopy(review.get("later_observation")),
        "reviewability": copy.deepcopy(review.get("reviewability")),
        "qualified_observed_comparison": copy.deepcopy(review.get("qualified_observed_comparison")),
        "allowed_evidence_references": {
            "known_at_t": list(provenance.get("known_at_t_references") or []),
            "new_after_t": list(provenance.get("new_after_t_references") or []),
        },
        "authority_limitations": copy.deepcopy(review.get("learning_limitations") or []),
        "purpose": "RETROSPECTIVE_EXPLANATION_ONLY_NOT_CURRENT_DECISION_INPUT",
    }


def _record_product_view(review: Mapping[str, Any], ai_response: Mapping[str, Any] | None) -> dict[str, Any]:
    if ai_response is not None:
        validated = validate_retrospective_learning_synthesis_output(ai_response, review)
        if validated["status"] != "accepted":
            raise ValueError("RETROSPECTIVE_AI_RESPONSE_REJECTED:" + ",".join(validated["reasons"]))
        ai_review = {"status": "VALIDATED_RESPONSE_ATTACHED", "response": copy.deepcopy(validated["accepted_output"])}
    else:
        ai_review = {"status": "AI_REVIEW_NOT_SUPPLIED", "input": build_retrospective_ai_input(review)}
    return {
        "review_identity": review["review_identity"],
        "ticker": (review.get("original_research_state") or {}).get("ticker"),
        "original_research_known_at_t": copy.deepcopy(review.get("original_research_state")),
        "later_governed_observation": copy.deepcopy(review.get("later_observation")),
        "reviewability": copy.deepcopy(review.get("reviewability")),
        "qualified_observed_comparison": copy.deepcopy(review.get("qualified_observed_comparison")),
        "evidence_consistent_with_original_research": {
            "status": "NOT_DETERMINISTICALLY_CLASSIFIED", "reason_codes": ["no_thesis_correctness_or_scenario_validation_contract"],
        },
        "evidence_against_or_tension_with_original_research": {
            "status": "NOT_DETERMINISTICALLY_CLASSIFIED", "reason_codes": ["no_thesis_correctness_or_scenario_validation_contract"],
        },
        "still_unresolved": copy.deepcopy(review.get("machine_condition_review")),
        "new_after_t": {
            "later_observation": copy.deepcopy(review.get("later_observation")),
            "evidence_references": list((review.get("provenance") or {}).get("new_after_t_references") or []),
        },
        "authority_limitations": copy.deepcopy(review.get("learning_limitations") or []),
        "provenance": copy.deepcopy(review.get("provenance")),
        "ai_review": ai_review,
    }


def build_learning_review_product(reviews: Sequence[Mapping[str, Any]], *, ai_responses: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    """Create a deterministic, retrospective-only machine-readable review product."""
    ai_responses = ai_responses or {}
    if not isinstance(ai_responses, Mapping):
        raise ValueError("AI_RESPONSES_NOT_MAPPING")
    all_valid_reviews: list[Mapping[str, Any]] = []
    valid_reviews: list[Mapping[str, Any]] = []
    views: list[dict[str, Any]] = []
    ordered_reviews = sorted(
        reviews,
        key=lambda review: (
            str(((review.get("provenance") or {}).get("temporal_link_identity") if isinstance(review, Mapping) else "") or ""),
            str(review.get("review_identity") if isinstance(review, Mapping) else ""),
        ),
    )
    seen_links: set[str] = set()
    for review in ordered_reviews:
        errors = _review_errors(review)
        if errors:
            raise ValueError("LEARNING_REVIEW_INVALID:" + ",".join(errors))
        all_valid_reviews.append(review)
        link = str((review.get("provenance") or {}).get("temporal_link_identity") or review["review_identity"])
        if link in seen_links:
            continue
        seen_links.add(link)
        valid_reviews.append(review)
        views.append(_record_product_view(review, ai_responses.get(review["review_identity"])))
    views.sort(key=lambda item: (str(item.get("ticker") or ""), item["review_identity"]))
    payload = {
        "schema_version": SCHEMA_VERSION,
        "contract_version": CONTRACT_VERSION,
        "product_purpose": "RETROSPECTIVE_RESEARCH_LEARNING_REVIEW_ONLY",
        "cohort_summary": summarize_learning_reviews(all_valid_reviews),
        "records": views,
        "authority_boundary": list(_AUTHORITY_BOUNDARY),
        "is_actionable": False,
    }
    payload["product_identity"] = _identity("prospective_learning_review_product:", payload)
    return payload


def render_learning_review_markdown(product: Mapping[str, Any]) -> str:
    """Render a concise, non-interpretive human brief from the product payload."""
    if not isinstance(product, Mapping) or product.get("contract_version") != CONTRACT_VERSION:
        raise ValueError("LEARNING_REVIEW_PRODUCT_CONTRACT_INVALID")
    summary = product.get("cohort_summary") or {}
    lines = [
        "# Prospective Learning Review Product",
        "",
        f"Product identity: `{product.get('product_identity')}`",
        "",
        "## Cohort summary",
        "",
        f"- Records: {summary.get('total_attribution_records')}",
        f"- Reviewable: {summary.get('reviewable')}",
        f"- Pending: {summary.get('pending')}",
        f"- Blocked or unqualified: {summary.get('blocked_or_unqualified')}",
        f"- Comparison not comparable: {summary.get('comparison_not_comparable')}",
        "",
        "`REVIEWABLE` means the retained evidence package can be reviewed. It does not establish thesis, scenario, or price-performance validation.",
    ]
    for record in product.get("records") or []:
        lines.extend(["", f"## {record.get('ticker') or 'Unknown ticker'}", "", "### ORIGINAL RESEARCH — KNOWN AT T", "", "```json", json.dumps(record.get("original_research_known_at_t"), ensure_ascii=True, sort_keys=True, indent=2), "```"])
        lines.extend(["", "### LATER GOVERNED OBSERVATION", "", "```json", json.dumps(record.get("later_governed_observation"), ensure_ascii=True, sort_keys=True, indent=2), "```"])
        lines.extend(["", "### REVIEWABILITY", "", "```json", json.dumps({"reviewability": record.get("reviewability"), "qualified_observed_comparison": record.get("qualified_observed_comparison")}, ensure_ascii=True, sort_keys=True, indent=2), "```"])
        lines.extend(["", "### EVIDENCE CONSISTENT WITH ORIGINAL RESEARCH", "", "No deterministic thesis-consistency classification is emitted."])
        lines.extend(["", "### EVIDENCE AGAINST / TENSION WITH ORIGINAL RESEARCH", "", "No deterministic thesis-tension classification is emitted."])
        lines.extend(["", "### STILL UNRESOLVED", "", "```json", json.dumps(record.get("still_unresolved"), ensure_ascii=True, sort_keys=True, indent=2), "```"])
        lines.extend(["", "### NEW AFTER T", "", "```json", json.dumps(record.get("new_after_t"), ensure_ascii=True, sort_keys=True, indent=2), "```"])
        lines.extend(["", "### AUTHORITY LIMITATIONS", ""] + [f"- `{item}`" for item in record.get("authority_limitations") or []])
        lines.extend(["", "### PROVENANCE", "", "```json", json.dumps(record.get("provenance"), ensure_ascii=True, sort_keys=True, indent=2), "```"])
    return "\n".join(lines) + "\n"


def write_learning_review_product(json_path: Path, markdown_path: Path, product: Mapping[str, Any]) -> None:
    """Write deterministic product artifacts without silently overwriting different content."""
    json_text = _canonical(product) + "\n"
    markdown_text = render_learning_review_markdown(product)
    for path, content in ((json_path, json_text), (markdown_path, markdown_text)):
        if path.exists() and path.read_text(encoding="utf-8") != content:
            raise ValueError("IMMUTABLE_LEARNING_REVIEW_PRODUCT_CONFLICT:" + str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
