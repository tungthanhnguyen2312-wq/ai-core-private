"""Read-only Consumer contract for Producer shadow-recommendation narratives.

This module intentionally imports no Producer Python.  It accepts only the serialized
``tickers[*].shadow_security_recommendation`` bundle attachment and treats the Producer
packet as immutable.  It prepares deterministic prompt data, validates proposed
narratives, and supplies a small non-LLM fallback formatter.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter
from typing import Any, Mapping

from builders.correlation_concentration_consumer_context import parse_correlation_concentration_context


CONSUMER_CONTRACT_VERSION = "shadow_recommendation_consumer_narrative/v1"
PRODUCER_CONTRACT_VERSION = "shadow_security_recommendation/v1"
ATTACHMENT_KEY = "shadow_security_recommendation"
LABELS = frozenset({
    "INITIATE_RESEARCH_CANDIDATE", "ACCUMULATE_RESEARCH_CANDIDATE",
    "WAIT_FOR_CONFIRMATION", "HIGH_RISK_SPECULATION_ONLY", "AVOID_NEW_ENTRY",
    "INSUFFICIENT_EVIDENCE",
})
READINESS = frozenset({"RECOMMENDATION_READY", "RECOMMENDATION_CONDITIONAL", "RECOMMENDATION_NOT_READY"})
REQUIRED_PACKET_SECTIONS = (
    "recommendation", "thesis_context", "market_confirmation", "technical_invalidation",
    "fundamental_invalidation", "catalyst_context", "valuation_context", "risk_context",
    "monitoring_context", "temporal_context", "authority_boundaries", "input_lineage",
)
NARRATIVE_FIELDS = (
    "ticker", "as_of_session", "producer_artifact_identity", "recommendation_label",
    "recommendation_readiness", "stance", "supporting_evidence", "uncertainties",
    "confirmation", "invalidation", "catalyst", "valuation", "risk", "watch_items",
    "counter_thesis", "authority", "lineage",
)
CORRELATION_CONCENTRATION_FIELD = "correlation_concentration_context"
_PROHIBITED_KEYS = frozenset({
    "action", "buy", "sell", "hold", "target_price", "price_target", "probability",
    "position_size", "position_sizing", "portfolio_weight", "allocation", "risk_budget",
})
_PROHIBITED_TEXT = re.compile(
    r"\b(buy|sell|hold|target\s+price|price\s+target|probability|position\s+size|portfolio\s+(?:weight|allocation)|risk\s+budget)\b",
    re.IGNORECASE,
)
_NUMBER = re.compile(r"(?<![A-Za-z_])-?\d+(?:\.\d+)?")


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def content_identity(value: Mapping[str, Any]) -> dict[str, str]:
    payload = {key: item for key, item in value.items() if key not in {"artifact_sha256", "artifact_identity"}}
    digest = hashlib.sha256(_canonical(payload).encode("utf-8")).hexdigest()
    return {"artifact_sha256": digest, "artifact_identity": f"shadow_recommendation_consumer_narrative:{digest}"}


def _result(status: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, **extra}


def _explicit_or_legacy_v1(attachment: Mapping[str, Any], packet: Mapping[str, Any]) -> str | None:
    """Return the only supported producer version.

    Current Producer bundle serialization deliberately exposes source identity plus the
    packet, but not the artifact's contract-version scalar.  The exact, opt-in envelope
    is therefore the documented backwards-compatible V1 wire form.  Any explicit
    version must be V1; a future producer must add its explicit version rather than
    silently inheriting this compatibility branch.
    """
    explicit = attachment.get("producer_contract_version", attachment.get("contract_version"))
    if explicit is not None:
        return explicit if explicit == PRODUCER_CONTRACT_VERSION else None
    source_identity = attachment.get("source_artifact_identity")
    if (
        attachment.get("shadow_mode") == "SHADOW_OPT_IN"
        and attachment.get("is_actionable") is False
        and isinstance(source_identity, str)
        and source_identity.startswith("shadow_security_recommendation:")
        and isinstance(packet.get("recommendation"), Mapping)
    ):
        return PRODUCER_CONTRACT_VERSION
    return None


def parse_shadow_recommendation_attachment(
    ticker_entry: Mapping[str, Any] | None, *, expected_ticker: str | None = None,
) -> dict[str, Any]:
    """Parse a single serialized optional attachment without recomputation or remapping."""
    if not isinstance(ticker_entry, Mapping) or ATTACHMENT_KEY not in ticker_entry:
        return _result("SHADOW_RECOMMENDATION_NOT_ATTACHED")
    attachment = ticker_entry.get(ATTACHMENT_KEY)
    if not isinstance(attachment, Mapping):
        return _result("SHADOW_RECOMMENDATION_MALFORMED_ATTACHMENT")
    packet = attachment.get("recommendation_packet")
    if not isinstance(packet, Mapping):
        return _result("SHADOW_RECOMMENDATION_MALFORMED_PACKET")
    version = _explicit_or_legacy_v1(attachment, packet)
    if version is None:
        return _result("UNSUPPORTED_SHADOW_RECOMMENDATION_CONTRACT")
    missing = [name for name in REQUIRED_PACKET_SECTIONS if name not in packet]
    recommendation = packet.get("recommendation")
    if missing or not isinstance(recommendation, Mapping):
        return _result("SHADOW_RECOMMENDATION_MALFORMED_PACKET", missing_sections=missing)
    ticker = packet.get("ticker")
    as_of = recommendation.get("as_of_session")
    label = recommendation.get("recommendation_label")
    readiness = recommendation.get("recommendation_readiness")
    if (
        not isinstance(ticker, str) or (expected_ticker is not None and ticker != expected_ticker)
        or not isinstance(as_of, str) or label not in LABELS or readiness not in READINESS
    ):
        return _result("SHADOW_RECOMMENDATION_MALFORMED_PACKET")
    identity = attachment.get("source_artifact_identity")
    if not isinstance(identity, str) or not identity.startswith("shadow_security_recommendation:"):
        return _result("SHADOW_RECOMMENDATION_MALFORMED_ATTACHMENT")
    producer_authority = packet.get("authority_boundaries")
    temporal = packet.get("temporal_context")
    if not isinstance(producer_authority, Mapping) or not isinstance(temporal, Mapping):
        return _result("SHADOW_RECOMMENDATION_MALFORMED_PACKET")
    authority = copy.deepcopy(dict(producer_authority))
    # These are byte-exact aliases from Producer fields, not Consumer policy decisions.
    authority["shadow_research_only"] = authority.get("shadow_research_recommendation_only")
    authority["same_close_execution_eligibility"] = temporal.get("close_price_execution_eligibility")
    required_false = (
        "personalized_advice_authority", "trade_execution_authority", "portfolio_allocation_authority",
        "position_sizing_authority", "target_price_authority", "probability_authority",
        "historical_pit_authority", "historical_backtest_authority",
    )
    if authority.get("shadow_research_only") is not True or authority.get("same_close_execution_eligibility") != "NOT_ESTABLISHED" or any(authority.get(key) is not False for key in required_false):
        return _result("SHADOW_RECOMMENDATION_MALFORMED_PACKET")
    return _result(
        "SHADOW_RECOMMENDATION_READY",
        narrative_input={
            "consumer_contract_version": CONSUMER_CONTRACT_VERSION,
            "producer_contract_version": version,
            "ticker": ticker,
            "as_of_session": as_of,
            "producer_artifact_identity": identity,
            "recommendation_label": label,
            "recommendation_readiness": readiness,
            "recommendation_packet": copy.deepcopy(dict(packet)),
            # Per-packet authority is the usable narrative boundary.  The attachment-level
            # block is retained provenance but is broader and cannot replace it.
            "authority_boundary": authority,
            "attachment_authority_boundary": copy.deepcopy(attachment.get("authority_boundary")),
            "shadow_mode": "SHADOW_OPT_IN",
            "is_actionable": False,
            "AI_NARRATIVE_CANNOT_OVERRIDE_PRODUCER_RECOMMENDATION": True,
        },
    )


def _locator(section: str, field: str, source_identity: str) -> dict[str, str]:
    return {"source_section": section, "source_field": field, "input_identity": source_identity}


def _claim(text: str, section: str, field: str, identity: str) -> dict[str, Any]:
    return {"text": text, "source_locator": _locator(section, field, identity), "numeric_facts": []}


def _status_text(value: Mapping[str, Any] | None, default: str = "UNKNOWN") -> str:
    return str((value or {}).get("status", default))


def response_fields(narrative_input: Mapping[str, Any]) -> tuple[str, ...]:
    """Keep the no-C2 response shape byte-compatible with V1."""
    return NARRATIVE_FIELDS + ((CORRELATION_CONCENTRATION_FIELD,) if isinstance(narrative_input.get(CORRELATION_CONCENTRATION_FIELD), Mapping) else ())


def attach_correlation_concentration_context(narrative_input: Mapping[str, Any], artifact: Mapping[str, Any] | None) -> dict[str, Any]:
    """Attach only validated serialized C2 context; never infer a correlation result."""
    if not isinstance(narrative_input, Mapping):
        return _result("CORRELATION_CONCENTRATION_NARRATIVE_INPUT_INVALID")
    parsed = parse_correlation_concentration_context(
        artifact, ticker=narrative_input.get("ticker"), recommendation_label=narrative_input.get("recommendation_label"),
        recommendation_readiness=narrative_input.get("recommendation_readiness"),
    )
    if parsed["status"] != "CORRELATION_CONCENTRATION_READY":
        return parsed
    attached = copy.deepcopy(dict(narrative_input))
    attached[CORRELATION_CONCENTRATION_FIELD] = parsed["context"]
    return _result("CORRELATION_CONCENTRATION_READY", narrative_input=attached)


def build_prompt_payload(narrative_input: Mapping[str, Any]) -> dict[str, Any]:
    """Build a deterministic, model-provider-neutral prompt payload; never call a model."""
    packet = narrative_input.get("recommendation_packet") if isinstance(narrative_input, Mapping) else None
    if not isinstance(packet, Mapping):
        raise ValueError("SHADOW_RECOMMENDATION_NARRATIVE_INPUT_INVALID")
    correlation = narrative_input.get(CORRELATION_CONCENTRATION_FIELD)
    system_rules = [
        "AI_NARRATIVE_CANNOT_OVERRIDE_PRODUCER_RECOMMENDATION.",
        "Explain the immutable Producer label and readiness; do not re-decide.",
        "Use only supplied packet facts and source locators; UNKNOWN remains UNKNOWN.",
        "Do not create BUY, SELL, HOLD, targets, probabilities, portfolio allocation, sizing, or risk budgets.",
        "Absent optional catalyst, valuation, or risk context stays absent or unavailable.",
        "Counter-thesis must cite supplied evidence, warnings, or reason codes.",
        "Preserve as_of_session and all authority boundaries exactly.",
    ]
    if isinstance(correlation, Mapping):
        system_rules.extend([
            "C2 correlation/concentration material is immutable Producer research context; explain it but do not recompute it.",
            "The C2 threshold is a non-calibrated research heuristic; correlation is not causation.",
            "Preserve partial pairwise and joint-matrix readiness exactly; do not infer diversification or allocation.",
        ])
    payload = {
        "contract_version": CONSUMER_CONTRACT_VERSION,
        "input_identity": narrative_input.get("producer_artifact_identity"),
        "system_rules": system_rules,
        "immutable_identity": {
            key: narrative_input.get(key)
            for key in ("ticker", "as_of_session", "producer_artifact_identity", "recommendation_label", "recommendation_readiness")
        },
        "packet": copy.deepcopy(dict(packet)),
        "response_schema": list(response_fields(narrative_input)),
    }
    if isinstance(correlation, Mapping):
        payload[CORRELATION_CONCENTRATION_FIELD] = copy.deepcopy(dict(correlation))
    return payload


def render_fallback_narrative(narrative_input: Mapping[str, Any]) -> dict[str, Any]:
    """Format upstream values into an auditable narrative without changing policy."""
    packet = narrative_input["recommendation_packet"]
    identity = narrative_input["producer_artifact_identity"]
    recommendation = packet["recommendation"]
    thesis = packet.get("thesis_context") or {}
    technical = packet.get("technical_invalidation") or {}
    fundamental = packet.get("fundamental_invalidation") or {}
    catalyst = packet.get("catalyst_context") or {}
    valuation = packet.get("valuation_context") or {}
    risk = packet.get("risk_context") or {}
    monitoring = packet.get("monitoring_context") or []
    warnings = packet.get("warnings") or []
    reason_codes = recommendation.get("recommendation_reason_codes") or []
    evidence_field = "thesis_evidence" if thesis.get("thesis_evidence") else "research_case_eligibility"
    evidence_text = "Producer thesis evidence is retained." if evidence_field == "thesis_evidence" else "Producer research-case eligibility bounds the stance."
    counter_field = "warnings" if warnings else "recommendation_reason_codes"
    counter_text = "Producer warnings form the counter-thesis." if warnings else "Producer reason codes bound the counter-thesis."
    result = {
        "ticker": narrative_input["ticker"],
        "as_of_session": narrative_input["as_of_session"],
        "producer_artifact_identity": identity,
        "recommendation_label": narrative_input["recommendation_label"],
        "recommendation_readiness": narrative_input["recommendation_readiness"],
        "stance": _claim("The deterministic Producer research stance is preserved without change.", "recommendation", "recommendation_label", identity),
        "supporting_evidence": [_claim(evidence_text, "thesis_context", evidence_field, identity)],
        "uncertainties": [_claim("Producer readiness and warnings remain the uncertainty boundary.", "recommendation", "recommendation_reason_codes", identity)],
        "confirmation": [_claim("Market confirmation remains only the Producer-provided boundary.", "market_confirmation", "status", identity)],
        "invalidation": [
            _claim("Technical invalidation state is preserved.", "technical_invalidation", "current_trigger_state", identity),
            _claim("Fundamental invalidation state is preserved.", "fundamental_invalidation", "current_trigger_state", identity),
        ],
        "catalyst": [_claim(f"Catalyst context status remains {_status_text(catalyst)}.", "catalyst_context", "status", identity)],
        "valuation": [_claim(f"Valuation context status remains {_status_text(valuation)}.", "valuation_context", "status", identity)],
        "risk": [_claim(f"Risk context status remains {_status_text(risk)}.", "risk_context", "status", identity)],
        "watch_items": [_claim("Monitoring requirements are preserved from the Producer packet.", "monitoring_context", "monitor_category", identity)] if monitoring else [_claim("No monitoring item is inferred when absent.", "monitoring_context", "status", identity)],
        "counter_thesis": [_claim(counter_text, "warnings" if warnings else "recommendation", counter_field, identity)],
        "authority": copy.deepcopy(narrative_input["authority_boundary"]),
        "lineage": copy.deepcopy(packet.get("input_lineage") or {}),
    }
    correlation = narrative_input.get(CORRELATION_CONCENTRATION_FIELD)
    if isinstance(correlation, Mapping):
        c2_identity = correlation["producer_artifact_identity"]
        claims = [_c2_claim(
            "C2 threshold metadata is a deterministic research heuristic and is not calibrated probability evidence.",
            "metadata", "threshold_contract", c2_identity,
        )]
        pair = next((edge for group in correlation.get("concentration_groups_for_security", [])
                     for edge in group.get("triggered_edges", []) if isinstance(edge, Mapping)), None)
        if isinstance(pair, Mapping):
            peer = pair["ticker_j"] if pair.get("ticker_i") == narrative_input["ticker"] else pair.get("ticker_i")
            claims.append(_c2_claim(
                f"C2 reports a material correlated peer {peer}: C1 Pearson correlation is {pair['correlation']} over {pair['lookback_sessions']} sessions; the Producer recommendation remains unchanged.",
                "pairwise_correlation_context", "correlation", c2_identity,
                [pair["correlation"], pair["lookback_sessions"]],
            ))
        elif correlation.get("guard_status") == "NO_MATERIAL_CORRELATION_CONCENTRATION":
            claims.append(_c2_claim(
                "No C2 material-concentration trigger was detected in the evaluated ready pairwise evidence; this does not establish diversification.",
                "guard_context", "status", c2_identity,
            ))
        elif correlation.get("guard_status") in {"PARTIAL_PAIRWISE_VIEW", "INSUFFICIENT_PAIRWISE_EVIDENCE"}:
            claims.append(_c2_claim(
                f"C2 pairwise evidence is partial: {correlation['pairwise_ready_count']} ready relationships and {correlation['pairwise_insufficient_or_unavailable_count']} insufficient or unavailable relationships are retained.",
                "validation", "pairwise_ready_count", c2_identity,
                [correlation["pairwise_ready_count"], correlation["pairwise_insufficient_or_unavailable_count"]],
            ))
        if correlation.get("joint_matrix_status") != "JOINT_MATRIX_READY" and correlation.get("pairwise_ready_count", 0):
            claims.append(_c2_claim(
                "C2 pairwise correlation context is available while the C1 joint-matrix view is unavailable under its readiness guard.",
                "guard_context", "joint_matrix_status", c2_identity,
            ))
        result[CORRELATION_CONCENTRATION_FIELD] = {"producer_context": copy.deepcopy(dict(correlation)), "narrative_claims": claims}
    return result


def _c2_claim(text: str, section: str, field: str, identity: str, numeric_facts: list[Any] | None = None) -> dict[str, Any]:
    claim = _claim(text, section, field, identity)
    claim["numeric_facts"] = [] if numeric_facts is None else [str(value) for value in numeric_facts]
    return claim


def _allowed_locator_pairs(packet: Mapping[str, Any]) -> set[tuple[str, str]]:
    pairs = {("recommendation", "recommendation_label"), ("recommendation", "recommendation_reason_codes")}
    for section, fields in {
        "thesis_context": ("thesis_evidence", "research_case_eligibility", "material_warnings"),
        "market_confirmation": ("status",),
        "technical_invalidation": ("current_trigger_state", "status"),
        "fundamental_invalidation": ("current_trigger_state", "status"),
        "catalyst_context": ("status", "qualified_catalysts", "retained_event_context"),
        "valuation_context": ("status", "availability", "price_session"),
        "risk_context": ("status", "security_volatility_context"),
        "monitoring_context": ("monitor_category", "boundary_status", "cadence_class", "status"),
        "warnings": ("warnings",),
    }.items():
        if section in packet:
            pairs.update((section, field) for field in fields)
    return pairs


def _allowed_c2_locator_pairs() -> set[tuple[str, str]]:
    return {("metadata", "threshold_contract"), ("guard_context", "status"),
            ("guard_context", "joint_matrix_status"), ("pairwise_correlation_context", "correlation"),
            ("validation", "pairwise_ready_count")}


def _numeric_strings(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, Mapping):
        for child in value.values(): found.update(_numeric_strings(child))
    elif isinstance(value, list):
        for child in value: found.update(_numeric_strings(child))
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        found.add(str(value))
    return found


def _contains_prohibited_narrative_text(text: str) -> bool:
    """Allow the sole negative C2 calibration disclaimer, never a probability claim."""
    return bool(_PROHIBITED_TEXT.search(text.replace("not calibrated probability evidence", "")))


def validate_narrative_response(response: Mapping[str, Any] | str, narrative_input: Mapping[str, Any]) -> dict[str, Any]:
    """Fail closed on response shape, overrides, authority expansion, or ungrounded facts."""
    try:
        candidate = json.loads(response) if isinstance(response, str) else response
    except (TypeError, ValueError):
        return _result("NARRATIVE_REJECTED_SCHEMA", reasons=["response_not_valid_json"])
    if not isinstance(candidate, Mapping) or not isinstance(narrative_input, Mapping):
        return _result("NARRATIVE_REJECTED_SCHEMA", reasons=["response_or_input_not_mapping"])
    if any(key in candidate for key in _PROHIBITED_KEYS):
        return _result("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", reasons=["prohibited_authority_field"])
    immutable = ("ticker", "as_of_session", "producer_artifact_identity", "recommendation_label", "recommendation_readiness")
    if any(candidate.get(field) != narrative_input.get(field) for field in immutable):
        return _result("NARRATIVE_REJECTED_RECOMMENDATION_OVERRIDE", reasons=["AI_NARRATIVE_CANNOT_OVERRIDE_PRODUCER_RECOMMENDATION"])
    if set(candidate) != set(response_fields(narrative_input)):
        return _result("NARRATIVE_REJECTED_SCHEMA", reasons=["response_fields_invalid"])
    if candidate["recommendation_label"] not in LABELS or candidate["recommendation_readiness"] not in READINESS:
        return _result("NARRATIVE_REJECTED_RECOMMENDATION_OVERRIDE", reasons=["producer_vocabulary_not_preserved"])
    packet = narrative_input.get("recommendation_packet")
    if not isinstance(packet, Mapping):
        return _result("NARRATIVE_REJECTED_SCHEMA", reasons=["narrative_input_packet_invalid"])
    if candidate.get("authority") != narrative_input.get("authority_boundary"):
        return _result("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", reasons=["authority_boundary_changed"])
    if candidate.get("lineage") != packet.get("input_lineage", {}):
        return _result("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", reasons=["lineage_changed"])
    allowed = _allowed_locator_pairs(packet)
    supported_numbers = _numeric_strings(packet)
    for field in ("stance", "supporting_evidence", "uncertainties", "confirmation", "invalidation", "catalyst", "valuation", "risk", "watch_items", "counter_thesis"):
        claims = candidate.get(field)
        claims = [claims] if field == "stance" else claims
        if not isinstance(claims, list) or not claims:
            return _result("NARRATIVE_REJECTED_SCHEMA", reasons=[f"{field}_invalid"])
        for claim in claims:
            if not isinstance(claim, Mapping) or not isinstance(claim.get("text"), str) or not isinstance(claim.get("source_locator"), Mapping):
                return _result("NARRATIVE_REJECTED_SCHEMA", reasons=[f"{field}_claim_invalid"])
            locator = claim["source_locator"]
            if locator.get("input_identity") != narrative_input.get("producer_artifact_identity") or (locator.get("source_section"), locator.get("source_field")) not in allowed:
                return _result("NARRATIVE_REJECTED_UNSUPPORTED_FACT", reasons=["claim_source_locator_not_supplied"])
            if _contains_prohibited_narrative_text(claim["text"]):
                return _result("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", reasons=["prohibited_action_or_authority_text"])
            numeric_facts = claim.get("numeric_facts", [])
            if not isinstance(numeric_facts, list) or any(str(number) not in supported_numbers for number in numeric_facts):
                return _result("NARRATIVE_REJECTED_UNSUPPORTED_FACT", reasons=["unsupported_numerical_fact"])
            # Structured claims must declare numeric facts; un-declared numeric prose is rejected.
            if _NUMBER.search(claim["text"]) and not numeric_facts:
                return _result("NARRATIVE_REJECTED_UNSUPPORTED_FACT", reasons=["unstructured_numerical_claim"])
    correlation = narrative_input.get(CORRELATION_CONCENTRATION_FIELD)
    if isinstance(correlation, Mapping):
        section = candidate.get(CORRELATION_CONCENTRATION_FIELD)
        if not isinstance(section, Mapping) or set(section) != {"producer_context", "narrative_claims"} or section.get("producer_context") != correlation:
            return _result("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", reasons=["correlation_concentration_context_changed"])
        claims = section.get("narrative_claims")
        if not isinstance(claims, list) or not claims:
            return _result("NARRATIVE_REJECTED_SCHEMA", reasons=["correlation_concentration_claims_invalid"])
        c2_numbers = _numeric_strings(correlation)
        for claim in claims:
            locator = claim.get("source_locator") if isinstance(claim, Mapping) else None
            numeric_facts = claim.get("numeric_facts", []) if isinstance(claim, Mapping) else []
            if not isinstance(claim, Mapping) or not isinstance(claim.get("text"), str) or not isinstance(locator, Mapping) or locator.get("input_identity") != correlation.get("producer_artifact_identity") or (locator.get("source_section"), locator.get("source_field")) not in _allowed_c2_locator_pairs():
                return _result("NARRATIVE_REJECTED_UNSUPPORTED_FACT", reasons=["correlation_concentration_locator_not_supplied"])
            if _contains_prohibited_narrative_text(claim["text"]):
                return _result("NARRATIVE_REJECTED_AUTHORITY_VIOLATION", reasons=["prohibited_action_or_authority_text"])
            if not isinstance(numeric_facts, list) or any(str(number) not in c2_numbers for number in numeric_facts) or (_NUMBER.search(claim["text"]) and not numeric_facts):
                return _result("NARRATIVE_REJECTED_UNSUPPORTED_FACT", reasons=["correlation_concentration_numerical_fact_invalid"])
    return _result("NARRATIVE_VALID", accepted_output=copy.deepcopy(dict(candidate)))


def validate_full_producer_artifact(producer_artifact: Mapping[str, Any], *, producer_head: str, consumer_start_head: str) -> dict[str, Any]:
    """Offline 523-record replay over retained JSON, not a Producer runtime import."""
    if producer_artifact.get("contract_version") != PRODUCER_CONTRACT_VERSION or not isinstance(producer_artifact.get("records"), Mapping):
        raise ValueError("UNSUPPORTED_SHADOW_RECOMMENDATION_CONTRACT")
    results, labels, readiness, representatives = [], Counter(), Counter(), {}
    for ticker, packet in sorted(producer_artifact["records"].items()):
        entry = {ATTACHMENT_KEY: {"ticker": ticker, "source_artifact_identity": producer_artifact.get("artifact_identity"), "recommendation_packet": copy.deepcopy(packet), "authority_boundary": copy.deepcopy(producer_artifact.get("authority_boundaries")), "shadow_mode": "SHADOW_OPT_IN", "is_actionable": False}}
        parsed = parse_shadow_recommendation_attachment(entry, expected_ticker=ticker)
        if parsed["status"] != "SHADOW_RECOMMENDATION_READY":
            raise ValueError(parsed["status"])
        item = parsed["narrative_input"]
        fallback = render_fallback_narrative(item)
        verdict = validate_narrative_response(fallback, item)
        if verdict["status"] != "NARRATIVE_VALID":
            raise ValueError(verdict["status"])
        labels[item["recommendation_label"]] += 1
        readiness[item["recommendation_readiness"]] += 1
        key = (item["recommendation_readiness"], item["recommendation_label"])
        representatives.setdefault(key, {"ticker": ticker, "label": item["recommendation_label"], "readiness": item["recommendation_readiness"], "fallback_stance": fallback["stance"]["text"], "evidence_locator": fallback["supporting_evidence"][0]["source_locator"], "counter_thesis_locator": fallback["counter_thesis"][0]["source_locator"], "authority": fallback["authority"]})
        results.append(item)
    source_counts = producer_artifact.get("validation", {}).get("recommendation_counts", {})
    source_readiness = producer_artifact.get("validation", {}).get("readiness_counts", {})
    if dict(sorted(labels.items())) != dict(sorted(source_counts.items())) or dict(sorted(readiness.items())) != dict(sorted(source_readiness.items())):
        raise ValueError("CONSUMER_PRODUCER_RECOMMENDATION_COUNT_MISMATCH")
    artifact: dict[str, Any] = {
        "contract_version": CONSUMER_CONTRACT_VERSION, "milestone": "SHADOW_RECOMMENDATION_CONSUMER_NARRATIVE_V1",
        "producer_contract_version": PRODUCER_CONTRACT_VERSION, "producer_source_head": producer_head,
        "consumer_start_head": consumer_start_head, "producer_artifact_identity": producer_artifact.get("artifact_identity"),
        "denominator": len(results), "residual": 0, "label_preservation_counts": dict(sorted(labels.items())),
        "readiness_preservation_counts": dict(sorted(readiness.items())), "label_drift_count": 0, "readiness_drift_count": 0,
        "fallback_render_coverage": len(results), "grounding_coverage": len(results),
        "validator_rejection_audit": {"recommendation_override": "NARRATIVE_REJECTED_RECOMMENDATION_OVERRIDE", "malformed": "NARRATIVE_REJECTED_SCHEMA", "unsupported_fact": "NARRATIVE_REJECTED_UNSUPPORTED_FACT", "authority": "NARRATIVE_REJECTED_AUTHORITY_VIOLATION"},
        "forbidden_authority_output_counts": {"BUY": 0, "SELL": 0, "HOLD": 0, "target_price": 0, "probability": 0, "position_size": 0, "portfolio_weight": 0, "risk_budget": 0},
        "representatives": {f"{ready}:{label}": value for (ready, label), value in sorted(representatives.items())},
        "authority_boundary": {"shadow_research_only": True, "same_close_execution_eligibility": "NOT_ESTABLISHED", "network_or_model_call_required": False},
    }
    return {**artifact, **content_identity(artifact)}
