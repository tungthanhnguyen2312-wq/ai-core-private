"""Replay the real, governed next_session_decision_brief/v1 handoff package through the
Consumer boundary and record the result as retained operations-review evidence."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.next_session_decision_context import (  # noqa: E402
    TRANSITION_SECTIONS,
    build_context,
    load_next_session_decision_package,
)


DEFAULT_HANDOFF_REPO = ROOT.parent / "stocklookup-ai-handoffs"
DEFAULT_BUILD_DIR = (
    DEFAULT_HANDOFF_REPO / "sessions" / "2026-08-28" / "builds"
    / "handoff_build_2be157b332a09b8ce48cf6e84f1091d2bd081704e2456df701fa8580c729eb17"
)
DEFAULT_CURRENT_SESSION = "2026-08-28"
DEFAULT_PREVIOUS_SESSION = "2026-08-27"
DEFAULT_OUTPUT = ROOT / "operations-review" / "next-session-decision-narrative-v1-20260830" / "artifact.json"


def replay(*, build_dir: Path, current_session: str, previous_session: str | None, producer_checkpoint: str | None) -> dict:
    package = load_next_session_decision_package(
        build_dir,
        expected_session=current_session,
        expected_previous_session=previous_session,
        expected_producer_checkpoint=producer_checkpoint,
    )
    context = build_context(package)
    summary = {
        "contract_version": "next_session_decision_context_replay/v1",
        "milestone": "AI_NEXT_SESSION_DECISION_NARRATIVE_V1",
        "consumer_contract_version": context["contract_version"],
        "producer_brief_contract_version": context["identity"]["producer_brief_contract_version"],
        "producer_brief_artifact_identity": context["identity"]["producer_brief_artifact_identity"],
        "consumer_artifact_identity": context["artifact_identity"],
        "current_session": context["identity"]["current_session"],
        "previous_qualified_session": context["identity"]["previous_qualified_session"],
        "producer_checkpoint": context["source_lineage"]["producer_checkpoint"],
        "market_transition": {
            "advance_ratio_direction": context["market_transition"]["transition"]["advance_ratio_direction"],
            "technical_covered_count_previous": context["market_transition"]["transition"]["technical_covered_count_previous"],
            "technical_covered_count_current": context["market_transition"]["transition"]["technical_covered_count_current"],
        },
        "opportunity_transition_counts": {
            "new_entry_relevant": len(context["opportunity_transition"]["new_entry_relevant"]),
            "persisting_entry_relevant": len(context["opportunity_transition"]["persisting_entry_relevant"]),
            "lost_entry_relevant": len(context["opportunity_transition"]["lost_entry_relevant"]),
            "new_high_priority": len(context["opportunity_transition"]["new_high_priority"]),
            "persisting_high_priority": len(context["opportunity_transition"]["persisting_high_priority"]),
            "lost_high_priority": len(context["opportunity_transition"]["lost_high_priority"]),
        },
        "lifecycle_transition": {
            "scope": context["lifecycle_transition"]["scope"],
            "comparable_count": context["lifecycle_transition"]["comparable_count"],
            "denominator": context["lifecycle_transition"]["denominator"],
        },
        "tactical_transition": {
            "scope": context["tactical_transition"]["scope"],
            "gained_confirmation_count": len(context["tactical_transition"]["gained_confirmation"]),
            "retained_confirmation_count": len(context["tactical_transition"]["retained_confirmation"]),
            "lost_confirmation_count": len(context["tactical_transition"]["lost_confirmation"]),
            "current_record_count": context["tactical_transition"]["source_lineage"]["current_record_count"],
        },
        "recommendation_transition": {
            "availability": context["recommendation_transition"]["availability"],
            "reason_codes": context["recommendation_transition"]["reason_codes"],
            "comparable_count": context["recommendation_transition"]["comparable_count"],
        },
        "invalidation_transition": {
            "availability": context["invalidation_transition"]["availability"],
            "reason_codes": context["invalidation_transition"]["reason_codes"],
            "comparable_count": context["invalidation_transition"]["comparable_count"],
        },
        "risk_context": {
            "availability": context["risk_context"]["availability"],
            "reason_codes": context["risk_context"]["reason_codes"],
        },
        "missingness": context["missingness"],
        "transition_sections_present": list(TRANSITION_SECTIONS),
        "authority_effect": "NONE",
        "is_actionable": False,
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD_DIR)
    parser.add_argument("--current-session", default=DEFAULT_CURRENT_SESSION)
    parser.add_argument("--previous-session", default=DEFAULT_PREVIOUS_SESSION)
    parser.add_argument("--producer-checkpoint", default=None)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)

    summary = replay(
        build_dir=args.build_dir,
        current_session=args.current_session,
        previous_session=args.previous_session,
        producer_checkpoint=args.producer_checkpoint,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    import json

    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(summary["consumer_artifact_identity"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
