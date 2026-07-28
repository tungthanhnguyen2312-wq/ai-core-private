"""Bounded, explicit, read-only shadow-comparison CLI.

Compares metadata for the same tickers as loaded from `vn_stock.db` (`load_metadata_slice`)
versus an immutable registry snapshot (`load_metadata_slice_from_registry_snapshot`), using
`compare_metadata_slices` for the field-level diff -- no logic is reimplemented here, all three
come from `build_ticker_context.py` / `metadata_registry_reader.py`.

Never writes to any database or snapshot. Never chooses a production path implicitly: --db,
--snapshot, and --output are all required. Not wired into `build_context_package`, the daily
pipeline, or any scheduled job -- this is a standalone, manually-invoked tool.

`check_registry_promotion_gate()` reuses `compare_ticker()` as a single-ticker preflight gate
that `build_ticker_context.py`'s optional `registry_shadow_gate` calls before trusting registry
data for one ticker; see that module for how a gate failure blocks the metadata section.
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


def check_registry_promotion_gate(
    ticker: str,
    db_path: Path,
    snapshot: Path,
    output: Path | None = None,
) -> dict[str, Any]:
    """Preflight promotion gate for one ticker: reuses compare_ticker (the same logic the CLI
    itself uses -- no separate comparison implementation) rather than deciding pass/fail on its
    own terms. Never writes anything unless the caller passes an explicit output path, so this is
    safe to call from inside a hot loader path (build_ticker_context.py's registry_shadow_gate)
    with zero implicit file I/O, and equally usable standalone with a persisted report."""
    result = compare_ticker(ticker, db_path, snapshot)
    if output is not None:
        report = {
            "ticker": ticker,
            "db_path": str(db_path),
            "snapshot_path": str(snapshot),
            **result,
        }
        output.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    return result


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

REGISTRY_METADATA_SOURCE_DATASET = "vnstock_metadata_snapshot registry"
REGISTRY_METADATA_TRANSFORMATION = (
    "Registry snapshot record group converted to the standard metadata slice shape; "
    "-1 dividend sentinel normalized to null."
)


def compare_context_semantic_invariance(
    database_context: dict[str, Any],
    registry_context: dict[str, Any],
    snapshot_path: Path,
) -> dict[str, Any]:
    """Fail-closed semantic context comparison for an explicit registry promotion.

    Contexts must be identical except for the source-specific metadata provenance that proves
    the registry was used: exactly one snapshot path appended to ``data_sources`` and exactly
    one replacement of the DB metadata provenance record.  This does not weaken business-data
    equality: metadata, freshness, ticker fields, and every other root field remain exact.
    """
    expected_deltas: list[dict[str, Any]] = []
    unexpected_deltas: list[dict[str, Any]] = []
    snapshot = str(Path(snapshot_path))

    for key in sorted(set(database_context) | set(registry_context)):
        if key in {"data_sources", "provenance"}:
            continue
        if database_context.get(key) != registry_context.get(key):
            unexpected_deltas.append({
                "path": f"$.{key}",
                "database": database_context.get(key),
                "registry": registry_context.get(key),
            })

    db_sources = database_context.get("data_sources")
    registry_sources = registry_context.get("data_sources")
    if not isinstance(db_sources, list) or not isinstance(registry_sources, list):
        unexpected_deltas.append({"path": "$.data_sources", "reason": "must be lists"})
    elif registry_sources == [*db_sources, snapshot]:
        expected_deltas.append({
            "path": "$.data_sources",
            "allowed": "one explicit registry snapshot path appended",
            "snapshot": snapshot,
        })
    else:
        unexpected_deltas.append({
            "path": "$.data_sources",
            "database": db_sources,
            "registry": registry_sources,
        })

    db_provenance = database_context.get("provenance")
    registry_provenance = registry_context.get("provenance")
    if not isinstance(db_provenance, list) or not isinstance(registry_provenance, list):
        unexpected_deltas.append({"path": "$.provenance", "reason": "must be lists"})
    elif len(db_provenance) != len(registry_provenance):
        unexpected_deltas.append({
            "path": "$.provenance", "reason": "length changed",
            "database_length": len(db_provenance), "registry_length": len(registry_provenance),
        })
    else:
        changed = [
            index for index, (db_item, registry_item) in enumerate(zip(db_provenance, registry_provenance))
            if db_item != registry_item
        ]
        if len(changed) != 1:
            unexpected_deltas.append({
                "path": "$.provenance", "reason": "exactly one metadata source record must differ",
                "changed_indexes": changed,
            })
        else:
            index = changed[0]
            db_item, registry_item = db_provenance[index], registry_provenance[index]
            allowed_fields = {"source_file", "source_dataset", "transformation"}
            unchanged = {
                key: db_item.get(key) for key in set(db_item) | set(registry_item)
                if key not in allowed_fields
            }
            unchanged_registry = {
                key: registry_item.get(key) for key in set(db_item) | set(registry_item)
                if key not in allowed_fields
            }
            is_metadata_replacement = (
                db_item.get("source_dataset") == "metadata"
                and unchanged == unchanged_registry
                and registry_item.get("source_file") == snapshot
                and registry_item.get("source_dataset") == REGISTRY_METADATA_SOURCE_DATASET
                and registry_item.get("transformation") == REGISTRY_METADATA_TRANSFORMATION
            )
            if is_metadata_replacement:
                expected_deltas.append({
                    "path": f"$.provenance[{index}]",
                    "allowed": "metadata source provenance replacement",
                    "snapshot": snapshot,
                    "source_dataset": REGISTRY_METADATA_SOURCE_DATASET,
                })
            else:
                unexpected_deltas.append({
                    "path": f"$.provenance[{index}]",
                    "database": db_item,
                    "registry": registry_item,
                })

    return {
        "is_semantically_invariant": not unexpected_deltas,
        "expected_deltas": expected_deltas,
        "unexpected_deltas": unexpected_deltas,
    }