"""Tests for the explicit metadata_source configuration and registry_shadow_gate added to
build_ticker_context.py's _select_metadata_loader / build_context_package.

Temp SQLite + temp registry snapshot only, except the one production-snapshot compatibility test,
which is read-only against the real *snapshot* (never the real database) and falls back to a
fixture if the snapshot is absent.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # matches test_phase9_snapshot_consumer.py's own convention

from builders import build_ticker_context as builder  # noqa: E402

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

_FIELDS = tuple(f for f in _DB_COLUMNS if f not in ("ticker", "updated"))


def _realistic_values(**overrides) -> dict:
    values = {
        "exchange": "HSX", "industry": "Hóa chất", "foreign_room_pct": 98.49,
        "pe": 8.38, "pb": 0.51, "roe": 6.75, "market_cap": 2_669_576_000_000.0,
        "shares_outstanding": 393_742_730.0, "free_float_est": 0.4977,
        "dividend_yield": 4.0, "margin_status": "margin_cut",
    }
    values.update(overrides)
    return values


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
    return (ticker, *(values.get(f) for f in _FIELDS), updated)


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


def _full_registry_records(ticker, values, **kwargs):
    return [_registry_record(ticker, f, values.get(f), **kwargs) for f in _FIELDS]


def _write_snapshot(directory: Path, records: list[dict], stamp: str = "20260728T000000Z") -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    body = ("\n".join(json.dumps(r, ensure_ascii=False) for r in records) + "\n").encode("utf-8")
    content_hash = hashlib.sha256(body).hexdigest()[:12]
    path = directory / f"vnstock_metadata_snapshot_{stamp}_{content_hash}.jsonl"
    path.write_bytes(body)
    return path


class DefaultSourceUnchangedTests(unittest.TestCase):
    def test_default_source_constant_is_database(self):
        self.assertEqual(inspect.signature(builder.build_context_package).parameters["metadata_source"].default,
                          builder.METADATA_SOURCE_DATABASE)
        self.assertEqual(builder.METADATA_SOURCE_DATABASE, "database")

    def test_default_call_uses_db_loader_structure_unchanged(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values)])

            load = builder._select_metadata_loader("AAA", db)  # every new arg at its default
            result, provenance = load()

            self.assertEqual(result["ticker"], "AAA")
            self.assertEqual(result["exchange"], "HSX")
            self.assertEqual(provenance[0]["source_dataset"], "metadata")  # unchanged DB provenance shape

    def test_default_ignores_snapshot_arg_when_source_is_database(self):
        with mock.patch.object(builder, "load_metadata_slice", return_value=({"source": "db"}, [])) as db_loader, \
             mock.patch.object(builder, "load_metadata_slice_from_registry_snapshot", return_value=({"source": "registry"}, [])) as registry_loader:
            load = builder._select_metadata_loader(
                "AAA", Path("unused.db"),
                metadata_source=builder.METADATA_SOURCE_DATABASE,
                metadata_registry_snapshot=Path("some/snapshot"),  # present but source is still "database"
            )
            result, _ = load()
            db_loader.assert_called_once()
            registry_loader.assert_not_called()
            self.assertEqual(result["source"], "db")


class RegistrySourceConfigTests(unittest.TestCase):
    def test_explicit_registry_source_succeeds(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))
            load = builder._select_metadata_loader(
                "AAA", Path("unused.db"),
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=path,
            )
            result, provenance = load()
            self.assertEqual(result["ticker"], "AAA")
            self.assertEqual(result["exchange"], "HSX")
            self.assertEqual(provenance[0]["source_dataset"], "vnstock_metadata_snapshot registry")

    def test_unknown_metadata_source_fails_closed(self):
        with self.assertRaises(builder.MetadataSourceConfigError):
            builder._select_metadata_loader("AAA", Path("unused.db"), metadata_source="csv_export")

    def test_registry_source_without_path_fails_closed(self):
        with self.assertRaises(builder.MetadataSourceConfigError):
            builder._select_metadata_loader(
                "AAA", Path("unused.db"), metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT
            )

    def test_build_context_package_accepts_new_params_with_safe_defaults(self):
        sig = inspect.signature(builder.build_context_package)
        self.assertIsNone(sig.parameters["metadata_registry_snapshot"].default)
        self.assertEqual(sig.parameters["metadata_source"].default, "database")
        self.assertEqual(sig.parameters["registry_shadow_gate"].default, False)


class RegistryShadowGateTests(unittest.TestCase):
    def test_gate_allows_on_exact_match(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))

            load = builder._select_metadata_loader(
                "AAA", db,
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=path,
                registry_shadow_gate=True,
            )
            result, _ = load()
            self.assertEqual(result["ticker"], "AAA")
            self.assertEqual(result["pe"], 8.38)

    def test_gate_blocks_on_value_mismatch(self):
        with tempfile.TemporaryDirectory() as raw:
            db_values = _realistic_values()
            registry_values = _realistic_values(pe=999.0)  # disagrees with DB
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", db_values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", registry_values))

            load = builder._select_metadata_loader(
                "AAA", db,
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=path,
                registry_shadow_gate=True,
            )
            with self.assertRaises(builder.RegistryPromotionBlocked):
                load()

    def test_gate_blocks_on_ticker_missing_from_db(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("BBB", values)])  # AAA absent from DB
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))

            load = builder._select_metadata_loader(
                "AAA", db,
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=path,
                registry_shadow_gate=True,
            )
            with self.assertRaises(builder.RegistryPromotionBlocked):
                load()

    def test_gate_disabled_ignores_mismatch(self):
        """registry_shadow_gate defaults to False -- a mismatch must not block unless the caller
        explicitly opts into the gate."""
        with tempfile.TemporaryDirectory() as raw:
            db_values = _realistic_values()
            registry_values = _realistic_values(pe=999.0)
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", db_values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", registry_values))

            load = builder._select_metadata_loader(
                "AAA", db,
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=path,
                # registry_shadow_gate omitted -> False
            )
            result, _ = load()
            self.assertEqual(result["pe"], 999.0)  # registry value served, ungated

    def test_no_db_fallback_when_gate_blocks(self):
        """When the gate blocks, the exception propagates -- the DB loader's data is never
        substituted as a silent result, even though the gate itself legitimately read the DB for
        comparison purposes."""
        with tempfile.TemporaryDirectory() as raw:
            db_values = _realistic_values()
            registry_values = _realistic_values(pe=999.0)
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", db_values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", registry_values))

            load = builder._select_metadata_loader(
                "AAA", db,
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=path,
                registry_shadow_gate=True,
            )
            try:
                load()
                self.fail("expected RegistryPromotionBlocked")
            except builder.RegistryPromotionBlocked:
                pass  # no result was ever produced -- nothing to check for DB-sourced substitution

    def test_gate_writes_no_artifact_without_explicit_output(self):
        with tempfile.TemporaryDirectory() as raw:
            values = _realistic_values()
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values)])
            path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))

            before = set(Path(raw).rglob("*"))
            from builders.metadata_registry_shadow_compare import check_registry_promotion_gate
            result = check_registry_promotion_gate("AAA", db, path)  # no output=
            after = set(Path(raw).rglob("*"))

            self.assertEqual(result["status"], "compared")
            self.assertEqual(before, after)  # no new file appeared anywhere under raw


class MultiTickerDeterminismTests(unittest.TestCase):
    def test_multiple_tickers_deterministic_across_repeated_loads(self):
        with tempfile.TemporaryDirectory() as raw:
            values_a, values_b = _realistic_values(), _realistic_values(pe=12.0, exchange="HNX")
            db = Path(raw) / "vn_stock.db"
            _make_db(db, [_db_row("AAA", values_a), _db_row("BBB", values_b)])
            path = _write_snapshot(
                Path(raw) / "snap",
                _full_registry_records("AAA", values_a) + _full_registry_records("BBB", values_b),
            )

            def load_both():
                return {
                    ticker: builder._select_metadata_loader(
                        ticker, db,
                        metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                        metadata_registry_snapshot=path,
                        registry_shadow_gate=True,
                    )()[0]
                    for ticker in ("AAA", "BBB")
                }

            first, second = load_both(), load_both()
            self.assertEqual(first, second)
            self.assertEqual(first["AAA"]["exchange"], "HSX")
            self.assertEqual(first["BBB"]["exchange"], "HNX")


class ProductionSnapshotConfigCompatibilityTests(unittest.TestCase):
    def test_registry_source_config_against_real_snapshot_if_present_else_fixture(self):
        real_dir = ROOT.parent / "stock-core-private" / "registry_snapshots" / "metadata"
        real_files = list(real_dir.glob("vnstock_metadata_snapshot_*.jsonl")) if real_dir.is_dir() else []

        if real_files:
            before = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_dir.iterdir()}
            load = builder._select_metadata_loader(
                "AAA", Path("unused.db"),  # gate disabled -> DB path never opened
                metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                metadata_registry_snapshot=real_dir,
            )
            result, _ = load()
            after = {p.name: (p.stat().st_size, p.stat().st_mtime_ns) for p in real_dir.iterdir()}
            self.assertEqual(before, after)  # read-only: real snapshot directory untouched
            self.assertTrue(result)
            self.assertEqual(result["ticker"], "AAA")
        else:
            with tempfile.TemporaryDirectory() as raw:
                values = _realistic_values()
                path = _write_snapshot(Path(raw) / "snap", _full_registry_records("AAA", values))
                load = builder._select_metadata_loader(
                    "AAA", Path("unused.db"),
                    metadata_source=builder.METADATA_SOURCE_REGISTRY_SNAPSHOT,
                    metadata_registry_snapshot=path,
                )
                result, _ = load()
                self.assertEqual(result["ticker"], "AAA")


if __name__ == "__main__":
    unittest.main()
