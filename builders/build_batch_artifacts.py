"""Generate batch manifest and validation reports from ticker context packages.

Read-only with respect to VNSTOCK. New artifacts may only be created inside
AI ANALYZE/exports/context_packages and existing files are never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Iterable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vn_time import vn_now_iso  # noqa: E402

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
DEFAULT_PACKAGE_DIR = (WORKSPACE_ROOT / "exports" / "context_packages").resolve()
VNSTOCK_ROOT = (WORKSPACE_ROOT.parent / "VNSTOCK").resolve()
MAX_BATCH_SIZE = 10
HASH_SIZE_LIMIT = 10 * 1024 * 1024
REQUIRED_SECTIONS = [
    "ticker", "generated_at", "mode", "data_sources", "latest_available_dates",
    "identity", "metadata", "price_summary", "financial_summary", "valuation_inputs",
    "technical_summary", "news_summary", "shareholder_summary", "risks",
    "data_quality", "provenance",
]


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"JSON not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return value


def save_text_new(path: Path, content: str) -> None:
    safe = validate_output_path(path)
    if safe.exists():
        raise FileExistsError(f"Refusing to overwrite: {safe}")
    safe.parent.mkdir(parents=True, exist_ok=True)
    with safe.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(content)


def save_json_new(path: Path, payload: dict[str, Any]) -> None:
    save_text_new(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_output_path(path: Path) -> Path:
    resolved = path if path.is_absolute() else WORKSPACE_ROOT / path
    resolved = resolved.resolve()
    if not _is_relative_to(resolved, DEFAULT_PACKAGE_DIR):
        raise ValueError(f"Batch artifact output must stay in {DEFAULT_PACKAGE_DIR}")
    if _is_relative_to(resolved, VNSTOCK_ROOT):
        raise ValueError("Output may not be inside VNSTOCK")
    if resolved.suffix.lower() not in {".json", ".md"}:
        raise ValueError("Output must be .json or .md")
    return resolved


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_file(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.exists() or not resolved.is_file():
        return {"path": str(resolved), "exists": False, "method": "missing"}
    stat = resolved.stat()
    result: dict[str, Any] = {
        "path": str(resolved), "exists": True, "size_bytes": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }
    if stat.st_size <= HASH_SIZE_LIMIT:
        result.update({"method": "sha256", "sha256": sha256_file(resolved)})
    else:
        result.update({"method": "stat_only_large_file", "sha256": None,
                       "warning": f"File exceeds {HASH_SIZE_LIMIT} bytes; content hash skipped."})
    return result


def _source_paths(package: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for raw in package.get("data_sources", []):
        if isinstance(raw, str):
            candidate = Path(raw)
            if candidate.is_absolute():
                paths.append(candidate)
            else:
                paths.append((WORKSPACE_ROOT / candidate).resolve())
    return list(dict.fromkeys(paths))


def validate_package(path: Path, package: dict[str, Any]) -> dict[str, Any]:
    missing_keys = [key for key in REQUIRED_SECTIONS if key not in package]
    data_quality = package.get("data_quality") if isinstance(package.get("data_quality"), dict) else {}
    missing_sections = data_quality.get("missing_sections", [])
    warnings = data_quality.get("warnings", [])
    not_confirmed = data_quality.get("not_fully_confirmed", [])
    provenance = package.get("provenance", [])
    non_strict_errors = []
    if missing_keys:
        non_strict_errors.append("Missing required keys: " + ", ".join(missing_keys))
    if not package.get("ticker"):
        non_strict_errors.append("Ticker missing")
    if not provenance:
        non_strict_errors.append("Provenance missing")
    strict_errors = list(non_strict_errors)
    if missing_sections:
        strict_errors.append("Missing sections: " + ", ".join(missing_sections))
    if not_confirmed:
        strict_errors.append("Not fully confirmed items remain")
    return {
        "ticker": package.get("ticker"), "file": path.name, "json_parse": "valid",
        "required_sections_present": not missing_keys, "missing_required_keys": missing_keys,
        "missing_sections": missing_sections, "warnings": warnings,
        "not_fully_confirmed": not_confirmed,
        "provenance_status": "present" if provenance else "missing",
        "provenance_count": len(provenance),
        "non_strict": "pass" if not non_strict_errors else "fail",
        "non_strict_errors": non_strict_errors,
        "strict": "pass" if not strict_errors else "fail", "strict_errors": strict_errors,
    }


def discover_packages(package_dir: Path, tickers: Iterable[str] | None = None) -> list[Path]:
    directory = package_dir.resolve()
    if not _is_relative_to(directory, DEFAULT_PACKAGE_DIR) and directory != DEFAULT_PACKAGE_DIR:
        raise ValueError("Package directory must stay inside the approved exports/context_packages area")
    if tickers:
        normalized = list(dict.fromkeys(item.strip().upper() for item in tickers if item.strip()))
        if len(normalized) > MAX_BATCH_SIZE:
            raise ValueError(f"Batch size exceeds safe maximum {MAX_BATCH_SIZE}")
        paths = [directory / f"{ticker}_context.json" for ticker in normalized]
    else:
        paths = sorted(directory.glob("*_context.json"))
        if len(paths) > MAX_BATCH_SIZE:
            raise ValueError(f"Discovered {len(paths)} packages; explicitly select at most {MAX_BATCH_SIZE}")
    missing = [str(path) for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("Missing packages: " + ", ".join(missing))
    if not paths:
        raise ValueError("No context packages selected")
    return paths


def build_artifacts(paths: list[Path]) -> tuple[dict[str, Any], dict[str, Any], str]:
    now = vn_now_iso()
    package_entries = []
    validation_results = []
    all_source_paths: list[Path] = []
    for path in paths:
        package = load_json(path)
        validation = validate_package(path, package)
        package_fingerprint = fingerprint_file(path)
        sources = _source_paths(package)
        all_source_paths.extend(sources)
        package_entries.append({
            "ticker": package.get("ticker"), "path": str(path.resolve()),
            "generated_at": package.get("generated_at"),
            "missing_sections": validation["missing_sections"],
            "warnings_count": len(validation["warnings"]),
            "package_fingerprint": package_fingerprint,
        })
        validation_results.append(validation)
    unique_sources = list(dict.fromkeys(all_source_paths))
    source_fingerprints = [fingerprint_file(path) for path in unique_sources]
    manifest = {
        "manifest_version": "2.0.0", "generated_at": now,
        "batch_size": len(package_entries),
        "tickers": [entry["ticker"] for entry in package_entries],
        "packages": package_entries,
        "source_fingerprints": source_fingerprints,
        "stale_detection_rule": "Compare package/source size, mtime_ns and SHA-256 when available against the previous manifest. Large files use stat-only fingerprints.",
        "warnings": ["Fingerprint changes indicate a rebuild/revalidation need, not an investment signal.",
                     "Large VNSTOCK files are not content-hashed to avoid expensive full reads."],
        "provenance": [{"source_files":[str(path.resolve()) for path in paths],"generated_at":now,
                        "transformation":"Discover selected context packages, validate contract and compute safe fingerprints.",
                        "limitations":["No upstream record-level audit","Large files use stat-only fingerprints"]}],
    }
    report = {
        "report_version": "2.0.0", "generated_at": now,
        "summary": {
            "package_count": len(validation_results),
            "json_parse_valid": len(validation_results),
            "non_strict_pass": sum(item["non_strict"] == "pass" for item in validation_results),
            "strict_pass": sum(item["strict"] == "pass" for item in validation_results),
            "provenance_present": sum(item["provenance_status"] == "present" for item in validation_results),
        },
        "results": validation_results,
        "warnings": ["Strict failures are expected while missing/not-fully-confirmed items remain."],
        "provenance": manifest["provenance"],
    }
    lines = [
        "# Automated Batch Validation Report", "", f"Generated: `{now}`", "",
        "| Ticker | JSON | Required | Missing sections | Provenance | Non-strict | Strict |", "|---|---|---|---|---|---|---|",
    ]
    for item in validation_results:
        lines.append(f"| {item['ticker']} | Valid | {'Yes' if item['required_sections_present'] else 'No'} | {', '.join(item['missing_sections']) or 'None'} | {item['provenance_status']} | {item['non_strict']} | {item['strict']} |")
    lines.extend([
        "", "## Provenance / Source Basis", "",
        "Generated directly from the selected context packages. Package files receive SHA-256 fingerprints; source files receive SHA-256 when small and stat-only fingerprints when large.",
        "", "## Known Limitations", "",
        "- This is contract/provenance validation, not an independent audit of upstream market records.",
        "- Large-file stat fingerprints can miss content changes that preserve size and mtime.",
        "- Strict failures are not investment-risk scores.",
        "", "## How AI Should Use This", "",
        "Read validation and fingerprint warnings before using a package. Rebuild packages when fingerprints change; never infer missing sections or investment conclusions.", "",
    ])
    return manifest, report, "\n".join(lines)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build automated batch manifest and validation reports.")
    parser.add_argument("--tickers", help="Comma-separated list, maximum 10; otherwise discover *_context.json")
    parser.add_argument("--package-dir", default=str(DEFAULT_PACKAGE_DIR))
    parser.add_argument("--manifest-output", default="exports/context_packages/batch_manifest_auto.json")
    parser.add_argument("--validation-json", default="exports/context_packages/batch_validation_report_auto.json")
    parser.add_argument("--validation-md", default="exports/context_packages/batch_validation_report_auto.md")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        tickers = args.tickers.split(",") if args.tickers else None
        paths = discover_packages(Path(args.package_dir), tickers)
        manifest, report, markdown = build_artifacts(paths)
        outputs = [validate_output_path(Path(args.manifest_output)), validate_output_path(Path(args.validation_json)), validate_output_path(Path(args.validation_md))]
        if not args.dry_run:
            save_json_new(outputs[0], manifest)
            save_json_new(outputs[1], report)
            save_text_new(outputs[2], markdown)
        print(json.dumps({"status":"dry_run_ok" if args.dry_run else "written","package_count":len(paths),
                          "tickers":manifest["tickers"],"outputs":[str(path) for path in outputs],
                          "non_strict_pass":report["summary"]["non_strict_pass"],"strict_pass":report["summary"]["strict_pass"]},
                         ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
