"""Prompt contract guards for the historical FY2024 fundamental brief."""

from __future__ import annotations

import unittest
from pathlib import Path


PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "ai_analysis_templates.md").read_text(encoding="utf-8")


class HistoricalFundamentalBriefPromptTests(unittest.TestCase):
    def test_all_categories_and_historical_metadata_are_explicit(self):
        for field in ("`facts`", "`data_warnings`", "`supported_inferences`", "`hypotheses`", "`missing_evidence`", "`invalidation_conditions`", "publication timestamp", "consolidated scope", "`provenance_references`"):
            self.assertIn(field, PROMPT)
        self.assertIn("Historical FY2024 Fundamental Brief", PROMPT)

    def test_categories_and_empty_hypotheses_are_not_reinterpreted(self):
        for clause in ("Do not recompute any metric", "merge facts with supported inferences", "Keep `hypotheses` empty", "must be omitted from the final output"):
            self.assertIn(clause, PROMPT)

    def test_market_warnings_and_prohibited_analysis_are_explicit(self):
        for warning in ("unknown price basis", "unknown volume basis", "unqualified current shares", "unavailable current-market trust"):
            self.assertIn(warning, PROMPT)
        for forbidden in ("ranking", "buy/sell/hold language", "target price", "valuation conclusion", "market-cap", "enterprise-value", "adjusted-return", "portfolio sizing", "backtest claim", "current-market momentum"):
            self.assertIn(forbidden, PROMPT)

    def test_frozen_prompt_rendering_is_deterministic_for_hpg_and_vnm(self):
        for ticker in ("HPG", "VNM"):
            first = PROMPT.replace("{TICKER}", ticker)
            self.assertEqual(first, PROMPT.replace("{TICKER}", ticker))


if __name__ == "__main__":
    unittest.main()
