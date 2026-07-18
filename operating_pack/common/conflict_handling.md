# Conflict and Missing-Data Handling

## Ordered procedure

1. Compare ticker, date/period, grain, unit, provider and reported/derived status.
2. Prefer raw/near-source evidence only when definitions and grain match.
3. Keep normalized processed values for standard use while preserving raw discrepancies.
4. Never average conflicting values or choose the more favorable number.
5. Mark unresolved differences as `unresolved_conflict` and stop dependent calculations.
6. Use an `unknown` bucket when screening criteria cannot be evaluated.

## Missing rules

- `-1` in documented fields means queried-no-value, not a negative economic value.
- Empty margin status means no flagged status under the project convention.
- Missing news/shareholder sections must not be inferred.
- A missing financial input blocks the dependent ratio.

## Known Limitations

The procedure cannot resolve semantic differences absent from source metadata.

## How AI Should Use This

Show conflicts and their provenance explicitly. Do not continue a dependent conclusion until compatibility is established.
