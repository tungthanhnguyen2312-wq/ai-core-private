# Current Research Claim Provenance Trace Contract

`builders/current_research_claim_provenance_trace.py` is a read-only, deterministic audit product over a current ticker context and a structured research-synthesis response. It invokes `accept_structured_research_synthesis` and reuses that boundary's `known_evidence_refs`; it does not revalidate, widen, or repair evidence references.

A trace entry contains the claim identifier and payload, referenced evidence identities, source contract and artifact identity, component-local temporal fields, qualification/authority fields, transport disposition, reason codes, and a minimal provenance chain. Whole artifacts are not copied into trace rows.

The existing response schema has only package-wide `provenance_references`. Without `claim_evidence_map`, claims are `SUPPORTED_WITH_LIMITATION` and marked `package_wide_provenance_references_not_claim_level_linkage`. A caller with an already structured claim-to-reference mapping may supply it; every supplied reference must still be in the boundary-derived allowed set. Unknown, unavailable, malformed, conflicted, and prohibited claims remain untraceable/fail-closed.

Packet/direct equivalent artifacts are represented once as `DEDUPLICATED_SAME_LOGICAL_EVIDENCE`; conflicts are `CONFLICT_FAIL_CLOSED`. Packet Bear/Base/Bull and direct CONSERVATIVE/BASE/SPECULATIVE remain separate scenario contracts. The trace neither changes the `LEGACY_DIRECT` default nor provides decision, recommendation, probability, valuation, sizing, PIT, RAW_AS_TRADED, or backtest authority.
