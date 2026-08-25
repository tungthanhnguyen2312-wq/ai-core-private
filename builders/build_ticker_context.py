"""Read-only VNSTOCK ticker context builder.

The builder reads a small ticker slice from SQLite/CSV sources, never writes to
VNSTOCK, and only creates new JSON files under the approved AI ANALYZE exports
area. It produces data context, not investment analysis or recommendations.
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import importlib.util
import json
import math
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vn_time import vn_now_iso  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent


def resolve_dashboard_runtime_root() -> Path:
    """Prefer the unified workspace runtime while supporting old and transitional layouts."""
    candidates = (
        WORKSPACE_ROOT.parent / "dashboard-runtime",
        WORKSPACE_ROOT.parent / "VNSTOCK",
        WORKSPACE_ROOT.parent.parent / "VNSTOCK",
    )
    return next((path.resolve() for path in candidates if path.exists()), candidates[0].resolve())


# Retain the established internal name so existing context logic and tests keep their contract.
VNSTOCK_ROOT = resolve_dashboard_runtime_root()
CONFIG_PATH = SCRIPT_DIR / "build_ticker_context_config.json"
REPORTS_ROOT = (WORKSPACE_ROOT / "reports").resolve()

try:
    from context_coverage import (
        ProfileConfigError,
        load_config as load_coverage_config,
        render_markdown as render_coverage_markdown,
        validate_profile,
    )
except ModuleNotFoundError:
    from builders.context_coverage import (
        ProfileConfigError,
        load_config as load_coverage_config,
        render_markdown as render_coverage_markdown,
        validate_profile,
    )

try:
    from missing_data_contract import (
        CONTRACT_VERSION,
        MetricStatus,
        build_metric_meta,
        build_section_coverage,
        is_metric_available,
        set_metric_with_meta,
    )
except ModuleNotFoundError:  # importlib-based tests load this file from the workspace root
    from builders.missing_data_contract import (
        CONTRACT_VERSION,
        MetricStatus,
        build_metric_meta,
        build_section_coverage,
        is_metric_available,
        set_metric_with_meta,
    )

try:
    from metadata_registry_reader import SnapshotError, read_snapshot
except ModuleNotFoundError:  # importlib-based tests load this file from the workspace root
    from builders.metadata_registry_reader import SnapshotError, read_snapshot

# check_registry_promotion_gate is imported lazily inside _select_metadata_loader, not here:
# metadata_registry_shadow_compare.py itself imports compare_metadata_slices/load_metadata_slice/
# load_metadata_slice_from_registry_snapshot FROM this module, so a top-level import here would
# be circular. Deferring it to call time (only reached when registry_shadow_gate=True) avoids
# that entirely, in either module's import order.


FINANCIAL_CONTRACT_METRICS = (
    "operating_cash_flow",
    "ebit",
    "ebitda",
    "interest_expense",
    "retained_earnings",
    "depreciation",
    "sga",
)

# Phase 2 price-basis consumer contract.  A provider name, endpoint, or OHLCV column
# name does not establish whether prices include corporate-action adjustments.
PRICE_BASIS_VALUES = frozenset({"raw", "adjusted", "unknown"})
PRICE_BASIS_UNVERIFIED_CODE = "price_basis_unverified"
VOLUME_BASIS_UNVERIFIED_CODE = "volume_basis_unverified"
CORPORATE_INTELLIGENCE_SECTIONS = (
    "company_profile",
    "company_subsidiaries",
    "ownership_structure",
    "major_shareholders",
    "corporate_events",
)
CORPORATE_INTELLIGENCE_STATUSES = frozenset({"available", "missing", "partial", "malformed", "incomparable"})


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"Required JSON file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {path}: {exc}") from exc


def resolve_optional_source_path(configured: str) -> Path:
    """Resolve a configured source, falling back to the discovered legacy runtime root."""
    path = Path(str(configured))
    if path.is_absolute():
        return path
    candidate = (WORKSPACE_ROOT / path).resolve()
    if candidate.exists() or not path.as_posix().startswith("../dashboard-runtime/"):
        return candidate
    return VNSTOCK_ROOT / Path(*path.parts[2:])


# ==========================================================================
# Exact-session trusted-subset verification (Producer contract 1.1.0)
# ==========================================================================
# A bundle is only trusted when its manifest proves it describes THIS export session --
# not merely that the manifest is well-shaped JSON. Schema 1.0.0 checked the bundle's own
# hash and nothing else, so a manifest paired with a different bundle body, an artifact
# rewritten after manifest generation, an undeclared trusted artifact sitting next to the
# bundle, or a bundle from an older Producer all passed. Each of those is now a distinct,
# named rejection.
#
# These values are pinned, not ranged. An older Producer's output is legacy, and legacy is
# never current trusted output.
PRODUCER_BUNDLE_CONTRACT_VERSION = "stocklookup-producer/2026.08.03"
TRUSTED_SUBSET_SCHEMA_VERSION = "1.1.0"
# Exactly the filenames that carry export-session trust. The Consumer scans only these
# names beside the bundle, so an unrelated file in the runtime root is never mistaken for
# an undeclared session artifact.
TRUSTED_ARTIFACT_NAMESPACE = (
    "analysis_bundle.json", "bundle_manifest.json", "focus_extract.json",
    "statement_taxonomy_sidecar.json",
)
BUNDLE_MANIFEST_FILENAME = "bundle_manifest.json"


def _sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_exact_session_bundle(bundle_path: Path, payload: Mapping[str, Any],
                                manifest: Any) -> tuple[bool, str | None]:
    """Return (integrity_verified, rejection_reason).

    Every rejection names one precise cause. Diagnostics carry filenames only -- never a
    filesystem path, a secret, or any bundle content -- so a rejection reason is safe to
    surface in a context package.
    """
    if not isinstance(manifest, Mapping):
        return False, "manifest_invalid_payload"
    proof = manifest.get("trusted_subset")
    if not isinstance(proof, Mapping):
        return False, "manifest_proof_missing"
    if proof.get("schema_version") != TRUSTED_SUBSET_SCHEMA_VERSION:
        return False, "manifest_schema_unsupported"
    if proof.get("producer_contract_version") != PRODUCER_BUNDLE_CONTRACT_VERSION:
        return False, "producer_contract_version_unsupported"
    proven = proof.get("tickers")
    if not isinstance(proven, list) or not proven or sorted(proven) != list(proven):
        return False, "proven_ticker_set_invalid"
    unproven = proof.get("unproven_tickers")
    if not isinstance(unproven, list):
        return False, "unproven_ticker_set_missing"
    covered = proof.get("bundle_ticker_set")
    if not isinstance(covered, list) or not covered:
        return False, "bundle_ticker_set_missing"
    # Complete accounting: every exported ticker is either proven for this session or
    # explicitly listed as unproven with a reason. A ticker silently absent from both is
    # exactly the case an "it looked schema-valid" check would wave through.
    unproven_names = {str((row or {}).get("ticker")) for row in unproven if isinstance(row, Mapping)}
    if set(covered) != set(proven) | unproven_names:
        return False, "ticker_accounting_incomplete"
    if any(not (row or {}).get("reason") for row in unproven if isinstance(row, Mapping)):
        return False, "unproven_ticker_missing_reason"
    if set(covered) != set(payload.get("tickers_requested") or covered):
        return False, "bundle_ticker_set_mismatch"
    if proof.get("bundle_filename") != bundle_path.name:
        return False, "bundle_filename_mismatch"

    session = proof.get("session_identity")
    if not session:
        return False, "session_identity_missing"

    # The manifest must describe THIS bundle body, not merely a bundle that hashes to
    # whatever the manifest happens to record.
    try:
        if proof.get("bundle_sha256") != _sha256_path(bundle_path):
            return False, "bundle_hash_mismatch"
    except OSError:
        return False, "bundle_unreadable"
    if proof.get("bundle_reference_session_date") != payload.get("reference_session_date"):
        return False, "bundle_session_mismatch"
    if proof.get("bundle_generated_at") != payload.get("generated_at"):
        return False, "bundle_generated_at_mismatch"
    if proof.get("generated_at") != payload.get("generated_at"):
        return False, "manifest_generated_at_mismatch"
    if manifest.get("generated_at") != payload.get("generated_at"):
        return False, "manifest_bundle_generated_at_mismatch"

    per_ticker = proof.get("per_ticker")
    if not isinstance(per_ticker, Mapping):
        return False, "per_ticker_proof_missing"
    if sorted(per_ticker) != list(proven):
        return False, "per_ticker_set_mismatch"
    for ticker in proven:
        entry = per_ticker.get(ticker)
        if not isinstance(entry, Mapping) or entry.get("session_identity") != session:
            return False, "per_ticker_session_mismatch"
        body = (payload.get("tickers") or {}).get(ticker)
        body_session = (body or {}).get("snapshot", {}).get("date") if isinstance(body, Mapping) else None
        if body_session != session:
            return False, "bundle_ticker_session_mismatch"

    # Required artifact set: every declared artifact must exist beside the bundle and still
    # hash to what the manifest recorded, and nothing in the trusted namespace may exist
    # that the manifest did not declare.
    required = proof.get("required_artifacts")
    if not isinstance(required, list) or not required:
        return False, "required_artifacts_missing"
    declared: dict[str, str] = {}
    for item in required:
        if not isinstance(item, Mapping) or not item.get("file") or not item.get("sha256"):
            return False, "required_artifacts_malformed"
        declared[str(item["file"])] = str(item["sha256"])
    if "analysis_bundle.json" not in declared:
        return False, "required_artifacts_missing_bundle"
    for filename, expected in sorted(declared.items()):
        artifact = bundle_path.with_name(filename)
        if not artifact.exists():
            return False, f"required_artifact_missing:{filename}"
        try:
            if _sha256_path(artifact) != expected:
                return False, f"required_artifact_hash_mismatch:{filename}"
        except OSError:
            return False, f"required_artifact_unreadable:{filename}"

    expected_set = proof.get("expected_artifact_filenames")
    if not isinstance(expected_set, list) or not expected_set:
        return False, "expected_artifact_set_missing"
    expected_names = {str(name) for name in expected_set}
    if expected_names != set(declared) | {BUNDLE_MANIFEST_FILENAME}:
        return False, "expected_artifact_set_inconsistent"
    for filename in TRUSTED_ARTIFACT_NAMESPACE:
        if bundle_path.with_name(filename).exists() and filename not in expected_names:
            return False, f"unexpected_trusted_artifact:{filename}"

    return True, None


def load_optional_analysis_bundle(config: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Load the configured Phase 1 bundle without making it a required runtime input.

    Sets `trusted_subset_validation` with two independent axes:
      integrity_state -- did this bundle prove exact-session association? Structural and
                         cryptographic only; nothing about market data quality.
      basis_state     -- are price AND volume basis verified? Market-data qualification
                         only; nothing about integrity.
    `state` stays the pre-existing single verdict (both axes must pass), so every existing
    consumer of it is unchanged.
    """
    configured = (config.get("source_paths") or {}).get("analysis_bundle")
    if not configured:
        return {}, "analysis_bundle_not_configured"
    path = resolve_optional_source_path(str(configured))
    if not path.exists():
        return {}, "analysis_bundle_missing"
    try:
        payload = load_json(path)
    except (OSError, ValueError):
        return {}, "analysis_bundle_invalid_json"
    if not isinstance(payload, dict):
        return {}, "analysis_bundle_invalid_payload"
    manifest_path = path.with_name(BUNDLE_MANIFEST_FILENAME)
    if not manifest_path.exists():
        payload["trusted_subset_validation"] = {
            "state": "legacy_untrusted", "reason": "manifest_missing", "warnings": [],
            "integrity_state": "legacy_unverified", "integrity_reason": "manifest_missing",
            "basis_state": "unknown",
        }
        return payload, "trusted_subset_legacy_untrusted"
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError):
        manifest = None
    try:
        integrity_ok, integrity_reason = verify_exact_session_bundle(path, payload, manifest)
    except (OSError, ValueError, AttributeError, TypeError):
        integrity_ok, integrity_reason = False, "manifest_invalid"

    proof = manifest.get("trusted_subset") if isinstance(manifest, Mapping) else None
    basis_qualified = (
        (proof.get("price_basis") or {}).get("verified") is True
        and (proof.get("volume_basis") or {}).get("verified") is True
        and proof.get("trust_state") == "exact_session_qualified"
    ) if isinstance(proof, Mapping) else False

    valid = integrity_ok and basis_qualified
    if valid:
        reason = None
    elif integrity_ok:
        reason = "basis_unqualified"
    else:
        reason = integrity_reason or "manifest_invalid"

    warnings: list[str] = []
    if not integrity_ok:
        warnings.append("trusted_subset_manifest_invalid")
    elif not basis_qualified:
        warnings.append("trusted_subset_basis_unqualified")

    proven = sorted(proof.get("tickers") or []) if isinstance(proof, Mapping) else []
    unproven = {str((row or {}).get("ticker")): str((row or {}).get("reason"))
                for row in (proof.get("unproven_tickers") or []) if isinstance(row, Mapping)} \
        if isinstance(proof, Mapping) else {}

    payload["trusted_subset_validation"] = {
        "state": "exact_session_trusted" if valid else "untrusted",
        "reason": reason,
        "warnings": warnings,
        "integrity_state": "exact_session_verified" if integrity_ok else "unverified",
        "integrity_reason": integrity_reason,
        "basis_state": "qualified" if basis_qualified else "unqualified",
        "proven_tickers": proven if integrity_ok else [],
        "unproven_tickers": unproven if integrity_ok else {},
    }
    return payload, None if valid else "trusted_subset_untrusted"


def _bundle_integrity_verified(bundle: Mapping[str, Any] | None,
                               ticker: str | None = None) -> tuple[bool, str | None]:
    """Exact-session integrity for the whole bundle and, when given, for `ticker`.

    A legacy bundle carrying no validation block at all is left to the caller's own legacy
    path, exactly as before. A ticker the proof did not cover is never exact-session
    trusted even when the bundle as a whole verified -- that is the entire point of the
    proof listing an explicit proven set.
    """
    trust = (bundle or {}).get("trusted_subset_validation") if isinstance(bundle, Mapping) else None
    if not isinstance(trust, Mapping):
        return True, None
    if trust.get("integrity_state") != "exact_session_verified":
        reason = trust.get("integrity_reason") or trust.get("reason") or trust.get("state")
        return False, str(reason)
    if ticker:
        proven = trust.get("proven_tickers")
        if isinstance(proven, list) and str(ticker) not in proven:
            unproven = trust.get("unproven_tickers")
            detail = unproven.get(str(ticker)) if isinstance(unproven, Mapping) else None
            return False, f"ticker_not_session_proven:{detail or 'not_in_proof'}"
    return True, None


def normalize_price_basis_contract(bundle: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Read Phase 1's additive price-basis & volume-basis fields with safe legacy fallback."""
    bundle = bundle or {}
    raw_basis = bundle.get("price_basis")
    basis = str(raw_basis).strip().lower() if raw_basis is not None else ""
    verified = bundle.get("price_basis_verified") is True

    raw_vol_basis = bundle.get("volume_basis")
    candidate_vol_basis = str(raw_vol_basis).strip().lower() if raw_vol_basis is not None else "unknown"
    vol_verified = (
        bundle.get("volume_basis_verified") is True
        and candidate_vol_basis in {"raw_shares_traded", "adjusted_volume"}
    )
    vol_basis = candidate_vol_basis if vol_verified else "unknown"

    adj_source = bundle.get("adjustment_source")
    eff_date = bundle.get("effective_date")
    provenance = bundle.get("price_basis_provenance")
    limitations = bundle.get("limitations")

    if verified and basis in {"raw", "adjusted"}:
        return {
            "price_basis": basis,
            "price_basis_verified": True,
            "is_actionable": True,
            "volume_basis": vol_basis,
            "volume_basis_verified": vol_verified,
            "adjustment_source": str(adj_source) if adj_source else None,
            "effective_date": str(eff_date) if eff_date else None,
            "limitations": list(limitations) if isinstance(limitations, list) else [],
            "price_basis_provenance": dict(provenance) if isinstance(provenance, Mapping) else {},
        }
    return {
        "price_basis": "unknown",
        "price_basis_verified": False,
        "is_actionable": False,
        "volume_basis": vol_basis,
        "volume_basis_verified": vol_verified,
        "adjustment_source": None,
        "effective_date": None,
        "limitations": list(limitations) if isinstance(limitations, list) else [
            "OHLCV price basis is unverified or unknown; corporate actions may affect return, MA, and RS."
        ],
        "price_basis_provenance": (
            dict(bundle["price_basis_provenance"])
            if isinstance(bundle.get("price_basis_provenance"), Mapping)
            else {"source": "missing_or_unverified_bundle_price_basis"}
        ),
    }


def validate_context_basis_compatibility(
    context_a: Mapping[str, Any],
    context_b: Mapping[str, Any],
    *,
    strict: bool = True,
) -> dict[str, Any]:
    """Validate that two ticker context packages use compatible price bases before comparison."""
    price_a = (context_a.get("price_summary") or {}).get("price_basis", "unknown")
    price_b = (context_b.get("price_summary") or {}).get("price_basis", "unknown")

    str_a = str(price_a).strip().lower()
    str_b = str(price_b).strip().lower()

    if str_a == "unknown" or str_b == "unknown":
        return {
            "is_compatible": False,
            "reason": "unverified_or_unknown_basis",
            "price_basis_a": str_a,
            "price_basis_b": str_b,
        }

    if str_a != str_b:
        msg = f"Cannot compare mixed price bases: context A is {str_a!r}, context B is {str_b!r}."
        if strict:
            raise ValueError(msg)
        return {
            "is_compatible": False,
            "reason": "mixed_raw_and_adjusted_basis",
            "price_basis_a": str_a,
            "price_basis_b": str_b,
        }

    return {
        "is_compatible": True,
        "reason": "compatible_basis",
        "price_basis_a": str_a,
        "price_basis_b": str_b,
    }


def apply_bundle_price_basis_contract(
    context: dict[str, Any],
    bundle: Mapping[str, Any] | None = None,
    bundle_load_warning: str | None = None,
) -> dict[str, Any]:
    """Propagate price-basis provenance and warning into an existing ticker context.

    This is additive-only: it neither recomputes technical values nor changes scores.
    It accepts both Phase 1 bundles and older payloads without price-basis fields.
    """
    contract = normalize_price_basis_contract(bundle)
    price_summary = context.setdefault("price_summary", {})
    price_summary.update(contract)

    quality = context.setdefault("data_quality", {})
    basis_warning_codes = {PRICE_BASIS_UNVERIFIED_CODE, VOLUME_BASIS_UNVERIFIED_CODE}
    flags = [flag for flag in quality.get("flags", [])
             if not (isinstance(flag, Mapping) and flag.get("code") in basis_warning_codes)]
    warnings = list(quality.get("warnings", []))
    warnings = [warning for warning in warnings
                if "price basis is unverified" not in str(warning).lower()
                and "volume basis is unverified" not in str(warning).lower()]
    not_confirmed = list(quality.get("not_fully_confirmed", []))
    not_confirmed = [item for item in not_confirmed if item not in {"OHLCV price basis", "OHLCV volume basis"}]

    if not contract["price_basis_verified"]:
        flags.append({
            "scope": "pipeline", "ticker": context.get("ticker"), "code": PRICE_BASIS_UNVERIFIED_CODE,
            "severity": "warning", "metric": "price_basis", "evidence": contract,
            "message": "OHLCV price basis is unverified; corporate actions may affect return, MA, and RS.",
            "consumer_action": "Do not assume raw or adjusted prices; qualify OHLCV-derived conclusions.",
        })
        warnings.append("OHLCV price basis is unverified; corporate actions may affect return, MA, and RS.")
        not_confirmed.append("OHLCV price basis")
    if not contract["volume_basis_verified"]:
        flags.append({
            "scope": "pipeline", "ticker": context.get("ticker"), "code": VOLUME_BASIS_UNVERIFIED_CODE,
            "severity": "warning", "metric": "volume_basis", "evidence": contract,
            "message": "OHLCV volume basis is unverified; liquidity conclusions are unavailable.",
            "consumer_action": "Do not infer shares, lots, adjusted volume, or liquidity from unqualified volume values.",
        })
        warnings.append("OHLCV volume basis is unverified; liquidity conclusions are unavailable.")
        not_confirmed.append("OHLCV volume basis")
    if bundle_load_warning:
        warnings.append(f"analysis_bundle fallback: {bundle_load_warning}.")

    quality["flags"] = flags
    quality["warnings"] = sorted(set(warnings))
    quality["not_fully_confirmed"] = sorted(set(not_confirmed))
    context.setdefault("provenance", []).append({
        "source_file": "analysis_bundle.json", "source_dataset": "price_basis_contract",
        "source_keys": {"ticker": context.get("ticker")},
        "transformation": "Propagate Phase 1 price-basis contract without changing OHLCV-derived calculations.",
        "price_basis": contract["price_basis"], "price_basis_verified": contract["price_basis_verified"],
        "volume_basis": contract["volume_basis"], "volume_basis_verified": contract["volume_basis_verified"],
        "limitations": contract["limitations"],
    })
    return context


def corporate_intelligence_contract(
    bundle: Mapping[str, Any] | None,
    ticker: str,
    bundle_load_warning: str | None = None,
) -> dict[str, Any]:
    """Return one ticker's producer-owned Corporate Intelligence contract unchanged.

    The producer owns all field semantics, identities, snapshot dates, and provenance.
    This consumer only validates the outer envelope so an absent or malformed optional
    section is explicit instead of being reconstructed from other ticker data.
    """
    if bundle_load_warning:
        return {"status": "missing", "reason": bundle_load_warning, "sources": []}
    if not isinstance(bundle, Mapping):
        return {"status": "missing", "reason": "analysis_bundle_not_available", "sources": []}
    tickers = bundle.get("tickers")
    if not isinstance(tickers, Mapping):
        return {"status": "missing", "reason": "analysis_bundle_tickers_not_available", "sources": []}
    ticker_entry = tickers.get(ticker)
    if not isinstance(ticker_entry, Mapping):
        return {"status": "missing", "reason": "ticker_not_in_analysis_bundle", "sources": []}
    raw = ticker_entry.get("corporate_intelligence")
    if raw is None:
        return {"status": "missing", "reason": "corporate_intelligence_not_in_bundle", "sources": []}
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "reason": "corporate_intelligence_not_an_object", "sources": []}

    status = raw.get("status")
    if not isinstance(status, str) or status not in CORPORATE_INTELLIGENCE_STATUSES:
        return {
            "status": "malformed", "reason": "corporate_intelligence_status_invalid",
            "producer_status": status, "sources": [],
        }
    contract = copy.deepcopy(dict(raw))
    invalid_sections = [section for section in CORPORATE_INTELLIGENCE_SECTIONS
                        if not isinstance(contract.get(section), Mapping)]
    if invalid_sections:
        return {
            "status": "malformed", "reason": "corporate_intelligence_section_invalid",
            "producer_status": status, "invalid_sections": invalid_sections, "sources": [],
        }
    return contract



FRESHNESS_STATUSES = frozenset({"current", "expiring", "stale", "missing", "historical", "unknown"})
FRESHNESS_FIELDS = ("generated_at", "as_of_date", "source", "freshness_status", "expected_update_frequency", "stale_reason", "is_actionable")

def freshness_history_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
    """Pass through optional producer envelopes; legacy bundles remain explicit missing."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("freshness") if isinstance(entry, Mapping) else None
    if raw is None:
        return {"status": "missing", "reason": "freshness_not_in_legacy_bundle", "domains": {}}
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "reason": "freshness_not_an_object", "domains": {}}
    domains = {}
    for name, envelope in raw.items():
        if not isinstance(envelope, Mapping) or envelope.get("freshness_status") not in FRESHNESS_STATUSES:
            return {"status": "malformed", "reason": f"freshness_domain_invalid:{name}", "domains": {}}
        domains[name] = copy.deepcopy(dict(envelope))
    warnings = [f"{name}: {value.get('freshness_status')} ? {value.get('stale_reason')}" for name, value in domains.items() if value.get("freshness_status") in {"stale", "missing", "unknown"}]
    return {"status": "available", "domains": domains, "data_warnings": warnings, "unknowns": [name for name, value in domains.items() if not value.get("is_actionable")]}

def apply_bundle_freshness_history_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = freshness_history_contract(bundle, str(context.get("ticker") or ""))
    context["freshness_history"] = contract
    if contract["status"] == "available":
        context.setdefault("warnings", []).extend(contract["data_warnings"])
        context.setdefault("data_quality", {}).setdefault("warnings", []).extend(contract["data_warnings"])
    context.setdefault("provenance", []).append({"source_file": "analysis_bundle.json", "source_dataset": "freshness_history", "transformation": "Pass through producer freshness metadata; not a business fact.", "limitations": ["Freshness does not override completeness or actionability."]})
    return context


READINESS_STATES = frozenset({"ready", "degraded", "blocked", "unknown"})

def analysis_readiness_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
    """Pass through producer readiness without turning it into a business fact.

    Gated on exact-session INTEGRITY, not on market-basis qualification: readiness reports
    per-domain states the Producer already computed with the basis contract in hand, so
    suppressing all of them because prices are basis-unverified discards honest information
    about domains that never depended on a price. An unqualified basis instead forces
    `inferences_allowed` to False and adds an explicit warning, so nothing market-dependent
    can become actionable through this path."""
    integrity_ok, integrity_reason = _bundle_integrity_verified(bundle, ticker)
    if not integrity_ok:
        return {"status": "unknown", "reason": integrity_reason, "domains": {}, "inferences_allowed": False}
    trust = (bundle or {}).get("trusted_subset_validation") if isinstance(bundle, Mapping) else None
    basis_unqualified = isinstance(trust, Mapping) and trust.get("basis_state") == "unqualified"
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("analysis_readiness") if isinstance(entry, Mapping) else None
    if raw is None:
        return {"status": "unknown", "reason": "analysis_readiness_not_in_legacy_bundle", "domains": {}}
    if not isinstance(raw, Mapping) or not isinstance(raw.get("domains"), Mapping):
        return {"status": "unknown", "reason": "analysis_readiness_malformed", "domains": {}}
    domains = copy.deepcopy(dict(raw["domains"]))
    invalid = [name for name, value in domains.items() if not isinstance(value, Mapping) or value.get("state") not in READINESS_STATES or (value.get("state") == "ready" and value.get("is_actionable") is not True)]
    if invalid:
        return {"status": "unknown", "reason": "analysis_readiness_domain_invalid", "invalid_domains": invalid, "domains": {}}
    warnings = [f"analysis readiness {name}: {value.get('state')} ? {value.get('reason')}" for name, value in domains.items() if value.get("state") != "ready"]
    if basis_unqualified:
        warnings = warnings + ["analysis readiness: price/volume basis is unverified; no market-dependent inference is permitted."]
    return {"status": "available", "reference_at": raw.get("reference_at"), "domains": domains, "data_warnings": warnings, "unknowns": [name for name, value in domains.items() if value.get("state") in {"unknown", "blocked"}], "inferences_allowed": (not basis_unqualified) and all(value.get("state") == "ready" for value in domains.values())}

def apply_bundle_analysis_readiness_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    readiness = analysis_readiness_contract(bundle, str(context.get("ticker") or ""))
    context["analysis_readiness"] = readiness
    if readiness["status"] != "available" or not readiness["inferences_allowed"]:
        context.setdefault("data_quality", {}).setdefault("warnings", []).extend(readiness.get("data_warnings", []) or ["Analysis readiness is unknown; do not promote inferences."])
    context.setdefault("provenance", []).append({"source_file": "analysis_bundle.json", "source_dataset": "analysis_readiness", "transformation": "Pass through producer readiness; it is a data-quality gate, not a business fact.", "limitations": ["Inference cannot override non-ready or non-actionable domains."]})
    return context


def financial_canonical_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
    """Optional producer financial records; never reconstruct missing provenance."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("financial_canonical") if isinstance(entry, Mapping) else None
    if raw is None: return {"status": "missing", "reason": "financial_canonical_not_in_legacy_bundle", "records": [], "warnings": ["Canonical financial metrics are unavailable."]}
    if not isinstance(raw, Mapping) or not isinstance(raw.get("records"), list): return {"status": "malformed", "reason": "financial_canonical_malformed", "records": [], "warnings": ["Canonical financial metrics are malformed."]}
    allowed = {"available", "unknown", "unavailable", "incomparable"}
    valid = [record for record in raw["records"] if isinstance(record, Mapping) and record.get("quality_state") in allowed]
    if len(valid) != len(raw["records"]): return {"status": "malformed", "reason": "financial_canonical_record_invalid", "records": [], "warnings": ["Canonical financial metric record is invalid."]}
    warnings = [f"{r.get('canonical_metric')}: {r.get('reason')}" for r in valid if r.get("quality_state") != "available"]
    return {"status": raw.get("status", "available"), "records": copy.deepcopy(valid), "invalid_periods": copy.deepcopy(raw.get("invalid_periods", [])), "warnings": warnings, "unknowns": [r.get("canonical_metric") for r in valid if r.get("quality_state") in {"unknown", "unavailable", "incomparable"}]}

def apply_bundle_financial_canonical_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    canonical = financial_canonical_contract(bundle, str(context.get("ticker") or ""))
    context["financial_canonical"] = canonical
    context.setdefault("data_quality", {}).setdefault("warnings", []).extend(canonical["warnings"])
    context.setdefault("provenance", []).append({"source_file": "analysis_bundle.json", "source_dataset": "financial_canonical", "transformation": "Pass through canonical financial metric provenance; do not present unavailable, derived, or incomparable values as facts.", "limitations": ["Publication time, scope, and restatement may be unknown."]})
    return context


def fundamental_quality_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
    entry=((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle,Mapping) else None
    raw=entry.get("fundamental_quality") if isinstance(entry,Mapping) else None
    if not isinstance(raw,Mapping) or not isinstance(raw.get("models"),Mapping): return {"status":"unknown","reason":"fundamental_quality_not_in_legacy_bundle","models":{},"warnings":["Fundamental quality is unavailable."]}
    models=copy.deepcopy(dict(raw["models"])); bad=[n for n,m in models.items() if not isinstance(m,Mapping) or m.get("result_state") not in {"available","partial","unavailable","inapplicable","incomparable","unknown"}]
    if bad:return {"status":"unknown","reason":"fundamental_quality_malformed","models":{},"warnings":["Fundamental quality is malformed."]}
    return {"status":"available","models":models,"warnings":[f"{n}: {m.get('result_state')}" for n,m in models.items() if m.get('result_state')!='available'],"unknowns":[n for n,m in models.items() if m.get('result_state')!='available']}
def apply_bundle_fundamental_quality_contract(context:dict[str,Any],bundle:Mapping[str,Any]|None)->dict[str,Any]:
    value=fundamental_quality_contract(bundle,str(context.get("ticker") or ""));context["fundamental_quality"]=value;context.setdefault("data_quality",{}).setdefault("warnings",[]).extend(value["warnings"]);context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"fundamental_quality","transformation":"Pass through producer model output; score interpretation is inference, not fact.","limitations":["No Consumer-side recomputation."]});return context

RELATIVE_VALUATION_STATES = frozenset({"available", "unavailable", "inapplicable", "incomparable", "malformed"})

INTRINSIC_VALUATION_STATES = frozenset({"available", "unavailable", "inapplicable", "incomparable", "malformed"})

def risk_analysis_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
 entry=((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle,Mapping) else None;raw=entry.get("risk_analysis") if isinstance(entry,Mapping) else None
 if not isinstance(raw,Mapping):return {"status":"unknown","reason":"risk_analysis_not_in_legacy_bundle"}
 return copy.deepcopy(dict(raw))
def apply_bundle_risk_analysis_contract(context:dict[str,Any],bundle:Mapping[str,Any]|None)->dict[str,Any]:
 value=risk_analysis_contract(bundle,str(context.get("ticker") or ""));context["risk_analysis"]=value;context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"risk_analysis","transformation":"Pass through producer risk metrics without recomputation.","limitations":["No position recommendation or expectancy."]});return context

