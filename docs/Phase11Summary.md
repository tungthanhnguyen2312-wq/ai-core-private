# Phase 11 — Operating Pack

## Completed work

- Created a common governance pack with system instructions, operator checklist, conflict handling and context-budget policy.
- Created independent ChatGPT, Gemini and Claude upload manifests, project instructions and workflows.
- Created a top-level operating pack manifest.
- Added a local operating-pack validator and Phase 11 tests.
- Generated `exports/operating_pack/operating_pack_validation.json/.md`.

## Validation result

- Operating-pack validation: **PASS**
- Critical/High/Medium/Low issues: 0
- Full Phase test suite: 22/22 passed
- External uploads: none
- Model calls: none

## Platform notes

ChatGPT Projects guidance was checked against the official OpenAI Help Center. It confirms Projects can group chats, uploaded reference files and project-specific instructions; project instructions apply within that project and override global custom instructions. Current account/file limits must be checked at operation time.

Gemini and Claude setup instructions remain generic because their current UI/limits were not externally verified in this phase.

## Operating policy

Use the platform reference manifest as the stable knowledge base. Attach one context for a ticker, two for comparison, or at most ten plus batch validation for screening. Never upload raw VNSTOCK or sensitive personal data.

## Provenance / Source Basis

The pack derives from Phase 1–10 knowledge, metadata, validation, prompts and final QA. ChatGPT product basis: https://help.openai.com/en/articles/10169521-using-projects-in-chatgpt

## Known Limitations

- No platform upload or live-model compliance test was performed.
- Retrieval behavior and account limits can change.
- Operating instructions cannot guarantee model compliance; human review remains required.

## How AI Should Use This

Treat Project Knowledge as governance and context packages as ticker evidence. Refuse to fill missing package data from general knowledge unless separately authorized and attributed.

Phase 12 has not started.
