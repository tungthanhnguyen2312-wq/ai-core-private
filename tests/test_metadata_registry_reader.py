from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# metadata_registry_reader.py lives in builders/, not the repo root -- load by explicit path
# rather than a plain top-level import, same as the reader's own sibling-module loading.
reader = _load_module("metadata_registry_reader_under_test", ROOT / "builders" / "metadata_registry_reader.py")
_validator = _load_module("registry_reader_test_schema_validator", ROOT / "builders" / "validate_json_schema_subset.py")
_SCHEMA = _validator.load_json(reader.SCHEMA_PATH)


def _record(ticker="AAA", field="pe", value=1.0, transform_version="meta_sync.py@sha256:aaaaaaaaaaaa", **overrides):
    basis = "scrape_time_approximates_unretained_reporting_period" if field in ("pe", "pb", "roe", "dividend_yield") else "scrape_time_live_value"
    provider = {
        "exchange": "vnstock:Listing(source=VCI).symbols_by_exchange",
        "industry": "vnstock:Listing(source=VCI).symbols_by_industries",
        "foreign_room_pct": "vnstock:Trading(source=VCI).price_board",
        "pe": "vnstock:Finance(source=KBS).ratio", "pb": "vnstock:Finance(source=KBS).ratio",
        "roe": "vnstock:Finance(source=KBS).ratio", "dividend_yield": "vnstock:Finance(source=KBS).ratio",
        "market_cap": "vnstock:Company(source=VCI).overview", "shares_outstanding": "vnstock:Company(source=VCI).overview",
        "free_float_est": "derived_local:Company(source=VCI).shareholders",
        "margin_status": "manual_curation:blacklist.csv",
    }.get(field, "vnstock:Finance(source=KBS).ratio")  # fallback keeps the fixture buildable even
    # for a deliberately-invalid `field` value (used to test schema-enum rejection)
    record = {
        "source": "vnstock_metadata_snapshot",
        "provider": provider,
        "ticker": ticker,
        "field": field,
        "value": value,
        "timestamps": {
            "observed_at": "2026-07-27 19:38",
            "effective_at": "2026-07-27 19:38",
            "provider_timestamp": None,
            "timestamp_basis": basis,
        },
        "raw_hash": {"raw_payload_retained": False, "value": None},
        "transform_version": transform_version,
        "qualification_status": "reported",
        "freshness_sla": {
            "domain": "vnstock_metadata_snapshot", "cadence_days": 92, "grace_days": 35,
            "policy_source": 'stock-core-private/freshness_history.py:RULES["vnstock_metadata_snapshot"]',
        },
    }
    record.update(overrides)
    return record


def _jsonl_body(records: list[dict]) -> bytes:
    return ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode("utf-8")


