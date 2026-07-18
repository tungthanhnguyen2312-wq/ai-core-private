"""Deterministic metric coverage and purpose-specific context validation."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable, Mapping


AVAILABLE = {"reported", "derived", "proxy"}
NOT_APPLICABLE = "not_applicable"


class ProfileConfigError(ValueError):
    """The requested validation profile or its configuration is invalid."""


def load_config(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            config = json.load(handle)
    except FileNotFoundError as exc:
        raise ProfileConfigError(f"Validation profile config not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ProfileConfigError(f"Invalid validation profile JSON: {exc}") from exc
    return validate_config(config)


def validate_config(config: Mapping[str, Any]) -> dict[str, Any]:
    """Validate profile structure and invariants protected by regression tests."""
    config = dict(config)
    if not isinstance(config.get("sections"), dict) or not isinstance(config.get("profiles"), dict):
        raise ProfileConfigError("Validation config requires sections and profiles objects")
    for name, profile in config["profiles"].items():
        required = {
            "required_sections", "blocking_metrics", "allowed_missing_statuses",
            "allow_proxy", "allow_stale", "minimum_section_coverage", "minimum_overall_coverage",
        }
        missing = sorted(required - set(profile))
        if missing:
            raise ProfileConfigError(f"Profile {name!r} missing keys: {', '.join(missing)}")
        unknown = sorted(set(profile["required_sections"]) - set(config["sections"]))
        if unknown:
            raise ProfileConfigError(f"Profile {name!r} has unknown sections: {', '.join(unknown)}")
    for name, contract in config.get("protected_contracts", {}).items():
        if name not in config["profiles"]:
            raise ProfileConfigError(f"Protected contract references unknown profile {name!r}")
        profile = config["profiles"][name]
        for key in contract.get("blocking_metrics_contains", []):
            if key not in profile.get("blocking_metrics", []):
                raise ProfileConfigError(
                    f"Protected profile {name!r} must block missing metric {key!r}"
                )
        for section in contract.get("required_sections_contains", []):
            if section not in profile.get("required_sections", []):
                raise ProfileConfigError(
                    f"Protected profile {name!r} must require section {section!r}"
                )
    return config


def get_path(payload: Mapping[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return None
        current = current[part]
    return current


def _has_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return bool(value)
    return True


def extract_metrics(context: Mapping[str, Any], config: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Create one canonical metric record per configured section/metric pair."""
    output: list[dict[str, Any]] = []
    seen: set[str] = set()
    for section, section_config in config["sections"].items():
        for spec in section_config.get("metrics", []):
            metric = str(spec["metric"])
            key = f"{section}.{metric}"
            if key in seen:
                continue
            seen.add(key)
            value = get_path(context, spec["value_path"])
            meta = get_path(context, spec.get("meta_path", "")) if spec.get("meta_path") else None
            if isinstance(meta, Mapping) and meta.get("status"):
                status = str(meta["status"])
                reason = meta.get("reason")
                source = meta.get("source")
                period = meta.get("period")
                basis = meta.get("basis")
                formula = meta.get("formula")
                inputs = list(meta.get("inputs") or [])
                meta_value = meta.get("value")
                if meta_value is not None or value is None:
                    value = meta_value
            elif _has_value(value):
                status = str(spec.get("default_status", "reported"))
                reason = None
                source = spec.get("source") or spec["value_path"].split(".")[0]
                period = None
                basis = "context_value"
                formula = None
                inputs = []
            else:
                status = str(spec.get("missing_status", "source_empty"))
                reason = spec.get("missing_reason") or "context_metric_missing_or_null"
                source = spec.get("source") or spec["value_path"].split(".")[0]
                period = None
                basis = "context_value"
                formula = None
                inputs = []
            output.append({
                "section": section,
                "metric": metric,
                "key": key,
                "value": value,
                "status": status,
                "reason": reason,
                "source": source,
                "period": period,
                "basis": basis,
                "formula": formula,
                "inputs": inputs,
            })
    return output


def metric_weight(metric: Mapping[str, Any], profile: Mapping[str, Any]) -> float:
    status = metric.get("status")
    if status in {"reported", "derived"}:
        return 1.0
    if status == "proxy":
        return float(profile.get("proxy_weight", 1.0)) if profile.get("allow_proxy") else 0.0
    if status == "stale":
        return float(profile.get("stale_weight", 1.0)) if profile.get("allow_stale") else 0.0
    return 0.0


