"""Phase 6 shareholder context compatibility tests."""

from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from builders import build_ticker_context as builder  # noqa: E402


class Phase6ShareholderContextTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "fixture.db"
        connection = sqlite3.connect(path)
        connection.executescript(
            """
            CREATE TABLE shareholders(ticker TEXT, shareholder_name TEXT, shares_owned REAL, pct REAL, source TEXT, updated_at TEXT);
            CREATE TABLE shareholders_progress(ticker TEXT PRIMARY KEY, status TEXT, rows INTEGER, updated TEXT);
            CREATE TABLE shareholder_records_v2(
                record_key TEXT PRIMARY KEY,ticker TEXT,holder_name TEXT,normalized_holder_name TEXT,
                shares REAL,ownership_pct REAL,as_of_date TEXT,source_name TEXT,source_reference TEXT,
                verified_at TEXT,fetched_at TEXT,note TEXT,record_origin TEXT,reconciliation_status TEXT,
                conflict_group TEXT,provenance_json TEXT);
            CREATE TABLE shareholder_source_attempts(
                id INTEGER PRIMARY KEY,ticker TEXT,source TEXT,status TEXT,error TEXT,reason TEXT,error_reason TEXT,
                record_count INTEGER,parsed_record_count INTEGER,request_timestamp TEXT,latest_as_of_date TEXT);
            CREATE TABLE shareholder_sync_runs(
                ticker TEXT PRIMARY KEY,final_status TEXT,reason TEXT,raw_record_count INTEGER,
                parsed_record_count INTEGER,deduplicated_record_count INTEGER,manual_override_count INTEGER,
                latest_as_of_date TEXT,freshness_json TEXT,updated TEXT);
            """
        )
        provenance = json.dumps([{"source_name": "Exchange filing", "record_origin": "manual"}])
        connection.execute(
            "INSERT INTO shareholder_records_v2 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            ("key", "PAN", "Verified Holder", "verified holder", 100, None, "2026-06-30",
             "Exchange filing", "https://example.test/filing", "2026-07-01T00:00:00Z",
             None, None, "manual", "accepted", None, provenance),
        )
        connection.execute(
            "INSERT INTO shareholder_source_attempts VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (1, "PAN", "VCI", "source_empty", None, "provider_returned_empty_payload", "provider_returned_empty_payload", 0, 0,
             "2026-07-13T00:00:00+00:00", None),
        )
        connection.execute(
            "INSERT INTO shareholder_sync_runs VALUES(?,?,?,?,?,?,?,?,?,?)",
            ("PAN", "manual_override", "verified_manual_records_merged_without_deleting_api_records",
             0, 0, 1, 1, "2026-06-30",
             json.dumps({"status": "fresh", "latest_as_of_date": "2026-06-30"}), "2026-07-13"),
        )
        connection.execute("INSERT INTO shareholders_progress VALUES('PAN','manual_override',1,'2026-07-13')")
        connection.commit()
        connection.close()
        return path

    def test_phase6_context_exposes_status_attempts_and_manual_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            summary, _ = builder.load_shareholder_slice("PAN", self._database(Path(temporary)))
        self.assertEqual(summary["status"], "manual_override")
        self.assertEqual(summary["sources_attempted"], ["VCI"])
        self.assertEqual(summary["manual_override_count"], 1)
        self.assertEqual(summary["top_holders"][0]["record_origin"], "manual")
        self.assertEqual(summary["top_holders"][0]["pct"], None)
        self.assertEqual(summary["meta"]["status"], "reported")

    def test_later_empty_attempt_keeps_prior_snapshot_without_zero_count(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self._database(Path(temporary))
            connection = sqlite3.connect(path)
            connection.execute(
                """UPDATE shareholder_sync_runs SET final_status='source_empty',
                   reason='configured_sources_returned_no_usable_records',
                   deduplicated_record_count=0,manual_override_count=0,latest_as_of_date=NULL,
                   freshness_json=? WHERE ticker='PAN'""",
                (json.dumps({"status": "unknown", "latest_as_of_date": None}),),
            )
            connection.execute("UPDATE shareholders_progress SET status='source_empty',rows=0 WHERE ticker='PAN'")
            connection.commit()
            connection.close()
            summary, _ = builder.load_shareholder_slice("PAN", path)
        self.assertEqual(summary["status"], "source_empty")
        self.assertEqual(summary["retained_record_count"], 1)
        self.assertEqual(summary["major_shareholders_count"], 1)
        self.assertEqual(summary["latest_as_of_date"], "2026-06-30")

    def test_top_holders_uses_only_latest_valid_snapshot(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self._database(Path(temporary))
            connection = sqlite3.connect(path)
            provenance = json.dumps([])
            connection.executemany(
                "INSERT INTO shareholder_records_v2 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                [
                    ("old", "PAN", "Older majority", "older majority", 100, 90, "2026-03-31", "Source", None, None, None, None, "api", "accepted", None, provenance),
                    ("new-a", "PAN", "Latest first", "latest first", 100, 30, "2026-06-30", "Source", None, None, None, None, "api", "accepted", None, provenance),
                    ("new-b", "PAN", "Latest second", "latest second", 100, 20, "2026-06-30", "Source", None, None, None, None, "api", "accepted", None, provenance),
                    ("bad", "PAN", "Malformed date", "malformed date", 100, 80, "not-a-date", "Source", None, None, None, None, "api", "accepted", None, provenance),
                    ("missing", "PAN", "Missing date", "missing date", 100, 70, None, "Source", None, None, None, None, "api", "accepted", None, provenance),
                ],
            )
            connection.commit()
            connection.close()
            summary, provenance_entries = builder.load_shareholder_slice("PAN", path)
        self.assertEqual(summary["latest_as_of_date"], "2026-06-30")
        self.assertEqual(summary["latest_snapshot_date"], "2026-06-30")
        self.assertEqual(
            [holder["shareholder_name"] for holder in summary["top_holders"]],
            ["Latest first", "Latest second", "Verified Holder"],
        )
        self.assertTrue(all(holder["as_of_date"] == "2026-06-30" for holder in summary["top_holders"]))
        self.assertEqual(provenance_entries[0]["source_keys"]["as_of_date"], "2026-06-30")

    def test_invalid_dates_use_deterministic_unknown_snapshot_fallback(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = self._database(Path(temporary))
            connection = sqlite3.connect(path)
            connection.execute("UPDATE shareholder_records_v2 SET as_of_date='not-a-date' WHERE ticker='PAN'")
            connection.execute(
                "INSERT INTO shareholder_records_v2 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                ("tie", "PAN", "A holder", "a holder", 100, 10, None, "Source", None, None, None, None, "api", "accepted", None, json.dumps([])),
            )
            connection.commit()
            connection.close()
            summary, provenance_entries = builder.load_shareholder_slice("PAN", path)
        self.assertIsNone(summary["latest_as_of_date"])
        self.assertIsNone(summary["latest_snapshot_date"])
        self.assertEqual([holder["shareholder_name"] for holder in summary["top_holders"]], ["A holder", "Verified Holder"])
        self.assertTrue(all(holder["as_of_date"] is None for holder in summary["top_holders"]))
        self.assertEqual(provenance_entries[0]["source_keys"]["as_of_date"], "unknown")


if __name__ == "__main__":
    unittest.main()
