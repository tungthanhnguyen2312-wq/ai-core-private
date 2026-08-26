"""Foreground CLI for deterministic prospective-learning registry rollforward."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.prospective_learning_registry_rollforward import (
    load_registry_or_empty,
    rollforward_registry,
    write_rollforward_output,
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", required=True, type=Path)
    parser.add_argument("--product", required=True, action="append", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--create-if-missing", action="store_true")
    args = parser.parse_args()
    registry = load_registry_or_empty(args.registry, create_if_missing=args.create_if_missing)
    product_inputs = [{"reference": path.as_posix(), "product": json.loads(path.read_text(encoding="utf-8"))} for path in args.product]
    result = rollforward_registry(registry, product_inputs)
    if result["registry"] is None:
        raise SystemExit(json.dumps({"status": result["status"], "reason_codes": result["reason_codes"]}, sort_keys=True))
    outputs = write_rollforward_output(args.output_dir, result)
    print(json.dumps({"status": result["status"], "rollforward_identity": result["manifest"]["rollforward_identity"], "output_registry_identity": result["registry"]["registry_identity"], "outputs": {name: path.as_posix() for name, path in outputs.items()}}, sort_keys=True))


if __name__ == "__main__":
    main()