def calculate_section_coverage(metrics: Iterable[Mapping[str, Any]], profile: Mapping[str, Any]) -> dict[str, Any]:
    unique: dict[str, dict[str, Any]] = {}
    for item in metrics:
        unique.setdefault(str(item["metric"]), dict(item))
    ordered = [unique[name] for name in sorted(unique)]
    not_applicable = [item for item in ordered if item["status"] == NOT_APPLICABLE]
    applicable = [item for item in ordered if item["status"] != NOT_APPLICABLE]
    weighted_available = sum(metric_weight(item, profile) for item in applicable)
    available = [item for item in applicable if metric_weight(item, profile) > 0]
    missing = [item for item in applicable if metric_weight(item, profile) == 0]
    expected = len(applicable)
    coverage = weighted_available / expected if expected else 1.0
    if not expected:
        status = "not_applicable"
    elif coverage >= 1.0:
        status = "complete"
    elif coverage > 0:
        status = "partial"
    else:
        status = "missing"
    return {
        "status": status,
        "coverage": round(coverage, 6),
        "available_metrics": len(available),
        "weighted_available_metrics": round(weighted_available, 6),
        "expected_metrics": expected,
        "missing_metrics": [
            {"metric": item["metric"], "status": item["status"], "reason": item.get("reason")}
            for item in missing
        ],
        "available_metric_names": [item["metric"] for item in available],
        "derived_metrics": [item["metric"] for item in applicable if item["status"] == "derived"],
        "proxy_metrics": [item["metric"] for item in applicable if item["status"] == "proxy"],
        "stale_metrics": [item["metric"] for item in applicable if item["status"] == "stale"],
        "not_applicable_metrics": [item["metric"] for item in not_applicable],
    }


def _schema_validation(context: Mapping[str, Any], schema_path: Path | None) -> tuple[bool, list[str]]:
    if schema_path is None:
        return True, []
    try:
        from validate_json_schema_subset import load_json, validate
    except ModuleNotFoundError:
        from builders.validate_json_schema_subset import load_json, validate
    errors = validate(context, load_json(schema_path))
    return not errors, errors


