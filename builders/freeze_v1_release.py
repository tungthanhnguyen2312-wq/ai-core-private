"""Create the immutable AI ANALYZE v1.0 release control pack.

The frozen payload is every managed AI ANALYZE artifact outside release/. The
release control files describe that payload and are validated separately to
avoid recursive self-hashing. VNSTOCK is never read or written by this script.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
RELEASE_ROOT = (ROOT / "release" / "v1.0").resolve()
MANAGED_DIRS = ["project_discovery","metadata","knowledge","summary","context_packages","validation","workflows","builders","exports","docs","prompts","tests","operating_pack"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_inventory() -> list[dict[str, Any]]:
    entries = []
    paths: list[Path] = []
    for name in MANAGED_DIRS:
        directory = ROOT / name
        if directory.exists():
            paths.extend(path for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    master = ROOT / "MASTER_PLAN.md"
    if master.exists():
        paths.append(master)
    for path in sorted(set(paths), key=lambda item: item.relative_to(ROOT).as_posix()):
        relative = path.relative_to(ROOT).as_posix()
        stat = path.stat()
        entries.append({"path":relative,"category":relative.split("/",1)[0],"size_bytes":stat.st_size,"sha256":sha256_file(path)})
    return entries


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required release input missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return value


def build_release(qa_path: Path, operating_path: Path) -> tuple[dict[str, Any], dict[str, Any], str, dict[str, str]]:
    qa = load_json(qa_path)
    operating = load_json(operating_path)
    if qa.get("release_gate") != "pass":
        raise ValueError("Final QA release gate is not PASS")
    if operating.get("status") != "pass":
        raise ValueError("Operating pack validation is not PASS")
    inventory = collect_inventory()
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    inventory_payload = {
        "inventory_version":"1.0.0","release":"v1.0","generated_at":now,
        "scope":"Managed AI ANALYZE payload excluding release/ control files and VNSTOCK",
        "artifact_count":len(inventory),"total_size_bytes":sum(item["size_bytes"] for item in inventory),
        "artifacts":inventory,
        "limitations":["Release control files are validated separately and excluded to avoid recursive self-hashing."],
        "provenance":[{"transformation":"Enumerate managed AI ANALYZE files and compute SHA-256","generated_at":now}]
    }
    checksum_text = "".join(f"{item['sha256']}  {item['path']}\n" for item in inventory)
    category_counts: dict[str, int] = {}
    for item in inventory:
        category_counts[item["category"]] = category_counts.get(item["category"], 0) + 1
    manifest = {
        "release_manifest_version":"1.0.0","product":"AI ANALYZE","version":"1.0.0","status":"frozen",
        "generated_at":now,"payload_scope":"AI ANALYZE managed artifacts excluding release/ control files",
        "artifact_count":len(inventory),"total_size_bytes":inventory_payload["total_size_bytes"],"category_counts":category_counts,
        "inventory_file":"artifact_inventory.json","checksums_file":"checksums.sha256",
        "qa":{"path":qa_path.relative_to(ROOT).as_posix(),"release_gate":qa.get("release_gate"),"sha256":sha256_file(qa_path)},
        "operating_pack":{"path":operating_path.relative_to(ROOT).as_posix(),"status":operating.get("status"),"sha256":sha256_file(operating_path)},
        "accepted_limitations_file":"docs/v1_0_KnownLimitations.md",
        "vnstock_policy":"read_only_not_part_of_release_payload",
        "external_upload_performed":False,"model_call_performed":False,
        "freeze_policy":"Any payload modification after freeze requires a new version and regenerated inventory/checksums.",
        "release_control_files":["release_manifest.json","artifact_inventory.json","checksums.sha256","RELEASE_NOTES.md","MAINTENANCE.md","FROZEN_POLICY.md","FREEZE_COMPLETE.json"],
        "warnings":["Frozen status covers artifact integrity and operating safety, not upstream market-data correctness."],
        "provenance":[{"source":[qa_path.relative_to(ROOT).as_posix(),operating_path.relative_to(ROOT).as_posix()],
                       "transformation":"Gate release on QA/operating PASS and freeze managed payload checksums","generated_at":now}]
    }
    docs = {
        "RELEASE_NOTES.md": release_notes(manifest),
        "MAINTENANCE.md": maintenance_guide(),
        "FROZEN_POLICY.md": frozen_policy(),
    }
    return manifest, inventory_payload, checksum_text, docs


def release_notes(manifest: dict[str, Any]) -> str:
    return f"""# AI ANALYZE v1.0 Release Notes

