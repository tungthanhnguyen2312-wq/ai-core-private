from __future__ import annotations

import copy

from builders.build_ticker_context import apply_bundle_qualified_research_snapshot_v2_contract


def snapshot(schema_version: str = "2.1.0") -> dict:
    return {
        "schema_version": schema_version,
        "snapshot_id": "qrs2-source-identity",
        "identity": {"schema_version": schema_version, "production_universe": ["HPG", "VNM"]},
        "tickers": [
            {
                "ticker": "HPG",
                "research_status": "qualified",
                "reason_codes": ["historical_evidence_qualified"],
                "analysis_states": {
                    "historical_research": {"status": "qualified", "reason_codes": []},
                    "raw_as_traded_price": {"status": "blocked", "reason_codes": ["raw_price_unqualified"]},
                    "current_valuation": {"status": "unknown", "reason_codes": ["inputs_unqualified"]},
                    "generic_liquidity": {"status": "blocked", "reason_codes": ["volume_unqualified"]},
                    "foreign_flow_value": {"status": "unqualified", "reason_codes": ["foreign_flow_missing"]},
                },
            },
            {
                "ticker": "VNM",
                "research_status": "unknown",
                "reason_codes": ["research_not_attached"],
                "analysis_states": {"historical_research": {"status": "unknown", "reason_codes": ["research_not_attached"]}},
            },
        ],
        "historical_only": True,
        "is_actionable": False,
    }


def test_passes_snapshot_verbatim_with_identity_order_and_states() -> None:
    source = snapshot()
    expected = copy.deepcopy(source)
    context = {"ticker": "HPG", "provenance": []}

    apply_bundle_qualified_research_snapshot_v2_contract(context, {"qualified_research_snapshot_v2": source})

    assert context["qualified_research_snapshot_v2"] == expected
    assert [row["ticker"] for row in context["qualified_research_snapshot_v2"]["tickers"]] == ["HPG", "VNM"]
    assert context["qualified_research_snapshot_v2"]["snapshot_id"] == "qrs2-source-identity"
    source["tickers"][0]["research_status"] = "mutated"
    assert context["qualified_research_snapshot_v2"]["tickers"][0]["research_status"] == "qualified"


def test_accepts_compatible_v2_0_snapshot_without_rewriting_it() -> None:
    source = snapshot("2.0.0")
    context = {"ticker": "HPG"}

    apply_bundle_qualified_research_snapshot_v2_contract(context, {"qualified_research_snapshot_v2": source})

    assert context["qualified_research_snapshot_v2"] == source
    assert context["qualified_research_snapshot_v2"]["schema_version"] == "2.0.0"


def test_legacy_bundle_omits_snapshot_without_a_synthetic_fallback() -> None:
    context = {"ticker": "HPG"}

    apply_bundle_qualified_research_snapshot_v2_contract(context, {})

    assert "qualified_research_snapshot_v2" not in context


def test_malformed_snapshot_fails_closed_without_numeric_or_actionable_fallback() -> None:
    context = {"ticker": "HPG"}
    malformed = {"qualified_research_snapshot_v2": {"snapshot_id": "not-a-contract", "target_price": 100, "probability": 0.9}}

    apply_bundle_qualified_research_snapshot_v2_contract(context, malformed)

    value = context["qualified_research_snapshot_v2"]
    assert value == {
        "status": "malformed",
        "historical_only": True,
        "is_actionable": False,
        "reason_codes": ["qualified_research_snapshot_v2_malformed"],
    }
    assert "target_price" not in value
    assert "probability" not in value
