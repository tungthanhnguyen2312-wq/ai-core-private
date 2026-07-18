# Builder Test Plan

## Test matrix

| Case | Input | Expected |
|---|---|---|
| Valid ticker | `--ticker SAMPLE --dry-run` | Exit 0, normalized ticker, `would_write=false`. |
| Invalid ticker | empty/unsafe punctuation | Exit 2, no file. |
| Ticker not known | valid format but no enumerated coverage | Non-strict skeleton with coverage `unknown`; strict fails. |
| Wrong output path | path in `../VNSTOCK` or outside workspace | Exit 2, no write. |
| Forbidden AI folder | output inside metadata/builders/etc. | Exit 2. |
| Existing output | `--no-dry-run` targeting existing file | Refuse overwrite. |
| Missing summary | rename absent in isolated fixture/config | Descriptive missing-file error. |
| Invalid JSON | malformed fixture/config | Descriptive parse error. |
| Dry-run default | omit `--dry-run` | Exit 0 and no file. |
| Explicit write | `--no-dry-run` with new exports path | One valid UTF-8 JSON skeleton. |
| Strict mode | `--strict` | Fail because Phase 4 skeleton has missing sections. |
| Vietnamese UTF-8 | warnings/limitations with Vietnamese | Round-trip without mojibake. |
| Import safety | import module | No CLI execution or file write. |
| VNSTOCK protection | variants using relative traversal | Resolve and reject all paths inside VNSTOCK. |

## Test levels

Unit tests for functions; integration tests in temporary workspace fixtures; security tests for path traversal/symlink behavior; smoke test with real Phase 3 artifacts. Phase 4 performs only compile and dry-run smoke checks, not a full suite.

## Provenance / Source Basis

Based on `builder_contract.md`, Phase 3 validation rules and Phase 4 safety constraints.

## Known Limitations

- No automated test files are created in Phase 4.
- Windows case-insensitive/symlink edge cases need dedicated tests.
- Real adapters cannot be tested until separately approved.

## How AI Should Use This

Use as acceptance criteria for a later implementation phase. Do not mark unexecuted cases as passed.
