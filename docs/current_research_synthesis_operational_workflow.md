# Current Research Synthesis Operational Workflow

`prepare_synthesis_session` creates provider-neutral request packages from explicit current contexts. It contains only governed compact metadata, boundary-derived permitted evidence refs, existing response schema requirements, and prohibited claims. It invokes no model.

When the named Daily Producer loader supplies `producer_handoff_surfaces`, the request
also carries those availability envelopes and Producer values verbatim. AVAILABLE and
MISSING remain distinct; the macro session projection retains its cutoff, source
identity and non-actionable status. This field adds context only and does not grant
new evidence references or change the response acceptance boundary.

`ingest_synthesis_session` accepts explicit response files, registers only boundary-accepted responses in the immutable corpus, and emits per-ticker accepted/rejected/no-response dispositions plus corpus-to-dossier batch handoff inputs. It is downstream-only; packet promotion remains owner approval and prospective learning remains paused pending real observations.
