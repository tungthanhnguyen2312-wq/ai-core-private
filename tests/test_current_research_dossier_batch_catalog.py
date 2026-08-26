from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from builders.current_research_dossier_batch_catalog import (
    AUTHORITY_BLOCKED, DOSSIER_READY, INPUT_NOT_FOUND, MALFORMED, NO_ACCEPTED_SYNTHESIS,
    REJECTED_UNTRACEABLE, build_dossier_batch_catalog, load_batch_manifest,
    render_dossier_batch_inventory, replay_dossier_batch_catalog, write_dossier_batch_output,
)

_FIXTURE_SPEC = importlib.util.spec_from_file_location("dossier_fixture", ROOT / "tests" / "test_current_research_claim_provenance_trace.py")
assert _FIXTURE_SPEC and _FIXTURE_SPEC.loader
_FIXTURE = importlib.util.module_from_spec(_FIXTURE_SPEC); _FIXTURE_SPEC.loader.exec_module(_FIXTURE)

def _record(ticker="TRACE", *, context=None, response=None, claim_map=None):
    context = copy.deepcopy(context if context is not None else _FIXTURE._context()); context["ticker"] = ticker
    response = copy.deepcopy(response if response is not None else _FIXTURE._response()); response["ticker"] = ticker
    return {"ticker": ticker, "context": context, "synthesis": response, "claim_evidence_map": claim_map}

def _result(records): return build_dossier_batch_catalog({"batch_session": "2026-08-25", "records": records})

