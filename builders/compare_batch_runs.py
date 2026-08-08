"""Compare two automated batch manifests and create a run registry/staleness report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vn_time import vn_now_iso  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = (ROOT / "exports" / "context_packages").resolve()


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def safe_output(path: Path, allow_existing: bool = False) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    if not _is_relative_to(resolved, OUTPUT_ROOT):
        raise ValueError(f"Output must stay inside {OUTPUT_ROOT}")
    if resolved.suffix.lower() not in {".json", ".md"}:
        raise ValueError("Output must be JSON or Markdown")
    if resolved.exists() and not allow_existing:
        raise FileExistsError(f"Refusing to overwrite: {resolved}")
    return resolved


def _fingerprint_key(value: dict[str, Any]) -> tuple[Any, ...]:
    method = value.get("method")
    if method == "sha256":
        return (method, value.get("sha256"), value.get("size_bytes"))
    if method == "stat_only_large_file":
        return (method, value.get("size_bytes"), value.get("mtime_ns"))
    return (method, value.get("exists"), value.get("size_bytes"), value.get("mtime_ns"))


def _index(manifest: dict[str, Any], key: str, path_field: str) -> dict[str, dict[str, Any]]:
    return {str(item.get(path_field)): item for item in manifest.get(key, [])}


def compare(previous: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    now = vn_now_iso()
    previous_packages = _index(previous, "packages", "ticker")
    current_packages = _index(current, "packages", "ticker")
    package_changes = []
    for ticker in sorted(set(previous_packages) | set(current_packages)):
        old = previous_packages.get(ticker)
        new = current_packages.get(ticker)
        if old is None:
            status = "new"
        elif new is None:
            status = "missing"
        elif _fingerprint_key(old.get("package_fingerprint", {})) == _fingerprint_key(new.get("package_fingerprint", {})):
            status = "unchanged"
        else:
            status = "changed"
        package_changes.append({"ticker":ticker,"status":status,"previous":old.get("package_fingerprint") if old else None,"current":new.get("package_fingerprint") if new else None})
    previous_sources = _index(previous, "source_fingerprints", "path")
    current_sources = _index(current, "source_fingerprints", "path")
    source_changes = []
    for path in sorted(set(previous_sources) | set(current_sources)):
        old = previous_sources.get(path)
        new = current_sources.get(path)
        if old is None:
            status = "new"
        elif new is None:
            status = "missing"
        elif _fingerprint_key(old) == _fingerprint_key(new):
            status = "unchanged_stat_only" if new.get("method") == "stat_only_large_file" else "unchanged"
        else:
            status = "changed"
        source_changes.append({"path":path,"status":status,"previous":old,"current":new})
    stale = any(item["status"] in {"changed","missing"} for item in package_changes + source_changes)
    return {
        "comparison_version":"1.0.0","generated_at":now,
        "previous_generated_at":previous.get("generated_at"),"current_generated_at":current.get("generated_at"),
        "stale_or_changed":stale,"package_changes":package_changes,"source_changes":source_changes,
        "warnings":["unchanged_stat_only is weaker than a content-hash comparison.","Staleness indicates rebuild/revalidation need, not investment risk."],
        "provenance":[{"transformation":"Compare package/source fingerprint keys across two manifests","generated_at":now,
                       "limitations":["Large files may use stat-only fingerprints"]}],
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Batch Run Staleness Report", "", f"Generated: `{report['generated_at']}`", "",
             f"Stale or changed: **{report['stale_or_changed']}**", "", "## Package changes", "",
             "| Ticker | Status |", "|---|---|"]
    lines.extend(f"| {item['ticker']} | {item['status']} |" for item in report["package_changes"])
    lines.extend(["", "## Source changes", "", "| Source | Status |", "|---|---|"])
    lines.extend(f"| `{item['path']}` | {item['status']} |" for item in report["source_changes"])
    lines.extend(["", "## Known Limitations", "", "- `unchanged_stat_only` is not content-level proof.",
                  "- This report detects artifact/source changes, not market or investment risk.", "",
                  "## How AI Should Use This", "", "Rebuild/revalidate when status is changed or missing. Keep stat-only limitations visible.", ""])
    return "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two batch manifests.")
    parser.add_argument("--previous", required=True)
    parser.add_argument("--current", required=True)
    parser.add_argument("--registry-output", default="exports/context_packages/run_registry.json")
    parser.add_argument("--report-json", default="exports/context_packages/staleness_report.json")
    parser.add_argument("--report-md", default="exports/context_packages/staleness_report.md")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        previous_path = Path(args.previous).resolve()
        current_path = Path(args.current).resolve()
        previous = load_json(previous_path)
        current = load_json(current_path)
        report = compare(previous, current)
        registry = {
            "registry_version":"1.0.0","generated_at":report["generated_at"],
            "runs":[
                {"manifest":str(previous_path),"generated_at":previous.get("generated_at"),"manifest_version":previous.get("manifest_version")},
                {"manifest":str(current_path),"generated_at":current.get("generated_at"),"manifest_version":current.get("manifest_version")},
            ],
            "latest_comparison":{"stale_or_changed":report["stale_or_changed"],"report":"staleness_report.json"},
            "warnings":report["warnings"],"provenance":report["provenance"],
        }
        outputs = [safe_output(Path(args.registry_output), allow_existing=args.dry_run), safe_output(Path(args.report_json), allow_existing=args.dry_run), safe_output(Path(args.report_md), allow_existing=args.dry_run)]
        if not args.dry_run:
            outputs[0].write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            outputs[1].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            outputs[2].write_text(markdown_report(report), encoding="utf-8", newline="\n")
        print(json.dumps({"status":"dry_run_ok" if args.dry_run else "written","stale_or_changed":report["stale_or_changed"],
                          "package_statuses":{item["status"]:sum(x["status"] == item["status"] for x in report["package_changes"]) for item in report["package_changes"]},
                          "outputs":[str(path) for path in outputs]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
