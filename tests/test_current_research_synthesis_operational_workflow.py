from __future__ import annotations
import copy,importlib.util,unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from builders.current_research_synthesis_operational_workflow import *
from builders.accepted_structured_synthesis_corpus import empty_accepted_structured_synthesis_corpus
spec=importlib.util.spec_from_file_location('fx',ROOT/'tests'/'test_current_research_claim_provenance_trace.py');assert spec and spec.loader
fx=importlib.util.module_from_spec(spec);spec.loader.exec_module(fx)
def pair(t='TRACE',r=None):c=fx._context();c['ticker']=t;x=copy.deepcopy(r or fx._response());x['ticker']=t;return c,x
class WorkflowTests(unittest.TestCase):
 def test_01_request_has_permitted_refs_and_prohibitions(self):
  c,_=pair();p=build_synthesis_request_package(c);self.assertIn('current_financial_momentum_context.components.revenue_growth',p['permitted_evidence_refs']);self.assertIn('target_price',p['prohibited_claims'])
 def test_02_request_deterministic(self):
  c,_=pair();self.assertEqual(build_synthesis_request_package(c)['request_identity'],build_synthesis_request_package(c)['request_identity'])
 def test_03_prepare_multi_ticker_order(self):
  a,_=pair('AAA');b,_=pair('BBB');s=prepare_synthesis_session([{'context':b},{'context':a}],session_label='s');self.assertEqual(['AAA','BBB'],[r['ticker'] for r in s['manifest']['requests']])
 def test_04_accept_ingests_to_corpus(self):
  c,r=pair();s=prepare_synthesis_session([{'context':c}],session_label='s');o=ingest_synthesis_session(s,{'TRACE':r},empty_accepted_structured_synthesis_corpus());self.assertEqual(1,o['ingestion_manifest']['accepted_count'])
 def test_05_unknown_ref_rejected(self):
  c,r=pair(r=fx._response(['unknown:evidence']));s=prepare_synthesis_session([{'context':c}],session_label='s');o=ingest_synthesis_session(s,{'TRACE':r},empty_accepted_structured_synthesis_corpus());self.assertEqual('REJECTED',o['ingestion_manifest']['response_results'][0]['disposition'])
 def test_06_prohibited_rejected(self):
  c,r=pair();r['thesis']='This is a BUY recommendation.';s=prepare_synthesis_session([{'context':c}],session_label='s');self.assertEqual(1,ingest_synthesis_session(s,{'TRACE':r},empty_accepted_structured_synthesis_corpus())['ingestion_manifest']['rejected_count'])
 def test_07_locality(self):
  a,ra=pair('AAA');b,rb=pair('BBB');rb['thesis']='This is a BUY recommendation.';s=prepare_synthesis_session([{'context':a},{'context':b}],session_label='s');o=ingest_synthesis_session(s,{'AAA':ra,'BBB':rb},empty_accepted_structured_synthesis_corpus());self.assertEqual((1,1),(o['ingestion_manifest']['accepted_count'],o['ingestion_manifest']['rejected_count']))
 def test_08_dossier_handoff(self):
  c,r=pair();s=prepare_synthesis_session([{'context':c}],session_label='s');self.assertEqual(1,len(ingest_synthesis_session(s,{'TRACE':r},empty_accepted_structured_synthesis_corpus())['ingestion_manifest']['dossier_batch_inputs']))
 def test_09_no_response_is_local(self):
  c,_=pair();s=prepare_synthesis_session([{'context':c}],session_label='s');self.assertEqual(1,ingest_synthesis_session(s,{},empty_accepted_structured_synthesis_corpus())['ingestion_manifest']['no_response_count'])
 def test_10_current_path_isolation(self):
  for p in (ROOT/'builders'/'build_ticker_context.py',ROOT/'builders'/'structured_research_synthesis_boundary.py'):self.assertNotIn('synthesis_operational_workflow',p.read_text(encoding='utf-8'))
