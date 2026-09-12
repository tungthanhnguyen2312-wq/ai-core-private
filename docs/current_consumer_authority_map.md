# Current Consumer authority map

## Authority and normal input

Producer is the factual and deterministic numerical authority. Consumer validates
and passes through qualified Producer contracts; AI narrative is non-authoritative.
The normal Daily input is an explicit retained Producer `run_manifest.json` plus
its co-located `ai_research_bundle_manifest.json` and
`ai_research_session_bundle.json`. Consumer never discovers a latest run, imports
Producer, crawls sources, reclassifies freshness, or creates a recommendation.

Legacy context packages are `OPTIONAL_FALLBACK` / `HISTORICAL_REPRODUCIBILITY`.
They remain useful only where their own contract is requested. The Consumer does
not construct one as the normal Daily path.

## Contract matrix

| Producer domain / contract | Consumer handling | Status / fail-closed behavior |
| --- | --- | --- |
| Price/descriptive, breadth, sector, screening | Existing current-state pass-through builders and Daily cards | `CURRENT_COMPATIBLE`; supplied source/freshness/reason fields remain supplied fields. |
| Tactical | Existing tactical classifier / decision-packet pass-through | `CURRENT_COMPATIBLE`; deterministic research label, never execution authority. |
| Fundamentals and valuation | Financial Analysis Consumer context and current valuation/fundamental pass-through | `CURRENT_COMPATIBLE`; unavailable intrinsic valuation stays unavailable/blocked. |
| Corporate intelligence and catalyst/event | Current corporate-intelligence/event pass-through | `CURRENT_COMPATIBLE`; missing or temporal-incomplete evidence is not negative evidence. |
| `ai_handoff_source_freshness_matrix/v1` | Canonical Daily ingestion exposes `producer_handoff_surfaces.source_freshness_matrix.value` byte-for-byte | `CURRENT_COMPATIBLE`; absent is `MISSING`, and `PARTIAL_INTERNAL`, `STALE_INTERNAL`, and `UNAVAILABLE_INTERNAL` are never upgraded. |
| `macro_presentation_context/v1` | Canonical Daily ingestion exposes a distinct presentation surface | `CURRENT_COMPATIBLE`; retains cadence/source/officialness fields; absence is `MISSING`. |
| `current_macro_regime/v1` | Separate Canonical Daily surface | `CURRENT_COMPATIBLE`; presentation context never synthesizes a regime. |
| Market flow / foreign flow | Existing DNSE foreign-flow and market-flow pass-through; Daily flow coverage surface | `CURRENT_COMPATIBLE`; foreign/value flow, broad positioning, and proprietary flow remain separate. |
| Integrated Decision / `integrated_decision_delivery_overlay/v1` | Daily card `integrated_decision_v1` plus bundle-scoped surface | `CURRENT_COMPATIBLE`; overlay is research support, not recommendation or sizing authority. |
| Session comparison / `session_comparison_semantics/v1` | `next_session_decision_context` preserves the Producer brief metadata | `CURRENT_COMPATIBLE`; comparison session, role, gap, fitness, reason codes, and skipped sessions are passed through. |
| Recommendation/invalidation and risk/scenario | Next-session, scenario, risk-register, and decision-packet products | `CURRENT_COMPATIBLE`; `PARTIAL`, `UNAVAILABLE`, and `NOT_APPLICABLE` survive. |
| Portfolio context | Explicit portfolio/financial Consumer surfaces where supplied | `PARTIAL_CONSUMER_SUPPORT`; no portfolio context implies no allocation, sizing, or share count. |
| Prospective and shadow metadata | Prospective learning and shadow narrative consumers | `CURRENT_COMPATIBLE`; shadow/prospective evidence stays non-production and non-authoritative. |

## Load-bearing builder map

| Classification | Builders |
| --- | --- |
| `ACTIVE_PRODUCER_DEPENDENCY` | `build_ticker_context.py` (Producer references its named contract functions). `canonical_daily_producer_session_ingestion.py` is the current Consumer immutable-handoff entry. Producer has no runtime import of Consumer code. |
| `ACTIVE_CONSUMER_PRODUCT` | `accepted_structured_synthesis_corpus.py`, `current_research_auditable_dossier.py`, `current_research_synthesis_operational_workflow.py`, `next_session_decision_context.py`, `financial_analysis_consumer_context.py`, `historical_fundamental_brief_response.py`, `multi_angle_synthesis_boundary.py`, `multi_angle_synthesis_response.py`, `structured_research_synthesis_boundary.py`, `structured_research_synthesis_response.py`, `current_research_claim_provenance_trace.py`, `current_research_dossier_batch_catalog.py`, `current_research_packet_shadow_parity.py`, `correlation_concentration_consumer_context.py`, `official_financial_candidate_evidence.py`, `prospective_research_learning_review.py`, `prospective_research_attribution.py`, `prospective_learning_review_product.py`, `prospective_learning_registry_rollforward.py`, `prospective_learning_longitudinal_registry.py`, `retrospective_learning_synthesis_response.py`, `shadow_recommendation_consumer_narrative.py`. |
| `ACTIVE_OPTIONAL_TOOL` | `build_artifact_catalog.py`, `build_context_coverage_universe.py`, `compare_batch_runs.py`, `cited_document_evidence.py`, `context_coverage.py`, `decide_rebuild.py`, `kbs_trading_value_coverage_contract.py`, `metadata_registry_reader.py`, `metadata_registry_shadow_compare.py`, `missing_data_contract.py`, `run_final_qa.py`, `validate_json_schema_subset.py`, `validate_operating_pack.py`, `vn_time.py`. |
| `HISTORICAL_REPRODUCIBILITY` | `build_ticker_context.py`, `build_context_coverage_universe.py`, `build_batch_artifacts.py`, `freeze_v1_release.py`. |
| `LEGACY_NOT_ON_CURRENT_PATH` | Context-package builders and VNStock-named schema support remain retained fallback, not a deletion target. |
| `UNKNOWN` | None found among tracked Python builders; each tracked builder belongs to one of the retained paths above. |

`build_ticker_context.py` is both a still-load-bearing Producer dependency and a
historical/optional context-package builder; these roles are intentionally kept
distinct rather than deleted or relabelled as current Daily ingestion.

## Consumer invariants

- Preserve Producer source identity, freshness, authority tier, reason codes,
  comparison metadata, and unavailable/missing state verbatim when supplied.
- Do not upgrade `PARTIAL_INTERNAL`, `STALE_INTERNAL`, or `UNAVAILABLE_INTERNAL`.
- Macro presentation is descriptive and cadence-aware; it is not historical PIT
  authority and cannot create `current_macro_regime/v1`.
- DNSE foreign/value flow is not broad market positioning or proprietary flow.
- Tactical reversal/shadow output is `SHADOW_ONLY`, never production policy.
- Missing valuation/sizing authority remains a blocker; Consumer never makes a
  target, probability, allocation, or share-count fallback.

## Rebaseline record

`AI_CORE_CONSUMER_REBASELINE_AND_CURRENT_PRODUCER_CONTRACT_CONVERGENCE_V1`
records Consumer convergence only. Producer `STATE.md` and `ROADMAP_STATE.json`
remain the authoritative Stock Lookup control plane.
