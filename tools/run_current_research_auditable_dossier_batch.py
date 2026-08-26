"""Foreground batch materialization for explicit current-research dossier inputs."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from builders.current_research_dossier_batch_catalog import build_dossier_batch_catalog, load_batch_manifest, write_dossier_batch_output
def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--input-manifest", required=True, type=Path); parser.add_argument("--output-dir", required=True, type=Path); parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args(); manifest = load_batch_manifest(args.input_manifest)
    for record in manifest["records"]:
        for field, target in (("context_path", "context"), ("synthesis_path", "synthesis"), ("claim_evidence_map_path", "claim_evidence_map")):
            if field in record:
                path = Path(record[field])
                if not path.exists(): record[target] = None; record["missing_" + target] = str(path)
                else: record[target] = json.loads(path.read_text(encoding="utf-8"))
    result = build_dossier_batch_catalog(manifest); outputs = write_dossier_batch_output(args.output_dir, result, preflight_only=args.preflight_only)
    catalog = result["catalog"]; print(json.dumps({"catalog_identity": catalog["catalog_identity"], "denominator": catalog["denominator"], "status_counts": catalog["status_counts"], "outputs": {name: path.as_posix() for name, path in outputs.items()}}, sort_keys=True))
if __name__ == "__main__": main()