def opportunity_ranking_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
    """Pass through the full Producer opportunity_ranking dict verbatim.

    The Producer contract includes schema_version, ticker, entity_type, state,
    ranking_key and other fields beyond the legacy dimensions subset. All must be
    preserved without reduction, renaming, or re-validation.
    Missing or malformed input fails closed without corrupting unrelated context.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("opportunity_ranking") if isinstance(entry, Mapping) else None
    if raw is None:
        return {"status": "unknown", "reason": "opportunity_ranking_not_in_bundle", "dimensions": {},
                "data_warnings": ["Opportunity ranking is unavailable."]}
    if not isinstance(raw, Mapping):
        return {"status": "unknown", "reason": "opportunity_ranking_malformed", "dimensions": {},
                "data_warnings": ["Opportunity ranking is malformed."]}
    # Pass through the complete Producer dict verbatim, without field selection or renaming.
    return copy.deepcopy(dict(raw))

def apply_bundle_opportunity_ranking_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    value = opportunity_ranking_contract(bundle, str(context.get("ticker") or ""))
    context["opportunity_ranking"] = value
    context.setdefault("data_quality", {}).setdefault("warnings", []).extend(value.get("data_warnings", []))
    context.setdefault("provenance", []).append({
        "source_file": "analysis_bundle.json", "source_dataset": "opportunity_ranking",
        "transformation": "Pass through producer opportunity_ranking contract verbatim without recomputation.",
        "limitations": ["No recommendation, probability, target price, or portfolio sizing."],
    })
    return context

def scenario_analysis_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
 entry=((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle,Mapping) else None; raw=entry.get("scenario_analysis") if isinstance(entry,Mapping) else None
 if not isinstance(raw,Mapping) or not isinstance(raw.get("scenarios"),Mapping):return {"status":"unknown","reason":"scenario_analysis_not_in_legacy_or_malformed_bundle","scenarios":{},"warnings":["Scenario evidence is unavailable."]}
 scenarios=copy.deepcopy(dict(raw["scenarios"]));allowed={"available","limited","unknown","blocked","partial","incomparable"}
 if any(not isinstance(v,Mapping) or v.get("state") not in allowed for v in scenarios.values()):return {"status":"unknown","reason":"scenario_analysis_invalid","scenarios":{},"warnings":["Scenario evidence is malformed."]}
 return {"status":raw.get("state","unknown"),"scenarios":scenarios,"facts":copy.deepcopy((raw.get("evidence_inventory") or {}).get("facts",[])),"data_warnings":copy.deepcopy(raw.get("data_warnings",[])),"unknowns":copy.deepcopy(raw.get("unknowns",[])),"inferences":copy.deepcopy((raw.get("evidence_inventory") or {}).get("inferences",[])),"hypotheses":copy.deepcopy((raw.get("evidence_inventory") or {}).get("hypotheses",[]))}
def apply_bundle_scenario_analysis_contract(context:dict[str,Any],bundle:Mapping[str,Any]|None)->dict[str,Any]:
 value=scenario_analysis_contract(bundle,str(context.get("ticker") or ""));context["scenario_analysis"]=value;context.setdefault("data_quality",{}).setdefault("warnings",[]).extend(value.get("data_warnings",value.get("warnings",[])));context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"scenario_analysis","transformation":"Pass through structured producer scenario evidence without recomputation.","limitations":["No recommendation, probability, or target price."]});return context
def intrinsic_valuation_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
 entry=((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle,Mapping) else None; raw=entry.get("intrinsic_valuation") if isinstance(entry,Mapping) else None
 if not isinstance(raw,Mapping) or not isinstance(raw.get("methods"),Mapping):return {"status":"unknown","reason":"intrinsic_valuation_not_in_legacy_or_malformed_bundle","methods":{},"warnings":["Intrinsic valuation is unavailable."]}
 methods=copy.deepcopy(dict(raw["methods"]));bad=[n for n,m in methods.items() if not isinstance(m,Mapping) or m.get("state") not in INTRINSIC_VALUATION_STATES]
 if bad:return {"status":"unknown","reason":"intrinsic_valuation_method_invalid","methods":{},"warnings":["Intrinsic valuation is malformed."]}
 return {"status":raw.get("status","unknown"),"methods":methods,"data_warnings":[f"intrinsic valuation {n}: {m.get('state')}" for n,m in methods.items() if m.get("state")!="available"],"inferences":["Scenario interpretation and margin of safety are inferences; no target price or recommendation is generated."]}
def apply_bundle_intrinsic_valuation_contract(context:dict[str,Any],bundle:Mapping[str,Any]|None)->dict[str,Any]:
 value=intrinsic_valuation_contract(bundle,str(context.get("ticker") or ""));context["intrinsic_valuation"]=value;context.setdefault("data_quality",{}).setdefault("warnings",[]).extend(value.get("data_warnings",value.get("warnings",[])));context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"intrinsic_valuation","transformation":"Pass through producer valuation without recomputation.","limitations":["No target price or recommendation."]});return context

def relative_valuation_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any]:
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("relative_valuation") if isinstance(entry, Mapping) else None
    if raw is None:
        return {"status": "unknown", "reason": "relative_valuation_not_in_legacy_bundle", "methods": {}, "warnings": ["Relative valuation is unavailable."]}
    if not isinstance(raw, Mapping) or not isinstance(raw.get("methods"), Mapping):
        return {"status": "unknown", "reason": "relative_valuation_malformed", "methods": {}, "warnings": ["Relative valuation is malformed."]}
    methods = copy.deepcopy(dict(raw["methods"]))
    bad = [name for name, method in methods.items() if not isinstance(method, Mapping) or method.get("state") not in RELATIVE_VALUATION_STATES or (method.get("is_actionable") is True and method.get("state") != "available")]
    if bad:
        return {"status": "unknown", "reason": "relative_valuation_method_invalid", "invalid_methods": bad, "methods": {}, "warnings": ["Relative valuation is malformed."]}
    warnings = [f"relative valuation {name}: {method.get('state')}" for name, method in methods.items() if method.get("state") != "available" or not method.get("is_actionable")]
    return {"status": raw.get("status", "unknown"), "methods": methods, "data_warnings": warnings,
            "unknowns": [name for name, method in methods.items() if method.get("state") != "available"],
            "inferences": ["Relative cheap/expensive assessments and comparisons remain inferences; no target price or recommendation is generated."]}

def apply_bundle_relative_valuation_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    value = relative_valuation_contract(bundle, str(context.get("ticker") or ""))
    context["relative_valuation"] = value
    context.setdefault("data_quality", {}).setdefault("warnings", []).extend(value.get("data_warnings", value.get("warnings", [])))
    context.setdefault("provenance", []).append({"source_file": "analysis_bundle.json", "source_dataset": "relative_valuation", "transformation": "Pass through producer valuation observations without Consumer-side recomputation.", "limitations": ["No target price, recommendation, or cheap/expensive conclusion is a fact."]})
    return context

def apply_bundle_corporate_intelligence_contract(
    context: dict[str, Any],
    bundle: Mapping[str, Any] | None = None,
    bundle_load_warning: str | None = None,
) -> dict[str, Any]:
    """Attach the source-scoped producer contract without merging or deriving fields."""
    contract = corporate_intelligence_contract(bundle, str(context.get("ticker") or ""), bundle_load_warning)
    context["corporate_intelligence"] = contract
    context.setdefault("provenance", []).append({
        "source_file": "analysis_bundle.json", "source_dataset": "corporate_intelligence",
        "source_keys": {"ticker": context.get("ticker")},
        "transformation": "Pass through producer-owned, source-scoped corporate snapshots without canonicalization.",
        "corporate_intelligence_status": contract["status"],
        "limitations": ([] if contract["status"] == "available"
                        else ["Corporate Intelligence is not fully available; do not infer missing or incomparable values."]),
    })
    return context


def financial_period_coverage_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("financial_period_coverage") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"coverage_status": "malformed", "limitations": ["Financial period coverage contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))

def apply_bundle_financial_period_coverage_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = financial_period_coverage_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["financial_period_coverage"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "financial_period_coverage",
            "transformation": "Pass through producer per-ticker financial period coverage contract.",
            "limitations": contract.get("limitations", []),
        })
    return context

def valuation_namespaces_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("valuation_namespaces") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "reasons": ["Valuation namespaces contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))

def apply_bundle_valuation_namespaces_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = valuation_namespaces_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["valuation_namespaces"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "valuation_namespaces",
            "transformation": "Pass through producer valuation namespaces contract.",
            "limitations": ["Live-vendor and historical-calculated valuation metrics are not interchangeable."],
        })
    return context

def share_basis_identities_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("share_basis_identities") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "reasons": ["Share basis identities contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))

def apply_bundle_share_basis_identities_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = share_basis_identities_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["share_basis_identities"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "share_basis_identities",
            "transformation": "Pass through producer share basis identities contract.",
            "limitations": ["Share counts from different dates or basis types must not be treated as interchangeable."],
        })
    return context

def earnings_anomaly_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("earnings_anomaly") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["Earnings anomaly contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))

def apply_bundle_earnings_anomaly_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = earnings_anomaly_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["earnings_anomaly"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "earnings_anomaly",
            "transformation": "Pass through producer earnings anomaly semantic contract.",
            "limitations": contract.get("limitations", []),
        })
    return context

def ta_signal_semantics_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("ta_signal_semantics") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["TA signal semantics contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))

def apply_bundle_ta_signal_semantics_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = ta_signal_semantics_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["ta_signal_semantics"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "ta_signal_semantics",
            "transformation": "Pass through producer technical signal semantics contract.",
            "limitations": contract.get("limitations", []),
        })
    return context

def news_window_semantics_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the Producer news_window_semantics nested under news_related verbatim.

    The Producer stores news_window_semantics at:
        tickers[ticker].news_related.news_window_semantics
    not at the top-level ticker entry. Missing semantics remain missing.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    news_rel = entry.get("news_related") if isinstance(entry, Mapping) else None
    if not isinstance(news_rel, Mapping):
        return None
    raw = news_rel.get("news_window_semantics")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["News window semantics contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))

def news_related_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the full Producer news_related dict verbatim, including nested news_window_semantics.

    Preserves all raw news_related fields (counts, items, metadata) and the
    nested news_window_semantics sub-contract without modification.
    Missing input remains missing; malformed input fails closed locally.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("news_related") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return None
    return copy.deepcopy(dict(raw))

def apply_bundle_news_window_semantics_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Apply news_related pass-through (including nested news_window_semantics) to context.

    Sets context['news_related'] to the full Producer news_related dict verbatim.
    Also sets context['news_window_semantics'] as a top-level compatibility alias
    when present, without replacing or reducing the canonical nested contract.
    """
    ticker = str(context.get("ticker") or "")
    news_rel = news_related_contract(bundle, ticker)
    if news_rel is not None:
        context["news_related"] = news_rel
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "news_related",
            "transformation": "Pass through producer news_related contract verbatim including nested news_window_semantics.",
            "limitations": [],
        })
        # Top-level alias for news_window_semantics — canonical value is news_related.news_window_semantics.
        nws = news_rel.get("news_window_semantics")
        if isinstance(nws, Mapping):
            context["news_window_semantics"] = nws
    return context

def risk_semantics_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Read risk_semantics from its canonical Producer location -- nested at
    tickers[ticker].analysis_score.risk_semantics, matching where
    build_analysis_score_contract() in export_ai_bundle.py actually places it -- with a
    legacy top-level tickers[ticker].risk_semantics used only as a fallback when the
    canonical nested value is absent. The canonical value always takes precedence over a
    conflicting legacy value. Neither entry nor entry['analysis_score'] is mutated; the
    full matched dict is passed through verbatim (no field selection)."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    if not isinstance(entry, Mapping):
        return None
    analysis_score = entry.get("analysis_score")
    canonical_raw = analysis_score.get("risk_semantics") if isinstance(analysis_score, Mapping) else None
    raw = canonical_raw if canonical_raw is not None else entry.get("risk_semantics")
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["Risk semantics contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))

def apply_bundle_risk_semantics_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = risk_semantics_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["risk_semantics"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "risk_semantics",
            "transformation": "Pass through producer risk semantics contract.",
            "limitations": contract.get("limitations", []),
        })
    return context


def analysis_lane_eligibility_contract(bundle: Mapping[str, Any] | None, ticker: str) -> list[Any] | dict[str, Any] | None:
    """Pass through the optional Phase 4B/4C analysis-lane eligibility result verbatim.

    Canonical location: tickers[ticker].analysis_lane_eligibility -- the exact list
    stock-core-private/analysis_lane_eligibility.py::evaluate_ticker_lanes() returns (one
    dict per lane: lane, status, eligible, blocking_reasons, data_warnings,
    required_evidence, supporting_paths, limitations, is_actionable). No Producer
    milestone wires this into analysis_bundle.json yet, so this is legacy-compatible by
    construction: absent in every current bundle, and simply returns None until it exists.
    This function never recalculates eligibility, ranks lanes/tickers, suppresses
    blocked_avoid, or adds a score -- it is a byte-identical pass-through, same as every
    other contract in this module. Missing input remains missing; malformed input fails
    closed locally without touching any other context field."""
    integrity_ok, integrity_reason = _bundle_integrity_verified(bundle, ticker)
    if not integrity_ok:
        return {"status": "untrusted", "limitations": [integrity_reason], "is_actionable": False}
    # Basis qualification is NOT gated here: evaluate_ticker_lanes() already blocks the
    # adjusted-return, liquidity and backtest claims on an unverified basis, per lane, with
    # its own reasons. Re-suppressing the whole result would hide the lanes it correctly
    # allows (which never touch a price) behind a market-data limitation.
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("analysis_lane_eligibility") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, list):
        return {"status": "malformed", "limitations": ["Analysis lane eligibility contract is malformed."], "is_actionable": False}
    return copy.deepcopy(list(raw))


def apply_bundle_analysis_lane_eligibility_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = analysis_lane_eligibility_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["analysis_lane_eligibility"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "analysis_lane_eligibility",
            "transformation": "Pass through producer analysis lane eligibility result verbatim; Consumer does not recalculate, rank, or interpret lane results.",
            "limitations": ["Optional field; absent until a future Producer milestone wires lane evaluation into analysis_bundle.json."],
        })
    return context


def distribution_evidence_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional Phase 5D distribution_evidence contract verbatim.

    Canonical location: tickers[ticker].distribution_evidence -- the exact dict
    stock-core-private/distribution_evidence.py::build_distribution_evidence_for_ticker()
    returns (schema_version, ticker, coverage_status, cash_distributions,
    non_cash_distributions, latest_cash_distribution, qualified_cash_event_count,
    covered_periods, history_status, blocking_reasons, limitations, provenance,
    is_actionable). No default Producer invocation attaches this yet (opt-in only, same
    flag as analysis_lane_eligibility), so this is legacy-compatible by construction:
    absent in every current bundle, and simply returns None until it exists. This
    function never recalculates coverage, derives yield/payout ratio/CAGR/return, or
    reclassifies cash vs non-cash -- it is a byte-identical pass-through, same as every
    other contract in this module. Missing input remains missing; malformed input fails
    closed locally without touching any other context field."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("distribution_evidence") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["Distribution evidence contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))


def apply_bundle_distribution_evidence_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = distribution_evidence_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["distribution_evidence"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "distribution_evidence",
            "transformation": "Pass through producer distribution evidence contract verbatim; Consumer does not recalculate coverage, derive yield/payout ratio/CAGR/return, or reclassify cash vs non-cash events.",
            "limitations": ["Optional field; absent until a future Producer milestone wires distribution evidence into analysis_bundle.json by default."],
        })
    return context


def foreign_flow_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional DNSE foreign_flow contract verbatim.

    Canonical location: tickers[ticker].foreign_flow -- the exact dict
    stock-core-private/dnse_foreign_flow_store.py::build_series() returns
    (schema_version, ticker, status, source, source_contract_version, source_scope,
    point_in_time_status, latest_session, observations, qualified_session_count,
    cumulative_net_value_vnd, cumulative_window, positive/negative/neutral_session_count,
    current_consecutive_net_buy/sell_sessions, window_summaries, freshness, warnings,
    limitations, is_actionable). The field stays opt-in at the Producer builder level
    (export_ai_bundle.py/operate_stocklookup.py default it off, independently testable
    either way) but the authoritative production release profile
    (release_orchestrator.py's --generate step) now opts it in for a real release --
    still legacy-compatible either way: absent in a bundle where it was not requested,
    and this function simply returns None until it exists. This function never
    recomputes a net value, never derives an ownership/free-float percentage, never
    computes a flow/trading-value ratio, and never reads or fabricates foreign volume or
    foreign room (the Producer contract never includes them here at all) -- it is a
    byte-identical pass-through, same as every other contract in this module. Missing
    input remains missing; malformed input fails closed locally without touching any
    other context field."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("foreign_flow") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["Foreign-flow contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))


def apply_bundle_foreign_flow_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = foreign_flow_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["foreign_flow"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "foreign_flow",
            "transformation": "Pass through the Producer's qualified DNSE foreign-investor VALUE contract verbatim (foreign_buy_value_vnd/foreign_sell_value_vnd/foreign_net_value_vnd per session, plus fail-closed multi-session window summaries). Consumer does not recompute a net value, derive an ownership/free-float percentage, or compute a flow/trading-value ratio.",
            "limitations": [
                "Opt-in field, wired into the authoritative production release profile but still absent from any bundle that did not request it (e.g. a manually-run export without the flag).",
                "Currently retained for HPG, VNM, QNS only; other tickers report status=\"missing\", never a fabricated value.",
                "Foreign volume and foreign room are not represented in this contract at all -- both remain unqualified by the Producer's own DNSE capability contracts.",
                "freshness compares the latest retained session against the release's own exact reference session in real trading sessions, not calendar days; a stale verdict is reported, never silently upgraded to current.",
            ],
        })
    return context


def current_state_market_risk_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional current_state_market_risk contract verbatim.

    Canonical location: tickers[ticker].current_state_market_risk -- the exact
    dict stock-core-private/dnse_current_state_market_risk.py's
    compute_current_state_beta_correlation() returns, plus the bundle-level
    "status" field export_ai_bundle.py's attach layer adds (available /
    not_qualified). Descriptive current-state (never point-in-time) HPG vs
    VNINDEX beta/correlation: pit_backtest_eligible is always False,
    is_actionable is always False, and sample_adequacy distinguishes
    MATHEMATICALLY_COMPUTABLE from an unaddressed "statistically strong" bar
    that this contract never claims. Distinct from the pre-existing
    tickers[ticker].risk_analysis.market_risk (risk_liquidity.py's
    point-in-time-labelled section, passed through separately by
    apply_bundle_risk_analysis_contract) -- this function never reads that
    field and never merges the two. The field stays opt-in at the Producer
    builder level (export_ai_bundle.py defaults it off), so this is
    legacy-compatible by construction: absent in every bundle that did not
    request it, and this function simply returns None until it exists. This
    function never recomputes a beta or correlation value, never derives a
    risk score or recommendation, and never asserts statistical strength for
    a short observation window -- it is a byte-identical pass-through, same
    as every other contract in this module. Missing input remains missing;
    malformed input fails closed locally without touching any other context
    field."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_state_market_risk") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "warnings": ["current_state_market_risk contract is malformed."],
                "pit_backtest_eligible": False, "is_actionable": False}
    return copy.deepcopy(dict(raw))


def apply_bundle_current_state_market_risk_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_state_market_risk_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_state_market_risk"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_state_market_risk",
            "transformation": "Pass through the Producer's current-state (never point-in-time) HPG-vs-VNINDEX beta/correlation contract verbatim. Consumer does not recompute beta, correlation, or any statistic, and never upgrades a short-window result to a statistically-strong claim.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-state-market-risk).",
                "Currently qualified for HPG only; every other ticker reports status=\"not_qualified\", never a fabricated beta/correlation.",
                "Descriptive current-state statistic only -- not a recommendation, not a risk score, and not evidence of causation.",
                "pit_backtest_eligible and is_actionable are always false; this is not point-in-time backtest evidence.",
            ],
        })
    return context


def current_state_price_analytics_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional current_state_price_analytics contract verbatim.

    Canonical location: tickers[ticker].current_state_price_analytics -- the exact
    dict stock-core-private/dnse_current_state_price_analytics.py returns.
    Descriptive current-state (never point-in-time) price analytics:
    pit_backtest_eligible is always False, is_actionable is always False.
    Distinct from current_state_market_risk and risk_analysis -- this function
    never reads those fields and never merges them. Absent input returns None;
    malformed input fails closed locally without touching any other context field.
    Consumer does NOT recompute returns, volatility, drawdown, RSI, SMA, or any statistic.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_state_price_analytics") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {
            "status": "malformed",
            "warnings": ["current_state_price_analytics contract is malformed."],
            "pit_backtest_eligible": False,
            "is_actionable": False,
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_current_state_price_analytics_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_state_price_analytics_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_state_price_analytics"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_state_price_analytics",
            "transformation": "Pass through the Producer's current-state (never point-in-time) price analytics contract verbatim. Consumer does not recompute returns, volatility, drawdown, RSI, SMA, or any statistic.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it.",
                "Currently qualified for HPG only; every other ticker reports status=\"not_qualified\", never a fabricated statistic.",
                "Descriptive current-state price analytics only -- not a recommendation, not a risk score, and not evidence of causation.",
                "pit_backtest_eligible and is_actionable are always false; this is not point-in-time backtest evidence.",
            ],
        })
    return context


def current_state_relative_valuation_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional current_state_relative_valuation contract verbatim.

    Canonical location: tickers[ticker].current_state_relative_valuation -- the exact
    dict stock-core-private/current_state_relative_valuation.py's
    evaluate_current_state_relative_valuation() returns, plus the bundle-level "status"
    field export_ai_bundle.py's attach layer adds (available / not_qualified). Current
    market cap/P-E/P-B/P-S/EV/EV-Sales/EV-EBITDA from the qualified DNSE current-state
    price times official-evidence current shares outstanding, against already-qualified
    historical financial denominators -- every method explicitly carries
    as_of_semantics="current_market_price_on_qualified_historical_fundamentals", never
    "TTM"/"forward"/"current earnings", and is_actionable is always False. Distinct from
    the pre-existing tickers[ticker].relative_valuation (historical point-in-time
    multiples, passed through separately by apply_bundle_relative_valuation_contract)
    and from tickers[ticker].ticker_capability_matrix.market_actionable.current_valuation
    (an unrelated, market-wide generic capability-status slot) -- this function never
    reads either and never merges them. The field stays opt-in at the Producer builder
    level (export_ai_bundle.py defaults it off), so this is legacy-compatible by
    construction: absent in every bundle that did not request it, and this function
    simply returns None until it exists. This function never recomputes a price, a
    share count, or a multiple, and never converts a comparability verdict into a
    cheap/expensive, buy/sell, or target-price conclusion -- it is a byte-identical
    pass-through, same as every other contract in this module. Missing input remains
    missing; malformed input fails closed locally without touching any other context
    field."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_state_relative_valuation") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    structurally_valid = (
        isinstance(raw, Mapping) and raw.get("ticker") == ticker and raw.get("is_actionable") is False
        and isinstance(raw.get("methods"), Mapping)
        and all(
            isinstance(method, Mapping) and method.get("is_actionable") is False
            for method in raw["methods"].values()
        )
    )
    if not structurally_valid:
        return {
            "status": "malformed",
            "warnings": ["current_state_relative_valuation contract is malformed."],
            "is_actionable": False,
            "methods": {},
            "historical_comparison": {"status": "incomparable", "reasons": ["malformed_producer_contract"], "comparisons": {}},
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_current_state_relative_valuation_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_state_relative_valuation_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_state_relative_valuation"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_state_relative_valuation",
            "transformation": "Pass through the Producer's current-state relative valuation contract verbatim (current market cap/P-E/P-B/P-S/EV/EV-Sales/EV-EBITDA from a qualified current price times official-evidence current shares, against qualified historical financial denominators). Consumer does not recompute a price, a share count, a multiple, or a comparability verdict.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-state-relative-valuation).",
                "Every method mixes a current market price with an older qualified financial period; none of them is a TTM, forward, or current-earnings valuation.",
                "A metric with state != \"available\" carries no numeric value; an unqualified current-share or current-price leg blocks every method, never a partial/fabricated one.",
                "historical_comparison is \"comparable\" only when the Producer explicitly marks both sides compatible; otherwise it is \"incomparable\" with reasons, never inferred as a change.",
                "is_actionable is always false; no target price, recommendation, or cheap/expensive conclusion is produced by this contract.",
            ],
        })
    return context


def fundamental_quality_evidence_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional Phase 6A fundamental_quality_evidence contract verbatim.

    Canonical location: tickers[ticker].fundamental_quality_evidence -- the exact dict
    stock-core-private/fundamental_quality_evidence.py::build_fundamental_quality_evidence_for_ticker()
    returns (schema_version, ticker, model, model_version, status, applicability,
    reporting_period, statement_scope, inputs, metrics, data_warnings, blocking_reasons,
    limitations, provenance, is_actionable). Distinct from the separate, always-present
    legacy tickers[ticker].fundamental_quality field (a different, multi-model shape) --
    this function never reads that field and never merges the two. No default Producer
    invocation attaches this yet (opt-in only), so this is legacy-compatible by
    construction: absent in every current bundle, and simply returns None until it exists.
    This function never recalculates a metric, derives yield/payout ratio/CAGR/return,
    ranks, scores, or rates -- it is a byte-identical pass-through, same as every other
    contract in this module. Missing input remains missing; malformed input fails closed
    locally without touching any other context field."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("fundamental_quality_evidence") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["Fundamental quality evidence contract is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))


def apply_bundle_fundamental_quality_evidence_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = fundamental_quality_evidence_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["fundamental_quality_evidence"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "fundamental_quality_evidence",
            "transformation": "Pass through producer fundamental quality evidence contract verbatim; Consumer does not recalculate metrics, derive yield/payout ratio/CAGR/return, or rank/score/rate the ticker.",
            "limitations": ["Optional field; absent until a future Producer milestone wires fundamental quality evidence into analysis_bundle.json by default."],
        })
    return context


def canonical_financial_facts_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional P1F canonical_financial_facts section verbatim.

    Canonical location: tickers[ticker].canonical_financial_facts -- the exact dict
    canonical_financial_bundle_section.py attaches from the layer 3 fact store.
    Distinct from legacy tickers[ticker].financial_canonical. Does not recalculate,
    derive, rank, or score. Malformed sections fail closed.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("canonical_financial_facts") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping):
        return {"status": "malformed", "limitations": ["Canonical financial facts section is malformed."], "is_actionable": False}
    status = raw.get("section_status") or raw.get("status")
    if isinstance(status, str) and status.lower() in ("malformed", "corrupt", "invalid"):
        return {"status": "malformed", "limitations": ["Canonical financial facts status is malformed."], "is_actionable": False}
    return copy.deepcopy(dict(raw))


def apply_bundle_canonical_financial_facts_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = canonical_financial_facts_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["canonical_financial_facts"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "canonical_financial_facts",
            "transformation": "Pass through producer canonical financial facts contract verbatim; Consumer does not recalculate metrics, derive yield/payout ratio/CAGR/return, or rank/score/rate the ticker.",
            "limitations": ["P1F opt-in canonical financial facts section from market-wide layer 3 store."],
        })
    return context


def apply_bundle_historical_capital_structure_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    entry = ((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle, Mapping) else None
    raw = entry.get("historical_capital_structure") if isinstance(entry, Mapping) else None
    if raw is not None:
        context["historical_capital_structure"] = copy.deepcopy(dict(raw)) if isinstance(raw, Mapping) else {
            "status": "malformed", "historical_only": True, "market_dependent": False, "is_actionable": False,
            "blocking_reasons": ["historical_capital_structure_malformed"],
        }
    return context


def apply_bundle_historical_fundamental_brief_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    entry = ((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle, Mapping) else None
    raw = entry.get("historical_fundamental_brief") if isinstance(entry, Mapping) else None
    required_categories = {"facts", "data_warnings", "supported_inferences", "hypotheses", "missing_evidence", "invalidation_conditions"}
    required_warnings = {"price_basis_unknown_or_unverified", "volume_basis_unknown_or_unverified", "current_shares_unqualified"}
    valid = isinstance(raw, Mapping) and required_categories <= set(raw) and raw.get("historical_only") is True
    valid = valid and isinstance(raw.get("data_warnings"), list) and required_warnings <= set(raw["data_warnings"])
    if raw is not None:
        context["historical_fundamental_brief"] = copy.deepcopy(dict(raw)) if valid else {
            "status": "malformed", "historical_only": True, "market_dependent": False, "is_actionable": False,
            "data_warnings": ["historical_fundamental_brief_malformed"],
        }
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "historical_fundamental_brief",
            "transformation": "Pass through the qualified FY2024 historical brief verbatim; Consumer does not recompute metrics, merge facts with inferences, or create interpretation.",
            "limitations": ["Historical-only; does not establish current-market trust, valuation, ranking, recommendation, sizing, adjusted-return, or backtest readiness."],
        })
    return context


def apply_bundle_historical_decision_analysis_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Pass through the Phase 4B Producer result without recomputation or interpretation."""
    entry = ((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle, Mapping) else None
    raw = entry.get("historical_decision_analysis") if isinstance(entry, Mapping) else None
    required = {"schema_version", "ticker", "analysis_mode", "eligibility", "quality_assessment", "risks",
                "catalysts", "scenarios", "invalidation_conditions", "historical_conclusion", "historical_only",
                "market_dependent", "is_actionable"}
    valid = (isinstance(raw, Mapping) and required <= set(raw) and raw.get("ticker") == context.get("ticker")
             and raw.get("analysis_mode") == "historical_only_qualified_data"
             and raw.get("historical_only") is True and raw.get("market_dependent") is False
             and raw.get("is_actionable") is False and isinstance(raw.get("eligibility"), Mapping)
             and raw["eligibility"].get("status") in {"eligible", "partially_eligible", "insufficient_evidence", "blocked"}
             and isinstance(raw.get("scenarios"), Mapping) and set(raw["scenarios"]) == {"bear", "base", "bull"})
    if raw is not None:
        context["historical_decision_analysis"] = copy.deepcopy(dict(raw)) if valid else {
            "status": "malformed", "historical_only": True, "market_dependent": False, "is_actionable": False,
            "reason_codes": ["historical_decision_analysis_malformed"],
        }
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "historical_decision_analysis",
            "transformation": "Pass through the Producer historical decision analysis verbatim; Consumer does not recompute quality, risks, catalysts, scenarios, eligibility, or conclusion.",
            "limitations": ["Historical-only qualified-data contract; no target price, valuation, recommendation, ranking, or portfolio sizing."],
        })
    return context

def apply_bundle_portfolio_risk_analysis_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    entry=((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle,Mapping) else None
    raw=entry.get("portfolio_risk_analysis") if isinstance(entry,Mapping) else None
    required={"schema_version","ticker","analysis_mode","fundamental_risk","liquidity","portfolio_considerations","allocation_eligibility","historical_only","market_dependent","is_actionable"}
    valid=isinstance(raw,Mapping) and required <= set(raw) and raw.get("ticker")==context.get("ticker") and raw.get("analysis_mode")=="historical_only_qualified_data" and raw.get("historical_only") is True and raw.get("market_dependent") is False and raw.get("is_actionable") is False
    if raw is not None:
        context["portfolio_risk_analysis"]=copy.deepcopy(dict(raw)) if valid else {"status":"malformed","historical_only":True,"market_dependent":False,"is_actionable":False,"reason_codes":["portfolio_risk_analysis_malformed"]}
        context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"portfolio_risk_analysis","transformation":"Pass through Producer risk, liquidity, portfolio-consideration, and allocation gates without recomputation.","limitations":["No portfolio allocation, sizing, recommendation, or current-market claim."]})
    return context

def apply_bundle_qualified_research_brief_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    entry=((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle,Mapping) else None;raw=entry.get("qualified_research_brief") if isinstance(entry,Mapping) else None
    if raw is not None:
        valid=isinstance(raw,Mapping) and raw.get("ticker")==context.get("ticker") and raw.get("historical_only") is True and raw.get("is_actionable") is False and raw.get("analysis_mode")=="historical_only_qualified_data"
        context["qualified_research_brief"]=copy.deepcopy(dict(raw)) if valid else {"status":"malformed","is_actionable":False,"reason_codes":["qualified_research_brief_malformed"]}
        context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"qualified_research_brief","transformation":"Verbatim Producer brief; Consumer performs no analysis recomputation.","limitations":["Historical-only; no recommendation, valuation, ranking, sizing, or allocation."]})
    return context


QUALIFIED_RESEARCH_SNAPSHOT_V2_SCHEMA_VERSIONS = frozenset({"2.0.0", "2.1.0"})


def qualified_research_snapshot_v2_contract(bundle: Mapping[str, Any] | None) -> dict[str, Any] | None:
    """Return the Producer-owned universe snapshot without recomputing any verdict.

    This is a bundle-level contract rather than a per-ticker calculation.  Every Consumer
    context therefore retains the exact same ordered snapshot, identity, and statuses so a
    downstream reader cannot mistake a filtered per-ticker projection for the source record.
    """
    raw = (bundle or {}).get("qualified_research_snapshot_v2") if isinstance(bundle, Mapping) else None
    if raw is None:
        return None
    required = {"schema_version", "snapshot_id", "identity", "tickers", "historical_only", "is_actionable"}
    valid = (
        isinstance(raw, Mapping)
        and required <= set(raw)
        and raw.get("schema_version") in QUALIFIED_RESEARCH_SNAPSHOT_V2_SCHEMA_VERSIONS
        and isinstance(raw.get("snapshot_id"), str)
        and isinstance(raw.get("identity"), Mapping)
        and isinstance(raw.get("tickers"), list)
        and raw.get("historical_only") is True
        and raw.get("is_actionable") is False
    )
    if valid:
        valid = all(
            isinstance(row, Mapping)
            and isinstance(row.get("ticker"), str)
            and isinstance(row.get("research_status"), str)
            and isinstance(row.get("reason_codes"), list)
            and isinstance(row.get("analysis_states"), Mapping)
            for row in raw["tickers"]
        )
    if valid:
        return copy.deepcopy(dict(raw))
    return {
        "status": "malformed",
        "historical_only": True,
        "is_actionable": False,
        "reason_codes": ["qualified_research_snapshot_v2_malformed"],
    }


def apply_bundle_qualified_research_snapshot_v2_contract(
    context: dict[str, Any], bundle: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Pass through the complete immutable v2 snapshot, or retain its absence for legacy bundles."""
    value = qualified_research_snapshot_v2_contract(bundle)
    if value is None:
        return context
    context["qualified_research_snapshot_v2"] = value
    context.setdefault("provenance", []).append({
        "source_file": "analysis_bundle.json",
        "source_dataset": "qualified_research_snapshot_v2",
        "transformation": "Verbatim Producer production-universe snapshot; Consumer performs no snapshot, capability, market, valuation, or event recomputation.",
        "limitations": ["Historical-only and non-actionable; no raw/PIT price, volume/liquidity value, target price, probability, or corporate-action fact is inferred."],
    })
    return context


