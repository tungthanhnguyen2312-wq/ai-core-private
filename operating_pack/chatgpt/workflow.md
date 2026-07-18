# ChatGPT Operating Workflow

1. Create a Project and add the reference files from `upload_manifest.json` within current account limits.
2. Add `project_instructions.md` as project instructions.
3. Start one chat per task type/cutoff to avoid mixing stale contexts.
4. Attach the required context package(s) and current batch validation when applicable.
5. Ask ChatGPT to run the validation preamble before analysis.
6. Review the operator checklist and reject answers that hide unknowns or lack provenance.

## Known Limitations

The workflow was validated locally as documentation only; no ChatGPT upload or model call was performed.

## How AI Should Use This

Do not start analysis until attachments and validation status are confirmed. Preserve project instructions even when the user asks for a shorter answer.
