"""Final v1.0 QA and safety audit for AI ANALYZE.

The audit reads AI ANALYZE artifacts and read-only VNSTOCK-facing builder code.
It never writes to VNSTOCK. Default mode is dry-run; report files must be new.
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vn_time import vn_now_iso  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = (ROOT / "exports" / "qa").resolve()
MANAGED_DIRS = ["project_discovery","metadata","knowledge","summary","context_packages","validation","workflows","builders","exports","docs","prompts","tests","operating_pack"]
TEXT_SUFFIXES = {".json",".md",".py",".txt",".css",".js",".html",".csv"}
REQUIRED_CONTEXT_KEYS = ["ticker","generated_at","mode","data_sources","latest_available_dates","identity","metadata","price_summary","financial_summary","valuation_inputs","technical_summary","news_summary","shareholder_summary","risks","data_quality","provenance"]


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def managed_files() -> list[Path]:
    files: list[Path] = []
    for name in MANAGED_DIRS:
        directory = ROOT / name
        if directory.exists():
            files.extend(path for path in directory.rglob("*") if path.is_file() and "__pycache__" not in path.parts)
    master = ROOT / "MASTER_PLAN.md"
    if master.exists():
        files.append(master)
    return sorted(set(files))


def issue(rule_id: str, severity: str, message: str, path: Path | None = None) -> dict[str, Any]:
    return {"rule_id":rule_id,"severity":severity,"message":message,"path":str(path) if path else None}


def run_checks() -> dict[str, Any]:
    started = vn_now_iso()
    files = managed_files()
    issues: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []

    text_files = [path for path in files if path.suffix.lower() in TEXT_SUFFIXES]
    utf8_failures = []
    for path in text_files:
        try:
            path.read_text(encoding="utf-8", errors="strict")
        except (UnicodeDecodeError, OSError) as exc:
            utf8_failures.append(path)
            issues.append(issue("QA002", "high", f"UTF-8 decode failed: {exc}", path))
    checks.append({"rule_id":"QA002","status":"pass" if not utf8_failures else "fail","files_checked":len(text_files)})

    json_files = [path for path in files if path.suffix.lower() == ".json"]
    json_failures = []
    for path in json_files:
        try:
            load_json(path)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
            json_failures.append(path)
            issues.append(issue("QA001", "critical", f"JSON parse failed: {exc}", path))
    checks.append({"rule_id":"QA001","status":"pass" if not json_failures else "fail","files_checked":len(json_files)})

    python_files = [path for path in files if path.suffix.lower() == ".py" and ("builders" in path.parts or "tests" in path.parts)]
    ast_failures = []
    for path in python_files:
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (SyntaxError, OSError, UnicodeDecodeError) as exc:
            ast_failures.append(path)
            issues.append(issue("QA003", "critical", f"Python AST parse failed: {exc}", path))
    checks.append({"rule_id":"QA003","status":"pass" if not ast_failures else "fail","files_checked":len(python_files)})

    validator = load_module("final_qa_validator", ROOT / "builders" / "validate_json_schema_subset.py")
    schema_pairs: list[tuple[Path, list[Path]]] = [
        (ROOT / "validation" / "schemas" / "ticker_context.schema.json", sorted((ROOT / "exports" / "context_packages").glob("[A-Z]*_context.json"))),
        (ROOT / "validation" / "schemas" / "batch_manifest.schema.json", [ROOT / "exports" / "context_packages" / "batch_manifest_auto_v2.json"]),
        (ROOT / "validation" / "schemas" / "batch_validation_report.schema.json", [ROOT / "exports" / "context_packages" / "batch_validation_report_auto_v2.json"]),
    ]
    schema_failures = 0
    schema_instances = 0
    for schema_path, instances in schema_pairs:
        schema = validator.load_json(schema_path)
        for instance_path in instances:
            schema_instances += 1
            errors = validator.validate(validator.load_json(instance_path), schema)
            if errors:
                schema_failures += 1
                issues.append(issue("QA005", "high", "Schema errors: " + "; ".join(errors), instance_path))
    checks.append({"rule_id":"QA005","status":"pass" if not schema_failures else "fail","instances_checked":schema_instances})

    contexts = sorted((ROOT / "exports" / "context_packages").glob("[A-Z]*_context.json"))
    context_failures = 0
    for path in contexts:
        value = load_json(path)
        missing = [key for key in REQUIRED_CONTEXT_KEYS if key not in value]
        quality = value.get("data_quality", {})
        if missing or not value.get("provenance") or "warnings" not in quality or "missing_sections" not in quality:
            context_failures += 1
            issues.append(issue("QA006", "high", f"Context contract incomplete; missing keys={missing}", path))
    checks.append({"rule_id":"QA006","status":"pass" if not context_failures else "fail","contexts_checked":len(contexts)})

    builder_sources = [path for path in (ROOT / "builders").glob("*.py") if path.name != "run_final_qa.py"]
    source_text = "\n".join(path.read_text(encoding="utf-8") for path in builder_sources)
    readonly_ok = "mode=ro" in source_text and "PRAGMA query_only = ON" in source_text
    forbidden_patterns = [r"subprocess[^\n]+vn_stock_pipeline", r"subprocess[^\n]+crawler", r"sqlite3\.connect\([^\n]*VNSTOCK[^\n]*(?!mode=ro)"]
    static_hits = [pattern for pattern in forbidden_patterns if re.search(pattern, source_text, re.IGNORECASE)]
    if not readonly_ok or static_hits:
        issues.append(issue("QA008", "critical", f"Read-only static invariant failed; readonly={readonly_ok}, hits={static_hits}"))
    checks.append({"rule_id":"QA008","status":"pass" if readonly_ok and not static_hits else "fail","builder_files_checked":len(builder_sources)})

    prompt_path = ROOT / "prompts" / "ai_analysis_templates.md"
    prompt_text = prompt_path.read_text(encoding="utf-8").lower() if prompt_path.exists() else ""
    investment_ok = "do not issue a buy/sell recommendation" in prompt_text and "never invent" in prompt_text
    if not investment_ok:
        issues.append(issue("QA011", "high", "AI prompt guardrails are missing or incomplete", prompt_path))
    checks.append({"rule_id":"QA011","status":"pass" if investment_ok else "fail"})

    release_docs = list((ROOT / "knowledge").glob("*.md")) + list((ROOT / "docs").glob("*.md")) + list((ROOT / "prompts").glob("*.md")) + list((ROOT / "operating_pack").rglob("*.md"))
    docs_missing = []
    for path in release_docs:
        text = path.read_text(encoding="utf-8")
        if "Known Limitations" not in text or "How AI Should Use This" not in text:
            docs_missing.append(path)
            issues.append(issue("QA012", "medium", "Missing Known Limitations or How AI Should Use This", path))
    checks.append({"rule_id":"QA012","status":"pass" if not docs_missing else "fail","documents_checked":len(release_docs)})

    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    test_run = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-p", "test_phase*.py", "-q"],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=env, check=False)
    match = re.search(r"Ran (\d+) tests", test_run.stderr + test_run.stdout)
    test_count = int(match.group(1)) if match else None
    if test_run.returncode != 0:
        issues.append(issue("QA004", "critical", "Full test suite failed: " + (test_run.stderr or test_run.stdout)[-2000:]))
    checks.append({"rule_id":"QA004","status":"pass" if test_run.returncode == 0 else "fail","tests_run":test_count,"exit_code":test_run.returncode})

    safety_test_names = {"test_output_traversal_and_overwrite_protection","test_reject_more_than_ten","test_builder_dry_run_and_strict"}
    test_source = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "tests").glob("test_phase*.py"))
    safety_present = all(name in test_source for name in safety_test_names)
    if not safety_present:
        issues.append(issue("QA007", "critical", "Required path/overwrite/dry-run safety tests are missing"))
    checks.append({"rule_id":"QA007","status":"pass" if safety_present and test_run.returncode == 0 else "fail"})
    checks.append({"rule_id":"QA009","status":"pass" if "test_reject_more_than_ten" in test_source and test_run.returncode == 0 else "fail"})

    maintenance_files = ["artifact_catalog.json","batch_manifest_auto_v2.json","staleness_report.json","rebuild_decision.json"]
    provenance_ok = True
    for name in maintenance_files:
        path = ROOT / "exports" / "context_packages" / name
        value = load_json(path)
        if not value.get("provenance"):
            provenance_ok = False
            issues.append(issue("QA010", "high", "Missing provenance", path))
    checks.append({"rule_id":"QA010","status":"pass" if provenance_ok else "fail","artifacts_checked":len(maintenance_files)})

    severity_counts = {level:sum(item["severity"] == level for item in issues) for level in ["critical","high","medium","low","info"]}
    release_gate = "pass" if severity_counts["critical"] == 0 and severity_counts["high"] == 0 else "fail"
    return {
        "report_version":"1.0.0","generated_at":started,"release_target":"v1.0","release_gate":release_gate,
        "severity_counts":severity_counts,"checks":checks,"issues":issues,
        "inventory":{"managed_files":len(files),"text_files":len(text_files),"json_files":len(json_files),"python_files":len(python_files),"context_packages":len(contexts)},
        "warnings":["Passing static/runtime QA does not prove upstream market data correctness.",
                    "JSON Schema validation uses the documented dependency-free subset."],
        "provenance":[{"source":"AI ANALYZE managed directories and Phase 1-9 tests","generated_at":started,
                       "transformation":"UTF-8/JSON/AST/schema/context/static safety/full-test/release-document audit",
                       "limitations":["Static side-effect detection is heuristic","No external source/model audit"]}],
    }


def markdown_report(report: dict[str, Any]) -> str:
    lines = ["# Final QA & Safety Audit — v1.0", "", f"Generated: `{report['generated_at']}`", "",
             f"Release gate: **{report['release_gate'].upper()}**", "", "## Check results", "",
             "| Rule | Status |", "|---|---|"]
    lines.extend(f"| {item['rule_id']} | {item['status']} |" for item in report["checks"])
    lines.extend(["", "## Issues", ""])
    if report["issues"]:
        lines.extend(f"- **{item['severity']} {item['rule_id']}** — {item['message']} ({item.get('path') or 'global'})" for item in report["issues"])
    else:
        lines.append("No issues detected.")
    lines.extend(["", "## Known Limitations", "", "- QA does not prove upstream market data correctness.",
                  "- Static read-only analysis is heuristic.", "- JSON Schema uses a documented subset validator.",
                  "", "## How AI Should Use This", "", "Use the release gate for v1.0 packaging only. Preserve all warnings and never treat QA success as investment evidence.", ""])
    return "\n".join(lines)


def safe_output(path: Path, allow_existing: bool = False) -> Path:
    resolved = path if path.is_absolute() else ROOT / path
    resolved = resolved.resolve()
    try:
        resolved.relative_to(OUTPUT_ROOT)
    except ValueError as exc:
        raise ValueError(f"QA output must stay inside {OUTPUT_ROOT}") from exc
    if resolved.suffix.lower() not in {".json", ".md"}:
        raise ValueError("QA output must be JSON or Markdown")
    if resolved.exists() and not allow_existing:
        raise FileExistsError(f"Refusing to overwrite: {resolved}")
    return resolved


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run final v1.0 QA and safety audit.")
    parser.add_argument("--output-json", default="exports/qa/final_qa_report.json")
    parser.add_argument("--output-md", default="exports/qa/final_qa_report.md")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        report = run_checks()
        outputs = [safe_output(Path(args.output_json), allow_existing=args.dry_run), safe_output(Path(args.output_md), allow_existing=args.dry_run)]
        if not args.dry_run:
            outputs[0].write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            outputs[1].write_text(markdown_report(report), encoding="utf-8", newline="\n")
        print(json.dumps({"status":"dry_run_ok" if args.dry_run else "written","release_gate":report["release_gate"],
                          "severity_counts":report["severity_counts"],"inventory":report["inventory"],
                          "issues":report["issues"],"outputs":[str(path) for path in outputs]}, ensure_ascii=False, indent=2))
        return 0 if report["release_gate"] == "pass" else 2
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
