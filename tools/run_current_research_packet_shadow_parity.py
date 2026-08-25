"""Generate the retained current_research_packet_shadow_parity/v1 artifact.

Runs a fully offline, deterministic replay: loads the retained Producer artifacts already
committed under stock-core-private/operations-review/ (no network acquisition, Producer
read-only), assembles a lightweight ticker_context per ticker in the official current
research universe (defaults to the retained packet's own 1,507 ticker keys), computes
market-wide packet-vs-legacy shadow parity, and writes one content-identified JSON
artifact under ai-core-private/operations-review/.

This tool performs no promotion, cutover, or default-path change -- it only produces
evidence. See builders/current_research_packet_shadow_parity.py for the classification
and aggregation logic this script merely drives and persists.

Usage (from the ai-core-private repository root):
    python tools/run_current_research_packet_shadow_parity.py [--out PATH] [--tickers T1,T2,...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_CONSUMER_ROOT = Path(__file__).resolve().parents[1]
if str(_CONSUMER_ROOT) not in sys.path:
    sys.path.insert(0, str(_CONSUMER_ROOT))

from builders.current_research_packet_shadow_parity import (  # noqa: E402
    build_market_wide_parity_report,
    load_market_wide_ticker_contexts_from_retained_artifacts,
    replay,
)

_DEFAULT_PRODUCER_ROOT = _CONSUMER_ROOT.parent / "stock-core-private"
_DEFAULT_OUT = (
    _CONSUMER_ROOT / "operations-review" / "current-research-packet-shadow-parity-v1-20260825"
    / "current_research_packet_shadow_parity_artifact.json"
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--producer-root", type=Path, default=_DEFAULT_PRODUCER_ROOT)
    parser.add_argument("--out", type=Path, default=_DEFAULT_OUT)
    parser.add_argument("--tickers", type=str, default=None, help="Comma-separated ticker subset (default: full retained universe).")
    args = parser.parse_args(argv)

    if not args.producer_root.is_dir():
        print(f"Producer checkout not found at {args.producer_root}", file=sys.stderr)
        return 2

    tickers = [t.strip() for t in args.tickers.split(",")] if args.tickers else None
    ticker_contexts = load_market_wide_ticker_contexts_from_retained_artifacts(args.producer_root, tickers=tickers)
    artifact = build_market_wide_parity_report(ticker_contexts)
    replay(artifact)  # self-verify before persisting

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    summary = {
        "artifact_identity": artifact["artifact_identity"],
        "denominator": artifact["denominator"],
        "packet_present_count": artifact["packet_present_count"],
        "legacy_present_count": artifact["legacy_present_count"],
        "malformed_context_count": artifact["malformed_context_count"],
        "totals": artifact["totals"],
        "unexplained_residual_count": artifact["unexplained_residual_count"],
        "overall_ticker_status_counts": artifact["overall_ticker_status_counts"],
        "component_breakdown": artifact["component_breakdown"],
        "promotion_readiness": artifact["promotion_readiness"],
        "written_to": str(args.out),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
