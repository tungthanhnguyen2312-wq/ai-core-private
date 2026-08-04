# KBS trading-value coverage pass-through (Consumer)

Implemented by `builders/kbs_trading_value_coverage_contract.py`, contract version `1.0.0`.
Producer side: `stock-core-private/kbs_trading_value_export.py` (export block `1.0.0`).

## What this receives

A KBS trading-value figure means nothing without knowing how much of the interval it
covers. Producer decides that; this module carries the decision intact.

```
provider = KBS · source_field = va
trading_value_unit = VND · qualification = empirically_deduced
coverage: 20 fields, all required
warning_tokens + warnings
```

`coverage_state` ∈ `complete` · `partial_known` · `absent` · `conflicted` · `unknown`
`statistic_scope` ∈ `single_observed_row` · `complete_requested_window` ·
`observed_rows_only` · `not_applicable`

## The division of labour

Consumer **validates and forwards**. It does not classify, does not recompute a count, and
does not hold a copy of Producer's capability matrix.

That split is deliberate. A Consumer that re-derives coverage will eventually disagree with
Producer, and the disagreement surfaces as a number that looks fine. A Consumer that only
checks and forwards can be wrong in exactly one way — it can drop something — and
`REQUIRED_COVERAGE_FIELDS` catches that.

| Rule | Enforced by |
|---|---|
| Every coverage field survives loading | `normalize_trading_value_contract` raises on any missing field |
| Labels agree with counts | `assert_labels_agree_with_counts` — a corruption check on two values Producer already sent, not a re-derivation |
| Coverage may be narrowed, never widened | `assert_not_upgraded` (both `coverage_state` and `usable_count`) |
| Warnings cannot be dropped | `assert_warnings_preserved` |
| Warning text cannot drift | `assert_warnings_pinned` against the shared fixture fingerprint |
| Aggregate claims need complete coverage | `evaluate_aggregate_claim` |
| No block ⇒ `unknown`, never complete | `normalize_trading_value_contract(None)` |

## AI context

`ai_context_block` labels the value `kbs_provider_observed_trading_value` and sets
`is_official_market_turnover`, `is_qualified_liquidity_evidence`,
`supports_market_scope_claim` and `supports_actionability` to **false at every coverage
state**, including complete. Warnings are repeated from the pinned table; this module
composes no sentences of its own.

## Legacy bundles

`legacy_row_observation` — explicit row identity, so the value may be displayed as a
provider observation; aggregates refused.
`legacy_aggregate_without_coverage` — refused entirely.
`legacy_no_trading_value` — unaffected.

Absence of metadata resolves to `unknown`. A legacy bundle has not told us its coverage is
full; it has told us nothing.

## Current state

No Producer artifact carries this block today — Producer's trace found KBS `va` is dropped
by the upstream adapter and never reaches the bundle. The live path is therefore the legacy
one: no block, `unknown`, aggregates refused. This is the receiving half of a seam, in place
before the first value arrives.

## Compatibility

No schema version bumped on either side. The block is additive; a reader that has never seen
one is not broken by it, and treats KBS trading value as `unknown`.
