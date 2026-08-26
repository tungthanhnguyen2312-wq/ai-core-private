"""Foreground CLI for a deterministic current research dossier."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from builders.current_research_auditable_dossier import build_current_research_auditable_dossier, render_current_research_auditable_dossier_markdown
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True, type=Path); parser.add_argument("--response", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path); parser.add_argument("--claim-evidence-map", type=Path)
    parser.add_argument("--packet-consumption-mode", choices=("LEGACY_DIRECT", "PACKET_SHADOW"), default="LEGACY_DIRECT")
    args = parser.parse_args()
    claim_map = json.loads(args.claim_evidence_map.read_text(encoding="utf-8")) if args.claim_evidence_map else None
    dossier = build_current_research_auditable_dossier(json.loads(args.context.read_text(encoding="utf-8")), json.loads(args.response.read_text(encoding="utf-8")), claim_evidence_map=claim_map, packet_consumption_mode=args.packet_consumption_mode)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "current_research_auditable_dossier.json"; markdown_path = args.output_dir / "current_research_auditable_dossier.md"
    json_path.write_text(json.dumps(dossier, ensure_ascii=True, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_current_research_auditable_dossier_markdown(dossier), encoding="utf-8")
    print(json.dumps({"dossier_identity": dossier.get("dossier_identity"), "status": dossier["status"], "outputs": {"json": json_path.as_posix(), "markdown": markdown_path.as_posix()}}, sort_keys=True))
if __name__ == "__main__": main()
