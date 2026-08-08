"""Live (non-frozen) generated_at path of build_ticker_context.py.

Companion to test_frozen_clock_context.py, which covers build_clock reproducibility mode and
is unchanged by this milestone. This file covers the opposite branch: no build_clock passed,
so generated_at must come from vn_time.vn_now_iso() -- and the frozen branch must never call it.
All data loaders are mocked (no production DB access), matching the existing harness.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from builders import build_ticker_context as builder  # noqa: E402

CLOCK_A = "2026-07-28T12:00:00Z"


def _build(build_clock=None):
    metadata = {"ticker": "AAA", "exchange": "HSX", "industry": "Utilities", "updated": "2026-07-28"}

    def select(_ticker, _db, selected, *_rest):
        return lambda: (copy.deepcopy(metadata), [])

    def news(_ticker, *, now=None):
        return ({"status": "no_company_specific_news", "cutoff": "live", "meta": {}, "coverage": {}}, [])

    patches = [
        mock.patch.object(builder, "check_ticker_coverage", return_value={}),
        mock.patch.object(builder, "_select_metadata_loader", side_effect=select),
        mock.patch.object(builder, "load_price_slice", return_value=({}, [])),
        mock.patch.object(builder, "load_financial_slice", return_value=({}, [])),
        mock.patch.object(builder, "load_news_slice", side_effect=news),
        mock.patch.object(builder, "load_shareholder_slice", return_value=({}, [])),
        mock.patch.object(builder, "load_technical_slice", return_value=({}, [])),
        mock.patch.object(builder, "load_share_reconciliation_slice", return_value=({}, [])),
        mock.patch.object(builder, "load_vnstock_entity_type", return_value="corporate"),
    ]
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], patches[8]:
        return builder.build_context_package("AAA", {"identity": {}}, {}, build_clock=build_clock)


class LiveGeneratedAtTests(unittest.TestCase):
    def test_no_build_clock_uses_vn_now_iso(self):
        with mock.patch.object(builder, "vn_now_iso", return_value="2026-08-08T16:00:00+07:00") as fake:
            context = _build(build_clock=None)
        fake.assert_called_once_with()
        self.assertEqual(context["generated_at"], "2026-08-08T16:00:00+07:00")

    def test_live_generated_at_is_vn_offset_and_host_independent(self):
        # Real (unmocked) vn_time call: confirm the actual wiring, not just the mock contract.
        context = _build(build_clock=None)
        self.assertRegex(context["generated_at"], r"\+07:00$")

    def test_frozen_clock_path_never_calls_vn_now_iso(self):
        """Semantic-preservation guard: the pre-existing reproducibility contract
        (test_frozen_clock_context.py) must still take the frozen branch exclusively."""
        with mock.patch.object(builder, "vn_now_iso", side_effect=AssertionError(
                "frozen build_clock path must not call vn_now_iso()")):
            context = _build(build_clock=CLOCK_A)
        self.assertEqual(context["generated_at"], "2026-07-28T12:00:00Z")


if __name__ == "__main__":
    unittest.main()
