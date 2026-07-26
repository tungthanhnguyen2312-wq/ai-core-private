import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_legacy_and_malformed_are_unknown(self):
  self.assertEqual(b.relative_valuation_contract({"tickers":{"A":{}}},"A")["status"],"unknown")
  self.assertEqual(b.relative_valuation_contract({"tickers":{"A":{"relative_valuation":{"methods":{"pe":{"state":"bad"}}}}}},"A")["status"],"unknown")
 def test_pass_through_never_promotes_inference(self):
  raw={"methods":{"pe":{"state":"available","is_actionable":False}}}
  value=b.relative_valuation_contract({"tickers":{"A":{"relative_valuation":raw}}},"A")
  self.assertIn("target price",value["inferences"][0])
if __name__=="__main__":unittest.main()
