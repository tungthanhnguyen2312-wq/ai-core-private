import unittest
from pathlib import Path


class QualifiedCohortAiPromptContractTests(unittest.TestCase):
    def test_prompt_binds_ai_to_producer_comparison_and_prohibited_claims(self):
        prompt = (Path(__file__).resolve().parents[1] / "prompts" / "ai_analysis_templates.md").read_text(encoding="utf-8")
        required = (
            "qualified_cohort_comparison", "sole authority", "cross_sectional_comparison",
            "multi_period_trend", "FX conversions", "PVD USD", "BUY/HOLD/SELL",
            "target price", "better investment", "position size", "source fact identities",
        )
        for value in required:
            self.assertIn(value, prompt)


if __name__ == "__main__":
    unittest.main()
