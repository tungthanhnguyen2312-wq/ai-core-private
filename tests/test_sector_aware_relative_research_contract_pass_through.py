import copy
import json
from pathlib import Path

from builders.build_ticker_context import (
    apply_bundle_sector_aware_relative_research_contract,
    sector_aware_relative_research_contract,
)


ARTIFACT = (Path(__file__).resolve().parents[2] / "stock-core-private" / "operations-review"
            / "sector-aware-relative-research-v1-20260824" / "sector_aware_relative_research_artifact.json")


def _raw():
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    raw = copy.deepcopy(artifact["records"]["AAA"])
    raw.update({"source_artifact_identity": artifact["artifact_identity"], "source_session": artifact["session"], "coverage": artifact["coverage"], "authority_boundary": artifact["authority_boundary"], "is_actionable": False})
    return raw


def test_sector_aware_contract_passes_retained_fields_without_reclassification():
    raw = _raw()
    bundle = {"tickers": {"AAA": {"sector_aware_relative_research": raw}}}
    assert sector_aware_relative_research_contract(bundle, "AAA") == raw
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_sector_aware_relative_research_contract(context, bundle)
    assert context["sector_aware_relative_research"]["peer_membership"] == raw["peer_membership"]
    assert context["sector_aware_relative_research"]["valuation_peer_context"]["status"] == "VALUATION_PEER_CONTEXT_UNAVAILABLE"


def test_malformed_peer_group_or_expectations_fails_closed():
    raw = _raw(); raw["peer_membership"]["peer_group_level"] = "INFERRED"
    result = sector_aware_relative_research_contract({"tickers": {"AAA": {"sector_aware_relative_research": raw}}}, "AAA")
    assert result["status"] == "malformed"
    raw = _raw(); raw["expectations_context"]["state"] = "BUY"
    result = sector_aware_relative_research_contract({"tickers": {"AAA": {"sector_aware_relative_research": raw}}}, "AAA")
    assert result["status"] == "malformed"
