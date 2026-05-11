# ADR-0019: STH publication via PushDrop chain (not OP_RETURN)

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)
**Credit:** Mitch (Binary partnership) — proposed the PushDrop-spend-the-next-time pattern over Slack.

## Context

The original spec text for §10.5 specified Signed Tree Head (STH) publication as a BRC-18 **OP_RETURN** output on overlay topic `tm_mpc_audit`. Each cosigner publishes one OP_RETURN per epoch (default 60s); the chain semantics were enforced only by verifier convention (i.e., a verifier would check that successive OP_RETURNs from the same cosigner had monotonically-increasing tree_size).

In Slack review, Mitch flagged that **PushDrop** (BRC-23, spendable output with embedded data fields) would be better than OP_RETURN. His specific framing: *"you can spend it the next time in the audit log."* The insight is that each STH PushDrop becomes the next STH publication's input — forming a chain via UTXO consensus rather than via verifier convention.

## Decision

STH publication SHALL use a **PushDrop chain**:
- Each cosigner has a long-lived **audit identity** keypair (distinct from the 90-day-rotating signing identity).
- The cosigner's first STH is published as a genesis PushDrop locked to the audit identity.
- Each subsequent STH spends the previous STH PushDrop and creates a new PushDrop with the new tree_size + root_hash + signature.
- The chain of spends across time IS the audit log.

BRC-18 participation proofs (§10.7) **remain OP_RETURN** — they have no chain semantics (each is an independent per-ceremony attestation). The OPEN-QUESTIONS list tracks "BRC-18-as-PushDrop reputation token" as a v1.5 question.

## Rationale

### Security
- **UTXO-consensus enforces chain continuity.** Tamper is impossible (double-spend impossible) rather than merely detectable. Strictly stronger than the previous "verifier convention" chain.
- **Identity authenticity enforced at the UTXO layer.** Only the holder of the audit identity private key can spend the previous PushDrop and create the next. Bitcoin Script enforces this, not just the verifier.
- **Witness cosigning (§10.6) becomes self-validating.** A cosigner pretending their tree_size grew without publishing the corresponding spend transaction is immediately detectable — the UTXO they claim is the latest doesn't exist.

### UX
- **"Latest STH for cosigner X" = single UTXO lookup.** Verifiers don't scan-and-filter overlay topics by timestamp; they query the unspent PushDrop at the cosigner's audit identity. One query, one answer.
- **History traversal = standard input lineage walk.** Well-supported by every BSV indexer.
- **Operationally invisible to users** (audit is opaque to end users either way).

### Cost
- Per-STH cost drops from ~100 sats (OP_RETURN with prefix + version + identity + fields + signature) to **~1-2 sats** (just the transaction fee, since the prior PushDrop's value is recovered as input).
- At 60s cadence (1,440 STHs/day, ~525K/year per cosigner):
  - **OP_RETURN:** ~52M sats/yr ≈ **$22/yr** per cosigner (at $50/BSV)
  - **PushDrop chain:** ~787K sats/yr ≈ **$0.40/yr** per cosigner
  - **~50× cost reduction.** Amplifies the spec's economic-moat thesis (PROPOSAL §2).

### Vendor-neutrality, operability, composability
- Vendor-neutral: same as OP_RETURN.
- BSV-overlay-native: PushDrop is what `tm_mpc_signing` and CHIP tokens already use; topic managers in `bsv-overlay-cloudflare` already index PushDrops.
- Composes with §08 cert binding (audit identity as a cert field), §13.7 operator replacement (chain-rotation ceremony), and §16.8 operator credential rotation.

## Consequences

- **`bsv-mpc`:**
  - Add PushDrop emit/spend code for STH chain (extend `bsv-mpc-overlay/src/chip.rs` patterns).
  - Generate a long-lived audit identity keypair during cosigner provisioning.
  - Implement chain-rotation ceremony for audit identity rotation.
  - ~300 LOC of new code; reuses existing PushDrop primitives from CHIP token implementation.
- **`rust-mpc`:**
  - Same primitives needed on Binary's side. Binary may already have PushDrop tooling for CHIP tokens; if so, reuse.
- **`rust-message-box`:** No change (transport layer not affected).
- **Spec:**
  - §10.5 rewritten as PushDrop chain (subsections 10.5.1–10.5.8: field layout, genesis tx, subsequent tx, audit identity key, stranded-UTXO fallback, chain rotation, verification procedure, cost).
  - §10.7 BRC-18 proofs explicitly stay OP_RETURN with rationale.
  - §08.2 cert format adds `audit_identity` as a REQUIRED field for cosigner certs.
  - OPEN-QUESTIONS Q13 added: BRC-18-as-PushDrop is a v1.5 question.

This ADR is **not Phase 0** — it doesn't affect cryptographic-correctness wire compat. It's Phase 1 (security-critical layer) and changes the audit substrate.

## Alternatives considered

- **Keep OP_RETURN but add explicit `prev_root_hash` chain field.** Achieves chain semantics at the data layer without UTXO management. Rejected: loses the 50× cost reduction and loses UTXO-enforced authenticity (chain integrity becomes verifier convention, not consensus rule).
- **PushDrop chain with a Runar/sCrypt covenant** that enforces monotonic tree_size on-chain via Script. Strictly stronger than the chosen design (chain integrity becomes consensus-enforced rather than convention-enforced + UTXO-enforced-continuity), but adds Runar/Script complexity inappropriate for v1. **Reserved as a v2 hardening path** under a future ADR.
- **Stay OP_RETURN.** Rejected per the analysis above.

## Open implementation question

The stranded-UTXO fallback (§10.5.5) uses `OP_CHECKLOCKTIMEVERIFY` to enable anyone-can-spend recovery after 90 days. Implementations MAY omit this and accept ~50 sats per decommissioned cosigner as permanently locked. Spec leaves this as an implementation choice; recommends including the fallback for hygiene.

## See also

- Spec: [`§10-audit.md`](../10-audit.md) §10.5 (rewritten)
- Spec: [`§08-identity.md`](../08-identity.md) §08.2 (`audit_identity` field added)
- Open question: [`OPEN-QUESTIONS.md` Q13](../OPEN-QUESTIONS.md) — BRC-18-as-PushDrop deferred to v1.5
- BRC-23 PushDrop spec (BSV overlay primitive)
- BRC-22 SHIP/SLAP/CHIP overlay protocol

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
