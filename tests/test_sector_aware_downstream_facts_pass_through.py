import copy,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from builders.build_ticker_context import attach_sector_aware_downstream_facts
class SectorAwarePassThroughTests(unittest.TestCase):
 def section(self,ticker='SSI',value=10):return {'contract_version':'1.0.0','section':'sector_aware_downstream_facts','facts':[{'ticker':ticker,'fact_identity':'brokerage_revenue','status':'available','value':value,'unit':'VND','period':{'period':'2024'},'statement_scope':'consolidated','canonical_input_ids':['r'],'official_document_source_type':'official_document_observation','document_sha256':'h','page_citations':['c'],'formula_applicability_version':'1.0.0','missing_input_or_inapplicability_reason':[]}]}
 def test_pass_through_is_verbatim_and_no_recomputation(self):
  c={'ticker':'SSI'};s=self.section(value=10);attach_sector_aware_downstream_facts(c,s);self.assertEqual(c['sector_aware_downstream_facts'],s);s['facts'][0]['value']=11;self.assertEqual(c['sector_aware_downstream_facts']['facts'][0]['value'],10)
 def test_legacy_absence_and_ticker_isolation(self):
  c={'ticker':'PAN','legacy':True};before=copy.deepcopy(c);attach_sector_aware_downstream_facts(c,None);self.assertEqual(c,before)
  with self.assertRaisesRegex(ValueError,'ticker_isolation'):attach_sector_aware_downstream_facts({'ticker':'PAN'},self.section('SSI'))
 def test_rejects_paths_and_invalid_contract(self):
  s=self.section();s['facts'][0]['source_path']='C:/x'
  with self.assertRaisesRegex(ValueError,'path_invalid'):attach_sector_aware_downstream_facts({'ticker':'SSI'},s)
  with self.assertRaisesRegex(ValueError,'contract_invalid'):attach_sector_aware_downstream_facts({'ticker':'SSI'},{})
if __name__=='__main__':unittest.main()
