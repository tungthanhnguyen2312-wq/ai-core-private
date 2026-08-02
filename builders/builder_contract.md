# Builder Contract

## Input

- `--ticker`: required; normalized to uppercase ASCII letters/digits, length 2–10.
- `--output`: optional new `.json` path inside AI ANALYZE, never inside forbidden directories or VNSTOCK.
- `--dry-run/--no-dry-run`: default from config is dry-run.
- `--strict/--no-strict`: strict rejects any missing context section.
- `--rotate-existing`: rename an existing export to `<name>_superseded_<UTC>.json` and keep it, then write the canonical name fresh. Off by default; the write-once rule below is unchanged either way.

## Output

The output follows `context_packages/ticker_context_template.json`. Phase 4 emits a skeleton: identity ticker, timestamps, explicit missing sections, warnings, validation status and provenance. It contains no real market/company numbers.

## Provenance bắt buộc

Source files, source dataset class, generated_at, transformation, assumptions and limitations. A context without provenance is invalid.

## Safety contract

- Import does not execute `main`.
- Default is dry-run.
- All inputs are lightweight AI ANALYZE artifacts.
- Output must resolve inside AI ANALYZE and outside configured forbidden directories.
- Output must end in `.json`. An existing export is never overwritten or deleted: without `--rotate-existing` the write is refused; with it, the previous export is renamed beside itself and kept.
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

## Exact-session bundle trust

`load_optional_analysis_bundle()` verifies that `bundle_manifest.json` proves association
with the exact export session that produced `analysis_bundle.json` — not merely that the
manifest is well-shaped. Producer contract `stocklookup-producer/2026.08.03`, proof schema
`1.1.0`, both pinned exactly. The full rule set and every rejection reason live in
`../stock-core-private/docs/exact_session_bundle_contract.md`.

`trusted_subset_validation` carries two independent axes:

- `integrity_state` — `exact_session_verified` | `unverified` | `legacy_unverified`, plus
  `proven_tickers` / `unproven_tickers`. Structural and cryptographic only.
- `basis_state` — `qualified` | `unqualified`. Price *and* volume basis verified only.

`state` remains the single pre-existing verdict and still requires both. Contracts gate on
the axis that applies: `analysis_readiness_contract` and `analysis_lane_eligibility_contract`
gate on integrity **per ticker**, and an unqualified basis forces `inferences_allowed = False`
with an explicit warning rather than suppressing the whole result.

A bundle with no manifest beside it is `legacy_untrusted` / `legacy_unverified`: readable,
never exact-session trusted.
