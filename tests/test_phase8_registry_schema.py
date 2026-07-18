"""Fixture-based Phase 8 tests independent of current VNSTOCK freshness."""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"
SCHEMAS = ROOT / "validation" / "schemas"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("phase8_validator", ROOT / "builders" / "validate_json_schema_subset.py")
comparator = load_module("phase8_comparator", ROOT / "builders" / "compare_batch_runs.py")


class SchemaTests(unittest.TestCase):
    def test_all_schema_files_are_valid_json(self):
        for path in SCHEMAS.glob("*.json"):
            with self.subTest(path=path.name):
                value = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(value["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_valid_context_fixture(self):
        schema = validator.load_json(SCHEMAS / "ticker_context.schema.json")
        instance = validator.load_json(FIXTURES / "context_valid_minimal.json")
        self.assertEqual(validator.validate(instance, schema), [])

    def test_invalid_context_fixture_reports_provenance(self):
        schema = validator.load_json(SCHEMAS / "ticker_context.schema.json")
        instance = validator.load_json(FIXTURES / "context_invalid_missing_provenance.json")
        errors = validator.validate(instance, schema)
        self.assertTrue(any("provenance" in error for error in errors), errors)

    def test_real_auto_artifacts_match_schemas(self):
        pairs = [
            ("batch_manifest.schema.json", "batch_manifest_auto.json"),
            ("batch_validation_report.schema.json", "batch_validation_report_auto.json"),
        ]
        for schema_name, instance_name in pairs:
            with self.subTest(instance=instance_name):
                schema = validator.load_json(SCHEMAS / schema_name)
                instance = validator.load_json(ROOT / "exports" / "context_packages" / instance_name)
                self.assertEqual(validator.validate(instance, schema), [])


class RegistryComparisonTests(unittest.TestCase):
    def test_changed_fixture_is_stale(self):
        previous = comparator.load_json(FIXTURES / "manifest_previous.json")
        current = comparator.load_json(FIXTURES / "manifest_current_changed.json")
        report = comparator.compare(previous, current)
        self.assertTrue(report["stale_or_changed"])
        self.assertEqual(report["package_changes"][0]["status"], "changed")
        self.assertEqual(report["source_changes"][0]["status"], "changed")

    def test_identical_fixture_is_not_stale(self):
        previous = comparator.load_json(FIXTURES / "manifest_previous.json")
        report = comparator.compare(previous, previous)
        self.assertFalse(report["stale_or_changed"])
        self.assertEqual(report["package_changes"][0]["status"], "unchanged")


if __name__ == "__main__":
    unittest.main()
