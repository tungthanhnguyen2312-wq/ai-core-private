"""Frozen-clock context tests; all data loaders are mocked (no production DB access)."""
from __future__ import annotations
import copy
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builders import build_ticker_context as builder

CLOCK_A = "2026-07-28T12:00:00Z"
CLOCK_B = "2026-07-29T12:00:00Z"

class FrozenClockTests(unittest.TestCase):
    def build(self, clock=CLOCK_A, source="database"):
        metadata = {"ticker":"AAA","exchange":"HSX","industry":"Utilities","updated":"2026-07-28"}
        def select(_ticker, _db, selected, *_rest):
            dataset = "metadata" if selected == "database" else "vnstock_metadata_snapshot registry"
            return lambda: (copy.deepcopy(metadata), [{"source_file": dataset, "source_dataset": dataset, "source_keys": {"ticker":"AAA"}, "transformation": "Read-only primary-key query; -1 dividend sentinel normalized to null." if dataset == "metadata" else "Registry snapshot record group converted to the standard metadata slice shape; -1 dividend sentinel normalized to null."}])
        def news(_ticker, *, now=None):
            return ({"status":"no_company_specific_news", "cutoff": now.isoformat().replace("+00:00","Z") if now else "live", "meta":{"status":"source_empty"}, "coverage":{}}, [])
        patches = [mock.patch.object(builder,"check_ticker_coverage",return_value={}),mock.patch.object(builder,"_select_metadata_loader",side_effect=select),mock.patch.object(builder,"load_price_slice",return_value=({},[])),mock.patch.object(builder,"load_financial_slice",return_value=({},[])),mock.patch.object(builder,"load_news_slice",side_effect=news),mock.patch.object(builder,"load_shareholder_slice",return_value=({},[])),mock.patch.object(builder,"load_technical_slice",return_value=({},[])),mock.patch.object(builder,"load_share_reconciliation_slice",return_value=({},[])),mock.patch.object(builder,"load_vnstock_entity_type",return_value="corporate")]
        with patches[0],patches[1],patches[2],patches[3],patches[4],patches[5],patches[6],patches[7],patches[8]:
            return builder.build_context_package("AAA", {"identity":{}}, {}, metadata_source=source, build_clock=clock)
    def test_same_input_and_frozen_clock_is_deterministic(self): self.assertEqual(self.build(), self.build())
    def test_clock_changes_only_documented_time_fields(self):
        a,b=self.build(CLOCK_A),self.build(CLOCK_B)
        self.assertNotEqual(a["generated_at"],b["generated_at"]);self.assertNotEqual(a["news_summary"]["cutoff"],b["news_summary"]["cutoff"]);self.assertNotEqual(a["provenance"][-1]["generated_at"],b["provenance"][-1]["generated_at"])
        for x in (a,b): x["generated_at"]=x["news_summary"]["cutoff"]=x["provenance"][-1]["generated_at"]="TIME"
        self.assertEqual(a,b)
    def test_database_and_registry_same_clock_match_nonmetadata(self):
        db,reg=self.build(source="database"),self.build(source="registry_snapshot")
        self.assertEqual(db["metadata"],reg["metadata"]);self.assertEqual(db["news_summary"],reg["news_summary"]);self.assertEqual(db["generated_at"],reg["generated_at"])
    def test_default_is_optional_and_utc_only(self):
        self.assertIsNone(builder.build_context_package.__defaults__[-1]);self.assertEqual(builder.resolve_build_clock(CLOCK_A),datetime(2026,7,28,12,tzinfo=timezone.utc))
        with self.assertRaises(ValueError): builder.resolve_build_clock("2026-07-28T12:00:00+07:00")

if __name__ == "__main__": unittest.main()