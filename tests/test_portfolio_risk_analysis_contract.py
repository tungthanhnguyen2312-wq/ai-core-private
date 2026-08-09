import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_passes_through(self):
  x={"schema_version":"1","ticker":"HPG","analysis_mode":"historical_only_qualified_data","historical_only":True,"market_dependent":False,"is_actionable":False,"fundamental_risk":{},"liquidity":{},"portfolio_considerations":{},"allocation_eligibility":{}}
  c={"ticker":"HPG","provenance":[]};b.apply_bundle_portfolio_risk_analysis_contract(c,{"tickers":{"HPG":{"portfolio_risk_analysis":x}}});self.assertEqual(c["portfolio_risk_analysis"],x);self.assertEqual(c["provenance"][-1]["source_dataset"],"portfolio_risk_analysis")
if __name__=="__main__":unittest.main()
