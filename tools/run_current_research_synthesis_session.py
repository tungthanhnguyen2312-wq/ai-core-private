"""Foreground provider-neutral request preparation and explicit response ingestion."""
from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from builders.current_research_synthesis_operational_workflow import prepare_synthesis_session,ingest_synthesis_session
from builders.accepted_structured_synthesis_corpus import empty_accepted_structured_synthesis_corpus,write_accepted_structured_synthesis_corpus
from builders.canonical_daily_producer_session_ingestion import load_canonical_daily_producer_session
def main():
 p=argparse.ArgumentParser();sub=p.add_subparsers(dest='mode',required=True);a=sub.add_parser('prepare');source=a.add_mutually_exclusive_group(required=True);source.add_argument('--input-manifest',type=Path);source.add_argument('--producer-session-manifest',type=Path);a.add_argument('--session',help='Required with --producer-session-manifest.');a.add_argument('--output-dir',required=True,type=Path);a.add_argument('--session-label',required=True);b=sub.add_parser('ingest');b.add_argument('--prepared-session',required=True,type=Path);b.add_argument('--contexts-manifest',required=True,type=Path);b.add_argument('--responses-manifest',required=True,type=Path);b.add_argument('--output-dir',required=True,type=Path);args=p.parse_args()
 if args.mode=='prepare':
  if args.producer_session_manifest:
   if not args.session:p.error('--session is required with --producer-session-manifest')
   loaded=load_canonical_daily_producer_session(args.producer_session_manifest,session=args.session);items=[{'context':context} for _,context in sorted(loaded['ticker_contexts'].items())]
  else:
   m=json.loads(args.input_manifest.read_text(encoding='utf-8'));items=[{'context':json.loads((args.input_manifest.parent/r['context_path']).read_text(encoding='utf-8'))} for r in m['records']]
  x=prepare_synthesis_session(items,session_label=args.session_label);args.output_dir.mkdir(parents=True,exist_ok=True);(args.output_dir/'synthesis_session_manifest.json').write_text(json.dumps(x['manifest'],sort_keys=True,indent=2)+'\n',encoding='utf-8');[(args.output_dir/f"{r['ticker']}_synthesis_request.json").write_text(json.dumps(r,sort_keys=True,indent=2)+'\n',encoding='utf-8') for r in x['manifest']['requests']];print(json.dumps({'session_identity':x['manifest']['session_identity'],'request_count':x['manifest']['denominator']},sort_keys=True));return
 manifest=json.loads(args.prepared_session.read_text(encoding='utf-8'));contexts=json.loads(args.contexts_manifest.read_text(encoding='utf-8'));responses=json.loads(args.responses_manifest.read_text(encoding='utf-8'));x=ingest_synthesis_session({'manifest':manifest,'contexts_by_ticker':contexts},responses,empty_accepted_structured_synthesis_corpus());args.output_dir.mkdir(parents=True,exist_ok=True);write_accepted_structured_synthesis_corpus(args.output_dir,x['corpus']);(args.output_dir/'response_ingestion_manifest.json').write_text(json.dumps(x['ingestion_manifest'],sort_keys=True,indent=2)+'\n',encoding='utf-8');print(json.dumps(x['ingestion_manifest'],sort_keys=True))
if __name__=='__main__':main()