Status: **FROZEN**  
Generated: `{manifest['generated_at']}`

## Included capabilities

- Project discovery, machine-readable metadata and AI knowledge documents.
- Summary, validation and point-in-time controls.
- Read-only ticker context builder and ten validated test packages.
- Batch manifests, fingerprints, staleness, catalog and rebuild decisions.
- Final QA/safety audit and operating packs for Gemini, ChatGPT and Claude.

## Release gates

- Final QA: PASS
- Operating pack validation: PASS
- VNSTOCK: read-only and excluded from release payload
- External uploads/model calls: none

## Known Limitations

See `docs/v1_0_KnownLimitations.md`. Frozen integrity does not prove upstream market-data correctness.

## How AI Should Use This

Use v1.0 artifacts with their validation, provenance and missing-data warnings. Do not modify frozen payload files in place.
"""


def maintenance_guide() -> str:
    return """# v1.0 Maintenance and Rebuild Guide

## Routine checks

1. Run `builders/run_final_qa.py --dry-run`.
2. Run `builders/validate_operating_pack.py --dry-run`.
3. Compare source/package fingerprints and read `rebuild_decision.json`.
4. Rebuild context only when deterministic rules require it.

## Change procedure

Never edit frozen payload files in place. Create a new version branch/directory, implement approved changes, rerun tests/QA, regenerate inventory/checksums and issue new release notes.

## Restore verification

Recompute SHA-256 for every line in `checksums.sha256`; any mismatch means the restored payload is not v1.0-identical.

## Known Limitations

VNSTOCK data refresh is outside this release and no crawler/pipeline is included.

## How AI Should Use This

Use maintenance commands only for artifact integrity. They are not market or investment signals.
"""


def frozen_policy() -> str:
    return """# v1.0 Frozen-File Policy

## Frozen scope

Every path in `artifact_inventory.json` is frozen at its recorded SHA-256.

## Prohibited in-place changes

Do not edit, delete, rename or replace frozen payload files while calling the result v1.0. Do not regenerate context packages under the same frozen filename.

## Allowed operations

Read, copy, verify and archive v1.0. Any functional/content change requires a new semantic version and complete QA/freeze cycle.

## Known Limitations

Release control files are outside the recursive payload checksum set and are validated by the freeze validator.

## How AI Should Use This

Treat `FREEZE_COMPLETE.json` as a terminal release marker. Do not begin another phase without explicit approval and a new version target.
"""


def safe_release_root() -> Path:
    try:
        RELEASE_ROOT.relative_to(ROOT)
    except ValueError as exc:
        raise ValueError("Release root must stay inside AI ANALYZE") from exc
    return RELEASE_ROOT


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Freeze AI ANALYZE v1.0 release.")
    parser.add_argument("--qa", default="exports/qa/final_qa_report_v3.json")
    parser.add_argument("--operating-validation", default="exports/operating_pack/operating_pack_validation.json")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        release_root = safe_release_root()
        manifest, inventory, checksums, docs = build_release((ROOT / args.qa).resolve(), (ROOT / args.operating_validation).resolve())
        if release_root.exists() and any(release_root.iterdir()):
            if not args.dry_run:
                raise FileExistsError(f"Refusing to overwrite non-empty release directory: {release_root}")
        if not args.dry_run:
            release_root.mkdir(parents=True, exist_ok=True)
            (release_root / "release_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            (release_root / "artifact_inventory.json").write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            (release_root / "checksums.sha256").write_text(checksums, encoding="utf-8", newline="\n")
            for name, content in docs.items():
                (release_root / name).write_text(content, encoding="utf-8", newline="\n")
            marker = {
                "version":"1.0.0","status":"freeze_complete","frozen_at":manifest["generated_at"],
                "release_manifest_sha256":sha256_file(release_root / "release_manifest.json"),
                "artifact_inventory_sha256":sha256_file(release_root / "artifact_inventory.json"),
                "checksums_sha256":sha256_file(release_root / "checksums.sha256"),
                "post_freeze_rule":"No in-place modifications; new work requires explicit approval and a new version.",
                "vnstock":"read_only_unchanged",
            }
            (release_root / "FREEZE_COMPLETE.json").write_text(json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        print(json.dumps({"status":"dry_run_ok" if args.dry_run else "frozen","release_root":str(release_root),
                          "artifact_count":manifest["artifact_count"],"total_size_bytes":manifest["total_size_bytes"],
                          "qa":manifest["qa"]["release_gate"],"operating_pack":manifest["operating_pack"]["status"]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
