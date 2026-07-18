# AI Analysis Templates Based on Context Packages

## Global guardrails

Use only attached context packages and approved Project Knowledge. Before answering, inspect `data_quality.validation_status`, `missing_sections`, `warnings`, `not_fully_confirmed` and `provenance`. Never invent missing values, suppress conflicts, treat current snapshots as historical data, or provide guaranteed buy/sell recommendations.

## 1. Single-ticker analysis template

### Purpose

Produce a structured, evidence-based description of one ticker using a validated context package.

### Required input

One `{TICKER}_context.json`, AnalysisGuide, AIUsageRules, and a user-specified purpose/cutoff.

### Prompt

```text
Analyze the attached ticker context package for {TICKER}.

First report package generated_at/latest dates, validation status, missing sections, warnings, not-fully-confirmed items, and whether the request is current, retrospective or backtest.

Then describe only supported sections: identity/current metadata; price and liquidity with recorded calculation method; financial summary with unit/availability warnings; valuation inputs without unsupported calculations; technical snapshot without certain predictions; shareholder snapshot with no-history warning; and news only if safely mapped.

Separate Fact, Derived, Inference and Unknown. Cite internal provenance near important values. End with data risks, alternative interpretations and information needed for higher confidence. Do not issue a buy/sell recommendation or price target.
```

### Expected output

Scope/cutoff, validation gate, factual tables, cautious interpretation, missing/conflicts, provenance and limitations.

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