class CurrentResearchDossierBatchCatalogTests(unittest.TestCase):
    def test_01_one_ready_ticker(self):
        catalog = _result([_record()])["catalog"]
        self.assertEqual(DOSSIER_READY, catalog["records"][0]["dossier_disposition"])

    def test_02_multiple_ready_tickers(self):
        catalog = _result([_record("BBB"), _record("AAA")])["catalog"]
        self.assertEqual(["AAA", "BBB"], [row["ticker"] for row in catalog["records"]])
        self.assertEqual(2, catalog["status_counts"][DOSSIER_READY])

    def test_03_no_synthesis_is_availability_not_research_judgment(self):
        record = _record(); del record["synthesis"]
        self.assertEqual(NO_ACCEPTED_SYNTHESIS, _result([record])["catalog"]["records"][0]["dossier_disposition"])

    def test_04_rejected_unknown_synthesis_is_local(self):
        response = _FIXTURE._response(["unknown:evidence"])
        self.assertEqual(REJECTED_UNTRACEABLE, _result([_record(response=response)])["catalog"]["records"][0]["dossier_disposition"])

    def test_05_prohibited_synthesis_is_authority_blocked(self):
        response = _FIXTURE._response(); response["thesis"] = "This is a BUY recommendation."
        self.assertEqual(AUTHORITY_BLOCKED, _result([_record(response=response)])["catalog"]["records"][0]["dossier_disposition"])

    def test_06_malformed_context_is_local(self):
        record = _record(); record["context"] = []
        self.assertEqual(MALFORMED, _result([record])["catalog"]["records"][0]["dossier_disposition"])

    def test_07_missing_input_is_explicit(self):
        record = _record(); record["missing_synthesis"] = "missing.json"
        self.assertEqual(INPUT_NOT_FOUND, _result([record])["catalog"]["records"][0]["dossier_disposition"])

    def test_08_one_bad_ticker_does_not_block_one_good_ticker(self):
        bad = _record("BAD"); del bad["synthesis"]
        catalog = _result([bad, _record("GOOD")])["catalog"]
        self.assertEqual(1, catalog["status_counts"][DOSSIER_READY]); self.assertEqual(1, catalog["status_counts"][NO_ACCEPTED_SYNTHESIS])

    def test_09_catalog_identity_is_deterministic(self):
        self.assertEqual(_result([_record()])["catalog"]["catalog_identity"], _result([_record()])["catalog"]["catalog_identity"])

    def test_10_input_order_does_not_change_identity(self):
        forward = _result([_record("AAA"), _record("BBB")])["catalog"]
        reverse = _result([_record("BBB"), _record("AAA")])["catalog"]
        self.assertEqual(forward["catalog_identity"], reverse["catalog_identity"])

    def test_11_dossier_identity_is_deterministic(self):
        first, second = _result([_record()])["dossiers"]["TRACE"], _result([_record()])["dossiers"]["TRACE"]
        self.assertEqual(first["dossier_identity"], second["dossier_identity"])

    def test_12_catalog_replay_and_residual(self):
        catalog = _result([_record()])["catalog"]
        replay_dossier_batch_catalog(catalog); self.assertEqual(0, catalog["unexplained_residual"])

    def test_13_inventory_counts_match_catalog(self):
        catalog = _result([_record(), _record("NO") | {"synthesis": None}])["catalog"]
        inventory = render_dossier_batch_inventory(catalog)
        self.assertIn(f"| {DOSSIER_READY} | 1 |", inventory); self.assertIn(f"| {NO_ACCEPTED_SYNTHESIS} | 1 |", inventory)

    def test_14_dossier_ready_is_not_actionable(self):
        catalog = _result([_record()])["catalog"]
        self.assertTrue(catalog["authority_boundary"]["dossier_ready_is_not_investment_readiness"])

    def test_15_output_materializes_ready_dossier_only(self):
        bad = _record("NO"); del bad["synthesis"]
        result = _result([_record("YES"), bad])
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp); paths = write_dossier_batch_output(output, result)
            self.assertTrue(paths["catalog"].exists()); self.assertTrue((output / "YES" / "current_research_auditable_dossier.md").exists())
            self.assertFalse((output / "NO").exists())

    def test_16_preflight_writes_catalog_not_dossiers(self):
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp); write_dossier_batch_output(output, _result([_record()]), preflight_only=True)
            self.assertTrue((output / "current_research_auditable_dossier_catalog.json").exists())
            self.assertFalse((output / "TRACE").exists())

    def test_17_immutable_output_replay_is_safe(self):
        with tempfile.TemporaryDirectory() as temp:
            result = _result([_record()]); write_dossier_batch_output(Path(temp), result); write_dossier_batch_output(Path(temp), result)

    def test_18_manifest_missing_fails_cleanly(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(FileNotFoundError, "BATCH_MANIFEST_NOT_FOUND"):
                load_batch_manifest(Path(temp) / "missing.json")

    def test_19_manifest_paths_are_explicit_and_no_discovery_occurs(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp); (base / "manifest.json").write_text(json.dumps({"records": [{"ticker": "AAA", "context_path": "a.json", "synthesis_path": "b.json"}]}), encoding="utf-8")
            loaded = load_batch_manifest(base / "manifest.json")
            self.assertEqual((base / "a.json").resolve().as_posix(), Path(loaded["records"][0]["context_path"]).as_posix())

    def test_20_retained_parity_artifact_has_no_implied_synthesis_corpus(self):
        path = ROOT / "operations-review" / "current-research-packet-shadow-parity-v1-20260825" / "current_research_packet_shadow_parity_artifact.json"
        artifact = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(1507, artifact["denominator"])
        self.assertNotIn("accepted_structured_synthesis_records", artifact)

    def test_21_retained_availability_catalog_honestly_has_zero_ready_inputs(self):
        path = ROOT / "operations-review" / "current-research-dossier-batch-catalog-v1-20260826" / "current_research_auditable_dossier_catalog.json"
        catalog = json.loads(path.read_text(encoding="utf-8"))
        replay_dossier_batch_catalog(catalog)
        self.assertEqual((0, 0), (catalog["denominator"], catalog["status_counts"][DOSSIER_READY]))

    def test_22_current_path_does_not_import_batch_catalog(self):
        for path in (ROOT / "builders" / "build_ticker_context.py", ROOT / "builders" / "structured_research_synthesis_boundary.py", ROOT / "builders" / "current_research_auditable_dossier.py"):
            self.assertNotIn("current_research_dossier_batch_catalog", path.read_text(encoding="utf-8"))

if __name__ == "__main__": unittest.main()
