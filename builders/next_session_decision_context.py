"""Read-only Consumer adapter for the Producer's serialized ``next_session_decision_brief/v1``
private-Git handoff package.

This module imports no Producer Python and recomputes nothing: every comparative figure,
availability state, and label below is read verbatim from the already-governed
``next_session_decision_brief.json`` artifact and the handoff package files beside it
(``ai_handoff_publication.py``'s own output). It verifies session identity, current/prior
ordering, producer checkpoint, and package manifest/lineage hashes against the files actually
present, and fails closed -- by raising ``NextSessionDecisionContextError`` -- on any mismatch.

It never derives a score, forecast, probability, target price, position size, or portfolio
allocation, and never merges the bundle-scoped lifecycle cohort with the full-market tactical
transition -- they remain two separately scoped sections.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Mapping

CONSUMER_CONTRACT_VERSION = "ai_next_session_decision_context/v1"
PRODUCER_BRIEF_CONTRACT_VERSION = "next_session_decision_brief/v1"
PRODUCER_BRIEF_SCHEMA_VERSION = "1.0.0"
MANIFEST_CONTRACT_VERSION = "ai_research_bundle_manifest/v1"
LATEST_CONTRACT_VERSION = "stocklookup_ai_handoff_latest/v2"

TACTICAL_SOURCE_IDENTITY_PREFIX = "watchlist_tactical_entry_classifier:"
LIFECYCLE_SOURCE_IDENTITY_PREFIX = "multi_session_thesis_recommendation_lifecycle:"

AVAILABLE, PARTIAL, UNAVAILABLE, NOT_APPLICABLE = "AVAILABLE", "PARTIAL", "UNAVAILABLE", "NOT_APPLICABLE"
_KNOWN_AVAILABILITY = frozenset({AVAILABLE, PARTIAL, UNAVAILABLE, NOT_APPLICABLE})

BRIEF_FILENAME = "next_session_decision_brief.json"
MANIFEST_FILENAME = "ai_research_bundle_manifest.json"
BUNDLE_FILENAME = "ai_research_session_bundle.json"
QUEUE_FILENAME = "daily_opportunity_decision_queue_artifact.json"

# The nine Producer-sourced transition/context sections this Consumer preserves. Each one
# follows the Producer's own ``{availability, reason_codes, ...}`` section shape.
TRANSITION_SECTIONS = (
    "market_transition", "sector_transition", "opportunity_transition", "lifecycle_transition",
    "recommendation_transition", "invalidation_transition", "tactical_transition",
    "risk_context", "next_session_watch_conditions",
)

_ABSOLUTE_PATH = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]{2}|/)")


class NextSessionDecisionContextError(ValueError):
    """A deliberately explicit fail-closed refusal (session/identity/hash/lineage mismatch)."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise NextSessionDecisionContextError(reason)


def _require_file(path: Path, reason: str) -> Path:
    _require(path.is_file(), reason)
    return path


def _read_json(path: Path) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise NextSessionDecisionContextError("PACKAGE_FILE_UNREADABLE:" + path.name) from exc
    _require(isinstance(value, Mapping), "PACKAGE_FILE_NOT_OBJECT:" + path.name)
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise NextSessionDecisionContextError("PACKAGE_FILE_UNREADABLE:" + path.name) from exc
    return digest.hexdigest()


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_identity(value: Mapping[str, Any]) -> dict[str, str]:
    payload = {key: item for key, item in value.items() if key not in {"artifact_sha256", "artifact_identity"}}
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {"artifact_sha256": digest, "artifact_identity": f"ai_next_session_decision_context:{digest}"}


def _producer_brief_content_identity(brief: Mapping[str, Any]) -> dict[str, str]:
    """Reproduce the Producer Brief's canonical ``content_identity`` contract locally.

    The Consumer intentionally does not import Producer code.  It does, however, verify the
    Producer's published deterministic identity over the exact JSON object it loaded.
    """
    payload = {key: item for key, item in brief.items() if key not in {"artifact_sha256", "artifact_identity"}}
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {"artifact_sha256": digest, "artifact_identity": f"next_session_decision_brief:{digest}"}


