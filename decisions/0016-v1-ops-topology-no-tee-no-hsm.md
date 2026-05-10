# ADR-0016: v1 ops topology — no TEE, no HSM cold tier

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)

## Context

The May 2026 design swarm's Operations zone (Appendix F) recommended a **hybrid hot-TEE + cold-HSM topology** for the operational quorum: 3 hot cosigners in TEEs (AWS Nitro / SEV-SNP / TDX) plus 1-2 cold-tier HSM-backed cosigners participating in resharing/recovery only.

That recommendation is the right answer for institutional-tier deployments with regulatory pressure for hardware-backed key custody. It is the **wrong answer for v1**:

| Component | Cost |
|---|---|
| AWS Nitro Enclave | ~$0.40/hr/cosigner ≈ $300/mo |
| AWS CloudHSM | ~$1.45/hr/cluster ≈ $1K/mo |
| Multi-region multi-vendor TEE | $1K+/mo just in enclave overhead |

For a partnership-stage product targeting per-signature pricing 3-4 OOM cheaper than Fireblocks, this overhead is excessive. The cryptographic stack we already have without enclave hardware (threshold + share refresh + audit + witness cosigning + share encryption at rest) is sufficient for the v1 threat model.

## Decision

**v1 ships without TEE and without HSM cold tier.** Cosigners run on standard cloud infrastructure (CF Workers, k8s pods, VMs). Diversification across distinct cloud vendors / accounts / jurisdictions provides cloud-correlation defense in lieu of TEE.

Forward-compat hooks are preserved — cert format keeps `attestation` and `binary_hash` fields as OPTIONAL (§08); policy engine keeps `RuleKind::RequireAttestation` schema (§09). When v2 ships TEE/HSM, no wire changes are required.

## Rationale

The cryptographic invariants without enclave hardware:

- **Threshold security (CGGMP'24 UC-IA, §01).** A malicious party cannot extract the joint key from t-1 corruptions. This is the bottom-line guarantee.
- **Share encryption at rest** (AES-256-GCM with BRC-42-derived keys). A host compromise that leaks the at-rest share file does not leak the share itself without the BRC-42 derivation key.
- **30-day share refresh (§16.5, POC 13).** Bounds the compromise window: any slow side-channel leak or undetected-share-theft is invalidated within 30 days.
- **Audit log + witness cosigning (§10).** Cryptographic non-repudiation: cosigner #2 cannot retroactively rewrite their log without #3 noticing on the next ceremony's witness round.
- **Per-cosigner policy enforcement (§09).** Each cosigner refuses to sign requests outside its policy; even if one is compromised, the others enforce limits.
- **Build-time supply-chain provenance (§17).** Reproducible Cargo + cosign + Rekor + SLSA L3 prove "what code produced this signature" without requiring runtime attestation.

What we lose by not having TEE in v1:

- **Defense against host-OS root compromise at runtime.** Mitigation: share refresh cadence bounds the compromise window. Combined with detection signals (anomalous policy decline rate, Rekor reverification failure, peer audit-anomaly posts) → IR-002 path → sub-30-min resharing-without-suspect.
- **"Code currently running in attested enclave" claim.** v1 gets build-time provenance only. Sufficient for the v1 audience (developers, agents, low-to-medium-value users); insufficient for regulated institutional custody — which is v2 audience.

What we lose by not having HSM cold tier in v1:

- **Air-gapped recovery option for catastrophic quorum loss (case (c) of §16.6).** Mitigation: encrypted backup at the user's BRC-100 wallet remains the v1 recovery path. Jurisdictional escrow is reserved for v2.
- **Vault tier (`ColdOnly` quorum profile).** Mitigation: v1 ships with one quorum profile (`Hot`); v2 adds `HotPlusCold` and `ColdOnly` when institutional users demand them. The mechanism (resharing across (t,n) profiles) is the same; v1 just doesn't activate cold-tier infrastructure.

The decision to defer is **cost-driven, not correctness-driven**. When v2's audience appears (regulated institutional custody, regulatory pressure for "what code produced this signature" provenance), a successor ADR will activate TEE/HSM with the existing forward-compat hooks. No wire format changes will be required.

## Consequences

- **`bsv-mpc`:** No deployment changes for v1. CF Worker remains a standard Workers deployment. ~0 days of extra work.
- **`rust-mpc`:** No deployment changes for v1. Standard k8s / VM / mobile deployments. ~0 days of extra work.
- **`bsv-messagebox-cloudflare`:** No change.
- **Spec:**
  - §16.1 codifies the v1 deployment posture explicitly.
  - §16.7 marks TEE attestation as v2-reserved (not v1).
  - §17.7 marks TEE cross-check as v2-reserved.
  - §17.9 distinguishes v1 conformance (binary_hash + rekor_uuid) from v2 (adds attestation_doc).
- **Test vectors:** No TEE-attestation vectors required for v1. Reserved for v2.
- **OPEN-QUESTIONS.md Q8:** marked DEFERRED to v2.

This ADR is **not Phase 0** — it doesn't block joint cryptographic ceremony interoperability. It is Phase 2 (operational stack) and can be revisited separately.

## Alternatives considered

- **Original swarm recommendation (hot TEE + cold HSM)** — rejected for v1 due to cost; reserved for v2.
- **TEE-only without HSM** — rejected; same cost issues, asymmetric topology.
- **HSM-only without TEE** — rejected; HSM cost dominates, doesn't address runtime integrity for the hot path.
- **Optional TEE per-deployment** — partially adopted: v1 implementations MAY opt into TEE if they have the budget, but the *spec* doesn't require or recommend it. Counterparties MAY require it via policy (`RuleKind::RequireAttestation`) but v1 default deployments do not.

## v2 trigger conditions

A v2 ADR (ADR-0019 or later) reopening this question SHOULD be filed when any of:

- The partnership signs an institutional customer requiring hardware-backed key custody.
- Regulatory pressure (e.g., NYDFS, BaFin guidance) makes runtime TEE attestation a market expectation.
- Cloud TEE pricing drops by ~50% (making the cost-benefit favorable for general use).
- Two of the three cosigner hosts independently adopt TEE deployments for non-regulatory reasons (signal that the ecosystem has moved).

## See also

- Spec: [`§16-operations.md`](../16-operations.md) — v1 deployment posture.
- Spec: [`§17-supply-chain.md`](../17-supply-chain.md) — build-time provenance retained.
- Open question: [`OPEN-QUESTIONS.md` Q8](../OPEN-QUESTIONS.md) — DEFERRED to v2.
- Appendix: [`appendices/swarm-reports/F-operations.md`](../appendices/swarm-reports/F-operations.md) — original swarm Option 3 recommendation, preserved for context.

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
