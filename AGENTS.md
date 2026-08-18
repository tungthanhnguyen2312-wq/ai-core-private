# Repository guardrails

Codex is the executor. Consumer preserves qualified Producer contracts and fails closed; it must not infer missing source semantics or upgrade blocked current-market states. For a normal bounded Consumer milestone, read this file, then `../stock-core-private/docs/STATE.md`, then only the Producer roadmap/decision/rule sections and contracts referenced there or required by the named milestone. Do not read all handoffs, all decisions, or the full roadmap by default. `stock-core-private/docs/STATE.md` is the current Producer entrypoint; operations reviews are historical/supporting evidence, not competing current authority. Do a full authority refresh only for architecture, governance, program-priority, source/capability-authority changes, documented contradictions, or an owner-requested rebaseline.

- Work only inside this repository unless the task explicitly names another workspace location.
- Treat the dashboard runtime selected by `STOCK_LOOKUP_RUNTIME_ROOT` as read-only; do not infer or hard-code its path.
- Keep repository documentation portable, with relative repository links only. Put machine-specific procedures in local operator documentation.
- Do not edit generated context packages, backups, credentials, or release snapshots unless explicitly requested.