def _collect_unsafe_paths(value: Any, path: str = "$") -> list[str]:
    """Mirror ``ai_handoff_publication._unsafe`` so an absolute local path never leaks out."""
    found: list[str] = []
    if isinstance(value, str):
        if _ABSOLUTE_PATH.match(value):
            found.append(path)
    elif isinstance(value, Mapping):
        for key, item in value.items():
            found.extend(_collect_unsafe_paths(item, f"{path}.{key}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_collect_unsafe_paths(item, f"{path}[{index}]"))
    return found


# ---------------------------------------------------------------------------
# Package loading and fail-closed validation
# ---------------------------------------------------------------------------

def load_next_session_decision_package(
    build_dir: Path,
    *,
    expected_session: str,
    expected_previous_session: str | None = None,
    expected_producer_checkpoint: str | None = None,
    expected_lineage: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Load and cross-verify one immutable handoff build directory.

    ``build_dir`` must be the exact, already-resolved package path -- this function never
    scans a directory tree or selects "the latest" build; that resolution belongs to a caller
    (or to :func:`load_from_handoff_latest`, which resolves it from the handoff repo's own
    fixed ``LATEST.json`` pointer). Never writes. Fails closed by raising
    ``NextSessionDecisionContextError`` on any structural, session, or hash/lineage mismatch.
    """
    _require(isinstance(expected_session, str) and bool(expected_session), "EXPECTED_SESSION_REQUIRED")
    _require(build_dir.is_dir(), "PACKAGE_BUILD_DIR_MISSING")

    brief_path = _require_file(build_dir / BRIEF_FILENAME, "PACKAGE_FILE_MISSING:" + BRIEF_FILENAME)
    manifest_path = _require_file(build_dir / MANIFEST_FILENAME, "PACKAGE_FILE_MISSING:" + MANIFEST_FILENAME)
    bundle_path = _require_file(build_dir / BUNDLE_FILENAME, "PACKAGE_FILE_MISSING:" + BUNDLE_FILENAME)
    queue_path = _require_file(build_dir / QUEUE_FILENAME, "PACKAGE_FILE_MISSING:" + QUEUE_FILENAME)

    brief = _read_json(brief_path)
    manifest = _read_json(manifest_path)

    # --- Brief self-consistency --------------------------------------------------------
    _require(brief.get("schema_version") == PRODUCER_BRIEF_SCHEMA_VERSION, "BRIEF_SCHEMA_VERSION_UNSUPPORTED")
    _require(brief.get("contract_version") == PRODUCER_BRIEF_CONTRACT_VERSION, "BRIEF_CONTRACT_VERSION_UNSUPPORTED")
    _require(brief.get("current_session") == expected_session, "BRIEF_SESSION_MISMATCH")
    previous_qualified_session = brief.get("previous_qualified_session")
    if expected_previous_session is not None:
        _require(previous_qualified_session == expected_previous_session, "BRIEF_PREVIOUS_SESSION_MISMATCH")
    if previous_qualified_session is not None:
        _require(
            isinstance(previous_qualified_session, str) and previous_qualified_session < expected_session,
            "BRIEF_PREVIOUS_SESSION_NOT_STRICTLY_BEFORE_CURRENT",
        )
    artifact_sha256, artifact_identity = brief.get("artifact_sha256"), brief.get("artifact_identity")
    _require(
        isinstance(artifact_sha256, str) and bool(artifact_sha256)
        and artifact_identity == f"next_session_decision_brief:{artifact_sha256}",
        "BRIEF_IDENTITY_SELF_INCONSISTENT",
    )
    _require(
        _producer_brief_content_identity(brief) == {
            "artifact_sha256": artifact_sha256,
            "artifact_identity": artifact_identity,
        },
        "BRIEF_CONTENT_IDENTITY_MISMATCH",
    )
    binding = brief.get("binding")
    _require(isinstance(binding, Mapping), "BRIEF_BINDING_MISSING")

    # --- Manifest / producer checkpoint --------------------------------------------------
    _require(manifest.get("schema_version") == MANIFEST_CONTRACT_VERSION, "MANIFEST_SCHEMA_VERSION_UNSUPPORTED")
    _require(manifest.get("session") == expected_session, "MANIFEST_SESSION_MISMATCH")
    producer_head = manifest.get("producer_head")
    _require(isinstance(producer_head, str) and bool(producer_head), "MANIFEST_PRODUCER_HEAD_MISSING")
    if expected_producer_checkpoint is not None:
        _require(producer_head == expected_producer_checkpoint, "PRODUCER_CHECKPOINT_MISMATCH")
    _require(
        isinstance(manifest.get("operation_identity"), str)
        and manifest.get("operation_identity") == binding.get("operation_identity"),
        "OPERATION_IDENTITY_MISMATCH",
    )

    # --- Current session bundle: file-hash cross-check only, no JSON parse of the bundle ---
    current_bundle_binding = binding.get("current_session_bundle")
    _require(isinstance(current_bundle_binding, Mapping), "BRIEF_CURRENT_BUNDLE_BINDING_MISSING")
    _require(_sha256_file(bundle_path) == current_bundle_binding.get("sha256"), "BUNDLE_HASH_MISMATCH")
    _require(current_bundle_binding.get("identity") == manifest.get("operation_identity"), "BUNDLE_IDENTITY_MISMATCH")

    # --- Previous session bundle: required exactly when a previous session is expected -----
    if expected_previous_session is not None:
        previous_bundle_path = _require_file(
            build_dir / f"previous_session_bundle_{expected_previous_session}.json",
            "PACKAGE_FILE_MISSING:previous_session_bundle",
        )
        previous_binding = binding.get("previous_session_bundle")
        _require(isinstance(previous_binding, Mapping), "BRIEF_PREVIOUS_BUNDLE_BINDING_MISSING")
        _require(_sha256_file(previous_bundle_path) == previous_binding.get("sha256"), "PREVIOUS_BUNDLE_HASH_MISMATCH")
    else:
        _require(binding.get("previous_session_bundle") is None, "BRIEF_UNEXPECTED_PREVIOUS_BUNDLE_BINDING")

    # --- Opportunity decision queue: identity cross-check (manifest <-> brief); file present ---
    opportunity_lineage = (brief.get("opportunity_transition") or {}).get("source_lineage") or {}
    current_queue_identity = opportunity_lineage.get("current_opportunity_decision_queue_identity")
    manifest_queue_identity = (manifest.get("source_artifact_identities") or {}).get("opportunity_decision_queue")
    if current_queue_identity is not None and manifest_queue_identity is not None:
        _require(current_queue_identity == manifest_queue_identity, "OPPORTUNITY_QUEUE_IDENTITY_MISMATCH")

    # --- Optional package-level lineage (e.g. the handoff repo's own LATEST.json) -----------
    if expected_lineage is not None:
        _require(
            expected_lineage.get("decision_brief_sha256") == _sha256_file(brief_path),
            "LINEAGE_DECISION_BRIEF_SHA256_MISMATCH",
        )
        producer_lineage = expected_lineage.get("producer_lineage") or {}
        _require(
            producer_lineage.get("next_session_decision_brief_identity") == artifact_identity,
            "LINEAGE_DECISION_BRIEF_IDENTITY_MISMATCH",
        )
        _require(expected_lineage.get("producer_checkpoint") == producer_head, "LINEAGE_PRODUCER_CHECKPOINT_MISMATCH")
        _require(
            expected_lineage.get("session_bundle_sha256") == _sha256_file(bundle_path),
            "LINEAGE_SESSION_BUNDLE_SHA256_MISMATCH",
        )
        _require(
            expected_lineage.get("manifest_sha256") == _sha256_file(manifest_path),
            "LINEAGE_MANIFEST_SHA256_MISMATCH",
        )
        _require(
            expected_lineage.get("opportunity_artifact_sha256") == _sha256_file(queue_path),
            "LINEAGE_OPPORTUNITY_ARTIFACT_SHA256_MISMATCH",
        )
        _require(expected_lineage.get("previous_session") == expected_previous_session, "LINEAGE_PREVIOUS_SESSION_MISMATCH")

    return {"brief": brief, "manifest": manifest, "build_dir": build_dir}


def load_from_handoff_latest(
    handoff_repo_root: Path, *, expected_producer_checkpoint: str | None = None,
) -> dict[str, Any]:
    """Read the handoff repo's own fixed ``LATEST.json`` pointer -- one explicitly named file,
    never a directory scan -- and load+verify the package it names."""
    latest_path = _require_file(handoff_repo_root / "LATEST.json", "LATEST_POINTER_MISSING")
    latest = _read_json(latest_path)
    _require(latest.get("schema_version") == LATEST_CONTRACT_VERSION, "LATEST_POINTER_SCHEMA_UNSUPPORTED")
    session = latest.get("latest_session")
    _require(isinstance(session, str) and bool(session), "LATEST_POINTER_SESSION_INVALID")
    immutable_session_path = latest.get("immutable_session_path")
    _require(isinstance(immutable_session_path, str) and bool(immutable_session_path), "LATEST_POINTER_PATH_INVALID")
    package = load_next_session_decision_package(
        handoff_repo_root / immutable_session_path,
        expected_session=session,
        expected_previous_session=latest.get("previous_session"),
        expected_producer_checkpoint=expected_producer_checkpoint,
        expected_lineage=latest,
    )
    package["handoff_build_id"] = latest.get("handoff_build_id")
    package["immutable_session_path"] = immutable_session_path
    return package


# ---------------------------------------------------------------------------
# Context construction (pure transform -- no I/O, no recomputation)
# ---------------------------------------------------------------------------

def _section_availability(section: Any, name: str) -> tuple[str, list[Any]]:
    _require(isinstance(section, Mapping), name.upper() + "_SECTION_MISSING_OR_MALFORMED")
    availability = section.get("availability")
    _require(availability in _KNOWN_AVAILABILITY, name.upper() + "_AVAILABILITY_UNKNOWN:" + str(availability))
    return availability, copy.deepcopy(list(section.get("reason_codes") or []))


def _ai_narrative_contract() -> dict[str, Any]:
    """A static, deterministic instruction block -- never derived from session data."""
    return {
        "contract_version": "ai_next_session_decision_context_narrative/v1",
        "role": (
            "AI RESEARCH NARRATIVE over an already-governed transition projection; not a new "
            "numerical authority, recommendation engine, market-regime model, or ranking."
        ),
        "required_narrative_sections": [
            {"key": "market_state_transition", "label": "A. Market state transition"},
            {"key": "breadth_and_participation", "label": "B. Breadth and participation"},
            {"key": "sector_rotation", "label": "C. Sector rotation"},
            {"key": "opportunity_set_changes", "label": "D. Opportunity-set changes"},
            {"key": "key_tickers_to_monitor", "label": "E. Key tickers to monitor"},
            {"key": "thesis_recommendation_invalidation_changes", "label": "F. Thesis/recommendation/invalidation changes"},
            {"key": "risk_and_concentration_limitations", "label": "G. Risk/concentration limitations"},
            {"key": "next_session_if_then_playbook", "label": "H. Next-session IF/THEN playbook"},
            {"key": "missing_evidence_and_uncertainty", "label": "I. Missing evidence / uncertainty"},
        ],
        "evidence_taxonomy": {
            "categories": ["Fact", "Derived", "Inference", "Opinion/scenario"],
            "source": "knowledge/AIUsageRules.md (this repository's existing taxonomy; do not substitute a new UNKNOWN category)",
            "definitions": {
                "Fact": "A value read directly from this context package, with its section/field cited.",
                "Derived": "A calculation reproducible from Facts already in this package, with the formula shown.",
                "Inference": "An uncertain logical conclusion, stated with its supporting evidence and counter-evidence.",
                "Opinion/scenario": "A conditional judgment, explicitly not a fact.",
            },
        },
        "label_preservation_rules": [
            "Quote every recommendation_transition/invalidation_transition value and reason_code exactly as supplied; PARTIAL and MISSING_PREVIOUS_CONTEXT must never be translated into UNCHANGED, NEUTRAL, WAIT, or SELL.",
            "WAIT_FOR_CONFIRMATION is not SELL. AVOID_NEW_ENTRY is not a forced exit. HIGH_RISK_SPECULATION_ONLY is a distinct lane and must never be merged with any other label.",
            "lifecycle_transition (scope SESSION_BUNDLE_COMPARABLE_TICKER_COHORT) and tactical_transition (scope FULL_MARKET_WATCHLIST_TACTICAL_ENTRY_CLASSIFIER) are separate contracts with different cohorts and denominators; never merge them into one unlabeled 'technical signal' statement -- always name which one, its scope, and its cohort size.",
            "next_session_watch_conditions.conditions[].condition_type (TRIGGER/INVALIDATION) and if_satisfied (REEVALUATE_CLASSIFICATION/FLAG_INVALIDATION) must be quoted exactly; never restate a condition as a numeric price target or probability.",
            "risk_context reflects the C2 correlation/concentration engine; when its availability is NOT_APPLICABLE, state that plainly and never infer a correlation, concentration, or diversification conclusion from ticker lists in other sections.",
        ],
        "forbidden_outputs": [
            "probabilities", "target_prices", "expected_returns", "position_sizing", "allocation_weights",
            "unsupported_buy_sell_hold", "unsupported_causal_explanations",
            "external_news_or_macroeconomic_claims_not_present_in_this_context",
        ],
        "external_research_rule": (
            "Outside web/news/macro research, if supplied separately, must be clearly labeled EXTERNAL and may "
            "add color only; it can never overwrite, silently override, or upgrade any Producer evidence, "
            "availability state, or label in this context."
        ),
        "citation_format": "[section.field] referencing this package's own top-level keys, matching this repository's existing internal citation convention (see knowledge/AIUsageRules.md).",
        "missingness_rule": "A section whose availability is UNAVAILABLE, PARTIAL, or NOT_APPLICABLE must still be named explicitly in the narrative as a limitation; never silently omitted or treated as zero/neutral.",
        "is_actionable": False,
    }


def build_context(package: Mapping[str, Any]) -> dict[str, Any]:
    """Build one ``ai_next_session_decision_context/v1`` from an already-validated package
    (the return value of :func:`load_next_session_decision_package`). Pure transform: no I/O,
    no recomputation of any Producer figure.
    """
    brief, manifest = package["brief"], package["manifest"]
    binding = brief["binding"]

    lifecycle = copy.deepcopy(brief["lifecycle"])
    lifecycle_identity = (lifecycle.get("source_lineage") or {}).get("lifecycle_artifact_identity")
    if lifecycle_identity is not None:
        _require(
            str(lifecycle_identity).startswith(LIFECYCLE_SOURCE_IDENTITY_PREFIX),
            "LIFECYCLE_TRANSITION_UNEXPECTED_SOURCE_IDENTITY",
        )
    lifecycle["scope"] = "SESSION_BUNDLE_COMPARABLE_TICKER_COHORT"

    tactical = copy.deepcopy(brief["tactical_transition"])
    tactical_identity = (tactical.get("source_lineage") or {}).get("current_tactical_artifact_identity")
    if tactical_identity is not None:
        _require(
            str(tactical_identity).startswith(TACTICAL_SOURCE_IDENTITY_PREFIX),
            "TACTICAL_TRANSITION_UNEXPECTED_SOURCE_IDENTITY",
        )
    tactical["scope"] = "FULL_MARKET_WATCHLIST_TACTICAL_ENTRY_CLASSIFIER"

    context: dict[str, Any] = {
        "schema_version": "1.0.0",
        "contract_version": CONSUMER_CONTRACT_VERSION,
        "identity": {
            "consumer_contract_version": CONSUMER_CONTRACT_VERSION,
            "producer_brief_contract_version": brief["contract_version"],
            "producer_brief_schema_version": brief["schema_version"],
            "current_session": brief["current_session"],
            "previous_qualified_session": brief["previous_qualified_session"],
            "producer_brief_artifact_identity": brief["artifact_identity"],
            "producer_brief_artifact_sha256": brief["artifact_sha256"],
        },
        "source_lineage": {
            "producer_checkpoint": manifest.get("producer_head"),
            "producer_head": manifest.get("producer_head"),
            "operation_identity": manifest.get("operation_identity"),
            "run_identity": binding.get("run_identity"),
            "run_identity_availability": binding.get("run_identity_availability"),
            "run_identity_reason_codes": copy.deepcopy(binding.get("run_identity_reason_codes") or []),
            "current_session_bundle": copy.deepcopy(binding.get("current_session_bundle")),
            "previous_session_bundle": copy.deepcopy(binding.get("previous_session_bundle")),
            "opportunity_decision_queue_identity": (
                (brief.get("opportunity_transition") or {}).get("source_lineage") or {}
            ).get("current_opportunity_decision_queue_identity"),
            "handoff_build_id": package.get("handoff_build_id"),
            "immutable_session_path": package.get("immutable_session_path"),
            "manifest_schema_version": manifest.get("schema_version"),
            "package_authority_boundary": copy.deepcopy(manifest.get("authority_boundary")),
            "package_warnings": copy.deepcopy(manifest.get("warnings") or []),
        },
        "authority_boundary": copy.deepcopy(brief["authority_boundary"]),
        "market_transition": copy.deepcopy(brief["market_transition"]),
        "sector_transition": copy.deepcopy(brief["sector_transition"]),
        "opportunity_transition": copy.deepcopy(brief["opportunity_transition"]),
        "lifecycle_transition": lifecycle,
        "recommendation_transition": copy.deepcopy(brief["recommendation_transition"]),
        "invalidation_transition": copy.deepcopy(brief["invalidation_transition"]),
        "tactical_transition": tactical,
        "risk_context": copy.deepcopy(brief["correlation_concentration_context"]),
        "next_session_watch_conditions": copy.deepcopy(brief["next_session_watch_conditions"]),
    }

    missingness: dict[str, Any] = {}
    for name in TRANSITION_SECTIONS:
        availability, reason_codes = _section_availability(context.get(name), name)
        missingness[name] = {"availability": availability, "reason_codes": reason_codes}
    context["missingness"] = missingness
    context["ai_narrative_contract"] = _ai_narrative_contract()

    unsafe_paths = _collect_unsafe_paths(context)
    _require(not unsafe_paths, "OUTPUT_CONTAINS_ABSOLUTE_PATH:" + ",".join(unsafe_paths[:3]))

    context.update(content_identity(context))
    return context