def apply_bundle_qualified_cohort_comparison_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Pass through the fixed qualified-cohort comparison without any comparison logic.

    The Producer owns metric selection, descriptive positions, provenance, and every
    limitation.  Consumer only checks the non-actionable historical envelope and preserves
    the complete section verbatim for AI grounding.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle, Mapping) else None
    raw = entry.get("qualified_cohort_comparison") if isinstance(entry, Mapping) else None
    if raw is None:
        return context
    required = {"schema_version", "status", "cohort_name", "cohort_tickers", "historical_only", "market_dependent",
                "is_actionable", "cross_sectional_comparison", "multi_period_trend", "ranking_prohibited", "rows"}
    valid = (isinstance(raw, Mapping) and required <= set(raw) and raw.get("historical_only") is True
             and raw.get("market_dependent") is False and raw.get("is_actionable") is False
             and raw.get("ranking_prohibited") is True and isinstance(raw.get("cohort_tickers"), list)
             and str(context.get("ticker") or "") in raw["cohort_tickers"] and isinstance(raw.get("rows"), list))
    context["qualified_cohort_comparison"] = copy.deepcopy(dict(raw)) if valid else {
        "status": "malformed", "historical_only": True, "market_dependent": False, "is_actionable": False,
        "reason_codes": ["qualified_cohort_comparison_malformed"],
    }
    context.setdefault("provenance", []).append({
        "source_file": "analysis_bundle.json", "source_dataset": "qualified_cohort_comparison",
        "transformation": "Verbatim Producer qualified-cohort comparison; Consumer performs no metric calculation, currency conversion, position calculation, ranking, or interpretation.",
        "limitations": ["Historical-only descriptive cohort context; not a peer group, recommendation, valuation, liquidity, sizing, or allocation input."],
    })
    return context

