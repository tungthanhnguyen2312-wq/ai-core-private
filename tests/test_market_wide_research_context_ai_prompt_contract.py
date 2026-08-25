"""Prompt guardrails for the two non-authoritative research-context siblings."""
from pathlib import Path


PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "ai_analysis_templates.md").read_text(encoding="utf-8")


def test_historical_and_valuation_are_side_by_side_only_not_an_authority_synthesis():
    assert "A valid historical context and a valid `market_wide_current_valuation` context may be presented side-by-side" in PROMPT
    assert "session compatibility authorizes only descriptive comparison" in PROMPT
    assert "joint setup-quality/cheapness conclusion, VALUE eligibility, research priority, entry action, recommendation, probability, expected return, or sizing" in PROMPT


def test_numbered_prohibitions_name_historical_valuation_and_research_usable_boundaries():
    assert "(29) treating `market_wide_historical_research_context` as historical performance, alpha, probability, or backtest evidence" in PROMPT
    assert "translating its `structural_state` into `entry_action` or strategy eligibility" in PROMPT
    assert "(30) treating a `market_wide_current_valuation` `RESEARCH_USABLE` method as authoritative valuation" in PROMPT
    assert "valuation multiple as cheapness, VALUE eligibility, a target price, intrinsic value, DCF, BUY/SELL, recommendation, or position sizing" in PROMPT
    assert "(31) combining `market_wide_historical_research_context` with `market_wide_current_valuation`" in PROMPT
