"""Validate the v1.0 operating pack locally without uploads or model calls."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = (ROOT / "exports" / "operating_pack").resolve()
PLATFORMS = ["chatgpt", "gemini", "claude"]
FORBIDDEN_TOKENS = ["../VNSTOCK/vn_stock.db", "ohlcv_flat.csv", "data_bctc/"]
REQUIRED_INSTRUCTION_CONCEPTS = ["Fact", "Derived", "Inference", "Unknown", "missing", "provenance", "buy/sell"]


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


def validate_pack() -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    issues: list[dict[str, str]] = []
    pack_manifest = load_json(ROOT / "operating_pack" / "operating_pack_manifest.json")
    budget = load_json(ROOT / "operating_pack" / "common" / "context_budget_policy.json")
    if budget.get("task_budgets", {}).get("screening", {}).get("context_packages_max") != 10:
        issues.append({"severity":"high","message":"Screening context package cap must be 10"})
    platform_results = []
    for platform in PLATFORMS:
        directory = ROOT / "operating_pack" / platform
        manifest_path = directory / "upload_manifest.json"
        instructions_path = directory / "project_instructions.md"
        workflow_path = directory / "workflow.md"
        manifest = load_json(manifest_path)
        missing_files = []
        for raw in manifest.get("reference_files", []) + manifest.get("operator_only_files", []):
            if not (ROOT / raw).exists():
                missing_files.append(raw)
        if missing_files:
            issues.append({"severity":"critical","message":f"{platform}: missing listed files: {missing_files}"})
        serialized = json.dumps(manifest, ensure_ascii=False)
        forbidden_reference_hits = [token for token in FORBIDDEN_TOKENS if token in serialized and token not in json.dumps(manifest.get("do_not_upload", []), ensure_ascii=False)]
        if forbidden_reference_hits:
            issues.append({"severity":"critical","message":f"{platform}: forbidden files appear as upload references: {forbidden_reference_hits}"})
        instruction_text = instructions_path.read_text(encoding="utf-8")
        missing_concepts = [concept for concept in REQUIRED_INSTRUCTION_CONCEPTS if concept.lower() not in instruction_text.lower()]
        if missing_concepts:
            issues.append({"severity":"high","message":f"{platform}: instruction concepts missing: {missing_concepts}"})
        for path in [instructions_path, workflow_path]:
            text = path.read_text(encoding="utf-8")
            if "Known Limitations" not in text or "How AI Should Use This" not in text:
                issues.append({"severity":"medium","message":f"{path}: required documentation sections missing"})
        platform_results.append({"platform":platform,"reference_file_count":len(manifest.get("reference_files", [])),
                                 "operator_file_count":len(manifest.get("operator_only_files", [])),
                                 "missing_files":missing_files,"instruction_concepts_missing":missing_concepts})
    common_instruction = (ROOT / "operating_pack" / "common" / "system_instructions.md").read_text(encoding="utf-8")
    for phrase in ["never provide guaranteed buy/sell", "never infer ticker-specific news", "point-in-time"]:
        if phrase not in common_instruction.lower():
            issues.append({"severity":"high","message":f"Common instruction missing phrase: {phrase}"})
    severity_counts = {level:sum(item["severity"] == level for item in issues) for level in ["critical","high","medium","low"]}
    status = "pass" if severity_counts["critical"] == 0 and severity_counts["high"] == 0 else "fail"
    return {
        "report_version":"1.0.0","generated_at":now,"status":status,
        "severity_counts":severity_counts,"platforms":platform_results,"issues":issues,
        "pack_manifest_version":pack_manifest.get("pack_version"),
        "external_upload_performed":False,"model_call_performed":False,
        "warnings":["Local validation cannot verify platform retrieval behavior or current account limits."],
        "provenance":[{"source":"operating_pack manifests/instructions/workflows","transformation":"Local JSON/path/guardrail/documentation validation"}]
    }


def markdown(report: dict[str, Any]) -> str:
    lines = ["# Operating Pack Validation", "", f"Status: **{report['status'].upper()}**", "",
             "| Platform | Reference files | Operator files | Missing files |", "|---|---:|---:|---|"]
    lines.extend(f"| {item['platform']} | {item['reference_file_count']} | {item['operator_file_count']} | {', '.join(item['missing_files']) or 'None'} |" for item in report["platforms"])
    lines.extend(["", "## Issues", ""])
    lines.extend([f"- **{item['severity']}** — {item['message']}" for item in report["issues"]] or ["No issues detected."])
    lines.extend(["", "## Known Limitations", "", "- No files were uploaded and no model was called.",
                  "- Platform UI, retrieval and current account limits were not fully validated.",
                  "", "## How AI Should Use This", "", "Use PASS only to prepare manual platform setup. Human review remains mandatory.", ""])
    return "\n".join(lines)


def safe_output(path: Path, allow_existing: bool = False) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    try:
        resolved.relative_to(OUTPUT_ROOT)
    except ValueError as exc:
        raise ValueError(f"Output must stay inside {OUTPUT_ROOT}") from exc
    if resolved.suffix.lower() not in {".json", ".md"}:
        raise ValueError("Output must be JSON or Markdown")
    if resolved.exists() and not allow_existing:
        raise FileExistsError(f"Refusing to overwrite: {resolved}")
    return resolved


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate AI ANALYZE operating pack locally.")
    parser.add_argument("--output-json", default="exports/operating_pack/operating_pack_validation.json")
    parser.add_argument("--output-md", default="exports/operating_pack/operating_pack_validation.md")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = validate_pack()
        outputs = [safe_output(Path(args.output_json), args.dry_run), safe_output(Path(args.output_md), args.dry_run)]
        if not args.dry_run:
            outputs[0].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            outputs[1].write_text(markdown(report), encoding="utf-8", newline="\n")
        print(json.dumps({"status":"dry_run_ok" if args.dry_run else "written","validation":report["status"],
                          "severity_counts":report["severity_counts"],"issues":report["issues"],
                          "outputs":[str(path) for path in outputs]}, ensure_ascii=False, indent=2))
        return 0 if report["status"] == "pass" else 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
