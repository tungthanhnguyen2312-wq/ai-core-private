# HPG/VNM historical-only AI output validation

Producer baseline: `58c0fc5`. Consumer baseline: `f1835fe`.

Consumer previously had no response parser, acceptance, storage, or display path. The new
pure acceptance boundary is fail-closed: it accepts only a typed, complete, canonical-brief
equivalent response, never free-form text. It compares all six categories, historical
metadata, persistent market-data warnings, and provenance references against the final
context brief; extra readiness/lane fields and prohibited claims are rejected.

Frozen `2026-08-02T00:00:00Z` HPG/VNM shadow flow used deterministic local mock responses
only. For both tickers, the canonical JSON response was accepted unchanged and a response
with a current-momentum buy claim was rejected with no accepted output. Context readiness
remained unknown. No external LLM was called.

Production analysis bundle, manifest, focus extract, and database hashes were unchanged.
Focused test: `tests.test_historical_fundamental_brief_response` (5 passing).
