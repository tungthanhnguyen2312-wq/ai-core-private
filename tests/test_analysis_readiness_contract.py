"""Consumer-side exact-session trusted-subset verification and readiness/lane gating.

Every integrity case below is exercised against a real artifact set written to disk --
bundle body, manifest, focus extract and taxonomy sidecar -- built by the same helper that
mirrors what `stock-core-private/export_ai_bundle.py::build_trusted_subset_proof` emits.
Hand-built dictionaries cannot catch a hash, artifact-set or cross-artifact defect, which
is precisely the class of defect this contract exists to reject.
"""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from builders import build_ticker_context as builder

SESSION = "2026-07-30"
GENERATED_AT = "2026-07-30T10:00:00+00:00"


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _bundle_body(session=SESSION, generated_at=GENERATED_AT, tickers=("HPG", "VNM"), extra=None):
    body = {
        "schema_version": "1.0.0",
        "generated_at": generated_at,
        "reference_session_date": session,
        "tickers_requested": list(tickers),
        "tickers": {ticker: {"snapshot": {"date": session}} for ticker in tickers},
    }
    if extra:
        for ticker, patch in extra.items():
            body["tickers"].setdefault(ticker, {}).update(patch)
    return body


class ExactSessionBundleFixture:
    """Write a complete, self-consistent export-session artifact set into `root`."""

    def __init__(self, root: Path, *, session=SESSION, generated_at=GENERATED_AT,
                 body=None, with_sidecar=True, basis_verified=True,
                 producer_version=builder.PRODUCER_BUNDLE_CONTRACT_VERSION,
                 schema_version=builder.TRUSTED_SUBSET_SCHEMA_VERSION):
        self.root = root
        self.bundle_path = root / "analysis_bundle.json"
        self.manifest_path = root / "bundle_manifest.json"
        self.session = session
        self.generated_at = generated_at

        body = body if body is not None else _bundle_body(session, generated_at)
        self.bundle_path.write_text(json.dumps(body), encoding="utf-8")

        artifacts = {}
        focus = root / "focus_extract.json"
        focus.write_text(json.dumps({"reference_session_date": session}), encoding="utf-8")
        artifacts["focus_extract.json"] = _sha256_bytes(focus.read_bytes())
        if with_sidecar:
            sidecar = root / "statement_taxonomy_sidecar.json"
            sidecar.write_text(json.dumps({"schema_version": "1.0.0", "records": []}), encoding="utf-8")
            artifacts["statement_taxonomy_sidecar.json"] = _sha256_bytes(sidecar.read_bytes())
        artifacts["analysis_bundle.json"] = _sha256_bytes(self.bundle_path.read_bytes())

        self.proof = {
            "schema_version": schema_version,
            "producer_contract_version": producer_version,
            "tickers": ["HPG", "VNM"],
            "unproven_tickers": [],
            "bundle_ticker_set": ["HPG", "VNM"],
            "trust_state": "exact_session_qualified" if basis_verified else "untrusted_basis",
            "session_identity": session,
            "generated_at": generated_at,
            "bundle_filename": "analysis_bundle.json",
            "bundle_sha256": artifacts["analysis_bundle.json"],
            "bundle_reference_session_date": session,
            "bundle_generated_at": generated_at,
            "required_artifacts": [{"file": name, "sha256": artifacts[name]} for name in sorted(artifacts)],
            "expected_artifact_filenames": sorted(set(artifacts) | {"bundle_manifest.json"}),
            "per_ticker": {t: {"session_identity": session} for t in ("HPG", "VNM")},
            "price_basis": {"state": "adjusted", "verified": basis_verified},
            "volume_basis": {"state": "shares", "verified": basis_verified},
        }
        self.manifest = {"schema_version": "1.1.0", "generated_at": generated_at,
                         "trusted_subset": self.proof}
        self._flush()

    def _flush(self):
        self.manifest["trusted_subset"] = self.proof
        self.manifest_path.write_text(json.dumps(self.manifest), encoding="utf-8")

    def mutate_proof(self, **fields):
        self.proof.update(fields)
        self._flush()
        return self

    def load(self):
        return builder.load_optional_analysis_bundle(
            {"source_paths": {"analysis_bundle": str(self.bundle_path)}})


