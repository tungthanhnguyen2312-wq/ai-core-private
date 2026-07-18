"""Phase 9 catalog and deterministic rebuild-decision tests."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "tests" / "fixtures"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


validator = load_module("phase9_validator", ROOT / "builders" / "validate_json_schema_subset.py")
comparator = load_module("phase9_comparator", ROOT / "builders" / "compare_batch_runs.py")
catalog_builder = load_module("phase9_catalog", ROOT / "builders" / "build_artifact_catalog.py")
decision_builder = load_module("phase9_decision", ROOT / "builders" / "decide_rebuild.py")


class ExtendedFixtureTests(unittest.TestCase):
    def test_malformed_provenance_fails_schema(self):
        schema = validator.load_json(ROOT / "validation" / "schemas" / "ticker_context.schema.json")
        instance = validator.load_json(FIXTURES / "context_invalid_malformed_provenance.json")
        errors = validator.validate(instance, schema)
        self.assertTrue(any("provenance" in item and "array" in item for item in errors), errors)

    def test_new_and_deleted_packages(self):
        previous = comparator.load_json(FIXTURES / "manifest_previous.json")
        current = comparator.load_json(FIXTURES / "manifest_current_new_deleted.json")
        report = comparator.compare(previous, current)
        statuses = {item["ticker"]: item["status"] for item in report["package_changes"]}
        self.assertEqual(statuses, {"NEW":"new", "TEST":"missing"})
        self.assertTrue(report["stale_or_changed"])


class RebuildDecisionTests(unittest.TestCase):
    def test_changed_package_requires_rebuild(self):
        staleness = decision_builder.load_json(FIXTURES / "staleness_changed.json")
        validation = decision_builder.load_json(FIXTURES / "validation_pass.json")
        result = decision_builder.decide(staleness, validation)
        self.assertEqual(result["decisions"][0]["action"], "rebuild_required")

    def test_current_unchanged_batch_requires_no_rebuild(self):
        staleness = decision_builder.load_json(ROOT / "exports" / "context_packages" / "staleness_report.json")
        validation = decision_builder.load_json(ROOT / "exports" / "context_packages" / "batch_validation_report_auto_v2.json")
        result = decision_builder.decide(staleness, validation)
        self.assertEqual(len(result["decisions"]), 10)
        self.assertTrue(all(item["action"] == "no_rebuild" for item in result["decisions"]))


class CatalogTests(unittest.TestCase):
    def test_catalog_links_ten_contexts_and_schemas(self):
        catalog = catalog_builder.build_catalog(
            ROOT / "exports" / "context_packages" / "batch_manifest_auto_v2.json",
            ROOT / "exports" / "context_packages" / "batch_validation_report_auto_v2.json",
            ROOT / "exports" / "context_packages" / "staleness_report.json",
        )
        contexts = [item for item in catalog["artifacts"] if item["artifact_type"] == "ticker_context"]
        schemas = [item for item in catalog["artifacts"] if item["artifact_type"] == "json_schema"]
        self.assertEqual(len(contexts), 10)
        self.assertEqual(len(schemas), 4)
        self.assertTrue(any(item["path"].endswith("context_coverage_report.schema.json") for item in schemas))
        self.assertTrue(all(len(item["sha256"]) == 64 for item in catalog["artifacts"]))


if __name__ == "__main__":
    unittest.main()
