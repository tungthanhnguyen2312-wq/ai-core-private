# AI Analysis Templates Based on Context Packages

## Global guardrails

Use only attached context packages and approved Project Knowledge. Before answering, inspect `data_quality.validation_status`, `missing_sections`, `warnings`, `not_fully_confirmed` and `provenance`. Never invent missing values, suppress conflicts, treat current snapshots as historical data, or provide guaranteed buy/sell recommendations.

## 1. Single-ticker analysis template

### Purpose

Produce a structured, evidence-based description of one ticker using a validated context package.

### Required input

One `{TICKER}_context.json`, AnalysisGuide, AIUsageRules, and a user-specified purpose/cutoff. `corporate_intelligence` is optional for backward-compatible older context packages.

### Prompt

```text
Analyze the attached ticker context package for {TICKER}.

First report package generated_at/latest dates, validation status, missing sections, warnings, not-fully-confirmed items, and whether the request is current, retrospective or backtest.

Then describe only supported sections: identity/current metadata; price and liquidity with recorded calculation method and explicit price/volume basis metadata (raw/adjusted/unknown); financial summary with unit/availability warnings; valuation inputs without unsupported calculations; technical snapshot without certain predictions; shareholder snapshot with no-history warning; and news only if safely mapped.

If `corporate_intelligence` is present, report its top-level status and separately report `company_profile`, `company_subsidiaries`, `ownership_structure`, `major_shareholders`, and `corporate_events`. Preserve each provider/source scope, source identity, provenance, raw relationship semantics, and snapshot date exactly as supplied. Do not merge KBS and VCI records, equate fields with different provider semantics, or derive a common ownership/relationship taxonomy. Corporate Events are forward observations with incomplete coverage, not complete history, lifecycle status, cancellation, completion, or future actionability; do not use them alone for an investment recommendation. For major-shareholder deltas, use a change only when its own status says it is comparable; retain `incomparable` and its reason as a data warning.

If `historical_fundamental_brief` is present, consume it only from this final context package and label it **Historical FY2024 Fundamental Brief**. Preserve its `facts`, `data_warnings`, `supported_inferences`, `hypotheses`, `missing_evidence`, and `invalidation_conditions` as six separate sections, with its period, publication timestamp, consolidated scope, currency, scale, `historical_only` state, and `provenance_references`. Do not recompute any metric, merge facts with supported inferences, invent management explanations/catalysts/forecasts, or turn warnings and missing evidence into signals. Keep `hypotheses` empty when the brief supplies an empty list. If the brief is missing, malformed, missing a category, or missing historical metadata, report it as unavailable and omit it rather than reconstructing it. Always retain warnings for unknown price basis, unknown volume basis, unqualified current shares, and unavailable current-market trust. Any additional interpretation is unsupported and must be omitted from the final output.

Place verified Price Basis and Volume Basis metadata (`raw` or `adjusted` with `price_basis_verified=true`) under Fact; place `unknown` price basis, unverified adjustment claims, missing basis metadata, and `volume_basis_verified=false` under Data Warnings/Unknown; put any carefully qualified interpretation under Inference. Do not mix raw and adjusted series or assume volume is adjusted when price is adjusted. Place source-recorded Corporate Intelligence values under Fact; place `missing`, `partial`, `malformed`, `incomparable`, absent provenance, and snapshot-date limitations under Data Warnings/Unknown; put any carefully qualified interpretation under Inference. Missing or malformed Corporate Intelligence is a data limitation, not negative evidence about the company. If an older context package has no `corporate_intelligence` section, state that it is unavailable and continue only with the other supported context sections.

Separate Fact, Derived, Inference and Unknown. Cite internal provenance near important values. End with data risks, alternative interpretations and information needed for higher confidence. Do not issue ranking, buy/sell/hold language, a recommendation, target price, valuation conclusion, market-cap or enterprise-value conclusion, adjusted-return claim, portfolio sizing, backtest claim, or current-market momentum/technical claim.

If `qualified_research_brief` is present, treat it as the authoritative compact research input. Render **Qualified Facts**, **Data Warnings / Limitations**, **Analysis / Inferences**, **Bear / Base / Bull**, **Key Risks**, **Catalysts / Conditions**, **Invalidation**, **Historical Research Conclusion**, and **What Cannot Yet Be Concluded** as separate sections. Do not recompute, omit blocked liquidity, convert `not_applicable` bank/corporate fields, or infer portfolio context. Its prohibited_claims list remains binding.

If `qualified_research_delta` is present, treat it as the sole authority for **What Changed Since Previous Qualified Snapshot**. State a change only when its `comparison_status` is `comparable` or `partially_comparable` and the Producer status is a change; never independently diff facts, quality, risks, scenarios, invalidations, portfolio gates, or conclusions. If comparison is `blocked`, `incomparable`, `not_comparable`, `unavailable`, or unchanged, report that boundary rather than a thesis change. Preserve the Producer's unchanged critical limitations, including blocked liquidity and portfolio context. A qualitative invalidation with `trigger_evaluation=unavailable` is not triggered. The existing prohibited claims remain binding.

If `ticker_capability_matrix` is present, treat every lane's Producer status, reason codes, dependencies, and descriptive-only marker as binding. Do not recompute or upgrade a capability: `descriptive_only` market observations are not generic price, valuation, liquidity, sizing, execution, or backtest evidence; `blocked` and `blocked_input` claims must be presented as unavailable boundaries; and `not_applicable` must not be described as missing or unknown. A matrix availability only permits discussion within that lane's stated authority and does not create a recommendation or current-market conclusion.
```

