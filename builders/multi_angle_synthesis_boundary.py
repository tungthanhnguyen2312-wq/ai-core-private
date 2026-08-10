"""Consumer acceptance and orchestration boundary for multi-angle AI synthesis.

This module provides the deterministic bridge between canonical ticker context,
derived validator metadata, and AI-produced multi-angle synthesis outputs.

It enforces strict context shape validation, derives contract metadata deterministically
from context state (e.g., unavailable indicators), delegates to the fail-closed
response validator, and returns structured accepted/rejected results.
"""

from __future__ import annotations

import copy
from typing import Any, Mapping

from builders.multi_angle_synthesis_response import validate_multi_angle_synthesis_output


def _reject_boundary(*reasons: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "status": "rejected",
        "accepted_output": None,
        "reasons": sorted(set(reasons)),
        "derived_contract_metadata": copy.deepcopy(metadata or {}),
        "multi_angle_boundary": True,
    }


def accept_multi_angle_synthesis(
    ticker_context: Mapping[str, Any],
    ai_response: str | Mapping[str, Any],
    *,
    requires_conflicting_evidence: bool | None = None,
) -> dict[str, Any]:
    """Accept and validate a multi-angle AI synthesis output using canonical ticker context."""
    if not isinstance(ticker_context, Mapping):
        return _reject_boundary("ticker_context_invalid_type")

    derived_meta: dict[str, Any] = {}
    unavailable_indicators: list[str] = []

    # 1. Derive unavailable indicators from canonical context
    #
    # Canonical shape (stock-core-private/dnse_current_state_price_analytics.py, passed
    # through byte-identically by build_ticker_context.py's
    # current_state_price_analytics_contract()): SMA20 lives at
    # current_state_price_analytics.technical_indicators.sma_20.status. There is no
    # evidence any committed Producer or Consumer contract ever emits a top-level
    # current_state_price_analytics.sma_20 -- a real fresh HPG context and the Producer
    # module's own source both confirm the nested path; only a pre-existing, never
    # cross-checked test fixture used the flat shape.
    if "current_state_price_analytics" in ticker_context and ticker_context["current_state_price_analytics"] is not None:
        cspa = ticker_context["current_state_price_analytics"]
        if not isinstance(cspa, Mapping):
            return _reject_boundary("ticker_context_malformed:current_state_price_analytics")

        if "technical_indicators" in cspa and cspa["technical_indicators"] is not None:
            technical_indicators = cspa["technical_indicators"]
            if not isinstance(technical_indicators, Mapping):
                return _reject_boundary("ticker_context_malformed:technical_indicators")

            if "sma_20" in technical_indicators and technical_indicators["sma_20"] is not None:
                sma20 = technical_indicators["sma_20"]
                if not isinstance(sma20, Mapping):
                    return _reject_boundary("ticker_context_malformed:sma_20")

                status = sma20.get("status")
                if not isinstance(status, str):
                    return _reject_boundary("ticker_context_malformed:sma_20_status")

                if status == "unavailable":
                    unavailable_indicators.append("sma_20")

    if unavailable_indicators:
        derived_meta["unavailable_indicators"] = sorted(set(unavailable_indicators))

    # 2. Derive conflicting evidence requirement (Monotonic Precedence & Strict Type Safety)
    caller_conflict: bool | None = None
    if requires_conflicting_evidence is not None:
        if type(requires_conflicting_evidence) is not bool:
            return _reject_boundary("trusted_caller_input_invalid:requires_conflicting_evidence")
        caller_conflict = requires_conflicting_evidence

    context_conflict: bool | None = None
    if "requires_conflicting_evidence" in ticker_context and ticker_context["requires_conflicting_evidence"] is not None:
        ctx_req = ticker_context["requires_conflicting_evidence"]
        if type(ctx_req) is not bool:
            return _reject_boundary("ticker_context_malformed:requires_conflicting_evidence")
        context_conflict = ctx_req

    effective_conflict = bool(context_conflict) or bool(caller_conflict)
    if effective_conflict:
        derived_meta["requires_conflicting_evidence"] = True
    elif context_conflict is False or caller_conflict is False:
        derived_meta["requires_conflicting_evidence"] = False


    # 3. Delegate to multi-angle synthesis response validator
    validator_result = validate_multi_angle_synthesis_output(
        ai_response,
        contract_metadata=derived_meta,
    )

    if validator_result["status"] == "rejected":
        return _reject_boundary(*validator_result["reasons"], metadata=derived_meta)

    return {
        "status": "accepted",
        "accepted_output": copy.deepcopy(validator_result["accepted_output"]),
        "reasons": [],
        "derived_contract_metadata": copy.deepcopy(derived_meta),
        "multi_angle_boundary": True,
    }
