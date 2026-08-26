# Current Research Dossier Batch Catalog Contract

The batch catalog accepts an explicit manifest of ticker context and already-created structured-synthesis JSON inputs. It performs no directory discovery, latest-by-mtime selection, model call, or synthesis generation. Missing input remains an availability disposition.

Ready inputs are materialized by the existing dossier builder at `<output-root>/<ticker>/current_research_auditable_dossier.{json,md}`. The root catalog and inventory are deterministic and immutable-by-content. A bad ticker stays local; malformed batch manifests fail globally.

`DOSSIER_READY` is an operational presentation state only, never an investment recommendation, entry state, valuation approval, liquidity finding, or sizing authority. The batch is downstream-only and leaves `LEGACY_DIRECT` and packet promotion unchanged.
