# ADR-0043: Post-quantum migration roadmap

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Security dimension; identified PQ forward-prep as a v3 reservation.

## Context

NIST FIPS 204 (ML-DSA, formerly CRYSTALS-Dilithium) and FIPS 205 (SLH-DSA, formerly SPHINCS+) standardized hash-based / lattice-based signatures in 2024. Threshold-MPC equivalents of these are still research-grade as of 2026; no production-ready threshold-ML-DSA exists.

BSV consensus is ECDSA-only and is unlikely to add a PQ signature opcode within the v1 window. But the partnership's stack has several non-consensus signature paths that can migrate independently:

- **Cert chain (BRC-52⊕)** — already uses ECDSA today. Could move to ML-DSA without consensus changes; only the cert-verification path on cosigners + the certifier issuance pipeline change.
- **Audit identity signatures (§10.5 PushDrop chain)** — BRC-77 today. Could become hybrid (ECDSA || ML-DSA) without breaking BSV consensus (the OP_DROP fields can carry the PQ signature).
- **BRC-31 mutual auth (§07)** — ECDSA today. Hybrid achievable for the auth layer.

The MPC-signature layer itself (cggmp24 → threshold ECDSA) cannot move until BSV consensus introduces a PQ signature opcode AND threshold-PQ-ECDSA equivalents reach production maturity. That's the v3 trigger.

## Decision

### Phase 1 (v3, BSV-consensus-independent layers) — concrete triggers per CHANGES-PROPOSED #12

**Trigger (whichever first):**

- **(a)** Production-ready Rust ML-DSA threshold implementation released. Operationally defined: at least one library at v1.0+ with a published CVE-disclosure pipeline AND at least one production deployment history.
- **(b)** NIST FIPS 204 (ML-DSA) stable status AND at least two independent published security audits of the Rust implementation.

When either trigger fires:

- Cert chain (BRC-52⊕) migrates to hybrid ECDSA || ML-DSA per cert layer.
- Audit identity signatures emit hybrid signatures (both algorithms; verifier requires both pass).
- BRC-31 mutual auth optionally accepts hybrid sigs.
- §02 ExecutionId `algorithm_tag` reserves `0x04` for "BRC-52⊕ + ML-DSA hybrid identity layer." The MPC-protocol layer (cggmp24) is unaffected — that's `algorithm_tag = 0x01` and stays.

### Phase 2 (v3+, BSV-consensus dependent) — concrete triggers per CHANGES-PROPOSED #12

**Trigger (BOTH must hold):**

- **(c)** BSV consensus has an active proposal AND testnet activation for a PQ-compatible signature opcode (e.g., PQ-equivalent of `OP_CHECKSIG`).
- **(d)** Threshold-PQ scheme reaches CGGMP'24-equivalent maturity. Operationally defined: 2 production implementations with shared CVE-disclosure pipeline, ≥18-month deployment history.

Both conditions provide independent assurance: (c) covers consensus-layer readiness; (d) covers cryptographic-scheme maturity. PQ migration without one is premature.

When both triggers hold:

- Threshold-PQ-ECDSA or threshold-ML-DSA equivalent integrated as an alternate signing protocol via the `algorithm_tag` mechanism in §02.
- `algorithm_tag = 0x05` reserved for "threshold ML-DSA" (or whatever the consensus-blessed PQ scheme becomes).

### Phase 3 (post-v3, contingent)

Sunset of ECDSA-only signing paths. Migration of existing wallets via threshold resharing to PQ-equivalent thresholds (no on-chain key move; same wallet address if BSV consensus allows). Requires a refresh ceremony that operates across the algorithm boundary.

## Rationale

- **No v1 work.** PQ migration is properly v3; v1's job is to keep the algorithm-tag mechanism in §02 such that v3 migration is a parameter change, not a redesign.
- **Threshold-PQ is genuinely not ready in 2026.** No production threshold ML-DSA implementation exists. Forcing a v1 commitment would be premature.
- **Hybrid is cheap, plaintext is risky.** When the threshold-PQ tooling matures, hybrid signing (both ECDSA and ML-DSA, verifier requires both) is much cheaper to deploy than full migration; it also gives a hedge if either algorithm is broken.
- **BSV consensus is the long-pole.** The partnership has no leverage over BSV consensus timeline; tying our PQ trigger to consensus events keeps us honest about what we can deliver.

## Consequences

### `bsv-mpc` + `rust-mpc`

- No v1 work.
- v3 work: integrate `liboqs` or `pqcrypto` Rust ML-DSA implementations; thread through cert verification + audit signature paths.

### `MPC-Spec`

- §02 ExecutionId `algorithm_tag` value `0x04` reserved (hybrid identity-layer).
- §02 ExecutionId `algorithm_tag` value `0x05` reserved (threshold-PQ MPC, contingent on consensus).
- No other spec changes at v1.

## Alternatives considered

- **Don't reserve.** Rejected — `algorithm_tag` is cheap to reserve; reservations don't constrain implementation. Forward-compat insurance.
- **Commit to ML-KEM-based encryption now.** ML-KEM is a KEM (key encapsulation), not a signature primitive. BRC-78 ECIES uses an EC point as the shared-secret derivation; ML-KEM-equivalent migration is a separate ADR (not this one). Reserved for separate v3 work.
- **Wait for BSV consensus before any prep.** Rejected — cert chain + audit chain migration is non-consensus and can land before consensus does. Reserving algorithm_tag now keeps the door open.

## M1 dependency

**None.** Pure v3 forward-prep.

## See also

- Spec: [§02](../02-execution-id.md) (algorithm_tag mechanism)
- NIST FIPS 204 (ML-DSA), FIPS 205 (SLH-DSA), FIPS 203 (ML-KEM)
- 2026-05-13 swarm: Security S/PQ

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
