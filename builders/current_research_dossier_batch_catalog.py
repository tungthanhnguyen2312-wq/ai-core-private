"""Deterministic batch availability/catalog for existing current research dossiers."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from builders.current_research_auditable_dossier import (
    build_current_research_auditable_dossier,
    render_current_research_auditable_dossier_markdown,
    replay_current_research_auditable_dossier,
)

SCHEMA_VERSION = "1.0.0"
CONTRACT_VERSION = "current_research_dossier_batch_catalog/v1"
DOSSIER_READY = "DOSSIER_READY"
NO_ACCEPTED_SYNTHESIS = "NO_ACCEPTED_SYNTHESIS"
REJECTED_UNTRACEABLE = "REJECTED_UNTRACEABLE"
CONTEXT_UNAVAILABLE = "CONTEXT_UNAVAILABLE"
EVIDENCE_CONFLICT_FAIL_CLOSED = "EVIDENCE_CONFLICT_FAIL_CLOSED"
MALFORMED = "MALFORMED"
AUTHORITY_BLOCKED = "AUTHORITY_BLOCKED"
INPUT_NOT_FOUND = "INPUT_NOT_FOUND"
_STATUSES = {DOSSIER_READY, NO_ACCEPTED_SYNTHESIS, REJECTED_UNTRACEABLE, CONTEXT_UNAVAILABLE, EVIDENCE_CONFLICT_FAIL_CLOSED, MALFORMED, AUTHORITY_BLOCKED, INPUT_NOT_FOUND}


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _identity(prefix: str, value: Any) -> str:
    return prefix + hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _load_object(path: Path) -> Mapping[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise ValueError("INPUT_JSON_NOT_OBJECT")
    return value


def load_batch_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError("BATCH_MANIFEST_NOT_FOUND:" + str(path))
    raw = _load_object(path)
    records = raw.get("records")
    if raw.get("contract_version") not in {None, CONTRACT_VERSION} or not isinstance(records, list):
        raise ValueError("BATCH_MANIFEST_MALFORMED")
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in records:
        if not isinstance(item, Mapping) or not isinstance(item.get("ticker"), str) or not item["ticker"].strip():
            raise ValueError("BATCH_MANIFEST_RECORD_MALFORMED")
        ticker = item["ticker"].strip().upper()
        if ticker in seen:
            raise ValueError("BATCH_MANIFEST_DUPLICATE_TICKER:" + ticker)
        seen.add(ticker)
        record = {"ticker": ticker}
        for name in ("context_path", "synthesis_path", "claim_evidence_map_path"):
            value = item.get(name)
            if value is not None and not isinstance(value, str):
                raise ValueError("BATCH_MANIFEST_RECORD_PATH_MALFORMED:" + ticker + ":" + name)
            if isinstance(value, str):
                record[name] = str((path.parent / value).resolve()) if not Path(value).is_absolute() else str(Path(value).resolve())
        result.append(record)
    return {"batch_session": raw.get("batch_session"), "records": result, "manifest_identity": _identity("current_research_dossier_batch_manifest:", {"batch_session": raw.get("batch_session"), "records": sorted(result, key=lambda row: row["ticker"])})}


def _availability_record(raw: Mapping[str, Any], *, dossier: Mapping[str, Any] | None = None, status: str, reasons: list[str]) -> dict[str, Any]:
    ticker = raw["ticker"]
    output_rel = f"{ticker}/current_research_auditable_dossier.json" if status == DOSSIER_READY else None
    response_status = None
    trace_identity = None
    if isinstance(dossier, Mapping):
        response_status = "accepted" if dossier.get("status") == "READY_FOR_AUDIT" else "rejected"
        trace_identity = dossier.get("research_identity", {}).get("trace_identity") if isinstance(dossier.get("research_identity"), Mapping) else dossier.get("trace_identity")
    return {
        "ticker": ticker, "dossier_disposition": status,
        "dossier_identity": dossier.get("dossier_identity") if isinstance(dossier, Mapping) else None,
        "structured_synthesis_status": response_status,
        "structured_synthesis_identity": dossier.get("research_identity", {}).get("structured_synthesis_identity") if isinstance(dossier, Mapping) and isinstance(dossier.get("research_identity"), Mapping) else None,
        "claim_trace_identity": trace_identity,
        "current_research_source_identity": dossier.get("research_identity", {}).get("current_research_source_identity") if isinstance(dossier, Mapping) and isinstance(dossier.get("research_identity"), Mapping) else None,
        "research_session": dossier.get("research_identity", {}).get("research_session") if isinstance(dossier, Mapping) and isinstance(dossier.get("research_identity"), Mapping) else None,
        "output_paths": {"json": output_rel, "markdown": output_rel.replace(".json", ".md") if output_rel else None},
        "unresolved_count": len(dossier.get("unresolved_questions") or []) if isinstance(dossier, Mapping) and dossier.get("status") == "READY_FOR_AUDIT" else None,
        "authority_limitation_count": len(dossier.get("authority_limitations") or []) if isinstance(dossier, Mapping) and dossier.get("status") == "READY_FOR_AUDIT" else None,
        "reason_codes": sorted(set(reasons)),
    }


def _rejected_status(dossier: Mapping[str, Any]) -> str:
    reasons = set(dossier.get("reason_codes") or [])
    if any("conflict" in reason for reason in reasons):
        return EVIDENCE_CONFLICT_FAIL_CLOSED
    if any(reason.startswith("prohibited_") for reason in reasons):
        return AUTHORITY_BLOCKED
    if any("malformed" in reason for reason in reasons):
        return MALFORMED
    return REJECTED_UNTRACEABLE


def build_dossier_batch_catalog(manifest: Mapping[str, Any]) -> dict[str, Any]:
    """Evaluate explicit records independently; no discovery or model generation occurs."""
    if not isinstance(manifest, Mapping) or not isinstance(manifest.get("records"), list):
        raise ValueError("BATCH_MANIFEST_MALFORMED")
    normalized: list[Mapping[str, Any]] = []
    seen: set[str] = set()
    for record in manifest["records"]:
        if not isinstance(record, Mapping) or not isinstance(record.get("ticker"), str):
            raise ValueError("BATCH_MANIFEST_RECORD_MALFORMED")
        ticker = record["ticker"].strip().upper()
        if not ticker or ticker in seen:
            raise ValueError("BATCH_MANIFEST_DUPLICATE_OR_EMPTY_TICKER")
        seen.add(ticker); normalized.append({**record, "ticker": ticker})
    rows: list[dict[str, Any]] = []
    dossiers: dict[str, dict[str, Any]] = {}
    for record in sorted(normalized, key=lambda item: item["ticker"]):
        context, response, claim_map = record.get("context"), record.get("synthesis"), record.get("claim_evidence_map")
        if record.get("missing_context") or record.get("missing_synthesis") or record.get("missing_claim_evidence_map"):
            missing = [name.removeprefix("missing_") for name in ("missing_context", "missing_synthesis", "missing_claim_evidence_map") if record.get(name)]
            rows.append(_availability_record(record, status=INPUT_NOT_FOUND, reasons=["input_not_found:" + name for name in missing])); continue
        if context is None:
            rows.append(_availability_record(record, status=CONTEXT_UNAVAILABLE, reasons=["context_not_supplied"])); continue
        if not isinstance(context, Mapping):
            rows.append(_availability_record(record, status=MALFORMED, reasons=["context_not_mapping"])); continue
        if response is None:
            rows.append(_availability_record(record, status=NO_ACCEPTED_SYNTHESIS, reasons=["accepted_synthesis_not_supplied"])); continue
        if claim_map is not None and not isinstance(claim_map, Mapping):
            rows.append(_availability_record(record, status=MALFORMED, reasons=["claim_evidence_map_not_mapping"])); continue
        if context.get("ticker") not in {None, record["ticker"]}:
            rows.append(_availability_record(record, status=MALFORMED, reasons=["manifest_context_ticker_mismatch"])); continue
        dossier = build_current_research_auditable_dossier(context, response, claim_evidence_map=claim_map, packet_consumption_mode=record.get("packet_consumption_mode", "LEGACY_DIRECT"))
        if dossier.get("status") == "READY_FOR_AUDIT":
            replay_current_research_auditable_dossier(dossier)
            dossiers[record["ticker"]] = dossier
            rows.append(_availability_record(record, dossier=dossier, status=DOSSIER_READY, reasons=[]))
        else:
            rows.append(_availability_record(record, dossier=dossier, status=_rejected_status(dossier), reasons=list(dossier.get("reason_codes") or [])))
    counts = Counter(row["dossier_disposition"] for row in rows)
    catalog = {
        "schema_version": SCHEMA_VERSION, "contract_version": CONTRACT_VERSION,
        "batch_session": manifest.get("batch_session"), "input_manifest_identity": manifest.get("manifest_identity"),
        "denominator": len(rows), "status_counts": {status: counts.get(status, 0) for status in sorted(_STATUSES)},
        "unexplained_residual": len(rows) - sum(counts.values()), "records": rows,
        "authority_boundary": {"is_actionable": False, "dossier_ready_is_not_investment_readiness": True, "does_not_generate_missing_synthesis": True, "does_not_change_packet_default": True},
    }
    catalog["catalog_identity"] = _identity("current_research_dossier_batch_catalog:", catalog)
    return {"catalog": catalog, "dossiers": dossiers}


def render_dossier_batch_inventory(catalog: Mapping[str, Any]) -> str:
    counts = catalog.get("status_counts") or {}
    lines = ["# Current Research Dossier Batch Inventory", "", f"Batch identity: `{catalog.get('catalog_identity')}`", f"Batch session: `{catalog.get('batch_session')}`", f"Ticker denominator: `{catalog.get('denominator')}`", "", "| Disposition | Count |", "|---|---:|"]
    lines.extend(f"| {status} | {counts.get(status, 0)} |" for status in sorted(_STATUSES))
    lines.extend(["", f"Unexplained residual: `{catalog.get('unexplained_residual')}`", "", "`DOSSIER_READY` means an auditable dossier exists; it does not mean BUY, entry now, investable, valuation-ready, low risk, liquid, or sizing-approved.", "", "## Records", "", "| Ticker | Operational status | Output |", "|---|---|---|"])
    for row in catalog.get("records") or []:
        lines.append(f"| {row.get('ticker')} | {row.get('dossier_disposition')} | {row.get('output_paths', {}).get('markdown') or '-'} |")
    return "\n".join(lines) + "\n"


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".dossier-batch-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle: handle.write(content)
        os.replace(temp, path)
    except Exception:
        if os.path.exists(temp): os.unlink(temp)
        raise


def write_dossier_batch_output(output_dir: Path, result: Mapping[str, Any], *, preflight_only: bool = False) -> dict[str, Path]:
    catalog = result.get("catalog"); dossiers = result.get("dossiers")
    if not isinstance(catalog, Mapping) or not isinstance(dossiers, Mapping): raise ValueError("BATCH_RESULT_MALFORMED")
    contents: dict[Path, str] = {output_dir / "current_research_auditable_dossier_catalog.json": _canonical(catalog) + "\n", output_dir / "current_research_auditable_dossier_inventory.md": render_dossier_batch_inventory(catalog)}
    if not preflight_only:
        for ticker, dossier in dossiers.items():
            folder = output_dir / ticker
            contents[folder / "current_research_auditable_dossier.json"] = _canonical(dossier) + "\n"
            contents[folder / "current_research_auditable_dossier.md"] = render_current_research_auditable_dossier_markdown(dossier)
    for path, content in contents.items():
        if path.exists() and path.read_text(encoding="utf-8") != content: raise ValueError("IMMUTABLE_BATCH_OUTPUT_CONFLICT:" + str(path))
    for path, content in contents.items():
        if not path.exists(): _atomic_write(path, content)
    return {"catalog": output_dir / "current_research_auditable_dossier_catalog.json", "inventory": output_dir / "current_research_auditable_dossier_inventory.md"}


def replay_dossier_batch_catalog(catalog: Mapping[str, Any]) -> None:
    if catalog.get("contract_version") != CONTRACT_VERSION: raise ValueError("BATCH_CATALOG_CONTRACT_VERSION_MISMATCH")
    expected = dict(catalog); identity = expected.pop("catalog_identity", None)
    if _identity("current_research_dossier_batch_catalog:", expected) != identity: raise ValueError("BATCH_CATALOG_IDENTITY_MISMATCH")
    if catalog.get("unexplained_residual") != 0: raise ValueError("BATCH_CATALOG_UNEXPLAINED_RESIDUAL")
    if sum((catalog.get("status_counts") or {}).values()) != catalog.get("denominator"): raise ValueError("BATCH_CATALOG_COUNTS_MISMATCH")
