# Builder Contract

## Input

- `--ticker`: required; normalized to uppercase ASCII letters/digits, length 2–10.
- `--output`: optional new `.json` path inside AI ANALYZE, never inside forbidden directories or VNSTOCK.
- `--dry-run/--no-dry-run`: default from config is dry-run.
- `--strict/--no-strict`: strict rejects any missing context section.

## Output

The output follows `context_packages/ticker_context_template.json`. Phase 4 emits a skeleton: identity ticker, timestamps, explicit missing sections, warnings, validation status and provenance. It contains no real market/company numbers.

## Provenance bắt buộc

Source files, source dataset class, generated_at, transformation, assumptions and limitations. A context without provenance is invalid.

## Safety contract

- Import does not execute `main`.
- Default is dry-run.
- All inputs are lightweight AI ANALYZE artifacts.
- Output must resolve inside AI ANALYZE and outside configured forbidden directories.
- Output must end in `.json` and must not already exist.
- No VNSTOCK write, crawler, DB update or market pipeline call exists.

## Errors phải raise/report

Invalid ticker; missing/invalid JSON; missing required summary/template; unsafe/non-JSON/existing output; required context key missing; empty provenance; strict mode with missing sections.

## Provenance / Source Basis

Contract implements Phase 3 context spec, validation rules and provenance standard.

## Known Limitations

- Coverage remains unknown per ticker.
- Real price/financial/metadata/news/shareholder/technical adapters are TODO.
- Validation rules file is configured but full rule execution is TODO.
- Safe path policy is intentionally narrower than the general Phase 4 wording.

## How AI Should Use This

Treat generated Phase 4 output as scaffolding only. Do not send it as factual ticker context except to test structure/missing handling.
