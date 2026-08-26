"""Read-only ingestion of one explicitly named Daily Producer run manifest.

This boundary deliberately accepts the immutable operational evidence that a
Daily Producer run materializes.  It does not discover a runtime directory,
select a latest run, import Producer code, or derive Producer decisions.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from builders.build_ticker_context import current_daily_decision_research_contract


DAILY_PRODUCER_RUN_CONTRACT = "daily_producer_run/v1"
AI_BUNDLE_MANIFEST_CONTRACT = "ai_research_bundle_manifest/v1"
AI_RESEARCH_SESSION_BUNDLE_CONTRACT = "ai_research_session_bundle/v1"
CONSUMER_COMPATIBLE_CONTRACT = "current_daily_decision_research_contract/v1"
RUN_MANIFEST_FILENAME = "run_manifest.json"
AI_MANIFEST_FILENAME = "ai_research_bundle_manifest.json"
AI_BUNDLE_FILENAME = "ai_research_session_bundle.json"


class CanonicalDailyProducerSessionError(ValueError):
    """A concise, deterministic refusal to consume operational evidence."""


def _load_json(path: Path, reason: str) -> Mapping[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CanonicalDailyProducerSessionError(reason) from exc
    if not isinstance(value, Mapping):
        raise CanonicalDailyProducerSessionError(reason)
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_ARTIFACT_UNREADABLE") from exc
    return digest.hexdigest()


def _require_string(value: Any, reason: str, *, prefix: str | None = None) -> str:
    if not isinstance(value, str) or not value or (prefix is not None and not value.startswith(prefix)):
        raise CanonicalDailyProducerSessionError(reason)
    return value


def _verify_hash(manifest: Mapping[str, Any], filename: str, path: Path) -> None:
    record = (manifest.get("files") or {}).get(filename)
    if not isinstance(record, Mapping) or not isinstance(record.get("sha256"), str):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_DELIVERY_HASH_MISSING:" + filename)
    if _sha256(path) != record["sha256"]:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_DELIVERY_HASH_MISMATCH:" + filename)


def _daily_card_context(
    ticker: str,
    card: Mapping[str, Any],
    bundle: Mapping[str, Any],
) -> dict[str, Any]:
    """Adapt an already-produced card to the established Consumer card contract."""
    context = {
        "ticker": ticker,
        "current_daily_decision_research": {
            **copy.deepcopy(dict(card)),
            "source_artifact_identity": bundle["product_identity"],
            "source_session": bundle["session"],
            "market_brief": copy.deepcopy((bundle.get("market") or {}).get("summary")),
            "authority_boundary": copy.deepcopy(bundle["authority_boundary"]),
            "is_actionable": False,
        },
    }
    accepted = current_daily_decision_research_contract(
        {"tickers": {ticker: {"current_daily_decision_research": context["current_daily_decision_research"]}}}, ticker,
    )
    if not isinstance(accepted, Mapping) or accepted.get("status") == "malformed":
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_TICKER_CONTEXT_INVALID:" + ticker)
    context["current_daily_decision_research"] = copy.deepcopy(dict(accepted))
    return context


def load_canonical_daily_producer_session(
    producer_session_manifest: str | Path,
    *,
    session: str,
) -> dict[str, Any]:
    """Load exactly one named Daily Producer run and its canonical ticker contexts.

    ``producer_session_manifest`` is an explicit retained ``run_manifest.json`` path.
    The two delivery files are resolved only by their fixed filenames beside that
    manifest; no directory enumeration, time-based selection, or Producer import occurs.
    """
    if not isinstance(session, str) or not session:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_SESSION_REQUIRED")
    run_path = Path(producer_session_manifest)
    if run_path.name != RUN_MANIFEST_FILENAME:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_RUN_MANIFEST_FILENAME_INVALID")
    run = _load_json(run_path, "DAILY_PRODUCER_RUN_MANIFEST_INVALID")
    if run.get("schema_version") != DAILY_PRODUCER_RUN_CONTRACT:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_RUN_CONTRACT_UNSUPPORTED")
    if run.get("target_market_session") != session:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_RUN_SESSION_MISMATCH")
    run_identity = _require_string(run.get("run_identity"), "DAILY_PRODUCER_RUN_IDENTITY_INVALID", prefix="daily_producer_run:")
    operation = run.get("daily_session_operation")
    if not isinstance(operation, Mapping):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_OPERATION_IDENTITY_MISSING")
    operation_identity = _require_string(
        operation.get("identity"), "DAILY_PRODUCER_OPERATION_IDENTITY_INVALID", prefix="daily_research_session_operation:",
    )
    producer_head = _require_string(run.get("producer_head"), "DAILY_PRODUCER_PRODUCER_HEAD_MISSING")
    _require_string(run.get("daily_product_identity"), "DAILY_PRODUCER_PRODUCT_IDENTITY_INVALID", prefix="current_daily_decision_research_product:")

    ai_manifest_path = run_path.with_name(AI_MANIFEST_FILENAME)
    bundle_path = run_path.with_name(AI_BUNDLE_FILENAME)
    ai_manifest = _load_json(ai_manifest_path, "DAILY_PRODUCER_AI_MANIFEST_INVALID")
    bundle = _load_json(bundle_path, "DAILY_PRODUCER_AI_BUNDLE_INVALID")
    ai_delivery = run.get("ai_delivery")
    if not isinstance(ai_delivery, Mapping):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_RUN_DELIVERY_MISSING")
    for filename, path in ((AI_MANIFEST_FILENAME, ai_manifest_path), (AI_BUNDLE_FILENAME, bundle_path)):
        record = ai_delivery.get(filename)
        if not isinstance(record, Mapping) or record.get("sha256") != _sha256(path):
            raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_RUN_DELIVERY_HASH_MISMATCH:" + filename)

    if ai_manifest.get("schema_version") != AI_BUNDLE_MANIFEST_CONTRACT:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AI_MANIFEST_CONTRACT_UNSUPPORTED")
    if ai_manifest.get("session") != session:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AI_MANIFEST_SESSION_MISMATCH")
    if ai_manifest.get("operation_identity") != operation_identity:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_OPERATION_IDENTITY_MISMATCH")
    if ai_manifest.get("producer_head") != producer_head:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_PRODUCER_HEAD_MISMATCH")
    if ai_manifest.get("consumer_compatible_contract_version") != CONSUMER_COMPATIBLE_CONTRACT:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_CONSUMER_CONTRACT_UNSUPPORTED")
    if ai_manifest.get("primary_bundle_filename") != AI_BUNDLE_FILENAME:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_PRIMARY_BUNDLE_REFERENCE_INVALID")
    _verify_hash(ai_manifest, AI_BUNDLE_FILENAME, bundle_path)

    if bundle.get("schema_version") != AI_RESEARCH_SESSION_BUNDLE_CONTRACT:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AI_BUNDLE_CONTRACT_UNSUPPORTED")
    if bundle.get("session") != session:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AI_BUNDLE_SESSION_MISMATCH")
    if bundle.get("operation_identity") != operation_identity:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AI_BUNDLE_OPERATION_IDENTITY_MISMATCH")
    if bundle.get("producer_head") != producer_head:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AI_BUNDLE_PRODUCER_HEAD_MISMATCH")
    if bundle.get("consumer_compatible_contract_version") != CONSUMER_COMPATIBLE_CONTRACT:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AI_BUNDLE_CONSUMER_CONTRACT_UNSUPPORTED")
    if bundle.get("product_identity") != run.get("daily_product_identity"):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_PRODUCT_IDENTITY_MISMATCH")
    upstream = run.get("upstream_artifact_identities")
    lineage = bundle.get("lineage")
    if not isinstance(upstream, Mapping) or not isinstance(lineage, Mapping):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_INPUT_LINEAGE_MISSING")
    if lineage.get("input_artifacts") != upstream:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_INPUT_LINEAGE_MISMATCH")
    if not isinstance(ai_manifest.get("source_artifact_identities"), Mapping):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_SOURCE_IDENTITIES_MISSING")
    if not isinstance(bundle.get("authority_boundary"), Mapping):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_AUTHORITY_BOUNDARY_MISSING")
    if not isinstance((bundle.get("market") or {}).get("summary"), Mapping):
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_MARKET_BRIEF_MISSING")
    cards = bundle.get("ticker_research_contexts")
    if not isinstance(cards, Mapping) or not cards:
        raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_TICKER_CONTEXTS_MISSING")

    contexts: dict[str, dict[str, Any]] = {}
    for ticker in sorted(cards):
        card = cards[ticker]
        if not isinstance(ticker, str) or not isinstance(card, Mapping):
            raise CanonicalDailyProducerSessionError("DAILY_PRODUCER_TICKER_CONTEXTS_INVALID")
        contexts[ticker] = _daily_card_context(ticker, card, bundle)
    provenance = {
        "producer_session_manifest": str(run_path),
        "run_identity": run_identity,
        "operation_identity": operation_identity,
        "product_identity": bundle["product_identity"],
        "producer_head": producer_head,
        "session": session,
        "input_artifact_identities": copy.deepcopy(dict(upstream)),
        "source_artifact_identities": copy.deepcopy(dict(ai_manifest["source_artifact_identities"])),
        "ai_bundle_sha256": _sha256(bundle_path),
        "ai_manifest_sha256": _sha256(ai_manifest_path),
    }
    return {"ticker_contexts": contexts, "provenance": provenance}
