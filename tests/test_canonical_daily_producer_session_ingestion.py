"""Synthetic operational-evidence tests for the canonical Daily Producer adapter."""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from builders.canonical_daily_producer_session_ingestion import (
    CanonicalDailyProducerSessionError,
    load_canonical_daily_producer_session,
)
from builders.current_research_synthesis_operational_workflow import prepare_synthesis_session


SESSION = "2026-08-25"
OPERATION = "daily_research_session_operation:operation"
PRODUCT = "current_daily_decision_research_product:product"
HEAD = "42d8da32f75e1b085ed1b02e86aff274196bf737"


def _canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _card(ticker="ABB"):
    return {
        "ticker": ticker,
        "current_decision_state": {
            "is_actionable": False, "requires_human_review": True,
            "position_sizing_status": "NOT_EVALUATED", "entry_action": "WAIT",
        },
        "peer_context": {}, "fundamental_context": {}, "valuation_context": {},
        "scenario": {"probability_status": "UNKNOWN_UNCALIBRATED", "bear_case": {}, "base_case": {}, "bull_case": {}},
        "thesis_counter_thesis": {"thesis": [], "counter_thesis": [], "questions_to_verify": []},
    }


class Fixture:
    def __init__(self, root: Path):
        self.root = root
        self.run_path = root / "run_manifest.json"
        self.ai_manifest_path = root / "ai_research_bundle_manifest.json"
        self.bundle_path = root / "ai_research_session_bundle.json"
        self.bundle = {
            "schema_version": "ai_research_session_bundle/v1", "session": SESSION,
            "operation_identity": OPERATION, "product_identity": PRODUCT, "producer_head": HEAD,
            "consumer_compatible_contract_version": "current_daily_decision_research_contract/v1",
            "authority_boundary": {"probability": "UNKNOWN_UNCALIBRATED"},
            "market": {"summary": {"source_market_session": SESSION}},
            "ticker_research_contexts": {"ABB": _card()},
            "lineage": {"input_artifacts": {"triage": {"artifact_identity": "triage:fixture"}}},
        }
        self._write_all()

    def _write_all(self):
        bundle_raw = _canonical(self.bundle)
        self.bundle_path.write_bytes(bundle_raw)
        self.ai_manifest = {
            "schema_version": "ai_research_bundle_manifest/v1", "session": SESSION,
            "operation_identity": OPERATION, "producer_head": HEAD,
            "consumer_compatible_contract_version": "current_daily_decision_research_contract/v1",
            "primary_bundle_filename": "ai_research_session_bundle.json",
            "files": {"ai_research_session_bundle.json": {"sha256": _sha(bundle_raw), "bytes": len(bundle_raw)}},
            "source_artifact_identities": {"triage": "triage:fixture"},
        }
        ai_manifest_raw = _canonical(self.ai_manifest)
        self.ai_manifest_path.write_bytes(ai_manifest_raw)
        run = {
            "schema_version": "daily_producer_run/v1", "run_identity": "daily_producer_run:run",
            "target_market_session": SESSION, "producer_head": HEAD,
            "daily_session_operation": {"identity": OPERATION}, "daily_product_identity": PRODUCT,
            "upstream_artifact_identities": {"triage": {"artifact_identity": "triage:fixture"}},
            "ai_delivery": {
                "ai_research_session_bundle.json": {"sha256": _sha(bundle_raw)},
                "ai_research_bundle_manifest.json": {"sha256": _sha(ai_manifest_raw)},
            },
        }
        self.run_path.write_bytes(_canonical(run))


class CanonicalDailyProducerSessionIngestionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.fixture = Fixture(Path(self.tmp.name))

    def test_valid_explicit_manifest_exposes_existing_consumer_card_context(self):
        loaded = load_canonical_daily_producer_session(self.fixture.run_path, session=SESSION)
        self.assertEqual(["ABB"], sorted(loaded["ticker_contexts"]))
        self.assertEqual(PRODUCT, loaded["ticker_contexts"]["ABB"]["current_daily_decision_research"]["source_artifact_identity"])
        self.assertEqual(HEAD, loaded["provenance"]["producer_head"])

    def test_wrong_identity_is_rejected(self):
        self.fixture.bundle["operation_identity"] = "daily_research_session_operation:other"
        self.fixture._write_all()
        with self.assertRaisesRegex(CanonicalDailyProducerSessionError, "AI_BUNDLE_OPERATION_IDENTITY_MISMATCH"):
            load_canonical_daily_producer_session(self.fixture.run_path, session=SESSION)

    def test_wrong_session_is_rejected(self):
        run = json.loads(self.fixture.run_path.read_text(encoding="utf-8"))
        run["target_market_session"] = "2026-08-24"
        self.fixture.run_path.write_bytes(_canonical(run))
        with self.assertRaisesRegex(CanonicalDailyProducerSessionError, "RUN_SESSION_MISMATCH"):
            load_canonical_daily_producer_session(self.fixture.run_path, session=SESSION)

    def test_malformed_or_missing_artifacts_fail_closed(self):
        self.fixture.bundle_path.write_text("not-json", encoding="utf-8")
        with self.assertRaisesRegex(CanonicalDailyProducerSessionError, "AI_BUNDLE_INVALID"):
            load_canonical_daily_producer_session(self.fixture.run_path, session=SESSION)
        self.fixture._write_all()
        self.fixture.bundle_path.unlink()
        with self.assertRaisesRegex(CanonicalDailyProducerSessionError, "AI_BUNDLE_INVALID"):
            load_canonical_daily_producer_session(self.fixture.run_path, session=SESSION)

    def test_deterministic_replay_and_no_latest_selection(self):
        (self.fixture.root / "LATEST_COMPLETED_RUN.json").write_text('{"ignore": true}', encoding="utf-8")
        first = load_canonical_daily_producer_session(self.fixture.run_path, session=SESSION)
        second = load_canonical_daily_producer_session(self.fixture.run_path, session=SESSION)
        self.assertEqual(first, second)
        prepared = prepare_synthesis_session(
            [{"context": context} for _, context in sorted(first["ticker_contexts"].items())],
            session_label=SESSION,
        )
        self.assertEqual(["ABB"], [request["ticker"] for request in prepared["manifest"]["requests"]])

    def test_current_path_isolation(self):
        root = Path(__file__).resolve().parents[1]
        adapter = (root / "builders" / "canonical_daily_producer_session_ingestion.py").read_text(encoding="utf-8")
        self.assertNotIn("run_session_operation", adapter)
        self.assertNotIn("export_ai_bundle", adapter)
        for path in (root / "builders" / "build_ticker_context.py", root / "builders" / "structured_research_synthesis_boundary.py"):
            self.assertNotIn("canonical_daily_producer_session_ingestion", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