class ExactSessionIntegrityTests(unittest.TestCase):
    def _in_tmp(self, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ExactSessionBundleFixture(Path(tmp.name), **kwargs)

    def _reject(self, fixture, expected_reason_prefix):
        payload, warning = fixture.load()
        validation = payload["trusted_subset_validation"]
        self.assertEqual(validation["integrity_state"], "unverified")
        self.assertEqual(validation["state"], "untrusted")
        self.assertTrue(str(validation["integrity_reason"]).startswith(expected_reason_prefix),
                        f"expected reason starting {expected_reason_prefix!r}, got {validation['integrity_reason']!r}")
        self.assertEqual(warning, "trusted_subset_untrusted")
        return validation

    # ---------------------------------------------------------------- accepted
    def test_valid_exact_session_bundle_is_trusted(self):
        payload, warning = self._in_tmp().load()
        validation = payload["trusted_subset_validation"]
        self.assertEqual(validation["integrity_state"], "exact_session_verified")
        self.assertEqual(validation["basis_state"], "qualified")
        self.assertEqual(validation["state"], "exact_session_trusted")
        self.assertIsNone(warning)

    def test_absent_optional_analysis_is_not_a_rejection(self):
        payload, warning = builder.load_optional_analysis_bundle({"source_paths": {}})
        self.assertEqual(payload, {})
        self.assertEqual(warning, "analysis_bundle_not_configured")

    def test_deterministic_regeneration_of_an_identical_session_verifies(self):
        first = self._in_tmp()
        second = self._in_tmp()
        self.assertEqual(first.proof["bundle_sha256"], second.proof["bundle_sha256"])
        for fixture in (first, second):
            self.assertEqual(fixture.load()[0]["trusted_subset_validation"]["integrity_state"],
                             "exact_session_verified")

    # ---------------------------------------------------------------- rejected
    def test_missing_manifest_is_legacy_untrusted_not_trusted(self):
        fixture = self._in_tmp()
        fixture.manifest_path.unlink()
        payload, warning = fixture.load()
        validation = payload["trusted_subset_validation"]
        self.assertEqual(validation["state"], "legacy_untrusted")
        self.assertEqual(validation["integrity_state"], "legacy_unverified")
        self.assertEqual(warning, "trusted_subset_legacy_untrusted")

    def test_legacy_schema_bundle_is_never_current_trusted_output(self):
        self._reject(self._in_tmp().mutate_proof(schema_version="1.0.0"), "manifest_schema_unsupported")

    def test_older_producer_contract_version_is_rejected(self):
        fixture = self._in_tmp()
        fixture.mutate_proof(producer_contract_version="stocklookup-producer/2026.01.01")
        self._reject(fixture, "producer_contract_version_unsupported")

    def test_wrong_session_in_manifest_is_rejected(self):
        # A manifest claiming a different session than the bundle body it hashes correctly
        # against. Internally consistent within the proof, so only the cross-artifact check
        # catches it.
        fixture = self._in_tmp().mutate_proof(
            session_identity="2026-07-29",
            bundle_reference_session_date="2026-07-29",
            per_ticker={t: {"session_identity": "2026-07-29"} for t in ("HPG", "VNM")},
        )
        self._reject(fixture, "bundle_session_mismatch")

    def test_manifest_session_not_matching_its_own_per_ticker_proof_is_rejected(self):
        self._reject(self._in_tmp().mutate_proof(session_identity="2026-07-29"),
                     "per_ticker_session_mismatch")

    def test_previous_session_manifest_against_current_bundle_is_rejected(self):
        fixture = self._in_tmp()
        fixture.mutate_proof(bundle_reference_session_date="2026-07-29",
                             bundle_generated_at="2026-07-29T10:00:00+00:00",
                             generated_at="2026-07-29T10:00:00+00:00")
        self._reject(fixture, "bundle_session_mismatch")

    def test_bundle_body_from_a_different_session_is_rejected(self):
        fixture = self._in_tmp()
        fixture.bundle_path.write_text(json.dumps(_bundle_body(session="2026-07-29")), encoding="utf-8")
        self._reject(fixture, "bundle_hash_mismatch")

    def test_one_changed_artifact_after_manifest_generation_is_rejected(self):
        fixture = self._in_tmp()
        (fixture.root / "focus_extract.json").write_text(json.dumps({"tampered": True}), encoding="utf-8")
        self._reject(fixture, "required_artifact_hash_mismatch:focus_extract.json")

    def test_missing_required_artifact_is_rejected(self):
        fixture = self._in_tmp()
        (fixture.root / "statement_taxonomy_sidecar.json").unlink()
        self._reject(fixture, "required_artifact_missing:statement_taxonomy_sidecar.json")

    def test_unexpected_extra_trusted_file_is_rejected(self):
        fixture = self._in_tmp(with_sidecar=False)
        (fixture.root / "statement_taxonomy_sidecar.json").write_text("{}", encoding="utf-8")
        self._reject(fixture, "unexpected_trusted_artifact:statement_taxonomy_sidecar.json")

    def test_per_ticker_session_mismatch_is_rejected(self):
        fixture = self._in_tmp()
        fixture.mutate_proof(per_ticker={"HPG": {"session_identity": SESSION},
                                          "VNM": {"session_identity": "2026-07-29"}})
        self._reject(fixture, "per_ticker_session_mismatch")

    def test_bundle_ticker_snapshot_session_mismatch_is_rejected(self):
        body = _bundle_body()
        body["tickers"]["VNM"]["snapshot"]["date"] = "2026-07-29"
        fixture = self._in_tmp(body=body)
        self._reject(fixture, "bundle_ticker_session_mismatch")

    def test_ticker_accounting_must_be_complete(self):
        # VNM dropped from the proven set without appearing under unproven_tickers.
        self._reject(self._in_tmp().mutate_proof(tickers=["HPG"]), "ticker_accounting_incomplete")

    def test_unproven_ticker_must_carry_a_reason(self):
        fixture = self._in_tmp().mutate_proof(
            tickers=["HPG"], unproven_tickers=[{"ticker": "VNM"}],
            per_ticker={"HPG": {"session_identity": SESSION}})
        self._reject(fixture, "unproven_ticker_missing_reason")

    def test_bundle_ticker_set_must_match_the_bundle_body(self):
        self._reject(self._in_tmp().mutate_proof(bundle_ticker_set=["HPG", "VNM", "FPT"]),
                     "ticker_accounting_incomplete")

    def test_schema_valid_but_proofless_manifest_is_not_accepted(self):
        fixture = self._in_tmp()
        fixture.manifest_path.write_text(json.dumps({"schema_version": "1.1.0"}), encoding="utf-8")
        self._reject(fixture, "manifest_proof_missing")

    def test_invalid_manifest_json_is_rejected(self):
        fixture = self._in_tmp()
        fixture.manifest_path.write_text("{not json", encoding="utf-8")
        self._reject(fixture, "manifest_invalid_payload")

    def test_rejection_reasons_do_not_leak_filesystem_paths(self):
        fixture = self._in_tmp()
        (fixture.root / "focus_extract.json").write_text("{}", encoding="utf-8")
        reason = fixture.load()[0]["trusted_subset_validation"]["integrity_reason"]
        self.assertNotIn(str(fixture.root), reason)
        self.assertNotIn("\\", reason)
        self.assertNotIn("/", reason)


class PartiallyProvenBundleTests(unittest.TestCase):
    """A bundle whose proof covers only some of its tickers is trusted for exactly those."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        body = _bundle_body(tickers=("HPG", "VNM", "VNINDEX"))
        body["tickers"]["VNINDEX"] = {"snapshot": None, "analysis_readiness": {"domains": {}}}
        body["tickers"]["HPG"]["analysis_readiness"] = {
            "reference_at": GENERATED_AT,
            "domains": {"fundamental": {"state": "ready", "reason": None, "is_actionable": True}}}
        self.fixture = ExactSessionBundleFixture(Path(tmp.name), body=body)
        self.fixture.mutate_proof(
            tickers=["HPG", "VNM"],
            unproven_tickers=[{"ticker": "VNINDEX", "observed_session_identity": None,
                                "reason": "snapshot_missing"}],
            bundle_ticker_set=["HPG", "VNINDEX", "VNM"],
        )
        self.payload = self.fixture.load()[0]

    def test_bundle_integrity_verifies_with_an_explicitly_unproven_ticker(self):
        validation = self.payload["trusted_subset_validation"]
        self.assertEqual(validation["integrity_state"], "exact_session_verified")
        self.assertEqual(validation["proven_tickers"], ["HPG", "VNM"])
        self.assertEqual(validation["unproven_tickers"], {"VNINDEX": "snapshot_missing"})

    def test_proven_ticker_is_readable(self):
        self.assertEqual(builder.analysis_readiness_contract(self.payload, "HPG")["status"], "available")

    def test_unproven_ticker_is_never_exact_session_trusted(self):
        readiness = builder.analysis_readiness_contract(self.payload, "VNINDEX")
        self.assertEqual(readiness["status"], "unknown")
        self.assertIn("ticker_not_session_proven", readiness["reason"])
        self.assertFalse(readiness["inferences_allowed"])


class BasisAxisTests(unittest.TestCase):
    def _fixture(self, **kwargs):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return ExactSessionBundleFixture(Path(tmp.name), **kwargs)

    def test_integrity_verified_but_basis_unqualified_is_precisely_named(self):
        payload, warning = self._fixture(basis_verified=False).load()
        validation = payload["trusted_subset_validation"]
        self.assertEqual(validation["integrity_state"], "exact_session_verified")
        self.assertEqual(validation["basis_state"], "unqualified")
        self.assertEqual(validation["state"], "untrusted")
        self.assertEqual(validation["reason"], "basis_unqualified")
        self.assertEqual(validation["warnings"], ["trusted_subset_basis_unqualified"])
        self.assertEqual(warning, "trusted_subset_untrusted")


class ReadinessAndLaneGateTests(unittest.TestCase):
    READINESS = {"reference_at": "2026-07-30T00:00:00+00:00",
                 "domains": {"fundamental": {"state": "ready", "reason": None, "is_actionable": True}}}

    def _bundle(self, integrity, basis):
        return {
            "trusted_subset_validation": {"state": "untrusted", "reason": "x",
                                           "integrity_state": integrity, "integrity_reason": "manifest_invalid",
                                           "basis_state": basis},
            "tickers": {"HPG": {"analysis_readiness": self.READINESS, "analysis_lane_eligibility": []}},
        }

    def test_legacy_and_malformed_are_conservative_unknown(self):
        self.assertEqual(builder.analysis_readiness_contract({"tickers": {"HPG": {}}}, "HPG")["status"], "unknown")
        self.assertEqual(builder.analysis_readiness_contract({"tickers": {"HPG": {"analysis_readiness": {}}}}, "HPG")["status"], "unknown")

    def test_ready_requires_actionable_and_degraded_warns(self):
        bundle = {"tickers": {"HPG": {"analysis_readiness": {"reference_at": "2026-07-26T00:00:00+00:00", "domains": {"market_technical": {"state": "degraded", "reason": "stale", "required_inputs": [], "is_actionable": False}}}}}}
        value = builder.analysis_readiness_contract(bundle, "HPG")
        self.assertEqual(value["status"], "available")
        self.assertFalse(value["inferences_allowed"])
        self.assertTrue(value["data_warnings"])

    def test_integrity_failure_blocks_readiness_and_lanes(self):
        bundle = self._bundle("unverified", "qualified")
        self.assertEqual(builder.analysis_readiness_contract(bundle, "HPG")["status"], "unknown")
        self.assertEqual(builder.analysis_lane_eligibility_contract(bundle, "HPG")["status"], "untrusted")

    def test_unqualified_basis_keeps_readiness_readable_but_never_inferable(self):
        bundle = self._bundle("exact_session_verified", "unqualified")
        readiness = builder.analysis_readiness_contract(bundle, "HPG")
        self.assertEqual(readiness["status"], "available")
        self.assertFalse(readiness["inferences_allowed"])
        self.assertTrue(any("basis is unverified" in w for w in readiness["data_warnings"]))
        self.assertEqual(builder.analysis_lane_eligibility_contract(bundle, "HPG"), [])

    def test_legacy_bundle_without_validation_block_keeps_prior_behaviour(self):
        bundle = {"tickers": {"HPG": {"analysis_lane_eligibility": []}}}
        self.assertEqual(builder.analysis_lane_eligibility_contract(bundle, "HPG"), [])


if __name__ == "__main__":
    unittest.main()
