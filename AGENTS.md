# Repository guardrails

- Work only inside this repository unless the task explicitly names another workspace location.
- Treat the dashboard runtime selected by `STOCK_LOOKUP_RUNTIME_ROOT` as read-only; do not infer or hard-code its path.
- Keep repository documentation portable, with relative repository links only. Put machine-specific procedures in local operator documentation.
- Do not edit generated context packages, backups, credentials, or release snapshots unless explicitly requested.
