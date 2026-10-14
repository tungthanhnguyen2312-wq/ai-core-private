"""Consumer pass-through of Producer ``financial_valuation_metric_research/v1``.

Fixtures were emitted by the unreleased Producer candidate 096b8f16's own test helpers
(synthetic PNJ rows).  They prove the contract shape, not live Daily compatibility.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.current_research_synthesis_operational_workflow import build_synthesis_request_package, prepare_synthesis_session
from builders.financial_metric_research_consumer_context import (
    FinancialMetricResearchConsumerContextError,
    build_financial_metric_research_consumer_context as project,
)

FIXTURES = ROOT / "tests" / "fixtures" / "producer_financial_valuation_metric_research_v1"
ROE = "ROE_REPORTED_PERIOD_END_EQUITY_PROXY"
CONTEXT = {"ticker": "PNJ"}


def load(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def reseal(payload: dict) -> dict:
    """Re-issue the Producer identity after a deliberate adversarial edit."""
    body = {k: v for k, v in payload.items() if k not in {"artifact_sha256", "artifact_identity"}}
    digest = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    return {**body, "artifact_sha256": digest, "artifact_identity": payload["contract_version"] + ":" + digest}


class FinancialMetricResearchConsumerContextTests(unittest.TestCase):
    def test_values_period_method_and_identity_pass_through_unchanged(self):
        payload = load("corporate_reported_roe")
        frozen = copy.deepcopy(payload)
        out = project(payload, "PNJ", session="2026-10-12")
        source = payload["records"]["PNJ"]["metrics"][ROE]
        roe = out["metrics"][ROE]
        self.assertEqual(payload, frozen)
        self.assertEqual("AVAILABLE", out["availability"])
        self.assertIs(roe["value"], source["value"])
        self.assertEqual(0.05, roe["value"])
        for field in ("method", "period_identity", "freshness", "statement_scope", "currency", "scale", "denominator_method",
                      "earnings_definition", "equity_definition", "formula", "formula_owner", "knowledge_time", "reason_codes", "limitations"):
            self.assertEqual(source[field], roe[field], field)
        self.assertEqual(payload["artifact_identity"], out["source_identity"]["artifact_identity"])
        self.assertEqual(payload["source_financial_v2_identity"], out["source_identity"]["source_financial_v2_identity"])
        self.assertEqual("2026-10-12", out["source_identity"]["decision_session"])
        self.assertEqual(ROE, roe["lineage_ref"]["metric_id"])
        self.assertNotIn("operand_lineage", roe)

    def test_research_proxy_is_distinct_from_exact_method_value(self):
        metrics = project(load("corporate_reported_roe"), "PNJ")["metrics"]
        self.assertEqual("RESEARCH_PROXY", metrics[ROE]["value_class"])
        self.assertEqual("RESEARCH_PROXY", metrics["P/B_OFFICIAL_RESEARCH"]["value_class"])
        self.assertEqual("NO_VALUE", metrics["P/E_TTM"]["value_class"])
        payload = load("corporate_reported_roe")
        # Even a READY fitness on a research-basis method stays a research proxy.
        payload["records"]["PNJ"]["metrics"]["P/B_OFFICIAL_RESEARCH"]["fitness"] = "READY"
        self.assertEqual("RESEARCH_PROXY", project(reseal(payload), "PNJ")["metrics"]["P/B_OFFICIAL_RESEARCH"]["value_class"])
        payload["records"]["PNJ"]["metrics"]["P/E"].update(fitness="READY", value=12.5)
        self.assertEqual("EXACT_METHOD_VALUE", project(reseal(payload), "PNJ")["metrics"]["P/E"]["value_class"])

    def test_blocked_and_not_applicable_keep_blockers_and_carry_no_value(self):
        bank = project(load("bank_not_applicable"), "PNJ")
        self.assertEqual("NOT_APPLICABLE", bank["metrics"][ROE]["fitness"])
        self.assertIsNone(bank["metrics"][ROE]["value"])
        self.assertEqual(["CORPORATE_RETURN_NOT_SPECIALIST_IDENTITY"], bank["metrics"][ROE]["reason_codes"])
        self.assertIn(ROE, bank["no_value_metric_ids"])
        shares = project(load("missing_shares"), "PNJ")
        self.assertEqual(["MARKET_CAP_RESEARCH_INPUT_UNAVAILABLE"], shares["metrics"]["P/E_REPORTED_PERIOD"]["reason_codes"])
        self.assertEqual(0.05, shares["metrics"][ROE]["value"])
        self.assertIn("BLOCKED_OR_MISSING_METRIC_IS_NOT_EVIDENCE", shares["research_use_restrictions"])

    def test_absent_payload_or_ticker_is_explicit_and_not_evidence(self):
        self.assertEqual(["PRODUCER_METRIC_RESEARCH_CONTEXT_NOT_PUBLISHED"], project(None, "PNJ")["reason_codes"])
        other = project(load("corporate_reported_roe"), "FPT")
        self.assertEqual(("ABSENT", ["PRODUCER_METRIC_RESEARCH_TICKER_NOT_IN_RECORDS"]), (other["availability"], other["reason_codes"]))
        self.assertNotIn("metrics", other)

    def test_unknown_future_metric_passes_through_but_never_exact(self):
        payload = load("corporate_reported_roe")
        future = copy.deepcopy(payload["records"]["PNJ"]["metrics"][ROE])
        future.update(metric_id="ROIC_FUTURE_METHOD", fitness="READY", value=0.11)
        payload["records"]["PNJ"]["metrics"]["ROIC_FUTURE_METHOD"] = future
        metric = project(reseal(payload), "PNJ")["metrics"]["ROIC_FUTURE_METHOD"]
        self.assertEqual((0.11, "UNCLASSIFIED_PRODUCER_METRIC", "RESEARCH_PROXY"), (metric["value"], metric["metric_family"], metric["value_class"]))

    def test_fail_closed_refusals(self):
        def refusal(mutate, *, sealed=True, session=None):
            payload = load("corporate_reported_roe")
            mutate(payload)
            with self.assertRaises(FinancialMetricResearchConsumerContextError) as raised:
                project(reseal(payload) if sealed else payload, "PNJ", session=session)
            return str(raised.exception)
        metrics = lambda p: p["records"]["PNJ"]["metrics"]
        self.assertEqual("FINANCIAL_METRIC_RESEARCH_IDENTITY_MISMATCH", refusal(lambda p: metrics(p)[ROE].update(value=0.5), sealed=False))
        self.assertEqual("FINANCIAL_METRIC_RESEARCH_VERSION_UNSUPPORTED", refusal(lambda p: p.update(contract_version="financial_valuation_metric_research/v2")))
        self.assertEqual("FINANCIAL_METRIC_RESEARCH_AUTHORITY_BOUNDARY_INVALID", refusal(lambda p: p["authority_boundary"].update(authority_promoted=True)))
        self.assertEqual("FINANCIAL_METRIC_RESEARCH_SESSION_MISMATCH", refusal(lambda p: None, session="2026-10-14"))
        self.assertEqual("FINANCIAL_METRIC_INELIGIBLE_VALUE_PRESENT:P/E_TTM", refusal(lambda p: metrics(p)["P/E_TTM"].update(value=9.0)))
        self.assertEqual("FINANCIAL_METRIC_VALUE_NOT_FINITE:" + ROE, refusal(lambda p: metrics(p)[ROE].update(value=None)))
        self.assertEqual("FINANCIAL_METRIC_FITNESS_UNSUPPORTED:" + ROE, refusal(lambda p: metrics(p)[ROE].update(fitness="QUALIFIED")))
        self.assertEqual("FINANCIAL_METRIC_ACTIONABILITY_MUST_BE_FALSE:" + ROE, refusal(lambda p: metrics(p)[ROE].update(is_actionable=True)))
        self.assertEqual("FINANCIAL_METRIC_TEMPORAL_FITNESS_MISSING:" + ROE, refusal(lambda p: metrics(p)[ROE].pop("freshness")))

    def test_synthesis_request_is_unchanged_without_payload_and_carries_projection_with_it(self):
        baseline = build_synthesis_request_package(CONTEXT)
        self.assertNotIn("financial_metric_research_context", baseline)
        payload = load("corporate_reported_roe")
        request = build_synthesis_request_package({**CONTEXT, "financial_valuation_metric_research": payload})
        self.assertEqual(project(payload, "PNJ"), request["financial_metric_research_context"])
        self.assertNotEqual(baseline["request_identity"], request["request_identity"])
        with self.assertRaises(ValueError):
            build_synthesis_request_package({**CONTEXT, "financial_valuation_metric_research": {**payload, "artifact_sha256": "0" * 64}})

    def test_prepare_without_retained_contexts_writes_identical_manifest(self):
        items = [{"context": {"ticker": "BBB"}}, {"context": {"ticker": "AAA"}}]
        kept = prepare_synthesis_session(items, session_label="s")
        lean = prepare_synthesis_session(items, session_label="s", retain_contexts=False)
        self.assertEqual(kept["manifest"], lean["manifest"])
        self.assertEqual({}, lean["contexts_by_ticker"])
        self.assertEqual({"AAA", "BBB"}, set(kept["contexts_by_ticker"]))


if __name__ == "__main__":
    unittest.main()
