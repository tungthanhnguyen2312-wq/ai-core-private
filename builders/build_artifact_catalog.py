"""Build a versioned catalog linking contexts, manifests, reports and schemas."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
EXPORT_ROOT = (ROOT / "exports" / "context_packages").resolve()


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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_entry(path: Path, artifact_type: str, version: Any = None) -> dict[str, Any]:
    resolved = path.resolve()
    stat = resolved.stat()
    return {
        "path": str(resolved), "artifact_type": artifact_type, "version": version,
        "size_bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns,
        "sha256": sha256_file(resolved), "exists": True,
    }


def build_catalog(manifest_path: Path, validation_path: Path, staleness_path: Path) -> dict[str, Any]:
    manifest = load_json(manifest_path)
    validation = load_json(validation_path)
    staleness = load_json(staleness_path)
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    artifacts: list[dict[str, Any]] = []
    relationships: list[dict[str, str]] = []
    for package in manifest.get("packages", []):
        path = Path(package["path"])
        artifacts.append(artifact_entry(path, "ticker_context", "1.1.0"))
        relationships.append({"from":str(path.resolve()),"to":str(manifest_path.resolve()),"relation":"listed_in"})
        relationships.append({"from":str(path.resolve()),"to":str(validation_path.resolve()),"relation":"validated_by"})
    top_level = [
        (manifest_path, "batch_manifest", manifest.get("manifest_version")),
        (validation_path, "batch_validation_report", validation.get("report_version")),
        (staleness_path, "staleness_report", staleness.get("comparison_version")),
    ]
    for path, kind, version in top_level:
        artifacts.append(artifact_entry(path, kind, version))
    for schema_path in sorted((ROOT / "validation" / "schemas").glob("*.json")):
        schema = load_json(schema_path)
        artifacts.append(artifact_entry(schema_path, "json_schema", schema.get("$schema")))
        relationships.append({"from":str(schema_path.resolve()),"to":str(validation_path.resolve()),"relation":"contract_for_artifact_class"})
    return {
        "catalog_version":"1.0.0","generated_at":now,
        "artifact_count":len(artifacts),"artifacts":artifacts,"relationships":relationships,
        "source_manifest":str(manifest_path.resolve()),
        "source_validation_report":str(validation_path.resolve()),
        "source_staleness_report":str(staleness_path.resolve()),
        "warnings":["Catalog hashes describe artifact files, not upstream market correctness.",
                    "Relationship contract_for_artifact_class is class-level, not record-level lineage."],
        "provenance":[{"generated_at":now,"transformation":"Read selected Phase 8 artifacts, compute SHA-256 and link catalog relationships.",
                       "limitations":["No external dependency or new source used"]}],
    }


def safe_output(path: Path, allow_existing: bool = False) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    try:
        resolved.relative_to(EXPORT_ROOT)
    except ValueError as exc:
        raise ValueError(f"Output must stay inside {EXPORT_ROOT}") from exc
    if resolved.suffix.lower() != ".json":
        raise ValueError("Catalog output must be JSON")
    if resolved.exists() and not allow_existing:
        raise FileExistsError(f"Refusing to overwrite: {resolved}")
    return resolved


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the AI ANALYZE artifact catalog.")
    parser.add_argument("--manifest", default="exports/context_packages/batch_manifest_auto_v2.json")
    parser.add_argument("--validation", default="exports/context_packages/batch_validation_report_auto_v2.json")
    parser.add_argument("--staleness", default="exports/context_packages/staleness_report.json")
    parser.add_argument("--output", default="exports/context_packages/artifact_catalog.json")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        catalog = build_catalog((ROOT / args.manifest).resolve(), (ROOT / args.validation).resolve(), (ROOT / args.staleness).resolve())
        output = safe_output(Path(args.output), allow_existing=args.dry_run)
        if not args.dry_run:
            output.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"status":"dry_run_ok" if args.dry_run else "written","output":str(output),
                          "artifact_count":catalog["artifact_count"],"relationship_count":len(catalog["relationships"])}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
