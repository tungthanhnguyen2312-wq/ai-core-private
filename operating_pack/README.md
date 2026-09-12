# AI ANALYZE v1.0 Operating Pack

## Purpose

This pack supports human research from the immutable Producer AI handoff. The normal
input is `ai_research_session_bundle.json` (with its explicit manifest/run lineage),
not a manually assembled or uploaded VNStock context package. Consumer validates and
preserves the supplied contract; it does not crawl sources, establish authority, or
generate investment recommendations.

> **[DEPRECATED 2026-07-17]** `gemini/` is kept on disk as a historical/audit artifact only. Two
> independent audits (`STOCK_ANALYSIS_MASTER_PLAN.md`, `FINAL_STOCK_ANALYSIS_20260717.md` at the
> `C:\Projects` root) found Gemini Deep Research repeatedly fabricating or omitting data even when
> given correctly-formatted input (e.g. falsely claiming HPG data / 30-session OHLCV were
> "completely missing" when both were present). Gemini is removed from the recommended workflow;
> do not attach `operating_pack/gemini/*` to new tasks.

## Operating model

**Normal Daily path (ChatGPT, Claude, Codex):**
1. Receive the explicit immutable Producer handoff and its manifest lineage.
2. Attach/reference the handoff and only its explicitly referenced deterministic artifacts.
3. Apply the platform instructions and selected prompt template.
4. Run the operator checklist before accepting an answer.

**Manual fallback:** Older context-package/upload procedures are retained only for
historical reproduction or a supported standalone workflow. Label any such use
`MANUAL_FALLBACK / NOT_NORMAL_DAILY_PATH`; do not present it as current architecture.

## Common safety invariant

Facts must come from the supplied Producer handoff and explicitly referenced
artifacts. Preserve source/freshness matrix states, macro presentation versus macro
regime distinction, comparison metadata, warnings, provenance and point-in-time
limitations. Distinguish Producer Fact, Deterministic Derived, Online Evidence,
Inference, and Unknown; never provide a guaranteed buy/sell recommendation.

## Provenance / Source Basis

The pack is derived from Phase 1–10 knowledge, metadata, validation, workflows, prompts and final QA artifacts. No platform upload or model call was performed.

## Known Limitations

- Platform UI, retrieval behavior and file limits can change.
- Gemini and Claude setup language is intentionally generic and not externally verified in Phase 11.
- ChatGPT Projects guidance was checked against the official OpenAI Help Center, but plan-specific limits must still be verified at use time.

## How AI Should Use This

Treat this directory as operating instructions, not market data. Refuse analysis when
no validated Producer handoff is attached or when the requested use violates
point-in-time rules.