def apply_bundle_qualified_market_observations_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Pass through the Producer's provider-scoped market observations verbatim.

    Independent of the qualified-research-brief lane above: Producer gates this on a
    single-provider retained OHLCV window (market_basis_capability_registry.py), not on the
    fundamental-evidence pilot set, so it may be present for any ticker with enough history,
    not just HPG/VNM/VCB. Consumer performs no recomputation and never widens a Producer
    ``unavailable`` into an ``available`` result -- an ``unavailable`` verdict is itself a
    valid, non-malformed pass-through, not something to fall back from.
    """
    entry=((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle,Mapping) else None;raw=entry.get("qualified_market_observations") if isinstance(entry,Mapping) else None
    if raw is not None:
        states={"available","unavailable"}
        structurally_valid=isinstance(raw,Mapping) and raw.get("ticker")==context.get("ticker") and raw.get("is_actionable") is False and raw.get("liquidity_actionable") is False and raw.get("status") in states
        # Short-circuits on structurally_valid first so a non-Mapping raw (already False
        # above) never reaches a second .get() call here.
        valid=structurally_valid and (raw.get("status")!="available" or (raw.get("descriptive_only") is True and raw.get("namespace")=="provider_scoped"))
        context["qualified_market_observations"]=copy.deepcopy(dict(raw)) if valid else {"status":"malformed","is_actionable":False,"liquidity_actionable":False,"reason_codes":["qualified_market_observations_malformed"]}
        context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"qualified_market_observations","transformation":"Verbatim Producer provider-scoped price/volume observations; Consumer performs no recomputation, narrowing, widening, or basis re-derivation.","limitations":["Provider-scoped descriptive/technical only; not a generic market basis, not liquidity, not a current valuation."]})
    return context


_MARKET_WIDE_CURRENT_LIQUIDITY_RESEARCH_DISPOSITIONS = {
    "CURRENT_SESSION_DESCRIPTIVE_ELIGIBLE", "INCOMPLETE", "MISSING", "PROVIDER_REJECTED", "MALFORMED",
}


def market_wide_current_liquidity_research_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional market_wide_current_liquidity_research contract verbatim.

    Canonical location: tickers[ticker].market_wide_current_liquidity_research -- the exact
    per-ticker record from stock-core-private's retained market_wide_current_liquidity_research
    artifact (tools/run_market_wide_current_liquidity_research.py), plus the bundle-level
    "status"/"is_actionable"/"reconciliation_verdict" convenience fields
    export_ai_bundle.py's attach layer adds. Current-session (never historical, never
    point-in-time) DNSE board composition across G1 (matched round lot) / G4 (matched odd lot)
    / T1,T3 (put-through round lot) / T4,T6 (put-through odd lot), the G1x10-vs-OHLC-v
    reconciliation verdict, and the liquidity_research_contract authority-boundary matrix.
    Consumer performs no recomputation: it never derives a traded value, turnover, ADTV, ADV,
    position size, or execution capacity from grossTradeAmount or any other field here, and
    never coerces a non-EXACT_MATCH g1_v_reconciliation.verdict (e.g. SHB's 4-unit residual)
    toward EXACT_MATCH.

    The four Producer dispositions (CURRENT_SESSION_DESCRIPTIVE_ELIGIBLE / INCOMPLETE / MISSING
    / PROVIDER_REJECTED), plus the Producer's own MALFORMED disposition, stay distinct and are
    reused verbatim -- this function invents no new vocabulary for them. A ticker outside the
    retained artifact's universe is a fifth, separate case: the key is absent from the bundle
    entry entirely, so this function returns None (never a synthesized MISSING/zero-filled
    record). The field stays opt-in at the Producer builder level (export_ai_bundle.py defaults
    it off), so this is legacy-compatible by construction: absent in every bundle that did not
    request it. Malformed/tampered input (wrong ticker, an actionable flag flipped true, an
    unknown status/disposition, or an "available" record missing its required reconciliation/
    contract fields) fails closed locally to an explicit malformed record, never silently
    upgraded or dropped.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("market_wide_current_liquidity_research") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    structurally_valid = (
        isinstance(raw, Mapping)
        and raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and raw.get("status") in {"available", "not_available"}
        and raw.get("disposition") in _MARKET_WIDE_CURRENT_LIQUIDITY_RESEARCH_DISPOSITIONS
    )
    # An "available" record additionally carries the full current-session evidence; every other
    # status is a valid, non-malformed Producer answer on its own (MISSING/INCOMPLETE/
    # PROVIDER_REJECTED/MALFORMED never carry board_composition -- nothing to widen from).
    valid = structurally_valid and (
        raw.get("status") != "available"
        or (
            raw.get("disposition") == "CURRENT_SESSION_DESCRIPTIVE_ELIGIBLE"
            and isinstance(raw.get("board_composition"), Mapping)
            and isinstance(raw.get("g1_v_reconciliation"), Mapping)
            and "verdict" in raw["g1_v_reconciliation"]
            and isinstance(raw.get("liquidity_research_contract"), Mapping)
            and "CURRENT_SESSION_LIQUIDITY_RESEARCH" in raw["liquidity_research_contract"]
            and raw.get("current_ohlc_v") is not None
        )
    )
    if not valid:
        return {
            "status": "malformed", "disposition": "MALFORMED", "is_actionable": False,
            "reason_codes": ["market_wide_current_liquidity_research_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_market_wide_current_liquidity_research_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = market_wide_current_liquidity_research_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["market_wide_current_liquidity_research"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "market_wide_current_liquidity_research",
            "transformation": "Pass through the Producer's current-session DNSE board-composition and G1x10-vs-OHLC-v reconciliation contract verbatim. Consumer performs no recomputation of board composition, reconciliation, traded value, turnover, ADTV, ADV, position sizing, or execution capacity.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-market-wide-current-liquidity-research).",
                "CURRENT_SESSION / DESCRIPTIVE_ONLY: never historical liquidity, ADV/ADTV, position sizing, execution capacity, PIT/backtest, or RAW_AS_TRADED authority.",
                "grossTradeAmount remains non-authoritative; no traded value, turnover, or ADTV is inferred from it here or upstream.",
                "A non-EXACT_MATCH g1_v_reconciliation.verdict (e.g. SHB's 4-unit residual) is preserved verbatim as an explicit warning, never coerced, upgraded, or hidden.",
                "A ticker outside the retained artifact's universe has no key at all here, distinct from an in-universe MISSING/INCOMPLETE/PROVIDER_REJECTED record.",
            ],
        })
    return context


_MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_ACTIVITY_STATES = {
    "ACTIVE_LISTED_OBSERVED", "ACTIVE_LISTED_NO_QUALIFIED_SESSION_OBSERVATION",
    "INACTIVE_OR_DELISTED", "UNSUPPORTED_OR_INVALID_PROVIDER_SYMBOL",
    "NOT_APPLICABLE_NON_EQUITY", "UNKNOWN",
}
_MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_TECHNICAL_STATUSES = {"SHADOW_ONLY", "MISSING", "NOT_APPLICABLE"}
_MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_LIQUIDITY_STATUSES = {"ELIGIBLE", "UNAVAILABLE", "NOT_APPLICABLE"}
_MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_SECTOR_STATUSES = {
    "AVAILABLE", "UNAVAILABLE_INSUFFICIENT_COVERAGE", "NOT_CLASSIFIED",
}
_CURRENT_SCREENING_COMPARISON_SCREEN_NAMES = {
    "TREND_AND_POSITIVE_MOMENTUM",
    "MOMENTUM_ABOVE_COHORT_MEDIAN",
    "RELATIVE_VOLUME_ABOVE_COHORT_MEDIAN",
    "TECHNICAL_AND_CURRENT_DESCRIPTIVE_LIQUIDITY",
}


def _market_wide_current_descriptive_research_technical_features_valid(features: Any) -> bool:
    if not isinstance(features, Mapping):
        return False
    status = features.get("status")
    if status not in _MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_TECHNICAL_STATUSES:
        return False
    if status != "SHADOW_ONLY":
        return True  # MISSING / NOT_APPLICABLE carry no values -- nothing to widen from
    return (
        isinstance(features.get("values"), Mapping)
        and "is_current_session" in features
        and "feature_as_of_session" in features
    )


def _market_wide_current_descriptive_research_liquidity_valid(liquidity: Any) -> bool:
    if not isinstance(liquidity, Mapping):
        return False
    status = liquidity.get("status")
    if status not in _MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_LIQUIDITY_STATUSES:
        return False
    if status != "ELIGIBLE":
        return True
    return (
        isinstance(liquidity.get("board_composition"), Mapping)
        and isinstance(liquidity.get("g1_v_reconciliation"), Mapping)
        and "verdict" in liquidity["g1_v_reconciliation"]
    )


def _market_wide_current_descriptive_research_sector_state_valid(sector_state: Any) -> bool:
    if sector_state is None:
        return True
    return isinstance(sector_state, Mapping) and sector_state.get("status") in _MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_SECTOR_STATUSES


def _current_screening_comparison_coverage_valid(coverage: Any, *, denominator: int, observed: int) -> bool:
    return (
        isinstance(coverage, Mapping)
        and coverage.get("current_descriptive_denominator") == denominator
        and coverage.get("observed_session_cohort") == observed
        and isinstance(coverage.get("eligible_count"), int)
        and isinstance(coverage.get("coverage_ratio"), (int, float))
        and isinstance(coverage.get("session"), str)
        and isinstance(coverage.get("source_artifact_identity"), str)
        and isinstance(coverage.get("quality_state"), str)
    )


def _current_screening_comparison_valid(
    screening: Any, *, ticker: str, market_coverage: Mapping[str, Any], source_artifact_identity: Any,
) -> bool:
    """Validate the optional nested screening extension without recalculating it.

    The Consumer accepts only the Producer's deterministic descriptive flags and comparison
    context.  A missing extension remains compatible with earlier opt-in bundles; a supplied
    malformed extension makes the enclosing contract fail closed rather than dropping its
    coverage, warning, or blocked-output semantics.
    """
    if not isinstance(screening, Mapping):
        return False
    denominator = market_coverage.get("current_active_equity_denominator")
    observed = market_coverage.get("observed_session_cohort")
    if not isinstance(denominator, int) or not isinstance(observed, int):
        return False
    disclosure = screening.get("coverage_disclosure")
    ticker_context = screening.get("ticker_context")
    if not (
        isinstance(screening.get("artifact_identity"), str)
        and isinstance(screening.get("source_lineage"), Mapping)
        and isinstance(source_artifact_identity, str)
        and screening["source_lineage"].get("current_descriptive_artifact_identity") == source_artifact_identity
        and isinstance(screening.get("session"), str)
        and isinstance(disclosure, Mapping)
        and disclosure.get("denominator") == denominator
        and disclosure.get("observed_session_cohort") == observed
        and isinstance(screening.get("screen_definitions"), Mapping)
        and set(screening["screen_definitions"]) == _CURRENT_SCREENING_COMPARISON_SCREEN_NAMES
        and isinstance(screening.get("screen_membership_counts"), Mapping)
        and set(screening["screen_membership_counts"]) == _CURRENT_SCREENING_COMPARISON_SCREEN_NAMES
        and all(isinstance(value, int) for value in screening["screen_membership_counts"].values())
        and isinstance(screening.get("market_relative_comparison_summary"), Mapping)
        and isinstance(screening.get("sector_relative_comparison_summary"), Mapping)
        and isinstance(screening.get("quality_warnings"), list)
        and isinstance(screening.get("blocked_outputs"), Mapping)
        and isinstance(screening.get("authority_boundary"), Mapping)
        and screening.get("is_actionable") is False
        and isinstance(ticker_context, Mapping)
        and ticker_context.get("ticker") == ticker
        and _current_screening_comparison_coverage_valid(
            ticker_context.get("coverage_context"), denominator=denominator, observed=observed,
        )
    ):
        return False
    memberships = ticker_context.get("screen_membership")
    if not isinstance(memberships, Mapping) or set(memberships) != _CURRENT_SCREENING_COMPARISON_SCREEN_NAMES:
        return False
    for membership in memberships.values():
        if not (
            isinstance(membership, Mapping)
            and membership.get("status") in {"ELIGIBLE", "UNAVAILABLE"}
            and (membership.get("member") is True or membership.get("member") is False or membership.get("member") is None)
            and _current_screening_comparison_coverage_valid(
                membership.get("coverage"), denominator=denominator, observed=observed,
            )
        ):
            return False
    for comparison_key in ("market_relative_comparison", "sector_relative_comparison", "liquidity_context"):
        comparison = ticker_context.get(comparison_key)
        if not isinstance(comparison, Mapping) or comparison.get("status") not in {"AVAILABLE", "ELIGIBLE", "UNAVAILABLE"}:
            return False
        if not _current_screening_comparison_coverage_valid(comparison.get("coverage"), denominator=denominator, observed=observed):
            return False
    return True


def market_wide_current_descriptive_research_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional market_wide_current_descriptive_research contract verbatim.

    Canonical location: tickers[ticker].market_wide_current_descriptive_research -- the exact
    per-ticker record from stock-core-private's retained
    market_wide_current_descriptive_research artifact
    (tools/run_market_wide_current_descriptive_research.py), plus the bundle-level
    "market_coverage"/"blocked_outputs"/"status"/"is_actionable" convenience fields
    export_ai_bundle.py's attach layer adds. Current-session (never historical, never
    point-in-time) market-wide breadth/sector/cross-sectional technical features and liquidity.

    denominator=1,510 (`market_coverage.current_active_equity_denominator`) and
    observed_session_cohort=960 (`market_coverage.observed_session_cohort`) travel with every
    ticker so a reader of a single ticker's context still sees the full-market coverage
    disclosure -- partial same-session coverage must never be represented as full-market
    breadth. `technical_features.is_current_session` distinguishes a genuine same-session
    reading from a stale prior-session value; both are legitimate Producer answers on their
    own and neither is coerced into the other. `sector_state.status =
    "UNAVAILABLE_INSUFFICIENT_COVERAGE"` is preserved exactly: Consumer never fills in or
    broadens an insufficient-coverage sector. `liquidity`'s SHB-style non-EXACT_MATCH
    `g1_v_reconciliation.verdict` is preserved exactly, never coerced toward EXACT_MATCH.
    Consumer performs no recomputation of breadth, sector cohorts, technical features,
    liquidity, traded value, turnover, ADTV, ADV, position sizing, or execution capacity.

    A ticker outside the retained artifact's universe is a separate case: the key is absent
    from the bundle entry entirely, so this function returns None (never a synthesized
    not_available/zero-filled record). The field stays opt-in at the Producer builder level
    (export_ai_bundle.py defaults it off), so this is legacy-compatible by construction.
    Malformed/tampered input (wrong ticker, an actionable flag flipped true, an unknown
    status/activity-state, or missing required nested structure) fails closed locally to an
    explicit malformed record, never silently upgraded or dropped.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("market_wide_current_descriptive_research") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    valid = (
        isinstance(raw, Mapping)
        and raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and raw.get("status") in {"available", "not_available"}
        and raw.get("activity_and_session_state") in _MARKET_WIDE_CURRENT_DESCRIPTIVE_RESEARCH_ACTIVITY_STATES
        and _market_wide_current_descriptive_research_technical_features_valid(raw.get("technical_features"))
        and _market_wide_current_descriptive_research_liquidity_valid(raw.get("liquidity"))
        and _market_wide_current_descriptive_research_sector_state_valid(raw.get("sector_state"))
        and isinstance(raw.get("market_coverage"), Mapping)
        and isinstance(raw["market_coverage"].get("current_active_equity_denominator"), int)
        and isinstance(raw["market_coverage"].get("observed_session_cohort"), int)
        and isinstance(raw.get("blocked_outputs"), Mapping)
        and ("screening_comparison" not in raw or _current_screening_comparison_valid(
            raw.get("screening_comparison"), ticker=ticker, market_coverage=raw["market_coverage"],
            source_artifact_identity=raw.get("source_artifact_identity"),
        ))
    )
    if not valid:
        return {
            "status": "malformed", "activity_and_session_state": "UNKNOWN", "is_actionable": False,
            "reason_codes": ["market_wide_current_descriptive_research_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_market_wide_current_descriptive_research_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = market_wide_current_descriptive_research_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["market_wide_current_descriptive_research"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "market_wide_current_descriptive_research",
            "transformation": "Pass through the Producer's current-session market-wide breadth/sector/cross-sectional-technical-feature/liquidity research contract verbatim, including an optional nested deterministic screening/comparison extension. Consumer performs no recomputation of breadth, sector cohorts, technical features, screening flags, relative positions, liquidity, traded value, turnover, ADTV, ADV, position sizing, or execution capacity.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-market-wide-current-descriptive-research).",
                "CURRENT_SESSION / DESCRIPTIVE_ONLY: never historical PIT, RAW_AS_TRADED, corporate-action/ex-date, backtesting, active-universe promotion, ranking, recommendation, valuation, ADV/ADTV, sizing, or execution authority (see blocked_outputs).",
                "market_coverage.current_active_equity_denominator (1,510) and observed_session_cohort (960) must always be reported together; a same-session statistic bounded by the smaller observed/technical-feature count must never be described as covering the full denominator.",
                "technical_features.is_current_session distinguishes a genuine same-session reading from a stale prior-session value; a stale value is reported only as of its own feature_as_of_session, never as today's.",
                "sector_state.status = UNAVAILABLE_INSUFFICIENT_COVERAGE is preserved verbatim; never filled in, estimated, or treated as zero/neutral.",
                "A non-EXACT_MATCH liquidity.g1_v_reconciliation.verdict (e.g. SHB's 4-unit residual) is preserved verbatim as an explicit warning, never coerced, upgraded, or hidden.",
                "grossTradeAmount remains non-authoritative; no traded value, turnover, or ADTV is inferred from it here or upstream.",
                "screening_comparison, when explicitly requested upstream, contains independent deterministic descriptive flags and market/sector-relative percentile or bucket context only: never a composite score, ordinal ranking, recommendation, forecast, valuation, probability, portfolio, sizing, or execution output.",
                "A ticker outside the retained artifact's universe has no key at all here, distinct from an in-universe not_available record.",
            ],
        })
    return context


_MARKET_WIDE_CURRENT_FUNDAMENTAL_RESEARCH_TIERS = {"OFFICIAL_QUALIFIED", "PROVIDER_RESEARCH", "BLOCKED"}
_MARKET_WIDE_CURRENT_FUNDAMENTAL_RESEARCH_STATUSES = {"official_qualified", "provider_research", "blocked"}
_MARKET_WIDE_CURRENT_FUNDAMENTAL_RESEARCH_READINESS_STATES = {"READY", "PARTIAL", "BLOCKED"}
_FUNDAMENTAL_TRAJECTORY_STATUSES = {"AVAILABLE", "UNAVAILABLE", "OFFICIAL_METRIC_CONTEXT_ONLY"}


def _valid_fundamental_trajectory_context(raw: Mapping[str, Any], tier: str) -> bool:
    """Validate the optional additive trajectory envelope without deriving or scoring it.

    Older retained artifacts legitimately omit this field.  When present, it must remain tied to
    the Producer's tier and keep its descriptive/non-actionable shape before Consumer passes it
    through verbatim.
    """
    context = raw.get("fundamental_trajectory_context")
    if context is None:
        return True
    if not isinstance(context, Mapping):
        return False
    if (context.get("authority_tier") != tier
            or context.get("trajectory_status") not in _FUNDAMENTAL_TRAJECTORY_STATUSES
            or not isinstance(context.get("entity_class"), str)
            or not isinstance(context.get("data_limitations"), list)
            or not isinstance(context.get("period_coverage"), Mapping)
            or not isinstance(context.get("revenue_vs_earnings_alignment"), Mapping)
            or not isinstance(context.get("balance_sheet_expansion_pattern"), Mapping)
            or not isinstance(context.get("acceleration"), Mapping)
            or any(key in context for key in ("score", "ranking", "recommendation", "target_price", "probability"))):
        return False
    if tier == "PROVIDER_RESEARCH":
        return (
            context.get("trajectory_status") in {"AVAILABLE", "UNAVAILABLE"}
            and context.get("official_metric_context") is None
            and isinstance(context.get("multi_dimensional_trajectory"), bool)
            and isinstance(context.get("unavailable_or_partial_reasons"), list)
        )
    if tier == "OFFICIAL_QUALIFIED":
        return (
            context.get("trajectory_status") == "OFFICIAL_METRIC_CONTEXT_ONLY"
            and isinstance(context.get("official_metric_context"), Mapping)
        )
    return context.get("trajectory_status") == "UNAVAILABLE"


def market_wide_current_fundamental_research_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional market_wide_current_fundamental_research contract verbatim.

    Canonical location: tickers[ticker].market_wide_current_fundamental_research -- the exact
    per-ticker record from stock-core-private's retained
    market_wide_current_fundamental_research artifact
    (tools/run_market_wide_current_fundamental_research.py), plus the bundle-level
    "status"/"is_actionable"/"source_artifact_identity"/"coverage" convenience fields
    export_ai_bundle.py's attach layer adds.

    Two authority tiers, never conflated: `OFFICIAL_QUALIFIED` (13 issuers today) carries the
    full per-metric lineage, periods used, sector-specific applicability
    (NOT_APPLICABLE industrial metrics on bank/securities issuers preserved verbatim), and
    fundamental_research_readiness; `PROVIDER_RESEARCH` and `BLOCKED` (the remaining ~510
    candidates) carry retained-provider statement-family presence, a blocked reason, and an
    allowed/forbidden-use list. When present, `provider_series_trends` contains only
    same-ticker/same-provider/consecutive-quarter trend rates or directions, never an absolute
    financial fact; scope/currency/scale remain UNKNOWN by design. Consumer performs no
    recomputation of any metric, and never upgrades a
    PROVIDER_RESEARCH/BLOCKED ticker toward OFFICIAL_QUALIFIED or a MISSING/BLOCKED/NOT_APPLICABLE
    metric toward EXACT_QUALIFIED/DERIVED_PROXY.

    A ticker outside the retained artifact's universe is a separate case from an in-universe
    BLOCKED record: the key is absent from the bundle entry entirely, so this function returns
    None (never a synthesized record). The field stays opt-in at the Producer builder level
    (export_ai_bundle.py defaults it off). Malformed/tampered input fails closed locally to an
    explicit malformed record, never silently upgraded or dropped.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("market_wide_current_fundamental_research") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    tier = raw.get("authority_tier") if isinstance(raw, Mapping) else None
    structurally_valid = (
        isinstance(raw, Mapping)
        and raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and raw.get("status") in _MARKET_WIDE_CURRENT_FUNDAMENTAL_RESEARCH_STATUSES
        and tier in _MARKET_WIDE_CURRENT_FUNDAMENTAL_RESEARCH_TIERS
        and isinstance(raw.get("sector"), str)
    )
    if structurally_valid and tier == "OFFICIAL_QUALIFIED":
        valid = (
            isinstance(raw.get("metrics"), list)
            and isinstance(raw.get("metric_family_states"), Mapping)
            and raw.get("fundamental_research_readiness") in _MARKET_WIDE_CURRENT_FUNDAMENTAL_RESEARCH_READINESS_STATES
            and isinstance(raw.get("entity_class"), str)
            and _valid_fundamental_trajectory_context(raw, tier)
        )
    elif structurally_valid:
        # PROVIDER_RESEARCH or BLOCKED: provider series remains descriptive-only. A retained
        # same-provider trend envelope is allowed, but no absolute provider fact or official tier.
        trends = raw.get("provider_series_trends")
        trends_valid = trends is None or (
            tier == "PROVIDER_RESEARCH"
            and isinstance(trends, Mapping)
            and trends.get("authority_tier") == "PROVIDER_RESEARCH"
            and trends.get("status") in {"AVAILABLE", "BLOCKED"}
            and isinstance(trends.get("metrics"), Mapping)
            and all(
                isinstance(metric, Mapping)
                and metric.get("ticker") == ticker
                and metric.get("authority_tier") == "PROVIDER_RESEARCH"
                and isinstance(metric.get("provider"), (str, type(None)))
                and isinstance(metric.get("periods"), list)
                and isinstance(metric.get("method"), str)
                and metric.get("status") in {"AVAILABLE", "BLOCKED"}
                and isinstance(metric.get("lineage"), list)
                and isinstance(metric.get("data_limitations"), list)
                and isinstance(metric.get("comparability_scope"), str)
                and metric.get("metric_family_classification") in {"POINT_IN_TIME_STOCK", "PERIOD_FLOW"}
                and isinstance(metric.get("period_basis"), list)
                and "blocked_reason" in metric
                and "value" not in metric
                and "absolute_value" not in metric
                and (
                    "comparisons" not in metric
                    or (
                        isinstance(metric.get("comparisons"), Mapping)
                        and all(
                            isinstance(comparison, Mapping)
                            and comparison.get("comparison_type") in {"QoQ", "YoY"}
                            and comparison.get("status") in {"AVAILABLE", "BLOCKED"}
                            and isinstance(comparison.get("provider"), (str, type(None)))
                            and isinstance(comparison.get("periods"), list)
                            and isinstance(comparison.get("lineage"), list)
                            and isinstance(comparison.get("period_basis"), list)
                            and "blocked_reason" in comparison
                            and "value" not in comparison
                            and "absolute_value" not in comparison
                            for comparison in metric["comparisons"].values()
                        )
                    )
                )
                for metric in trends["metrics"].values()
            )
        )
        valid = (
            isinstance(raw.get("disposition"), str)
            and isinstance(raw.get("allowed_uses"), list)
            and isinstance(raw.get("forbidden_uses"), list)
            and "metrics" not in raw
            and trends_valid
            and _valid_fundamental_trajectory_context(raw, tier)
        )
    else:
        valid = False
    if not valid:
        return {
            "status": "malformed", "authority_tier": "MALFORMED", "is_actionable": False,
            "reason_codes": ["market_wide_current_fundamental_research_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_market_wide_current_fundamental_research_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = market_wide_current_fundamental_research_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["market_wide_current_fundamental_research"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "market_wide_current_fundamental_research",
            "transformation": "Pass through the Producer's market-wide fundamental-research coverage contract verbatim: the officially-qualified per-metric lineage for OFFICIAL_QUALIFIED issuers, or the provider-tier disposition/blocked reason, allowed/forbidden-use list, and already-computed same-provider series trends for PROVIDER_RESEARCH/BLOCKED candidates. Consumer performs no recomputation of any metric value, growth rate, ratio, or sector applicability gate.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-market-wide-current-fundamental-research).",
                "OFFICIAL_QUALIFIED issuers are a small, evidence-constrained cohort (13 today). PROVIDER_RESEARCH may carry only same-provider consecutive-quarter trend research, with no absolute provider fact or calculation-grade authority; statement scope, currency, and unit scale remain UNKNOWN by design.",
                "A NOT_APPLICABLE metric on a bank/securities issuer (e.g. debt_to_equity on VCB) is preserved verbatim; never treated as missing or as zero.",
                "Never a valuation, target price, ranking, recommendation, probability, portfolio weight, sizing, or backtest output.",
                "A ticker outside the retained artifact's universe has no key at all here, distinct from an in-universe BLOCKED record.",
            ],
        })
    return context


_CURRENT_MARKET_SECTOR_BREADTH_STATES = {
    "BROAD_PARTICIPATION", "DETERIORATING_BREADTH", "NARROW_LEADERSHIP", "MIXED_BREADTH", "DATA_LIMITED",
}
_CURRENT_MARKET_SECTOR_TICKER_STATUSES = {"AVAILABLE", "PARTIAL", "DATA_LIMITED"}
_CURRENT_MARKET_SECTOR_BREADTH_SUPPORT_STATES = {
    "MARKET_AND_GROUP_BREADTH_SUPPORT", "GROUP_ONLY_SUPPORT_MARKET_NOT_BROAD",
    "MARKET_ONLY_SUPPORT_GROUP_NOT_BROAD", "DATA_LIMITED", "ISOLATED_OR_MIXED_PARTICIPATION",
}
_CURRENT_MARKET_SECTOR_LEADERSHIP_STATUSES = {"AVAILABLE", "DATA_LIMITED", "UNAVAILABLE"}


def _current_market_sector_leadership_context_valid(raw: Any, *, ticker: str) -> bool:
    if not isinstance(raw, Mapping):
        return False
    market = raw.get("market")
    ticker_context = raw.get("ticker_context")
    blocked_outputs = raw.get("blocked_outputs")
    authority_boundary = raw.get("authority_boundary")
    if not (
        raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and raw.get("status") in {"available", "data_limited"}
        and isinstance(raw.get("session"), str)
        and isinstance(raw.get("source_artifact_identity"), str)
        and raw["source_artifact_identity"].startswith("current_market_sector_leadership_context:")
        and raw.get("research_mode") == "CURRENT_SESSION_DESCRIPTIVE_MARKET_AND_SECTOR_CONTEXT"
        and isinstance(market, Mapping)
        and isinstance(ticker_context, Mapping)
        and isinstance(raw.get("coverage"), Mapping)
        and isinstance(blocked_outputs, Mapping)
        and isinstance(authority_boundary, Mapping)
        and authority_boundary.get("is_actionable") is False
        and authority_boundary.get("no_strategy_priority_entry_or_sizing_mutation") is True
        and authority_boundary.get("no_opaque_global_score") is True
        and authority_boundary.get("missing_current_session_bar_is_not_zero") is True
        and blocked_outputs.get("research_priority") == "NOT_MODIFIED"
        and blocked_outputs.get("entry_action") == "NOT_MODIFIED"
        and blocked_outputs.get("strategy_eligibility") == "NOT_MODIFIED"
        and blocked_outputs.get("global_or_ticker_ranking_score") == "NOT_EMITTED"
    ):
        return False
    if not (
        isinstance(market.get("session"), str)
        and isinstance(market.get("official_universe_count"), int)
        and isinstance(market.get("exact_session_observed_count"), int)
        and isinstance(market.get("missing_current_session_count"), int)
        and market.get("current_breadth_state") in _CURRENT_MARKET_SECTOR_BREADTH_STATES
        and isinstance(market.get("warnings"), list)
    ):
        return False
    if not (
        ticker_context.get("ticker") == ticker
        and ticker_context.get("status") in _CURRENT_MARKET_SECTOR_TICKER_STATUSES
        and isinstance(ticker_context.get("market_relative_momentum"), Mapping)
        and isinstance(ticker_context.get("sector_relative_momentum"), Mapping)
        and isinstance(ticker_context.get("sector_leadership_context"), Mapping)
        and ticker_context["sector_leadership_context"].get("status") in _CURRENT_MARKET_SECTOR_LEADERSHIP_STATUSES
        and ticker_context.get("breadth_support_state") in _CURRENT_MARKET_SECTOR_BREADTH_SUPPORT_STATES
        and isinstance(ticker_context.get("coverage_limitations"), list)
    ):
        return False
    return True


def current_market_sector_leadership_context_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed pass-through for the opt-in current market/sector leadership context.

    Canonical location: tickers[ticker].current_market_sector_leadership_context, attached by
    stock-core-private's export_ai_bundle.py only with
    --include-current-market-sector-leadership-context. Descriptive current-session breadth/
    leadership only; Producer's own blocked_outputs and authority_boundary mark
    research_priority/entry_action/strategy_eligibility/sizing as never modified and no opaque
    score as ever emitted. Consumer performs no recomputation of any ratio, percentile, or state.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_market_sector_leadership_context") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not _current_market_sector_leadership_context_valid(raw, ticker=ticker):
        return {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_market_sector_leadership_context_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_current_market_sector_leadership_context_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_market_sector_leadership_context_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_market_sector_leadership_context"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_market_sector_leadership_context",
            "transformation": "Pass through the Producer's current-session official-universe market breadth, this ticker's own row (market/sector-relative momentum, breadth_support_state, sector_leadership_context), coverage counts, blocked outputs, and authority boundary verbatim. Consumer performs no recomputation of any ratio, percentile, breadth state, or leadership state.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-market-sector-leadership-context).",
                "CURRENT_SESSION_DESCRIPTIVE_MARKET_AND_SECTOR_CONTEXT only: current cross-sectional relative strength, not historical, not PIT, not a backtest.",
                "A missing current-session technical bar is an explicit coverage gap, never an unchanged or zero return.",
                "An unknown sector identity stays unknown; never inferred from ticker name or model knowledge.",
                "No opaque global or ticker ranking score; research_priority, entry_action, strategy_eligibility, and sizing/execution are never modified by this section.",
            ],
        })
    return context


_FINANCIAL_MOMENTUM_EVIDENCE_TIERS = {"OFFICIAL_QUALIFIED", "PROVIDER_RESEARCH", "BLOCKED", "UNAVAILABLE"}
_FINANCIAL_MOMENTUM_COVERAGE_STATUSES = {"FULL", "PARTIAL", "INSUFFICIENT", "NOT_APPLICABLE"}
_FINANCIAL_MOMENTUM_STATES = {
    "BROAD_IMPROVEMENT", "EARNINGS_IMPROVING", "MIXED", "DETERIORATING",
    "LOSS_MAKING_OR_STRESSED", "INSUFFICIENT_COMPARABLE_DATA", "NOT_APPLICABLE",
}
_FINANCIAL_MOMENTUM_COMPONENT_STATUSES = {"AVAILABLE", "PARTIAL", "BLOCKED", "UNAVAILABLE", "NOT_APPLICABLE"}
_FINANCIAL_MOMENTUM_PRICE_CONTRAST_STATUSES = {"AVAILABLE", "UNAVAILABLE"}
_FINANCIAL_MOMENTUM_REQUIRED_PROHIBITED_USES = {
    "cheapness", "VALUE", "target_price", "forecast", "probability",
    "strategy_eligibility", "research_priority", "entry_action", "recommendation", "sizing",
}


def _financial_momentum_component_valid(component: Any) -> bool:
    current_value = component.get("current_value") if isinstance(component, Mapping) else None
    return (
        isinstance(component, Mapping)
        and component.get("status") in _FINANCIAL_MOMENTUM_COMPONENT_STATUSES
        and isinstance(component.get("periods"), list)
        and isinstance(component.get("warnings"), list)
        and (current_value is None or (isinstance(current_value, (int, float)) and not isinstance(current_value, bool)))
        and (component.get("status") in {"AVAILABLE", "PARTIAL"} or component.get("direction") is None)
    )


def _current_financial_momentum_context_valid(raw: Any, *, ticker: str) -> bool:
    if not isinstance(raw, Mapping):
        return False
    ticker_context = raw.get("ticker_context")
    blocked_outputs = raw.get("blocked_outputs")
    authority_boundary = raw.get("authority_boundary")
    if not (
        raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and raw.get("status") in {"available", "data_limited"}
        and (raw.get("session") is None or isinstance(raw.get("session"), str))
        and isinstance(raw.get("source_artifact_identity"), str)
        and raw["source_artifact_identity"].startswith("current_financial_momentum_context:")
        and raw.get("research_mode") == "CURRENT_RESEARCH_ONLY"
        and isinstance(ticker_context, Mapping)
        and isinstance(raw.get("coverage"), Mapping)
        and isinstance(blocked_outputs, Mapping)
        and blocked_outputs.get("strategy_eligibility") == "NOT_MODIFIED"
        and blocked_outputs.get("research_priority") == "NOT_MODIFIED"
        and blocked_outputs.get("entry_action") == "NOT_MODIFIED"
        and blocked_outputs.get("fundamental_improvement_strategy") == "NOT_ENABLED_BY_THIS_CONTEXT"
        and isinstance(authority_boundary, Mapping)
        and authority_boundary.get("is_actionable") is False
        and authority_boundary.get("financial_momentum_is_not_strategy_eligibility") is True
        and authority_boundary.get("financial_momentum_is_not_research_priority") is True
        and authority_boundary.get("financial_momentum_is_not_entry_action") is True
        and authority_boundary.get("financial_momentum_is_not_recommendation") is True
        and authority_boundary.get("financial_momentum_is_not_value") is True
        and authority_boundary.get("financial_momentum_is_not_target_price") is True
        and authority_boundary.get("financial_momentum_is_not_probability") is True
        and authority_boundary.get("financial_momentum_is_not_sizing") is True
        and authority_boundary.get("financial_momentum_is_not_price_momentum") is True
        and authority_boundary.get("official_and_provider_remain_separated") is True
        and authority_boundary.get("provider_not_upgraded_to_official") is True
        and authority_boundary.get("missing_is_not_zero") is True
    ):
        return False
    components = ticker_context.get("components")
    price_context = ticker_context.get("price_momentum_context")
    if not (
        ticker_context.get("ticker") == ticker
        and ticker_context.get("evidence_tier") in _FINANCIAL_MOMENTUM_EVIDENCE_TIERS
        and ticker_context.get("coverage_status") in _FINANCIAL_MOMENTUM_COVERAGE_STATUSES
        and ticker_context.get("financial_momentum_state") in _FINANCIAL_MOMENTUM_STATES
        and isinstance(ticker_context.get("entity_class"), str)
        and isinstance(ticker_context.get("supporting_dimensions"), list)
        and isinstance(ticker_context.get("weakening_dimensions"), list)
        and isinstance(ticker_context.get("blockers"), list)
        and isinstance(ticker_context.get("warnings"), list)
        and isinstance(ticker_context.get("comparable_period_identities"), list)
        and isinstance(ticker_context.get("allowed_uses"), list)
        and isinstance(ticker_context.get("prohibited_uses"), list)
        and _FINANCIAL_MOMENTUM_REQUIRED_PROHIBITED_USES <= set(ticker_context["prohibited_uses"])
        and isinstance(components, Mapping)
        and all(_financial_momentum_component_valid(component) for component in components.values())
        and isinstance(price_context, Mapping)
        and price_context.get("status") in _FINANCIAL_MOMENTUM_PRICE_CONTRAST_STATUSES
        and price_context.get("financial_momentum_is_not_price_momentum") is True
    ):
        return False
    return True


def current_financial_momentum_context_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed pass-through for the opt-in current financial momentum context.

    Canonical location: tickers[ticker].current_financial_momentum_context, attached by
    stock-core-private's export_ai_bundle.py only with
    --include-current-financial-momentum-context. Descriptive current-research-only
    projection of already-qualified official FY YoY metrics and already-emitted provider-
    series trends; Producer's own blocked_outputs/authority_boundary mark
    strategy_eligibility/research_priority/entry_action as never modified, official and
    provider tiers as never merged, and FUNDAMENTAL_IMPROVEMENT as never enabled by this
    context. Consumer performs no recomputation of any growth, margin, or state.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_financial_momentum_context") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not _current_financial_momentum_context_valid(raw, ticker=ticker):
        return {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_financial_momentum_context_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_current_financial_momentum_context_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_financial_momentum_context_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_financial_momentum_context"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_financial_momentum_context",
            "transformation": "Pass through the Producer's current financial-momentum research context verbatim: evidence tier, comparable-period component states (revenue/earnings/margin/operating cash flow), supporting/weakening dimensions, financial_momentum_state, coverage status, price-momentum contrast, blockers, warnings, and authority boundary. Consumer performs no recomputation of any growth rate, margin change, or momentum state.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-financial-momentum-context).",
                "CURRENT_RESEARCH_ONLY: never a forecast, valuation, cheapness/VALUE, target price, probability, recommendation, strategy eligibility, research_priority, entry_action, or sizing claim; does not enable FUNDAMENTAL_IMPROVEMENT.",
                "OFFICIAL_QUALIFIED and PROVIDER_RESEARCH tiers stay separated; provider evidence is never upgraded to official merely because components, price momentum, or sector leadership agree with it.",
                "FY YoY, quarterly YoY, and QoQ PARTIAL are distinct comparison types and are never relabelled as each other; a missing comparable dimension is a coverage gap, never zero.",
                "Bank/securities archetypes never receive an industrial revenue/margin interpretation; NOT_APPLICABLE is preserved exactly, never treated as missing.",
                "price_momentum_context contrasts operational financial momentum with current-session price momentum descriptively; it is not itself a trade signal.",
            ],
        })
    return context


_CORPORATE_EVENT_STATUSES = {
    "CONFIRMED_UPCOMING", "CONFIRMED_RECENT", "EXECUTED", "PLANNED_NOT_EXECUTED",
    "CANCELLED", "TEMPORAL_DETAILS_INCOMPLETE", "CONFLICTING_EVIDENCE", "DATA_LIMITED",
}
_CORPORATE_EVENT_TEMPORAL_COMPLETENESS_STATES = {"COMPLETE", "INCOMPLETE"}
_CORPORATE_EVENT_CONTEXT_STATUSES = {"available", "data_limited"}
_CORPORATE_EVENT_FORBIDDEN_USES = {
    "EVENT_DRIVEN_eligibility", "price_impact", "probability", "target",
    "research_priority", "entry_action", "recommendation", "sizing",
}
_CORPORATE_EVENT_NULLABLE_STRING_FIELDS = (
    "source", "published_at", "observed_at", "known_at", "announcement_date",
    "record_date", "ex_date", "effective_date", "execution_date",
    "qualification", "source_event_id", "source_record_identity",
)
_CORPORATE_EVENT_TICKER_CONTEXT_COUNT_FIELDS = (
    "confirmed_upcoming_count", "recent_confirmed_count", "executed_count",
    "recent_confirmed_or_executed_count", "planned_unresolved_count",
    "conflicting_count", "data_limited_count", "temporal_incomplete_count",
    "qualified_event_count",
)


def _corporate_event_valid(event: Any, *, ticker: str) -> bool:
    """One retained event record: every temporal field independent, none inferred."""
    if not isinstance(event, Mapping):
        return False
    if not (
        event.get("ticker") == ticker
        and isinstance(event.get("event_type"), str) and event["event_type"]
        and event.get("event_status") in _CORPORATE_EVENT_STATUSES
        and isinstance(event.get("status_reason"), str) and event["status_reason"]
        and isinstance(event.get("evidence_tier"), str) and event["evidence_tier"]
        and event.get("temporal_completeness") in _CORPORATE_EVENT_TEMPORAL_COMPLETENESS_STATES
        and isinstance(event.get("conflicts"), list)
        and isinstance(event.get("warnings"), list)
        and isinstance(event.get("blockers"), list)
        and isinstance(event.get("materiality_status"), str)
        and isinstance(event.get("source_identities"), list)
        and isinstance(event.get("supporting_evidence"), list)
        and all(isinstance(item, Mapping) for item in event["supporting_evidence"])
        and isinstance(event.get("insufficient_for_event_driven"), bool)
        and isinstance(event.get("allowed_uses"), list)
        and isinstance(event.get("prohibited_uses"), list)
        and _CORPORATE_EVENT_FORBIDDEN_USES <= set(event["prohibited_uses"])
        and isinstance(event.get("event_id"), str)
        and event["event_id"].startswith("current_corporate_event:")
    ):
        return False
    for field in _CORPORATE_EVENT_NULLABLE_STRING_FIELDS:
        value = event.get(field)
        if value is not None and not isinstance(value, str):
            return False
    return True


def _current_corporate_event_context_valid(raw: Any, *, ticker: str) -> bool:
    if not isinstance(raw, Mapping):
        return False
    ticker_context = raw.get("ticker_context")
    blocked_outputs = raw.get("blocked_outputs")
    authority_boundary = raw.get("authority_boundary")
    if not (
        raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and raw.get("status") in _CORPORATE_EVENT_CONTEXT_STATUSES
        and isinstance(raw.get("research_session"), str) and raw["research_session"]
        and isinstance(raw.get("source_artifact_identity"), str)
        and raw["source_artifact_identity"].startswith("current_corporate_event_context:")
        and raw.get("research_mode") == "CURRENT_RESEARCH_ONLY"
        and isinstance(ticker_context, Mapping)
        and isinstance(raw.get("coverage"), Mapping)
        and isinstance(blocked_outputs, Mapping)
        and blocked_outputs.get("strategy_eligibility") == "NOT_MODIFIED"
        and blocked_outputs.get("event_driven_strategy") == "NOT_ENABLED_BY_THIS_CONTEXT"
        and blocked_outputs.get("research_priority") == "NOT_MODIFIED"
        and blocked_outputs.get("entry_action") == "NOT_MODIFIED"
        and isinstance(authority_boundary, Mapping)
        and authority_boundary.get("is_actionable") is False
        and authority_boundary.get("corporate_event_context_is_not_event_driven_eligibility") is True
        and authority_boundary.get("corporate_event_context_is_not_price_impact") is True
        and authority_boundary.get("corporate_event_context_is_not_probability") is True
        and authority_boundary.get("corporate_event_context_is_not_target") is True
        and authority_boundary.get("corporate_event_context_is_not_research_priority") is True
        and authority_boundary.get("corporate_event_context_is_not_entry_action") is True
        and authority_boundary.get("corporate_event_context_is_not_recommendation") is True
        and authority_boundary.get("corporate_event_context_is_not_sizing") is True
        and authority_boundary.get("record_date_is_not_ex_date") is True
        and authority_boundary.get("planned_is_not_executed") is True
        and authority_boundary.get("announcement_is_not_execution") is True
        and authority_boundary.get("ex_date_not_inferred") is True
        and authority_boundary.get("execution_date_not_inferred") is True
        and authority_boundary.get("no_look_ahead") is True
        and authority_boundary.get("pit") == "BLOCKED"
    ):
        return False
    events = ticker_context.get("events")
    if not (
        ticker_context.get("ticker") == ticker
        # Both fields are set from the same artifact-level session by Producer; a
        # mismatch is a tampered/inconsistent artifact, not a legitimate variant.
        and ticker_context.get("research_session") == raw["research_session"]
        and isinstance(events, list)
        and all(_corporate_event_valid(event, ticker=ticker) for event in events)
        and all(
            isinstance(ticker_context.get(field), int) and not isinstance(ticker_context.get(field), bool)
            for field in _CORPORATE_EVENT_TICKER_CONTEXT_COUNT_FIELDS
        )
        and isinstance(ticker_context.get("has_qualified_event"), bool)
        and ticker_context.get("does_not_enable_event_driven") is True
        and isinstance(ticker_context.get("allowed_uses"), list)
        and isinstance(ticker_context.get("prohibited_uses"), list)
        and _CORPORATE_EVENT_FORBIDDEN_USES <= set(ticker_context["prohibited_uses"])
    ):
        return False
    return True


def current_corporate_event_context_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed pass-through for the opt-in current corporate event context.

    Canonical location: tickers[ticker].current_corporate_event_context, attached by
    stock-core-private's export_ai_bundle.py only with
    --include-current-corporate-event-context. Descriptive current-research-only
    projection of retained official exchange events and retained issuer/VSDC corporate-
    action chains; Producer's own blocked_outputs/authority_boundary mark
    strategy_eligibility/research_priority/entry_action as never modified and EVENT_DRIVEN
    strategy as never enabled by this context. Consumer performs no recomputation of any
    event status and never infers a missing ex_date, execution_date, or effective_date
    from record_date or any other related date.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_corporate_event_context") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not _current_corporate_event_context_valid(raw, ticker=ticker):
        return {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_corporate_event_context_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_current_corporate_event_context_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_corporate_event_context_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_corporate_event_context"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_corporate_event_context",
            "transformation": "Pass through the Producer's current corporate-event research context verbatim: per-event identity, event_type, event_status, evidence_tier, source/evidence identities, every temporal field (published_at, observed_at, known_at, announcement_date, record_date, ex_date, effective_date, execution_date) independently, temporal_completeness, conflicts, warnings, blockers, materiality_status, insufficient_for_event_driven, ticker-level event counts, coverage, blocked outputs, and authority boundary. Consumer performs no recomputation of any event status and never infers ex_date, execution_date, or effective_date from a related date.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-corporate-event-context).",
                "CURRENT_RESEARCH_ONLY: event existence is never a price-impact, reaction-probability, EVENT_DRIVEN-eligibility, research_priority, entry_action, recommendation, or sizing claim.",
                "record_date without ex_date stays record_date without ex_date; ex_date is never synthesized as record_date minus one trading day or any equivalent heuristic.",
                "Planned/approved issuance (PLANNED_NOT_EXECUTED) stays planned/approved unless the retained record itself carries execution evidence; announcement is never treated as execution.",
                "A CONFLICTING_EVIDENCE event's conflicting dates are never silently resolved to one value by source preference.",
                "An upcoming or recent event was itself known by the retained known_at/published_at boundary; this context never admits future-unannounced information.",
            ],
        })
    return context


_RISK_REGISTER_FORBIDDEN_USES = {
    "numeric_risk_score", "risk_adjusted_return", "expected_loss", "VaR", "probability",
    "position_size", "participation_cap", "recommendation", "strategy_eligibility",
    "research_priority", "entry_action", "VALUE", "daily_decision_queue",
}
_RISK_REGISTER_ITEM_STATUSES = {"ESTABLISHED", "WATCH", "DATA_LIMITATION", "UNRESOLVED_CONFLICT"}
_RISK_REGISTER_STATUSES = {"MATERIAL_RISKS_ESTABLISHED", "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE"}
_RISK_REGISTER_SOURCE_CONTEXT_NAMES = {"historical", "leadership", "financial", "event", "valuation"}


def _risk_register_item_valid(item: Any, *, ticker: str, expected_status: str) -> bool:
    """One risk-register item: category membership fixes its own status exactly."""
    if not isinstance(item, Mapping):
        return False
    severity = item.get("severity_band")
    source_as_of = item.get("source_as_of")
    return (
        isinstance(item.get("risk_id"), str) and item["risk_id"].startswith(f"{ticker}:")
        and isinstance(item.get("risk_domain"), str) and item["risk_domain"]
        and isinstance(item.get("risk_type"), str) and item["risk_type"]
        and item.get("status") == expected_status
        and item.get("status") in _RISK_REGISTER_ITEM_STATUSES
        and (severity is None or isinstance(severity, str))
        and isinstance(item.get("source_context"), str) and item["source_context"]
        and (source_as_of is None or isinstance(source_as_of, str))
        and isinstance(item.get("observed_facts"), Mapping)
        and isinstance(item.get("reason_codes"), list)
        and isinstance(item.get("authority_tier"), str) and item["authority_tier"]
        and isinstance(item.get("allowed_uses"), list)
        and isinstance(item.get("prohibited_uses"), list)
        and _RISK_REGISTER_FORBIDDEN_USES <= set(item["prohibited_uses"])
    )


def _current_research_risk_register_valid(raw: Any, *, ticker: str) -> bool:
    if not isinstance(raw, Mapping):
        return False
    source_contexts = raw.get("source_contexts")
    risk_register = raw.get("risk_register")
    blocked_outputs = raw.get("blocked_outputs")
    authority_boundary = raw.get("authority_boundary")
    if not (
        raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and isinstance(raw.get("source_artifact_identity"), str)
        and raw["source_artifact_identity"].startswith("current_research_risk_register:")
        and isinstance(source_contexts, Mapping)
        and _RISK_REGISTER_SOURCE_CONTEXT_NAMES <= set(source_contexts)
        and all(
            isinstance(source_contexts[name], Mapping) and isinstance(source_contexts[name].get("available"), bool)
            for name in _RISK_REGISTER_SOURCE_CONTEXT_NAMES
        )
        and isinstance(risk_register, Mapping)
        and isinstance(blocked_outputs, Mapping)
        and all(blocked_outputs.get(use) == "NOT_EMITTED_OR_MODIFIED" for use in _RISK_REGISTER_FORBIDDEN_USES)
        and isinstance(authority_boundary, Mapping)
        and authority_boundary.get("is_actionable") is False
        and authority_boundary.get("no_numeric_risk_score") is True
        and authority_boundary.get("absence_is_not_low_risk") is True
        and authority_boundary.get("data_limitation_is_not_economic_risk") is True
        and authority_boundary.get("source_sessions_preserved_independently") is True
        and authority_boundary.get("no_upstream_decision_mutation") is True
        and authority_boundary.get("no_sizing_or_participation") is True
        and authority_boundary.get("pit") == "BLOCKED"
    ):
        return False
    material = risk_register.get("material_risks")
    watch = risk_register.get("watch_risks")
    limitations = risk_register.get("data_authority_limitations")
    conflicts = risk_register.get("unresolved_conflicts")
    if not (
        risk_register.get("ticker") == ticker
        and isinstance(material, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="ESTABLISHED") for i in material)
        and isinstance(watch, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="WATCH") for i in watch)
        and isinstance(limitations, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="DATA_LIMITATION") for i in limitations)
        and isinstance(conflicts, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="UNRESOLVED_CONFLICT") for i in conflicts)
        and risk_register.get("risk_register_status") in _RISK_REGISTER_STATUSES
        # The absence-is-not-low-risk semantic, hard-checked: whether material risk exists
        # is exactly what selects between the two status values, never independently set.
        and (
            (bool(material) and risk_register["risk_register_status"] == "MATERIAL_RISKS_ESTABLISHED")
            or (not material and risk_register["risk_register_status"] == "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE")
        )
    ):
        return False
    return True


def current_research_risk_register_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed pass-through for the opt-in current research risk register.

    Canonical location: tickers[ticker].current_research_risk_register, attached by
    stock-core-private's export_ai_bundle.py only with
    --include-current-research-risk-register. A descriptive, multi-domain projection of
    already-retained context (historical/leadership/financial/event/valuation), never a
    numeric score, probability, expected loss, VaR, sizing, or upstream-decision mutation.
    Absence of an emitted material_risks item means only
    NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE, never LOW_RISK/SAFE. Consumer
    performs no recomputation of any risk classification and never merges
    material_risks/watch_risks/data_authority_limitations/unresolved_conflicts into one list.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_research_risk_register") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not _current_research_risk_register_valid(raw, ticker=ticker):
        return {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_research_risk_register_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_current_research_risk_register_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_research_risk_register_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_research_risk_register"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_research_risk_register",
            "transformation": "Pass through the Producer's current multi-domain research risk register verbatim: each item's risk_id, risk_domain, risk_type, status, severity_band, source_context, source_as_of, observed_facts, reason_codes, and authority_tier, keeping material_risks, watch_risks, data_authority_limitations, and unresolved_conflicts as four separate lists, plus risk_register_status, per-source session identities, blocked outputs, and authority boundary. Consumer performs no recomputation of any risk classification, severity, or status, and never collapses the four categories into one.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-research-risk-register).",
                "No numeric risk score, risk-adjusted return, expected loss, VaR, or probability is ever computed or implied by this section.",
                "An empty material_risks list means NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE only -- never LOW_RISK, SAFE, or suitable for large sizing.",
                "A data_authority_limitation (e.g. blocked valuation authority, unknown sector, missing exact-session data) is a coverage gap, never itself an investment-risk direction or a cheapness/expense conclusion.",
                "An unresolved_conflicts item is reported as an unresolved conflict, never silently resolved to one interpretation.",
                "strategy_eligibility, research_priority, and entry_action are never modified by this section; each source context's own as-of identity stays independent and is never unified into one synthesized session.",
            ],
        })
    return context


_SCENARIO_CONTEXT_AXES = ("CONSERVATIVE", "BASE", "SPECULATIVE")
_SCENARIO_CONTEXT_STATUSES = {
    "SUPPORTED", "CONDITIONALLY_SUPPORTED", "NOT_SUPPORTED", "DATA_LIMITED", "UNQUALIFIED",
}
_SCENARIO_CONTEXT_FORBIDDEN_USES = {
    "probability", "expected_return", "target_price", "upside_pct", "downside_pct",
    "payoff_ratio", "intrinsic_value", "recommendation", "position_size", "sizing",
    "strategy_eligibility", "research_priority", "entry_action", "daily_decision_queue",
    "VALUE", "RAW_AS_TRADED", "PIT", "backtest",
}
_SCENARIO_CONTEXT_SOURCE_CONTEXT_NAMES = {
    "official_universe", "tactical", "opportunity", "historical", "leadership",
    "financial", "event", "valuation", "risk_register",
}
_SCENARIO_CONTEXT_AS_OF_NAMES = {
    "tactical", "opportunity", "historical", "leadership", "financial", "event", "valuation",
}


def _scenario_condition_item_valid(item: Any, *, expected_polarity: str) -> bool:
    """One evidence condition: domain/code/facts plus a polarity fixed by its own list."""
    if not isinstance(item, Mapping):
        return False
    return (
        isinstance(item.get("condition_id"), str) and bool(item["condition_id"])
        and isinstance(item.get("domain"), str) and bool(item["domain"])
        and item.get("polarity") == expected_polarity
        and isinstance(item.get("code"), str) and bool(item["code"])
        and isinstance(item.get("facts"), Mapping)
        and isinstance(item.get("authority_tier"), str) and bool(item["authority_tier"])
        and isinstance(item.get("source_context"), str) and bool(item["source_context"])
    )


def _scenario_mixed_item_valid(item: Any, *, ticker: str, condition_polarity: str, risk_status: str) -> bool:
    """A heterogeneous list: either a condition-shaped entry or a quoted risk-register item.

    authority_limitations/unresolved_questions are populated from two different sources in
    Producer (its own DATA_AUTHORITY/UNRESOLVED conditions, plus quoted risk-register
    data_authority_limitations/unresolved_conflicts items) -- both shapes are legitimate.
    """
    if _scenario_condition_item_valid(item, expected_polarity=condition_polarity):
        return True
    return _risk_register_item_valid(item, ticker=ticker, expected_status=risk_status)


def _scenario_gate_valid(gate: Any) -> bool:
    """A confirmation/invalidation gate: UNAVAILABLE never carries invented text."""
    if not isinstance(gate, Mapping):
        return False
    status = gate.get("status")
    text = gate.get("text")
    if status not in {"AVAILABLE", "UNAVAILABLE"}:
        return False
    if gate.get("invented") is not False:
        return False
    if not isinstance(gate.get("reason"), str) or not gate["reason"]:
        return False
    if status == "UNAVAILABLE":
        return text is None
    return isinstance(text, str) and bool(text)


def _scenario_axis_record_valid(
    row: Any, *, ticker: str, axis: str, decision_context: Mapping[str, Any], source_as_of: Mapping[str, Any],
) -> bool:
    if not isinstance(row, Mapping):
        return False
    confirmation = row.get("confirmation_conditions")
    invalidation = row.get("invalidation_conditions")
    material_risks = row.get("material_risks")
    limitations = row.get("authority_limitations")
    unresolved = row.get("unresolved_questions")
    evidence_refs = row.get("evidence_references")
    expected_material_risk_rule = (
        "MATERIAL_RISK_BLOCKS_CONSERVATIVE_SUPPORTED" if axis == "CONSERVATIVE" else "MATERIAL_RISK_LISTED_NOT_SCORED"
    )
    return (
        row.get("ticker") == ticker
        and row.get("scenario_axis") == axis
        and row.get("scenario_status") in _SCENARIO_CONTEXT_STATUSES
        and isinstance(row.get("status_rule"), str) and bool(row["status_rule"])
        and isinstance(row.get("status_reasons"), list) and all(isinstance(r, str) for r in row["status_reasons"])
        and row.get("source_as_of") == source_as_of
        and row.get("current_decision_context") == decision_context
        and isinstance(row.get("eligible_strategy_lanes"), list)
        and list(row["eligible_strategy_lanes"]) == list(decision_context.get("eligible_strategy_lanes") or [])
        and isinstance(row.get("supporting_conditions"), list)
        and all(_scenario_condition_item_valid(i, expected_polarity="SUPPORT") for i in row["supporting_conditions"])
        and isinstance(row.get("opposing_conditions"), list)
        and all(_scenario_condition_item_valid(i, expected_polarity="OPPOSE") for i in row["opposing_conditions"])
        and isinstance(confirmation, list) and len(confirmation) == 1 and _scenario_gate_valid(confirmation[0])
        and isinstance(invalidation, list) and len(invalidation) == 1 and _scenario_gate_valid(invalidation[0])
        and isinstance(material_risks, list)
        and all(_risk_register_item_valid(i, ticker=ticker, expected_status="ESTABLISHED") for i in material_risks)
        and isinstance(limitations, list)
        and all(_scenario_mixed_item_valid(i, ticker=ticker, condition_polarity="LIMITATION", risk_status="DATA_LIMITATION") for i in limitations)
        and isinstance(unresolved, list)
        and all(_scenario_mixed_item_valid(i, ticker=ticker, condition_polarity="UNRESOLVED", risk_status="UNRESOLVED_CONFLICT") for i in unresolved)
        and isinstance(evidence_refs, list)
        and len(evidence_refs) == len(_SCENARIO_CONTEXT_SOURCE_CONTEXT_NAMES)
        and {ref.get("source") for ref in evidence_refs if isinstance(ref, Mapping)} == _SCENARIO_CONTEXT_SOURCE_CONTEXT_NAMES
        and all(
            isinstance(ref, Mapping) and isinstance(ref.get("identity"), str) and bool(ref["identity"])
            for ref in evidence_refs
        )
        and row.get("allowed_uses") == ["CURRENT_RESEARCH_CONTEXT"]
        and isinstance(row.get("prohibited_uses"), list)
        and _SCENARIO_CONTEXT_FORBIDDEN_USES <= set(row["prohibited_uses"])
        and row.get("base_is_not_most_likely") == (True if axis == "BASE" else None)
        and row.get("evidence_standard_lowered") is False
        and row.get("material_risk_rule") == expected_material_risk_rule
        and row.get("does_not_modify_research_priority") is True
        and row.get("does_not_modify_strategy_eligibility") is True
        and row.get("does_not_modify_entry_action") is True
    )


def _current_research_scenario_context_valid(raw: Any, *, ticker: str) -> bool:
    if not isinstance(raw, Mapping):
        return False
    source_contexts = raw.get("source_contexts")
    scenario_context = raw.get("scenario_context")
    blocked_outputs = raw.get("blocked_outputs")
    authority_boundary = raw.get("authority_boundary")
    if not (
        raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and isinstance(raw.get("source_artifact_identity"), str)
        and raw["source_artifact_identity"].startswith("current_research_scenario_context:")
        and isinstance(source_contexts, Mapping)
        and _SCENARIO_CONTEXT_SOURCE_CONTEXT_NAMES <= set(source_contexts)
        and all(
            isinstance(source_contexts[name], Mapping) and isinstance(source_contexts[name].get("available"), bool)
            for name in _SCENARIO_CONTEXT_SOURCE_CONTEXT_NAMES
        )
        and isinstance(scenario_context, Mapping)
        and isinstance(blocked_outputs, Mapping)
        and all(blocked_outputs.get(use) == "NOT_EMITTED_OR_MODIFIED" for use in _SCENARIO_CONTEXT_FORBIDDEN_USES)
        and isinstance(authority_boundary, Mapping)
        and authority_boundary.get("is_actionable") is False
        and authority_boundary.get("research_only") is True
        and authority_boundary.get("no_probability") is True
        and authority_boundary.get("no_expected_return") is True
        and authority_boundary.get("no_target_price") is True
        and authority_boundary.get("no_sizing") is True
        and authority_boundary.get("no_recommendation") is True
        and authority_boundary.get("does_not_modify_research_priority") is True
        and authority_boundary.get("does_not_modify_strategy_eligibility") is True
        and authority_boundary.get("does_not_modify_entry_action") is True
        and authority_boundary.get("does_not_modify_daily_decision_queue") is True
        and authority_boundary.get("does_not_replace_evidence_bound_bear_base_bull") is True
        and authority_boundary.get("data_limitation_is_not_economic_risk") is True
        and authority_boundary.get("raw_as_traded") == "NOT_PROMOTED"
        and authority_boundary.get("pit") == "BLOCKED"
        and authority_boundary.get("backtest") == "NOT_EMITTED"
    ):
        return False
    decision_context = scenario_context.get("current_decision_context")
    axes = scenario_context.get("axes")
    record_source_as_of = scenario_context.get("source_as_of")
    record_blocked_outputs = scenario_context.get("blocked_outputs")
    if not (
        scenario_context.get("ticker") == ticker
        and isinstance(decision_context, Mapping)
        and decision_context.get("quoted_not_modified") is True
        and isinstance(decision_context.get("eligible_strategy_lanes"), list)
        and isinstance(record_source_as_of, Mapping)
        and _SCENARIO_CONTEXT_AS_OF_NAMES <= set(record_source_as_of)
        and isinstance(record_blocked_outputs, Mapping)
        and all(record_blocked_outputs.get(use) == "NOT_EMITTED_OR_MODIFIED" for use in _SCENARIO_CONTEXT_FORBIDDEN_USES)
        and isinstance(axes, Mapping)
        and set(axes) == set(_SCENARIO_CONTEXT_AXES)
    ):
        return False
    return all(
        _scenario_axis_record_valid(
            axes[axis], ticker=ticker, axis=axis,
            decision_context=decision_context, source_as_of=record_source_as_of,
        )
        for axis in _SCENARIO_CONTEXT_AXES
    )


def current_research_scenario_context_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed pass-through for the opt-in current research scenario context.

    Canonical location: tickers[ticker].current_research_scenario_context, attached by
    stock-core-private's export_ai_bundle.py only with
    --include-current-research-scenario-context. Three orthogonal research/decision-
    condition axes (CONSERVATIVE/BASE/SPECULATIVE) over already-retained tactical/
    opportunity/historical/leadership/financial/event/valuation/risk-register context --
    never a Bear/Base/Bull price scenario, a probability, a strategy lane, or an entry
    action. Consumer performs no recomputation of any axis status and never infers a
    missing confirmation or invalidation condition.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_research_scenario_context") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not _current_research_scenario_context_valid(raw, ticker=ticker):
        return {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_research_scenario_context_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_current_research_scenario_context_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_research_scenario_context_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_research_scenario_context"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_research_scenario_context",
            "transformation": "Pass through the Producer's current CONSERVATIVE/BASE/SPECULATIVE research scenario context verbatim: each axis's scenario_status, status_rule, status_reasons, supporting/opposing conditions, confirmation/invalidation gates, material risks, authority limitations, unresolved questions, evidence references, and allowed/prohibited uses, plus the shared current_decision_context, per-source as-of identities, blocked outputs, and authority boundary. Consumer performs no recomputation of any axis status and never infers a missing confirmation or invalidation condition.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-research-scenario-context).",
                "CONSERVATIVE, BASE, and SPECULATIVE are research/decision-condition axes, never bearish/neutral/bullish, low/medium/high return or probability buckets, or defensive/normal/aggressive position sizing.",
                "No scenario axis carries a probability, target price, expected return, or sizing figure; BASE is never a most-likely claim and SPECULATIVE is never a higher-expected-return or bullish claim.",
                "A scenario axis may explain an existing upstream entry_action/research_priority/strategy-eligibility state but can never modify it: if entry_action is WAIT, it stays WAIT regardless of any axis's status.",
                "An UNAVAILABLE confirmation or invalidation gate stays unavailable; this section never invents a price level, financial threshold, event date, or target.",
                "This sibling is additive to, and never replaces, the existing evidence-bound Bear/Base/Bull scenario overlay.",
            ],
        })
    return context


_MARKET_WIDE_HISTORICAL_RESEARCH_CONTEXT_STATUSES = {
    "AVAILABLE", "PARTIAL", "INSUFFICIENT_HISTORY", "MISSING", "NOT_APPLICABLE",
}
_MARKET_WIDE_HISTORICAL_STRUCTURAL_STATES = {
    "TREND_CONTINUATION", "MATURE_TREND", "BASE", "EARLY_REVERSAL", "DETERIORATION", "INDETERMINATE",
}
_MARKET_WIDE_HISTORICAL_FIELD_NAMES = (
    "trailing_range", "fifty_two_week_range", "drawdown", "volatility_regime", "momentum",
    "ma_alignment", "relative_volume", "technical_state_frequency", "structural_state",
)
_MARKET_WIDE_CURRENT_VALUATION_RESEARCH_LABELS = {
    "CURRENT_RESEARCH_ONLY", "NOT_AUTHORITATIVE", "NOT_PIT", "NOT_FOR_TARGET_PRICE",
    "NOT_FOR_SIZING", "NOT_FOR_EXECUTION", "NOT_FOR_VALUE_STRATEGY",
}
_MARKET_WIDE_CURRENT_VALUATION_RESEARCH_FORBIDDEN_USES = {
    "AUTHORITATIVE_VALUATION", "VALUE_STRATEGY_ELIGIBILITY", "TARGET_PRICE", "INTRINSIC_VALUE",
    "DCF", "SIZING", "EXECUTION", "RANKING", "RECOMMENDATION", "PIT",
}


def _market_wide_historical_research_context_valid(raw: Mapping[str, Any], ticker: str) -> bool:
    """Validate the Producer's explicitly non-authoritative historical envelope only."""
    history = raw.get("history")
    in_scope = raw.get("in_current_descriptive_scope")
    context_status = raw.get("context_status")
    structural = raw.get("structural_state")
    authority_boundary = raw.get("authority_boundary")
    if not (
        raw.get("ticker") == ticker
        and raw.get("status") in {"available", "not_available"}
        and raw.get("is_actionable") is False
        and raw.get("research_mode") == "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER"
        and isinstance(raw.get("session"), str)
        and isinstance(raw.get("source_artifact_identity"), str)
        and raw["source_artifact_identity"].startswith("market_wide_historical_research_context:")
        and isinstance(raw.get("coverage"), Mapping)
        and isinstance(raw.get("blocked_outputs"), Mapping)
        and isinstance(in_scope, bool)
        and context_status in _MARKET_WIDE_HISTORICAL_RESEARCH_CONTEXT_STATUSES
        and isinstance(authority_boundary, Mapping)
        and authority_boundary.get("research_mode") == "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER"
        and authority_boundary.get("price_basis") == "ADJUSTED_RETROSPECTIVE"
        and authority_boundary.get("RAW_AS_TRADED") == "NOT_PROMOTED"
        and authority_boundary.get("PIT") == "BLOCKED"
    ):
        return False
    if in_scope is False:
        return (
            raw.get("status") == "not_available"
            and context_status == "NOT_APPLICABLE"
            and raw.get("as_of_session") is None
            and raw.get("is_current_session") is False
        )
    if not (
        raw.get("status") == "available"
        and isinstance(history, Mapping)
        and history.get("price_basis") == "ADJUSTED_RETROSPECTIVE"
        and history.get("raw_as_traded") == "NOT_PROMOTED"
        and history.get("historical_pit_eligible") is False
        and all(isinstance(raw.get(name), Mapping) for name in _MARKET_WIDE_HISTORICAL_FIELD_NAMES)
        and isinstance(structural, Mapping)
        and structural.get("status") in _MARKET_WIDE_HISTORICAL_RESEARCH_CONTEXT_STATUSES | {"BLOCKED"}
    ):
        return False
    if structural.get("status") == "AVAILABLE" and not (
        structural.get("value") in _MARKET_WIDE_HISTORICAL_STRUCTURAL_STATES
        and structural.get("not_entry_state") is True
        and structural.get("not_strategy_eligibility") is True
    ):
        return False
    as_of = raw.get("as_of_session")
    if raw.get("is_current_session") is True:
        if not isinstance(as_of, str) or as_of != raw["session"]:
            return False
    elif as_of is not None and not isinstance(as_of, str):
        return False
    if isinstance(as_of, str) and history.get("last_session") != as_of:
        return False
    current_window = raw.get("current_feature_window")
    if isinstance(current_window, Mapping) and not (
        current_window.get("price_basis") == "ADJUSTED_RETROSPECTIVE"
        and current_window.get("historical_pit_eligible") is False
    ):
        return False
    return True


