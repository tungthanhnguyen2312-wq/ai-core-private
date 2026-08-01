import unittest
from pathlib import Path

from builders import build_ticker_context as b


def component(metric: str) -> dict:
    return {
        "canonical_metric": metric, "derivation_role": "required_component", "value": 1,
        "period_identity": {"period": "2024", "period_type": "annual"},
        "statement_scope": "consolidated", "currency": "VND", "unit_scale": 1,
        "source": "test", "observation_ids": [f"obs-{metric}"],
        "citation_id": f"cit-{metric}", "evidence_id": f"evi-{metric}",
    }


class FundamentalQualityContractTests(unittest.TestCase):
    def test_legacy_unknown(self):
        self.assertEqual(b.fundamental_quality_contract({"tickers": {"A": {}}}, "A")["status"], "unknown")

    def test_available(self):
        bundle = {"tickers": {"A": {"fundamental_quality": {"models": {"p": {"result_state": "unavailable"}}}}}}
        self.assertEqual(b.fundamental_quality_contract(bundle, "A")["status"], "available")

    def test_approved_nested_export_path_is_deterministic(self):
        path = b.WORKSPACE_ROOT / "exports" / "context_packages" / "phase4a-shadow" / "HPG_context.json"
        self.assertEqual(b.validate_safe_output_path(path), path.resolve())
        self.assertEqual(b.validate_safe_output_path(path), path.resolve())

    def test_output_outside_consumer_boundary_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Output must stay inside AI ANALYZE"):
            b.validate_safe_output_path(Path("C:/tmp/phase4a-shadow/HPG_context.json"))

    def test_hpg_vnm_derived_lineage_is_passed_through_without_recomputation(self):
        fact = {
            "value": 3, "period_identity": {"period": "2024", "period_type": "annual"},
            "statement_scope": "consolidated", "currency": "VND", "unit_scale": 1,
            "source": "financial_canonical", "observation_ids": ["derived-debt"],
            "citation_id": None, "evidence_id": None,
            "component_lineage": [component("long_term_borrowings"), component("short_term_borrowings")],
        }
        model = {"result_state": "available", "used_input_facts": {"total_debt": fact}}
        bundle = {"tickers": {ticker: {"fundamental_quality": {"models": {"financial_strength": model}}} for ticker in ("HPG", "VNM")}}
        received = b.fundamental_quality_contract(bundle, "HPG")
        self.assertEqual(received["models"]["financial_strength"]["used_input_facts"], {"total_debt": fact})
        received["models"]["financial_strength"]["used_input_facts"]["total_debt"]["value"] = 99
        self.assertEqual(bundle["tickers"]["HPG"]["fundamental_quality"]["models"]["financial_strength"]["used_input_facts"]["total_debt"]["value"], 3)

    def test_opportunity_ranking_is_passed_through_without_recomputation(self):
        dimensions={name:{"state":"available"} for name in ("financial_quality","valuation","technical_current_market_readiness","catalyst_evidence","downside_invalidation","data_confidence")}
        raw={"state":"available","dimensions":dimensions,"facts":[{"citation_id":"cit-1"}],"data_warnings":[],"inferences":[],"hypotheses":[],"interpretation_limits":["no recommendation"]}
        bundle={"tickers":{"HPG":{"opportunity_ranking":raw}}}
        received=b.opportunity_ranking_contract(bundle,"HPG")
        self.assertEqual(received["dimensions"],dimensions)
        received["dimensions"]["valuation"]["state"]="unknown"
        self.assertEqual(raw["dimensions"]["valuation"]["state"],"available")

    def test_vcb_bank_only_gating_is_preserved(self):
        models = {
            "bank_financial_quality": {"result_state": "available", "used_input_facts": {"net_income": {"citation_id": "cit-ni"}}},
            "financial_strength": {"result_state": "inapplicable", "warnings": ["corporate_variant_not_qualified_for_bank_entity"]},
            "earnings_quality": {"result_state": "inapplicable", "warnings": ["corporate_variant_not_qualified_for_bank_entity"]},
        }
        received = b.fundamental_quality_contract({"tickers": {"VCB": {"fundamental_quality": {"models": models}}}}, "VCB")
        self.assertEqual(received["models"], models)
        self.assertEqual(received["models"]["bank_financial_quality"]["result_state"], "available")
        self.assertEqual(received["models"]["financial_strength"]["result_state"], "inapplicable")

    def test_historical_capital_structure_is_passed_through_and_never_sets_readiness(self):
        raw = {"status": "available", "historical_only": True, "market_dependent": False,
               "is_actionable": False, "data_warnings": ["price_basis_unknown_or_unverified"],
               "metrics": {"net_debt": {"value": -1, "qualification_status": "qualified"}}}
        context = {"ticker": "HPG", "analysis_readiness": {"analysis_ready": False}, "provenance": []}
        b.apply_bundle_historical_capital_structure_contract(context, {"tickers": {"HPG": {"historical_capital_structure": raw}}})
        self.assertEqual(context["historical_capital_structure"], raw)
        self.assertFalse(context["analysis_readiness"]["analysis_ready"])

    def test_historical_fundamental_brief_is_verbatim_and_does_not_change_readiness(self):
        raw = {"status": "available", "historical_only": True, "market_dependent": False,
               "is_actionable": False, "facts": [], "data_warnings": ["price_basis_unknown_or_unverified"],
               "supported_inferences": [], "hypotheses": []}
        context = {"ticker": "VNM", "analysis_readiness": {"analysis_ready": False}, "provenance": []}
        b.apply_bundle_historical_fundamental_brief_contract(context, {"tickers": {"VNM": {"historical_fundamental_brief": raw}}})
        self.assertEqual(context["historical_fundamental_brief"], raw)
        self.assertFalse(context["analysis_readiness"]["analysis_ready"])


if __name__ == "__main__":
    unittest.main()
