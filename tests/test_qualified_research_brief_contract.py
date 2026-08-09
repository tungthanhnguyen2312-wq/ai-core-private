import unittest
from builders import build_ticker_context as b
class T(unittest.TestCase):
 def test_verbatim(self):
  x={"ticker":"HPG","analysis_mode":"historical_only_qualified_data","historical_only":True,"is_actionable":False};c={"ticker":"HPG","provenance":[]};b.apply_bundle_qualified_research_brief_contract(c,{"tickers":{"HPG":{"qualified_research_brief":x}}});self.assertEqual(c["qualified_research_brief"],x);self.assertEqual(c["provenance"][-1]["source_dataset"],"qualified_research_brief")
 def test_delta_is_verbatim_and_never_recomputed(self):
  x={"ticker":"HPG","analysis_mode":"historical_only_qualified_data","historical_only":True,"is_actionable":False,"comparison_status":"comparable","material_change_summary":{"material_change_detected":True,"highest_priority_changes":[{"category":"fact","reference":"producer-only"}]}}
  c={"ticker":"HPG","provenance":[]};b.apply_bundle_qualified_research_delta_contract(c,{"tickers":{"HPG":{"qualified_research_delta":x}}})
  self.assertEqual(c["qualified_research_delta"],x);self.assertEqual(c["provenance"][-1]["source_dataset"],"qualified_research_delta")
 def test_malformed_delta_fails_closed(self):
  c={"ticker":"HPG","provenance":[]};b.apply_bundle_qualified_research_delta_contract(c,{"tickers":{"HPG":{"qualified_research_delta":{"ticker":"HPG"}}}})
  self.assertEqual(c["qualified_research_delta"]["status"],"malformed")

 def test_change_events_pass_through_and_malformed_fails_closed(self):
  x={"status":"events_available","events":[{"event_id":"qrc-x","provenance_references":["identity.eligibility"]}]};c={"ticker":"HPG","provenance":[]};b.apply_bundle_qualified_research_change_events_contract(c,{"tickers":{"HPG":{"qualified_research_change_events":x}}});self.assertEqual(c["qualified_research_change_events"],x)
  c={"ticker":"HPG","provenance":[]};b.apply_bundle_qualified_research_change_events_contract(c,{"tickers":{"HPG":{"qualified_research_change_events":{"events":[]}}}});self.assertEqual(c["qualified_research_change_events"]["status"],"malformed")
