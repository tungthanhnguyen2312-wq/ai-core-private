# Operator Checklist

## Before upload

- [ ] Use only the platform upload manifest.
- [ ] Do not upload `../VNSTOCK`, SQLite, raw OHLCV or `data_bctc/`.
- [ ] Confirm files contain no sensitive personal notes or portfolio data.
- [ ] Confirm final QA release gate is PASS.
- [ ] Confirm context package JSON parses and provenance is present.

## Before each task

- [ ] Select single-ticker, comparison or screening workflow.
- [ ] Attach only required context packages.
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
