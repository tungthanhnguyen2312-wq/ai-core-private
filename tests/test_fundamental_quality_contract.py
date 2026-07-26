import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_legacy_unknown(self): self.assertEqual(b.fundamental_quality_contract({"tickers":{"A":{}}},"A")["status"],"unknown")
 def test_available(self):
  bundle={"tickers":{"A":{"fundamental_quality":{"models":{"p":{"result_state":"unavailable"}}}}}}
  self.assertEqual(b.fundamental_quality_contract(bundle,"A")["status"],"available")
if __name__=="__main__": unittest.main()
