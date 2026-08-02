# Consumer volume-basis fail-closed boundary

Date: 2026-08-02T13:10:30+07:00

## Finding

`normalize_price_basis_contract` treated an absent volume basis as `raw_shares_traded` and treated any value other than literal `false` as verified. A legacy or partial bundle could therefore acquire qualified volume semantics inside Consumer despite Producer retaining `unknown/unverified`.

## Change

- Volume is qualified only when the canonical value is `raw_shares_traded` or `adjusted_volume` and `volume_basis_verified is True`.
- Missing, invalid, unverified, and string-valued verification resolve to `unknown/false`.
- Consumer data quality now emits an explicit volume-basis warning and not-confirmed identity without changing readiness or lane eligibility.
- The legacy compatibility contract now documents the fail-closed behavior.

## Validation

- Focused Consumer tests: 14 passed across `test_price_basis_contract` and `test_analysis_readiness_contract`.
- One frozen HPG/VNM dry-run produced valid contexts without writes. Both retained explicit unverified price and volume warnings and `trusted_subset_untrusted`; no readiness promotion occurred.
- Production database and artifact hashes remained byte-identical to the recorded Producer validation.

No Producer source, Dashboard source, production artifact, external provider, ranking, valuation, recommendation, or publishing path was modified.