def market_wide_historical_research_context_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed pass-through for retrospective descriptive within-ticker research."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("market_wide_historical_research_context") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not isinstance(raw, Mapping) or not _market_wide_historical_research_context_valid(raw, ticker):
        return {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["market_wide_historical_research_context_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_market_wide_historical_research_context_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = market_wide_historical_research_context_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["market_wide_historical_research_context"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json",
            "source_dataset": "market_wide_historical_research_context",
            "transformation": "Pass through the Producer's retrospective descriptive within-ticker history, including range, drawdown, technical persistence, structural state, blockers, session, and lineage verbatim; Consumer derives no historical result.",
            "limitations": [
                "RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER only: adjusted retained history is not RAW_AS_TRADED, historical PIT, performance, alpha, win-probability, or executable backtest evidence.",
                "structural_state is descriptive only and remains explicitly not an entry state or strategy-eligibility signal; this layer does not alter research priority, entry action, sizing, or recommendation authority.",
                "Relative volume is provider-scoped descriptive context, not liquidity, turnover, ADV/ADTV, sizing, or execution authority.",
                "Optional field: an absent sibling stays absent; malformed supplied content remains an explicit non-actionable malformed record.",
            ],
        })
    return context


def market_wide_current_valuation_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Validate and pass through the Producer's current-only valuation snapshot.

    The Consumer deliberately accepts only the bounded, non-actionable envelope;
    it never recomputes values or upgrades stale shares/provider fundamentals.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("market_wide_current_valuation") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    shadow = raw.get("shadow_proxy_valuation") if isinstance(raw, Mapping) else None
    shadow_valid = shadow is None or (
        isinstance(shadow, Mapping) and shadow.get("share_basis_type") == "PROVIDER_ISSUED_SHARE_PROXY"
        and shadow.get("authority_tier") == "SHADOW_RESEARCH_ONLY" and shadow.get("is_actionable") is False
        and isinstance(shadow.get("source_observation"), Mapping) and isinstance(shadow.get("metrics"), Mapping)
        and "COMMON_SHARES_OUTSTANDING" in set(shadow.get("forbidden_uses") or [])
        and all(
            isinstance(metric, Mapping) and metric.get("status") in {"SHADOW_PROXY_READY", "BLOCKED", "NOT_APPLICABLE"}
            and "SHADOW" in set(metric.get("labels") or []) and "NON_AUTHORITATIVE" in set(metric.get("labels") or [])
            and ((metric.get("status") == "SHADOW_PROXY_READY" and isinstance(metric.get("value"), (int, float)))
                 or (metric.get("status") != "SHADOW_PROXY_READY" and metric.get("value") is None))
            for metric in shadow["metrics"].values()
        )
    )
    metrics = raw.get("metrics") if isinstance(raw, Mapping) else None
    price_input = raw.get("price_input") if isinstance(raw, Mapping) else None
    price_session = price_input.get("session") if isinstance(price_input, Mapping) else None
    forbidden_top_level_fields = {
        "target_price", "intrinsic_value", "dcf", "recommendation", "entry_action",
        "position_size", "position_sizing", "buy_sell",
    }
    valid = (
        isinstance(raw, Mapping) and raw.get("ticker") == ticker and raw.get("status") == "current_valuation_snapshot"
        and raw.get("is_actionable") is False and isinstance(raw.get("entity_class"), str)
        and isinstance(raw.get("price_input"), Mapping) and isinstance(raw.get("share_basis_input"), Mapping)
        and isinstance(raw.get("financial_input"), Mapping) and isinstance(raw.get("metrics"), Mapping)
        and not (forbidden_top_level_fields & set(raw))
        and all(
            isinstance(metric, Mapping) and metric.get("status") in {"READY", "RESEARCH_USABLE", "BLOCKED", "NOT_APPLICABLE"}
            and ((metric.get("status") in {"READY", "RESEARCH_USABLE"}
                  and isinstance(metric.get("value"), (int, float)) and not isinstance(metric.get("value"), bool))
                 or (metric.get("status") not in {"READY", "RESEARCH_USABLE"} and metric.get("value") is None))
            and (metric.get("status") not in {"READY", "RESEARCH_USABLE"} or (
                isinstance(price_session, str) and metric.get("price_session") == price_session
            ))
            and (metric.get("status") != "RESEARCH_USABLE" or (
                isinstance(metric.get("metric_id"), str)
                and metric.get("is_actionable") is False
                and metric.get("historical_pit_eligible") is False
                and isinstance(metric.get("labels"), list)
                and _MARKET_WIDE_CURRENT_VALUATION_RESEARCH_LABELS.issubset(set(metric["labels"]))
                and metric.get("allowed_uses") == ["CURRENT_RESEARCH_ONLY"]
                and isinstance(metric.get("forbidden_uses"), list)
                and _MARKET_WIDE_CURRENT_VALUATION_RESEARCH_FORBIDDEN_USES.issubset(set(metric["forbidden_uses"]))
                and "CURRENT_RESEARCH_ONLY" in set(metric.get("allowed_uses") or [])
            ))
            for metric in metrics.values()
        )
        and (not isinstance(raw.get("source_artifact_identity"), str)
             or raw["source_artifact_identity"].startswith("market_wide_current_valuation:"))
        and ("source_session" not in raw or not isinstance(price_session, str) or raw.get("source_session") == price_session)
        and shadow_valid
    )
    if not valid:
        return {"status": "malformed", "is_actionable": False,
                "reason_codes": ["market_wide_current_valuation_malformed"]}
    return copy.deepcopy(dict(raw))


def apply_bundle_market_wide_current_valuation_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = market_wide_current_valuation_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["market_wide_current_valuation"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "market_wide_current_valuation",
            "transformation": "Pass through Producer current valuation inputs, per-method applicability/status, share-authority tiers, financial period/basis, lineage, and blockers verbatim.",
            "limitations": ["CURRENT_RESEARCH only; never historical PIT or RAW_AS_TRADED.", "RESEARCH_USABLE is research-only and never becomes READY, authoritative valuation, or VALUE eligibility.", "NOT_APPLICABLE is preserved per method and does not globally block the ticker.", "No target price, intrinsic value, DCF, ranking, recommendation, sizing, or portfolio instruction.", "Consumer does not upgrade share or financial authority, or combine valuation methods across differing price sessions."],
        })
    return context


_SECTOR_AWARE_EXPECTATIONS = {
    "MARKET_AND_FUNDAMENTALS_ALIGNED_POSITIVE", "MARKET_AND_FUNDAMENTALS_ALIGNED_NEGATIVE",
    "MARKET_STRENGTH_AHEAD_OF_FUNDAMENTALS", "FUNDAMENTALS_AHEAD_OF_MARKET",
    "TECHNICAL_RECOVERY_WITH_FUNDAMENTAL_UNCERTAINTY", "MIXED_OR_INSUFFICIENT_EVIDENCE",
}
_SECTOR_AWARE_MEMBERSHIP_LEVELS = {"QUALIFIED_ENTITY_CLASS", "RETAINED_PROVIDER_DESCRIPTIVE_INDUSTRY", "INSUFFICIENT"}
_SECTOR_AWARE_TECHNICAL_STATUSES = {"AVAILABLE", "INSUFFICIENT_COHORT_OR_METRIC_UNAVAILABLE"}
_SECTOR_AWARE_FUNDAMENTAL_STATUSES = {"AVAILABLE", "UNAVAILABLE", "INSUFFICIENT_COHORT"}


def sector_aware_relative_research_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed, verbatim Producer contract; Consumer never reclassifies peers."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("sector_aware_relative_research") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    membership = raw.get("peer_membership") if isinstance(raw, Mapping) else None
    technical = raw.get("technical_peer_context") if isinstance(raw, Mapping) else None
    fundamental = raw.get("fundamental_peer_context") if isinstance(raw, Mapping) else None
    valuation = raw.get("valuation_peer_context") if isinstance(raw, Mapping) else None
    expectation = raw.get("expectations_context") if isinstance(raw, Mapping) else None
    boundary = raw.get("authority_boundary") if isinstance(raw, Mapping) else None
    valid = (
        isinstance(raw, Mapping) and raw.get("ticker") == ticker and raw.get("is_actionable") is False
        and isinstance(raw.get("source_artifact_identity"), str) and raw["source_artifact_identity"].startswith("sector_aware_relative_research:")
        and isinstance(raw.get("source_session"), str) and isinstance(raw.get("coverage"), Mapping)
        and isinstance(membership, Mapping) and isinstance(membership.get("entity_class"), str)
        and isinstance(membership.get("peer_group_id"), str) and isinstance(membership.get("peer_group_label"), str)
        and membership.get("peer_group_level") in _SECTOR_AWARE_MEMBERSHIP_LEVELS
        and membership.get("status") in {"AVAILABLE", "INSUFFICIENT_COHORT"} and isinstance(membership.get("member_count"), int)
        and isinstance(technical, Mapping) and technical.get("status") in _SECTOR_AWARE_TECHNICAL_STATUSES and isinstance(technical.get("eligible_count"), int) and isinstance(technical.get("metrics"), Mapping)
        and isinstance(fundamental, Mapping) and fundamental.get("status") in _SECTOR_AWARE_FUNDAMENTAL_STATUSES and isinstance(fundamental.get("dimensions"), Mapping)
        and isinstance(valuation, Mapping) and valuation.get("status") == "VALUATION_PEER_CONTEXT_UNAVAILABLE" and valuation.get("eligible_count") == 0
        and isinstance(expectation, Mapping) and expectation.get("state") in _SECTOR_AWARE_EXPECTATIONS and expectation.get("descriptive_only") is True
        and isinstance(raw.get("data_gaps"), list) and isinstance(raw.get("authority_limitations"), list)
        and isinstance(boundary, Mapping) and boundary.get("recommendation") is False and boundary.get("ranking") is False
    )
    if not valid:
        return {"status": "malformed", "is_actionable": False, "reason_codes": ["sector_aware_relative_research_malformed"]}
    return copy.deepcopy(dict(raw))


def apply_bundle_sector_aware_relative_research_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = sector_aware_relative_research_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["sector_aware_relative_research"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "sector_aware_relative_research",
            "transformation": "Pass through Producer peer membership, retained comparison coverage, factual relative context, and expectations state verbatim; Consumer performs no peer selection, score, classification, or valuation computation.",
            "limitations": ["Descriptive-only and opt-in.", "No ranking, recommendation, target, probability, alpha, sizing, or valuation-peer claim.", "A malformed Producer record fails closed and is not reinterpreted by the Consumer."],
        })
    return context


_CURRENT_EVIDENCE_SCENARIO_DISPOSITIONS = {"SCENARIO_READY", "SCENARIO_PARTIAL", "SCENARIO_INSUFFICIENT_DATA", "SCENARIO_NOT_APPLICABLE"}


def current_market_flow_positioning_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the producer-owned current-flow record without interpretation."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_market_flow_positioning") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    sections = ("traded_value", "foreign_flow", "foreign_room", "proprietary_flow", "active_order_context")
    valid = (isinstance(raw, Mapping) and raw.get("ticker") == ticker and raw.get("is_actionable") is False
             and isinstance(raw.get("source_artifact_identity"), str) and raw["source_artifact_identity"].startswith("current_market_flow_positioning:")
             and isinstance(raw.get("source_session"), str) and isinstance(raw.get("price_flow_relationships"), list)
             and isinstance(raw.get("authority_boundary"), Mapping)
             and raw["authority_boundary"].get("liquidity_sizing_execution") == "BLOCKED"
             and all(isinstance(raw.get(name), Mapping) and raw[name].get("status") in {"AVAILABLE", "MISSING", "PROVIDER_REJECTED", "RATE_LIMITED", "SEMANTIC_BLOCKED", "NOT_APPLICABLE"} for name in sections))
    if not valid:
        return {"status": "malformed", "is_actionable": False, "reason_codes": ["current_market_flow_positioning_malformed"]}
    return copy.deepcopy(dict(raw))


def apply_bundle_current_market_flow_positioning_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_market_flow_positioning_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_market_flow_positioning"] = contract
        context.setdefault("provenance", []).append({"source_file": "analysis_bundle.json", "source_dataset": "current_market_flow_positioning", "transformation": "Verbatim Producer pass-through; Consumer does not recompute flow, reconcile providers, or infer intent/causality.", "limitations": ["No smart-money, institutional-intent, causal, recommendation, sizing, liquidity, or execution claim."]})
    return context


def current_evidence_bound_scenario_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Validate the additive current scenario envelope without interpreting a case."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_evidence_bound_scenario") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    cases = {name: raw.get(name + "_case") for name in ("bear", "base", "bull")} if isinstance(raw, Mapping) else {}
    def valid_case(name: str, case: Any) -> bool:
        return (isinstance(case, Mapping) and isinstance(case.get("case_id"), str)
                and case.get("probability_status") == "UNKNOWN_UNCALIBRATED"
                and case.get("case_status") in {"CONDITIONAL", "INSUFFICIENT_EVIDENCE"}
                and isinstance(case.get("data_gaps"), list) and isinstance(case.get("authority_limitations"), list)
                and ((name == "base" and isinstance(case.get("continuation_conditions"), list)
                     and isinstance(case.get("transition_to_bull_conditions"), list)
                     and isinstance(case.get("transition_to_bear_conditions"), list))
                     or (name != "base" and isinstance(case.get("required_confirmations"), list)
                         and "invalidation" in case and isinstance(case.get("counter_evidence"), list))))
    valid = (
        isinstance(raw, Mapping) and raw.get("ticker") == ticker and raw.get("is_actionable") is False
        and isinstance(raw.get("source_artifact_identity"), str) and raw["source_artifact_identity"].startswith("current_evidence_bound_scenario:")
        and isinstance(raw.get("source_session"), str) and raw.get("scenario_disposition") in _CURRENT_EVIDENCE_SCENARIO_DISPOSITIONS
        and raw.get("probability_status") == "UNKNOWN_UNCALIBRATED" and isinstance(raw.get("scenario_drivers"), Mapping)
        and all(valid_case(name, case) for name, case in cases.items())
        and isinstance(raw.get("authority_boundary"), Mapping) and raw["authority_boundary"].get("probabilities") == "UNKNOWN_UNCALIBRATED"
        and isinstance(raw.get("authority_limitations"), list)
    )
    if not valid:
        return {"status": "malformed", "is_actionable": False, "reason_codes": ["current_evidence_bound_scenario_malformed"]}
    return copy.deepcopy(dict(raw))


def apply_bundle_current_evidence_bound_scenario_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_evidence_bound_scenario_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_evidence_bound_scenario"] = contract
        context.setdefault("provenance", []).append({"source_file": "analysis_bundle.json", "source_dataset": "current_evidence_bound_scenario", "transformation": "Pass through Producer conditional Bear/Base/Bull cases verbatim; Consumer creates no scenario, probability, target, score, or recommendation.", "limitations": ["Base is a current-continuation reference, not most likely.", "Probability is UNKNOWN_UNCALIBRATED.", "AI must not convert a conditional case into a prediction or investment instruction."]})
    return context


def current_daily_decision_research_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail closed on malformed daily product cards; do not synthesize analyst prose."""
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_daily_decision_research") if isinstance(entry, Mapping) else None
    state = raw.get("current_decision_state") if isinstance(raw, Mapping) else None
    scenario = raw.get("scenario") if isinstance(raw, Mapping) else None
    claims = raw.get("thesis_counter_thesis") if isinstance(raw, Mapping) else None
    valid = (
        isinstance(raw, Mapping) and raw.get("ticker") == ticker and raw.get("is_actionable") is False
        and isinstance(raw.get("source_artifact_identity"), str) and raw["source_artifact_identity"].startswith("current_daily_decision_research_product:")
        and isinstance(raw.get("source_session"), str) and isinstance(raw.get("market_brief"), Mapping)
        and raw["market_brief"].get("source_market_session") == raw.get("source_session")
        and isinstance(state, Mapping) and state.get("is_actionable") is False and state.get("requires_human_review") is True
        and state.get("position_sizing_status") == "NOT_EVALUATED" and isinstance(state.get("entry_action"), (str, type(None)))
        and isinstance(raw.get("peer_context"), Mapping) and isinstance(raw.get("fundamental_context"), Mapping) and isinstance(raw.get("valuation_context"), Mapping)
        and ("corporate_intelligence_context" not in raw or (isinstance(raw.get("corporate_intelligence_context"), Mapping) and raw["corporate_intelligence_context"].get("is_actionable") is False and isinstance(raw["corporate_intelligence_context"].get("confirmed"), list) and isinstance(raw["corporate_intelligence_context"].get("planned_or_pending"), list)))
        and ("strategy_fit" not in raw or (isinstance(raw.get("strategy_fit"), Mapping) and raw["strategy_fit"].get("is_actionable") is False and isinstance(raw["strategy_fit"].get("eligible_strategy_ids"), list) and isinstance(raw["strategy_fit"].get("strategies"), list) and all(isinstance(item, Mapping) and isinstance(item.get("strategy_id"), str) and item.get("status") in {"ELIGIBLE", "PARTIAL", "BLOCKED", "NOT_APPLICABLE", "INSUFFICIENT_DATA"} for item in raw["strategy_fit"]["strategies"])))
        and ("portfolio_risk" not in raw or (isinstance(raw.get("portfolio_risk"), Mapping) and raw["portfolio_risk"].get("contract_version") == "current_portfolio_risk_envelope/v1" and isinstance(raw["portfolio_risk"].get("portfolio_id"), str) and raw["portfolio_risk"].get("is_actionable") is False and raw["portfolio_risk"].get("position_sizing_status") == "BLOCKED" and isinstance(raw["portfolio_risk"].get("blocked_risk_dimensions"), Mapping)))
        and ("macro_context" not in raw or (isinstance(raw.get("macro_context"), Mapping) and raw["macro_context"].get("is_actionable") is False and raw["macro_context"].get("status") in {"AVAILABLE", "UNAVAILABLE"} and (raw["macro_context"].get("status") != "AVAILABLE" or isinstance(raw["macro_context"].get("macro_artifact_identity"), str))))
        and isinstance(scenario, Mapping) and scenario.get("probability_status") == "UNKNOWN_UNCALIBRATED"
        and all(isinstance(scenario.get(name), Mapping) for name in ("bear_case", "base_case", "bull_case"))
        and isinstance(claims, Mapping) and all(isinstance(claims.get(name), list) for name in ("thesis", "counter_thesis", "questions_to_verify"))
        and all(claim.get("type") in {"FACT", "INFERENCE", "DATA_GAP", "QUESTION_TO_VERIFY"} and isinstance(claim.get("evidence_field"), str) for group in claims.values() for claim in group if isinstance(claim, Mapping))
        and isinstance(raw.get("authority_boundary"), Mapping) and raw["authority_boundary"].get("probability") == "UNKNOWN_UNCALIBRATED"
    )
    if not valid:
        return {"status": "malformed", "is_actionable": False, "reason_codes": ["current_daily_decision_research_malformed"]}
    return copy.deepcopy(dict(raw))


def apply_bundle_current_daily_decision_research_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_daily_decision_research_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_daily_decision_research"] = contract
        context.setdefault("provenance", []).append({"source_file": "analysis_bundle.json", "source_dataset": "current_daily_decision_research_product", "transformation": "Pass through the Producer daily human-review card and cited claim categories verbatim; Consumer does not derive a new state, peer group, scenario, thesis, or recommendation.", "limitations": ["Human-review research only; entry_action remains a deterministic tactical state.", "Any optional portfolio-risk envelope is explicit-input descriptive context only; Consumer does not derive allocation, sizing, or execution.", "No probability, target, expected return, ranking, recommendation, sizing, portfolio, or execution instruction."]})
    return context


def current_opportunity_decision_context_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the opt-in Producer daily opportunity-decision queue.

    The queue is a separate, all-lane research-priority contract. It is not the
    pre-existing 47-name tactical human-review cohort and it is not a new
    Consumer selection, ranking, or recommendation.
    """
    raw = bundle.get("daily_opportunity_decision_queue") if isinstance(bundle, Mapping) else None
    if raw is None:
        return None
    records = raw.get("records") if isinstance(raw, Mapping) else None
    record = records.get(ticker) if isinstance(records, Mapping) else None
    # A queue may be valid while a caller asks for a ticker outside its retained
    # universe. Preserve that absence rather than inventing an unavailable row.
    if isinstance(records, Mapping) and record is None:
        return None
    valid = (
        isinstance(raw, Mapping)
        and raw.get("contract_version") == "daily_opportunity_decision_queue/v1"
        and isinstance(raw.get("artifact_identity"), str)
        and raw["artifact_identity"].startswith("daily_opportunity_decision_queue:")
        and isinstance(raw.get("research_session"), str)
        and isinstance(raw.get("source_artifact_identities"), Mapping)
        and isinstance(records, Mapping)
        and isinstance(record, Mapping)
        and record.get("ticker") == ticker
        and isinstance(record.get("research_priority_tier"), str)
        and isinstance(record.get("eligible_strategies"), list)
        and all(isinstance(strategy, str) for strategy in record["eligible_strategies"])
        and isinstance(record.get("lane_specific_priority"), Mapping)
        and isinstance(record.get("entry_action"), (str, type(None)))
        and isinstance(record.get("entry_relevant"), bool)
        and record.get("is_actionable") is False
        and isinstance(record.get("authority_note"), str)
        and isinstance(record.get("invalidation_or_context_warnings"), list)
        and isinstance(raw.get("full_priority_now"), list)
        and all(isinstance(symbol, str) for symbol in raw["full_priority_now"])
        and isinstance(raw.get("lane_queues"), Mapping)
        and isinstance(raw.get("entry_relevant_summary"), Mapping)
        and isinstance(raw.get("multi_strategy"), Mapping)
        and isinstance(raw.get("primary_review_candidates"), Mapping)
        and isinstance(raw["primary_review_candidates"].get("tickers"), list)
        and raw["primary_review_candidates"].get("count") == len(raw["primary_review_candidates"]["tickers"])
        and raw["primary_review_candidates"].get("policy_kind") == "EXISTING_EVIDENCE_GATED_ELIGIBILITY_NOT_A_FIXED_CAP"
        and isinstance(raw.get("legacy_comparison"), Mapping)
        and isinstance(raw.get("authority_boundary"), Mapping)
        and raw["authority_boundary"].get("no_global_score") is True
        and raw["authority_boundary"].get("research_priority_is_not_trade_readiness") is True
        and raw["authority_boundary"].get("priority_now_is_not_buy_now") is True
        and raw["authority_boundary"].get("priority_now_is_not_sizing_ready") is True
    )
    if not valid:
        return {
            "status": "malformed",
            "is_actionable": False,
            "reason_codes": ["daily_opportunity_decision_queue_malformed"],
        }
    return copy.deepcopy({
        "contract_version": raw["contract_version"],
        "source_artifact_identity": raw["artifact_identity"],
        "research_session": raw["research_session"],
        "source_artifact_identities": raw["source_artifact_identities"],
        "ticker_record": record,
        # These are deliberately separate: the full all-lane research-priority
        # output must not collapse into the legacy tactical review policy.
        "full_priority_now": raw["full_priority_now"],
        "lane_queues": raw["lane_queues"],
        "entry_relevant_summary": raw["entry_relevant_summary"],
        "multi_strategy": raw["multi_strategy"],
        "legacy_human_review_queue": raw["primary_review_candidates"],
        "legacy_comparison": raw["legacy_comparison"],
        "authority_boundary": raw["authority_boundary"],
        "is_actionable": False,
    })


def apply_bundle_current_opportunity_decision_context_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_opportunity_decision_context_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_opportunity_decision_context"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json",
            "source_dataset": "daily_opportunity_decision_queue",
            "transformation": "Pass through the Producer's all-lane research-priority queue, target ticker record, full PRIORITY_NOW membership, lane queues, multi-strategy membership, and separately named legacy human-review policy. Consumer derives no rank, score, selection, entry action, sizing, or recommendation.",
            "limitations": [
                "Research priority is distinct from entry action, entry relevance, full-position readiness, and sizing authority.",
                "The legacy human-review queue is an existing evidence-gated tactical policy, not a fixed-cap or top-stock list.",
                "Producer warnings, blockers, source identities, and authority boundary remain binding; is_actionable=false.",
            ],
        })
    return context


_WATCHLIST_TACTICAL_ENTRY_CLASSIFIER_STATUSES = {"classified", "insufficient_data"}
_WATCHLIST_TACTICAL_ENTRY_STATES = {
    "DOWNTREND", "SELLING_PRESSURE_EASING", "EARLY_REVERSAL_CANDIDATE", "BASE_BUILDING",
    "SIDEWAYS_NEUTRAL", "BREAKOUT_READY", "UPTREND_CONFIRMED", "DISTRIBUTION_RISK", "BREAKDOWN_RISK",
}
_WATCHLIST_TACTICAL_ACTIONS = {
    "EARLY_ENTRY", "BUY_ON_CONFIRMATION", "ACCUMULATE_IN_BASE", "HOLD_DO_NOT_ADD", "WAIT", "AVOID", "REDUCE_EXIT",
}
# PRIMARY field for "should I enter" -- deliberately excludes HOLD_DO_NOT_ADD/REDUCE_EXIT, which
# presuppose a position this pipeline has no holdings input to confirm (2026-08-23 closeout
# correction: see watchlist_tactical_entry_classifier.py's module docstring in stock-core-private).
_WATCHLIST_TACTICAL_ENTRY_ACTIONS = {
    "EARLY_ENTRY", "BUY_ON_CONFIRMATION", "ACCUMULATE_IN_BASE", "WAIT", "AVOID",
}


def _watchlist_tactical_entry_classifier_valid(raw: Any, *, ticker: str) -> bool:
    if not isinstance(raw, Mapping):
        return False
    if not (
        raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and raw.get("status") in _WATCHLIST_TACTICAL_ENTRY_CLASSIFIER_STATUSES
        and isinstance(raw.get("market_state"), str)
        and isinstance(raw.get("ticker_structure_state"), str)
        and isinstance(raw.get("evidence_for"), list)
        and isinstance(raw.get("evidence_against"), list)
        and isinstance(raw.get("data_quality"), Mapping)
        and isinstance(raw.get("action"), str)
        and raw["action"] in _WATCHLIST_TACTICAL_ACTIONS
        and isinstance(raw.get("entry_action"), str)
        and raw["entry_action"] in _WATCHLIST_TACTICAL_ENTRY_ACTIONS
        and raw.get("is_full_position_ready") is False
        and raw.get("position_sizing_status") == "NOT_EVALUATED"
        and isinstance(raw.get("fundamental_context"), Mapping)
    ):
        return False
    if raw["status"] == "classified":
        if not (
            raw.get("entry_state") in _WATCHLIST_TACTICAL_ENTRY_STATES
            and isinstance(raw.get("confirmation_trigger"), str) and raw["confirmation_trigger"]
            and isinstance(raw.get("invalidation"), str) and raw["invalidation"]
            and isinstance(raw.get("horizon"), str)
        ):
            return False
    else:
        if raw.get("entry_state") is not None or raw.get("horizon") is not None:
            return False
    return True


def watchlist_tactical_entry_classifier_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Pass through the optional watchlist_tactical_entry_classifier contract verbatim.

    Canonical location: tickers[ticker].watchlist_tactical_entry_classifier -- the exact per-ticker
    record from stock-core-private's retained watchlist_tactical_entry_classifier artifact
    (tools/run_watchlist_tactical_entry_classifier.py), plus the bundle-level
    "state_taxonomy"/"action_taxonomy"/"action_by_entry_state"/"blocked_outputs"/"status"/
    "is_actionable" convenience fields export_ai_bundle.py's attach layer adds.

    A deterministic nine-state tactical entry classification (`entry_state`) built only from
    already-computed market_wide_current_descriptive_research/current_market_screening_
    opportunity_comparison_foundation/market_wide_current_fundamental_research lanes -- Consumer
    performs no recomputation of any technical feature, screening flag, percentile/bucket,
    fundamental tier, market_state, entry_state, action, entry_action, evidence,
    confirmation_trigger, invalidation, horizon, or is_full_position_ready. Two separate action
    fields travel with every record (2026-08-23 closeout correction, deliberately not conflated):
    `entry_action` is the PRIMARY field answering "should I enter" (fixed nine-to-five lookup,
    never `HOLD_DO_NOT_ADD`/`REDUCE_EXIT` since those presuppose a position this pipeline has no
    holdings input to confirm); `action` is a SECONDARY, position-management-conditional field
    (fixed nine-to-seven lookup) only meaningful if the reader already holds the ticker. Both are
    independently-derived-recommendation-free fixed lookups from `entry_state`.
    `is_full_position_ready` is revalidated (never just trusted) to be unconditionally `False` for
    every record, and `position_sizing_status` to be unconditionally `"NOT_EVALUATED"` -- position
    sizing is not implemented anywhere in this pipeline, so no record may ever claim full-position
    readiness, regardless of `entry_state`/`entry_action`/`action`.

    A ticker outside the retained artifact's universe is a separate case: the key is absent from
    the bundle entry entirely, so this function returns None (never a synthesized record). The
    field stays opt-in at the Producer builder level (export_ai_bundle.py defaults it off).
    Malformed/tampered input fails closed locally to an explicit malformed record, never silently
    upgraded or dropped.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("watchlist_tactical_entry_classifier") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not _watchlist_tactical_entry_classifier_valid(raw, ticker=ticker):
        return {
            "status": "malformed", "entry_state": None, "action": "WAIT", "entry_action": "WAIT",
            "is_actionable": False, "is_full_position_ready": False, "position_sizing_status": "NOT_EVALUATED",
            "reason_codes": ["watchlist_tactical_entry_classifier_malformed"],
        }
    return copy.deepcopy(dict(raw))


