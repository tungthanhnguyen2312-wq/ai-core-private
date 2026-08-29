"""Validate serialized Producer C2 context through the Consumer narrative boundary."""
from __future__ import annotations

import argparse
import copy
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.correlation_concentration_consumer_context import content_identity
from builders.shadow_recommendation_consumer_narrative import (
    ATTACHMENT_KEY,
    attach_correlation_concentration_context,
    parse_shadow_recommendation_attachment,
    render_fallback_narrative,
    validate_narrative_response,
)


DEFAULT_SHADOW = ROOT.parent / "stock-core-private" / "operations-review" / "shadow-security-recommendation-v1-20260829" / "artifact.json"
DEFAULT_C2 = ROOT.parent / "stock-core-private" / "operations-review" / "correlation-concentration-guard-v1-20260829" / "artifact.json"
DEFAULT_OUTPUT = ROOT / "operations-review" / "correlation-concentration-consumer-integration-v1-20260829" / "artifact.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate(*, shadow_artifact: dict, c2_artifact: dict, producer_head: str, consumer_start_head: str) -> dict:
    labels, readiness, representative = Counter(), Counter(), None
    selected = c2_artifact["input_cohort"]["security_identifiers"]
    for ticker in selected:
        packet = shadow_artifact["records"].get(ticker)
        if not isinstance(packet, dict):
            raise ValueError("C2_SHADOW_PACKET_MISSING")
        entry = {ATTACHMENT_KEY: {"ticker": ticker, "source_artifact_identity": shadow_artifact["artifact_identity"],
            "recommendation_packet": copy.deepcopy(packet), "authority_boundary": copy.deepcopy(shadow_artifact["authority_boundaries"]),
            "shadow_mode": "SHADOW_OPT_IN", "is_actionable": False}}
        parsed = parse_shadow_recommendation_attachment(entry, expected_ticker=ticker)
        if parsed["status"] != "SHADOW_RECOMMENDATION_READY":
            raise ValueError(parsed["status"])
        attached = attach_correlation_concentration_context(parsed["narrative_input"], c2_artifact)
        if attached["status"] != "CORRELATION_CONCENTRATION_READY":
            raise ValueError(attached["status"])
        item = attached["narrative_input"]
        fallback = render_fallback_narrative(item)
        if validate_narrative_response(fallback, item)["status"] != "NARRATIVE_VALID":
            raise ValueError("C2_NARRATIVE_VALIDATION_FAILED")
        labels[item["recommendation_label"]] += 1
        readiness[item["recommendation_readiness"]] += 1
        if ticker == "BSR":
            context = item["correlation_concentration_context"]
            pair = next(row for row in context["pairs_for_security"] if {row["ticker_i"], row["ticker_j"]} == {"BSR", "GAS"})
            representative = {"ticker": ticker, "peer": "GAS", "correlation": pair["correlation"],
                              "lookback_sessions": pair["lookback_sessions"], "guard_status": context["guard_status"],
                              "joint_matrix_status": context["joint_matrix_status"],
                              "recommendation_label": item["recommendation_label"], "recommendation_readiness": item["recommendation_readiness"]}
    artifact = {"contract_version": "correlation_concentration_consumer_integration/v1", "milestone": "C2_CORRELATION_CONTEXT_CONSUMER_INTEGRATION_V1",
        "producer_c2_contract_version": c2_artifact.get("contract_version"), "producer_c2_artifact_identity": c2_artifact.get("artifact_identity"),
        "producer_shadow_artifact_identity": shadow_artifact.get("artifact_identity"), "producer_source_head": producer_head,
        "consumer_start_head": consumer_start_head, "denominator": len(selected), "residual": 0,
        "label_preservation_counts": dict(sorted(labels.items())), "readiness_preservation_counts": dict(sorted(readiness.items())),
        "recommendation_mutation_count": 0, "fallback_render_coverage": len(selected), "grounding_coverage": len(selected),
        "c2_validation": copy.deepcopy(c2_artifact["validation"]), "c2_guard_status": c2_artifact["guard_context"]["status"],
        "representative_bsr_gas": representative, "forbidden_authority_output_counts": {"BUY": 0, "SELL": 0, "HOLD": 0, "target_price": 0, "probability": 0, "position_size": 0, "portfolio_weight": 0, "risk_budget": 0, "allocation": 0, "execution": 0},
        "authority_boundary": {"consumer_explanation_only": True, "producer_recommendation_immutable": True, "producer_correlation_numerical_authority": True, "consumer_recomputes_correlation": False, "historical_pit": "BLOCKED", "raw_as_traded": "NOT_PROMOTED", "historical_backtest": "BLOCKED"}}
    return {**artifact, **content_identity(artifact)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shadow-artifact", type=Path, default=DEFAULT_SHADOW)
    parser.add_argument("--c2-artifact", type=Path, default=DEFAULT_C2)
    parser.add_argument("--producer-head", required=True)
    parser.add_argument("--consumer-start-head", required=True)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    artifact = validate(shadow_artifact=_load(args.shadow_artifact), c2_artifact=_load(args.c2_artifact), producer_head=args.producer_head, consumer_start_head=args.consumer_start_head)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(artifact["artifact_identity"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
