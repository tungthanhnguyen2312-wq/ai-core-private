import unittest
from builders import build_ticker_context as builder
class FinancialCanonicalContractTests(unittest.TestCase):
    def test_legacy_missing_and_unavailable_are_explicit(self): self.assertEqual(builder.financial_canonical_contract({'tickers':{'AAA':{}}},'AAA')['status'],'missing')
    def test_provenance_and_incomparable_are_preserved(self):
        b={'tickers':{'AAA':{'financial_canonical':{'status':'available','records':[{'canonical_metric':'revenue','value':0,'quality_state':'available','source_field':'revenue'},{'canonical_metric':'net_income','value':None,'quality_state':'incomparable','reason':'conflict'}]}}}}
        r=builder.financial_canonical_contract(b,'AAA'); self.assertEqual(r['records'][0]['value'],0); self.assertIsNone(r['records'][1]['value']); self.assertTrue(r['warnings'])
if __name__=='__main__': unittest.main()
