"""Deterministically decide rebuild/revalidation actions from Phase 8 artifacts."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


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


def decide(staleness: dict[str, Any], validation: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    package_status = {str(item.get("ticker")): item.get("status") for item in staleness.get("package_changes", [])}
    validation_status = {str(item.get("ticker")): item for item in validation.get("results", [])}
    source_statuses = {item.get("status") for item in staleness.get("source_changes", [])}
    source_changed = bool(source_statuses & {"changed", "missing", "new"})
    stat_only_warning = "unchanged_stat_only" in source_statuses
    tickers = sorted(set(package_status) | set(validation_status))
    decisions = []
    for ticker in tickers:
        status = package_status.get(ticker, "unknown")
        check = validation_status.get(ticker, {})
        reasons: list[str] = []
        if status in {"changed", "missing", "new"}:
            action = "rebuild_required"
            reasons.append(f"package fingerprint status is {status}")
        elif check.get("non_strict") != "pass":
            action = "blocked_validation_failure"
            reasons.append("non-strict validation does not pass")
        elif source_changed:
            action = "rebuild_required"
            reasons.append("one or more source fingerprints changed/new/missing")
        elif status == "unchanged":
            action = "no_rebuild"
            reasons.append("package fingerprint unchanged and non-strict validation passes")
        else:
            action = "revalidate_required"
            reasons.append(f"package status is {status}")
        warnings = []
        if stat_only_warning:
            warnings.append("At least one large source is unchanged_stat_only; content equality is not proven.")
        if check.get("strict") == "fail":
            warnings.append("Strict validation fails; declared missing/not-fully-confirmed items remain.")
        decisions.append({"ticker":ticker,"action":action,"reasons":reasons,"warnings":warnings,
                          "package_status":status,"non_strict":check.get("non_strict"),"strict":check.get("strict")})
    counts = {action:sum(item["action"] == action for item in decisions) for action in sorted({item["action"] for item in decisions})}
    return {
        "decision_version":"1.0.0","rules_version":"phase9-rebuild-rules-1","generated_at":now,
        "decisions":decisions,"counts":counts,
        "rules":[
            "changed/missing/new package => rebuild_required",
            "non-strict validation failure => blocked_validation_failure",
            "changed/new/missing source => rebuild_required",
            "unchanged package + non-strict pass => no_rebuild",
            "otherwise => revalidate_required"
        ],
        "warnings":["Strict failure alone does not force rebuild when it only reflects declared missing/uncertainty.",
                    "Decisions concern artifact maintenance, not investment action."],
        "provenance":[{"generated_at":now,"transformation":"Apply ordered deterministic rules to staleness and validation reports.",
                       "limitations":["Depends on fingerprint strength and report completeness"]}],
    }


def markdown_report(result: dict[str, Any]) -> str:
    lines = ["# Deterministic Rebuild Decision", "", f"Generated: `{result['generated_at']}`", "",
             "| Ticker | Action | Package | Non-strict | Strict |", "|---|---|---|---|---|"]
    lines.extend(f"| {item['ticker']} | {item['action']} | {item['package_status']} | {item['non_strict']} | {item['strict']} |" for item in result["decisions"])
    lines.extend(["", "## Rules", ""] + [f"- {rule}" for rule in result["rules"]])
    lines.extend(["", "## Known Limitations", "", "- Decisions inherit fingerprint and validation limitations.",
                  "- `no_rebuild` does not prove upstream data correctness.", "- These are maintenance actions, not investment recommendations.",
                  "", "## How AI Should Use This", "", "Use actions to schedule package maintenance only. Preserve warnings and never map them to buy/sell decisions.", ""])
    return "\n".join(lines)


def safe_new_output(path: Path, allow_existing: bool = False) -> Path:
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
    parser = argparse.ArgumentParser(description="Decide deterministic rebuild actions.")
    parser.add_argument("--staleness", default="exports/context_packages/staleness_report.json")
    parser.add_argument("--validation", default="exports/context_packages/batch_validation_report_auto_v2.json")
    parser.add_argument("--output-json", default="exports/context_packages/rebuild_decision.json")
    parser.add_argument("--output-md", default="exports/context_packages/rebuild_decision.md")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        result = decide(load_json((ROOT / args.staleness).resolve()), load_json((ROOT / args.validation).resolve()))
        outputs = [safe_new_output(Path(args.output_json), allow_existing=args.dry_run), safe_new_output(Path(args.output_md), allow_existing=args.dry_run)]
        if not args.dry_run:
            outputs[0].write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
            outputs[1].write_text(markdown_report(result), encoding="utf-8", newline="\n")
        print(json.dumps({"status":"dry_run_ok" if args.dry_run else "written","counts":result["counts"],"outputs":[str(path) for path in outputs]}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
