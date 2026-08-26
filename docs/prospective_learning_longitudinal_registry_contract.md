# Prospective Learning Longitudinal Registry V1

The longitudinal registry indexes validated learning-review product records by identities and minimal retrieval metadata. It retains research origin, later observation, attribution/review/product identities, reviewability, comparison status, authority limitations, and product reference; it does not duplicate full upstream artifacts.

Registration is append-only. Exact immutable logical-case duplicates are idempotent. A conflicting attribution/review identity for the same ticker, research snapshot, and later observation fails closed. A later observed record uses a new logical-case identity and links to prior pending registrations sharing the same research origin, leaving the pending record unchanged.

`query_registry` and `tools/query_prospective_learning_registry.py` provide exact-match retrieval only. The registry is not a current-research input and has no performance, scoring, prediction, recommendation, sizing, PIT, or RAW_AS_TRADED authority.
