# Prospective Learning Review Product V1

`prospective_learning_review_product` turns validated retrospective-learning review envelopes into a deterministic JSON product and concise Markdown brief. It consumes the review contract only; it does not rejoin raw observations or feed the current research product.

Each record exposes original research known at T, later governed observation/new-after-T evidence, reviewability, qualified-comparison status, unresolved state, authority limitations, and exact provenance. The optional AI input carries only these review-bound materials and allowed evidence references. An AI response is attached only after validation by `retrospective_learning_synthesis_response`.

Product files are deterministic and write-once: an existing file with different content is rejected. The product is retrospective explanation only, never correctness, scoring, recommendation, sizing, strategy, PIT, RAW_AS_TRADED, or backtest authority.
