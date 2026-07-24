# Context coverage

## Purpose

Context coverage measures whether metrics are usable for a declared analysis purpose. It is a data-readiness result, not an investment score or recommendation. Phase 7 replaces “the section object exists” checks with deterministic metric-status coverage.

## Status classification

| Class | Statuses | Coverage behavior |
|---|---|---|
| Available | `reported`, `derived` | Weight 1.0. Derived metrics retain formula/inputs in `metric_inventory`. |
| Profile-dependent | `proxy` | Allowed, down-weighted, or rejected using `allow_proxy` and `proxy_weight`. |
| Profile-dependent | `stale` | Accepted/down-weighted or rejected using `allow_stale` and `stale_weight`; always listed in `stale_metrics`. |
| Missing | `source_empty`, `mapping_missing`, `insufficient_periods`, `parse_failed`, `not_queried`, `network_failed`, `unsupported`, `derivation_not_implemented`, `unit_unknown`, `period_basis_unknown` | Weight 0. A required profile may block the status; optional metrics remain non-blocking. |
| Excluded | `not_applicable` | Removed from the denominator and never fails validation by itself. |

For metadata, price, financial core and technical fields that predate parallel metric metadata, the extractor creates a canonical status from the actual non-null value. It does not mark an empty object usable merely because its key exists.

## Sections

The centralized registry in `validation/context_validation_profiles.json` defines unique metrics for:

- `metadata`
- `price`
- `financial_core`
- `financial_advanced`
- `cash_flow`
- `news`
- `shareholders`
- `technical`
- `macro`

Each `section.metric` key is counted once. `operating_cash_flow` belongs to `cash_flow`, not also to `financial_advanced`.

## Formula

For a section:

```text
coverage = sum(profile metric weights) / applicable metric count
```

`not_applicable` metrics are not applicable and are excluded. A section containing only not-applicable metrics returns `status=not_applicable`, `coverage=1.0`, and an expected count of zero, avoiding division by zero.

`available_metrics` is the number with positive weight. `weighted_available_metrics` preserves proxy/stale down-weighting. Missing entries include metric, status and source reason.

Overall coverage uses only the profile's required sections. Optional sections are still fully reported and contribute to `non_blocking_missing`, but cannot silently lower the purpose-specific denominator.

## Output

The JSON report includes:

- schema and required-section validity;
- `profile_valid` and explicit `valid_semantics`;
- minimum section/overall coverage results;
- section coverage;
- blocking and non-blocking missing;
- stale, proxy, derived, and not-applicable metrics;
- source/mapping reasons and the canonical metric inventory.

The Markdown report presents the same decision fields and section table for human review.

## Universe aggregation

`builders/context_coverage.py::aggregate_universe()` returns one row per canonical metric with:

`metric, available, derived, proxy, missing, stale, not_applicable, coverage_pct`

The command below reads saved context packages only; it does not call VNSTOCK APIs:

```powershell
Set-Location <consumer-repository>
python builders/build_context_coverage_universe.py --profile current_snapshot --dry-run
python builders/build_context_coverage_universe.py --profile current_snapshot --no-dry-run
```

The write command creates `reports/context_coverage_universe.json` and `.csv`, refusing to overwrite existing files.

## PAN example

PAN has usable metadata, price, core financials, technical indicators, derived EBIT/SG&A, reported interest expense/retained earnings, and reported OCF selected from the latest non-null `2025-Q4` YTD observation. EBITDA remains `insufficient_periods` and `2026-Q1` depreciation is `stale` rather than silently falling back. Company-specific news is `source_empty`; shareholders are `not_queried`. These gaps do not fail `current_snapshot` or `technical_analysis`, while valuation/forensic profiles correctly remain stricter.
