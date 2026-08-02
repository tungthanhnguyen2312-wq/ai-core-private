# HPG/VNM historical fundamental brief AI-context integration

Producer baseline: `58c0fc5`. Consumer baseline: `fde0792`.

Consumer final ticker contexts preserve `historical_fundamental_brief` exactly, including
facts, data warnings, supported inferences, hypotheses, missing evidence, invalidation
conditions, FY2024 period, publication timestamp, consolidated scope, currency, scale,
historical-only flag, and provenance references.

The focused structural guard rejects a brief missing any required category or any of the
three mandatory market-data warnings. Valid briefs are deep-copied verbatim and receive
only Consumer provenance metadata; no metric, inference, or readiness recomputation occurs.

Frozen-time shadow export/load/context build at `2026-08-02T00:00:00Z` showed exact source
and context equality for HPG and VNM. Both contained all six categories, had empty
hypotheses, and retained `analysis_readiness.status=unknown`; bundle trust remained
`trusted_subset_untrusted`. Production artifact and database hashes were unchanged.

Focused Consumer test: `tests.test_fundamental_quality_contract` (10 passing).
