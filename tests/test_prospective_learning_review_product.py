from __future__ import annotations

import copy
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.prospective_learning_review_product import (
    build_learning_review_product,
    render_learning_review_markdown,
    write_learning_review_product,
)
from builders.prospective_research_attribution import build_attribution_record
from builders.prospective_research_learning_review import build_learning_review


def snapshot(**changes):
    value = {
        "ticker": "HPG", "research_session": "2026-08-20",
        "snapshot_identity": "prospective_research_snapshot:hpg-t",
        "source_artifact_identity": "daily_research_product:hpg-t",
        "research_state": {"deterministic_decision_state": {"research_priority": "MONITOR", "entry_action": "WAIT"}},
        "evidence_provenance": [{"identity": "evidence:hpg-t"}],
        "authority_limitations": ["NOT_PIT", "NOT_RAW_AS_TRADED"],
    }
    value.update(changes)
    return value


def outcome(**changes):
    value = {
        "ticker": "HPG", "observation_session": "2026-08-21",
        "observation_identity": "exact_session_observation:hpg-t1",
        "source_artifact_identity": "exact_session_snapshot:hpg-t1",
        "research_snapshot_identity": "prospective_research_snapshot:hpg-t",
        "research_source_artifact_identity": "daily_research_product:hpg-t",
        "observed_fields": {"close": 21000},
        "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": False, "pit_authority": False},
        "evidence_provenance": [{"identity": "evidence:hpg-t1"}],
    }
    value.update(changes)
    return value


def review(**changes):
    record = build_attribution_record(snapshot(**changes), outcome())
    return build_learning_review(record)


def valid_ai_response(review):
    known = review["provenance"]["known_at_t_references"][0]
    later = review["provenance"]["new_after_t_references"][0]
    item = lambda text, refs: {"statement": text, "evidence_references": refs}
    return {
        "ticker": "HPG",
        "original_research_summary": [item("The retained original state is presented.", [known])],
        "later_observation_summary": [item("The retained later observation is presented.", [later])],
        "evidence_consistent_with_original_thesis": [], "evidence_against_original_thesis": [],
        "still_unresolved": [item("Interpretation remains unresolved.", [known, later])],
        "learning_takeaways": [item("Keep the temporal evidence sets separate.", [known, later])],
        "authority_limitations": [item("The observation has no PIT authority.", [known])],
    }


def test_deterministic_json_product_and_markdown_sections():
    product = build_learning_review_product([review()])
    assert product == build_learning_review_product([review()])
    markdown = render_learning_review_markdown(product)
    for heading in ("ORIGINAL RESEARCH — KNOWN AT T", "LATER GOVERNED OBSERVATION", "REVIEWABILITY", "NEW AFTER T", "PROVENANCE"):
        assert heading in markdown
    assert product["records"][0]["reviewability"]["status"] == "REVIEWABLE"
    assert product["records"][0]["qualified_observed_comparison"]["status"] == "NOT_COMPARABLE"


def test_known_at_t_and_new_after_t_are_separate_in_the_product():
    product = build_learning_review_product([review()])
    record = product["records"][0]
    known = record["original_research_known_at_t"]
    new = record["new_after_t"]
    assert known["research_session"] == "2026-08-20"
    assert new["later_observation"]["observation_session"] == "2026-08-21"
    assert new["later_observation"]["observation_identity"] not in record["provenance"]["known_at_t_references"]


def test_pending_and_qualified_metric_behaviors_are_explicit():
    pending = build_learning_review(build_attribution_record(snapshot()))
    pending_product = build_learning_review_product([pending])
    assert pending_product["records"][0]["reviewability"]["status"] == "OUTCOME_PENDING"
    qualified = build_learning_review(build_attribution_record(
        snapshot(price_observation={"observed_fields": {"close": 20000}, "basis": {"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True}}),
        outcome(basis={"price_basis": "ADJUSTED_RETROSPECTIVE", "qualified": True, "pit_authority": False}),
    ))
    product = build_learning_review_product([qualified])
    assert product["records"][0]["qualified_observed_comparison"]["observed_metric"]["simple_price_return"] == pytest.approx(0.05)


def test_product_deduplicates_direct_packet_transport_and_one_blocked_record_does_not_block_valid_record():
    direct = review()
    packet = review(transport="PACKET_SHADOW")
    blocked = build_learning_review(build_attribution_record(snapshot(ticker="SSI", snapshot_identity="prospective_research_snapshot:ssi-t", source_artifact_identity="daily_research_product:ssi-t"), outcome(ticker="SSI", research_snapshot_identity="prospective_research_snapshot:ssi-t", research_source_artifact_identity="daily_research_product:ssi-t", observation_session="2026-08-20")))
    product = build_learning_review_product([packet, blocked, direct])
    assert len(product["records"]) == 2
    assert product["cohort_summary"]["reviewable"] == 1
    assert product["cohort_summary"]["blocked_or_unqualified"] == 1
    assert product["cohort_summary"]["duplicate_transport_records_excluded"] == 1


def test_ai_input_is_exported_without_model_call_and_validated_response_can_attach():
    source_review = review()
    product = build_learning_review_product([source_review])
    assert product["records"][0]["ai_review"]["status"] == "AI_REVIEW_NOT_SUPPLIED"
    assert product["records"][0]["ai_review"]["input"]["purpose"] == "RETROSPECTIVE_EXPLANATION_ONLY_NOT_CURRENT_DECISION_INPUT"
    attached = build_learning_review_product([source_review], ai_responses={source_review["review_identity"]: valid_ai_response(source_review)})
    assert attached["records"][0]["ai_review"]["status"] == "VALIDATED_RESPONSE_ATTACHED"
    bad = valid_ai_response(source_review)
    bad["learning_takeaways"][0]["statement"] = "This has a target price of 30."
    with pytest.raises(ValueError, match="RETROSPECTIVE_AI_RESPONSE_REJECTED"):
        build_learning_review_product([source_review], ai_responses={source_review["review_identity"]: bad})


def test_write_is_deterministic_and_refuses_changed_existing_product(tmp_path):
    product = build_learning_review_product([review()])
    json_path, markdown_path = tmp_path / "product.json", tmp_path / "product.md"
    write_learning_review_product(json_path, markdown_path, product)
    write_learning_review_product(json_path, markdown_path, product)
    changed = copy.deepcopy(product)
    changed["product_purpose"] = "different"
    with pytest.raises(ValueError, match="IMMUTABLE_LEARNING_REVIEW_PRODUCT_CONFLICT"):
        write_learning_review_product(json_path, markdown_path, changed)


def test_product_has_no_scoring_fields_or_current_path_imports():
    product = build_learning_review_product([review()])
    assert not any("score" in key or "win" in key or "rate" in key for key in product["cohort_summary"])
    for path in (
        ROOT / "builders" / "build_ticker_context.py",
        ROOT / "builders" / "structured_research_synthesis_boundary.py",
        ROOT / "builders" / "current_research_packet_shadow_parity.py",
    ):
        assert "prospective_learning_review_product" not in path.read_text(encoding="utf-8")
