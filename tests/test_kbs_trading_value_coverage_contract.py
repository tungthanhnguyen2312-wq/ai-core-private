"""Consumer pass-through tests for the Producer KBS trading-value coverage verdict.

Every case runs against the frozen fixture Producer also pins, so a divergence between the
two repositories fails here rather than in a bundle. No network, no runtime artifact.
"""

from __future__ import annotations

import ast
import copy
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from builders import kbs_trading_value_coverage_contract as contract  # noqa: E402

FIXTURE = REPO_ROOT / "tests" / "fixtures" / "kbs_trading_value_export_block.json"


def fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class PassThroughTest(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.partial = self.data["partial_window_block"]
        self.complete = self.data["complete_window_block"]

    def test_11_every_required_coverage_field_survives_loading(self):
        result = contract.normalize_trading_value_contract(self.partial)
        self.assertTrue(result["present"])
        for field in contract.REQUIRED_COVERAGE_FIELDS:
            self.assertIn(field, result["coverage"], field)
        # Values are carried verbatim, not recomputed.
        for field in contract.REQUIRED_COVERAGE_FIELDS:
            self.assertEqual(result["coverage"][field], self.partial["coverage"][field], field)

    def test_11b_a_dropped_field_is_detected_rather_than_tolerated(self):
        for field in contract.REQUIRED_COVERAGE_FIELDS:
            damaged = copy.deepcopy(self.partial)
            del damaged["coverage"][field]
            with self.assertRaises(contract.TradingValueCoverageContractError, msg=field):
                contract.normalize_trading_value_contract(damaged)
        for field in contract.REQUIRED_BLOCK_FIELDS:
            damaged = copy.deepcopy(self.partial)
            del damaged[field]
            with self.assertRaises(contract.TradingValueCoverageContractError, msg=field):
                contract.normalize_trading_value_contract(damaged)

    def test_12_consumer_cannot_upgrade_coverage(self):
        produced = contract.normalize_trading_value_contract(self.partial)
        contract.assert_not_upgraded(producer=produced, consumer=produced)
        with self.assertRaises(contract.TradingValueCoverageContractError):
            contract.assert_not_upgraded(
                producer=produced,
                consumer={**produced, "coverage_state": contract.COVERAGE_COMPLETE},
            )
        with self.assertRaises(contract.TradingValueCoverageContractError):
            contract.assert_not_upgraded(
                producer=produced,
                consumer={
                    **produced,
                    "coverage": {**produced["coverage"], "usable_count": 99},
                },
            )
        # Narrowing is permitted.
        contract.assert_not_upgraded(
            producer=produced,
            consumer={**produced, "coverage_state": contract.COVERAGE_UNKNOWN},
        )
        # A block whose label contradicts its own counts is refused outright.
        forged = copy.deepcopy(self.partial)
        forged["coverage"]["coverage_state"] = contract.COVERAGE_COMPLETE
        forged["coverage"]["statistic_scope"] = contract.SCOPE_COMPLETE_WINDOW
        with self.assertRaises(contract.TradingValueCoverageContractError):
            contract.normalize_trading_value_contract(forged)

    def test_13_consumer_cannot_remove_partial_coverage_warnings(self):
        produced = contract.normalize_trading_value_contract(self.partial)
        contract.assert_warnings_preserved(produced)
        for stripped in (
            {**produced, "warning_tokens": [contract.TOKEN_PROVIDER_AUTHORITY]},
            {**produced, "warning_tokens": [contract.TOKEN_PARTIAL_COVERAGE]},
            {**produced, "not_comparable_to_complete_period_total": False},
        ):
            with self.assertRaises(contract.TradingValueCoverageContractError):
                contract.assert_warnings_preserved(stripped)
        # A block arriving without its partial warning is refused at load.
        damaged = copy.deepcopy(self.partial)
        damaged["warning_tokens"] = [contract.TOKEN_PROVIDER_AUTHORITY]
        with self.assertRaises(contract.TradingValueCoverageContractError):
            contract.normalize_trading_value_contract(damaged)

    def test_04b_present_zero_survives_consumer_loading(self):
        zero = contract.normalize_trading_value_contract(self.data["zero_row_block"])
        self.assertEqual(zero["coverage"]["present_zero_count"], 1)
        self.assertEqual(zero["coverage"]["usable_count"], 1)
        self.assertEqual(zero["coverage_state"], contract.COVERAGE_COMPLETE)
        omitted = contract.normalize_trading_value_contract(self.data["omitted_row_block"])
        self.assertEqual(omitted["coverage"]["field_omitted_count"], 1)
        self.assertEqual(omitted["coverage"]["present_null_count"], 0)
        self.assertEqual(omitted["coverage"]["usable_count"], 0)

    def test_16b_complete_window_claims_require_complete_coverage(self):
        complete = contract.normalize_trading_value_contract(self.complete)
        self.assertTrue(complete["aggregate_claims_allowed"])
        self.assertEqual(
            contract.evaluate_aggregate_claim(
                complete, claim="period_total_trading_value")["allowed"],
            True,
        )
        partial = contract.normalize_trading_value_contract(self.partial)
        self.assertFalse(partial["aggregate_claims_allowed"])
        decision = contract.evaluate_aggregate_claim(
            partial, claim="period_total_trading_value")
        self.assertFalse(decision["allowed"])
        self.assertEqual(decision["reason"], "coverage_is_not_complete_for_the_requested_window")
        # Some claims are unavailable even at complete coverage.
        for claim in ("official_market_turnover", "official_vwap_claim",
                      "trading_value_liquidity_metric", "cross_ticker_trading_value_ranking"):
            self.assertFalse(
                contract.evaluate_aggregate_claim(complete, claim=claim)["allowed"], claim
            )

    def test_17b_partial_aggregates_stay_labelled_observed_rows_only(self):
        partial = contract.normalize_trading_value_contract(self.partial)
        self.assertEqual(partial["statistic_scope"], contract.SCOPE_OBSERVED_ROWS_ONLY)
        self.assertTrue(partial["not_comparable_to_complete_period_total"])
        self.assertIn(contract.TOKEN_PARTIAL_COVERAGE, partial["warning_tokens"])


class LegacyTest(unittest.TestCase):
    def test_14_legacy_aggregate_without_coverage_fails_closed(self):
        result = contract.classify_legacy_payload({"trading_value": 1.2e12})
        self.assertEqual(result["legacy_class"], contract.LEGACY_AGGREGATE_WITHOUT_COVERAGE)
        self.assertFalse(result["aggregate_claims_allowed"])
        self.assertFalse(result["row_display_allowed"])
        self.assertEqual(result["coverage_state"], contract.COVERAGE_UNKNOWN)
        # And a bundle with no block at all resolves to unknown, never complete.
        empty = contract.normalize_trading_value_contract(None)
        self.assertFalse(empty["present"])
        self.assertEqual(empty["coverage_state"], contract.COVERAGE_UNKNOWN)
        self.assertFalse(empty["aggregate_claims_allowed"])
        self.assertEqual(empty["reason"], "no_producer_coverage_block")

    def test_15_legacy_row_observation_remains_displayable(self):
        result = contract.classify_legacy_payload(
            {"session_date": "2026-07-20", "trading_value_value": 1.1e12}
        )
        self.assertEqual(result["legacy_class"], contract.LEGACY_ROW_OBSERVATION)
        self.assertTrue(result["row_display_allowed"])
        self.assertFalse(result["aggregate_claims_allowed"])
        self.assertIn(contract.TOKEN_PROVIDER_AUTHORITY, result["warning_tokens"])
        self.assertEqual(
            contract.classify_legacy_payload({"close": 20000})["legacy_class"],
            contract.LEGACY_NO_TRADING_VALUE,
        )

    def test_15c_consumer_and_producer_agree_on_legacy_classification(self):
        data = fixture()
        self.assertEqual(
            contract.classify_legacy_payload(
                {"session_date": "2026-07-20", "trading_value_value": 1.1e12}
            )["legacy_class"],
            data["legacy_row_observation"]["legacy_class"],
        )
        self.assertEqual(
            contract.classify_legacy_payload({"trading_value": 1.2e12})["legacy_class"],
            data["legacy_aggregate_without_coverage"]["legacy_class"],
        )
        self.assertEqual(
            contract.classify_legacy_payload({"close": 20000})["legacy_class"],
            data["legacy_no_trading_value"]["legacy_class"],
        )


class AIContextTest(unittest.TestCase):
    def test_18_ai_context_distinguishes_provider_observation_from_official_turnover(self):
        data = fixture()
        for key in ("partial_window_block", "complete_window_block"):
            block = contract.normalize_trading_value_contract(data[key])
            ctx = contract.ai_context_block(block)
            self.assertEqual(ctx["field_label"], "kbs_provider_observed_trading_value")
            self.assertFalse(ctx["is_official_market_turnover"], key)
            self.assertIn(contract.TOKEN_PROVIDER_AUTHORITY, ctx["warning_tokens"])
            self.assertTrue(any("not an official exchange" in w for w in ctx["warnings"]))
        partial_ctx = contract.ai_context_block(
            contract.normalize_trading_value_contract(data["partial_window_block"])
        )
        self.assertIn(contract.TOKEN_PARTIAL_COVERAGE, partial_ctx["warning_tokens"])
        self.assertTrue(any("observed rows only" in w for w in partial_ctx["warnings"]))
        self.assertFalse(partial_ctx["aggregate_claims_allowed"])

    def test_19_ai_context_does_not_infer_liquidity_or_scope_from_trading_value(self):
        data = fixture()
        ctx = contract.ai_context_block(
            contract.normalize_trading_value_contract(data["complete_window_block"])
        )
        self.assertFalse(ctx["is_qualified_liquidity_evidence"])
        self.assertFalse(ctx["supports_market_scope_claim"])
        self.assertFalse(ctx["supports_actionability"])
        # Even a complete-coverage context refuses the liquidity claim.
        self.assertFalse(
            contract.evaluate_aggregate_claim(
                contract.normalize_trading_value_contract(data["complete_window_block"]),
                claim="trading_value_liquidity_metric",
            )["allowed"]
        )

    def test_18b_warnings_come_from_one_pinned_source(self):
        data = fixture()
        contract.assert_warnings_pinned(data["warnings_fingerprint"])
        self.assertEqual(contract.CANONICAL_WARNINGS, data["canonical_warnings"])
        with self.assertRaises(contract.TradingValueCoverageContractError):
            contract.assert_warnings_pinned("0" * 64)


class DeterminismTest(unittest.TestCase):
    def test_23_consumer_replay_is_deterministic(self):
        data = fixture()
        first = contract.normalize_trading_value_contract(data["partial_window_block"])
        second = contract.normalize_trading_value_contract(data["partial_window_block"])
        self.assertEqual(json.dumps(first, sort_keys=True), json.dumps(second, sort_keys=True))

    def test_22b_other_providers_do_not_inherit_kbs_coverage_semantics(self):
        data = fixture()
        foreign = copy.deepcopy(data["complete_window_block"])
        foreign["provider"] = "VCI"
        with self.assertRaises(contract.TradingValueCoverageContractError):
            contract.normalize_trading_value_contract(foreign)
        wrong_field = copy.deepcopy(data["complete_window_block"])
        wrong_field["source_field"] = "volume"
        with self.assertRaises(contract.TradingValueCoverageContractError):
            contract.normalize_trading_value_contract(wrong_field)

    def test_25_no_network_request_occurs(self):
        source = Path(contract.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        for forbidden in ("requests", "urllib", "http", "socket", "ssl", "sqlite3",
                          "subprocess", "asyncio"):
            self.assertNotIn(forbidden, imported, forbidden)
        self.assertEqual(imported, {"__future__", "hashlib", "json", "typing"})


if __name__ == "__main__":
    unittest.main()
