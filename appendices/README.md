# Appendices

Supporting depth for the spec proper. Each appendix preserves the full output of one agent from the May 2026 god-tier-design swarm — depth that didn't fit cleanly into the numbered spec files.

## Swarm reports

Six agents, each covering one architectural layer. Every agent graded designs against the 5-axis rubric (security, UX, vendor-neutrality, operability, composability), cited at least 2-3 production-system precedents, and produced 2-3 concrete options with trade-offs.

| Appendix | Topic | Spec sections informed |
|---|---|---|
| [A — Transport](swarm-reports/A-transport.md) | rust-message-box vs rust-mpc transport gap; Iroh, libp2p, Matrix, Lit Protocol comparisons | §05, §06 |
| [B — Identity & certs](swarm-reports/B-identity.md) | BRC-52⊕ profile, Fulcio comparison, federation mechanism | §07, §08, §13 |
| [C — Policy & audit](swarm-reports/C-policy-audit.md) | Canonical-CBOR PolicyManifest, Cedar comparison, Rekor audit substrate, witness cosigning | §09, §10 |
| [D — Protocol/crypto](swarm-reports/D-protocol-crypto.md) | CGGMP'24 + CVE patches, DKLs23/FROST forward-prep, BRC-42 canonicalization, ExecutionId, SessionId | §01, §02, §03, §04 |
| [E — Notary product](swarm-reports/E-notary-product.md) | Three-tier product design, Fireblocks comparison, fee economics | §11, §12, §15 |
| [F — Operations](swarm-reports/F-operations.md) | Hybrid hot-TEE + cold-HSM, OTel discipline, refresh choreography, supply chain | §16, §17, §18 |

## Reading order

If reading the appendices first (instead of the spec):

1. **D** (protocol) — the cryptographic foundation. Sets up everything else.
2. **A** (transport) — the substrate over which protocol messages flow.
3. **B** (identity) — the cert format that gates participation.
4. **C** (policy + audit) — what cosigners enforce + how to prove it after the fact.
5. **E** (Notary product) — what the user-facing product looks like.
6. **F** (operations) — how it stays running.

If the appendices and the spec sections disagree, **the spec wins**. Appendices preserve the swarm's analysis; the spec is the contract.

## Provenance

The swarm was run on 2026-05-10 using six general-purpose agents. Each agent had:
- Read access to both implementation repos and supporting BSV infrastructure.
- Ability to consult external systems via web search/fetch (Fireblocks, Lit, Coinbase MPC, Sigstore, SPIFFE, Cedar, Iroh, Matrix, etc.).
- A 5-axis rubric for grading designs.
- Specific files to read (preventing rediscovery of prior swarm findings).
- A required output format (god-tier definition + options + trade-offs + spec language drafts).

The synthesis into the spec was done by a coordinator (the AI session running the swarm) and then reviewed and steered by the project lead (Calhoun). Disagreements were resolved by re-reading agent outputs and re-evaluating against the rubric, not by majority vote.

The agents had no knowledge of each other's outputs while working — each was an independent perspective. Convergence was performed after all six returned.
