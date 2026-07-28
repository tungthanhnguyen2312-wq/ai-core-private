"""Tests for the bounded, explicit shadow-comparison CLI (metadata_registry_shadow_compare.py).
Temp SQLite + temp registry snapshot only -- never opens vn_stock.db or any production file."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # matches test_phase9_snapshot_consumer.py's own convention

from builders import metadata_registry_shadow_compare as shadow_cli  # noqa: E402
from builders.metadata_registry_reader import SnapshotError  # noqa: E402

_DB_COLUMNS = (
    "ticker", "exchange", "industry", "foreign_room_pct", "pe", "pb", "roe", "market_cap",
    "shares_outstanding", "free_float_est", "dividend_yield", "margin_status", "updated",
)

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


def _make_db(path: Path, rows: list[tuple]) -> None:
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE metadata(
        ticker TEXT PRIMARY KEY, exchange TEXT, industry TEXT, foreign_room_pct REAL,
        pe REAL, pb REAL, roe REAL, market_cap REAL, shares_outstanding REAL,
        free_float_est REAL, dividend_yield REAL, margin_status TEXT, updated TEXT)""")
    placeholders = ",".join("?" for _ in _DB_COLUMNS)
    conn.executemany(f"INSERT INTO metadata({','.join(_DB_COLUMNS)}) VALUES ({placeholders})", rows)
    conn.commit()
    conn.close()


def _db_row(ticker: str, values: dict, updated: str = "2026-07-27 19:38") -> tuple:
    return (ticker, *(values.get(f) for f in _DB_COLUMNS[1:-1]), updated)


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


def _realistic_values(**overrides) -> dict:
    """Type-correct per field (exchange/industry/margin_status are TEXT; the rest are numeric) --
    using a uniform placeholder like 1.0 for every field would silently corrupt this comparison:
    SQLite's TEXT column affinity coerces a REAL value to the string "1.0" on insert, while the
    JSON-based registry snapshot keeps it as the float 1.0, producing a spurious value_mismatch
    that has nothing to do with the two loaders' actual (correct) behavior."""
    values = {
        "exchange": "HSX", "industry": "Hóa chất", "foreign_room_pct": 98.49,
        "pe": 8.38, "pb": 0.51, "roe": 6.75, "market_cap": 2_669_576_000_000.0,
        "shares_outstanding": 393_742_730.0, "free_float_est": 0.4977,
        "dividend_yield": 4.0, "margin_status": "margin_cut",
    }
    values.update(overrides)
    return values


def _full_registry_records(ticker, values, **kwargs):
    return [_registry_record(ticker, f, values.get(f), **kwargs) for f in shadow_cli.METADATA_FIELDS]


def _write_snapshot(directory: Path, records: list[dict], stamp: str = "20260728T000000Z") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    body = ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode("utf-8")
    content_hash = hashlib.sha256(body).hexdigest()[:12]
    path = directory / f"vnstock_metadata_snapshot_{stamp}_{content_hash}.jsonl"
    path.write_bytes(body)
    return path