def _guard_failures(context: Mapping[str, Any], guards: Iterable[str]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for guard in guards:
        if guard == "analysis_cutoff_present" and not context.get("analysis_cutoff"):
            failures.append({"section": "guardrails", "metric": "analysis_cutoff", "status": "not_queried", "reason": "backtest_requires_analysis_cutoff"})
        elif guard == "financial_point_in_time_safe":
            warning = str(get_path(context, "financial_summary.availability_warning") or "")
            if "not point-in-time safe" in warning.lower() or not warning:
                failures.append({"section": "guardrails", "metric": "financial_publication_date", "status": "period_basis_unknown", "reason": "financial_availability_date_not_confirmed"})
        elif guard == "price_adjustment_confirmed":
            warning = str(get_path(context, "price_summary.adjusted_price_warning") or "")
            if "not fully confirmed" in warning.lower() or not warning:
                failures.append({"section": "guardrails", "metric": "price_adjustment", "status": "period_basis_unknown", "reason": "corporate_action_adjustment_not_confirmed"})
        elif guard not in {"analysis_cutoff_present", "financial_point_in_time_safe", "price_adjustment_confirmed"}:
            raise ProfileConfigError(f"Unknown profile guard: {guard}")
    return failures


def validate_profile(
    context: Mapping[str, Any],
    profile_name: str,
    config: Mapping[str, Any],
    *,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    profiles = config.get("profiles", {})
    if profile_name not in profiles:
        raise ProfileConfigError(f"Unknown validation profile: {profile_name}")
    profile = profiles[profile_name]
    metrics = extract_metrics(context, config)
    by_section = {
        section: [item for item in metrics if item["section"] == section]
        for section in config["sections"]
    }
    coverage = {
        section: calculate_section_coverage(section_metrics, profile)
        for section, section_metrics in by_section.items()
    }
    schema_valid, schema_errors = _schema_validation(context, schema_path)
    required_sections = list(profile["required_sections"])
    missing_required_sections = [
        section for section in required_sections
        if not _has_value(get_path(context, config["sections"][section]["context_path"]))
    ]
    blocking: list[dict[str, Any]] = []
    blocking_keys: set[str] = set()
    metric_by_key = {item["key"]: item for item in metrics}
    for key in profile.get("blocking_metrics", []):
        item = metric_by_key.get(key)
        if item is None:
            raise ProfileConfigError(f"Profile {profile_name!r} references unknown metric {key!r}")
        if item["status"] != NOT_APPLICABLE and metric_weight(item, profile) == 0:
            failure = {name: item.get(name) for name in ("section", "metric", "status", "reason", "source", "period", "basis")}
            failure["blocking_rule"] = "blocking_metric"
            blocking.append(failure)
            blocking_keys.add(key)
    for group in profile.get("blocking_any_of", []):
        candidates = [metric_by_key.get(key) for key in group.get("metrics", [])]
        if any(item is None for item in candidates):
            raise ProfileConfigError(f"Profile {profile_name!r} has an unknown blocking_any_of metric")
        applicable = [item for item in candidates if item and item["status"] != NOT_APPLICABLE]
        usable = sum(metric_weight(item, profile) > 0 for item in applicable)
        if usable < int(group.get("minimum_available", 1)):
            blocking.append({
                "section": applicable[0]["section"] if applicable else "profile",
                "metric": " | ".join(group.get("metrics", [])),
                "status": "insufficient_periods",
                "reason": group.get("reason") or "blocking_any_of_not_satisfied",
                "blocking_rule": "blocking_any_of",
            })
            blocking_keys.update(group.get("metrics", []))
    allowed_missing = set(profile.get("allowed_missing_statuses", []))
    for item in metrics:
        if item["section"] not in required_sections or item["status"] == NOT_APPLICABLE:
            continue
        if metric_weight(item, profile) == 0 and item["status"] not in allowed_missing and item["key"] not in blocking_keys:
            failure = {name: item.get(name) for name in ("section", "metric", "status", "reason", "source", "period", "basis")}
            failure["blocking_rule"] = "missing_status_not_allowed"
            blocking.append(failure)
            blocking_keys.add(item["key"])
    for section in missing_required_sections:
        blocking.append({"section": section, "metric": None, "status": "section_missing", "reason": "required_context_section_missing", "blocking_rule": "required_section"})
    section_threshold_passed = True
    for section in required_sections:
        threshold = float(profile.get("minimum_section_coverage", {}).get(section, 0.0))
        if coverage[section]["coverage"] < threshold:
            section_threshold_passed = False
            blocking.append({
                "section": section, "metric": None, "status": "coverage_below_minimum",
                "reason": f"coverage={coverage[section]['coverage']:.6f};minimum={threshold:.6f}",
                "blocking_rule": "minimum_section_coverage",
            })
    blocking.extend(_guard_failures(context, profile.get("guards", [])))
    required_metrics = [item for item in metrics if item["section"] in required_sections and item["status"] != NOT_APPLICABLE]
    expected = len(required_metrics)
    weighted_available = sum(metric_weight(item, profile) for item in required_metrics)
    overall_coverage = weighted_available / expected if expected else 1.0
    minimum_overall = float(profile["minimum_overall_coverage"])
    minimum_coverage_passed = section_threshold_passed and overall_coverage >= minimum_overall
    if overall_coverage < minimum_overall:
        blocking.append({
            "section": "overall", "metric": None, "status": "coverage_below_minimum",
            "reason": f"coverage={overall_coverage:.6f};minimum={minimum_overall:.6f}",
            "blocking_rule": "minimum_overall_coverage",
        })
    missing_metric_records = [
        item for item in metrics
        if item["status"] != NOT_APPLICABLE and metric_weight(item, profile) == 0
    ]
    non_blocking = [
        {name: item.get(name) for name in ("section", "metric", "status", "reason", "source", "period", "basis")}
        for item in missing_metric_records if item["key"] not in blocking_keys
    ]
    blocking = sorted(blocking, key=lambda item: (str(item.get("section")), str(item.get("metric")), str(item.get("blocking_rule"))))
    non_blocking = sorted(non_blocking, key=lambda item: (str(item.get("section")), str(item.get("metric"))))
    profile_valid = schema_valid and not blocking and minimum_coverage_passed and not missing_required_sections
    overall_status = "invalid" if not schema_valid else (
        "complete" if overall_coverage >= 1.0 else "partial" if overall_coverage > 0 else "missing"
    )
    proxy_metrics = sorted(
        ({name: item.get(name) for name in ("section", "metric", "status", "reason", "source")}
         for item in metrics if item["status"] == "proxy"),
        key=lambda item: (item["section"], item["metric"]),
    )
    stale_metrics = sorted(
        ({name: item.get(name) for name in ("section", "metric", "status", "reason", "source", "period")}
         for item in metrics if item["status"] == "stale"),
        key=lambda item: (item["section"], item["metric"]),
    )
    not_applicable_metrics = sorted(
        ({name: item.get(name) for name in ("section", "metric", "status", "reason", "source")}
         for item in metrics if item["status"] == NOT_APPLICABLE),
        key=lambda item: (item["section"], item["metric"]),
    )
    warnings = []
    if proxy_metrics:
        warnings.append(f"Profile proxy policy: allowed={bool(profile['allow_proxy'])}, weight={float(profile.get('proxy_weight', 0.0)):.2f}.")
    if stale_metrics:
        warnings.append(f"Profile stale policy: allowed={bool(profile['allow_stale'])}, weight={float(profile.get('stale_weight', 0.0)):.2f}.")
    return {
        "report_version": "1.0.0",
        "ticker": context.get("ticker"),
        "validation_profile": profile_name,
        "valid": schema_valid and not missing_required_sections,
        "valid_semantics": "legacy-compatible schema/required-section validity; use profile_valid for purpose suitability",
        "schema_valid": schema_valid,
        "schema_errors": schema_errors,
        "required_sections_present": not missing_required_sections,
        "missing_required_sections": missing_required_sections,
        "minimum_coverage_passed": minimum_coverage_passed,
        "profile_valid": profile_valid,
        "overall_status": overall_status,
        "overall_coverage": round(overall_coverage, 6),
        "minimum_overall_coverage": minimum_overall,
        "blocking_missing": blocking,
        "non_blocking_missing": non_blocking,
        "warnings": warnings,
        "coverage": coverage,
        "stale_metrics": stale_metrics,
        "proxy_metrics": proxy_metrics,
        "not_applicable_metrics": not_applicable_metrics,
        "metric_inventory": metrics,
        "profile_policy": {
            "required_sections": required_sections,
            "blocking_metrics": list(profile.get("blocking_metrics", [])),
            "blocking_any_of": list(profile.get("blocking_any_of", [])),
            "allowed_missing_statuses": sorted(allowed_missing),
            "allow_proxy": bool(profile["allow_proxy"]),
            "proxy_weight": float(profile.get("proxy_weight", 0.0)),
            "allow_stale": bool(profile["allow_stale"]),
            "stale_weight": float(profile.get("stale_weight", 0.0)),
        },
    }


def render_markdown(report: Mapping[str, Any]) -> str:
    def label(item: Mapping[str, Any]) -> str:
        section = str(item.get("section") or "unknown")
        metric = item.get("metric")
        if not metric:
            return section
        metric_text = str(metric)
        return metric_text if metric_text.startswith(section + ".") else f"{section}.{metric_text}"

    lines = [
        f"# Context coverage — {report.get('ticker')}", "",
        f"- Profile: `{report['validation_profile']}`",
        f"- Profile valid: `{str(report['profile_valid']).lower()}`",
        f"- Schema valid: `{str(report['schema_valid']).lower()}`",
        f"- Overall status: `{report['overall_status']}`",
        f"- Overall coverage: `{report['overall_coverage']:.2%}`", "",
        "## Section coverage", "",
        "| Section | Status | Coverage | Available | Expected |", "|---|---:|---:|---:|---:|",
    ]
    for section, item in report["coverage"].items():
        lines.append(f"| {section} | {item['status']} | {item['coverage']:.2%} | {item['available_metrics']} | {item['expected_metrics']} |")
    for title, key in (("Blocking missing", "blocking_missing"), ("Non-blocking missing", "non_blocking_missing")):
        lines.extend(["", f"## {title}", ""])
        items = report[key]
        if not items:
            lines.append("- None.")
        else:
            for item in items:
                lines.append(f"- `{label(item)}` — `{item.get('status')}`: {item.get('reason') or 'no reason supplied'}")
    for title, key in (("Stale metrics", "stale_metrics"), ("Proxy metrics", "proxy_metrics"), ("Not-applicable metrics", "not_applicable_metrics")):
        lines.extend(["", f"## {title}", ""])
        items = report[key]
        lines.append("- None." if not items else "\n".join(f"- `{item['section']}.{item['metric']}`" for item in items))
    lines.extend(["", "## Interpretation", "", "Coverage measures data usability for the selected profile. It is not an investment score or recommendation.", ""])
    return "\n".join(lines)


def aggregate_universe(reports: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for report in reports:
        for item in report.get("metric_inventory", []):
            key = str(item["key"])
            bucket = grouped.setdefault(key, {"metric": key, "available": 0, "derived": 0, "proxy": 0, "missing": 0, "stale": 0, "not_applicable": 0, "total": 0})
            status = item["status"]
            bucket["total"] += 1
            if status in AVAILABLE:
                bucket["available"] += 1
            else:
                bucket["missing"] += status != NOT_APPLICABLE
            bucket["derived"] += status == "derived"
            bucket["proxy"] += status == "proxy"
            bucket["stale"] += status == "stale"
            bucket["not_applicable"] += status == NOT_APPLICABLE
    output = []
    for key in sorted(grouped):
        row = grouped[key]
        denominator = row["total"] - row["not_applicable"]
        row["coverage_pct"] = round((row["available"] / denominator * 100.0) if denominator else 100.0, 6)
        output.append(row)
    return output


def save_universe_reports(
    rows: list[dict[str, Any]],
    json_path: Path,
    csv_path: Path,
    metadata: Mapping[str, Any] | None = None,
) -> None:
    payload = {**dict(metadata or {}), "metrics": rows}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fields = ["metric", "available", "derived", "proxy", "missing", "stale", "not_applicable", "coverage_pct"]
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
