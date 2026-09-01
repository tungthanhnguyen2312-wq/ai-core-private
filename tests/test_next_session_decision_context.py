from __future__ import annotations

import copy
import hashlib
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.next_session_decision_context import (  # noqa: E402
    NextSessionDecisionContextError,
    TRANSITION_SECTIONS,
    build_context,
    load_from_handoff_latest,
    load_next_session_decision_package,
)


# Real, retained evidence for the governed 2026-08-27 -> 2026-08-28 session pair, published by
# the Producer's own ai_handoff_publication.py. This is a specific, dated build (not "latest"),
# matching this repository's existing test convention of pinning to retained evidence.
HANDOFF_REPO = ROOT.parent / "stocklookup-ai-handoffs"
REAL_BUILD_DIR = (
    HANDOFF_REPO / "sessions" / "2026-08-28" / "builds"
    / "handoff_build_2be157b332a09b8ce48cf6e84f1091d2bd081704e2456df701fa8580c729eb17"
)
REAL_PRODUCER_CHECKPOINT = "a71d0a143157a114a5deb2ddd1ff1a3f38fe49ad"

_NON_LIVE_VALUE_PATTERN = re.compile(
    r"^(NOT_EMITTED|NOT_APPLICABLE|NOT_ESTABLISHED|NOT_PROMOTED|BLOCKED|UNKNOWN_UNCALIBRATED|UNKNOWN)$"
)
_LIVE_VALUE_KEY_FRAGMENTS = (
    "probability", "target_price", "price_target", "expected_return", "position_siz",
    "portfolio_weight", "allocation", "risk_budget",
)
_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{2}|/)")
_SECRET_KEY_FRAGMENTS = ("password", "secret", "api_key", "apikey", "private_key", "access_token")


def _collect(value: Any, path: str, out: list[tuple[str, Any]], key_fragments: tuple[str, ...]) -> None:
    """Collect (path, value) for keys matching a forbidden fragment.

    Keys prefixed ``no_`` (e.g. ``no_probability``, ``no_target_price``) are this
    repository's own established convention for a boolean *confirming absence* -- the
    opposite polarity of a live value -- and are deliberately excluded here.
    """
    if isinstance(value, dict):
        for key, item in value.items():
            here = f"{path}.{key}"
            key_l = str(key).lower()
            if not key_l.startswith("no_") and any(fragment in key_l for fragment in key_fragments):
                out.append((here, item))
            _collect(item, here, out, key_fragments)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _collect(item, f"{path}[{index}]", out, key_fragments)


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True), encoding="utf-8")