class ShadowCompareTests(unittest.TestCase):
    def test_exact_match(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))

            report = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA",))

            self.assertEqual(report["results"]["AAA"]["status"], "compared")
            self.assertTrue(report["results"]["AAA"]["comparison"]["is_fully_consistent"])
            self.assertTrue(report["summary"]["is_fully_consistent"])
            self.assertEqual(report["summary"]["value_mismatch_field_count"], 0)

    def test_value_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as raw:
            db_values = _realistic_values()
            registry_values = dict(db_values)
            registry_values["pe"] = 99.0
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", db_values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", registry_values))

            report = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA",))

            self.assertFalse(report["summary"]["is_fully_consistent"])
            self.assertEqual(report["summary"]["value_mismatch_field_count"], 1)
            self.assertEqual(report["results"]["AAA"]["comparison"]["value_mismatch"][0]["field"], "pe")

    def test_null_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as raw:
            db_values = _realistic_values()
            db_values["market_cap"] = None
            registry_values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", db_values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", registry_values))

            report = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA",))

            self.assertEqual(report["summary"]["null_mismatch_field_count"], 1)
            self.assertEqual(report["results"]["AAA"]["comparison"]["null_mismatch"][0]["field"], "market_cap")

    def test_provenance_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as raw:
            db_values = _realistic_values()
            db_values["dividend_yield"] = -1  # DB path normalizes this to None + an annotation
            registry_values = dict(db_values)
            registry_values["dividend_yield"] = None  # registry: genuinely null, no sentinel, no annotation
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", db_values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", registry_values))

            report = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA",))

            self.assertEqual(report["summary"]["provenance_mismatch_field_count"], 1)
            self.assertEqual(report["results"]["AAA"]["comparison"]["provenance_mismatch"][0]["field"], "dividend_yield")

    def test_missing_ticker_in_registry(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("BBB", values))  # different ticker

            report = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA",))

            self.assertEqual(report["results"]["AAA"]["status"], "missing_in_registry")
            self.assertIsNone(report["results"]["AAA"]["comparison"])
            self.assertIn("AAA", report["summary"]["tickers_missing_in_registry"])
            self.assertFalse(report["summary"]["is_fully_consistent"])

    def test_missing_ticker_in_db(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("BBB", values)])  # different ticker
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))

            report = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA",))

            self.assertEqual(report["results"]["AAA"]["status"], "missing_in_db")
            self.assertIn("AAA", report["summary"]["tickers_missing_in_db"])

    def test_missing_ticker_in_both(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("BBB", values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("CCC", values))

            report = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA",))

            self.assertEqual(report["results"]["AAA"]["status"], "missing_in_both")

    def test_invalid_snapshot_fails_closed(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values)])
            bad_path = Path(raw) / "not_a_registered_snapshot_name.jsonl"
            bad_path.write_text('{"not": "valid"}\n', encoding="utf-8")

            with self.assertRaises(SnapshotError):
                shadow_cli.run_shadow_comparison(db, bad_path, tickers=("AAA",))

    def test_deterministic_report(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values), _db_row("BBB", values)])
            path = _write_snapshot(
                Path(raw) / "snap",
                _full_registry_records("AAA", values) + _full_registry_records("BBB", values),
            )

            first = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA", "BBB"))
            second = shadow_cli.run_shadow_comparison(db, path, tickers=("AAA", "BBB"))
            self.assertEqual(first, second)

    def test_cli_requires_explicit_paths(self):
        with self.assertRaises(SystemExit):
            shadow_cli._parse_args([])
        with self.assertRaises(SystemExit):
            shadow_cli._parse_args(["--db", "x.db"])
        with self.assertRaises(SystemExit):
            shadow_cli._parse_args(["--db", "x.db", "--snapshot", "y.jsonl"])

    def test_cli_end_to_end_writes_report_and_touches_nothing_else(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values)])
            snap_path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))
            output = Path(raw) / "report.json"

            db_before = (db.stat().st_size, db.stat().st_mtime_ns)
            snap_before = (snap_path.stat().st_size, snap_path.stat().st_mtime_ns)

            exit_code = shadow_cli.main([
                "--db", str(db), "--snapshot", str(snap_path), "--output", str(output), "--tickers", "AAA",
            ])

            self.assertEqual(exit_code, 0)
            written = json.loads(output.read_text(encoding="utf-8"))
            self.assertIn("generated_at", written)
            self.assertTrue(written["summary"]["is_fully_consistent"])

            self.assertEqual((db.stat().st_size, db.stat().st_mtime_ns), db_before)  # DB never written to
            self.assertEqual((snap_path.stat().st_size, snap_path.stat().st_mtime_ns), snap_before)  # snapshot untouched


if __name__ == "__main__":
    unittest.main()
