import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_verbatim(self):
  x={"ticker":"HPG","analysis_mode":"historical_only_qualified_data","historical_only":True,"is_actionable":False};c={"ticker":"HPG","provenance":[]};b.apply_bundle_qualified_research_brief_contract(c,{"tickers":{"HPG":{"qualified_research_brief":x}}});self.assertEqual(c["qualified_research_brief"],x);self.assertEqual(c["provenance"][-1]["source_dataset"],"qualified_research_brief")
