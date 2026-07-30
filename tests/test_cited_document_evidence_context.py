import copy,unittest
from builders.cited_document_evidence import attach
class EvidenceContextTests(unittest.TestCase):
 def context(self,ticker='HPG'):return {'ticker':ticker}
 def result(self,ticker='HPG'):
  return {'state':'available','reason':None,'results':[{'ticker':ticker,'document_id':'doc','document_sha256':'hash','chunk_id':'chunk','page':7,'section':'page_7','published_at':'2025-01-01','observed_at':'2025-01-02','text':'never leak','citations':[{'citation_id':'cite'}]}]}
 def test_passes_citation_metadata_without_text(self):
  x=attach(self.context(),{'ticker':'HPG','period':'2024','metric':'net_sales'},self.result())['cited_document_evidence'];self.assertEqual(x['results'][0]['citation_ids'],['cite']);self.assertNotIn('text',x['results'][0])
 def test_isolation_unsupported_and_no_passage(self):
  self.assertEqual(attach(self.context('VNM'),{'ticker':'HPG'},self.result())['cited_document_evidence']['reason'],'unsupported_query')
  x=attach(self.context(),{'ticker':'HPG'}, {'state':'available','results':[]})['cited_document_evidence'];self.assertEqual(x['reason'],'no_source_supported_passage')
  self.assertEqual(attach(self.context(),{'ticker':'HPG'}, {'state':'unavailable','reason':'missing_document'})['cited_document_evidence']['reason'],'missing_document')
 def test_order_and_legacy_are_deterministic(self):
  r=self.result();r['results']=[{**r['results'][0],'chunk_id':'z'},{**r['results'][0],'chunk_id':'a'}];a=attach(self.context(),{'ticker':'HPG'},r);b=attach(self.context(),{'ticker':'HPG'},r);self.assertEqual(a,b);self.assertEqual([x['chunk_id'] for x in a['cited_document_evidence']['results']],['a','z'])
if __name__=='__main__':unittest.main()