def _write_snapshot(directory: Path, records: list[dict], stamp: str = "20260728T000000Z", corrupt_hash: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    body = _jsonl_body(records)
    content_hash = hashlib.sha256(body).hexdigest()[:12]
    if corrupt_hash:
        content_hash = "0" * 12 if content_hash != "0" * 12 else "1" * 12
    path = directory / f"vnstock_metadata_snapshot_{stamp}_{content_hash}.jsonl"
    path.write_bytes(body)
    return path


class ReadSnapshotExplicitFileTests(unittest.TestCase):
    def test_valid_file_returns_grouped_records(self):
        with tempfile.TemporaryDirectory() as raw:
            path = _write_snapshot(Path(raw), [
                _record(ticker="AAA", field="pe", value=8.38),
                _record(ticker="AAA", field="pb", value=0.51),
                _record(ticker="BBB", field="pe", value=12.0),
            ])
            grouped = reader.read_snapshot(path)
            self.assertEqual(set(grouped), {"AAA", "BBB"})
            self.assertEqual(set(grouped["AAA"]), {"pe", "pb"})
            self.assertEqual(grouped["AAA"]["pe"]["value"], 8.38)
            self.assertEqual(grouped["BBB"]["pe"]["value"], 12.0)

    def test_never_modifies_source_file(self):
        with tempfile.TemporaryDirectory() as raw:
            path = _write_snapshot(Path(raw), [_record()])
            before = (path.stat().st_size, path.read_bytes())
            reader.read_snapshot(path)
            after = (path.stat().st_size, path.read_bytes())
            self.assertEqual(before, after)

    def test_deterministic_grouped_output(self):
        with tempfile.TemporaryDirectory() as raw:
            path = _write_snapshot(Path(raw), [_record(ticker="AAA", field="pe"), _record(ticker="BBB", field="roe")])
            first = reader.read_snapshot(path)
            second = reader.read_snapshot(path)
            self.assertEqual(first, second)

    def test_malformed_filename_is_rejected_even_if_content_is_valid(self):
        with tempfile.TemporaryDirectory() as raw:
            good_path = _write_snapshot(Path(raw), [_record()])
            bad_path = good_path.with_name("not_a_registered_snapshot_name.jsonl")
            bad_path.write_bytes(good_path.read_bytes())
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(bad_path)

    def test_content_hash_mismatch_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = _write_snapshot(Path(raw), [_record()], corrupt_hash=True)
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(path)

    def test_schema_violation_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            bad_record = _record(field="not_a_real_field")
            path = _write_snapshot(Path(raw), [_record(), bad_record])
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(path)

    def test_malformed_json_line_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            good = _jsonl_body([_record()])[:-1]  # drop trailing newline, we'll append manually
            body = good + b"\n{not valid json\n"
            content_hash = hashlib.sha256(body).hexdigest()[:12]
            path = Path(raw) / f"vnstock_metadata_snapshot_20260728T000000Z_{content_hash}.jsonl"
            path.write_bytes(body)
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(path)

    def test_duplicate_identity_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = _write_snapshot(Path(raw), [
                _record(ticker="AAA", field="pe", value=1.0),
                _record(ticker="AAA", field="pe", value=2.0),
            ])
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(path)

    def test_mixed_transform_version_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            path = _write_snapshot(Path(raw), [
                _record(ticker="AAA", field="pe", transform_version="meta_sync.py@sha256:aaaaaaaaaaaa"),
                _record(ticker="BBB", field="pe", transform_version="meta_sync.py@sha256:bbbbbbbbbbbb"),
            ])
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(path)

    def test_empty_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            body = b""
            content_hash = hashlib.sha256(body).hexdigest()[:12]
            path = Path(raw) / f"vnstock_metadata_snapshot_20260728T000000Z_{content_hash}.jsonl"
            path.write_bytes(body)
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(path)

    def test_nonexistent_path_is_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(Path(raw) / "does_not_exist.jsonl")


class DirectoryDiscoveryTests(unittest.TestCase):
    def test_selects_newest_by_timestamp(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            older = _write_snapshot(directory, [_record(ticker="AAA")], stamp="20260727T000000Z")
            newer = _write_snapshot(directory, [_record(ticker="BBB")], stamp="20260728T000000Z")
            selected = reader.select_newest_snapshot(directory)
            self.assertEqual(selected, newer)
            self.assertNotEqual(selected, older)

    def test_read_snapshot_on_directory_uses_newest(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            _write_snapshot(directory, [_record(ticker="AAA")], stamp="20260727T000000Z")
            _write_snapshot(directory, [_record(ticker="BBB")], stamp="20260728T000000Z")
            grouped = reader.read_snapshot(directory)
            self.assertEqual(set(grouped), {"BBB"})

    def test_ambiguous_same_timestamp_raises(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            _write_snapshot(directory, [_record(ticker="AAA", value=1.0)], stamp="20260728T000000Z")
            _write_snapshot(directory, [_record(ticker="AAA", value=2.0)], stamp="20260728T000000Z")
            with self.assertRaises(reader.SnapshotError):
                reader.select_newest_snapshot(directory)
            with self.assertRaises(reader.SnapshotError):
                reader.read_snapshot(directory)

    def test_ignores_temp_and_unrelated_files(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            valid = _write_snapshot(directory, [_record()], stamp="20260728T000000Z")
            (directory / ".tmp-abcd1234.jsonl").write_bytes(b"not a real snapshot, mid-write")
            (directory / "notes.txt").write_text("unrelated file")
            selected = reader.select_newest_snapshot(directory)
            self.assertEqual(selected, valid)

    def test_empty_directory_raises(self):
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(reader.SnapshotError):
                reader.select_newest_snapshot(Path(raw))

    def test_directory_with_only_temp_files_raises(self):
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            (directory / ".tmp-abcd1234.jsonl").write_bytes(b"mid-write")
            with self.assertRaises(reader.SnapshotError):
                reader.select_newest_snapshot(directory)


class ModuleGuardrailTests(unittest.TestCase):
    def test_no_database_or_producer_dependency_in_source(self):
        source = Path(reader.__file__).read_text(encoding="utf-8")
        self.assertNotIn("sqlite3", source)
        self.assertNotIn("vn_stock.db", source)
        # The docstring legitimately *mentions* metadata_registry_export.py (documenting where the
        # writer lives); what must never appear is an actual import of it.
        self.assertIsNone(re.search(r"^\s*(import|from)\s+metadata_registry_export\b", source, re.MULTILINE))


class ProductionSnapshotCompatibilityTests(unittest.TestCase):
    def test_reads_real_production_snapshot_if_present_else_fixture(self):
        expected_fields = set(_SCHEMA["properties"]["field"]["enum"])
        real_dir = ROOT.parent / "stock-core-private" / "registry_snapshots" / "metadata"
        real_files = list(real_dir.glob("vnstock_metadata_snapshot_*.jsonl")) if real_dir.is_dir() else []

        if real_files:
            before = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_dir.iterdir()}
            grouped = reader.read_snapshot(real_dir)
            after = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_dir.iterdir()}
            self.assertEqual(before, after)  # read-only: real production directory untouched
        else:
            with tempfile.TemporaryDirectory() as raw:
                directory = Path(raw)
                _write_snapshot(directory, [
                    _record(ticker="AAA", field="pe"), _record(ticker="AAA", field="pb"),
                    _record(ticker="BBB", field="pe"),
                ])
                grouped = reader.read_snapshot(directory)

        self.assertGreater(len(grouped), 0)
        for ticker, fields in grouped.items():
            self.assertTrue(re.match(r"^[A-Z0-9]{2,10}$", ticker))
            self.assertTrue(set(fields).issubset(expected_fields))
            for field_name, record in fields.items():
                self.assertEqual(record["ticker"], ticker)
                self.assertEqual(record["field"], field_name)
                self.assertEqual(_validator.validate(record, _SCHEMA), [])


if __name__ == "__main__":
    unittest.main()
