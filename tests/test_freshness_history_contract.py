import unittest

from builders import build_ticker_context as builder


class FreshnessHistoryConsumerTests(unittest.TestCase):
    def test_legacy_bundle_is_explicitly_backward_compatible(self):
        result = builder.freshness_history_contract({"tickers": {"HPG": {}}}, "HPG")
        self.assertEqual(result["status"], "missing")

    def test_stale_envelope_remains_visible_and_not_actionable(self):
        bundle = {"tickers": {"HPG": {"freshness": {"daily_prices": {
            "generated_at": "2026-07-20T00:00:00+00:00", "as_of_date": "2026-07-20",
            "source": "screen_snapshot_live.csv", "freshness_status": "stale",
            "expected_update_frequency": "1d", "stale_reason": "source_age_5d_exceeds_1d_grace",
            "is_actionable": False,
        }}}}}
        result = builder.freshness_history_contract(bundle, "HPG")
        self.assertEqual(result["status"], "available")
        self.assertIn("daily_prices", result["unknowns"])
        self.assertTrue(result["data_warnings"])

    def test_malformed_status_fails_closed(self):
        result = builder.freshness_history_contract({"tickers": {"HPG": {"freshness": {"x": {"freshness_status": "fresh"}}}}}, "HPG")
        self.assertEqual(result["status"], "malformed")


if __name__ == "__main__":
    unittest.main()
