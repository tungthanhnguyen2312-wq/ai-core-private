# Prospective Research Attribution Contract V1

`builders/prospective_research_attribution.py` is a pure Consumer boundary that links one immutable research snapshot at T to one separately governed observation at a strictly later session. It does not write retained evidence, select an outcome, or change packet transport.

The research input requires a ticker, ISO research session, snapshot identity, source-artifact identity, `research_state`, non-empty evidence provenance, and authority limitations. A later observation requires its own identity and source identity, ticker/session, non-empty provenance, explicit basis and observed fields, plus bindings to the original snapshot and research source identities.

`research_at_t` and `what_was_observed_later` are copied independently into the output. The record statuses are `ATTRIBUTABLE`, `OUTCOME_PENDING`, `INPUT_UNQUALIFIED`, `IDENTITY_MISMATCH`, `TEMPORAL_VIOLATION`, `MALFORMED`, and `UNSUPPORTED_COMPARISON`. A missing outcome is therefore pending, not a failure.

An optional realized price change is emitted only when both inputs have explicit positive closes, explicitly qualified matching price bases, and no claimed PIT authority. Its formula is `(later_close - research_close) / research_close`; it is expressly an observed result, never an expected return, score, thesis verdict, scenario validation, backtest, recommendation, sizing input, or RAW_AS_TRADED/PIT promotion.

The cohort summary deduplicates only identical deterministic attribution identities, which prevents the same immutable record passed through direct and packet transports from being counted twice. It emits transparent counts, reason codes, and temporal violations only—no strategy ranking, win rate, or learning interpretation.
