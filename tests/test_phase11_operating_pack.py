"""Phase 11 operating pack validation tests."""

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


operating = load_module("phase11_operating", ROOT / "builders" / "validate_operating_pack.py")


class OperatingPackTests(unittest.TestCase):
    def test_operating_pack_passes(self):
        report = operating.validate_pack()
        self.assertEqual(report["status"], "pass", report["issues"])
        self.assertEqual(len(report["platforms"]), 3)
        self.assertFalse(report["external_upload_performed"])
        self.assertFalse(report["model_call_performed"])

    def test_output_guard(self):
        with tempfile.TemporaryDirectory() as temporary:
            approved = Path(temporary).resolve()
            inside = approved / "report.json"
            outside = approved.parent / "outside.json"
            with patch.object(operating, "OUTPUT_ROOT", approved):
                self.assertEqual(operating.safe_output(inside), inside)
                with self.assertRaises(ValueError):
                    operating.safe_output(outside)
                inside.write_text("{}", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    operating.safe_output(inside)


if __name__ == "__main__":
    unittest.main()
