"""Import-wiring regression guard for the 7 simple builders whose generated_at now comes from
vn_time.vn_now_iso() (build_ticker_context.py has its own richer coverage in
test_vn_time_live_context.py, since it also has a frozen-clock branch to preserve).

Each of these builders is loaded the same way its own existing test suite loads it
(importlib.util.spec_from_file_location, no package __init__.py) -- exactly the mechanism that
would fail loudly if the sys.path bootstrap in front of `from vn_time import vn_now_iso` were
missing, so this also guards against a re-introduced ModuleNotFoundError regression.
"""
from __future__ import annotations

import importlib.util
import re
import unittest
from pathlib import Path

BUILDERS_DIR = Path(__file__).resolve().parent.parent / "builders"

MODULES = [
    "build_artifact_catalog",
    "build_batch_artifacts",
    "compare_batch_runs",
    "decide_rebuild",
    "freeze_v1_release",
    "run_final_qa",
    "validate_operating_pack",
]


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, BUILDERS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BuilderVnTimeWiringTests(unittest.TestCase):
    def test_each_builder_resolves_vn_now_iso_with_correct_offset(self):
        for name in MODULES:
            with self.subTest(module=name):
                module = _load(name)
                self.assertTrue(hasattr(module, "vn_now_iso"), f"{name} did not import vn_now_iso")
                self.assertRegex(module.vn_now_iso(), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+07:00$")

    def test_no_builder_still_contains_the_bare_astimezone_pattern(self):
        for name in MODULES:
            with self.subTest(module=name):
                source = (BUILDERS_DIR / f"{name}.py").read_text(encoding="utf-8")
                self.assertNotRegex(source, re.escape("astimezone()"))


if __name__ == "__main__":
    unittest.main()
