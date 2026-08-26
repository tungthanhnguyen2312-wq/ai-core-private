# Accepted Structured Synthesis Corpus Contract

The corpus retains only responses accepted by `accept_structured_research_synthesis`; it never creates, repairs, or partially accepts research prose. Each immutable record contains the accepted response, its content/context identity, allowed evidence references, packet/direct metadata, and authority limitations.

Duplicate identical registration is idempotent. Identity/content disagreement fails closed. Records for different sessions remain separate. `corpus_to_dossier_batch_inputs` is an explicit one-way adapter requiring caller-supplied contexts, so the corpus does not reconstruct or infer context.
