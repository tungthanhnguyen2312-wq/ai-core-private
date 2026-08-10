"""Dedicated prompt-contract tests for multi-angle AI synthesis across price analytics, market risk, and foreign flow."""

from __future__ import annotations

import unittest
from pathlib import Path

PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "ai_analysis_templates.md").read_text(encoding="utf-8")


class MultiAngleAiPromptContractTests(unittest.TestCase):
    def test_multi_angle_lanes_are_explicit(self):
        for required_lane in (
            "`current_state_price_analytics`",
            "`current_state_market_risk`",
            "`foreign_flow`",
        ):
            self.assertIn(required_lane, PROMPT)

    def test_safety_flags_are_explicit(self):
        self.assertIn("`pit_backtest_eligible=false`", PROMPT)
        self.assertIn("`is_actionable=false`", PROMPT)
        self.assertIn("cannot independently justify an investment action", PROMPT)
        self.assertIn("cannot be cited as point-in-time historical backtest evidence", PROMPT)

    def test_unavailable_indicator_preservation_guarded(self):
        self.assertIn("`sma_20.status = unavailable`", PROMPT)
        self.assertIn("MUST NOT fabricate SMA20", PROMPT)
        self.assertIn("infer its value, replace it with current price, or state whether price is above or below SMA20", PROMPT)

    def test_market_risk_sample_adequacy_and_causality_guarded(self):
        self.assertIn("`MATHEMATICALLY_COMPUTABLE`", PROMPT)
        self.assertIn("NOT that it is statistically robust or significant", PROMPT)
        self.assertIn("Correlation does not imply causation", PROMPT)
        self.assertIn("`paired_return_count`", PROMPT)

    def test_foreign_flow_value_scope_and_causality_guarded(self):
        self.assertIn("qualified foreign net transaction VALUE lane", PROMPT)
        self.assertIn("Do not infer qualified foreign volume, foreign room semantics, flow-to-turnover ratios, institutional accumulation, or causal price impact", PROMPT)

    def test_conflicting_evidence_explicit(self):
        self.assertIn("suppress conflicts", PROMPT)
        self.assertIn("**Conflicting Evidence**", PROMPT)
        self.assertIn("explicitly", PROMPT)
        self.assertIn("before forming any higher-level inference", PROMPT)
        self.assertIn("do not resolve the disagreement by inventing confidence", PROMPT)
        self.assertIn("automatic BUY/SELL or directional rating", PROMPT)

    def test_fact_inference_categories_and_synthesis_order(self):
        for category in ("**Fact**", "**Data Warnings / Limitations**", "**Inference**", "**Conflicting Evidence**", "**Hypotheses**", "**Missing Evidence**", "**Invalidation Conditions**"):
            self.assertIn(category, PROMPT)
        self.assertIn("Synthesize in logical order: (1) fundamental/business quality, (2) price/technical behavior, (3) benchmark/market risk, (4) foreign flow, (5) corporate/event evidence, (6) warnings/missing evidence", PROMPT)

    def test_prohibited_claims_explicit(self):
        for forbidden in (
            "BUY/SELL/HOLD recommendations",
            "target prices or valuation claims",
            "claiming RSI or any technical indicator is an independent buy or sell signal",
            "treating unavailable SMA20 as known",
            "claiming a current-state beta is a permanent or true long-term risk score",
            "claiming correlation proves causation",
            "claiming a bounded `paired_return_count` or `MATHEMATICALLY_COMPUTABLE` sample adequacy is statistically robust",
            "treating foreign net buy VALUE as proof of institutional accumulation",
            "treating current-state analytics as PIT/backtest evidence",
        ):
            self.assertIn(forbidden, PROMPT)

    def test_no_live_hpg_snapshot_values_embedded_in_reusable_prompt(self):
        """The reusable prompt MUST NOT embed concrete live HPG numbers."""
        for forbidden_literal in ("-2.22", "-9.56", "47.27", "0.809", "0.566"):
            self.assertNotIn(forbidden_literal, PROMPT)


if __name__ == "__main__":
    unittest.main()
