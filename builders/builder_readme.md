# Ticker Context Builder

## Mục đích

`build_ticker_context.py` đọc lát cắt VNSTOCK theo ticker ở chế độ read-only, tạo context package có missing/provenance và không thực hiện investment analysis.

## Lệnh mẫu

Dry-run mặc định:

```powershell
python builders/build_ticker_context.py --ticker HPG --dry-run
```

Tạo package mới trong `exports/context_packages/` (không ghi đè):

```powershell
python builders/build_ticker_context.py --ticker HPG --no-dry-run
```

Chỉ định output an toàn:

```powershell
python builders/build_ticker_context.py --ticker HPG --output exports/context_packages/HPG_context_v2.json --no-dry-run
```

Batch an toàn tối đa 10 ticker:

```powershell
python builders/build_ticker_context.py --tickers HPG,FPT,VCB,VNM,MWG,TCB,MBB,SSI,VIC,VRE --dry-run
```

Strict mode sẽ fail nếu còn missing hoặc not-fully-confirmed:

```powershell
python builders/build_ticker_context.py --ticker HPG --strict --dry-run
```

## Guard path

Script chỉ cho output `.json` trong `exports/context_packages/`, tuyệt đối không trong `../VNSTOCK`. File đã tồn tại sẽ không bị ghi đè; batch bị giới hạn tối đa 10 ticker.

## Provenance / Source Basis

Builder dùng config, Phase 3 summary/template, SQLite `mode=ro` và CSV streaming theo ticker. Không gọi API, crawler, pipeline hoặc VNSTOCK code.

## Known Limitations

- News chưa có canonical ticker mapping.
- Price adjustment, BCTC unit/scale và filing dates chưa fully confirmed.
- Full automated validation/report generator vẫn là TODO.
- `--strict` cố ý không pass khi package còn missing/uncertainty.

## How AI Should Use This

Dùng dry-run trước khi build. Khi đưa package cho AI, phải đọc validation status, warnings, missing sections và provenance; output không phải khuyến nghị đầu tư.

## Automated batch artifacts

Dry-run manifest, validation and fingerprint generation:

```powershell
python builders/build_batch_artifacts.py --tickers HPG,FPT,VCB,VNM,MWG,TCB,MBB,SSI,VIC,VRE --dry-run
```

Create new `_auto` artifacts without overwriting existing files:

```powershell
python builders/build_batch_artifacts.py --tickers HPG,FPT,VCB,VNM,MWG,TCB,MBB,SSI,VIC,VRE --no-dry-run
```

Small source files receive SHA-256 fingerprints; large files receive size/mtime fingerprints and an explicit warning.

## Schema and staleness checks

Validate an artifact with the dependency-free schema subset:

```powershell
python builders/validate_json_schema_subset.py --schema validation/schemas/ticker_context.schema.json --instance exports/context_packages/HPG_context.json
```

Compare two automated manifests in dry-run mode:

```powershell
python builders/compare_batch_runs.py --previous exports/context_packages/batch_manifest_auto.json --current exports/context_packages/batch_manifest_auto_v2.json --dry-run
```

The validator is intentionally a documented subset, not a full Draft 2020-12 engine. A stat-only unchanged source is weaker evidence than an unchanged SHA-256 hash.

## Artifact catalog and rebuild decision

Build a new catalog without overwriting an existing artifact:

```powershell
python builders/build_artifact_catalog.py --dry-run
```

Evaluate deterministic maintenance actions:

```powershell
python builders/decide_rebuild.py --dry-run
```

These commands manage artifact freshness and validation only. `no_rebuild` is not proof of upstream data correctness and is never an investment signal.

## Final QA

Run the v1.0 gate without writing reports:

```powershell
python builders/run_final_qa.py --dry-run
```

Create new QA reports under `exports/qa/`:

```powershell
python builders/run_final_qa.py --no-dry-run
```

The release gate requires zero Critical and High findings. QA success does not prove upstream market-data correctness.

## Operating pack validation

```powershell
python builders/validate_operating_pack.py --dry-run
```

This validates manifests, referenced paths, context limits and mandatory guardrails locally. It does not upload files or call a model.
