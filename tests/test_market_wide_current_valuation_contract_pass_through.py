from builders.build_ticker_context import (
    apply_bundle_market_wide_current_valuation_contract,
    market_wide_current_valuation_contract,
)


def _raw():
    return {"ticker": "AAA", "status": "current_valuation_snapshot", "is_actionable": False,
            "entity_class": "corporate", "price_input": {"status": "PRICE_READY"},
            "share_basis_input": {"status": "PROVIDER_REPORTED_STALE"},
            "financial_input": {"authority": "OFFICIAL_QUALIFIED"},
            "metrics": {"market_cap": {"status": "BLOCKED", "value": None}, "P/E": {"status": "BLOCKED", "value": None}}}


def test_current_valuation_snapshot_passes_through_without_authority_upgrade():
    bundle = {"tickers": {"AAA": {"market_wide_current_valuation": _raw()}}}
    result = market_wide_current_valuation_contract(bundle, "AAA")
    assert result == _raw()
    context = {"ticker": "AAA", "provenance": []}
    apply_bundle_market_wide_current_valuation_contract(context, bundle)
    assert context["market_wide_current_valuation"]["share_basis_input"]["status"] == "PROVIDER_REPORTED_STALE"
    assert context["market_wide_current_valuation"]["metrics"]["P/E"]["value"] is None


def test_value_or_actionable_mutation_fails_closed():
    raw = _raw()
    raw["metrics"]["P/E"]["value"] = 7.0
    result = market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")
    assert result["status"] == "malformed"


def test_shadow_proxy_requires_lower_authority_labels_and_preserves_stale_share_semantics():
    raw = _raw()
    raw["shadow_proxy_valuation"] = {
        "share_basis_type": "PROVIDER_ISSUED_SHARE_PROXY", "authority_tier": "SHADOW_RESEARCH_ONLY", "is_actionable": False,
        "source_observation": {"status": "PROXY_STALE", "semantic_identity": "ISSUED_SHARES"},
        "forbidden_uses": ["COMMON_SHARES_OUTSTANDING", "AUTHORITATIVE_VALUATION"],
        "metrics": {"proxy_P/E": {"status": "SHADOW_PROXY_READY", "value": 7.0, "labels": ["SHADOW", "NON_AUTHORITATIVE"]}},
    }
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["shadow_proxy_valuation"] == raw["shadow_proxy_valuation"]
    raw["shadow_proxy_valuation"]["share_basis_type"] = "COMMON_SHARES_OUTSTANDING"
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"
