import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_legacy(self):self.assertEqual(b.scenario_analysis_contract({"tickers":{"A":{}}},"A")["status"],"unknown")
 def test_preserves_categories(self):
  x={"state":"unknown","scenarios":{"base":{"state":"unknown"}},"evidence_inventory":{"facts":[],"inferences":[],"hypotheses":[]},"data_warnings":[],"unknowns":["x"]};self.assertEqual(b.scenario_analysis_contract({"tickers":{"A":{"scenario_analysis":x}}},"A")["unknowns"],["x"])
if __name__=="__main__":unittest.main()
