# Gemini Operating Workflow

> **[DEPRECATED 2026-07-17]** Gemini is removed from the recommended workflow. Two independent
> audits (`STOCK_ANALYSIS_MASTER_PLAN.md`, `FINAL_STOCK_ANALYSIS_20260717.md` at the `C:\Projects`
> root) found Gemini Deep Research repeatedly fabricating or omitting data even when given
> correctly-formatted input. This file is kept as a historical/audit artifact only — do not use it
> for new tasks. Current workflow: ChatGPT/Claude (`operating_pack/chatgpt/`, `operating_pack/claude/`)
> or Codex/Claude Code (direct file access, see `docs/v1_0_DailyWorkflow.md` mục D).

1. Create the available project/Gem-style workspace manually.
2. Add only manifest-listed references within current platform limits.
3. Add the project instructions in the available instruction field.
4. Attach only task-specific context packages.
5. Request validation preamble, then use the matching prompt template.
6. Apply the operator checklist before accepting output.

## Known Limitations

No Gemini upload, UI verification or model call was performed.

## How AI Should Use This

Treat any unavailable platform feature as an operating limitation; do not improvise by uploading raw VNSTOCK data.
