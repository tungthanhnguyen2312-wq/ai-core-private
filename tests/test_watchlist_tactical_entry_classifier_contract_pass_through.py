"""Consumer pass-through tests for the watchlist_tactical_entry_classifier contract.

Mirrors tests/test_market_wide_current_fundamental_research_contract_pass_through.py's hermetic
convention: synthetic-but-schema-faithful fixtures shaped exactly like
export_ai_bundle.build_watchlist_tactical_entry_classifier_for_ticker_safe()'s real output (verified
separately, with real retained data, by
test_watchlist_tactical_entry_classifier_frozen_time_e2e.py).

tickers[ticker].watchlist_tactical_entry_classifier is a byte-identical pass-through of one record
from stock-core-private's retained watchlist_tactical_entry_classifier artifact
(tools/run_watchlist_tactical_entry_classifier.py), plus the "status"/"is_actionable"/
"source_artifact_identity"/"state_taxonomy"/"action_taxonomy"/"action_by_entry_state"/
"blocked_outputs" fields export_ai_bundle.py's attach layer adds. Consumer never recomputes a
technical feature, screening flag, fundamental tier, market_state, entry_state, action, evidence,
confirmation_trigger, invalidation, horizon, or is_full_position_ready.
"""
from __future__ import annotations

import copy
import unittest

from builders import build_ticker_context as b

_TAXONOMY_STATE_TAXONOMY = [
    "DOWNTREND", "SELLING_PRESSURE_EASING", "EARLY_REVERSAL_CANDIDATE", "BASE_BUILDING",
    "SIDEWAYS_NEUTRAL", "BREAKOUT_READY", "UPTREND_CONFIRMED", "DISTRIBUTION_RISK", "BREAKDOWN_RISK",
]
_ACTION_TAXONOMY = [
    "EARLY_ENTRY", "BUY_ON_CONFIRMATION", "ACCUMULATE_IN_BASE", "HOLD_DO_NOT_ADD", "WAIT", "AVOID", "REDUCE_EXIT",
]
_ACTION_BY_ENTRY_STATE = {
    "BREAKOUT_READY": "BUY_ON_CONFIRMATION", "UPTREND_CONFIRMED": "HOLD_DO_NOT_ADD",
    "EARLY_REVERSAL_CANDIDATE": "EARLY_ENTRY", "BASE_BUILDING": "ACCUMULATE_IN_BASE",
    "SELLING_PRESSURE_EASING": "WAIT", "SIDEWAYS_NEUTRAL": "WAIT", "DISTRIBUTION_RISK": "HOLD_DO_NOT_ADD",
    "BREAKDOWN_RISK": "REDUCE_EXIT", "DOWNTREND": "AVOID",
}
_ENTRY_ACTION_TAXONOMY = ["EARLY_ENTRY", "BUY_ON_CONFIRMATION", "ACCUMULATE_IN_BASE", "WAIT", "AVOID"]
_ENTRY_ACTION_BY_ENTRY_STATE = {
    "BREAKOUT_READY": "BUY_ON_CONFIRMATION", "UPTREND_CONFIRMED": "WAIT",
    "EARLY_REVERSAL_CANDIDATE": "EARLY_ENTRY", "BASE_BUILDING": "ACCUMULATE_IN_BASE",
    "SELLING_PRESSURE_EASING": "WAIT", "SIDEWAYS_NEUTRAL": "WAIT", "DISTRIBUTION_RISK": "WAIT",
    "BREAKDOWN_RISK": "AVOID", "DOWNTREND": "AVOID",
}
# `action` (secondary, 7-value) unambiguously determines `entry_action` (primary, 5-value) --
# every entry_state sharing one `action` value also shares the same `entry_action` value, so this
# test helper can auto-derive a schema-faithful entry_action from whichever `action` a call site
# passes, without needing every call site to specify both.
_ENTRY_ACTION_BY_ACTION = {
    "BUY_ON_CONFIRMATION": "BUY_ON_CONFIRMATION", "HOLD_DO_NOT_ADD": "WAIT", "EARLY_ENTRY": "EARLY_ENTRY",
    "ACCUMULATE_IN_BASE": "ACCUMULATE_IN_BASE", "WAIT": "WAIT", "AVOID": "AVOID", "REDUCE_EXIT": "AVOID",
}
_BLOCKED_OUTPUTS = {
    "ordinal_market_ranking": "RANKING_PROHIBITED", "opportunity_score": "SCORING_PROHIBITED",
    "probabilities_or_target_prices": "FORECAST_PROHIBITED",
    "portfolio_weights_or_position_sizes": "SIZING_FORMULA_NOT_YET_IMPLEMENTED",
    "historical_raw_as_traded_or_pit": "RAW_AS_TRADED_NOT_PROMOTED", "backtesting": "OUT_OF_SCOPE_THIS_MILESTONE",
    "confirmed_bottom_or_top_claims": "EARLY_REVERSAL_OR_BASE_LANGUAGE_ONLY_NEVER_A_CONFIRMED_INFLECTION_CLAIM",
    "traded_value_turnover_adv_adtv": "GROSS_TRADE_AMOUNT_NON_AUTHORITATIVE_SCALE_UNRESOLVED",
}


