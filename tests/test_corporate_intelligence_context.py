"""Read-only Corporate Intelligence consumer contract tests."""

from __future__ import annotations

import copy
import unittest

from builders import build_ticker_context as builder


def context() -> dict:
    return {"ticker": "HPG", "data_quality": {"warnings": [], "missing_sections": []}, "provenance": []}


def producer_contract(status: str = "available") -> dict:
    return {
        "status": status,
        "company_profile": {"status": "available", "sources": [{
            "source_name": "VCI", "snapshot_date": "2026-07-22T00:00:00+00:00",
            "record": {"qualified_fields": {"sector": "Steel"}, "provenance": {"provider": "VCI"}},
        }, {
            "source_name": "KBS", "snapshot_date": "2026-07-21T00:00:00+00:00",
            "record": {"qualified_fields": {"business_model": "Industrial"}, "provenance": {"provider": "KBS"}},
        }]},
        "company_subsidiaries": {"status": "available", "sources": [{
            "source_name": "VCI", "snapshot_date": "2026-07-22T00:00:00+00:00", "records": [],
        }]},
        "ownership_structure": {"status": "available", "sources": [{
            "source_name": "KBS", "snapshot_date": "2026-07-22T00:00:00+00:00", "records": [],
        }]},
        "major_shareholders": {"status": "available", "sources": [{
            "source_name": "VCI", "snapshot_date": "2026-06-30", "records": [],
            "delta": {"status": "incomparable", "reason": "no_prior_comparable_snapshot", "changes": []},
        }]},
        "corporate_events": {"status": "partial", "coverage_status": "partial_unqualified_50_row_cap", "sources": [{
            "source_name": "VCI", "records": [{"provider_event_id": "event-1", "fields": {"record_date": None, "value_per_share": 0}, "provenance": {"provider": "VCI"}}],
        }]},
    }


class CorporateIntelligenceConsumerTests(unittest.TestCase):
    def test_available_contract_preserves_sources_provenance_and_snapshot_dates(self):
        bundle = {"tickers": {"HPG": {"corporate_intelligence": producer_contract()}}}
        result = builder.apply_bundle_corporate_intelligence_contract(context(), bundle)
        corporate = result["corporate_intelligence"]
        self.assertEqual(corporate["status"], "available")
        self.assertEqual([source["source_name"] for source in corporate["company_profile"]["sources"]], ["VCI", "KBS"])
        self.assertEqual(corporate["company_profile"]["sources"][0]["record"]["provenance"]["provider"], "VCI")
        self.assertEqual(corporate["ownership_structure"]["sources"][0]["snapshot_date"], "2026-07-22T00:00:00+00:00")
        self.assertEqual(corporate["major_shareholders"]["sources"][0]["delta"]["status"], "incomparable")

    def test_missing_legacy_bundle_is_explicit_and_backward_compatible(self):
        result = builder.apply_bundle_corporate_intelligence_contract(context(), {"tickers": {"HPG": {}}})
        self.assertEqual(result["corporate_intelligence"], {
            "status": "missing", "reason": "corporate_intelligence_not_in_bundle", "sources": [],
        })

    def test_partial_contract_is_preserved_without_filling_missing_sources(self):
        payload = producer_contract("partial")
        payload["company_subsidiaries"] = {"status": "missing", "reason": "snapshot_tables_unavailable", "sources": []}
        result = builder.apply_bundle_corporate_intelligence_contract(context(), {"tickers": {"HPG": {"corporate_intelligence": payload}}})
        corporate = result["corporate_intelligence"]
        self.assertEqual(corporate["status"], "partial")
        self.assertEqual(corporate["company_subsidiaries"]["status"], "missing")
        self.assertEqual(corporate["company_subsidiaries"]["sources"], [])

    def test_malformed_contract_is_rejected_deterministically(self):
        result = builder.apply_bundle_corporate_intelligence_contract(
            context(), {"tickers": {"HPG": {"corporate_intelligence": {"status": "available"}}}},
        )
        self.assertEqual(result["corporate_intelligence"]["status"], "malformed")
        self.assertEqual(result["corporate_intelligence"]["reason"], "corporate_intelligence_section_invalid")
        self.assertEqual(result["corporate_intelligence"]["invalid_sections"], list(builder.CORPORATE_INTELLIGENCE_SECTIONS))
        invalid_status = builder.corporate_intelligence_contract(
            {"tickers": {"HPG": {"corporate_intelligence": {"status": []}}}}, "HPG",
        )
        self.assertEqual(invalid_status["status"], "malformed")
        self.assertEqual(invalid_status["reason"], "corporate_intelligence_status_invalid")

    def test_consumer_does_not_mutate_or_merge_producer_payload(self):
        payload = producer_contract()
        original = copy.deepcopy(payload)
        result = builder.apply_bundle_corporate_intelligence_contract(context(), {"tickers": {"HPG": {"corporate_intelligence": payload}}})
        result["corporate_intelligence"]["company_profile"]["sources"][0]["record"]["qualified_fields"]["sector"] = "Changed"
        self.assertEqual(payload, original)
        self.assertNotIn("business_model", result["corporate_intelligence"]["company_profile"]["sources"][0]["record"]["qualified_fields"])


if __name__ == "__main__":
    unittest.main()
