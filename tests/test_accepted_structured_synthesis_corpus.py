from __future__ import annotations
import copy, importlib.util, json, tempfile, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from builders.accepted_structured_synthesis_corpus import *
from builders import accepted_structured_synthesis_corpus as corpus_module
from builders.current_research_dossier_batch_catalog import build_dossier_batch_catalog
spec=importlib.util.spec_from_file_location('fx',ROOT/'tests'/'test_current_research_claim_provenance_trace.py');assert spec and spec.loader
fx=importlib.util.module_from_spec(spec);spec.loader.exec_module(fx)
packet_spec=importlib.util.spec_from_file_location('packet_fx',ROOT/'tests'/'test_current_research_decision_packet_contract_pass_through.py');assert packet_spec and packet_spec.loader
packet_fx=importlib.util.module_from_spec(packet_spec);packet_spec.loader.exec_module(packet_fx)
def inp(t='TRACE',response=None):
 c=fx._context();c['ticker']=t;r=copy.deepcopy(response or fx._response());r['ticker']=t;return c,r
class CorpusTests(unittest.TestCase):
 def test_01_accepted_registers(self):
  c,r=inp();o=register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r);self.assertEqual('REGISTERED',o['status'])
 def test_02_rejected_cannot_register(self):
  c,r=inp(response=fx._response(['unknown:evidence']));self.assertEqual('REJECTED',register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r)['status'])
 def test_03_prohibited_cannot_register(self):
  c,r=inp();r['thesis']='This is a BUY recommendation.';self.assertEqual('REJECTED',register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r)['status'])
 def test_04_malformed_cannot_register(self):
  c,r=inp();del r['thesis'];self.assertEqual('REJECTED',register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r)['status'])
 def test_05_duplicate_idempotent(self):
  c,r=inp();a=register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r);b=register_accepted_structured_synthesis(a['corpus'],c,r);self.assertEqual('DUPLICATE_IDENTICAL',b['status']);self.assertEqual(a['corpus'],b['corpus'])
 def test_06_tampered_same_identity_conflicts(self):
  c,r=inp();a=register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r);bad=copy.deepcopy(a['corpus']);bad['records'][0]['accepted_response']['thesis']='tampered';bad['corpus_identity']=corpus_module._identity('accepted_structured_synthesis_corpus:',{k:v for k,v in bad.items() if k!='corpus_identity'});self.assertEqual('CONFLICT_FAIL_CLOSED',register_accepted_structured_synthesis(bad,c,r)['status'])
 def test_07_two_tickers(self):
  c,r=inp();c2,r2=inp('OTHER');o=register_many(empty_accepted_structured_synthesis_corpus(),[{'ticker':'TRACE','context':c,'response':r},{'ticker':'OTHER','context':c2,'response':r2}]);self.assertEqual(2,o['corpus']['summary']['unique_ticker_count'])
 def test_08_two_sessions_survive(self):
  c,r=inp();a=register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r);r2=copy.deepcopy(r);r2['analysis_session']='2026-08-26';b=register_accepted_structured_synthesis(a['corpus'],c,r2);self.assertEqual(2,len(b['corpus']['records']))
 def test_09_identity_deterministic(self):
  c,r=inp();self.assertEqual(register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r)['record']['accepted_synthesis_identity'],register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r)['record']['accepted_synthesis_identity'])
 def test_10_order_independent(self):
  c,r=inp();c2,r2=inp('OTHER');a=register_many(empty_accepted_structured_synthesis_corpus(),[{'context':c,'response':r},{'context':c2,'response':r2}]);b=register_many(empty_accepted_structured_synthesis_corpus(),[{'context':c2,'response':r2},{'context':c,'response':r}]);self.assertEqual(a['corpus']['corpus_identity'],b['corpus']['corpus_identity'])
 def test_11_query_ticker_session_identity(self):
  c,r=inp();o=register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r);cor=o['corpus'];rec=o['record'];self.assertEqual(1,len(query_accepted_structured_synthesis_corpus(cor,ticker='TRACE')));self.assertEqual(1,len(query_accepted_structured_synthesis_corpus(cor,research_session=r['analysis_session'])));self.assertEqual(1,len(query_accepted_structured_synthesis_corpus(cor,accepted_synthesis_identity=rec['accepted_synthesis_identity'])))
 def test_12_adapter_feeds_batch(self):
  c,r=inp();o=register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r);rows=corpus_to_dossier_batch_inputs(o['corpus'],{o['record']['source_context_identity']:c});self.assertEqual(1,build_dossier_batch_catalog({'records':rows})['catalog']['status_counts']['DOSSIER_READY'])
 def test_13_write_is_immutable(self):
  c,r=inp();o=register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r)
  with tempfile.TemporaryDirectory() as d: write_accepted_structured_synthesis_corpus(Path(d),o['corpus']);write_accepted_structured_synthesis_corpus(Path(d),o['corpus']);self.assertTrue((Path(d)/o['record']['retained_reference']).exists())
 def test_14_empty_is_valid(self): replay_accepted_structured_synthesis_corpus(empty_accepted_structured_synthesis_corpus())
 def test_15_inventory_no_fake_record(self): self.assertIn('No real retained accepted structured synthesis records',render_accepted_structured_synthesis_inventory(empty_accepted_structured_synthesis_corpus()))
 def test_16_packet_conflict_rejected(self):
  c,r=inp();c['current_financial_momentum_context']['source_artifact_identity']='current_financial_momentum_context:different';c['current_research_decision_packet']=copy.deepcopy(packet_fx._PACKET_RAW);self.assertEqual('REJECTED',register_accepted_structured_synthesis(empty_accepted_structured_synthesis_corpus(),c,r,packet_consumption_mode='PACKET_SHADOW')['status'])
 def test_17_current_paths_do_not_import_corpus(self):
  for p in (ROOT/'builders'/'build_ticker_context.py',ROOT/'builders'/'structured_research_synthesis_boundary.py',ROOT/'builders'/'current_research_auditable_dossier.py'):self.assertNotIn('accepted_structured_synthesis_corpus',p.read_text(encoding='utf-8'))
 def test_18_retained_real_corpus_is_empty_and_valid(self):
  c=json.loads((ROOT/'operations-review'/'accepted-structured-synthesis-corpus-v1-20260826'/'accepted_structured_synthesis_corpus.json').read_text(encoding='utf-8'));replay_accepted_structured_synthesis_corpus(c);self.assertEqual(0,c['summary']['registered_accepted_response_count'])
