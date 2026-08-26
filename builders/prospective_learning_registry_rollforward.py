"""Deterministic foreground orchestration for longitudinal-registry ingestion."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

from builders.prospective_learning_longitudinal_registry import (
    empty_registry,
    register_review_product,
    render_registry_inventory,
    summarize_registry,
)


SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "prospective_learning_registry_rollforward/v1"
_AUTHORITY_BOUNDARY = [
    "ORCHESTRATION_ONLY_REUSES_EXISTING_PRODUCT_AND_REGISTRY_CONTRACTS",
    "APPEND_ONLY_REGISTRY_NO_CURRENT_DECISION_FEEDBACK",
    "NOT_SCORE_PERFORMANCE_BACKTEST_OR_MODEL_LEARNING",
    "NOT_PIT_RAW_AS_TRADED_OR_RECOMMENDATION_AUTHORITY",
]


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def rollforward_registry(registry: Mapping[str, Any], product_inputs: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Apply bounded product registrations in canonical order without writing anything."""
    if not isinstance(registry, Mapping):
        return {"status": "MALFORMED", "reason_codes": ["input_registry_not_mapping"], "registry": None, "manifest": None}
    try:
        summarize_registry(registry)
    except ValueError as error:
        return {"status": "MALFORMED", "reason_codes": [str(error)], "registry": copy.deepcopy(dict(registry)), "manifest": None}
    normalized: list[dict[str, Any]] = []
    for item in product_inputs:
        if not isinstance(item, Mapping) or not isinstance(item.get("reference"), str) or not isinstance(item.get("product"), Mapping):
            return {"status": "MALFORMED", "reason_codes": ["product_input_malformed"], "registry": copy.deepcopy(dict(registry)), "manifest": None}
        product = item["product"]
        normalized.append({"reference": item["reference"], "product": product, "product_identity": product.get("product_identity")})
    normalized.sort(key=lambda item: (str(item["product_identity"] or ""), item["reference"]))
    current = copy.deepcopy(dict(registry))
    results: list[dict[str, Any]] = []
    reason_counts: Counter[str] = Counter()
    appended = duplicate = linked = rejected = 0
    for item in normalized:
        outcome = register_review_product(current, item["product"], retained_product_reference=item["reference"])
        status = outcome.get("status")
        reasons = sorted(set(outcome.get("reason_codes") or []))
        registrations = outcome.get("results") or []
        reason_counts.update(reason for reason in reasons if isinstance(reason, str))
        if status in {"REGISTERED", "DUPLICATE_IDENTICAL"}:
            current = outcome["registry"]
            appended_rows = [row for row in registrations if row.get("status") == "REGISTERED"]
            duplicate_rows = [row for row in registrations if row.get("status") == "DUPLICATE_IDENTICAL"]
            appended += len(appended_rows)
            duplicate += len(duplicate_rows)
            linked += sum(
                bool(next((record.get("lineage", {}).get("prior_pending_registration_identities") for record in current.get("registrations", []) if record.get("registration_identity") == row.get("registration_identity")), []))
                for row in appended_rows
            )
        else:
            rejected += 1
        results.append({"product_identity": item["product_identity"], "reference": item["reference"], "status": status, "reason_codes": reasons, "registration_results": copy.deepcopy(registrations)})
    summary = summarize_registry(current) if current is not None else None
    manifest = {
        "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
        "input_registry_identity": registry.get("registry_identity"),
        "input_products": [{"product_identity": item["product_identity"], "reference": item["reference"]} for item in normalized],
        "product_results": results,
        "accepted_product_count": len(normalized) - rejected,
        "appended_registration_count": appended,
        "duplicate_identical_count": duplicate,
        "pending_to_later_linked_count": linked,
        "blocked_or_conflict_count": rejected,
        "reason_code_distribution": dict(sorted(reason_counts.items())),
        "output_registry_identity": current.get("registry_identity") if current else None,
        "output_summary": summary,
        "unexplained_residual": 0,
        "authority_boundary": list(_AUTHORITY_BOUNDARY), "is_actionable": False,
    }
    manifest["rollforward_identity"] = _identity("prospective_learning_registry_rollforward:", manifest)
    if rejected:
        status = "COMPLETED_WITH_REJECTIONS"
    elif appended == 0:
        status = "NO_OP_DUPLICATE_IDENTICAL"
    else:
        status = "COMPLETED"
    return {"status": status, "reason_codes": [], "registry": current, "manifest": manifest}


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=".rollforward-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        os.replace(temporary_name, path)
    except Exception:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def write_rollforward_output(output_dir: Path, result: Mapping[str, Any]) -> dict[str, Path]:
    """Atomically write a new immutable registry, inventory, and run manifest set."""
    if result.get("registry") is None or result.get("manifest") is None:
        raise ValueError("ROLLFORWARD_RESULT_INCOMPLETE")
    outputs = {
        "registry": output_dir / "prospective_learning_longitudinal_registry.json",
        "inventory": output_dir / "prospective_learning_longitudinal_registry_inventory.md",
        "manifest": output_dir / "prospective_learning_registry_rollforward_manifest.json",
    }
    contents = {
        "registry": _canonical(result["registry"]) + "\n",
        "inventory": render_registry_inventory(result["registry"]),
        "manifest": _canonical(result["manifest"]) + "\n",
    }
    for name, path in outputs.items():
        if path.exists() and path.read_text(encoding="utf-8") != contents[name]:
            raise ValueError("IMMUTABLE_ROLLFORWARD_OUTPUT_CONFLICT:" + str(path))
    for name, path in outputs.items():
        if not path.exists():
            _atomic_write(path, contents[name])
    return outputs


def load_registry_or_empty(path: Path, *, create_if_missing: bool) -> dict[str, Any]:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    if create_if_missing:
        return empty_registry()
    raise FileNotFoundError(path)
