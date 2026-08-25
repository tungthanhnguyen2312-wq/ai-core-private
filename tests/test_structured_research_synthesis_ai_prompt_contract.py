"""Prompt contract guards for the structured research synthesis template (AI_STRUCTURED_RESEARCH_SYNTHESIS_V1)."""

from __future__ import annotations

import unittest
from pathlib import Path


PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "ai_analysis_templates.md").read_text(encoding="utf-8")


class StructuredResearchSynthesisPromptContractTests(unittest.TestCase):
    def test_template_section_present(self):
        self.assertIn("## 4. Structured research synthesis template", PROMPT)
        self.assertIn("builders/structured_research_synthesis_boundary.py", PROMPT)

    def test_required_fields_are_explicit(self):
        for field in (
            "`ticker`", "`analysis_session`", "`synthesis_status`", "`thesis`", "`supporting_evidence`",
            "`counter_thesis`", "`counter_evidence`", "`historical_context_summary`", "`valuation_context_summary`",
            "`catalyst_context`", "`risk_context`", "`invalidation_conditions`", "`unresolved_questions`",
            "`authority_limitations`", "`upstream_decision_context`", "`provenance_references`", "`is_actionable`",
        ):
            self.assertIn(field, PROMPT)

    def test_counter_thesis_is_mandatory(self):
        self.assertIn("`counter_thesis` is mandatory", PROMPT)
        self.assertIn("a generic disclaimer is not a counter-thesis", PROMPT)

    def test_core_authority_rule_explicit(self):
        self.assertIn("You may EXPLAIN an upstream deterministic state; you may never MINT or UPGRADE one", PROMPT)
        self.assertIn("if it says `WAIT`, this object still says `WAIT`, never `BUY`", PROMPT)

    def test_prohibited_minted_fields_explicit(self):
        for forbidden in (
            "`research_priority`", "`entry_action`", "`action`", "`probability`", "`confidence`",
            "`expected_return`", "`target_price`", "`intrinsic_value`", "`dcf`", "`position_size`",
            "`recommendation`", "`rating`", "and `score`",
        ):
            self.assertIn(forbidden, PROMPT)
        self.assertIn("must never appear as top-level fields of this object", PROMPT)

    def test_historical_authority_boundary_explicit(self):
        self.assertIn("RETROSPECTIVE_DESCRIPTIVE_WITHIN_TICKER", PROMPT)
        self.assertIn("it never becomes an entry action or strategy eligibility", PROMPT)

    def test_valuation_authority_boundary_explicit(self):
        self.assertIn("a ticker may have usable P/B and blocked EV/EBITDA at the same time", PROMPT)
        self.assertIn("`RESEARCH_USABLE` stays research-only, never cheapness, VALUE eligibility, or a target price", PROMPT)

    def test_session_discipline_explicit(self):
        self.assertIn("Session identities are not interchangeable", PROMPT)
        self.assertIn("never merged into one synthesized \"current\" date", PROMPT)

    def test_missing_sibling_handling_explicit(self):
        self.assertIn("absence of one optional sibling must never blank out the whole object", PROMPT)
        self.assertIn("omit the unsupported factual conclusion, surface the limitation explicitly", PROMPT)

    def test_uncertainty_vocabulary_is_qualitative_not_numeric(self):
        for status in (
            "`EVIDENCE_COMPLETE`", "`PARTIAL_EVIDENCE`", "`MATERIAL_UNRESOLVED_DATA`",
            "`CONFLICTING_EVIDENCE`", "or `AUTHORITY_LIMITED`",
        ):
            self.assertIn(status, PROMPT)
        self.assertIn("never a numeric confidence or probability", PROMPT)

    def test_fabrication_prohibitions_explicit(self):
        self.assertIn(
            "do not fabricate management guidance, corporate actions, financial facts, catalysts, or historical outcomes",
            PROMPT,
        )
        self.assertIn("never an invented price level", PROMPT)

    def test_evidence_traceability_required(self):
        self.assertIn("do not invent a source that is not supplied", PROMPT)
        self.assertIn("market_wide_current_valuation.metrics.<method>", PROMPT)

    def test_no_live_ticker_values_embedded_in_reusable_prompt(self):
        """The reusable prompt MUST NOT embed concrete live figures for any real ticker."""
        section_start = PROMPT.index("## 4. Structured research synthesis template")
        section_end = PROMPT.index("## Provenance / Source Basis")
        section = PROMPT[section_start:section_end]
        for forbidden_literal in ("35000", "0.809", "0.566", "-2.22", "-9.56"):
            self.assertNotIn(forbidden_literal, section)


if __name__ == "__main__":
    unittest.main()