def _minimal_package(
    tmp: Path, *, current_session: str, previous_session: str | None, bundle_payload: Any | None = None,
) -> Path:
    """Write a minimal, internally-consistent synthetic package to ``tmp`` and return its dir."""
    build_dir = tmp / "build"
    build_dir.mkdir(parents=True, exist_ok=True)

    bundle_bytes = json.dumps(
        bundle_payload if bundle_payload is not None else {"note": "synthetic current bundle placeholder"},
        ensure_ascii=False, sort_keys=True,
    ).encode("utf-8")
    (build_dir / "ai_research_session_bundle.json").write_bytes(bundle_bytes)
    bundle_sha256 = _sha256_bytes(bundle_bytes)

    queue_bytes = b'{"note": "synthetic queue placeholder"}'
    (build_dir / "daily_opportunity_decision_queue_artifact.json").write_bytes(queue_bytes)

    operation_identity = "daily_research_session_operation:synthetic-current"
    previous_binding = None
    if previous_session is not None:
        previous_bundle_bytes = b'{"note": "synthetic previous bundle placeholder"}'
        (build_dir / f"previous_session_bundle_{previous_session}.json").write_bytes(previous_bundle_bytes)
        previous_binding = {
            "identity": "daily_research_session_operation:synthetic-previous",
            "sha256": _sha256_bytes(previous_bundle_bytes),
        }

    empty_transition = {"availability": "UNAVAILABLE", "reason_codes": ["NO_PREVIOUS_QUALIFIED_SESSION"]}
    brief_payload = {
        "schema_version": "1.0.0",
        "contract_version": "next_session_decision_brief/v1",
        "current_session": current_session,
        "previous_qualified_session": previous_session,
        "binding": {
            "run_identity": "daily_producer_run:synthetic",
            "run_identity_availability": "AVAILABLE",
            "run_identity_reason_codes": [],
            "operation_identity": operation_identity,
            "current_session_bundle": {"identity": operation_identity, "sha256": bundle_sha256},
            "previous_session_bundle": previous_binding,
        },
        "market_transition": dict(empty_transition, previous=None, current=None, transition=None),
        "sector_transition": dict(empty_transition, sectors={}),
        "opportunity_transition": dict(
            empty_transition,
            new_entry_relevant=[], persisting_entry_relevant=[], lost_entry_relevant=[],
            new_high_priority=[], persisting_high_priority=[], lost_high_priority=[],
            source_lineage={"current_opportunity_decision_queue_identity": "daily_opportunity_decision_queue:synthetic"},
        ),
        "lifecycle": dict(
            empty_transition, denominator=0, comparable_count=0, lifecycle_state_counts={},
            material_change_count=0, tactical_confirmation_transition_counts={}, records={},
            source_lineage={"lifecycle_artifact_identity": "multi_session_thesis_recommendation_lifecycle:synthetic"},
        ),
        "recommendation_transition": dict(empty_transition, comparable_count=0, records={}),
        "invalidation_transition": dict(empty_transition, comparable_count=0, records={}),
        "tactical_transition": dict(
            empty_transition, confirmation_states=["BREAKOUT_READY"],
            gained_confirmation=[], retained_confirmation=[], lost_confirmation=[],
            source_lineage={"current_tactical_artifact_identity": "watchlist_tactical_entry_classifier:synthetic"},
        ),
        "correlation_concentration_context": {
            "availability": "NOT_APPLICABLE",
            "reason_codes": ["NO_QUALIFIED_PAIR_BOUND_C2_ARTIFACT", "ENGINE_REQUIRES_EXPLICIT_SECURITY_SET_AND_LOOKBACK"],
            "engine_contract_version_reference": "correlation_concentration_guard/v1",
        },
        "next_session_watch_conditions": {
            "availability": "UNAVAILABLE", "reason_codes": ["NO_CURRENT_SESSION_TRIGGER_OR_INVALIDATION_TEXT"],
            "conditions": [], "no_forecast": True, "no_probability": True, "no_target_price": True,
        },
        "authority_boundary": {
            "derived_evidence_not_new_factual_authority": True, "supersedes_session_bundle_authority": False,
            "is_actionable": False, "no_forecast": True, "no_probability": True, "no_target_price": True, "no_sizing": True,
        },
    }
    payload_for_hash = {k: v for k, v in brief_payload.items() if k not in {"artifact_sha256", "artifact_identity"}}
    digest = hashlib.sha256(
        json.dumps(payload_for_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    brief_payload["artifact_sha256"] = digest
    brief_payload["artifact_identity"] = f"next_session_decision_brief:{digest}"
    _write_json(build_dir / "next_session_decision_brief.json", brief_payload)

    manifest_payload = {
        "schema_version": "ai_research_bundle_manifest/v1",
        "session": current_session,
        "operation_identity": operation_identity,
        "producer_head": "synthetic0000000000000000000000000000000",
        "source_artifact_identities": {"opportunity_decision_queue": "daily_opportunity_decision_queue:synthetic"},
        "authority_boundary": {"recommendation": "NOT_EMITTED", "probability": "UNKNOWN_UNCALIBRATED"},
        "warnings": [],
    }
    _write_json(build_dir / "ai_research_bundle_manifest.json", manifest_payload)
    return build_dir


@unittest.skipUnless(REAL_BUILD_DIR.is_dir(), "retained real handoff evidence is unavailable")
class RealHandoffReplayTests(unittest.TestCase):
    """Real, governed 2026-08-27 -> 2026-08-28 replay -- exact production numbers."""

    @classmethod
    def setUpClass(cls):
        cls.package = load_next_session_decision_package(
            REAL_BUILD_DIR,
            expected_session="2026-08-28",
            expected_previous_session="2026-08-27",
            expected_producer_checkpoint=REAL_PRODUCER_CHECKPOINT,
        )
        cls.context = build_context(cls.package)

    def test_identity_and_session_ordering(self):
        identity = self.context["identity"]
        self.assertEqual("2026-08-28", identity["current_session"])
        self.assertEqual("2026-08-27", identity["previous_qualified_session"])
        self.assertEqual("next_session_decision_brief/v1", identity["producer_brief_contract_version"])
        self.assertEqual("ai_next_session_decision_context/v1", self.context["contract_version"])

    def test_producer_checkpoint_recorded(self):
        self.assertEqual(REAL_PRODUCER_CHECKPOINT, self.context["source_lineage"]["producer_checkpoint"])
        self.assertEqual(REAL_PRODUCER_CHECKPOINT, self.context["source_lineage"]["producer_head"])

    def test_market_transition_technical_coverage_and_direction(self):
        transition = self.context["market_transition"]["transition"]
        self.assertEqual(838, transition["technical_covered_count_previous"])
        self.assertEqual(942, transition["technical_covered_count_current"])
        self.assertEqual("WEAKENING", transition["advance_ratio_direction"])

    def test_opportunity_transition_preserves_exact_counts(self):
        opportunity = self.context["opportunity_transition"]
        self.assertEqual(65, len(opportunity["new_entry_relevant"]))
        self.assertEqual(48, len(opportunity["persisting_entry_relevant"]))
        self.assertEqual(48, len(opportunity["lost_entry_relevant"]))
        self.assertEqual(33, len(opportunity["new_high_priority"]))
        self.assertEqual(131, len(opportunity["persisting_high_priority"]))
        self.assertEqual(20, len(opportunity["lost_high_priority"]))
        # Byte-for-byte pass-through fidelity: no reinterpretation of Producer's own sets.
        self.assertEqual(self.package["brief"]["opportunity_transition"], opportunity)

    def test_lifecycle_and_tactical_transition_scopes_never_collapse(self):
        lifecycle = self.context["lifecycle_transition"]
        tactical = self.context["tactical_transition"]
        self.assertEqual("SESSION_BUNDLE_COMPARABLE_TICKER_COHORT", lifecycle["scope"])
        self.assertEqual("FULL_MARKET_WATCHLIST_TACTICAL_ENTRY_CLASSIFIER", tactical["scope"])
        self.assertEqual(58, lifecycle["comparable_count"])
        self.assertEqual(1683, tactical["source_lineage"]["current_record_count"])
        self.assertEqual(12, len(tactical["gained_confirmation"]))
        self.assertEqual(5, len(tactical["retained_confirmation"]))
        self.assertEqual(20, len(tactical["lost_confirmation"]))
        # The two scopes must never share a denominator/cohort-size field name/value by accident.
        self.assertNotEqual(lifecycle["comparable_count"], tactical["source_lineage"]["current_record_count"])

    def test_recommendation_and_invalidation_partial_with_missing_previous_context(self):
        for name in ("recommendation_transition", "invalidation_transition"):
            section = self.context[name]
            self.assertEqual("PARTIAL", section["availability"])
            self.assertIn("SOME_COMPARABLE_RECORDS_MISSING_PREVIOUS_OR_CURRENT_CONTEXT", section["reason_codes"])
            self.assertEqual(58, section["comparable_count"])
            # Exact pass-through: Consumer must not reinterpret PARTIAL/MISSING_PREVIOUS_CONTEXT.
            self.assertEqual(self.package["brief"][name], section)
            forbidden = {"UNCHANGED", "NEUTRAL", "WAIT", "SELL"}
            for record in section["records"].values():
                if "MISSING_PREVIOUS_CONTEXT" in record.get("reason_codes", []):
                    self.assertNotIn(record.get("transition"), forbidden)
                    self.assertIsNone(record.get("previous"))

    def test_risk_context_not_applicable_and_no_sizing(self):
        risk = self.context["risk_context"]
        self.assertEqual("NOT_APPLICABLE", risk["availability"])
        self.assertIn("NO_QUALIFIED_PAIR_BOUND_C2_ARTIFACT", risk["reason_codes"])
        for key in ("position_size", "position_sizing", "portfolio_weight", "allocation", "risk_budget", "leverage"):
            self.assertNotIn(key, risk)

    def test_missingness_covers_every_transition_section(self):
        missingness = self.context["missingness"]
        self.assertEqual(set(TRANSITION_SECTIONS) | {"financial_analysis_session_summary"}, set(missingness))
        for name in TRANSITION_SECTIONS:
            self.assertEqual(self.context[name]["availability"], missingness[name]["availability"])
        self.assertEqual("NOT_APPLICABLE", missingness["risk_context"]["availability"])
        self.assertEqual("PARTIAL", missingness["recommendation_transition"]["availability"])
        self.assertIn(
            self.context["financial_analysis_session_summary"]["availability"],
            {"AVAILABLE", "UNAVAILABLE"},
        )

    def test_deterministic_output(self):
        rebuilt = build_context(self.package)
        self.assertEqual(self.context, rebuilt)
        self.assertEqual(self.context["artifact_identity"], rebuilt["artifact_identity"])

    def test_no_live_forbidden_values_and_no_absolute_paths(self):
        serialized = json.dumps(self.context, ensure_ascii=False)
        found_paths: list[str] = []

        def _scan_paths(value, path):
            if isinstance(value, str):
                if _ABSOLUTE_PATH.match(value):
                    found_paths.append(path)
            elif isinstance(value, dict):
                for k, v in value.items():
                    _scan_paths(v, f"{path}.{k}")
            elif isinstance(value, list):
                for i, v in enumerate(value):
                    _scan_paths(v, f"{path}[{i}]")

        _scan_paths(self.context, "$")
        self.assertEqual([], found_paths)

        live_values: list[tuple[str, Any]] = []
        _collect(self.context, "$", live_values, _LIVE_VALUE_KEY_FRAGMENTS)
        for path, value in live_values:
            if isinstance(value, str):
                self.assertTrue(
                    _NON_LIVE_VALUE_PATTERN.match(value) or path.startswith("$.ai_narrative_contract"),
                    f"unexpected live-looking value at {path}: {value!r}",
                )
            elif isinstance(value, bool):
                self.assertFalse(value, f"unexpected True flag at {path}")
            elif isinstance(value, (int, float)):
                self.fail(f"unexpected numeric forbidden-category value at {path}: {value!r}")

        secret_hits: list[tuple[str, Any]] = []
        _collect(self.context, "$", secret_hits, _SECRET_KEY_FRAGMENTS)
        self.assertEqual([], secret_hits)
        self.assertNotIn("BEGIN PRIVATE KEY", serialized)

    def test_watch_conditions_trigger_and_invalidation_distinct(self):
        conditions = self.context["next_session_watch_conditions"]["conditions"]
        self.assertTrue(conditions)
        types = {c["condition_type"] for c in conditions}
        self.assertEqual({"TRIGGER", "INVALIDATION"}, types)
        for condition in conditions:
            if condition["condition_type"] == "TRIGGER":
                self.assertEqual("REEVALUATE_CLASSIFICATION", condition["if_satisfied"])
            else:
                self.assertEqual("FLAG_INVALIDATION", condition["if_satisfied"])

    def test_ai_narrative_contract_declares_all_nine_sections_and_forbidden_outputs(self):
        narrative = self.context["ai_narrative_contract"]
        self.assertEqual(9, len(narrative["required_narrative_sections"]))
        self.assertEqual(["Fact", "Derived", "Inference", "Opinion/scenario"], narrative["evidence_taxonomy"]["categories"])
        self.assertFalse(narrative["is_actionable"])
        for forbidden in ("probabilities", "target_prices", "position_sizing", "allocation_weights"):
            self.assertIn(forbidden, narrative["forbidden_outputs"])


@unittest.skipUnless((HANDOFF_REPO / "LATEST.json").is_file(), "handoff repo LATEST.json is unavailable")
class RealHandoffLatestPointerTests(unittest.TestCase):
    """Structural-only checks via the repo's own LATEST.json (future-proof against a newer session)."""

    def test_load_from_handoff_latest_produces_a_valid_context(self):
        package = load_from_handoff_latest(HANDOFF_REPO)
        context = build_context(package)
        self.assertLess(context["identity"]["previous_qualified_session"] or "", context["identity"]["current_session"])
        for name in TRANSITION_SECTIONS:
            self.assertIn(context[name]["availability"], {"AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_APPLICABLE"})


class SyntheticFailClosedTests(unittest.TestCase):
    """Negative-path fail-closed tests against small synthetic fixtures (never touches real evidence)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmpdir.name)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_missing_package_file_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        (build_dir / "ai_research_bundle_manifest.json").unlink()
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(build_dir, expected_session="2026-09-01")
        self.assertIn("PACKAGE_FILE_MISSING", str(ctx.exception))

    def test_brief_session_mismatch_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(build_dir, expected_session="2026-09-02")
        self.assertIn("BRIEF_SESSION_MISMATCH", str(ctx.exception))

    def test_previous_session_ordering_violation_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session="2026-09-01")
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(
                build_dir, expected_session="2026-09-01", expected_previous_session="2026-09-01",
            )
        self.assertIn("NOT_STRICTLY_BEFORE_CURRENT", str(ctx.exception))

    def test_producer_checkpoint_mismatch_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(
                build_dir, expected_session="2026-09-01", expected_producer_checkpoint="deadbeef" * 5,
            )
        self.assertIn("PRODUCER_CHECKPOINT_MISMATCH", str(ctx.exception))

    def test_bundle_hash_mismatch_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        (build_dir / "ai_research_session_bundle.json").write_bytes(b'{"tampered": true}')
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(build_dir, expected_session="2026-09-01")
        self.assertIn("BUNDLE_HASH_MISMATCH", str(ctx.exception))

    def test_missing_previous_bundle_file_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-02", previous_session="2026-09-01")
        (build_dir / "previous_session_bundle_2026-09-01.json").unlink()
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(
                build_dir, expected_session="2026-09-02", expected_previous_session="2026-09-01",
            )
        self.assertIn("PACKAGE_FILE_MISSING:previous_session_bundle", str(ctx.exception))

    def test_brief_identity_self_inconsistent_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        brief_path = build_dir / "next_session_decision_brief.json"
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        brief["artifact_identity"] = "next_session_decision_brief:not-the-real-digest"
        _write_json(brief_path, brief)
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(build_dir, expected_session="2026-09-01")
        self.assertIn("BRIEF_IDENTITY_SELF_INCONSISTENT", str(ctx.exception))

    def test_brief_semantic_tamper_with_unchanged_declared_identity_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        brief_path = build_dir / "next_session_decision_brief.json"
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        brief["market_transition"]["availability"] = "PARTIAL"
        # Deliberately leave artifact_sha256 and artifact_identity unchanged: direct loading
        # must independently validate the actual Brief content even without LATEST lineage.
        _write_json(brief_path, brief)
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(build_dir, expected_session="2026-09-01")
        self.assertEqual("BRIEF_CONTENT_IDENTITY_MISMATCH", str(ctx.exception))

    def test_unknown_section_availability_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        brief_path = build_dir / "next_session_decision_brief.json"
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        brief["tactical_transition"]["availability"] = "SORT_OF_MAYBE"
        payload_for_hash = {k: v for k, v in brief.items() if k not in {"artifact_sha256", "artifact_identity"}}
        digest = hashlib.sha256(
            json.dumps(payload_for_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        brief["artifact_sha256"], brief["artifact_identity"] = digest, f"next_session_decision_brief:{digest}"
        _write_json(brief_path, brief)
        package = load_next_session_decision_package(build_dir, expected_session="2026-09-01")
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            build_context(package)
        self.assertIn("AVAILABILITY_UNKNOWN", str(ctx.exception))

    def test_tactical_source_identity_drift_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        brief_path = build_dir / "next_session_decision_brief.json"
        brief = json.loads(brief_path.read_text(encoding="utf-8"))
        brief["tactical_transition"]["source_lineage"]["current_tactical_artifact_identity"] = "some_other_engine:deadbeef"
        payload_for_hash = {k: v for k, v in brief.items() if k not in {"artifact_sha256", "artifact_identity"}}
        digest = hashlib.sha256(
            json.dumps(payload_for_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        brief["artifact_sha256"], brief["artifact_identity"] = digest, f"next_session_decision_brief:{digest}"
        _write_json(brief_path, brief)
        package = load_next_session_decision_package(build_dir, expected_session="2026-09-01")
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            build_context(package)
        self.assertIn("TACTICAL_TRANSITION_UNEXPECTED_SOURCE_IDENTITY", str(ctx.exception))

    def test_lineage_mismatch_fails_closed(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-01", previous_session=None)
        brief = json.loads((build_dir / "next_session_decision_brief.json").read_text(encoding="utf-8"))
        bad_lineage = {
            "decision_brief_sha256": "0" * 64,
            "producer_checkpoint": "synthetic0000000000000000000000000000000",
            "producer_lineage": {"next_session_decision_brief_identity": brief["artifact_identity"]},
            "session_bundle_sha256": "0" * 64,
            "manifest_sha256": "0" * 64,
            "opportunity_artifact_sha256": "0" * 64,
            "previous_session": None,
        }
        with self.assertRaises(NextSessionDecisionContextError) as ctx:
            load_next_session_decision_package(
                build_dir, expected_session="2026-09-01", expected_lineage=bad_lineage,
            )
        self.assertIn("LINEAGE_DECISION_BRIEF_SHA256_MISMATCH", str(ctx.exception))

    def test_valid_synthetic_package_round_trips(self):
        build_dir = _minimal_package(self.tmp, current_session="2026-09-02", previous_session="2026-09-01")
        package = load_next_session_decision_package(
            build_dir, expected_session="2026-09-02", expected_previous_session="2026-09-01",
        )
        context = build_context(package)
        self.assertEqual("2026-09-02", context["identity"]["current_session"])
        self.assertEqual("SESSION_BUNDLE_COMPARABLE_TICKER_COHORT", context["lifecycle_transition"]["scope"])
        self.assertEqual("FULL_MARKET_WATCHLIST_TACTICAL_ENTRY_CLASSIFIER", context["tactical_transition"]["scope"])

    def test_financial_analysis_session_summary_is_optional_and_read_only(self):
        build_dir = _minimal_package(
            self.tmp, current_session="2026-09-02", previous_session=None,
            bundle_payload={"financial_analysis": {
                "source_context_identity": "financial_analysis_context/v2:synthetic",
                "market_summary": {"contract_version": "financial_analysis_market_summary/v1", "availability": "AVAILABLE"},
                "ticker_index": {"AAA": {"status": "AVAILABLE"}},
            }},
        )
        package = load_next_session_decision_package(build_dir, expected_session="2026-09-02")
        context = build_context(package)
        summary = context["financial_analysis_session_summary"]
        self.assertEqual("AVAILABLE", summary["availability"])
        self.assertFalse(summary["is_actionable"])
        self.assertEqual("financial_analysis_context/v2:synthetic", context["source_lineage"]["financial_analysis_source_context_identity"])
        self.assertEqual("UNAVAILABLE", context["market_transition"]["availability"])


if __name__ == "__main__":
    unittest.main()
