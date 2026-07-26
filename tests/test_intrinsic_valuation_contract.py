import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_legacy(self):self.assertEqual(b.intrinsic_valuation_contract({"tickers":{"A":{}}},"A")["status"],"unknown")
 def test_pass(self):self.assertEqual(b.intrinsic_valuation_contract({"tickers":{"A":{"intrinsic_valuation":{"methods":{"fcff_dcf":{"state":"unavailable"}}}}}},"A")["status"],"unknown")
if __name__=="__main__":unittest.main()
