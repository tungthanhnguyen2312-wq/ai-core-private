"""Phase 7 safety and contract tests. No VNSTOCK writes or crawler calls."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load_module("phase7_builder", ROOT / "builders" / "build_ticker_context.py")
batch = load_module("phase7_batch", ROOT / "builders" / "build_batch_artifacts.py")


class BuilderUnitTests(unittest.TestCase):
    def test_normalize_and_deduplicate(self):
        self.assertEqual(builder.normalize_ticker_list([" hpg ", "FPT", "HPG"], 10), ["HPG", "FPT"])

    def test_reject_more_than_ten(self):
        with self.assertRaisesRegex(ValueError, "exceeds safe maximum"):
            builder.normalize_ticker_list([f"T{i:02d}" for i in range(11)], 10)

    def test_reject_invalid_ticker(self):
        with self.assertRaises(ValueError):
            builder.normalize_ticker("HPG;DROP")

    def test_builder_dry_run_and_strict(self):
        dry = subprocess.run(
            [sys.executable, str(ROOT / "builders" / "build_ticker_context.py"), "--ticker", "HPG", "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(dry.returncode, 0, dry.stderr)
        self.assertIn('"would_write": false', dry.stdout)
        strict = subprocess.run(
            [sys.executable, str(ROOT / "builders" / "build_ticker_context.py"), "--ticker", "HPG", "--strict", "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(strict.returncode, 2)
        self.assertIn("Strict mode rejects", strict.stderr)


class BatchArtifactTests(unittest.TestCase):
    def test_package_contract_validation(self):
        path = ROOT / "exports" / "context_packages" / "HPG_context.json"
        package = batch.load_json(path)
        result = batch.validate_package(path, package)
        self.assertEqual(result["non_strict"], "pass")
        self.assertEqual(result["strict"], "fail")
        self.assertEqual(result["provenance_status"], "present")

    def test_small_file_fingerprint_and_utf8(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "tiếng_việt.json"
            path.write_text('{"text":"Tiếng Việt"}\n', encoding="utf-8")
            fingerprint = batch.fingerprint_file(path)
            self.assertEqual(fingerprint["method"], "sha256")
            self.assertEqual(len(fingerprint["sha256"]), 64)

    def test_output_traversal_and_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            approved = Path(temporary).resolve()
            safe = approved / "new.json"
            outside = approved.parent / "outside.json"
            with patch.object(batch, "DEFAULT_PACKAGE_DIR", approved):
                self.assertEqual(batch.validate_output_path(safe), safe)
                with self.assertRaises(ValueError):
                    batch.validate_output_path(outside)
                safe.write_text("{}", encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    batch.save_json_new(safe, {"new": True})

    def test_batch_dry_run(self):
        tickers = "HPG,FPT,VCB,VNM,MWG,TCB,MBB,SSI,VIC,VRE"
        run = subprocess.run(
            [sys.executable, str(ROOT / "builders" / "build_batch_artifacts.py"), "--tickers", tickers, "--dry-run"],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", check=False,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        payload = json.loads(run.stdout)
        self.assertEqual(payload["package_count"], 10)
        self.assertEqual(payload["non_strict_pass"], 10)


if __name__ == "__main__":
    unittest.main()
