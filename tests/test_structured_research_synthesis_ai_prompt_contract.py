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
            "`market_context_summary`", "`sector_context_summary`", "`relative_strength_context`",
            "`catalyst_context`", "`risk_context`", "`invalidation_conditions`", "`unresolved_questions`",
            "`authority_limitations`", "`upstream_decision_context`", "`provenance_references`", "`is_actionable`",
        ):
            self.assertIn(field, PROMPT)

    def test_market_sector_leadership_context_documented_in_single_ticker_template(self):
        self.assertIn("If `current_market_sector_leadership_context` is present", PROMPT)
        self.assertIn("never a trade signal by itself", PROMPT)
        self.assertIn("an unknown sector identity stays unknown and must never be inferred", PROMPT)
        self.assertIn("CURRENT_CROSS_SECTIONAL_DESCRIPTIVE_NOT_ORDINAL_RANKING", PROMPT)

    def test_market_sector_authority_boundary_in_synthesis_template(self):
        self.assertIn("if upstream `entry_action` is `WAIT`, strong sector leadership cannot turn it into entry", PROMPT)
        self.assertIn("market breadth cannot promote it", PROMPT)
        self.assertIn("Never combine market, sector, technical, and valuation evidence into one opaque synthetic confidence score", PROMPT)
        self.assertIn("never an unchanged or zero return", PROMPT)

    def test_market_sector_prohibited_claims_extend_master_list(self):
        for forbidden in (
            "treating `current_market_sector_leadership_context.market.current_breadth_state` as a trade signal by itself",
            "treating `sector_leadership_context`'s `leadership_state` as strategy eligibility",
            "inferring a ticker's sector identity from its name or general knowledge",
            "treating a `missing_current_session_count` ticker as an unchanged or zero return",
            "combining `current_market_sector_leadership_context` with technical, valuation, or historical evidence into one opaque combined score",
        ):
            self.assertIn(forbidden, PROMPT)

    def test_financial_momentum_documented_in_single_ticker_template(self):
        self.assertIn("If `current_financial_momentum_context` is present", PROMPT)
        self.assertIn("`OFFICIAL_QUALIFIED`, `PROVIDER_RESEARCH`, `BLOCKED`, or `UNAVAILABLE`", PROMPT)
        self.assertIn("never merged", PROMPT)
        self.assertIn("revenue up, margin down is `MIXED`, not \"improving\"", PROMPT)
        self.assertIn("FY YoY is not \"current earnings,\"", PROMPT)
        self.assertIn("absence_from_fundamental_cohort_is_not_zero_or_deterioration", PROMPT)

    def test_financial_momentum_routed_through_existing_synthesis_fields(self):
        self.assertIn("it does not get its own dedicated summary field", PROMPT)
        self.assertIn("cited directly into `thesis`, `supporting_evidence`, `counter_thesis`, `risk_context`, and `unresolved_questions`", PROMPT)
        self.assertIn("cannot itself enable, create, or upgrade one, nor change `strategy_eligibility`, `research_priority`, or `entry_action`", PROMPT)

    def test_financial_momentum_prohibited_claims_extend_master_list(self):
        for forbidden in (
            "describing `current_financial_momentum_context`'s `PROVIDER_RESEARCH` evidence tier as official-qualified",
            "turning `financial_momentum_state` (including `BROAD_IMPROVEMENT`) into a forecast, target price, cheapness/VALUE conclusion, probability, recommendation, entry action, or sizing figure",
            "relabelling a `QoQ`/`PARTIAL` component comparison as `YoY`",
            "treating a component `status` of `UNAVAILABLE`/`BLOCKED` as zero, negative, or deteriorating",
            "forcing an industrial revenue/margin/cash-flow interpretation onto a bank/securities `entity_class` component",
            "treating `current_financial_momentum_context` as enabling, creating, or upgrading a `FUNDAMENTAL_IMPROVEMENT` state",
        ):
            self.assertIn(forbidden, PROMPT)

    def test_corporate_event_context_documented_in_single_ticker_template(self):
        self.assertIn("If `current_corporate_event_context` is present", PROMPT)
        self.assertIn(
            "`CONFIRMED_UPCOMING`, `CONFIRMED_RECENT`, `EXECUTED`, `PLANNED_NOT_EXECUTED`, `CANCELLED`, "
            "`TEMPORAL_DETAILS_INCOMPLETE`, `CONFLICTING_EVIDENCE`, or `DATA_LIMITED`",
            PROMPT,
        )
        self.assertIn("never bullish/bearish, positive/negative, or a reaction probability", PROMPT)
        self.assertIn("`record_date` without `ex_date` stays `record_date` without `ex_date`", PROMPT)
        self.assertIn("never synthesize a missing `ex_date` as `record_date` minus one trading day", PROMPT)
        self.assertIn("PLANNED_NOT_EXECUTED` stays planned/approved unless the retained record itself carries execution evidence", PROMPT)
        self.assertIn("insufficient_for_event_driven=true", PROMPT)
        self.assertIn("this sibling alone can never mint or upgrade it", PROMPT)

    def test_corporate_event_context_routed_through_existing_synthesis_fields(self):
        self.assertIn(
            "cited directly into `thesis`, `supporting_evidence`, `counter_thesis`, `counter_evidence`, "
            "`catalyst_context`, `risk_context`, and `unresolved_questions`",
            PROMPT,
        )
        self.assertIn("`catalyst_context` is its natural home for a confirmed/upcoming event", PROMPT)
        self.assertIn("This sibling can never itself confirm, create, or upgrade `EVENT_DRIVEN` strategy eligibility", PROMPT)

    def test_corporate_event_prohibited_claims_extend_master_list(self):
        for forbidden in (
            "describing a `current_corporate_event_context` event as bullish, bearish, or otherwise implying a price direction",
            "fabricating an event reaction probability",
            "inferring a missing `ex_date` from `record_date`",
            "describing a `PLANNED_NOT_EXECUTED` event as executed, completed, or effectively done",
            "silently resolving a `CONFLICTING_EVIDENCE` event's conflicting dates to one value by source preference",
            "treating a retained corporate event, its recency, its status, or its official evidence tier as itself confirming, creating, or upgrading `EVENT_DRIVEN` strategy eligibility",
            "issuing a BUY/SELL/HOLD recommendation timed to a `record_date`/`ex_date`",
            "asserting an event was known or confirmed earlier than its own retained `known_at`/`published_at` boundary",
        ):
            self.assertIn(forbidden, PROMPT)

    def test_risk_register_documented_in_single_ticker_template(self):
        self.assertIn("If `current_research_risk_register` is present", PROMPT)
        self.assertIn(
            "never merge them, and never derive a numeric or global risk score, grade, or rating from their counts",
            PROMPT,
        )
        self.assertIn(
            "an empty `material_risks` list means only that no material risk has been established "
            "from the available evidence -- never LOW_RISK, SAFE, or suitable for large sizing",
            PROMPT,
        )
        self.assertIn(
            "a blocked valuation authority does not mean the stock is expensive, and an unknown sector "
            "does not mean the sector is a source of risk",
            PROMPT,
        )
        self.assertIn("this register has no single unified session of its own", PROMPT)
        self.assertIn("it can never override, upgrade, or downgrade `entry_action`, `research_priority`, or strategy eligibility", PROMPT)

    def test_risk_register_routed_through_existing_synthesis_fields(self):
        self.assertIn(
            "cited directly into `risk_context`, `counter_thesis`, `counter_evidence`, `unresolved_questions`, "
            "and `authority_limitations`",
            PROMPT,
        )
        self.assertIn("it does not get its own dedicated summary field", PROMPT)
        self.assertIn("this is never rephrased as LOW_RISK, SAFE, or a sizing endorsement", PROMPT)

    def test_risk_register_prohibited_claims_extend_master_list(self):
        for forbidden in (
            "deriving a numeric or global risk score, grade, rating, or \"overall risk\" figure from `current_research_risk_register`'s item counts",
            "treating an empty `risk_register.material_risks` list, or `risk_register_status=\"NO_MATERIAL_RISK_ESTABLISHED_FROM_AVAILABLE_EVIDENCE\"`, as a LOW_RISK, SAFE, or \"few risk flags mean it's safer\" conclusion",
            "treating a `data_authority_limitations` item",
            "fabricating a probability, expected loss, or Value-at-Risk figure from `current_research_risk_register` evidence",
            "claiming `current_research_risk_register` overrides, upgrades, or downgrades `entry_action`, `research_priority`, or strategy eligibility",
            "deriving a position-size or participation-capacity instruction or inference from `current_research_risk_register` evidence",
            "silently resolving an `unresolved_conflicts` item to one interpretation",
            "merging `material_risks`, `watch_risks`, `data_authority_limitations`, and `unresolved_conflicts` into one undifferentiated risk list or count",
        ):
            self.assertIn(forbidden, PROMPT)

    def test_scenario_context_documented_in_single_ticker_template(self):
        self.assertIn("If `current_research_scenario_context` is present", PROMPT)
        self.assertIn("three orthogonal current-research/decision-condition axes", PROMPT)
        self.assertIn("never Bear/Base/Bull price-direction labels, never probabilities, never strategy lanes, and never entry actions", PROMPT)
        self.assertIn("`CONSERVATIVE` is never bearish or automatically safe/safer/safest", PROMPT)
        self.assertIn("`BASE` is a current-state interpretation only and is never the most-likely or expected case", PROMPT)
        self.assertIn("never a bullish or higher-expected-return claim, and it never lowers the evidence standard", PROMPT)
        self.assertIn("if `entry_action` is `WAIT`, it stays `WAIT` regardless of any axis's status", PROMPT)
        self.assertIn("never replaces, the existing evidence-bound Bear/Base/Bull scenario overlay", PROMPT)

    def test_scenario_context_routed_through_existing_synthesis_fields(self):
        self.assertIn(
            "cited directly into `thesis`, `supporting_evidence`, `counter_thesis`, `counter_evidence`, "
            "`risk_context`, `invalidation_conditions`, `unresolved_questions`, and `authority_limitations`",
            PROMPT,
        )
        self.assertIn("optional `scenario_context_summary` object", PROMPT)
        self.assertIn("must quote Producer's own per-axis `scenario_status`/`status_rule` byte-exact", PROMPT)
        self.assertIn("it can never be cited at all once the sibling itself is malformed", PROMPT)
        self.assertIn('"BASE is supported, while the deterministic entry action remains WAIT" is a valid explanation', PROMPT)
        self.assertIn('"BASE supported therefore BUY" or "not supported, so downgrade to WAIT" are not', PROMPT)

    def test_scenario_context_prohibited_claims_extend_master_list(self):
        for forbidden in (
            "treating `current_research_scenario_context`'s CONSERVATIVE/BASE/SPECULATIVE axes as Bear/Base/Bull price-direction labels",
            "fabricating a scenario probability, a \"most likely\"/\"less likely\"/\"more likely\" comparative-likelihood claim",
            "describing BASE's `scenario_status=\"SUPPORTED\"` as the most-likely or expected outcome",
            "describing SPECULATIVE's `scenario_status=\"SUPPORTED\"` as bullish, a higher-expected-return, or a higher-upside claim",
            "describing CONSERVATIVE's `scenario_status` as bearish, or as automatically safe/safer/safest",
            "claiming a scenario axis's status causes, overrides, upgrades, or downgrades `entry_action`, `research_priority`, or strategy eligibility",
            "inventing a price level, financial threshold, event date, or target to fill an `UNAVAILABLE` `confirmation_conditions`/`invalidation_conditions` gate",
            "reporting a `scenario_context_summary` value that does not byte-exactly match Producer's own per-axis `scenario_status`/`status_rule`",
        ):
            self.assertIn(forbidden, PROMPT)

    def test_scenario_context_summary_optional_field_documented(self):
        self.assertIn(
            "You may additionally include one optional field, `scenario_context_summary`, only when "
            "`current_research_scenario_context` is present in the attached package; omit it entirely otherwise.",
            PROMPT,
        )

    def test_absent_sibling_enumeration_includes_scenario_context(self):
        self.assertIn(
            "If a historical, valuation, market/sector, financial-momentum, corporate-event, risk-register, "
            "or scenario-context sibling is absent, missing, or malformed",
            PROMPT,
        )

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

    def test_liquidity_capacity_and_alpha_out_of_scope_explicit(self):
        self.assertIn("This contract consumes no liquidity, traded-value, or matched-value lane", PROMPT)
        self.assertIn("never state or imply alpha, a DCF assumption, or a liquidity/execution/participation capacity", PROMPT)

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
