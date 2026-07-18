"""Phase 10 final QA runner tests."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


qa = load_module("phase10_qa", ROOT / "builders" / "run_final_qa.py")


class FinalQATests(unittest.TestCase):
    def test_safe_output_rejects_outside_and_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary:
            approved = Path(temporary).resolve()
            inside = approved / "report.json"
            outside = approved.parent / "outside.json"
            with patch.object(qa, "OUTPUT_ROOT", approved):
                self.assertEqual(qa.safe_output(inside), inside)
                with self.assertRaises(ValueError):
                    qa.safe_output(outside)
                inside.write_text("{}", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    qa.safe_output(inside)
                self.assertEqual(qa.safe_output(inside, allow_existing=True), inside)

if __name__ == "__main__":
    unittest.main()
