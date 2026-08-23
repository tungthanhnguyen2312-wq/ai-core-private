import copy
import json
from pathlib import Path

from builders.build_ticker_context import (
    apply_bundle_current_evidence_bound_scenario_contract,
    current_evidence_bound_scenario_contract,
)


ARTIFACT = (Path(__file__).resolve().parents[2] / "stock-core-private" / "operations-review"
            / "current-evidence-bound-scenario-v1-20260824" / "current_evidence_bound_scenario_artifact.json")


def _raw():
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    raw = copy.deepcopy(artifact["records"]["HPG"])
    raw.update({"source_artifact_identity": artifact["artifact_identity"], "source_session": artifact["session"], "coverage": artifact["coverage"], "authority_boundary": artifact["authority_boundary"], "is_actionable": False})
    return raw


def test_current_scenario_passes_through_and_keeps_probability_unknown():
    raw = _raw(); bundle = {"tickers": {"HPG": {"current_evidence_bound_scenario": raw}}}
    assert current_evidence_bound_scenario_contract(bundle, "HPG") == raw
    context = {"ticker": "HPG", "provenance": []}
    apply_bundle_current_evidence_bound_scenario_contract(context, bundle)
    assert context["current_evidence_bound_scenario"]["base_case"] == raw["base_case"]
    assert context["current_evidence_bound_scenario"]["probability_status"] == "UNKNOWN_UNCALIBRATED"


def test_malformed_case_or_probability_fails_closed_for_ai_guardrail():
    raw = _raw(); raw["bull_case"]["probability_status"] = "60_PERCENT"
    assert current_evidence_bound_scenario_contract({"tickers": {"HPG": {"current_evidence_bound_scenario": raw}}}, "HPG")["status"] == "malformed"
    raw = _raw(); raw["base_case"].pop("continuation_conditions")
    assert current_evidence_bound_scenario_contract({"tickers": {"HPG": {"current_evidence_bound_scenario": raw}}}, "HPG")["status"] == "malformed"
