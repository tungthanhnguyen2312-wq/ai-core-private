"""Focused unit tests for the market-wide packet-vs-legacy shadow parity gate.

Reuses the existing structured_research_synthesis_boundary packet-shadow fixtures
(TEST_FIXTURE_ONLY, defined in test_structured_research_synthesis_boundary.py) rather
than re-declaring a second copy of the same synthetic ticker_context/packet shapes.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

import test_structured_research_synthesis_boundary as fx  # noqa: E402

from builders.current_research_packet_shadow_parity import (  # noqa: E402
    DUAL_CONFLICT_FAIL_CLOSED,
    DUAL_EQUIVALENT,
    DUAL_NONCOMPARABLE_SEMANTICS,
    IDENTITY_UNAVAILABLE_FAIL_CLOSED,
    LEGACY_ONLY,
    MALFORMED_CONTEXT,
    PACKET_ONLY,
    UNRESOLVED_NO_USABLE_REPRESENTATION,
    CurrentResearchPacketShadowParityError,
    build_market_wide_parity_report,
    compute_ticker_parity,
    content_identity,
    replay,
)


def _full_context(ticker="TEST_TICKER", *, packet_kwargs=None):
    ctx = copy.deepcopy(fx._TICKER_CONTEXT_FIXTURE)
    ctx["ticker"] = ticker
    ctx["current_research_decision_packet"] = fx._packet_context(ticker=ticker, **(packet_kwargs or {}))
    return ctx


class ComputeTickerParityTests(unittest.TestCase):
    def test_matching_identity_component_is_dual_equivalent(self):
        row = compute_ticker_parity(_full_context())
        self.assertEqual(DUAL_EQUIVALENT, row["components"]["risk_register"])
        self.assertTrue(row["packet_present"])
        self.assertTrue(row["legacy_present"])
        self.assertFalse(row["context_malformed"])

    def test_scenario_is_always_noncomparable_never_equivalent_or_conflict(self):
        # Even with a deliberately mismatched packet scenario identity, scenario must
        # never resolve to DUAL_EQUIVALENT or DUAL_CONFLICT_FAIL_CLOSED -- Bear/Base/Bull
        # and CONSERVATIVE/BASE/SPECULATIVE are adjacent, distinct contracts.
        ctx = _full_context(packet_kwargs={"identities": {"scenario": "current_evidence_bound_scenario:UNRELATED"}})
        row = compute_ticker_parity(ctx)
        self.assertEqual(DUAL_NONCOMPARABLE_SEMANTICS, row["components"]["scenario"])

    def test_conflicting_identity_is_dual_conflict_fail_closed(self):
        ctx = _full_context(packet_kwargs={"identities": {"risk_register": "current_research_risk_register:DIFFERENT_HASH"}})
        row = compute_ticker_parity(ctx)
        self.assertEqual(DUAL_CONFLICT_FAIL_CLOSED, row["components"]["risk_register"])

    def test_packet_only_when_direct_sibling_absent(self):
        ctx = _full_context()
        fx._drop_sibling(ctx, "current_research_risk_register")
        row = compute_ticker_parity(ctx)
        self.assertEqual(PACKET_ONLY, row["components"]["risk_register"])
        self.assertTrue(row["legacy_present"])  # other direct siblings are still usable

    def test_legacy_only_when_packet_component_missing_but_sibling_present(self):
        """The gap this module fills beyond the boundary's own per-ticker product: a
        packet component that is locally malformed/absent must not silently vanish from
        a market-wide audit when its direct sibling is perfectly usable."""
        ctx = _full_context()
        components = copy.deepcopy(fx._PACKET_FULL_COMPONENTS)
        components["risk_register"] = {"status": "malformed", "reason_codes": ["x"]}
        ctx["current_research_decision_packet"] = fx._packet_context(components=components)
        row = compute_ticker_parity(ctx)
        self.assertEqual(LEGACY_ONLY, row["components"]["risk_register"])

    def test_unresolved_when_neither_side_usable(self):
        ctx = _full_context()
        fx._drop_sibling(ctx, "current_research_risk_register")
        components = copy.deepcopy(fx._PACKET_FULL_COMPONENTS)
        components["risk_register"] = {"status": "malformed", "reason_codes": ["x"]}
        ctx["current_research_decision_packet"] = fx._packet_context(components=components)
        row = compute_ticker_parity(ctx)
        self.assertEqual(UNRESOLVED_NO_USABLE_REPRESENTATION, row["components"]["risk_register"])

    def test_whole_packet_absent_is_legacy_only_overall_with_per_component_gap_filling(self):
        ctx = copy.deepcopy(fx._TICKER_CONTEXT_FIXTURE)  # no current_research_decision_packet at all
        row = compute_ticker_parity(ctx)
        self.assertEqual("LEGACY_ONLY", row["overall_status"])
        self.assertFalse(row["packet_present"])
        self.assertTrue(row["legacy_present"])
        # Every component whose direct sibling is usable must be filled in, not silently
        # dropped, once we are auditing market-wide rather than accepting one AI response.
        self.assertEqual(LEGACY_ONLY, row["components"]["risk_register"])
        self.assertEqual(LEGACY_ONLY, row["components"]["historical"])

    def test_malformed_ticker_context_shape_yields_malformed_context_for_every_component(self):
        ctx = _full_context()
        ctx["current_research_risk_register"] = "not-a-mapping"  # trips the boundary's basic shape check
        row = compute_ticker_parity(ctx)
        self.assertTrue(row["context_malformed"])
        self.assertEqual(MALFORMED_CONTEXT, row["overall_status"])
        self.assertTrue(all(status == MALFORMED_CONTEXT for status in row["components"].values()))

    def test_opportunity_priority_metadata_stays_noncomparable(self):
        ctx = _full_context()
        row = compute_ticker_parity(ctx)
        self.assertEqual(DUAL_NONCOMPARABLE_SEMANTICS, row["opportunity_priority_metadata_parity"])

    def test_decision_context_equivalent_and_conflict(self):
        equivalent = compute_ticker_parity(_full_context())
        self.assertEqual(DUAL_EQUIVALENT, equivalent["decision_context_parity"])

        conflicting = _full_context(packet_kwargs={"decision_context": {**fx._PACKET_DECISION_CONTEXT, "entry_action": "AVOID"}})
        conflicting_row = compute_ticker_parity(conflicting)
        self.assertEqual(DUAL_CONFLICT_FAIL_CLOSED, conflicting_row["decision_context_parity"])

    def test_raw_to_standard_map_is_closed_over_exactly_the_boundarys_own_vocabulary(self):
        from builders.current_research_packet_shadow_parity import _RAW_TO_STANDARD
        self.assertEqual(
            {"PACKET_ONLY", "EQUIVALENT", "NONCOMPARABLE_SEMANTICS", "CONFLICT_FAIL_CLOSED", "IDENTITY_UNAVAILABLE"},
            set(_RAW_TO_STANDARD),
        )

    def test_unresolved_and_identity_unavailable_are_distinct_from_malformed_context(self):
        """These three must never collapse into one label: UNRESOLVED means neither side
        has usable data, IDENTITY_UNAVAILABLE means both sides are usable but cannot be
        compared, MALFORMED_CONTEXT means the ticker_context itself is shape-invalid."""
        self.assertEqual(
            3, len({UNRESOLVED_NO_USABLE_REPRESENTATION, IDENTITY_UNAVAILABLE_FAIL_CLOSED, MALFORMED_CONTEXT}),
        )


class MarketWideReportTests(unittest.TestCase):
    def _small_universe(self):
        equivalent_ctx = _full_context(ticker="EQV")
        conflict_ctx = _full_context(
            ticker="CFL", packet_kwargs={"identities": {"risk_register": "current_research_risk_register:DIFFERENT_HASH"}},
        )
        packet_only_ctx = _full_context(ticker="PKO")
        fx._drop_sibling(packet_only_ctx, "current_research_risk_register")
        legacy_only_ctx = copy.deepcopy(fx._TICKER_CONTEXT_FIXTURE)
        legacy_only_ctx["ticker"] = "LGO"
        malformed_ctx = _full_context(ticker="MLF")
        malformed_ctx["current_research_risk_register"] = "not-a-mapping"
        return {
            "EQV": equivalent_ctx, "CFL": conflict_ctx, "PKO": packet_only_ctx,
            "LGO": legacy_only_ctx, "MLF": malformed_ctx,
        }

    def test_denominator_and_presence_counts(self):
        artifact = build_market_wide_parity_report(self._small_universe())
        self.assertEqual(5, artifact["denominator"])
        # EQV/CFL/PKO carry a structurally valid packet; LGO carries none; MLF's basic
        # ticker_context shape check fails on an unrelated key (current_research_risk_
        # register set to a non-Mapping) before packet status is ever derived, so a
        # malformed context conservatively reports nothing present, including its packet.
        self.assertEqual(3, artifact["packet_present_count"])
        self.assertEqual(1, artifact["malformed_context_count"])  # MLF

    def test_totals_reconcile_to_total_component_cells_with_zero_residual(self):
        artifact = build_market_wide_parity_report(self._small_universe())
        self.assertEqual(0, artifact["unexplained_residual_count"])
        self.assertEqual(sum(artifact["totals"].values()), artifact["total_component_cells"])
        self.assertEqual(artifact["denominator"] * len(artifact["component_names"]), artifact["total_component_cells"])

    def test_component_breakdown_sums_match_totals(self):
        artifact = build_market_wide_parity_report(self._small_universe())
        for name in artifact["component_names"]:
            breakdown_sum = sum(artifact["component_breakdown"][name].values())
            self.assertEqual(5, breakdown_sum, f"{name} breakdown does not cover every ticker")

    def test_scenario_never_reaches_equivalent_or_conflict_across_the_universe(self):
        artifact = build_market_wide_parity_report(self._small_universe())
        scenario_breakdown = artifact["component_breakdown"]["scenario"]
        self.assertEqual(0, scenario_breakdown.get(DUAL_EQUIVALENT, 0))
        self.assertEqual(0, scenario_breakdown.get(DUAL_CONFLICT_FAIL_CLOSED, 0))

    def test_content_identity_is_deterministic_and_input_sensitive(self):
        universe = self._small_universe()
        first = build_market_wide_parity_report(universe)
        second = build_market_wide_parity_report(universe)
        self.assertEqual(first["artifact_sha256"], second["artifact_sha256"])

        smaller_universe = dict(universe)
        del smaller_universe["MLF"]
        third = build_market_wide_parity_report(smaller_universe)
        self.assertNotEqual(first["artifact_sha256"], third["artifact_sha256"])

        recomputed = content_identity(first)
        self.assertEqual(first["artifact_sha256"], recomputed["artifact_sha256"])

    def test_replay_accepts_a_well_formed_artifact_and_rejects_tampering(self):
        artifact = build_market_wide_parity_report(self._small_universe())
        replay(artifact)  # must not raise

        tampered = copy.deepcopy(artifact)
        tampered["denominator"] = 999
        with self.assertRaises(CurrentResearchPacketShadowParityError):
            replay(tampered)

        tampered_residual = copy.deepcopy(artifact)
        tampered_residual["unexplained_residual_count"] = 1
        with self.assertRaises(CurrentResearchPacketShadowParityError):
            replay(tampered_residual)

    def test_promotion_readiness_never_declares_promotion_or_default_change(self):
        artifact = build_market_wide_parity_report(self._small_universe())
        readiness = artifact["promotion_readiness"]
        self.assertEqual("NOT_MADE_BY_THIS_GATE_OWNER_REVIEW_REQUIRED", readiness["promotion_decision"])
        self.assertEqual("LEGACY_DIRECT", readiness["default_path_unchanged"])
        self.assertEqual("LEGACY_DIRECT", artifact["authority_boundary"]["default_path_unchanged"])
        self.assertTrue(readiness["are_conflicts_present"]["answer"])  # CFL contributes one
        self.assertTrue(readiness["are_noncomparable_semantic_families_kept_separate"]["answer"])

    def test_representative_evidence_covers_the_constructed_cases(self):
        artifact = build_market_wide_parity_report(self._small_universe())
        evidence = artifact["representative_evidence"]
        self.assertTrue(evidence["dual_equivalent"])
        self.assertTrue(evidence["material_comparable_conflict"])
        self.assertTrue(evidence["packet_only"])
        self.assertTrue(evidence["legacy_only"])
        self.assertTrue(evidence["noncomparable_scenario_coexistence"])
        self.assertTrue(evidence["noncomparable_prioritization_metadata"])
        # No fabrication: every category is present in the artifact even when a
        # particular constructed universe has no real match for it.
        for category, examples in evidence.items():
            self.assertIsInstance(examples, list)

    def test_no_forbidden_ai_authority_concepts_appear_as_values(self):
        """Field NAMES may legitimately name a prohibited concept to declare its absence
        (e.g. authority_boundary's own creates_no_recommendation_probability_...  key,
        mirroring current_research_decision_packet.py's own FORBIDDEN/blocked_outputs
        convention) -- what must never happen is one of those concepts appearing as an
        emitted VALUE, so this walks values only, not keys."""
        artifact = build_market_wide_parity_report(self._small_universe())
        forbidden_values = {"buy", "sell", "hold", "promoted"}

        def _walk(node):
            if isinstance(node, dict):
                for value in node.values():
                    _walk(value)
            elif isinstance(node, list):
                for item in node:
                    _walk(item)
            elif isinstance(node, str):
                self.assertNotIn(node.strip().lower(), forbidden_values, f"forbidden value leaked: {node!r}")
            elif isinstance(node, (int, float)) and not isinstance(node, bool):
                pass  # counts/denominators are expected numeric content, not a probability/target-price claim

        _walk(artifact)
        self.assertEqual("NOT_MADE_BY_THIS_GATE_OWNER_REVIEW_REQUIRED", artifact["promotion_readiness"]["promotion_decision"])


if __name__ == "__main__":
    unittest.main()
