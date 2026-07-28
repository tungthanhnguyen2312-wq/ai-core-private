# Consumer Price and Volume Basis Metadata Integration Contract

**Recorded:** 2026-07-28
**Component:** `ai-core-private` (Consumer)
**Modules:** `builders/build_ticker_context.py`, `prompts/ai_analysis_templates.md`

---

## 1. Executive Summary & Core Principles

This contract defines the Consumer-side integration of Producer-qualified price basis, corporate action adjustment, and historical volume metadata into ticker context packages and AI prompts.

Key Guarantees:
1. **Pass-Through Provenance:** Producer price basis (`raw`, `adjusted`, `unknown`) and volume basis (`raw_shares_traded`, `adjusted_volume`, `unknown`) metadata are propagated into `context.price_summary` without recomputing or guessing values.
2. **Fail-Closed on Unknown:** Missing or unverified price basis defaults to `unknown` with `price_basis_verified=False` and `is_actionable=False`.
3. **Decoupled Volume Semantics:** Historical volume is maintained as an independent metadata field (`volume_basis`). A price adjustment claim does not imply volume adjustment.
4. **Compatibility Guardrails:** `validate_context_basis_compatibility()` detects and rejects attempts to compare or combine `raw` and `adjusted` price packages in strict mode.
5. **Backward Compatibility:** Older context packages or bundles without Phase 1D fields parse safely without error, defaulting to `unknown` price basis and `raw_shares_traded` volume basis.
6. **AI Prompt Structuring:** AI prompt templates classify verified basis metadata as Fact, and unverified or unknown basis as Data Warnings/Unknown.

---

## 2. Propagated Schema Structure (`price_summary`)

| Field Name | Type | Description |
|---|---|---|
| `price_basis` | `str` | Price basis classification (`raw`, `adjusted`, `unknown`) |
| `price_basis_verified` | `bool` | `True` only when upstream provider basis is verified |
| `is_actionable` | `bool` | `True` when basis is verified and actionable for corporate-action calculations |
| `volume_basis` | `str` | Historical volume basis classification (`raw_shares_traded`, `adjusted_volume`, `unknown`) |
| `volume_basis_verified` | `bool` | `True` when volume basis classification is verified |
| `adjustment_source` | `str \| null` | Upstream provider or pipeline responsible for adjustments |
| `effective_date` | `str \| null` | Effective timestamp of corporate action adjustments |
| `limitations` | `list[str]` | Human-readable limitations and uncertainty warnings |
