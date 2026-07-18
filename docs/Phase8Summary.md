# Phase 8 Summary

## Completed work

- Added JSON Schema contracts for ticker contexts, automated manifests and validation reports.
- Added a dependency-free schema-subset validator because `jsonschema` is unavailable in the local environment.
- Added fixture-based tests independent of current VNSTOCK freshness.
- Added run comparison, registry and staleness reporting based on package/source fingerprints.
- Generated a second automated run and compared it with the Phase 7 baseline.

## Files created

- `validation/schemas/ticker_context.schema.json`
- `validation/schemas/batch_manifest.schema.json`
- `validation/schemas/batch_validation_report.schema.json`
- `builders/validate_json_schema_subset.py`
- `builders/compare_batch_runs.py`
- `tests/test_phase8_registry_schema.py`
- Four fixture JSON files under `tests/fixtures/`
- `exports/context_packages/batch_manifest_auto_v2.json`
- `exports/context_packages/batch_validation_report_auto_v2.json/.md`
- `exports/context_packages/run_registry.json`
- `exports/context_packages/staleness_report.json/.md`

## Test and comparison results

- Phase 7–8 tests: 14/14 passed.
- Current automated manifest/report conform to the implemented schema subset.
- Ten context packages were unchanged between the two automated runs.
- `stale_or_changed` is false.
- The SQLite fingerprint remains stat-only; small sources/packages use SHA-256.

## Safety

VNSTOCK remained read-only. No crawler, pipeline, API, database update or external model was used. Existing artifacts were not overwritten.

## Provenance / Source Basis

Phase 8 uses Phase 7 automated manifests, the existing ten context packages and read-only file fingerprints. Fixture tests use synthetic local JSON only.

## Known Limitations

- The validator supports only the documented subset of Draft 2020-12 keywords; it is not a complete JSON Schema implementation.
- Stat-only fingerprints are weaker than content hashes.
- A false `stale_or_changed` result does not prove upstream market data correctness.
- No new sources for corporate actions, filing dates or news mapping were investigated because that requires separate approval.

## How AI Should Use This

Use schema validation and staleness reports as admission controls before loading context packages. Keep stat-only and upstream-data limitations visible; never treat unchanged fingerprints as investment evidence.
