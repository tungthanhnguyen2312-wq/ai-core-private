# AI ANALYZE — Consumer contract layer

AI ANALYZE is the fail-closed Consumer for Stock Lookup. Its normal input is the
immutable Producer handoff (`ai_research_session_bundle/v1`) and any explicitly
referenced deterministic artifact. It validates and preserves qualified contracts
for human research interaction in ChatGPT, Codex, or another approved AI surface.

`stock-core-private` is the Producer and factual/numerical authority. DNSE is its
primary current market-data direction. This repository does not crawl markets,
create source authority, upgrade freshness, or turn AI prose into a recommendation.

## Start here

- Read [the current Consumer authority map](docs/current_consumer_authority_map.md).
- For a current Daily handoff, use
  `builders/canonical_daily_producer_session_ingestion.py` with one explicit,
  retained `run_manifest.json`; it resolves only its co-located immutable delivery
  files and never selects a “latest” run.
- Use [the prompt library](prompts/ai_analysis_templates.md) and
  [the operating pack](operating_pack/README.md) after the handoff is available.
- Read [historical planning and operating documents](docs/HISTORICAL_DOCUMENTS.md)
  only for reproduction or audit context. They do not supersede Producer state.

## Authority boundary

Producer → qualified deterministic research → immutable AI handoff → Consumer
validation/pass-through → human AI research interaction.

- A Producer fact, source identity, freshness state, authority tier, reason code,
  or unavailable state is preserved as supplied.
- `macro_presentation_context/v1` is descriptive presentation context and remains
  distinct from `current_macro_regime/v1`.
- DNSE foreign/value flow, broader market-flow positioning, and proprietary-flow
  availability are separate concepts; Consumer does not merge them.
- Tactical/shadow evidence is non-authoritative. It cannot become a production
  recommendation, probability, target, or sizing instruction.
- Missing intrinsic valuation or sizing authority remains blocked/unavailable.
- AI narrative is non-authoritative: it cannot create a buy/sell decision,
  target, probability, expected return, allocation, or share count.

## Legacy and historical material

Context packages, VNStock-named schemas, old platform upload instructions, and
the Gemini pack remain for reproducibility where retained. They are
`HISTORICAL` or `OPTIONAL_FALLBACK`, not the normal Daily path. Gemini material is
deprecated historical/audit material and is not a recommended executor.

## Repository guardrails

- Do not modify the runtime selected by `STOCK_LOOKUP_RUNTIME_ROOT`.
- Do not treat missing, null, sentinel, stale, partial, or blocked inputs as a
  usable current value.
- Keep point-in-time, source, unit, scale, and authority boundaries explicit.
- Producer state and roadmap remain authoritative; this repository does not own a
  competing Stock Lookup roadmap.
