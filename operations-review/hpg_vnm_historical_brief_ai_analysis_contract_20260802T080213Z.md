# HPG/VNM historical fundamental brief AI analysis contract

Producer baseline: `58c0fc5`. Consumer baseline: `9b285e7`.

The single-ticker AI template now explicitly consumes the final-context
`historical_fundamental_brief` as a Historical FY2024 Fundamental Brief. It preserves the
six canonical categories, historical metadata, and provenance references; it forbids
recalculation, fact/inference merging, unsupported hypotheses, and market-dependent claims.

Frozen-time `2026-08-02T00:00:00Z` shadow flow (Producer bundle, Consumer load, final
ticker context, final prompt rendering) verified HPG and VNM source briefs equal their
context briefs exactly. Both had all six categories and zero hypotheses. Prompt rendering
was deterministic. No external LLM was called.

The final contexts remained current-market untrusted; their analysis readiness was unknown.
Production analysis bundle, manifest, focus extract, and database hashes were unchanged.

Focused Consumer test: `tests.test_historical_fundamental_brief_ai_analysis_contract`
(4 passing).
