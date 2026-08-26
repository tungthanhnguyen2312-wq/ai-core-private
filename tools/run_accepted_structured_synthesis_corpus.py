from __future__ import annotations
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from builders.accepted_structured_synthesis_corpus import empty_accepted_structured_synthesis_corpus,register_many,replay_accepted_structured_synthesis_corpus,write_accepted_structured_synthesis_corpus
def main():
 p=argparse.ArgumentParser();p.add_argument('--input-manifest',required=True,type=Path);p.add_argument('--output-dir',required=True,type=Path);p.add_argument('--corpus',type=Path);a=p.parse_args();m=json.loads(a.input_manifest.read_text(encoding='utf-8'));inputs=[]
 for r in m.get('records',[]): inputs.append({'ticker':r.get('ticker'),'context':json.loads((a.input_manifest.parent/r['context_path']).read_text(encoding='utf-8')),'response':json.loads((a.input_manifest.parent/r['synthesis_path']).read_text(encoding='utf-8'))})
 corpus=json.loads(a.corpus.read_text(encoding='utf-8')) if a.corpus else empty_accepted_structured_synthesis_corpus();replay_accepted_structured_synthesis_corpus(corpus);result=register_many(corpus,inputs);paths=write_accepted_structured_synthesis_corpus(a.output_dir,result['corpus']);print(json.dumps({'corpus_identity':result['corpus']['corpus_identity'],'receipt':result['receipt'],'outputs':{k:v.as_posix() for k,v in paths.items()}},sort_keys=True))
if __name__=='__main__':main()
