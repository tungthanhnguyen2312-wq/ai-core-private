# Context validation profiles

## Validation layers

Phase 7 reports three distinct decisions:

1. `valid`: backward-compatible structural validity. It means the legacy required keys, ticker and provenance checks passed. It is not purpose suitability.
2. `schema_valid`: the context passes the repository's documented dependency-free JSON Schema subset.
3. `profile_valid`: schema, blocking rules, required sections and minimum coverage all pass for `validation_profile`.

Consumers deciding whether a context is usable for an analysis purpose must use `profile_valid`, not `valid` or section presence alone.

## Profiles

All rules live in `validation/context_validation_profiles.json`, rather than being distributed across loaders.

### `current_snapshot`

Requires metadata, price and core financials. News, shareholders and EBITDA are non-blocking. Proxy/stale metrics may be accepted with reduced weight.

### `technical_analysis`

Requires price and technical coverage, including latest price, RSI and structure. EBITDA, SG&A and shareholders are not required. Stale metrics are rejected.

### `valuation`

Requires metadata, price, core financials, cash flow and some advanced coverage. OCF is explicitly blocking. At least one of EBIT or EBITDA must be usable. Proxy and stale metrics are rejected unless the profile config is changed deliberately.

### `forensic`

Requires core/advanced financials and cash flow. OCF, retained earnings, interest expense and depreciation are blocking quality metrics. Mapping gaps and stale values fail.

### `backtest`

Requires price and financial core plus point-in-time guards. It blocks a missing analysis cutoff, unconfirmed financial publication availability and unconfirmed corporate-action price adjustment. Current metadata and shareholder snapshots are not treated as historical observations.

## Blocking semantics

- A configured blocking metric with no usable profile weight is added to `blocking_missing`.
- `blocking_any_of` supports requirements such as “EBIT or EBITDA”.
- A missing status not listed in `allowed_missing_statuses` blocks when it occurs in a required section.
- Section or overall coverage below its configured minimum blocks.
- Missing optional metrics are listed in `non_blocking_missing` and do not change the exit code.
- `not_applicable` does not block and is excluded from coverage.

## CLI

Both ticker forms are supported:

```powershell
python builders/build_ticker_context.py PAN --validate-profile valuation --dry-run
python builders/build_ticker_context.py --ticker PAN --validate-profile current_snapshot --dry-run
```

To write explicit coverage artifacts while leaving the context build in dry-run:

```powershell
python builders/build_ticker_context.py PAN --validate-profile valuation --dry-run `
  --coverage-report-json reports/context_coverage_pan.json `
  --coverage-report-markdown reports/context_coverage_pan.md
```

Coverage outputs are restricted to `AI ANALYZE/reports`, use `.json`/`.md`, and refuse overwrite. Context `--dry-run` behavior is unchanged; explicit coverage output flags authorize only the named reports.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Structural/schema validation and the requested profile pass. Non-blocking missing is allowed. |
| 2 | Build, strict validation, schema, path, or serialization error. |
| 3 | Context/schema can be read, but the requested profile has blocking missing or insufficient coverage. |
| 4 | Unknown or invalid validation profile/configuration. |

When no profile is requested, the legacy dry-run and strict behavior remains unchanged.

## Backward compatibility and migration

- Context schema version is `1.4.0` for newly built packages.
- No existing context object or scalar is removed or replaced.
- `data_quality.validation_status` retains legacy structural semantics.
- Profile builds add `data_quality.validation_profile` and `profile_validation_status`.
- Existing batch `non_strict/strict` consumers continue to work.
- New consumers should migrate from `valid`/section presence to `schema_valid` plus `profile_valid`.

## PAN result interpretation

After the Phase 9 rebuild, PAN passes `current_snapshot` and `technical_analysis`. It still fails `valuation` because the profile rejects proxy free float and stale depreciation, and fails `forensic` because current-period depreciation is stale and EBITDA is `insufficient_periods`. This is an intentional purpose-policy result, not a snapshot migration failure. `backtest` continues to fail point-in-time guards because filing availability and adjustment confirmation are absent.
