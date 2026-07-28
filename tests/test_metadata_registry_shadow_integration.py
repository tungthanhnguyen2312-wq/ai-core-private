"""Tests for the opt-in registry-snapshot metadata path in build_ticker_context.py:
load_metadata_slice_from_registry_snapshot, compare_metadata_slices, and _select_metadata_loader.

None of these tests open vn_stock.db or any other production file. The one production-snapshot
test is read-only against the real registry snapshot and falls back to a fixture if it's absent;
it never opens the database either -- shadow comparison there uses a hand-built reference slice,
not a live DB read.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # matches test_phase9_snapshot_consumer.py's own convention

from builders import build_ticker_context as builder  # noqa: E402
from builders.metadata_registry_reader import SnapshotError  # noqa: E402

_FIELDS = ("exchange", "industry", "foreign_room_pct", "pe", "pb", "roe", "market_cap",
           "shares_outstanding", "free_float_est", "dividend_yield", "margin_status")

_PROVIDER_BY_FIELD = {
    "exchange": "vnstock:Listing(source=VCI).symbols_by_exchange",
    "industry": "vnstock:Listing(source=VCI).symbols_by_industries",
    "foreign_room_pct": "vnstock:Trading(source=VCI).price_board",
    "pe": "vnstock:Finance(source=KBS).ratio", "pb": "vnstock:Finance(source=KBS).ratio",
    "roe": "vnstock:Finance(source=KBS).ratio", "dividend_yield": "vnstock:Finance(source=KBS).ratio",
    "market_cap": "vnstock:Company(source=VCI).overview", "shares_outstanding": "vnstock:Company(source=VCI).overview",
    "free_float_est": "derived_local:Company(source=VCI).shareholders",
    "margin_status": "manual_curation:blacklist.csv",
}


def _registry_record(ticker, field, value, transform_version="meta_sync.py@sha256:aaaaaaaaaaaa", observed_at="2026-07-27 19:38"):
    basis = "scrape_time_approximates_unretained_reporting_period" if field in ("pe", "pb", "roe", "dividend_yield") else "scrape_time_live_value"
    return {
        "source": "vnstock_metadata_snapshot", "provider": _PROVIDER_BY_FIELD[field], "ticker": ticker,
        "field": field, "value": value,
        "timestamps": {"observed_at": observed_at, "effective_at": observed_at, "provider_timestamp": None, "timestamp_basis": basis},
        "raw_hash": {"raw_payload_retained": False, "value": None},
        "transform_version": transform_version, "qualification_status": "reported",
        "freshness_sla": {"domain": "vnstock_metadata_snapshot", "cadence_days": 92, "grace_days": 35,
                           "policy_source": 'stock-core-private/freshness_history.py:RULES["vnstock_metadata_snapshot"]'},
    }


def _full_ticker_records(ticker, values, **kwargs):
    return [_registry_record(ticker, f, values.get(f), **kwargs) for f in _FIELDS]


def _write_snapshot(directory: Path, records: list[dict], stamp: str = "20260728T000000Z") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    body = ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode("utf-8")
    content_hash = hashlib.sha256(body).hexdigest()[:12]
    path = directory / f"vnstock_metadata_snapshot_{stamp}_{content_hash}.jsonl"
    path.write_bytes(body)
    return path


class LoadMetadataSliceFromRegistrySnapshotTests(unittest.TestCase):
    def test_valid_ticker_matches_db_slice_key_shape(self):
        with tempfile.TemporaryDirectory() as raw:
            values = {"exchange": "HSX", "industry": "Hóa chất", "foreign_room_pct": 98.49,
                      "pe": 8.38, "pb": 0.51, "roe": 6.75, "market_cap": 2_669_576_000_000.0,
                      "shares_outstanding": 393_742_730.0, "free_float_est": 0.4977,
                      "dividend_yield": 4.0, "margin_status": "margin_cut"}
            path = _write_snapshot(Path(raw), _full_ticker_records("AAA", values))
            result, provenance = builder.load_metadata_slice_from_registry_snapshot("AAA", path)

            expected_keys = {"ticker", "updated", "company_name", "point_in_time_warning",
                              "free_float_warning", "company_name_warning", *_FIELDS}
            self.assertEqual(expected_keys, set(result) - {"dividend_yield_missing_reason", "margin_status_meaning"})
            self.assertEqual(result["exchange"], "HSX")
            self.assertEqual(result["pe"], 8.38)
            self.assertEqual(result["updated"], "2026-07-27 19:38")
            self.assertEqual(len(provenance), 1)
            self.assertEqual(provenance[0]["source_dataset"], "vnstock_metadata_snapshot registry")

    def test_dividend_yield_sentinel_normalized_same_as_db_path(self):
        with tempfile.TemporaryDirectory() as raw:
            values = {f: 1.0 for f in _FIELDS}
            values["dividend_yield"] = -1
            values["margin_status"] = "warning"
            path = _write_snapshot(Path(raw), _full_ticker_records("BBB", values))
            result, _ = builder.load_metadata_slice_from_registry_snapshot("BBB", path)
            self.assertIsNone(result["dividend_yield"])
            self.assertEqual(result["dividend_yield_missing_reason"], "queried_no_value")

    def test_falsy_margin_status_normalized_same_as_db_path(self):
        with tempfile.TemporaryDirectory() as raw:
            values = {f: 1.0 for f in _FIELDS}
            values["margin_status"] = None
            path = _write_snapshot(Path(raw), _full_ticker_records("CCC", values))
            result, _ = builder.load_metadata_slice_from_registry_snapshot("CCC", path)
            self.assertIsNone(result["margin_status"])
            self.assertEqual(result["margin_status_meaning"], "no flagged status under project convention")

    def test_ticker_absent_from_valid_snapshot_returns_empty_with_provenance(self):
        with tempfile.TemporaryDirectory() as raw:
            values = {f: 1.0 for f in _FIELDS}
            path = _write_snapshot(Path(raw), _full_ticker_records("AAA", values))
            result, provenance = builder.load_metadata_slice_from_registry_snapshot("ZZZ", path)
            self.assertEqual(result, {})
            self.assertEqual(len(provenance), 1)  # provenance is unconditional, matching load_metadata_slice

    def test_invalid_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            bad_path = Path(raw) / "not_a_registered_snapshot_name.jsonl"
            bad_path.write_text('{"source": "vnstock_metadata_snapshot"}\n', encoding="utf-8")
            with self.assertRaises(SnapshotError):
                builder.load_metadata_slice_from_registry_snapshot("AAA", bad_path)

    def test_missing_required_field_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            records = [_registry_record("AAA", f, 1.0) for f in _FIELDS if f != "margin_status"]  # drop one field
            path = _write_snapshot(Path(raw), records)
            with self.assertRaises(SnapshotError):
                builder.load_metadata_slice_from_registry_snapshot("AAA", path)

    def test_inconsistent_observed_at_across_fields_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            records = [_registry_record("AAA", f, 1.0, observed_at="2026-07-27 19:38") for f in _FIELDS]
            records[0] = _registry_record("AAA", records[0]["field"], 1.0, observed_at="2026-07-20 00:00")
            path = _write_snapshot(Path(raw), records)
            with self.assertRaises(SnapshotError):
                builder.load_metadata_slice_from_registry_snapshot("AAA", path)

    def test_directory_target_selects_newest_snapshot(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            _write_snapshot(directory, _full_ticker_records("AAA", {f: 1.0 for f in _FIELDS}), stamp="20260727T000000Z")
            _write_snapshot(directory, _full_ticker_records("AAA", {f: 2.0 for f in _FIELDS}), stamp="20260728T000000Z")
            result, _ = builder.load_metadata_slice_from_registry_snapshot("AAA", directory)
            self.assertEqual(result["pe"], 2.0)  # from the newer snapshot, not the older one


class CompareMetadataSlicesTests(unittest.TestCase):
    def _slice(self, **overrides):
        base = {f: 1.0 for f in _FIELDS}
        base.update(overrides)
        return base

    def test_exact_match(self):
        db_slice = self._slice()
        registry_slice = self._slice()
        report = builder.compare_metadata_slices(db_slice, registry_slice)
        self.assertEqual(set(report["exact_match"]), set(_FIELDS))
        self.assertEqual(report["null_mismatch"], [])
        self.assertEqual(report["value_mismatch"], [])
        self.assertEqual(report["provenance_mismatch"], [])
        self.assertTrue(report["is_fully_consistent"])

    def test_null_mismatch(self):
        db_slice = self._slice(pe=None)
        registry_slice = self._slice(pe=8.38)
        report = builder.compare_metadata_slices(db_slice, registry_slice)
        self.assertEqual(report["null_mismatch"], [{"field": "pe", "db_value": None, "registry_value": 8.38}])
        self.assertFalse(report["is_fully_consistent"])

    def test_value_mismatch(self):
        db_slice = self._slice(market_cap=100.0)
        registry_slice = self._slice(market_cap=200.0)
        report = builder.compare_metadata_slices(db_slice, registry_slice)
        self.assertEqual(report["value_mismatch"], [{"field": "market_cap", "db_value": 100.0, "registry_value": 200.0}])

    def test_provenance_mismatch(self):
        db_slice = self._slice(dividend_yield=None, dividend_yield_missing_reason="queried_no_value")
        registry_slice = self._slice(dividend_yield=None)  # same (null) value, no annotation
        report = builder.compare_metadata_slices(db_slice, registry_slice)
        self.assertEqual(
            report["provenance_mismatch"],
            [{"field": "dividend_yield", "db_annotation": "queried_no_value", "registry_annotation": None}],
        )

    def test_deterministic_and_does_not_mutate_inputs(self):
        db_slice = self._slice()
        registry_slice = self._slice(pe=99.0)
        db_copy, registry_copy = dict(db_slice), dict(registry_slice)
        first = builder.compare_metadata_slices(db_slice, registry_slice)
        second = builder.compare_metadata_slices(db_slice, registry_slice)
        self.assertEqual(first, second)
        self.assertEqual(db_slice, db_copy)
        self.assertEqual(registry_slice, registry_copy)


class SelectMetadataLoaderTests(unittest.TestCase):
    def test_default_none_uses_db_loader_only(self):
        with mock.patch.object(builder, "load_metadata_slice", return_value=({"source": "db"}, [])) as db_loader, \
             mock.patch.object(builder, "load_metadata_slice_from_registry_snapshot", return_value=({"source": "registry"}, [])) as registry_loader:
            load = builder._select_metadata_loader(
                "AAA", Path("unused/vn_stock.db"), metadata_source=builder.METADATA_SOURCE_DATABASE
            )
            result, _ = load()
            db_loader.assert_called_once_with("AAA", Path("unused/vn_stock.db"))
            registry_loader.assert_not_called()
            self.assertEqual(result["source"], "db")

    def test_explicit_snapshot_uses_registry_loader_never_db(self):
        snapshot_path = Path("some/snapshot.jsonl")
        with mock.patch.object(builder, "load_metadata_slice", return_value=({"source": "db"}, [])) as db_loader, \
             mock.patch.object(builder, "load_metadata_slice_from_registry_snapshot", return_value=({"source": "registry"}, [])) as registry_loader:
            load = builder._select_metadata_loader(
                "AAA", Path("unused/vn_stock.db"),
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=snapshot_path,
            )
            result, _ = load()
            registry_loader.assert_called_once_with("AAA", snapshot_path)
            db_loader.assert_not_called()  # no DB fallback once a snapshot is requested
            self.assertEqual(result["source"], "registry")

    def test_build_context_package_default_is_none(self):
        default = inspect.signature(builder.build_context_package).parameters["metadata_registry_snapshot"].default
        self.assertIsNone(default)


class ProductionSnapshotShadowCompatibilityTests(unittest.TestCase):
    def test_reads_real_snapshot_read_only_if_present_else_fixture(self):
        real_dir = ROOT.parent / "stock-core-private" / "registry_snapshots" / "metadata"
        real_files = list(real_dir.glob("vnstock_metadata_snapshot_*.jsonl")) if real_dir.is_dir() else []

        if real_files:
            before = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_dir.iterdir()}
            result, provenance = builder.load_metadata_slice_from_registry_snapshot("AAA", real_dir)
            after = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_dir.iterdir()}
            self.assertEqual(before, after)  # read-only: real production directory untouched
            self.assertTrue(result)  # AAA is known to be present in the pilot snapshot
        else:
            with tempfile.TemporaryDirectory() as raw:
                values = {f: 1.0 for f in _FIELDS}
                path = _write_snapshot(Path(raw), _full_ticker_records("AAA", values))
                result, provenance = builder.load_metadata_slice_from_registry_snapshot("AAA", path)

        self.assertEqual(result["ticker"], "AAA")
        self.assertIn("updated", result)
        # Shadow-compare against a hand-built reference (no DB access) to prove
        # compare_metadata_slices works on real-shaped data end to end. A faithful full copy
        # (including any dividend_yield_missing_reason/margin_status_meaning annotation) must
        # compare as an exact match.
        matching_reference = dict(result)
        report = builder.compare_metadata_slices(matching_reference, result)
        self.assertTrue(report["is_fully_consistent"])

        mismatched_reference = dict(result)
        mismatched_reference["pe"] = (mismatched_reference.get("pe") or 0) + 12345.0
        mismatch_report = builder.compare_metadata_slices(mismatched_reference, result)
        self.assertFalse(mismatch_report["is_fully_consistent"])
        self.assertTrue(any(m["field"] == "pe" for m in mismatch_report["value_mismatch"] + mismatch_report["null_mismatch"]))


if __name__ == "__main__":
    unittest.main()
