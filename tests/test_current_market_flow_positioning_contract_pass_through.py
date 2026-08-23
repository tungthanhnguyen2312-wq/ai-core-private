from builders.build_ticker_context import current_market_flow_positioning_contract, apply_bundle_current_market_flow_positioning_contract


def raw():
    section = {"status": "AVAILABLE"}
    return {"ticker": "HPG", "source_artifact_identity": "current_market_flow_positioning:test", "source_session": "2026-08-21", "is_actionable": False, "traded_value": section, "foreign_flow": section, "foreign_room": section, "proprietary_flow": section, "active_order_context": section, "price_flow_relationships": ["BREAKOUT_WITH_FLOW_CONFIRMATION"], "authority_boundary": {"liquidity_sizing_execution": "BLOCKED"}}


def test_current_flow_is_verbatim_and_non_actionable():
    value = raw(); bundle = {"tickers": {"HPG": {"current_market_flow_positioning": value}}}
    assert current_market_flow_positioning_contract(bundle, "HPG") == value
    context = {"ticker": "HPG", "provenance": []}
    apply_bundle_current_market_flow_positioning_contract(context, bundle)
    assert context["current_market_flow_positioning"]["price_flow_relationships"] == ["BREAKOUT_WITH_FLOW_CONFIRMATION"]


def test_current_flow_fails_closed_on_sizing_authority():
    value = raw(); value["authority_boundary"]["liquidity_sizing_execution"] = "READY"
    assert current_market_flow_positioning_contract({"tickers": {"HPG": {"current_market_flow_positioning": value}}}, "HPG")["status"] == "malformed"
