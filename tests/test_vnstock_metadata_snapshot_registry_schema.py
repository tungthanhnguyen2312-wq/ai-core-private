"""Schema-only tests for the vnstock_metadata_snapshot Evidence Platform Registry handoff
record. No runtime wiring: this validates instances against validation/schemas/ only."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = ROOT / "validation" / "schemas" / "vnstock_metadata_snapshot_registry_handoff.schema.json"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("registry_schema_validator", ROOT / "builders" / "validate_json_schema_subset.py")


def _valid_record(**overrides):
    record = {
        "source": "vnstock_metadata_snapshot",
        "provider": "vnstock:Finance(source=KBS).ratio",
        "ticker": "AAA",
        "field": "roe",
        "value": 6.75,
        "timestamps": {
            "observed_at": "2026-07-27 19:38",
            "effective_at": "2026-07-27 19:38",
            "provider_timestamp": None,
            "timestamp_basis": "scrape_time_approximates_unretained_reporting_period",
        },
        "raw_hash": {"raw_payload_retained": False, "value": None},
        "transform_version": "meta_sync.py@sha256:f110d22d1231",
        "qualification_status": "reported",
        "distinct_from": ["financial_summary.roe_quarter", "financial_summary.roe_fy", "financial_summary.roe_ttm"],
        "freshness_sla": {
            "domain": "vnstock_metadata_snapshot",
            "cadence_days": 92,
            "grace_days": 35,
            "policy_source": "stock-core-private/freshness_history.py:RULES[\"vnstock_metadata_snapshot\"]",
        },
    }
    record.update(overrides)
    return record


class RegistryHandoffSchemaTests(unittest.TestCase):
    def setUp(self):
        self.schema = validator.load_json(SCHEMA_PATH)

    def test_schema_file_is_valid_json_schema_document(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(
            self.schema["$id"],
            "https://local.ai-analyze/schemas/vnstock_metadata_snapshot_registry_handoff.schema.json",
        )

    def test_valid_record_passes(self):
        self.assertEqual(validator.validate(_valid_record(), self.schema), [])

    def test_valid_record_with_null_value_passes(self):
        # margin_status is legitimately null when a ticker carries no blacklist flag -- must
        # not be rejected just because value is None.
        record = _valid_record(
            field="margin_status",
            provider="manual_curation:blacklist.csv",
            value=None,
        )
        record["timestamps"] = {**record["timestamps"], "timestamp_basis": "scrape_time_live_value"}
        record.pop("distinct_from")
        self.assertEqual(validator.validate(record, self.schema), [])

    def test_valid_record_with_dividend_yield_sentinel_passes(self):
        # -1 means "queried via --ratio-only, provider had no value" -- a real, meaningful
        # value distinct from NULL. The schema must accept it, not just 0/blank/null.
        record = _valid_record(field="dividend_yield", value=-1)
        record.pop("distinct_from")
        self.assertEqual(validator.validate(record, self.schema), [])

    def test_missing_required_top_level_field_is_rejected(self):
        record = _valid_record()
        del record["freshness_sla"]
        errors = validator.validate(record, self.schema)
        self.assertTrue(any("freshness_sla" in e for e in errors), errors)

    def test_fabricated_provider_timestamp_is_rejected(self):
        record = _valid_record()
        record["timestamps"] = {**record["timestamps"], "provider_timestamp": "2026-07-27T19:38:00Z"}
        errors = validator.validate(record, self.schema)
        self.assertTrue(any("provider_timestamp" in e for e in errors), errors)

    def test_fabricated_raw_payload_retained_is_rejected(self):
        record = _valid_record()
        record["raw_hash"] = {"raw_payload_retained": True, "value": "deadbeef"}
        errors = validator.validate(record, self.schema)
        self.assertTrue(errors)

    def test_wrong_freshness_sla_cadence_is_rejected(self):
        record = _valid_record()
        record["freshness_sla"] = {**record["freshness_sla"], "cadence_days": 30}
        errors = validator.validate(record, self.schema)
        self.assertTrue(any("cadence_days" in e for e in errors), errors)

    def test_unknown_field_name_is_rejected(self):
        record = _valid_record(field="not_a_real_field")
        errors = validator.validate(record, self.schema)
        self.assertTrue(any(e.startswith("$.field") for e in errors), errors)


if __name__ == "__main__":
    unittest.main()