def apply_bundle_watchlist_tactical_entry_classifier_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = watchlist_tactical_entry_classifier_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["watchlist_tactical_entry_classifier"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "watchlist_tactical_entry_classifier",
            "transformation": "Pass through the Producer's deterministic nine-state tactical entry classification verbatim: market_state, ticker_structure_state, entry_state, entry_action, action, evidence_for/against, confirmation_trigger, invalidation, data_quality, horizon, is_full_position_ready, and position_sizing_status. Consumer performs no recomputation of any technical feature, screening flag, fundamental tier, or tactical classification.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-watchlist-tactical-entry-classifier).",
                "Descriptive tactical classification for human review only: is_actionable=false and requires_human_review=true always; never an execution instruction, order, or automated trade signal.",
                "entry_action is the primary field for 'should I enter' and never carries HOLD_DO_NOT_ADD/REDUCE_EXIT; action is secondary, position-management-conditional guidance only meaningful if the reader already holds the ticker -- never use action to decide whether to enter when holdings are unknown.",
                "is_full_position_ready is unconditionally false and position_sizing_status is unconditionally NOT_EVALUATED for every ticker; position sizing is not implemented anywhere in this pipeline and no record may ever claim full-position readiness.",
                "No fabricated probability, target price, expected-return figure, or portfolio-sizing formula exists anywhere in this lane.",
                "entry_state never asserts a confirmed bottom or top; EARLY_REVERSAL_CANDIDATE and BASE_BUILDING are early/base language only, carrying stricter invalidation than a confirmed-trend state.",
                "market_state is contemporaneous breadth/regime context shared by every ticker in the same build; it is never a market forecast, timing call, or a gate that overrides a ticker's own entry_state.",
                "Missing or BLOCKED fundamental-tier context narrows horizon toward the shortest tier and lowers data_quality.confidence; it does not by itself force a WAIT action when tactical evidence is otherwise sufficient.",
                "A ticker outside the retained artifact's universe has no key at all here, distinct from an in-universe insufficient_data record.",
            ],
        })
    return context


_CURRENT_RESEARCH_DECISION_PACKET_COMPONENT_NAMES = (
    "scenario", "risk_register", "market_sector", "financial_momentum",
    "corporate_event", "valuation", "historical",
)
# Maps each manifest component name to the key it appears under inside packet.components.
_CURRENT_RESEARCH_DECISION_PACKET_COMPONENT_KEY = {
    "scenario": "scenario_context",
    "risk_register": "risk_register",
    "market_sector": "market_sector_context",
    "financial_momentum": "financial_momentum_context",
    "corporate_event": "corporate_event_context",
    "valuation": "valuation_context",
    "historical": "historical_research_context",
}
_CURRENT_RESEARCH_DECISION_PACKET_MANIFEST_STATUSES = {"PRESENT", "ABSENT", "MALFORMED"}
_CURRENT_RESEARCH_DECISION_PACKET_STATUSES = {"COMPLETE_FOR_AVAILABLE_COMPONENTS", "PARTIAL"}
_CURRENT_RESEARCH_DECISION_PACKET_DECISION_CONTEXT_FIELDS = (
    "priority_tier", "entry_action", "eligible_strategies", "lane_priority", "tactical_state",
    "scenario_status", "blocking_reasons", "invalidation_or_context_warnings", "source_input_identities",
)
_CURRENT_RESEARCH_DECISION_PACKET_ALLOWED_USES = ["AI_RESEARCH_NARRATIVE", "HUMAN_REVIEW", "AUDIT_REPLAY"]
_CURRENT_RESEARCH_DECISION_PACKET_FORBIDDEN_USES = {
    "recommendation", "probability", "expected_return", "target_price", "position_size", "sizing",
}
_CURRENT_RESEARCH_DECISION_PACKET_AUTHORITY_BOUNDARY = {
    "is_actionable": False, "no_global_authority_score": True, "upstream_decisions_passthrough_only": True,
    "source_sessions_preserved_independently": True,
    "no_recommendation_probability_expected_return_target_or_sizing": True,
    "raw_as_traded": "NOT_PROMOTED", "pit": "BLOCKED",
}
_PACKET_VALUATION_METRIC_STATUSES = {"READY", "RESEARCH_USABLE", "BLOCKED", "NOT_APPLICABLE"}


def _current_research_decision_packet_manifest_entry_valid(name: str, entry: Any) -> bool:
    """One component_manifest entry: PRESENT/ABSENT/MALFORMED fixes which fields apply.

    This manifest is shared artifact-wide (identical across every ticker in the same
    packet); it records whether a sibling artifact was supplied to the packet builder at
    all, not whether this specific ticker's own row exists within it.
    """
    if not isinstance(entry, Mapping) or entry.get("component_name") != name:
        return False
    status = entry.get("status")
    source_identity = entry.get("source_artifact_identity")
    source_as_of = entry.get("source_as_of")
    if status == "ABSENT":
        return (
            source_identity is None and source_as_of is None
            and entry.get("authority_use_status") == "OPTIONAL_NOT_SUPPLIED"
        )
    if status == "MALFORMED":
        return (
            (source_identity is None or isinstance(source_identity, str))
            and source_as_of is None
            and entry.get("authority_use_status") == "FAIL_CLOSED_LOCALLY"
        )
    if status == "PRESENT":
        return (
            isinstance(source_identity, str) and bool(source_identity)
            and (source_as_of is None or isinstance(source_as_of, str))
            and isinstance(entry.get("source_content_hash"), str) and bool(entry["source_content_hash"])
            and entry.get("authority_use_status") == "PASSTHROUGH_ONLY"
        )
    return False


def _current_research_decision_packet_record_valid(record: Any, *, ticker: str, manifest: Mapping[str, Any]) -> bool:
    """One ticker's packet record: components/unresolved_components partition the 7 names."""
    if not isinstance(record, Mapping):
        return False
    decision = record.get("current_decision_context")
    components = record.get("components")
    unresolved = record.get("unresolved_components")
    if not (
        record.get("ticker") == ticker
        and record.get("packet_status") in _CURRENT_RESEARCH_DECISION_PACKET_STATUSES
        and isinstance(decision, Mapping)
        and set(_CURRENT_RESEARCH_DECISION_PACKET_DECISION_CONTEXT_FIELDS) <= set(decision)
        and isinstance(components, Mapping)
        and set(components) <= set(_CURRENT_RESEARCH_DECISION_PACKET_COMPONENT_KEY.values())
        and isinstance(unresolved, list)
        and set(unresolved) <= set(_CURRENT_RESEARCH_DECISION_PACKET_COMPONENT_NAMES)
        and record.get("authority_limitations") == [f"{name}_UNAVAILABLE_OR_MALFORMED" for name in sorted(unresolved)]
        and isinstance(record.get("warnings"), list)
        and record.get("allowed_uses") == _CURRENT_RESEARCH_DECISION_PACKET_ALLOWED_USES
        and isinstance(record.get("prohibited_uses"), list)
        and _CURRENT_RESEARCH_DECISION_PACKET_FORBIDDEN_USES <= set(record["prohibited_uses"])
        and record.get("is_actionable") is False
    ):
        return False
    # components/unresolved_components must exactly partition the 7 component names, and a
    # components entry can only exist for a manifest-PRESENT component (a manifest ABSENT/
    # MALFORMED component can never have a per-ticker payload) -- the converse does not
    # hold: manifest PRESENT does not guarantee this specific ticker has a row, since that
    # sibling's own per-ticker universe may not include this ticker at all.
    for name, key in _CURRENT_RESEARCH_DECISION_PACKET_COMPONENT_KEY.items():
        manifest_entry = manifest.get(name)
        manifest_status = manifest_entry.get("status") if isinstance(manifest_entry, Mapping) else None
        if key in components and manifest_status != "PRESENT":
            return False
        if key not in components and name not in unresolved:
            return False
        if key in components and name in unresolved:
            return False
    return True


def _packet_risk_register_component_valid(payload: Any, *, ticker: str) -> bool:
    """Reuses the existing risk-register item validator; Producer quotes this verbatim
    from the same current_research_risk_register artifact the direct sibling reads."""
    if not isinstance(payload, Mapping):
        return False
    material = payload.get("material_risks")
    watch = payload.get("watch_risks")
    limitations = payload.get("data_authority_limitations")
    conflicts = payload.get("unresolved_conflicts")
    if not (
        payload.get("ticker") == ticker
        and isinstance(material, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="ESTABLISHED") for i in material)
        and isinstance(watch, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="WATCH") for i in watch)
        and isinstance(limitations, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="DATA_LIMITATION") for i in limitations)
        and isinstance(conflicts, list) and all(_risk_register_item_valid(i, ticker=ticker, expected_status="UNRESOLVED_CONFLICT") for i in conflicts)
        and payload.get("risk_register_status") in _RISK_REGISTER_STATUSES
    ):
        return False
    return (
        (bool(material) and payload["risk_register_status"] == "MATERIAL_RISKS_ESTABLISHED")
        or (not material and payload["risk_register_status"] == "NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE")
    )


def _packet_financial_momentum_component_valid(payload: Any) -> bool:
    """Reuses the existing per-component validator; components is quoted verbatim."""
    if not isinstance(payload, Mapping):
        return False
    period = payload.get("as_of_financial_period")
    components = payload.get("components")
    return (
        (period is None or isinstance(period, str))
        and payload.get("financial_momentum_state") in _FINANCIAL_MOMENTUM_STATES
        and payload.get("coverage_status") in _FINANCIAL_MOMENTUM_COVERAGE_STATUSES
        and payload.get("evidence_tier") in _FINANCIAL_MOMENTUM_EVIDENCE_TIERS
        and isinstance(payload.get("blockers"), list) and isinstance(payload.get("warnings"), list)
        and isinstance(components, Mapping)
        and all(_financial_momentum_component_valid(c) for c in components.values())
    )


def _packet_market_sector_component_valid(payload: Any, *, ticker: str) -> bool:
    if not isinstance(payload, Mapping):
        return False
    market = payload.get("market")
    ticker_context = payload.get("ticker_context")
    if not (isinstance(market, Mapping) and isinstance(ticker_context, Mapping)):
        return False
    return (
        market.get("current_breadth_state") in _CURRENT_MARKET_SECTOR_BREADTH_STATES
        and ticker_context.get("ticker") == ticker
        and ticker_context.get("status") in _CURRENT_MARKET_SECTOR_TICKER_STATUSES
        and ticker_context.get("breadth_support_state") in _CURRENT_MARKET_SECTOR_BREADTH_SUPPORT_STATES
    )


