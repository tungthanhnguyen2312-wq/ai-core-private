# JSON Schema Dependency Evaluation

## Current state

The local Python environment does not include the `jsonschema` package. Phase 8–9 therefore uses `builders/validate_json_schema_subset.py`, supporting only the keywords needed by current contracts.

## Options

1. **Keep the subset validator:** zero dependency and predictable, but incomplete Draft 2020-12 coverage.
2. **Approve installation of `jsonschema`:** strongest standards support and diagnostics, but changes the environment and requires separate authorization/version pinning.
3. **Vendor a validator:** avoids runtime installation but adds substantial third-party code, licensing and maintenance risk; not recommended without a formal dependency process.

## Recommendation

Continue using the documented subset while schemas remain simple. Before adopting advanced keywords such as `$ref`, `oneOf`, conditional schemas or formats, request approval to install and pin the official `jsonschema` Python package. Do not vendor third-party code ad hoc.

## Provenance / Source Basis

The evaluation is based on the observed `ModuleNotFoundError` for `jsonschema` and current schema keyword usage. No package was downloaded or installed.

## Known Limitations

Package availability, licensing and supported versions were not researched online because network/source expansion was not approved.

## How AI Should Use This

Do not claim full JSON Schema compliance. Request explicit approval before dependency installation or vendoring.