def _classified_record(ticker: str, *, entry_state: str, action: str, is_full_position_ready: bool = False,
                       entry_action: str | None = None, position_sizing_status: str = "NOT_EVALUATED",
                       fundamental_status: str = "AVAILABLE", fundamental_tier: str | None = "OFFICIAL_QUALIFIED") -> dict:
    return {
        "ticker": ticker, "market_state": "MIXED_NO_CLEAR_MARKET_REGIME", "ticker_structure_state": "ABOVE_MA20_MOMENTUM_POSITIVE",
        "entry_state": entry_state, "action": action,
        "entry_action": entry_action if entry_action is not None else _ENTRY_ACTION_BY_ACTION[action],
        "evidence_for": ["Price is above its 20-day moving average.", "20-day momentum is positive (0.1500)."],
        "evidence_against": ["Provider-relative volume is at or below the same-session cohort median today."],
        "confirmation_trigger": "Already showing today's price, momentum, and volume confirmation.",
        "invalidation": "A session close back below the 20-day moving average invalidates this classification.",
        "data_quality": {"confidence": "HIGH", "technical_eligible": True, "warnings": []},
        "horizon": "NEXT_SESSION_WATCH", "is_full_position_ready": is_full_position_ready,
        "position_sizing_status": position_sizing_status,
        "fundamental_context": {"status": fundamental_status, "authority_tier": fundamental_tier,
                                "fundamental_research_readiness": "READY" if fundamental_tier == "OFFICIAL_QUALIFIED" else None,
                                "disposition": None},
        "rule_id": "R2_BREAKOUT_READY_CONFIRMED",
        "signals": {"close": 115.0, "ma_20": 100.0, "momentum_20d": 0.15},
        "is_actionable": False,
        "source_artifact_identity": "watchlist_tactical_entry_classifier:FIXTUREHASH",
        "session": "2026-08-21",
        "state_taxonomy": list(_TAXONOMY_STATE_TAXONOMY), "action_taxonomy": list(_ACTION_TAXONOMY),
        "action_by_entry_state": dict(_ACTION_BY_ENTRY_STATE),
        "entry_action_taxonomy": list(_ENTRY_ACTION_TAXONOMY), "entry_action_by_entry_state": dict(_ENTRY_ACTION_BY_ENTRY_STATE),
        "blocked_outputs": dict(_BLOCKED_OUTPUTS),
        "status": "classified",
    }


