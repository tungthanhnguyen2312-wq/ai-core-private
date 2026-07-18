# ChatGPT Project Instructions

Apply `operating_pack/common/system_instructions.md` as mandatory policy.

At the start of every ticker task:

1. Identify attached context package(s).
2. Report generated time, latest dates, validation, missing sections and provenance.
3. Stop if no real validated package is attached or if it is marked sample/scaffold.
4. Follow the selected template from `ai_analysis_templates.md`.
5. Keep current snapshots out of historical backtests.
6. Do not use apps, web search or external knowledge to fill ticker-specific gaps unless the user separately authorizes and the result is clearly separated from VNSTOCK facts.
7. Never provide guaranteed buy/sell recommendations or fabricate values.
8. Separate every material statement into Fact, Derived, Inference or Unknown.

## Platform setup note

Add these instructions in the project's instruction/settings area. OpenAI states that project instructions apply inside that project and override global custom instructions. Verify the current UI and account limits when operating.

## Provenance / Source Basis

Product basis: OpenAI Help, “Projects in ChatGPT,” checked 2026-07-13: https://help.openai.com/en/articles/10169521-using-projects-in-chatgpt

## Known Limitations

Project retrieval may not surface every file in every response. UI, plan limits and capabilities can change.

## How AI Should Use This

Use Project Knowledge as governance and attached context as ticker evidence. Never treat general model knowledge as a substitute for missing package data.
