# Repository guardrails

Codex is the executor. Consumer preserves qualified Producer contracts and fails closed; it must not infer missing source semantics or upgrade blocked current-market states. Read Producer canonical governance at `../stock-core-private/docs/` before work — see especially `WORKSPACE_GOVERNANCE.md` there for the cross-repo agent contract (`operations-review/AGENT_WORKING_CONTRACT.md`) and current project state (`operations-review/PROJECT_STATE.md`), which take precedence over any single repo's own docs for cross-repo questions.

- Work only inside this repository unless the task explicitly names another workspace location.
- Treat the dashboard runtime selected by `STOCK_LOOKUP_RUNTIME_ROOT` as read-only; do not infer or hard-code its path.
- Keep repository documentation portable, with relative repository links only. Put machine-specific procedures in local operator documentation.
- Do not edit generated context packages, backups, credentials, or release snapshots unless explicitly requested.
