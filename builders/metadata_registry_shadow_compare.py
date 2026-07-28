"""Bounded, explicit, read-only shadow-comparison CLI.

Compares metadata for the same tickers as loaded from `vn_stock.db` (`load_metadata_slice`)
versus an immutable registry snapshot (`load_metadata_slice_from_registry_snapshot`), using
`compare_metadata_slices` for the field-level diff -- no logic is reimplemented here, all three
come from `build_ticker_context.py` / `metadata_registry_reader.py`.

Never writes to any database or snapshot. Never chooses a production path implicitly: --db,
--snapshot, and --output are all required. Not wired into `build_context_package`, the daily
pipeline, or any scheduled job -- this is a standalone, manually-invoked tool.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    from build_ticker_context import (
        compare_metadata_slices,
        load_metadata_slice,
        load_metadata_slice_from_registry_snapshot,
    )
except ModuleNotFoundError:  # importlib-based tests load this file from the workspace root
    from builders.build_ticker_context import (
        compare_metadata_slices,
        load_metadata_slice,
        load_metadata_slice_from_registry_snapshot,
    )

# Mirrors stock-core-private/daily_analysis_pipeline.py's DEFAULT_TICKERS watchlist as of
# 2026-07-27 -- a fixed snapshot/copy for this Consumer-side tool, not a live cross-repo import
# (this repo never imports Producer source).
DEFAULT_WATCHLIST_TICKERS: tuple[str, ...] = ("POW", "SSI", "HPG", "EVF", "PAN", "PNJ", "QNS", "PDR", "GEX")

METADATA_FIELDS: tuple[str, ...] = (
    "exchange", "industry", "foreign_room_pct", "pe", "pb", "roe", "market_cap",
    "shares_outstanding", "free_float_est", "dividend_yield", "margin_status",
)


def compare_ticker(ticker: str, db_path: Path, snapshot: Path) -> dict[str, Any]:
    """One ticker's shadow comparison. Missing from either source is reported as its own status,
    distinct from a field-level mismatch -- never silently skipped, never treated as a match."""
    db_slice, _ = load_metadata_slice(ticker, db_path)
    registry_slice, _ = load_metadata_slice_from_registry_snapshot(ticker, snapshot)  # SnapshotError propagates -- fail closed

    db_missing = not db_slice
    registry_missing = not registry_slice
    if db_missing and registry_missing:
        return {"status": "missing_in_both", "comparison": None}
    if db_missing:
        return {"status": "missing_in_db", "comparison": None}
    if registry_missing:
        return {"status": "missing_in_registry", "comparison": None}
    return {"status": "compared", "comparison": compare_metadata_slices(db_slice, registry_slice)}


def run_shadow_comparison(
    db_path: Path,
    snapshot: Path,
    tickers: tuple[str, ...] = DEFAULT_WATCHLIST_TICKERS,
) -> dict[str, Any]:
    """Pure and deterministic: no wall-clock, no randomness. The same DB snapshot, registry
    snapshot, and ticker list always produce byte-identical results. (The CLI adds a
    `generated_at` timestamp on top of this when writing to a file -- see main().)"""
    results = {ticker: compare_ticker(ticker, db_path, snapshot) for ticker in tickers}

    tickers_missing_in_db = [t for t in tickers if results[t]["status"] in ("missing_in_db", "missing_in_both")]
    tickers_missing_in_registry = [t for t in tickers if results[t]["status"] in ("missing_in_registry", "missing_in_both")]
    compared = [results[t]["comparison"] for t in tickers if results[t]["comparison"] is not None]

    summary = {
        "tickers_compared": len(compared),
        "tickers_missing_in_db": tickers_missing_in_db,
        "tickers_missing_in_registry": tickers_missing_in_registry,
        "exact_match_field_count": sum(len(c["exact_match"]) for c in compared),
        "null_mismatch_field_count": sum(len(c["null_mismatch"]) for c in compared),
        "value_mismatch_field_count": sum(len(c["value_mismatch"]) for c in compared),
        "provenance_mismatch_field_count": sum(len(c["provenance_mismatch"]) for c in compared),
        "is_fully_consistent": (
            all(c["is_fully_consistent"] for c in compared)
            and not tickers_missing_in_db
            and not tickers_missing_in_registry
        ),
    }
    return {
        "db_path": str(db_path),
        "snapshot_path": str(snapshot),
        "tickers": list(tickers),
        "fields": list(METADATA_FIELDS),
        "results": results,
        "summary": summary,
    }


def _parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bounded, read-only shadow comparison between vn_stock.db metadata and an "
        "immutable registry snapshot. --db, --snapshot, and --output are all required -- there "
        "is no default or auto-discovered production path."
    )
    parser.add_argument("--db", required=True, type=Path, help="path to vn_stock.db")
    parser.add_argument("--snapshot", required=True, type=Path, help="registry snapshot file or directory")
    parser.add_argument("--output", required=True, type=Path, help="path to write the JSON report")
    parser.add_argument("--tickers", nargs="*", default=None, help="ticker subset (default: the 9-ticker watchlist)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse_args(argv)
    tickers = tuple(args.tickers) if args.tickers else DEFAULT_WATCHLIST_TICKERS
    report = run_shadow_comparison(args.db, args.snapshot, tickers)
    report["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(f"[metadata_registry_shadow_compare] wrote report to {args.output}")
    print(f"[metadata_registry_shadow_compare] is_fully_consistent={report['summary']['is_fully_consistent']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