def _insufficient_record(ticker: str) -> dict:
    return {
        "ticker": ticker, "market_state": "MIXED_NO_CLEAR_MARKET_REGIME", "ticker_structure_state": "NOT_AVAILABLE",
        "entry_state": None, "action": "WAIT", "entry_action": "WAIT", "evidence_for": [],
        "evidence_against": ["Same-session technical features are unavailable for this ticker."],
        "confirmation_trigger": "Await same-session technical-feature availability before any tactical classification.",
        "invalidation": None,
        "data_quality": {"confidence": "INSUFFICIENT", "technical_eligible": False, "warnings": ["..."]},
        "horizon": None, "is_full_position_ready": False, "position_sizing_status": "NOT_EVALUATED",
        "fundamental_context": {"status": "NOT_IN_FUNDAMENTAL_COHORT", "authority_tier": None,
                                "fundamental_research_readiness": None, "disposition": None},
        "rule_id": "R0_TECHNICAL_FEATURES_UNAVAILABLE", "is_actionable": False,
        "source_artifact_identity": "watchlist_tactical_entry_classifier:FIXTUREHASH", "session": "2026-08-21",
        "state_taxonomy": list(_TAXONOMY_STATE_TAXONOMY), "action_taxonomy": list(_ACTION_TAXONOMY),
        "action_by_entry_state": dict(_ACTION_BY_ENTRY_STATE),
        "entry_action_taxonomy": list(_ENTRY_ACTION_TAXONOMY), "entry_action_by_entry_state": dict(_ENTRY_ACTION_BY_ENTRY_STATE),
        "blocked_outputs": dict(_BLOCKED_OUTPUTS),
        "status": "insufficient_data",
    }


def _bundle(records: dict) -> dict:
    return {"tickers": {ticker: {"watchlist_tactical_entry_classifier": record} for ticker, record in records.items()}}


