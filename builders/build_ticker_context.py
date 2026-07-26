"""Read-only VNSTOCK ticker context builder.

The builder reads a small ticker slice from SQLite/CSV sources, never writes to
VNSTOCK, and only creates new JSON files under the approved AI ANALYZE exports
area. It produces data context, not investment analysis or recommendations.
"""

from __future__ import annotations

import argparse
import copy
import csv
import importlib.util
import json
import math
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping


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


def load_optional_analysis_bundle(config: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    """Load the configured Phase 1 bundle without making it a required runtime input."""
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
    return payload, None


def normalize_price_basis_contract(bundle: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Read Phase 1's additive price-basis fields with a safe legacy fallback."""
    bundle = bundle or {}
    raw_basis = bundle.get("price_basis")
    basis = str(raw_basis).strip().lower() if raw_basis is not None else ""
    verified = bundle.get("price_basis_verified") is True
    if verified and basis in {"raw", "adjusted"}:
        provenance = bundle.get("price_basis_provenance")
        return {
            "price_basis": basis,
            "price_basis_verified": True,
            "price_basis_provenance": dict(provenance) if isinstance(provenance, Mapping) else {},
        }
    return {
        "price_basis": "unknown",
        "price_basis_verified": False,
        "price_basis_provenance": (
            dict(bundle["price_basis_provenance"])
            if isinstance(bundle.get("price_basis_provenance"), Mapping)
            else {"source": "missing_or_unverified_bundle_price_basis"}
        ),
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
    flags = [flag for flag in quality.get("flags", [])
             if not (isinstance(flag, Mapping) and flag.get("code") == PRICE_BASIS_UNVERIFIED_CODE)]
    warnings = list(quality.get("warnings", []))
    warnings = [warning for warning in warnings if "price basis is unverified" not in str(warning).lower()]
    not_confirmed = list(quality.get("not_fully_confirmed", []))
    not_confirmed = [item for item in not_confirmed if item != "OHLCV price basis"]

    if not contract["price_basis_verified"]:
        flags.append({
            "scope": "pipeline", "ticker": context.get("ticker"), "code": PRICE_BASIS_UNVERIFIED_CODE,
            "severity": "warning", "metric": "price_basis", "evidence": contract,
            "message": "OHLCV price basis is unverified; corporate actions may affect return, MA, and RS.",
            "consumer_action": "Do not assume raw or adjusted prices; qualify OHLCV-derived conclusions.",
        })
        warnings.append("OHLCV price basis is unverified; corporate actions may affect return, MA, and RS.")
        not_confirmed.append("OHLCV price basis")
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
        "limitations": [] if contract["price_basis_verified"] else ["OHLCV basis is not verified"],
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
    """Pass through producer readiness without turning it into a business fact."""
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
    return {"status": "available", "reference_at": raw.get("reference_at"), "domains": domains, "data_warnings": warnings, "unknowns": [name for name, value in domains.items() if value.get("state") in {"unknown", "blocked"}], "inferences_allowed": all(value.get("state") == "ready" for value in domains.values())}

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


def save_json(path: Path, payload: Any) -> None:
    safe = validate_safe_output_path(path)
    if safe.exists():
        raise FileExistsError(f"Refusing to overwrite existing output: {safe}")
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


def load_news_slice(ticker: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
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
) -> dict[str, Any]:
    db_path = VNSTOCK_ROOT / "vn_stock.db"
    context = copy.deepcopy(template)
    context["schema_version"] = "1.4.0"
    context["mode"] = "test_context_package"
    context["ticker"] = ticker
    context["generated_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
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
        "metadata": lambda: load_metadata_slice(ticker, db_path),
        "financial_summary": lambda: load_financial_slice(ticker),
        "news_summary": lambda: load_news_slice(ticker),
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
    context["warnings"] = context["data_quality"]["warnings"]
    context["data_sources"] = sorted(set(context["data_sources"]))
    attach_provenance(context, ["summary layer", "Phase 5 read-only adapters"])
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


def _parse_args() -> argparse.Namespace:
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
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        config = load_json(CONFIG_PATH)
        dry_run = config["dry_run_default"] if args.dry_run is None else args.dry_run
        strict = config["strict_mode_default"] if args.strict is None else args.strict
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
                save_json(safe_output, context)
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
