# Operator Checklist

## Before upload

- [ ] Use only the platform upload manifest.
- [ ] Do not upload the dashboard runtime selected by `STOCK_LOOKUP_RUNTIME_ROOT`, SQLite, raw OHLCV or `data_bctc/`.
- [ ] Confirm files contain no sensitive personal notes or portfolio data.
- [ ] Confirm final QA release gate is PASS.
- [ ] Confirm the immutable Producer handoff JSON parses, its manifest lineage is present, and provenance is present. A context package is manual fallback only.

## Before each task

- [ ] Select single-ticker, comparison or screening workflow.
- [ ] Attach only the required Producer handoff and explicitly referenced deterministic artifacts.
- [ ] Check current manifest/validation/staleness/rebuild decision.
- [ ] Verify `missing_sections`, strict/non-strict status and latest dates.
- [ ] State current, retrospective or backtest mode.

## Review the answer

- [ ] Data cutoff and internal source references are shown.
- [ ] Fact/Derived/Inference/Unknown are separated.
- [ ] Missing and uncertainty are not hidden.
- [ ] No unsupported news, unit conversion or historical snapshot use.
- [ ] No guaranteed recommendation, price target or return promise.

## Known Limitations

Checklist completion does not prove market-data accuracy or model compliance.

## How AI Should Use This

The AI should mirror the checklist in its validation preamble. The human operator makes the final acceptance decision.