class WatchlistTacticalEntryClassifierContractPassThroughTests(unittest.TestCase):
    def test_ticker_outside_bundle_returns_none(self) -> None:
        self.assertIsNone(b.watchlist_tactical_entry_classifier_contract({"tickers": {}}, "ZZZ"))
        self.assertIsNone(b.watchlist_tactical_entry_classifier_contract(None, "ZZZ"))

    def test_classified_record_passes_through_verbatim(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION")
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        self.assertEqual(result, record)
        self.assertIsNot(result, record)  # deep-copied, not a shared reference
        self.assertEqual(result["entry_action"], "BUY_ON_CONFIRMATION")
        self.assertEqual(result["position_sizing_status"], "NOT_EVALUATED")

    def test_deepcopy_mutation_does_not_leak_back(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION")
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        result["evidence_for"].append("MUTATED")
        self.assertNotIn("MUTATED", bundle["tickers"]["BRK"]["watchlist_tactical_entry_classifier"]["evidence_for"])

    def test_insufficient_data_record_passes_through(self) -> None:
        record = _insufficient_record("THN")
        bundle = _bundle({"THN": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "THN")
        self.assertEqual(result, record)
        self.assertIsNone(result["entry_state"])
        self.assertIsNone(result["horizon"])

    def test_early_entry_never_full_position_ready_accepted(self) -> None:
        record = _classified_record("REV", entry_state="EARLY_REVERSAL_CANDIDATE", action="EARLY_ENTRY", is_full_position_ready=False)
        bundle = _bundle({"REV": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "REV")
        self.assertFalse(result["is_full_position_ready"])

    def test_early_entry_with_full_position_ready_true_fails_closed(self) -> None:
        """A tampered/malformed upstream record claiming EARLY_ENTRY + full position ready must
        never reach the Consumer context as-is -- this is the structural enforcement of this
        milestone's own 'EARLY_ENTRY must never imply full-size position' rule at the Consumer
        boundary, independent of whatever the Producer already guarantees."""
        record = _classified_record("REV", entry_state="EARLY_REVERSAL_CANDIDATE", action="EARLY_ENTRY", is_full_position_ready=True)
        bundle = _bundle({"REV": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "REV")
        self.assertEqual(result["status"], "malformed")
        self.assertFalse(result["is_full_position_ready"])

    def test_accumulate_in_base_with_full_position_ready_true_fails_closed(self) -> None:
        record = _classified_record("BAS", entry_state="BASE_BUILDING", action="ACCUMULATE_IN_BASE", is_full_position_ready=True)
        bundle = _bundle({"BAS": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BAS")
        self.assertEqual(result["status"], "malformed")

    def test_breakout_ready_with_full_position_ready_true_also_fails_closed(self) -> None:
        """2026-08-23 closeout correction: position sizing is not implemented anywhere in this
        pipeline, so is_full_position_ready=true is now rejected unconditionally -- even for
        BREAKOUT_READY/BUY_ON_CONFIRMATION, which the old (now-removed) conditional gate used to
        allow under strict liquidity/fundamental/market conditions."""
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION", is_full_position_ready=True)
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        self.assertEqual(result["status"], "malformed")
        self.assertFalse(result["is_full_position_ready"])

    def test_position_sizing_status_not_not_evaluated_fails_closed(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION",
                                    position_sizing_status="SIZED")
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        self.assertEqual(result["status"], "malformed")

    def test_unknown_entry_action_fails_closed(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION",
                                    entry_action="STRONG_BUY")
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        self.assertEqual(result["status"], "malformed")

    def test_entry_action_never_hold_or_reduce_when_valid(self) -> None:
        """entry_action is the PRIMARY field for 'should I enter'; HOLD_DO_NOT_ADD/REDUCE_EXIT
        presuppose an existing position and must never appear there (2026-08-23 closeout
        correction) -- action (secondary, position-management-conditional) may still carry them."""
        for state, action in _ACTION_BY_ENTRY_STATE.items():
            with self.subTest(state=state):
                record = _classified_record("TKR", entry_state=state, action=action)
                bundle = _bundle({"TKR": record})
                result = b.watchlist_tactical_entry_classifier_contract(bundle, "TKR")
                self.assertEqual(result["status"], "classified")
                self.assertNotIn(result["entry_action"], ("HOLD_DO_NOT_ADD", "REDUCE_EXIT"))

    def test_missing_required_fields_fails_closed(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION")
        del record["confirmation_trigger"]
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        self.assertEqual(result["status"], "malformed")
        self.assertEqual(result["reason_codes"], ["watchlist_tactical_entry_classifier_malformed"])

    def test_is_actionable_true_fails_closed(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION")
        record["is_actionable"] = True
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        self.assertEqual(result["status"], "malformed")

    def test_unknown_action_fails_closed(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="STRONG_BUY", entry_action="AVOID")
        bundle = _bundle({"BRK": record})
        result = b.watchlist_tactical_entry_classifier_contract(bundle, "BRK")
        self.assertEqual(result["status"], "malformed")

    def test_apply_bundle_sets_context_key_and_provenance(self) -> None:
        record = _classified_record("BRK", entry_state="BREAKOUT_READY", action="BUY_ON_CONFIRMATION")
        bundle = _bundle({"BRK": record})
        context = {"ticker": "BRK", "provenance": []}
        b.apply_bundle_watchlist_tactical_entry_classifier_contract(context, bundle)
        self.assertIn("watchlist_tactical_entry_classifier", context)
        sources = [p["source_dataset"] for p in context["provenance"]]
        self.assertIn("watchlist_tactical_entry_classifier", sources)

    def test_apply_bundle_absent_key_leaves_context_untouched(self) -> None:
        context = {"ticker": "ZZZ", "provenance": []}
        b.apply_bundle_watchlist_tactical_entry_classifier_contract(context, {"tickers": {}})
        self.assertNotIn("watchlist_tactical_entry_classifier", context)
        self.assertEqual(context["provenance"], [])

    def test_all_nine_entry_states_accepted_when_well_formed(self) -> None:
        for state, action in _ACTION_BY_ENTRY_STATE.items():
            with self.subTest(state=state):
                record = _classified_record("TKR", entry_state=state, action=action)
                bundle = _bundle({"TKR": record})
                result = b.watchlist_tactical_entry_classifier_contract(bundle, "TKR")
                self.assertEqual(result["status"], "classified")
                self.assertEqual(result["entry_state"], state)


if __name__ == "__main__":
    unittest.main()
