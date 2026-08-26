# Prospective Learning Registry Rollforward V1

The rollforward composes validated learning-review products with the existing longitudinal registry. Inputs are explicit paths only: one registry and one or more products. It never scans for evidence, builds observations, or changes the input registry in place.

Products are processed in canonical product-identity/reference order. Exact duplicate registrations remain no-ops; a pending origin followed by a later observed product appends a linked registration; malformed or conflicting products are isolated and reported without corrupting eligible registrations.

Each run emits a deterministic manifest, registry JSON, and inventory Markdown. Output files are validated before writing and created atomically as new immutable output artifacts. The flow is operational indexing only—no current-decision feedback, scoring, performance, backtest, PIT, or RAW_AS_TRADED authority.
