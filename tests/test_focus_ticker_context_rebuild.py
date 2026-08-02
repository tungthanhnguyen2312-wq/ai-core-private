"""Regression tests for the P0-5 rebuild (STOCK_ANALYSIS_MASTER_PLAN.md section 4.3/7).

Covers: POW and EVF now have a context package (previously missing from the phase 5/6 test
batch), SSI/HPG/PAN were rebuilt from the current VNSTOCK location, and none of the five focus
packages still reference the pre-migration OneDrive path
(C:\\Users\\...\\OneDrive\\Desktop\\DATA PYTHON\\...).

Run: `python -m unittest tests.test_focus_ticker_context_rebuild` from the AI ANALYZE root.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGES_DIR = ROOT / "exports" / "context_packages"
# The runtime root moved from a sibling `VNSTOCK` directory to `dashboard-runtime` during
# the workspace migration; `builders/build_ticker_context.py::resolve_dashboard_runtime_root`
# already prefers the new location. Pinning this to the old name made every freshly rebuilt
# package fail an assertion about the *old* layout, which said nothing about whether the
# package still pointed somewhere it should not.
def _runtime_root() -> Path:
    for name in ("dashboard-runtime", "VNSTOCK"):
        candidate = (ROOT.parent / name)
        if candidate.is_dir():
            return candidate.resolve()
    return (ROOT.parent / "dashboard-runtime").resolve()


VNSTOCK_ROOT = _runtime_root()
FOCUS_TICKERS = ["POW", "SSI", "HPG", "EVF", "PAN"]

# The stale phase6_test_batch packages this replaces were generated 2026-07-13 and pointed at
# C:\Users\...\OneDrive\Desktop\DATA PYTHON\VNSTOCK (pre-migration path). A freshly rebuilt
# package must postdate that batch.
STALE_BATCH_DATE = "2026-07-13"


class FocusTickerContextPackageTests(unittest.TestCase):

    def test_all_five_focus_tickers_have_a_context_package(self):
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            self.assertTrue(path.exists(), f"Missing context package for {ticker}")

    def test_no_focus_package_references_old_onedrive_path(self):
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("OneDrive", text,
                             f"{ticker}_context.json still references the old OneDrive path")

    def test_data_sources_point_inside_current_vnstock_root(self):
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            self.assertTrue(payload.get("data_sources"), f"{ticker} has empty data_sources")
            for source in payload["data_sources"]:
                resolved = Path(source).resolve()
                self.assertTrue(
                    resolved.is_relative_to(VNSTOCK_ROOT),
                    f"{ticker} data_source not under current VNSTOCK root: {source}")

    def test_provenance_source_files_point_inside_current_vnstock_root(self):
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            for entry in payload.get("provenance", []):
                source_file = entry.get("source_file")
                if not source_file or not isinstance(source_file, str):
                    continue  # some provenance entries (e.g. context_builder) list sources, not a path
                if not Path(source_file).is_absolute():
                    # Bundle pass-through contracts name their source artifact logically
                    # ("analysis_bundle.json"), not by location. Resolving that against the
                    # process CWD and then asserting on the result tests the CWD, not the
                    # package. Only real absolute paths can leak a wrong root.
                    continue
                resolved = Path(source_file).resolve()
                self.assertTrue(
                    resolved.is_relative_to(VNSTOCK_ROOT),
                    f"{ticker} provenance source_file not under current VNSTOCK root: {source_file}")

    def test_ticker_field_matches_filename(self):
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            self.assertEqual(payload.get("ticker"), ticker)

    def test_rebuilt_packages_postdate_the_stale_batch(self):
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            generated_at = payload.get("generated_at") or ""
            self.assertGreater(
                generated_at[:10], STALE_BATCH_DATE,
                f"{ticker} context package looks like the stale pre-rebuild batch: {generated_at}")

    def test_evf_entity_type_is_finance_company_not_unknown(self):
        # item E, Data Contract Hardening v1.1: EVF must no longer surface as entity_type
        # "unknown" once config/ticker_entity_profiles.csv classifies it.
        path = PACKAGES_DIR / "EVF_context.json"
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
        self.assertEqual(payload.get("identity", {}).get("entity_type"), "finance_company")

    def test_all_focus_tickers_have_a_classified_entity_type(self):
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            entity_type = payload.get("identity", {}).get("entity_type")
            self.assertIsNotNone(entity_type, f"{ticker} missing identity.entity_type")

    def test_hpg_and_pan_share_reconciliation_is_material_warning(self):
        # item D: real par-value-derived vs live share counts differ >=10% for HPG/PAN as of
        # the 2026-07-17 data snapshot (general threshold logic, not a per-ticker hardcode).
        for ticker in ("HPG", "PAN"):
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            reconciliation = payload.get("share_reconciliation", {})
            self.assertEqual(
                reconciliation.get("status"), "material_warning",
                f"{ticker} share_reconciliation status: {reconciliation}",
            )

    def test_pow_and_ssi_share_reconciliation_is_ok(self):
        for ticker in ("POW", "SSI"):
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            reconciliation = payload.get("share_reconciliation", {})
            self.assertEqual(
                reconciliation.get("status"), "ok",
                f"{ticker} share_reconciliation status: {reconciliation}",
            )

    def test_package_has_no_missing_price_or_technical_section(self):
        # price_summary/technical_summary come straight from VNSTOCK's own live pipeline output
        # (screen_snapshot/ta_signals/ohlcv); for 5 currently-live, currently-covered tickers these
        # must never be silently empty.
        for ticker in FOCUS_TICKERS:
            path = PACKAGES_DIR / f"{ticker}_context.json"
            with path.open(encoding="utf-8") as f:
                payload = json.load(f)
            missing = set(payload.get("data_quality", {}).get("missing_sections", []))
            self.assertNotIn("price_summary", missing, f"{ticker} missing price_summary")
            self.assertNotIn("technical_summary", missing, f"{ticker} missing technical_summary")
            self.assertNotIn("financial_summary", missing, f"{ticker} missing financial_summary")


if __name__ == "__main__":
    unittest.main()