### Expected output

Scope/cutoff, validation gate, factual tables, Corporate Intelligence facts by source when available, data warnings/unknowns, cautious interpretation, missing/conflicts, provenance and limitations.

## 2. Two-ticker comparison template

### Purpose

Compare two packages on compatible fields without forcing a winner.

### Required input

Two context packages, compatible cutoff/period where possible, plus Project Knowledge.

### Prompt

```text
Compare {TICKER_A} and {TICKER_B} using only their attached context packages.

First create a compatibility check for generated_at, latest price date, financial period/type, unit status, missing sections and provenance. Do not compare a field when unit, period or definition is incompatible.

For compatible fields, compare current metadata, price coverage/liquidity/returns, financial coverage and reported values, valuation inputs already present, technical snapshots, shareholder availability and data readiness. Separate facts from inference. Do not rank expected returns, declare a winner or recommend buying/selling. State differences potentially caused by missing data, scale, timing or business-model differences.
```

### Expected output

Compatibility matrix, comparable facts, non-comparable items, balanced trade-offs, gaps and provenance.

## 3. Context-package screening template

### Purpose

Screen only the supplied package set under explicit criteria. This is not a full-market screen or investment ranking.

### Required input

Batch manifest, batch validation report, up to ten context packages, explicit screening type and thresholds.

### Prompt

```text
Screen only packages in {BATCH_MANIFEST}. Screen type: {fundamental|technical|data-readiness|risk}; criteria: {CRITERIA}.

Validation gate: missing values never pass a numeric criterion; use only recorded dates/periods; do not infer missing news/shareholders; do not compare financial amounts until unit compatibility is confirmed; preserve point-in-time and adjusted-price warnings.

Return a funnel: input, validation-eligible, each criterion and resulting count. For every included/excluded/unknown ticker, state the exact rule and source field. Use an unknown bucket when data is insufficient. This is a data filter, not a recommendation. Do not rank expected returns or say buy/sell.
```

### Expected output

Criteria manifest, validation funnel, pass/fail/unknown table, provenance and missing-data impact.

## Provenance / Source Basis

Templates implement Phase 2 AnalysisGuide/AIUsageRules, Phase 3 provenance/point-in-time standards, Phase 4 workflows and Phase 6 batch artifacts.

## Known Limitations

- Prompts cannot compensate for missing/stale context.
- Current batch lacks safely mapped ticker news; TCB, VIC and VRE also lack shareholder summaries.
- Model compliance/retrieval behavior is not fully confirmed across platforms.

## How AI Should Use This

Select one template, attach only required packages and keep the validation gate. If a package is sample, scaffold or invalid, do not analyze it as real data.
