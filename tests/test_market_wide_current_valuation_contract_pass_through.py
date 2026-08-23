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
