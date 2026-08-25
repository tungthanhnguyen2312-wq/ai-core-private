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


def test_research_usable_ready_blocked_and_not_applicable_stay_per_method():
    raw = _raw()
    raw["entity_class"] = "bank"
    raw["price_input"]["session"] = "2026-08-21"
    raw["share_basis_input"]["authority"] = "provider_reported_lagged"
    raw["metrics"] = {
        "P/E": {
            "status": "RESEARCH_USABLE", "value": 7.0, "is_actionable": False,
            "allowed_uses": ["CURRENT_RESEARCH_ONLY"],
            "forbidden_uses": ["VALUE_STRATEGY_ELIGIBILITY", "TARGET_PRICE"],
            "applicability": "APPLICABLE", "financial_period": "2026-Q2", "price_session": "2026-08-21",
        },
        "P/B": {"status": "READY", "value": 1.2, "applicability": "APPLICABLE", "price_session": "2026-08-21"},
        "EV/EBITDA": {"status": "BLOCKED", "value": None, "applicability": "APPLICABLE", "price_session": "2026-08-21"},
        "EV/Sales": {"status": "NOT_APPLICABLE", "value": None, "applicability": "NOT_APPLICABLE", "price_session": "2026-08-21"},
    }
    result = market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")
    assert result["metrics"]["P/E"]["status"] == "RESEARCH_USABLE"
    assert result["metrics"]["P/B"]["status"] == "READY"
    assert result["metrics"]["EV/Sales"]["status"] == "NOT_APPLICABLE"
    assert result["share_basis_input"]["authority"] == "provider_reported_lagged"


def test_wrong_metric_session_and_invented_authority_fields_fail_closed():
    raw = _raw()
    raw["price_input"]["session"] = "2026-08-21"
    raw["metrics"]["P/E"]["price_session"] = "2026-08-24"
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"

    raw = _raw()
    raw["target_price"] = 100.0
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"
