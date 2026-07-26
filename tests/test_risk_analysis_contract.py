import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_legacy(self):self.assertEqual(b.risk_analysis_contract({"tickers":{"A":{}}},"A")["status"],"unknown")
if __name__=="__main__":unittest.main()
