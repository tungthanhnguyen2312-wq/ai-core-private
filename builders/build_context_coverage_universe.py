"""Aggregate deterministic metric coverage across saved context packages."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REPORTS_ROOT = (ROOT / "reports").resolve()

try:
    from context_coverage import aggregate_universe, load_config, save_universe_reports, validate_profile
except ModuleNotFoundError:
    from builders.context_coverage import aggregate_universe, load_config, save_universe_reports, validate_profile


def _inside(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_report_path(raw: str, suffix: str) -> Path:
    path = Path(raw)
    resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    if not _inside(resolved, REPORTS_ROOT):
        raise ValueError("Universe coverage output must stay inside AI ANALYZE/reports")
    if resolved.suffix.lower() != suffix:
        raise ValueError(f"Universe coverage output must use {suffix}")
    return resolved


def build_reports(context_dir: Path, profile: str) -> tuple[dict, list[dict]]:
    config = load_config(ROOT / "validation" / "context_validation_profiles.json")
    schema = ROOT / "validation" / "schemas" / "ticker_context.schema.json"
    paths = sorted(context_dir.glob("[A-Z]*_context.json"))
    if not paths:
        raise ValueError(f"No context packages found in {context_dir}")
    reports = []
    for path in paths:
        with path.open("r", encoding="utf-8") as handle:
            reports.append(validate_profile(json.load(handle), profile, config, schema_path=schema))
    rows = aggregate_universe(reports)
    payload = {
        "report_version": "1.0.0",
        "validation_profile": profile,
        "ticker_count": len(reports),
        "tickers": sorted(str(report.get("ticker")) for report in reports),
        "profile_pass_count": sum(bool(report["profile_valid"]) for report in reports),
        "metrics": rows,
    }
    return payload, rows


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Aggregate context metric coverage across saved packages")
    parser.add_argument("--profile", default="current_snapshot")
    parser.add_argument("--context-dir", default="exports/context_packages")
    parser.add_argument("--output-json", default="reports/context_coverage_universe.json")
    parser.add_argument("--output-csv", default="reports/context_coverage_universe.csv")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        context_dir = Path(args.context_dir)
        context_dir = context_dir.resolve() if context_dir.is_absolute() else (ROOT / context_dir).resolve()
        payload, rows = build_reports(context_dir, args.profile)
        json_path = safe_report_path(args.output_json, ".json")
        csv_path = safe_report_path(args.output_csv, ".csv")
        if not args.dry_run:
            existing = [str(path) for path in (json_path, csv_path) if path.exists()]
            if existing:
                raise FileExistsError("Refusing to overwrite: " + ", ".join(existing))
            json_path.parent.mkdir(parents=True, exist_ok=True)
            save_universe_reports(rows, json_path, csv_path, {key: value for key, value in payload.items() if key != "metrics"})
        print(json.dumps({
            "status": "dry_run_ok" if args.dry_run else "written",
            "validation_profile": args.profile,
            "ticker_count": payload["ticker_count"],
            "metric_count": len(rows),
            "output_json": str(json_path),
            "output_csv": str(csv_path),
        }, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