def _packet_corporate_event_component_valid(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    events = payload.get("events")
    if not isinstance(events, list):
        return False
    for event in events:
        if not isinstance(event, Mapping):
            return False
        if event.get("event_status") not in _CORPORATE_EVENT_STATUSES:
            return False
        if event.get("temporal_completeness") not in _CORPORATE_EVENT_TEMPORAL_COMPLETENESS_STATES:
            return False
        for field in ("known_at", "published_at", "ex_date", "effective_date", "execution_date"):
            value = event.get(field)
            if value is not None and not isinstance(value, str):
                return False
    count_fields = (
        "qualified_event_count", "planned_unresolved_count", "temporal_incomplete_count",
        "data_limited_count", "conflicting_count",
    )
    return (
        isinstance(payload.get("research_session"), str) and bool(payload["research_session"])
        and all(isinstance(payload.get(f), int) and not isinstance(payload.get(f), bool) for f in count_fields)
    )


def _packet_valuation_component_valid(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    metrics = payload.get("metrics")
    if not isinstance(metrics, Mapping):
        return False
    valuation_session = payload.get("valuation_session")
    return (
        (valuation_session is None or isinstance(valuation_session, str))
        and all(isinstance(m, Mapping) and m.get("status") in _PACKET_VALUATION_METRIC_STATUSES for m in metrics.values())
    )


def _packet_historical_component_valid(payload: Any) -> bool:
    if not isinstance(payload, Mapping):
        return False
    authority_boundary = payload.get("authority_boundary")
    return (
        payload.get("context_status") in _MARKET_WIDE_HISTORICAL_RESEARCH_CONTEXT_STATUSES
        and isinstance(authority_boundary, Mapping)
        and authority_boundary.get("PIT") == "BLOCKED"
        and authority_boundary.get("RAW_AS_TRADED") == "NOT_PROMOTED"
    )


def _packet_scenario_component_valid(payload: Any) -> bool:
    """Shallow check only: this component is Producer's current_evidence_bound_scenario
    (Bear/Base/Bull), a sibling with its own already-tested but non-reusable (nested
    closure) case validator -- duplicating its full depth here would re-derive, not reuse,
    that logic, so this checks the same top-level identity fields the packet actually
    preserves without re-implementing per-case structural validation."""
    if not isinstance(payload, Mapping):
        return False
    cases = {name: payload.get(f"{name}_case") for name in ("bear", "base", "bull")}
    return (
        payload.get("scenario_disposition") in _CURRENT_EVIDENCE_SCENARIO_DISPOSITIONS
        and isinstance(payload.get("authority_limitations"), list)
        and all(
            isinstance(case, Mapping) and case.get("probability_status") == "UNKNOWN_UNCALIBRATED"
            for case in cases.values()
        )
    )


_PACKET_COMPONENT_VALIDATORS = {
    "risk_register": lambda payload, ticker: _packet_risk_register_component_valid(payload, ticker=ticker),
    "financial_momentum": lambda payload, ticker: _packet_financial_momentum_component_valid(payload),
    "market_sector": lambda payload, ticker: _packet_market_sector_component_valid(payload, ticker=ticker),
    "corporate_event": lambda payload, ticker: _packet_corporate_event_component_valid(payload),
    "valuation": lambda payload, ticker: _packet_valuation_component_valid(payload),
    "historical": lambda payload, ticker: _packet_historical_component_valid(payload),
    "scenario": lambda payload, ticker: _packet_scenario_component_valid(payload),
}


def _current_research_decision_packet_valid(raw: Any, *, ticker: str) -> bool:
    if not isinstance(raw, Mapping):
        return False
    manifest = raw.get("component_manifest")
    packet = raw.get("packet")
    if not (
        raw.get("ticker") == ticker
        and raw.get("is_actionable") is False
        and isinstance(raw.get("source_artifact_identity"), str)
        and raw["source_artifact_identity"].startswith("current_research_decision_packet:")
        and isinstance(manifest, Mapping)
        and set(manifest) == set(_CURRENT_RESEARCH_DECISION_PACKET_COMPONENT_NAMES)
        and all(_current_research_decision_packet_manifest_entry_valid(name, manifest[name]) for name in manifest)
        and raw.get("authority_boundary") == _CURRENT_RESEARCH_DECISION_PACKET_AUTHORITY_BOUNDARY
        and isinstance(packet, Mapping)
    ):
        return False
    return _current_research_decision_packet_record_valid(packet, ticker=ticker, manifest=manifest)


def current_research_decision_packet_contract(bundle: Mapping[str, Any] | None, ticker: str) -> dict[str, Any] | None:
    """Fail-closed pass-through for the opt-in current research decision packet.

    Canonical location: tickers[ticker].current_research_decision_packet, attached by
    stock-core-private's export_ai_bundle.py only with
    --include-current-research-decision-packet. A canonical current-session decision-
    support packet that packages already-retained sibling context (scenario, risk
    register, market/sector, financial momentum, corporate event, valuation, historical)
    for COHESION only -- it creates no new authority and never recomputes a sibling's own
    value. Fail-closed granularity is per-component: a component that fails Consumer's own
    structural check (even though Producer's own component_manifest marks it PRESENT) is
    locally neutralized to a malformed sentinel without invalidating the rest of the
    packet or any other component.

    The packet's own "scenario" component is Producer's current_evidence_bound_scenario
    (Bear/Base/Bull), never the separate current_research_scenario_context (CONSERVATIVE/
    BASE/SPECULATIVE) sibling this same module already passes through above -- confirmed
    by reading stock-core-private's current_research_decision_packet.py at the pinned
    schema commit, which imports content_identity only from current_evidence_bound_scenario.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(ticker) if isinstance(bundle, Mapping) else None
    raw = entry.get("current_research_decision_packet") if isinstance(entry, Mapping) else None
    if raw is None:
        return None
    if not _current_research_decision_packet_valid(raw, ticker=ticker):
        return {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["current_research_decision_packet_malformed"],
        }
    contract = copy.deepcopy(dict(raw))
    components = contract["packet"].get("components")
    if isinstance(components, Mapping):
        for name, key in _CURRENT_RESEARCH_DECISION_PACKET_COMPONENT_KEY.items():
            if key not in components:
                continue
            if not _PACKET_COMPONENT_VALIDATORS[name](components[key], ticker):
                components[key] = {
                    "status": "malformed",
                    "reason_codes": [f"current_research_decision_packet_component_{name}_malformed"],
                }
    return contract


def apply_bundle_current_research_decision_packet_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    contract = current_research_decision_packet_contract(bundle, str(context.get("ticker") or ""))
    if contract is not None:
        context["current_research_decision_packet"] = contract
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "current_research_decision_packet",
            "transformation": "Pass through the Producer's canonical current-session decision-support packet verbatim: ticker, packet identity, packet status, component manifest, deterministic current decision context, supplied component payloads, unresolved components, authority limitations, warnings, and allowed/prohibited uses. Consumer performs no recomputation of any upstream sibling value; a component that fails Consumer's own structural check is locally replaced with an explicit malformed record without invalidating the rest of the packet.",
            "limitations": [
                "Opt-in field, absent from any bundle that did not request it (export_ai_bundle.py --include-current-research-decision-packet).",
                "COHESION/TRANSPORT only: it creates no new authority and cannot strengthen, weaken, or recompute a Producer sibling's own value.",
                "component_manifest and authority_boundary are shared across every ticker in the same packet artifact; only packet.components/unresolved_components/authority_limitations are ticker-specific.",
                "The packet's scenario component is the existing evidence-bound Bear/Base/Bull overlay (current_evidence_bound_scenario), not the CONSERVATIVE/BASE/SPECULATIVE current_research_scenario_context sibling.",
                "A packet-supplied fact that duplicates an already-present direct sibling is the same upstream fact through a second transport path, never independent confirmation; a materially conflicting duplicate must never be silently resolved by preferring either representation.",
                "current_decision_context is quoted decision metadata, never evidence; it can never widen, override, or independently confirm research_priority, entry_action, strategy eligibility, or tactical state beyond what the existing deterministic siblings already establish.",
            ],
        })
    return context


def apply_bundle_ticker_capability_matrix_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Preserve the Producer's P1.5 capability projection without interpretation.

    The Consumer validates only the safety envelope (same ticker, known semantic status,
    and no actionable flag) before deep-copying the complete matrix.  It never derives a
    capability from a fact, a provider observation, or its own entity lookup.
    """
    entry = ((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle, Mapping) else None
    raw = entry.get("ticker_capability_matrix") if isinstance(entry, Mapping) else None
    states = {"available", "descriptive_only", "partial", "blocked", "blocked_input", "unavailable", "not_applicable", "unknown"}
    sections = ("fundamental_data", "market_descriptive", "market_actionable", "research", "portfolio")
    required = {"schema_version", "ticker", "identity", *sections, "market_data_authority", "summary", "is_actionable"}
    valid = isinstance(raw, Mapping) and required <= set(raw) and raw.get("ticker") == context.get("ticker") and raw.get("is_actionable") is False
    if valid:
        identity = raw.get("identity")
        archetype = identity.get("analysis_archetype_qualification") if isinstance(identity, Mapping) else None
        valid = (isinstance(identity, Mapping) and isinstance(identity.get("entity_type"), str)
                 and isinstance(archetype, Mapping) and archetype.get("status") in states
                 and archetype.get("is_actionable") is False)
    if valid:
        for section_name in sections:
            section = raw.get(section_name)
            if not isinstance(section, Mapping):
                valid = False
                break
            for capability in section.values():
                if (not isinstance(capability, Mapping) or capability.get("status") not in states
                        or capability.get("is_actionable") is not False
                        or not isinstance(capability.get("descriptive_only"), bool)):
                    valid = False
                    break
            if not valid:
                break
    if raw is not None:
        context["ticker_capability_matrix"] = copy.deepcopy(dict(raw)) if valid else {
            "status": "malformed", "is_actionable": False,
            "reason_codes": ["ticker_capability_matrix_malformed"],
        }
        context.setdefault("provenance", []).append({
            "source_file": "analysis_bundle.json", "source_dataset": "ticker_capability_matrix",
            "transformation": "Verbatim Producer capability/trust matrix; Consumer performs no eligibility, market-basis, research, or portfolio recomputation.",
            "limitations": ["Capability-specific only: provider-scoped descriptive observations never open generic valuation, liquidity, sizing, execution, or backtest claims."],
        })
    return context

def apply_bundle_qualified_research_delta_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Pass through the Producer-owned snapshot delta; never re-diff the brief here."""
    entry=((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle,Mapping) else None;raw=entry.get("qualified_research_delta") if isinstance(entry,Mapping) else None
    if raw is not None:
        states={"comparable","partially_comparable","incomparable","blocked"}
        valid=isinstance(raw,Mapping) and raw.get("ticker")==context.get("ticker") and raw.get("historical_only") is True and raw.get("is_actionable") is False and raw.get("analysis_mode")=="historical_only_qualified_data" and raw.get("comparison_status") in states
        context["qualified_research_delta"]=copy.deepcopy(dict(raw)) if valid else {"status":"malformed","historical_only":True,"is_actionable":False,"reason_codes":["qualified_research_delta_malformed"]}
        context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"qualified_research_delta","transformation":"Verbatim Producer snapshot delta; Consumer performs no metric, quality, risk, scenario, invalidation, or conclusion recomputation.","limitations":["Historical-only comparison; no recommendation, valuation, ranking, sizing, allocation, prediction, or current-market claim."]})
    return context


def apply_bundle_qualified_research_change_events_contract(context: dict[str, Any], bundle: Mapping[str, Any] | None) -> dict[str, Any]:
    """Verbatim Producer change events; Consumer never compares or assigns importance."""
    entry=((bundle or {}).get("tickers") or {}).get(str(context.get("ticker") or "")) if isinstance(bundle,Mapping) else None; raw=entry.get("qualified_research_change_events") if isinstance(entry,Mapping) else None
    if raw is not None:
        valid=isinstance(raw,Mapping) and isinstance(raw.get("status"),str) and isinstance(raw.get("events"),list) and all(isinstance(event,Mapping) and isinstance(event.get("event_id"),str) and isinstance(event.get("provenance_references"),list) for event in raw.get("events",[]))
        context["qualified_research_change_events"]=copy.deepcopy(dict(raw)) if valid else {"status":"malformed","events":[],"historical_only":True,"is_actionable":False,"reason_codes":["qualified_research_change_events_malformed"]}
        context.setdefault("provenance",[]).append({"source_file":"analysis_bundle.json","source_dataset":"qualified_research_change_events","transformation":"Verbatim Producer events; Consumer performs no diff, identity, provenance, or importance recomputation.","limitations":["Historical-only; events are not investment signals, recommendations, valuation, allocation, or market claims."]})
    return context


def save_json(path: Path, payload: Any, *, rotate_existing: bool = False) -> None:
    """Write a context package. Never overwrites an existing export.

    `rotate_existing` does not relax that rule: the previous export is renamed to
    `<stem>_superseded_<UTC timestamp>.json` beside itself and kept, and only then is the
    canonical name written fresh. Without it, a daily refresh had no supported path at all
    -- the Producer reads the canonical `<TICKER>_context.json`, so leaving the previous
    one in place meant the bundle silently consumed a context package several sessions old,
    which the export's own session-scoped freshness gate then correctly refused.
    """
    safe = validate_safe_output_path(path)
    if safe.exists():
        if not rotate_existing:
            raise FileExistsError(f"Refusing to overwrite existing output: {safe}")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        superseded = safe.with_name(f"{safe.stem}_superseded_{stamp}{safe.suffix}")
        if superseded.exists():
            raise FileExistsError(f"Refusing to overwrite existing rotation target: {superseded}")
        safe.rename(superseded)
    safe.parent.mkdir(parents=True, exist_ok=True)
    with safe.open("x", encoding="utf-8", newline="\n") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def validate_coverage_report_path(path: Path, suffix: str) -> Path:
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = WORKSPACE_ROOT / resolved
    resolved = resolved.resolve()
    if not _is_relative_to(resolved, REPORTS_ROOT):
        raise ValueError(f"Coverage report must stay inside {REPORTS_ROOT}")
    if resolved.suffix.lower() != suffix:
        raise ValueError(f"Coverage report must use {suffix}")
    if resolved.exists():
        raise FileExistsError(f"Refusing to overwrite existing coverage report: {resolved}")
    return resolved


def save_coverage_report(path: Path, payload: Any, *, markdown: bool = False) -> None:
    safe = validate_coverage_report_path(path, ".md" if markdown else ".json")
    safe.parent.mkdir(parents=True, exist_ok=True)
    content = str(payload) if markdown else json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    safe.write_text(content, encoding="utf-8", newline="\n")


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def validate_safe_output_path(path: Path, config: dict[str, Any] | None = None) -> Path:
    config = config or load_json(CONFIG_PATH)
    resolved = path.expanduser()
    if not resolved.is_absolute():
        resolved = WORKSPACE_ROOT / resolved
    resolved = resolved.resolve()
    if not _is_relative_to(resolved, WORKSPACE_ROOT):
        raise ValueError(f"Output must stay inside AI ANALYZE: {resolved}")
    if _is_relative_to(resolved, VNSTOCK_ROOT):
        raise ValueError(f"Output must never be inside VNSTOCK: {resolved}")
    for raw in config.get("forbidden_output_dirs", []):
        candidate = Path(raw)
        forbidden = candidate.resolve() if candidate.is_absolute() else (WORKSPACE_ROOT / candidate).resolve()
        if _is_relative_to(resolved, forbidden):
            raise ValueError(f"Output is inside a forbidden directory: {forbidden}")
    allowed = (WORKSPACE_ROOT / config["default_output_dir"]).resolve()
    if not _is_relative_to(resolved, allowed):
        raise ValueError(f"Output must stay inside approved exports directory: {allowed}")
    if resolved.suffix.lower() != ".json":
        raise ValueError("Output must use a .json extension")
    return resolved


def normalize_ticker(value: str) -> str:
    ticker = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9]{2,10}", ticker):
        raise ValueError("Ticker must contain 2-10 uppercase ASCII letters/digits")
    return ticker


def normalize_ticker_list(values: Iterable[str], max_batch_size: int = 10) -> list[str]:
    """Normalize, de-duplicate in input order, and enforce the safe batch cap."""
    tickers = list(dict.fromkeys(normalize_ticker(item) for item in values if item.strip()))
    if not tickers:
        raise ValueError("At least one ticker value is required")
    if len(tickers) > max_batch_size:
        raise ValueError(f"Batch size {len(tickers)} exceeds safe maximum {max_batch_size}")
    return tickers


def load_summary_layer(config: dict[str, Any]) -> dict[str, Any]:
    loaded: dict[str, Any] = {}
    for raw in config["required_summary_files"]:
        loaded[Path(raw).name] = load_json((WORKSPACE_ROOT / raw).resolve())
    return loaded


def _connect_read_only(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"VNSTOCK database not found: {db_path}")
    connection = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA query_only = ON")
    return connection


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def _number(value: Any) -> float | int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        number = float(value)
        if not math.isfinite(number):
            return None
        return int(number) if number.is_integer() else number
    except (TypeError, ValueError):
        return None


def _bool_string(value: Any) -> bool | None:
    if value == "True" or value is True:
        return True
    if value == "False" or value is False:
        return False
    return None


def _stream_csv_ticker(path: Path, ticker: str) -> list[dict[str, str]]:
    if not path.exists():
        return []
    matches: list[dict[str, str]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "ticker" not in reader.fieldnames:
            raise ValueError(f"Expected ticker column in {path}")
        for row in reader:
            if (row.get("ticker") or "").strip().upper() == ticker:
                matches.append(dict(row))
    return matches


def check_ticker_coverage(ticker: str, summaries: dict[str, Any], db_path: Path) -> dict[str, Any]:
    result = {"ticker": ticker, "has_price": False, "has_metadata": False, "has_financial": False,
              "has_news": None, "has_shareholder": False, "has_technical": False, "status": "checked"}
    connection = _connect_read_only(db_path)
    try:
        result["has_price"] = connection.execute("SELECT 1 FROM ohlcv WHERE ticker=? LIMIT 1", (ticker,)).fetchone() is not None
        result["has_metadata"] = connection.execute("SELECT 1 FROM metadata WHERE ticker=? LIMIT 1", (ticker,)).fetchone() is not None
        result["has_shareholder"] = connection.execute("SELECT 1 FROM shareholders WHERE ticker=? LIMIT 1", (ticker,)).fetchone() is not None
    finally:
        connection.close()
    result["has_financial"] = bool(_stream_csv_ticker(VNSTOCK_ROOT / "financial_snapshot.csv", ticker))
    result["has_technical"] = bool(_stream_csv_ticker(VNSTOCK_ROOT / "screen_snapshot.csv", ticker) or _stream_csv_ticker(VNSTOCK_ROOT / "ta_signals.csv", ticker))
    result["coverage_summary_note"] = summaries.get("ticker_coverage_summary.json", {}).get("reason")
    result["has_news"] = None
    return result


def load_price_slice(ticker: str, db_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection = _connect_read_only(db_path)
    try:
        rows = connection.execute(
            "SELECT date, open, high, low, close, volume, source FROM ohlcv WHERE ticker=? ORDER BY date",
            (ticker,),
        ).fetchall()
    finally:
        connection.close()
    provenance = [{"source_file": str(db_path), "source_dataset": "ohlcv", "source_keys": {"ticker": ticker},
                   "transformation": "Read-only indexed ticker query; ordered by date; lightweight aggregates and trading-day returns."}]
    if not rows:
        return {}, provenance
    closes = [_number(row["close"]) for row in rows]
    latest_close = closes[-1]

    def trading_return(lookback: int) -> float | None:
        if latest_close is None or len(rows) <= lookback:
            return None
        base = closes[-(lookback + 1)]
        if base in (None, 0):
            return None
        return round((float(latest_close) / float(base) - 1.0) * 100.0, 6)

    volumes = [_number(row["volume"]) for row in rows[-20:]]
    valid_volumes = [float(v) for v in volumes if v is not None]
    summary = {
        "first_date": rows[0]["date"], "last_date": rows[-1]["date"], "trading_days": len(rows),
        "latest_close": latest_close, "latest_volume": _number(rows[-1]["volume"]),
        "return_1m_pct": trading_return(21), "return_3m_pct": trading_return(63),
        "return_1y_pct": trading_return(252),
        "avg_volume_20d": round(sum(valid_volumes) / len(valid_volumes), 3) if valid_volumes else None,
        "currency": "VND", "latest_source": rows[-1]["source"],
        "adjusted_price_warning": "Price adjustment for dividends/splits is not fully confirmed; trading-day returns may be affected by corporate actions.",
        "return_method": "latest close versus close 21/63/252 trading observations earlier",
    }
    return summary, provenance


def load_metadata_slice(ticker: str, db_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fields = ["ticker","exchange","industry","foreign_room_pct","pe","pb","roe","market_cap",
              "shares_outstanding","free_float_est","dividend_yield","margin_status","updated"]
    connection = _connect_read_only(db_path)
    try:
        row = connection.execute(f"SELECT {','.join(fields)} FROM metadata WHERE ticker=?", (ticker,)).fetchone()
    finally:
        connection.close()
    provenance = [{"source_file": str(db_path), "source_dataset": "metadata", "source_keys": {"ticker": ticker},
                   "transformation": "Read-only primary-key query; -1 dividend sentinel normalized to null."}]
    if row is None:
        return {}, provenance
    result = {field: _clean(row[field]) for field in fields}
    result["company_name"] = None
    if result.get("dividend_yield") == -1:
        result["dividend_yield"] = None
        result["dividend_yield_missing_reason"] = "queried_no_value"
    if not result.get("margin_status"):
        result["margin_status"] = None
        result["margin_status_meaning"] = "no flagged status under project convention"
    result["point_in_time_warning"] = "Current metadata snapshot; do not use directly for historical backtests."
    result["free_float_warning"] = "free_float_est is a proxy, not an official value."
    result["company_name_warning"] = "company_name is not available in the confirmed metadata schema."
    return result, provenance


# The 11 vnstock_metadata_snapshot registry fields, in the same order load_metadata_slice's own
# `fields` list uses them (excluding "ticker" and "updated", which are handled separately below).
_REGISTRY_METADATA_FIELDS = (
    "exchange", "industry", "foreign_room_pct", "pe", "pb", "roe", "market_cap",
    "shares_outstanding", "free_float_est", "dividend_yield", "margin_status",
)

# dividend_yield/margin_status carry a field-specific annotation key when normalized; used by
# both load_metadata_slice_from_registry_snapshot (to set it) and compare_metadata_slices (to
# compare it). Not a generic {field}_suffix pattern -- these two are the only fields load_metadata_slice
# itself annotates this way.
_METADATA_PROVENANCE_ANNOTATION_KEYS = {
    "dividend_yield": "dividend_yield_missing_reason",
    "margin_status": "margin_status_meaning",
}


def load_metadata_slice_from_registry_snapshot(ticker: str, snapshot: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Opt-in alternative to load_metadata_slice(): reads ONE ticker's metadata from an immutable
    vnstock_metadata_snapshot registry snapshot (see metadata_registry_reader.read_snapshot) and
    converts it into the exact same slice shape load_metadata_slice produces from vn_stock.db --
    same field names, same -1/margin_status normalization, same warning annotations -- so the two
    sources are directly comparable (see compare_metadata_slices) and interchangeable to every
    downstream consumer of context["metadata"].

    Never touches vn_stock.db. Fails closed: any malformed/ambiguous/invalid snapshot (from
    read_snapshot) or an internally inconsistent one (missing required field, or fields that
    disagree on their own observed_at) raises SnapshotError rather than returning a partial or
    fabricated result. A ticker simply absent from a *valid* snapshot returns ({}, provenance) --
    the same "not present" shape load_metadata_slice returns for a missing DB row."""
    grouped = read_snapshot(snapshot)  # SnapshotError propagates untouched -- fail closed
    ticker_records = grouped.get(ticker, {})
    provenance = [{
        "source_file": str(snapshot), "source_dataset": "vnstock_metadata_snapshot registry",
        "source_keys": {"ticker": ticker},
        "transformation": "Registry snapshot record group converted to the standard metadata "
                           "slice shape; -1 dividend sentinel normalized to null.",
    }]
    if not ticker_records:
        return {}, provenance

    missing_fields = [f for f in _REGISTRY_METADATA_FIELDS if f not in ticker_records]
    if missing_fields:
        raise SnapshotError(f"ticker {ticker}: registry snapshot is missing required field(s) {missing_fields}")

    observed_at_values = {ticker_records[f]["timestamps"]["observed_at"] for f in _REGISTRY_METADATA_FIELDS}
    if len(observed_at_values) != 1:
        raise SnapshotError(
            f"ticker {ticker}: inconsistent observed_at across fields in registry snapshot: "
            f"{sorted(observed_at_values)}"
        )

    result: dict[str, Any] = {"ticker": ticker}
    for field in _REGISTRY_METADATA_FIELDS:
        result[field] = _clean(ticker_records[field]["value"])
    result["updated"] = next(iter(observed_at_values))
    result["company_name"] = None
    if result.get("dividend_yield") == -1:
        result["dividend_yield"] = None
        result[_METADATA_PROVENANCE_ANNOTATION_KEYS["dividend_yield"]] = "queried_no_value"
    if not result.get("margin_status"):
        result["margin_status"] = None
        result[_METADATA_PROVENANCE_ANNOTATION_KEYS["margin_status"]] = "no flagged status under project convention"
    result["point_in_time_warning"] = "Current metadata snapshot; do not use directly for historical backtests."
    result["free_float_warning"] = "free_float_est is a proxy, not an official value."
    result["company_name_warning"] = "company_name is not available in the confirmed metadata schema."
    return result, provenance


def compare_metadata_slices(db_slice: dict[str, Any], registry_slice: dict[str, Any]) -> dict[str, Any]:
    """Shadow-mode comparison between a DB-sourced and a registry-sourced metadata slice (both
    already in the load_metadata_slice output shape -- see load_metadata_slice_from_registry_snapshot).
    Pure and deterministic: same two inputs always produce the same report. In-memory only --
    writes nothing, and is never called from build_context_package, so it cannot affect context
    output on its own.

    Reports, per field in _REGISTRY_METADATA_FIELDS:
    - exact_match: identical value and identical provenance annotation (if any).
    - null_mismatch: exactly one side is null.
    - value_mismatch: both sides non-null but the values differ.
    - provenance_mismatch: values agree (both null or equal) but the field-specific annotation
      (dividend_yield_missing_reason / margin_status_meaning) differs.
    """
    exact_match: list[str] = []
    null_mismatch: list[dict[str, Any]] = []
    value_mismatch: list[dict[str, Any]] = []
    provenance_mismatch: list[dict[str, Any]] = []

    for field in _REGISTRY_METADATA_FIELDS:
        db_value = db_slice.get(field)
        registry_value = registry_slice.get(field)
        db_is_null = db_value is None
        registry_is_null = registry_value is None

        if db_is_null != registry_is_null:
            null_mismatch.append({"field": field, "db_value": db_value, "registry_value": registry_value})
            continue
        if not db_is_null and db_value != registry_value:
            value_mismatch.append({"field": field, "db_value": db_value, "registry_value": registry_value})
            continue

        annotation_key = _METADATA_PROVENANCE_ANNOTATION_KEYS.get(field)
        db_annotation = db_slice.get(annotation_key) if annotation_key else None
        registry_annotation = registry_slice.get(annotation_key) if annotation_key else None
        if db_annotation != registry_annotation:
            provenance_mismatch.append({"field": field, "db_annotation": db_annotation, "registry_annotation": registry_annotation})
            continue

        exact_match.append(field)

    return {
        "exact_match": exact_match,
        "null_mismatch": null_mismatch,
        "value_mismatch": value_mismatch,
        "provenance_mismatch": provenance_mismatch,
        "is_fully_consistent": not (null_mismatch or value_mismatch or provenance_mismatch),
    }


# Explicit metadata source configuration. "database" is the only source requiring no extra
# argument and is the default everywhere -- see build_context_package. Passing the string
# "registry_snapshot" opts into the immutable-file source; the reverse (an unrecognized string,
# or "registry_snapshot" without a path) is a config error, not a silent fallback to "database".
METADATA_SOURCE_DATABASE = "database"
METADATA_SOURCE_REGISTRY_SNAPSHOT = "registry_snapshot"
VALID_METADATA_SOURCES = (METADATA_SOURCE_DATABASE, METADATA_SOURCE_REGISTRY_SNAPSHOT)


class MetadataSourceConfigError(ValueError):
    """Raised for an invalid or incomplete metadata source configuration -- e.g. an unrecognized
    metadata_source string, or metadata_source='registry_snapshot' without an explicit snapshot
    path. Fail-closed: never silently falls back to 'database'."""


class RegistryPromotionBlocked(ValueError):
    """Raised when registry_shadow_gate is enabled and metadata_registry_shadow_compare's
    check_registry_promotion_gate finds this ticker's registry data missing relative to, or
    disagreeing with, the live DB. Blocks using registry data for this one ticker rather than
    silently serving a value that has just been shown to be questionable."""


def _select_metadata_loader(
    ticker: str,
    db_path: Path,
    metadata_source: str = METADATA_SOURCE_DATABASE,
    metadata_registry_snapshot: Path | None = None,
    registry_shadow_gate: bool = False,
):
    """The one decision point for build_context_package's metadata section. "database" (the
    default) requires nothing further and behaves exactly as it always has. "registry_snapshot"
    requires an explicit snapshot path -- never auto-discovered -- and, when registry_shadow_gate
    is enabled, a passing preflight comparison against the live DB for this specific ticker
    before its registry data is trusted. Exactly one loader is ever returned; there is no
    fallback from a requested registry source back to the database."""
    if metadata_source not in VALID_METADATA_SOURCES:
        raise MetadataSourceConfigError(
            f"unknown metadata_source {metadata_source!r}; must be one of {VALID_METADATA_SOURCES}"
        )

    if metadata_source == METADATA_SOURCE_DATABASE:
        return lambda: load_metadata_slice(ticker, db_path)

    if metadata_registry_snapshot is None:
        raise MetadataSourceConfigError(
            "metadata_source='registry_snapshot' requires an explicit metadata_registry_snapshot "
            "path; it is never auto-discovered"
        )

    def _load_from_registry():
        if registry_shadow_gate:
            try:
                from metadata_registry_shadow_compare import check_registry_promotion_gate
            except ModuleNotFoundError:  # importlib-based tests load this file from the workspace root
                from builders.metadata_registry_shadow_compare import check_registry_promotion_gate
            gate = check_registry_promotion_gate(ticker, db_path, metadata_registry_snapshot)
            gate_passed = gate["status"] == "compared" and gate["comparison"]["is_fully_consistent"]
            if not gate_passed:
                raise RegistryPromotionBlocked(
                    f"ticker {ticker}: registry shadow gate blocked promotion "
                    f"(status={gate['status']!r}, comparison={gate['comparison']})"
                )
        return load_metadata_slice_from_registry_snapshot(ticker, metadata_registry_snapshot)

    return _load_from_registry


def resolve_metadata_source_options(config: Mapping[str, Any], args: argparse.Namespace) -> tuple[str, Path | None, bool]:
    """Resolve explicit Consumer metadata-source options without snapshot discovery."""
    raw = config.get("metadata_source", {})
    if not isinstance(raw, Mapping):
        raise MetadataSourceConfigError("metadata_source config must be an object")
    source = args.metadata_source if args.metadata_source is not None else raw.get("mode", METADATA_SOURCE_DATABASE)
    snapshot_value = (args.metadata_registry_snapshot if args.metadata_registry_snapshot is not None
                      else raw.get("registry_snapshot"))
    shadow_gate = args.registry_shadow_gate if args.registry_shadow_gate is not None else raw.get("shadow_gate", False)
    if not isinstance(shadow_gate, bool):
        raise MetadataSourceConfigError("metadata_source.shadow_gate must be a boolean")
    snapshot = None if snapshot_value in (None, "") else Path(str(snapshot_value))
    return str(source), snapshot, shadow_gate


def resolve_build_clock(value: datetime | str) -> datetime:
    """Validate an explicit reproducibility clock as an aware UTC instant."""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("frozen clock must be an ISO-8601 UTC timestamp") from exc
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("frozen clock must be timezone-aware UTC (Z or +00:00)")
    return value.astimezone(timezone.utc)

def _period_key(period: str) -> tuple[int, int]:
    match = re.fullmatch(r"(\d{4})(?:-Q([1-4]))?", period or "")
    return (int(match.group(1)), int(match.group(2) or 5)) if match else (-1, -1)


def _is_period_verified(row: dict[str, str]) -> bool:
    """Kỳ được coi là ĐÃ XÁC MINH theo lịch dương trừ khi bctc_processor.py (P0-4,
    flag_fiscal_period_verification) gắn cờ rõ 'future_relative_to_calendar_quarter_end' — dấu
    hiệu năm tài chính lệch (HSG/CTD...) hoặc lỗi nhãn nguồn. File financial_snapshot.csv cũ
    (sinh trước khi có cột fiscal_period_status) không có cột này -> mặc định coi là verified,
    không hồi tố cảnh báo cho dữ liệu cũ."""
    return row.get("fiscal_period_status") != "future_relative_to_calendar_quarter_end"


def load_financial_slice(ticker: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = VNSTOCK_ROOT / "financial_snapshot.csv"
    rows = _stream_csv_ticker(path, ticker)
    provenance = [{"source_file": str(path), "source_dataset": "financial_snapshot", "source_keys": {"ticker": ticker},
                   "transformation": "UTF-8 streaming CSV filter by ticker; latest period selected by parsed period key."}]
    if not rows:
        summary: dict[str, Any] = {
            "latest_period": None,
            "latest_period_type": None,
            "available_periods_count": 0,
            "available_periods": [],
            "source_rows_found": False,
        }
        empty_metas = {}
        for metric in FINANCIAL_CONTRACT_METRICS:
            meta = build_metric_meta(
                None,
                MetricStatus.SOURCE_EMPTY,
                reason="ticker_missing_from_financial_snapshot",
                source="financial_snapshot",
                basis="reported",
                confidence=0.0,
            )
            set_metric_with_meta(summary, metric, meta)
            empty_metas[metric] = meta
        # item A/C: kept out of empty_metas/coverage (same as the populated path below) —
        # these are not part of FINANCIAL_CONTRACT_METRICS.
        for extra_metric in ("roe_quarter", "roe_fy", "roe_ttm", "eps_calc", "book_value"):
            set_metric_with_meta(summary, extra_metric, build_metric_meta(
                None, MetricStatus.SOURCE_EMPTY, reason="ticker_missing_from_financial_snapshot",
                source="financial_snapshot", confidence=0.0,
            ))
        summary["coverage"] = build_section_coverage(empty_metas)
        summary["coverage_scope"] = list(FINANCIAL_CONTRACT_METRICS)
        summary["metric_contract_version"] = CONTRACT_VERSION
        return summary, provenance
    rows.sort(key=lambda row: _period_key(row.get("period", "")))
    verified_rows = [r for r in rows if _is_period_verified(r)]
    excluded_periods = sorted({r.get("period") for r in rows if not _is_period_verified(r) and r.get("period")})
    # [P0-4] Không chọn kỳ chưa xác minh (nhãn dương lịch tương lai) làm "latest" mặc định.
    # Chỉ rơi về toàn bộ rows nếu KHÔNG CÒN kỳ nào đã xác minh (an toàn hơn là báo trống hoàn toàn).
    latest = verified_rows[-1] if verified_rows else rows[-1]
    fields = ["revenue","net_profit","total_assets","equity","total_liabilities"]
    summary: dict[str, Any] = {
        "snapshot_schema_version": latest.get("schema_version") or "1.0-legacy",
        "latest_period": latest.get("period") or None,
        "latest_period_type": latest.get("period_type") or None,
        "available_periods_count": len({row.get("period") for row in rows if row.get("period")}),
        "available_periods": sorted({row.get("period") for row in rows if row.get("period")}, key=_period_key),
        "source_rows_found": True,
        "excluded_unverified_fiscal_periods": excluded_periods,
    }
    for field in fields:
        summary[field] = _number(latest.get(field))
    metric_metas: dict[str, dict[str, Any]] = {}
    def latest_value_row(field: str) -> dict[str, Any] | None:
        return next((row for row in reversed(rows) if _number(row.get(field)) is not None), None)

    ocf_fields = [
        "operating_cash_flow_reported",
        "operating_cash_flow_ytd",
        "operating_cash_flow_quarter",
        "operating_cash_flow_ttm",
    ]
    for field in ocf_fields:
        selected = latest_value_row(field)
        summary[field] = _number(selected.get(field)) if selected else None

    # Prefer a valid TTM; otherwise use the latest non-null reported observation.
    # Backward compatibility: old snapshots may only have operating_cash_flow.
    selected_ttm = latest_value_row("operating_cash_flow_ttm")
    selected_reported = latest_value_row("operating_cash_flow_reported")
    selected_legacy = latest_value_row("operating_cash_flow")
    selected_ocf = selected_ttm or selected_reported or selected_legacy
    if selected_ocf:
        selected_field = (
            "operating_cash_flow_ttm" if selected_ttm is selected_ocf
            else "operating_cash_flow_reported" if selected_reported is selected_ocf
            else "operating_cash_flow"
        )
        ocf_value = _number(selected_ocf.get(selected_field))
        basis = selected_ocf.get("operating_cash_flow_basis") or (
            "ttm" if selected_field == "operating_cash_flow_ttm"
            else "reported" if selected_field == "operating_cash_flow_reported"
            else MetricStatus.PERIOD_BASIS_UNKNOWN.value
        )
        details = {
            "financial_latest_period": summary["latest_period"],
            "selected_latest_non_null_reported": selected_ocf.get("period") != summary["latest_period"],
            "raw_unit": selected_ocf.get("operating_cash_flow_raw_unit") or None,
            "normalized_unit": selected_ocf.get("operating_cash_flow_normalized_unit") or "unknown",
            "unit_multiplier": _number(selected_ocf.get("operating_cash_flow_unit_multiplier")),
            "unit_status": selected_ocf.get("operating_cash_flow_unit_status") or MetricStatus.UNIT_UNKNOWN.value,
            "report_scope": selected_ocf.get("operating_cash_flow_report_scope") or "unknown",
            "audit_status": selected_ocf.get("operating_cash_flow_audit_status") or "unknown",
        }
        basis_confidence = _number(selected_ocf.get("operating_cash_flow_basis_confidence"))
        if basis_confidence is None:
            basis_confidence = 1.0 if basis == "ttm" else 0.5
        if basis == "ttm":
            ocf_meta = build_metric_meta(
                ocf_value,
                MetricStatus.DERIVED,
                source="financial_snapshot",
                period=selected_ocf.get("period"),
                basis="ttm",
                confidence=basis_confidence,
                formula="sum(last_four_comparable_operating_cash_flow_quarters)",
                inputs=["operating_cash_flow_quarter"],
                details=details,
            )
        else:
            ocf_meta = build_metric_meta(
                ocf_value,
                MetricStatus.REPORTED,
                source="financial_snapshot",
                period=selected_ocf.get("period"),
                basis=basis,
                confidence=basis_confidence,
                details=details,
            )
    else:
        ocf_meta = build_metric_meta(
            None,
            MetricStatus.SOURCE_EMPTY,
            reason="no_non_null_operating_cash_flow_in_snapshot",
            source="financial_snapshot",
            period=summary["latest_period"],
            basis=summary["latest_period_type"],
            confidence=0.0,
        )
    set_metric_with_meta(summary, "operating_cash_flow", ocf_meta)
    metric_metas["operating_cash_flow"] = ocf_meta

    missing_definitions = {
        "ebit": (MetricStatus.INSUFFICIENT_PERIODS, "missing_pbt_or_interest_expense"),
        "ebitda": (MetricStatus.INSUFFICIENT_PERIODS, "missing_ebit_or_complete_da_inputs"),
        "interest_expense": (MetricStatus.MAPPING_MISSING, "reported_interest_expense_not_available"),
        "retained_earnings": (MetricStatus.MAPPING_MISSING, "reported_total_missing_and_split_components_incomplete"),
        "depreciation": (MetricStatus.MAPPING_MISSING, "reported_depreciation_not_available"),
        "sga": (MetricStatus.INSUFFICIENT_PERIODS, "missing_selling_or_general_admin_expense"),
    }

    def parse_inputs(raw: Any) -> list[str] | None:
        if not raw:
            return None
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
        except json.JSONDecodeError:
            parsed = [item.strip() for item in str(raw).split("|") if item.strip()]
        return list(parsed) if isinstance(parsed, list) else None

    for metric, (status, reason) in missing_definitions.items():
        value_field = "retained_earnings_end_period" if metric == "retained_earnings" and "retained_earnings_end_period" in latest else metric
        value = _number(latest.get(value_field))
        explicit_status = latest.get(f"{metric}_status")
        explicit_reason = latest.get(f"{metric}_reason") or reason
        explicit_basis = latest.get(f"{metric}_basis") or summary["latest_period_type"]
        explicit_source = latest.get(f"{metric}_source") or "financial_snapshot"
        explicit_period = latest.get(f"{metric}_period") or summary["latest_period"]
        formula = latest.get(f"{metric}_formula") or None
        inputs = parse_inputs(latest.get(f"{metric}_inputs"))
        latest_non_null = next(
            (
                {"period": row.get("period"), "value": _number(row.get(value_field))}
                for row in reversed(rows)
                if _number(row.get(value_field)) is not None
            ),
            None,
        )
        if value is not None:
            resolved_status = explicit_status if explicit_status in {
                MetricStatus.REPORTED.value, MetricStatus.DERIVED.value, MetricStatus.PROXY.value
            } else MetricStatus.REPORTED.value
            kwargs: dict[str, Any] = {}
            if resolved_status == MetricStatus.DERIVED.value:
                kwargs = {"formula": formula, "inputs": inputs}
            meta = build_metric_meta(
                value, resolved_status, source=explicit_source,
                period=explicit_period, basis=explicit_basis,
                confidence=1.0,
                details={
                    "unit_status": MetricStatus.UNIT_UNKNOWN.value,
                    "interest_expense_sign_convention": latest.get("interest_expense_sign_convention") if metric == "interest_expense" else None,
                },
                **kwargs,
            )
        elif explicit_status == MetricStatus.NOT_APPLICABLE.value:
            meta = build_metric_meta(
                None, MetricStatus.NOT_APPLICABLE, reason=explicit_reason,
                source="financial_snapshot", period=summary["latest_period"],
                basis=explicit_basis, confidence=1.0,
            )
        elif latest_non_null:
            meta = build_metric_meta(
                None,
                MetricStatus.STALE,
                reason="selected_period_value_missing",
                source="financial_snapshot",
                period=summary["latest_period"],
                basis=summary["latest_period_type"],
                confidence=0.0,
                details={
                    "latest_non_null_period": latest_non_null["period"],
                    "latest_non_null_value": latest_non_null["value"],
                    "fallback_not_applied": True,
                    "unit_status": MetricStatus.UNIT_UNKNOWN.value,
                },
            )
        elif explicit_status in {item.value for item in MetricStatus}:
            meta = build_metric_meta(
                None, explicit_status, reason=explicit_reason,
                source="financial_snapshot", period=summary["latest_period"],
                basis=explicit_basis, confidence=0.0,
            )
        else:
            meta = build_metric_meta(
                None,
                status,
                reason=reason,
                source="financial_snapshot",
                period=summary["latest_period"],
                basis=summary["latest_period_type"],
                confidence=0.0,
            )
        set_metric_with_meta(summary, metric, meta)
        metric_metas[metric] = meta

    summary["known_missing_mappings"] = sorted(
        metric for metric, meta in metric_metas.items()
        if meta["status"] == MetricStatus.MAPPING_MISSING.value
    )
    summary["known_unimplemented_derivations"] = sorted(
        metric for metric, meta in metric_metas.items()
        if meta["status"] == MetricStatus.DERIVATION_NOT_IMPLEMENTED.value
    )
    summary["coverage"] = build_section_coverage(metric_metas)
    summary["coverage_scope"] = list(FINANCIAL_CONTRACT_METRICS)
    summary["metric_contract_version"] = CONTRACT_VERSION
    summary["unit_scale_warning"] = "Financial statement monetary unit/scale is not fully confirmed from current metadata; do not compare or calculate across sources without verification."
    summary["availability_warning"] = "Reporting period is not the filing publication/availability date; not point-in-time safe for strict backtests."

    # item A (Data Contract Hardening v1.1): roe_quarter/roe_fy/roe_ttm — kept OUT of
    # FINANCIAL_CONTRACT_METRICS/coverage on purpose. That tuple drives
    # coverage/coverage_scope for every one of ~1492 tickers' context packages; folding new
    # metrics into it would silently shift the ratio system-wide with no test protection.
    def _roe_metric_meta(name: str) -> dict[str, Any]:
        value = _number(latest.get(name))
        status = latest.get(f"{name}_status") or MetricStatus.INSUFFICIENT_PERIODS.value
        reason = latest.get(f"{name}_reason") or None
        shared: dict[str, Any] = {
            "source": latest.get(f"{name}_source") or "financial_snapshot",
            "period": latest.get(f"{name}_period") or None,
            "basis": latest.get(f"{name}_basis") or None,
            "unit": latest.get(f"{name}_unit") or None,
            "period_calendar_end": latest.get(f"{name}_period_calendar_end") or None,
            "annualization": latest.get(f"{name}_annualization") or None,
        }
        if status == MetricStatus.DERIVED.value:
            return build_metric_meta(
                value, MetricStatus.DERIVED, confidence=1.0,
                formula=latest.get(f"{name}_formula") or None, inputs=["net_profit", "equity"], **shared,
            )
        if status == MetricStatus.NOT_APPLICABLE.value:
            return build_metric_meta(None, MetricStatus.NOT_APPLICABLE, reason=reason, confidence=1.0, **shared)
        return build_metric_meta(None, MetricStatus.INSUFFICIENT_PERIODS, reason=reason, confidence=0.0, **shared)

    for roe_name in ("roe_quarter", "roe_fy", "roe_ttm"):
        set_metric_with_meta(summary, roe_name, _roe_metric_meta(roe_name))

    # item C: eps_calc/book_value are self-computed ratios over a period-end (not
    # weighted-average) share proxy — never canonical. status="proxy" so no consumer promotes
    # them silently (acceptance: "self-computed EPS from share proxy must never be canonical").
    for proxy_name in ("eps_calc", "book_value"):
        value = _number(latest.get(proxy_name))
        proxy_status = latest.get(f"{proxy_name}_status") or None
        basis = latest.get(f"{proxy_name}_basis") or None
        if proxy_status == MetricStatus.PROXY.value and value is not None:
            proxy_meta = build_metric_meta(
                value, MetricStatus.PROXY, source="financial_snapshot", period=summary["latest_period"],
                basis=basis, confidence=0.5, unit="vnd_per_share",
            )
        else:
            proxy_meta = build_metric_meta(
                None, MetricStatus.SOURCE_EMPTY, reason="underlying_amount_or_shares_period_end_not_reported",
                source="financial_snapshot", period=summary["latest_period"], basis=basis, confidence=0.0,
            )
        set_metric_with_meta(summary, proxy_name, proxy_meta)

    return summary, provenance


SHARE_MISMATCH_WARNING_PCT = 5.0
SHARE_MISMATCH_MATERIAL_PCT = 10.0


def load_share_reconciliation_slice(ticker: str, db_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Reconcile shares_period_end (financial_snapshot, balance-sheet par-value derived) vs
    shares_current (VNSTOCK metadata table, live) — item D, Data Contract Hardening v1.1.
    Ticker-agnostic threshold rule (>=5% warning, >=10% material_warning per SHARE_MISMATCH_*
    constants above): real HPG/PAN data already produce material warnings and POW/SSI do not,
    from this general logic alone — no ticker is special-cased.

    weighted_average_shares_basic/diluted are exposed as explicit status="proxy" metric
    objects (proxy_of=shares_period_end): no weighted-average share count is reported
    anywhere in the raw BCTC source, and deriving one from EPS was deliberately rejected
    elsewhere in this codebase as unreliable — using ending shares AS a labeled proxy is safer
    than silently omitting the concept.
    """
    financial_path = VNSTOCK_ROOT / "financial_snapshot.csv"
    rows = _stream_csv_ticker(financial_path, ticker)
    provenance = [
        {"source_file": str(financial_path), "source_dataset": "financial_snapshot", "source_keys": {"ticker": ticker},
         "transformation": "UTF-8 streaming CSV filter by ticker; latest verified period's shares_period_end selected."},
        {"source_file": str(db_path), "source_dataset": "metadata", "source_keys": {"ticker": ticker},
         "transformation": "Read-only primary-key query for shares_outstanding (shares_current, live)."},
    ]

    shares_period_end = None
    shares_period_end_period = None
    if rows:
        rows.sort(key=lambda row: _period_key(row.get("period", "")))
        verified_rows = [r for r in rows if _is_period_verified(r)]
        latest = verified_rows[-1] if verified_rows else rows[-1]
        shares_period_end = _number(latest.get("shares_period_end") or latest.get("shares_outstanding"))
        shares_period_end_period = latest.get("period") or None

    connection = _connect_read_only(db_path)
    try:
        row = connection.execute("SELECT shares_outstanding, updated FROM metadata WHERE ticker=?", (ticker,)).fetchone()
    finally:
        connection.close()
    shares_current = _number(row["shares_outstanding"]) if row else None
    shares_current_date = row["updated"] if row else None

    period_end_meta = build_metric_meta(
        shares_period_end,
        MetricStatus.DERIVED if shares_period_end is not None else MetricStatus.SOURCE_EMPTY,
        reason=None if shares_period_end is not None else "common_shares_and_charter_capital_and_paid_in_capital_not_reported",
        source="financial_snapshot", period=shares_period_end_period, basis="balance_sheet_par_value_derived",
        confidence=1.0 if shares_period_end is not None else 0.0,
        formula="common_shares_or_charter_capital_or_paid_in_capital / 10000" if shares_period_end is not None else None,
        inputs=["common_shares", "charter_capital", "paid_in_capital"] if shares_period_end is not None else None,
    )
    current_meta = build_metric_meta(
        shares_current,
        MetricStatus.REPORTED if shares_current is not None else MetricStatus.SOURCE_EMPTY,
        reason=None if shares_current is not None else "metadata_shares_outstanding_not_available",
        source="vnstock_metadata_snapshot", period=shares_current_date, basis="live_current",
        confidence=1.0 if shares_current is not None else 0.0,
    )

    mismatch_pct = None
    status = "unavailable"
    reason = "insufficient_data_for_reconciliation"
    if shares_period_end is not None and shares_current is not None and shares_period_end != 0:
        # Round to 1 decimal place BEFORE threshold comparison — both share counts are
        # themselves estimates (par-value division; a live provider snapshot), so comparing
        # at full float precision would let sub-0.1pp floating-point noise flip a genuinely
        # 10.0% mismatch to "warning" instead of "material_warning" depending on the exact
        # bytes involved. General rounding rule, applied identically to every ticker.
        mismatch_pct = round(abs(shares_current - shares_period_end) / abs(shares_period_end) * 100.0, 1)
        if mismatch_pct >= SHARE_MISMATCH_MATERIAL_PCT:
            status, reason = "material_warning", f"shares_current_and_shares_period_end_differ_{SHARE_MISMATCH_MATERIAL_PCT:g}pct_or_more"
        elif mismatch_pct >= SHARE_MISMATCH_WARNING_PCT:
            status, reason = "warning", f"shares_current_and_shares_period_end_differ_{SHARE_MISMATCH_WARNING_PCT:g}pct_or_more"
        else:
            status, reason = "ok", None

    possible_reason = (
        "Share issuance (stock dividend/rights issue/ESOP), buyback, or a metadata snapshot "
        "taken from a different date than the financial statement period — investigate before "
        "computing per-share figures across the two counts."
        if status in ("warning", "material_warning") else None
    )
    consumer_action = {
        "ok": "shares_period_end and shares_current agree within tolerance; either is safe for period-matched per-share ratios.",
        "warning": "Prefer shares_current for live market_cap/valuation; prefer shares_period_end for ratios computed against that same financial period. Do not mix the two in one ratio.",
        "material_warning": "Do not compute per-share or market-cap figures without first confirming which share count matches the metric's period — the two disagree materially.",
        "unavailable": "Neither share count is reliably available; do not compute any per-share or market-cap figure for this ticker.",
    }[status]

    if shares_period_end is not None:
        weighted_average_meta = build_metric_meta(
            shares_period_end, MetricStatus.PROXY, source="financial_snapshot", period=shares_period_end_period,
            basis="shares_period_end_used_as_proxy", confidence=0.3,
            details={
                "proxy_of": "shares_period_end",
                "true_weighted_average_not_available": "no weighted-average share count is reported in the raw BCTC source",
            },
        )
    else:
        weighted_average_meta = build_metric_meta(
            None, MetricStatus.SOURCE_EMPTY, reason="no_share_count_available_to_proxy",
            source="financial_snapshot", confidence=0.0,
        )

    result: dict[str, Any] = {
        "mismatch_pct": mismatch_pct,
        "status": status,
        "reason": reason,
        "possible_reason": possible_reason,
        "consumer_action": consumer_action,
        "thresholds": {"warning_pct": SHARE_MISMATCH_WARNING_PCT, "material_warning_pct": SHARE_MISMATCH_MATERIAL_PCT},
    }
    set_metric_with_meta(result, "shares_period_end", period_end_meta)
    set_metric_with_meta(result, "shares_current", current_meta)
    set_metric_with_meta(result, "weighted_average_shares_basic", weighted_average_meta)
    set_metric_with_meta(result, "weighted_average_shares_diluted", weighted_average_meta)
    return result, provenance


def load_vnstock_entity_type(ticker: str) -> str:
    """Import VNSTOCK's financial_mapping.py the same way load_news_slice (below) imports
    news_ticker_mapping.py — a dynamic file-path import, not a duplicated classification.
    Single source of truth for entity_type (item E, Data Contract Hardening v1.1): whatever
    bctc_processor.py used to gate corporate-only ratios is exactly what identity.entity_type
    reports here, so the two can never silently disagree."""
    module_path = VNSTOCK_ROOT / "financial_mapping.py"
    spec = importlib.util.spec_from_file_location("vnstock_financial_mapping", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load financial mapping registry: {module_path}")
    mapping_module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mapping_module
    spec.loader.exec_module(mapping_module)
    return mapping_module.get_default_registry().entity_type_for(ticker)


def load_news_slice(ticker: str, *, now: datetime | None = None) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    path = VNSTOCK_ROOT / "news_latest.csv"
    provenance = [{"source_file": str(path), "source_dataset": "news_latest", "source_keys": {"ticker": ticker},
                   "transformation": "Deduplicate articles, apply versioned exact alias mapping, and keep company/sector/market news separate."}]
    if not path.exists():
        meta = build_metric_meta(
            None, MetricStatus.SOURCE_EMPTY, reason="news_source_file_missing",
            source="news_latest", basis="ticker_linked", confidence=0.0,
        )
        return {
            "status": "source_empty", "company_news_count": 0,
            "sector_news_count": 0, "market_news_count": 0,
            "lookback_days": None, "items": [], "sector_items": [], "market_items": [],
            "latest_news_count": 0, "latest_published_utc": None, "sample_titles": [],
            "meta": meta, "coverage": build_section_coverage({"news_summary": meta}),
            "metric_contract_version": CONTRACT_VERSION,
        }, provenance

    module_path = VNSTOCK_ROOT / "news_ticker_mapping.py"
    spec = importlib.util.spec_from_file_location("vnstock_news_ticker_mapping", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load news mapper: {module_path}")
    mapper = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mapper
    spec.loader.exec_module(mapper)
    registry = mapper.TickerAliasRegistry.from_csv(VNSTOCK_ROOT / "config" / "ticker_aliases.csv")
    registry.add_metadata_aliases([{"ticker": ticker}])
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        articles = list(csv.DictReader(handle))
    mapped = mapper.summarize_news(
        ticker, articles, registry,
        config=mapper.load_config(VNSTOCK_ROOT / "config" / "news_mapping_config.json"),
        now=now,
    )
    company_count = int(mapped["company_news_count"])
    if company_count:
        confidences = [item["ticker_mapping"]["confidence"] for item in mapped["items"]]
        meta = build_metric_meta(
            company_count, MetricStatus.REPORTED, source="news_latest",
            period=mapped["latest_published_utc"], basis="canonical_ticker_alias",
            confidence=min(confidences) if confidences else 0.9,
            details={"mapping_version": mapped["mapping_version"]},
        )
    else:
        meta = build_metric_meta(
            None, MetricStatus.SOURCE_EMPTY, reason="no_company_specific_news",
            source="news_latest", basis="canonical_ticker_alias", confidence=0.0,
            details={
                "mapping_version": mapped["mapping_version"],
                "candidate_review_count": mapped["candidate_review_count"],
            },
        )
    mapped.update({
        "latest_news_count": company_count,
        "sample_titles": [item.get("title") for item in mapped["items"][:5]],
        "ticker_linkage_method": "canonical_alias_registry",
        "mapping_warning": None if company_count else "No company-specific news matched the accepted confidence threshold.",
        "meta": meta,
        "coverage": build_section_coverage({"news_summary": meta}),
        "metric_contract_version": CONTRACT_VERSION,
    })
    return mapped, provenance


def load_shareholder_slice(ticker: str, db_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    connection = _connect_read_only(db_path)
    try:
        tables = {row["name"] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        progress = connection.execute("SELECT status, rows, updated FROM shareholders_progress WHERE ticker=?", (ticker,)).fetchone()
        run = None
        attempts = []
        if "shareholder_records_v2" in tables:
            rows = connection.execute(
                """SELECT record_key, holder_name, shares, ownership_pct, source_name, as_of_date,
                          fetched_at, source_reference, verified_at, record_origin,
                          reconciliation_status, conflict_group, provenance_json
                   FROM shareholder_records_v2 WHERE ticker=?""",
                (ticker,),
            ).fetchall()
            if "shareholder_sync_runs" in tables:
                run = connection.execute(
                    """SELECT final_status,reason,raw_record_count,parsed_record_count,
                              deduplicated_record_count,manual_override_count,latest_as_of_date,
                              freshness_json,updated
                       FROM shareholder_sync_runs WHERE ticker=?""",
                    (ticker,),
                ).fetchone()
            if "shareholder_source_attempts" in tables:
                latest_attempt = connection.execute(
                    "SELECT MAX(request_timestamp) FROM shareholder_source_attempts WHERE ticker=?",
                    (ticker,),
                ).fetchone()[0]
                if latest_attempt:
                    attempts = connection.execute(
                        """SELECT source,status,error,reason,error_reason,record_count,parsed_record_count,
                                  request_timestamp,latest_as_of_date
                           FROM shareholder_source_attempts
                           WHERE ticker=? AND request_timestamp=? ORDER BY id""",
                        (ticker, latest_attempt),
                    ).fetchall()
            if not rows and run is None and not attempts:
                rows = connection.execute(
                    """SELECT shareholder_name, shares_owned, pct, source, updated_at
                       FROM shareholders WHERE ticker=?
                       ORDER BY CASE WHEN pct IS NULL OR pct=-1 THEN 1 ELSE 0 END, pct DESC LIMIT 20""",
                    (ticker,),
                ).fetchall()
        else:
            rows = connection.execute(
                """SELECT shareholder_name, shares_owned, pct, source, updated_at
                   FROM shareholders WHERE ticker=?
                   ORDER BY CASE WHEN pct IS NULL OR pct=-1 THEN 1 ELSE 0 END, pct DESC LIMIT 20""",
                (ticker,),
            ).fetchall()
    finally:
        connection.close()
    phase6 = run is not None or bool(attempts) or bool(rows and "holder_name" in rows[0].keys())
    selected_as_of_date = None
    if phase6:
        valid_dates = set()
        for row in rows:
            value = row["as_of_date"]
            if not isinstance(value, str):
                continue
            try:
                parsed_date = datetime.strptime(value, "%Y-%m-%d").date().isoformat()
            except ValueError:
                continue
            if value == parsed_date:
                valid_dates.add(parsed_date)
        if valid_dates:
            selected_as_of_date = max(valid_dates)
            rows = [row for row in rows if row["as_of_date"] == selected_as_of_date]

        def shareholder_rank_key(row: sqlite3.Row) -> tuple[int, float, str, str]:
            pct = _number(row["ownership_pct"])
            return (pct is None, -(pct or 0.0), (row["holder_name"] or "").casefold(), row["record_key"] or "")

        rows = sorted(rows, key=shareholder_rank_key)[:20]
    provenance = [{"source_file": str(db_path), "source_dataset": "shareholder_records_v2 + attempts + sync_runs" if phase6 else "shareholders + shareholders_progress", "source_keys": {"ticker": ticker, "as_of_date": selected_as_of_date or "unknown"},
                   "transformation": "Read-only ticker query; Phase 6 records are ranked only within the latest valid as_of_date snapshot, with a deterministic unknown-date fallback; legacy -1 pct normalized to null."}]
    holders = []
    for row in rows:
        if phase6:
            pct = _number(row["ownership_pct"])
            try:
                row_provenance = json.loads(row["provenance_json"] or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                row_provenance = []
            holders.append({
                "shareholder_name": row["holder_name"], "shares_owned": _number(row["shares"]),
                "pct": pct, "source": row["source_name"], "updated_at": row["fetched_at"],
                "as_of_date": selected_as_of_date, "source_reference": row["source_reference"],
                "verified_at": row["verified_at"], "record_origin": row["record_origin"],
                "reconciliation_status": row["reconciliation_status"], "conflict_group": row["conflict_group"],
                "provenance": row_provenance,
            })
        else:
            pct = _number(row["pct"])
            holders.append({"shareholder_name": row["shareholder_name"], "shares_owned": _number(row["shares_owned"]),
                            "pct": None if pct == -1 else pct, "source": row["source"], "updated_at": row["updated_at"]})
    dates = ([selected_as_of_date] if selected_as_of_date else []) if phase6 else [
        row["updated_at"] for row in rows if row["updated_at"]
    ]
    progress_status = progress["status"] if progress else None
    final_status = run["final_status"] if run else ({"empty": "source_empty", "failed": "network_failed"}.get(progress_status, progress_status))
    reason = run["reason"] if run else None
    freshness = None
    if run:
        try:
            freshness = json.loads(run["freshness_json"])
        except (TypeError, ValueError, json.JSONDecodeError):
            freshness = {"status": "unknown", "latest_as_of_date": run["latest_as_of_date"]}
    if rows:
        metric_status = MetricStatus.STALE if final_status == "stale" else MetricStatus.REPORTED
        meta = build_metric_meta(len(rows), metric_status, reason=reason,
                                 source="shareholder_records_v2" if phase6 else "shareholders + shareholders_progress",
                                 period=max(dates) if dates else (run["updated"] if run else (progress["updated"] if progress else None)),
                                 basis="point_in_time", confidence=0.6 if metric_status == MetricStatus.STALE else 1.0,
                                 details={"pipeline_status": final_status, "attempt_count": len(attempts)})
    elif progress is None and run is None:
        meta = build_metric_meta(
            None,
            MetricStatus.NOT_QUERIED,
            reason="ticker_absent_from_shareholders_progress",
            source="shareholders_progress",
            basis="point_in_time",
            confidence=0.0,
        )
    elif final_status == "source_empty":
        meta = build_metric_meta(
            None,
            MetricStatus.SOURCE_EMPTY,
            reason="configured_sources_returned_no_usable_records",
            source="shareholders_progress",
            period=run["updated"] if run else progress["updated"],
            basis="point_in_time",
            confidence=1.0,
        )
    elif final_status == "network_failed":
        meta = build_metric_meta(
            None,
            MetricStatus.NETWORK_FAILED,
            reason="shareholder_source_attempt_failed",
            source="shareholders_progress",
            period=run["updated"] if run else progress["updated"],
            basis="point_in_time",
            confidence=0.0,
        )
    elif final_status == "unsupported":
        meta = build_metric_meta(
            None, MetricStatus.UNSUPPORTED, reason=reason or "configured_sources_do_not_support_shareholders",
            source="shareholder_source_attempts", period=run["updated"] if run else (progress["updated"] if progress else None),
            basis="point_in_time", confidence=0.0,
        )
    else:
        meta = build_metric_meta(
            None,
            MetricStatus.PARSE_FAILED,
            reason="progress_state_has_no_usable_records",
            source="shareholders_progress",
            period=run["updated"] if run else (progress["updated"] if progress else None),
            basis="point_in_time",
            confidence=0.0,
        )
    return {
        "status": final_status or "not_queried",
        "reason": reason or ("ticker_absent_from_shareholders_progress" if progress is None else meta.get("reason")),
        "attempts": [dict(item) for item in attempts],
        "sources_attempted": [item["source"] for item in attempts],
        "latest_as_of_date": selected_as_of_date if phase6 else (max(dates) if dates else None),
        "freshness": freshness,
        "manual_override_count": int(run["manual_override_count"]) if run else 0,
        "raw_record_count": int(run["raw_record_count"]) if run else None,
        "parsed_record_count": int(run["parsed_record_count"]) if run else None,
        "deduplicated_record_count": int(run["deduplicated_record_count"]) if run else (len(rows) if rows else None),
        "retained_record_count": len(rows),
        "latest_snapshot_date": selected_as_of_date if phase6 else (max(dates) if dates else (progress["updated"] if progress else None)),
        "major_shareholders_count": (
            int(run["deduplicated_record_count"])
            if rows and run and run["deduplicated_record_count"]
            else int(progress["rows"])
            if rows and progress and progress["rows"]
            else (len(rows) if rows else None)
        ),
        "returned_top_holders_count": len(holders), "top_holders": holders,
        "progress_status": progress_status,
        "snapshot_warning": "Shareholder data is point-in-time and has no history; do not use as historical ownership.",
        "meta": meta,
        "coverage": build_section_coverage({"shareholder_summary": meta}),
        "metric_contract_version": CONTRACT_VERSION,
    }, provenance


def load_technical_slice(ticker: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    screen_path = VNSTOCK_ROOT / "screen_snapshot.csv"
    signals_path = VNSTOCK_ROOT / "ta_signals.csv"
    screens = _stream_csv_ticker(screen_path, ticker)
    signals = _stream_csv_ticker(signals_path, ticker)
    provenance = [
        {"source_file": str(screen_path), "source_dataset": "screen_snapshot", "source_keys": {"ticker": ticker}, "transformation": "Streaming filter; latest ticker row selected; string booleans parsed."},
        {"source_file": str(signals_path), "source_dataset": "ta_signals", "source_keys": {"ticker": ticker}, "transformation": "Streaming filter; latest ticker row selected; semicolon signal lists parsed."},
    ]
    if not screens and not signals:
        return {}, provenance
    screen = max(screens, key=lambda row: row.get("date", "")) if screens else {}
    signal = max(signals, key=lambda row: row.get("date", "")) if signals else {}
    patterns = [item for item in (signal.get("patterns") or "").split(";") if item]
    smc = [item for item in (signal.get("smc") or "").split(";") if item]
    return {
        "latest_signal_date": signal.get("date") or screen.get("date") or None,
        "screen_snapshot_date": screen.get("date") or None,
        "rsi14": _number(screen.get("rsi14")), "macd_hist": _number(screen.get("macd_hist")),
        "above_sma50": _bool_string(screen.get("above_sma50")), "above_sma200": _bool_string(screen.get("above_sma200")),
        "golden_cross": _bool_string(screen.get("golden_cross")), "structure": screen.get("structure") or None,
        "rs_rating": _number(screen.get("rs_rating") or signal.get("rs_rating")),
        "available_signals": {"patterns": patterns, "smc": smc, "confluence": _bool_string(signal.get("confluence")), "direction": signal.get("direction") or None},
        "snapshot_warning": "Technical data/signals are snapshots and derived indicators, not buy/sell conclusions.",
    }, provenance


def build_context_package(
    ticker: str,
    template: dict[str, Any],
    summaries: dict[str, Any],
    strict: bool = False,
    bundle_payload: Mapping[str, Any] | None = None,
    bundle_load_warning: str | None = None,
    metadata_registry_snapshot: Path | None = None,
    metadata_source: str = METADATA_SOURCE_DATABASE,
    registry_shadow_gate: bool = False,
    build_clock: datetime | str | None = None,
    cited_document_query: Mapping[str, Any] | None = None,
    cited_document_result: Mapping[str, Any] | None = None,
    sector_aware_downstream_facts: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """metadata_source defaults to "database", which preserves the exact existing behavior:
    metadata is read from vn_stock.db via load_metadata_slice, and metadata_registry_snapshot /
    registry_shadow_gate are both ignored. Passing metadata_source="registry_snapshot" (with an
    explicit metadata_registry_snapshot file or directory -- never auto-discovered) switches the
    metadata section (only) to load_metadata_slice_from_registry_snapshot instead; setting
    registry_shadow_gate=True on top of that additionally requires a passing shadow comparison
    against the live DB for this ticker before its registry data is used -- see
    _select_metadata_loader and metadata_registry_shadow_compare.check_registry_promotion_gate.
    An invalid config (unknown metadata_source, or registry_snapshot without a path) or a blocked
    gate raises (both are ValueError subclasses), which the existing per-section exception
    handling below turns into a missing/warned metadata section unless strict=True."""
    db_path = VNSTOCK_ROOT / "vn_stock.db"
    frozen_clock = resolve_build_clock(build_clock) if build_clock is not None else None
    context = copy.deepcopy(template)
    context["schema_version"] = "1.4.0"
    context["mode"] = "test_context_package"
    context["ticker"] = ticker
    context["generated_at"] = (frozen_clock.isoformat(timespec="seconds").replace("+00:00", "Z") if frozen_clock is not None else vn_now_iso())
    context["analysis_cutoff"] = None
    context["identity"]["ticker"] = ticker
    context["data_sources"] = []
    context["provenance"] = []

    coverage = check_ticker_coverage(ticker, summaries, db_path)
    warnings: list[str] = []
    not_confirmed: list[str] = []
    missing: list[str] = []

    loaders = {
        "price_summary": lambda: load_price_slice(ticker, db_path),
        "metadata": _select_metadata_loader(
            ticker, db_path, metadata_source, metadata_registry_snapshot, registry_shadow_gate
        ),
        "financial_summary": lambda: load_financial_slice(ticker),
        "news_summary": lambda: load_news_slice(ticker, now=frozen_clock),
        "shareholder_summary": lambda: load_shareholder_slice(ticker, db_path),
        "technical_summary": lambda: load_technical_slice(ticker),
        "share_reconciliation": lambda: load_share_reconciliation_slice(ticker, db_path),
    }
    loaded: dict[str, dict[str, Any]] = {}
    for section, loader in loaders.items():
        try:
            data, provenance = loader()
            loaded[section] = data
            context["provenance"].extend(provenance)
            context["data_sources"].extend(item["source_file"] for item in provenance)
            if not data or (section == "financial_summary" and not data.get("source_rows_found", False)):
                missing.append(section)
                warnings.append(f"{section} is unavailable for {ticker}.")
            elif section == "news_summary" and not is_metric_available(data.get("meta")):
                missing.append(section)
                warnings.append(f"news_summary status is {data.get('status')} for {ticker}; sector/market fallback is kept separate.")
            elif section == "shareholder_summary" and not is_metric_available(data.get("meta")):
                missing.append(section)
                warnings.append(f"shareholder_summary status is {data.get('meta', {}).get('status')} for {ticker}.")
            elif section == "share_reconciliation" and data.get("status") == "unavailable":
                missing.append(section)
                warnings.append(f"share_reconciliation is unavailable for {ticker}: {data.get('reason')}.")
        except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
            if strict:
                raise
            loaded[section] = {}
            missing.append(section)
            warnings.append(f"{section} fallback: {exc}")

    metadata = loaded.get("metadata", {})
    try:
        entity_type = load_vnstock_entity_type(ticker)
    except (OSError, ValueError, RuntimeError, AttributeError) as exc:
        entity_type = "unknown"
        warnings.append(f"entity_type lookup failed for {ticker}: {exc}")
    context["identity"] = {"ticker": ticker, "exchange": metadata.get("exchange"), "industry": metadata.get("industry"),
                           "company_name": metadata.get("company_name"), "activity_status": "not fully confirmed",
                           "status_basis": "metadata exchange plus latest price coverage; explicit trading status not queried",
                           "entity_type": entity_type,
                           "entity_type_warning": "financial ratios gated by entity_type (ebit/ebitda/sga/liquidity) are only structurally not_applicable for a confirmed non-corporate type; entity_type=='unknown' means unclassified, not confirmed corporate"}
    context["metadata"] = metadata
    context["price_summary"] = loaded.get("price_summary", {})
    context["financial_summary"] = loaded.get("financial_summary", {})
    context["technical_summary"] = loaded.get("technical_summary", {})
    context["news_summary"] = loaded.get("news_summary", {})
    context["shareholder_summary"] = loaded.get("shareholder_summary", {})
    context["share_reconciliation"] = loaded.get("share_reconciliation", {})
    external_roe = metadata.get("roe")
    # item A: wrap the external, already-percentage metadata.roe (trailing/TTM, computed by
    # the vnstock library — a different source and methodology than financial_summary's
    # locally-derived roe_quarter/roe_fy/roe_ttm) so a consumer can never mistake this
    # percentage for one of those decimal ratios (the exact "6.94% vs 0.0175" trap).
    if external_roe is not None:
        roe_meta = build_metric_meta(
            external_roe, MetricStatus.REPORTED, source="vnstock_metadata_snapshot",
            period=metadata.get("updated"), basis="trailing_ttm_external_provider", unit="percent",
            confidence=1.0,
            details={"distinct_from": "financial_summary.roe_quarter/roe_fy/roe_ttm are a different source and methodology; do not treat as the same number"},
        )
    else:
        roe_meta = build_metric_meta(
            None, MetricStatus.SOURCE_EMPTY, reason="metadata_roe_not_available",
            source="vnstock_metadata_snapshot", basis="trailing_ttm_external_provider", confidence=0.0,
        )
    context["valuation_inputs"] = {
        "as_of": context["price_summary"].get("last_date"), "price": context["price_summary"].get("latest_close"),
        "market_cap": metadata.get("market_cap"), "pe": metadata.get("pe"), "pb": metadata.get("pb"), "roe": metadata.get("roe"),
        "roe_meta": roe_meta,
        "net_profit_latest": context["financial_summary"].get("net_profit"), "equity_latest": context["financial_summary"].get("equity"),
        "unit_warning": "Price is VND; financial statement unit/scale is not fully confirmed. No new valuation multiples were calculated.",
    }
    context["risks"] = []
    context["latest_available_dates"] = {
        "price": context["price_summary"].get("last_date"),
        "technical": context["technical_summary"].get("latest_signal_date"),
        "metadata_updated": metadata.get("updated"),
        "financial_period": context["financial_summary"].get("latest_period"),
        "shareholder_updated": context["shareholder_summary"].get("latest_snapshot_date"),
        "news_published_utc": context["news_summary"].get("latest_published_utc"),
    }
    not_confirmed.extend(["price adjustment for dividends/splits", "financial statement monetary unit/scale",
                          "financial filing publication/availability dates", "news alias coverage outside configured aliases", "explicit current trading status"])
    warnings.extend(["Context contains data only and is not investment analysis or a buy/sell recommendation.",
                     "Metadata is a current snapshot and shareholder data has no history."])
    context["data_quality"] = {
        "coverage": coverage, "validation_status": "pending_validation", "missing_sections": sorted(set(missing)),
        "warnings": sorted(set(warnings)), "not_fully_confirmed": sorted(set(not_confirmed)),
        "sentinels_normalized": True, "boolean_strings_normalized": True,
        "metric_contract_version": CONTRACT_VERSION,
        "section_coverage": {
            "financial_summary": context["financial_summary"].get("coverage"),
            "news_summary": context["news_summary"].get("coverage"),
            "shareholder_summary": context["shareholder_summary"].get("coverage"),
        },
    }
    context["missing_sections"] = context["data_quality"]["missing_sections"]
    context["warnings"] = context["data_quality"]["warnings"]
    apply_bundle_price_basis_contract(context, bundle_payload, bundle_load_warning)
    apply_bundle_corporate_intelligence_contract(context, bundle_payload, bundle_load_warning)
    apply_bundle_freshness_history_contract(context, bundle_payload)
    apply_bundle_analysis_readiness_contract(context, bundle_payload)
    apply_bundle_financial_canonical_contract(context, bundle_payload)
    apply_bundle_fundamental_quality_contract(context, bundle_payload)
    apply_bundle_opportunity_ranking_contract(context, bundle_payload)
    apply_bundle_relative_valuation_contract(context, bundle_payload)
    apply_bundle_intrinsic_valuation_contract(context, bundle_payload)
    apply_bundle_risk_analysis_contract(context, bundle_payload)
    apply_bundle_financial_period_coverage_contract(context, bundle_payload)
    apply_bundle_valuation_namespaces_contract(context, bundle_payload)
    apply_bundle_share_basis_identities_contract(context, bundle_payload)
    apply_bundle_earnings_anomaly_contract(context, bundle_payload)
    apply_bundle_ta_signal_semantics_contract(context, bundle_payload)
    apply_bundle_news_window_semantics_contract(context, bundle_payload)
    apply_bundle_risk_semantics_contract(context, bundle_payload)
    apply_bundle_analysis_lane_eligibility_contract(context, bundle_payload)
    apply_bundle_distribution_evidence_contract(context, bundle_payload)
    apply_bundle_foreign_flow_contract(context, bundle_payload)
    apply_bundle_current_state_market_risk_contract(context, bundle_payload)
    apply_bundle_current_state_price_analytics_contract(context, bundle_payload)
    apply_bundle_current_state_relative_valuation_contract(context, bundle_payload)
    apply_bundle_fundamental_quality_evidence_contract(context, bundle_payload)
    apply_bundle_canonical_financial_facts_contract(context, bundle_payload)
    apply_bundle_historical_capital_structure_contract(context, bundle_payload)
    apply_bundle_historical_fundamental_brief_contract(context, bundle_payload)
    apply_bundle_historical_decision_analysis_contract(context, bundle_payload)
    apply_bundle_portfolio_risk_analysis_contract(context, bundle_payload)
    apply_bundle_qualified_research_brief_contract(context, bundle_payload)
    apply_bundle_qualified_research_snapshot_v2_contract(context, bundle_payload)
    apply_bundle_qualified_cohort_comparison_contract(context, bundle_payload)
    apply_bundle_qualified_research_delta_contract(context, bundle_payload)
    apply_bundle_qualified_research_change_events_contract(context, bundle_payload)
    apply_bundle_qualified_market_observations_contract(context, bundle_payload)
    apply_bundle_market_wide_current_liquidity_research_contract(context, bundle_payload)
    apply_bundle_market_wide_current_descriptive_research_contract(context, bundle_payload)
    apply_bundle_market_wide_current_fundamental_research_contract(context, bundle_payload)
    apply_bundle_current_market_sector_leadership_context_contract(context, bundle_payload)
    apply_bundle_current_financial_momentum_context_contract(context, bundle_payload)
    apply_bundle_current_corporate_event_context_contract(context, bundle_payload)
    apply_bundle_current_research_risk_register_contract(context, bundle_payload)
    apply_bundle_current_research_scenario_context_contract(context, bundle_payload)
    apply_bundle_market_wide_historical_research_context_contract(context, bundle_payload)
    apply_bundle_market_wide_current_valuation_contract(context, bundle_payload)
    apply_bundle_current_market_flow_positioning_contract(context, bundle_payload)
    apply_bundle_sector_aware_relative_research_contract(context, bundle_payload)
    apply_bundle_current_evidence_bound_scenario_contract(context, bundle_payload)
    apply_bundle_current_daily_decision_research_contract(context, bundle_payload)
    apply_bundle_current_opportunity_decision_context_contract(context, bundle_payload)
    apply_bundle_watchlist_tactical_entry_classifier_contract(context, bundle_payload)
    apply_bundle_current_research_decision_packet_contract(context, bundle_payload)
    apply_bundle_ticker_capability_matrix_contract(context, bundle_payload)
    attach_sector_aware_downstream_facts(context, sector_aware_downstream_facts)
    if cited_document_query is not None or cited_document_result is not None:
        from builders.cited_document_evidence import attach as attach_cited_document_evidence
        attach_cited_document_evidence(context, cited_document_query or {}, cited_document_result or {"state": "unavailable", "reason": "missing_document"})
    context["warnings"] = context["data_quality"]["warnings"]
    context["data_sources"] = sorted(set(context["data_sources"]))
    attach_provenance(context, ["summary layer", "Phase 5 read-only adapters"])
    return context


def attach_sector_aware_downstream_facts(context: dict[str, Any], section: Mapping[str, Any] | None) -> dict[str, Any]:
    """Attach a caller-supplied, same-ticker official-fact section verbatim.

    This is deliberately a read-only pass-through: it performs no calculation,
    aliasing, scaling, conflict resolution, or inference. Omitting ``section``
    leaves legacy contexts byte-compatible because no new key is added.
    """
    if section is None:
        return context
    if not isinstance(section, Mapping) or section.get("contract_version") != "1.0.0" or section.get("section") != "sector_aware_downstream_facts":
        raise ValueError("sector_aware_downstream_facts_contract_invalid")
    facts = section.get("facts")
    if not isinstance(facts, list) or any(not isinstance(fact, Mapping) or fact.get("ticker") != context.get("ticker") for fact in facts):
        raise ValueError("sector_aware_downstream_facts_ticker_isolation_invalid")
    if any(any("path" in str(key).lower() for key in fact) for fact in facts):
        raise ValueError("sector_aware_downstream_facts_path_invalid")
    context["sector_aware_downstream_facts"] = copy.deepcopy(dict(section))
    return context

def attach_provenance(context: dict[str, Any], sources: list[str]) -> dict[str, Any]:
    context["provenance"].append({
        "source_file": sources, "source_dataset": "context_builder",
        "source_keys": {"ticker": context.get("ticker")}, "generated_at": context.get("generated_at"),
        "transformation": "Assemble validated read-only ticker slices into context template; no investment analysis.",
        "assumptions": ["21/63/252 observations approximate 1m/3m/1y trading returns"],
        "limitations": context.get("data_quality", {}).get("not_fully_confirmed", []),
    })
    return context


def validate_context(
    context: dict[str, Any],
    strict: bool = False,
    *,
    profile: str | None = None,
    profile_config: dict[str, Any] | None = None,
    schema_path: Path | None = None,
) -> dict[str, Any]:
    required = ["ticker","generated_at","mode","data_sources","latest_available_dates","identity","metadata",
                "price_summary","financial_summary","valuation_inputs","technical_summary","news_summary",
                "shareholder_summary","risks","data_quality","provenance"]
    missing_keys = [key for key in required if key not in context]
    errors = [f"Missing required key: {key}" for key in missing_keys]
    if not context.get("provenance"):
        errors.append("Provenance is empty")
    if not context.get("ticker"):
        errors.append("Ticker is empty")
    missing_sections = context.get("data_quality", {}).get("missing_sections", [])
    if strict and missing_sections:
        errors.append("Strict mode rejects missing sections: " + ", ".join(missing_sections))
    if strict and context.get("data_quality", {}).get("not_fully_confirmed"):
        errors.append("Strict mode rejects not-fully-confirmed items")
    result = {
        "valid": not errors,
        "valid_semantics": "legacy structural validation; use profile_valid when validation_profile is set",
        "strict": strict,
        "errors": errors,
        "required_sections_present": not missing_keys,
        "missing_sections": missing_sections,
        "provenance_status": "present" if context.get("provenance") else "missing",
    }
    if profile:
        if profile_config is None:
            raise ProfileConfigError("profile_config is required when profile validation is requested")
        result.update(validate_profile(context, profile, profile_config, schema_path=schema_path))
        result["legacy_valid"] = not errors
        result["valid"] = not errors
        if errors:
            result["profile_valid"] = False
    return result


def section_is_available(context: dict[str, Any], section: str) -> bool:
    value = context.get(section)
    if not isinstance(value, dict):
        return bool(value)
    if section in {"news_summary", "shareholder_summary"}:
        return is_metric_available(value.get("meta"))
    if section == "financial_summary":
        return bool(value.get("source_rows_found"))
    return bool(value)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build read-only VNSTOCK ticker context packages.")
    parser.add_argument("positional_ticker", nargs="?", help="Single ticker (backward-compatible shorthand)")
    parser.add_argument("--ticker", action="append", default=[], help="Ticker; repeat flag to build multiple tickers")
    parser.add_argument("--tickers", help="Comma-separated ticker list; combined maximum is 10")
    parser.add_argument("--output", help="Output file for one ticker or output directory for multiple tickers")
    parser.add_argument("--dry-run", action=argparse.BooleanOptionalAction, default=None,
                        help="Dry-run is default; use --no-dry-run to create new export JSON")
    parser.add_argument("--strict", action=argparse.BooleanOptionalAction, default=None,
                        help="Reject missing or not-fully-confirmed context")
    parser.add_argument("--validate-profile",
                        help="Validation profile: current_snapshot, technical_analysis, valuation, forensic, or backtest")
    parser.add_argument("--coverage-report-json", help="Write one-ticker machine-readable report under reports/")
    parser.add_argument("--coverage-report-markdown", help="Write one-ticker human-readable report under reports/")
    parser.add_argument("--metadata-source", choices=VALID_METADATA_SOURCES, default=None,
                        help="Metadata source override; default remains configured database.")
    parser.add_argument("--metadata-registry-snapshot",
                        help="Explicit registry snapshot file or directory; required for registry_snapshot mode.")
    parser.add_argument("--registry-shadow-gate", action=argparse.BooleanOptionalAction, default=None,
                        help="Require exact per-ticker registry-vs-DB comparison before registry use.")
    parser.add_argument("--frozen-clock", help="Optional ISO-8601 UTC clock for reproducible context builds.")
    parser.add_argument("--rotate-existing", action="store_true",
                        help="Rename an existing export to <name>_superseded_<UTC>.json and keep it, "
                             "then write the canonical name fresh. Still never overwrites anything.")
    return parser.parse_args(argv)


def main() -> int:
    args = _parse_args()
    try:
        config = load_json(CONFIG_PATH)
        dry_run = config["dry_run_default"] if args.dry_run is None else args.dry_run
        strict = config["strict_mode_default"] if args.strict is None else args.strict
        metadata_source, metadata_registry_snapshot, registry_shadow_gate = resolve_metadata_source_options(config, args)
        build_clock = resolve_build_clock(args.frozen_clock) if args.frozen_clock else None
        requested = ([args.positional_ticker] if args.positional_ticker else []) + list(args.ticker)
        if args.tickers:
            requested.extend(item for item in args.tickers.split(",") if item.strip())
        max_batch_size = int(config.get("max_batch_size", 10))
        tickers = normalize_ticker_list(requested, max_batch_size=max_batch_size)
        if (args.coverage_report_json or args.coverage_report_markdown) and not args.validate_profile:
            raise ProfileConfigError("Coverage report output requires --validate-profile")
        if (args.coverage_report_json or args.coverage_report_markdown) and len(tickers) != 1:
            raise ProfileConfigError("Coverage report output supports exactly one ticker")
        coverage_json_path = validate_coverage_report_path(Path(args.coverage_report_json), ".json") if args.coverage_report_json else None
        coverage_markdown_path = validate_coverage_report_path(Path(args.coverage_report_markdown), ".md") if args.coverage_report_markdown else None
        coverage_config = None
        schema_path = None
        if args.validate_profile:
            coverage_config = load_coverage_config((WORKSPACE_ROOT / config["validation_profiles_path"]).resolve())
            schema_path = (WORKSPACE_ROOT / config["context_schema_path"]).resolve()
        summaries = load_summary_layer(config)
        template = load_json((WORKSPACE_ROOT / config["context_template_path"]).resolve())
        bundle_payload, bundle_load_warning = load_optional_analysis_bundle(config)
        results = []
        any_profile_failed = False
        any_schema_failed = False
        for ticker in tickers:
            context = build_context_package(
                ticker, template, summaries, strict=strict,
                bundle_payload=bundle_payload, bundle_load_warning=bundle_load_warning,
                metadata_source=metadata_source,
                metadata_registry_snapshot=metadata_registry_snapshot,
                registry_shadow_gate=registry_shadow_gate,
                build_clock=build_clock,
            )
            validation = validate_context(
                context,
                strict=strict,
                profile=args.validate_profile,
                profile_config=coverage_config,
                schema_path=schema_path,
            )
            context["data_quality"]["validation_status"] = "valid" if validation["valid"] else "invalid"
            if args.validate_profile:
                context["data_quality"]["validation_profile"] = args.validate_profile
                context["data_quality"]["profile_validation_status"] = "pass" if validation["profile_valid"] else "fail"
                any_profile_failed = any_profile_failed or not validation["profile_valid"]
                any_schema_failed = any_schema_failed or not validation["schema_valid"]
            if not validation["valid"]:
                raise ValueError(f"{ticker}: " + "; ".join(validation["errors"]))
            if args.output and len(tickers) == 1 and Path(args.output).suffix.lower() == ".json":
                output = Path(args.output)
            else:
                output_dir = Path(args.output) if args.output else Path(config["default_output_dir"])
                output = output_dir / f"{ticker}_context.json"
            safe_output = validate_safe_output_path(output, config)
            if not dry_run:
                save_json(safe_output, context, rotate_existing=bool(args.rotate_existing))
            if coverage_json_path:
                save_coverage_report(coverage_json_path, validation)
            if coverage_markdown_path:
                save_coverage_report(coverage_markdown_path, render_coverage_markdown(validation), markdown=True)
            results.append({"ticker":ticker,"status":"dry_run_ok" if dry_run else "written","output":str(safe_output),
                            "would_write":not dry_run,"validation":validation,
                            "available_sections":[key for key in ["metadata","price_summary","financial_summary","technical_summary","news_summary","shareholder_summary"] if section_is_available(context, key)],
                            "warnings":context["data_quality"]["warnings"]})
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
        if any_schema_failed:
            return 2
        if any_profile_failed:
            return 3
        return 0
    except ProfileConfigError as exc:
        print(f"PROFILE CONFIG ERROR: {exc}", file=sys.stderr)
        return 4
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
