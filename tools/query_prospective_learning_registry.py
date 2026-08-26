"""Read-only exact-match query helper for a longitudinal learning registry JSON file."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from builders.prospective_learning_longitudinal_registry import query_registry


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("registry", type=Path)
    for name in ("ticker", "research-session", "outcome-session", "research-snapshot-identity", "attribution-identity", "learning-review-identity", "review-product-identity", "reviewability-status"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    raw = json.loads(args.registry.read_text(encoding="utf-8"))
    filters = {key.replace("-", "_"): value for key, value in vars(args).items() if key != "registry" and value is not None}
    print(json.dumps(query_registry(raw, **filters), ensure_ascii=True, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
