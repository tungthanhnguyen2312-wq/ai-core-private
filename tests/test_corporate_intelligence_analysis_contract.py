"""Contract guards for Corporate Intelligence use in the ticker-analysis prompt."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
PROMPT_PATH = ROOT / "prompts" / "ai_analysis_templates.md"


class CorporateIntelligenceAnalysisContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prompt = PROMPT_PATH.read_text(encoding="utf-8")

    def test_single_ticker_prompt_transmits_all_source_scoped_sections(self):
        for section in (
            "`company_profile`", "`company_subsidiaries`", "`ownership_structure`", "`major_shareholders`",
        ):
            self.assertIn(section, self.prompt)
        for required_field in ("source identity", "provenance", "raw relationship semantics", "snapshot date"):
            self.assertIn(required_field, self.prompt)
        self.assertIn("Do not merge KBS and VCI records", self.prompt)

    def test_statuses_are_data_warnings_not_negative_conclusions(self):
        for status in ("`missing`", "`partial`", "`malformed`", "`incomparable`"):
            self.assertIn(status, self.prompt)
        self.assertIn("under Data Warnings/Unknown", self.prompt)
        self.assertIn("not negative evidence about the company", self.prompt)

    def test_prompt_requires_fact_warning_and_inference_separation(self):
        self.assertIn("under Fact", self.prompt)
        self.assertIn("under Inference", self.prompt)
        self.assertIn("comparable", self.prompt)

    def test_old_context_without_section_remains_usable(self):
        self.assertIn("optional for backward-compatible older context packages", self.prompt)
        self.assertIn("has no `corporate_intelligence` section", self.prompt)
        self.assertIn("continue only with the other supported context sections", self.prompt)


if __name__ == "__main__":
    unittest.main()
