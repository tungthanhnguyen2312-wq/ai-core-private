# Consumer test status at the 2026-08-03 StockLookup production release

**Verdict: analysis-bundle production path validated; six batch-export tests remain outside
the active path.**

`python -m pytest tests` in `ai-core-private` reports **375 passed, 6 failed** (2026-08-03,
system Python 3.13). The Consumer repository is *not* clean, and this document exists so
that nobody reads "the release is validated" as "the Consumer is green".

## The six failures

| # | Test | Missing artifact |
|---|------|------------------|
| 1 | `test_phase11_operating_pack.py::OperatingPackTests::test_operating_pack_passes` | `exports/qa/final_qa_report_v2.json` |
| 2 | `test_phase7_batch.py::BatchArtifactTests::test_batch_dry_run` | `exports/context_packages/{VCB,MWG,TCB,MBB,VIC,VRE}_context.json` |
| 3 | `test_phase8_registry_schema.py::SchemaTests::test_real_auto_artifacts_match_schemas[batch_manifest_auto.json]` | `exports/context_packages/batch_manifest_auto.json` |
| 4 | `test_phase8_registry_schema.py::SchemaTests::test_real_auto_artifacts_match_schemas[batch_validation_report_auto.json]` | `exports/context_packages/batch_validation_report_auto.json` |
| 5 | `test_phase9_catalog_rebuild.py::RebuildDecisionTests::test_current_unchanged_batch_requires_no_rebuild` | `exports/context_packages/staleness_report.json` |
| 6 | `test_phase9_catalog_rebuild.py::CatalogTests::test_catalog_links_ten_contexts_and_schemas` | `exports/context_packages/batch_manifest_auto_v2.json` |

Every one of them is a `FileNotFoundError` (or, for #1, a manifest listing a file that does
not exist) for a **batch-export sidecar artifact** that the batch tooling produces. None of
them is an assertion about a wrong value, and none of them fails inside a module the
released analysis bundle touches.

## Why none of them is on the operating path

The one supported operator command is

```
stock-core-private/tools/operate_stocklookup.py --runtime-root <dashboard-runtime> --execute [--prepare-inputs] [--publish --web-root <served checkout> [--live]]
```

Its entire Consumer surface is two entry points:

* `builders/build_ticker_context.py --tickers <...> [--no-dry-run --rotate-existing | --dry-run]`
  — builds and smoke-checks the per-ticker context packages;
* `builders.build_ticker_context.load_optional_analysis_bundle` /
  `verify_exact_session_bundle` — the exact-session validation the release publisher and the
  operator both gate on.

`builders/build_ticker_context.py` imports none of `builders/batch_*`,
`builders/decide_rebuild.py`, `builders/build_artifact_catalog.py`,
`builders/validate_json_schema_subset.py`, or the operating-pack builder — verified by
import scan, not by inspection of names.

## Why none of them affects the published bundle

* The published release set is exactly `analysis_bundle.json`, `bundle_manifest.json`,
  `focus_extract.json`, `statement_taxonomy_sidecar.json`. None of the six missing
  artifacts is in that set, in `trusted_subset.required_artifacts`, or in
  `TRUSTED_ARTIFACT_NAMESPACE`.
* The bundle manifest's `files` list references exactly twelve Consumer context packages —
  `{POW, SSI, HPG, EVF, PAN, PNJ, FPT, QNS, VNM, PVD, NVL, VNINDEX}_context.json`. All
  twelve are present, and `export_ai_bundle.py --verify` re-hashed every one of them
  against the manifest during this release run and passed.
* The tickers whose context packages are missing (VCB, MWG, TCB, MBB, VIC, VRE) are not in
  the published universe, so no published entry depends on them.

## What would change this verdict

If a future release adds VCB/MWG/TCB/MBB/VIC/VRE to the published ticker set, failure #2
moves onto the operating path and must be fixed before that release ships. Rebuilding the
batch-export artifact set is a separate piece of work and was deliberately not started as
part of the production-release closeout.
