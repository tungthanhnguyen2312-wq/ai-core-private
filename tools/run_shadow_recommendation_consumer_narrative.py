"""Validate retained Producer shadow recommendations through the Consumer offline."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.shadow_recommendation_consumer_narrative import validate_full_producer_artifact


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--producer-artifact", required=True, type=Path)
    parser.add_argument("--producer-head", required=True)
    parser.add_argument("--consumer-start-head", required=True)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    artifact = validate_full_producer_artifact(json.loads(args.producer_artifact.read_text(encoding="utf-8")), producer_head=args.producer_head, consumer_start_head=args.consumer_start_head)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"artifact_identity": artifact["artifact_identity"], "denominator": artifact["denominator"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
