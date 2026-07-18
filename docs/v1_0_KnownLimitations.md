# v1.0 Known Limitations

## Accepted data limitations

- Price adjustment for dividends, splits and other corporate actions is not fully confirmed.
- Financial-statement monetary unit/scale is not fully confirmed for every raw source/field.
- Financial reporting period is not the filing publication/availability date; strict point-in-time backtests are unsupported.
- News has no canonical ticker mapping; ticker-specific news sections remain missing.
- Shareholder data is point-in-time/no-history and is missing for some test tickers.
- Company metadata is a current snapshot and cannot be used as a historical dimension.

## Accepted technical limitations

- The dependency-free schema validator implements only the documented JSON Schema subset.
- Large source files use size/mtime fingerprints instead of full SHA-256.
- Artifact lineage is file/class-level, not record-level.
- Static read-only checks cannot prove the absence of every possible runtime side effect.
- Context returns use 21/63/252 observations rather than exact calendar matching.

## Operating limitations

- Context packages are descriptive data artifacts, not investment analyses.
- Strict validation currently fails where missing/not-fully-confirmed items remain; non-strict use must preserve warnings.
- No external AI platform has yet been tested with the operating pack.
- No crawler, pipeline or automatic market refresh is included in AI ANALYZE.

## Provenance / Source Basis

This list consolidates limitations recorded in Phase 1–10 metadata, knowledge, validation, context and QA artifacts.

## Known Limitations

The list may not capture unknown upstream-source defects. Any new evidence must be versioned rather than silently changing frozen v1.0 claims.

## How AI Should Use This

Keep relevant limitations adjacent to every analysis. Missing or unconfirmed information must never be guessed, imputed without an approved method or converted into a buy/sell recommendation.
