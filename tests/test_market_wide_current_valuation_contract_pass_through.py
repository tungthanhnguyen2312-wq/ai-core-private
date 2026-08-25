import copy
import json
from pathlib import Path

from builders.build_ticker_context import (
    apply_bundle_market_wide_current_valuation_contract,
    market_wide_current_valuation_contract,
)


ARTIFACT = (Path(__file__).resolve().parents[2] / "stock-core-private" / "operations-review"
            / "market-wide-current-valuation-research-scaleout-v1" / "market_wide_current_valuation_artifact.json")


def _raw():
    return {"ticker": "AAA", "status": "current_valuation_snapshot", "is_actionable": False,
            "entity_class": "corporate", "price_input": {"status": "PRICE_READY"},
            "share_basis_input": {"status": "PROVIDER_REPORTED_STALE"},
            "financial_input": {"authority": "OFFICIAL_QUALIFIED"},
            "metrics": {"market_cap": {"status": "BLOCKED", "value": None}, "P/E": {"status": "BLOCKED", "value": None}}}


def _research_usable_metric(price_session="2026-08-21"):
    return {
        "metric_id": "P/E", "status": "RESEARCH_USABLE", "value": 7.0,
        "applicability": "APPLICABLE", "formula_version": "market_wide_current_valuation/v1+p3f_current_market_valuation/v1",
        "blocked_reasons": [], "price_session": price_session, "is_actionable": False,
        "historical_pit_eligible": False,
        "labels": [
            "CURRENT_RESEARCH_ONLY", "NOT_AUTHORITATIVE", "NOT_PIT", "NOT_FOR_TARGET_PRICE",
            "NOT_FOR_SIZING", "NOT_FOR_EXECUTION", "NOT_FOR_VALUE_STRATEGY",
        ],
        "allowed_uses": ["CURRENT_RESEARCH_ONLY"],
        "forbidden_uses": [
            "AUTHORITATIVE_VALUATION", "VALUE_STRATEGY_ELIGIBILITY", "TARGET_PRICE", "INTRINSIC_VALUE",
            "DCF", "SIZING", "EXECUTION", "RANKING", "RECOMMENDATION", "PIT",
        ],
    }


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
        "P/E": {**_research_usable_metric(), "financial_period": "2026-Q2"},
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
    raw["metrics"]["P/E"] = _research_usable_metric("2026-08-24")
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"

    raw = _raw()
    raw["target_price"] = 100.0
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"


def test_numeric_metric_missing_session_and_thin_research_authority_envelope_fail_closed():
    raw = _raw()
    raw["price_input"]["session"] = "2026-08-21"
    metric = _research_usable_metric()
    metric.pop("price_session")
    raw["metrics"]["P/E"] = metric
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"

    raw = _raw()
    raw["price_input"]["session"] = "2026-08-21"
    raw["metrics"]["P/B"] = {"status": "READY", "value": 1.2, "applicability": "APPLICABLE"}
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"

    raw = _raw()
    raw["price_input"]["session"] = "2026-08-21"
    metric = _research_usable_metric()
    metric["labels"].remove("NOT_FOR_VALUE_STRATEGY")
    raw["metrics"]["P/E"] = metric
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"

    raw = _raw()
    raw["price_input"]["session"] = "2026-08-21"
    metric = _research_usable_metric()
    metric["forbidden_uses"].remove("AUTHORITATIVE_VALUATION")
    raw["metrics"]["P/E"] = metric
    assert market_wide_current_valuation_contract({"tickers": {"AAA": {"market_wide_current_valuation": raw}}}, "AAA")["status"] == "malformed"


def test_actual_producer_research_usable_metric_passes_unchanged():
    artifact = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    raw = copy.deepcopy(artifact["records"]["HPG"])
    raw.update({
        "source_artifact_identity": artifact["artifact_identity"],
        "coverage": artifact["coverage"], "status": "current_valuation_snapshot", "is_actionable": False,
    })
    assert market_wide_current_valuation_contract(
        {"tickers": {"HPG": {"market_wide_current_valuation": raw}}}, "HPG"
    ) == raw
