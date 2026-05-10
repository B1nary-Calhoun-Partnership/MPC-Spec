# ADR-0004: Canonical SessionId formula

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)

## Context

SessionId is the 32-byte ceremony-unique identifier consumed by ExecutionId (§02) and threaded through every transport envelope (§05). The audit log (§10) cites SessionId in BRC-18 participation proofs, so any third party recomputing SessionId from inputs must produce the same hash.

Today, both implementations use **random** session IDs (rust-mpc generates a 16-byte hex like `"sign_<32-hex>"` via `new_session_id`; bsv-mpc produces strings ad-hoc). Random IDs break audit-recoverability — the only way to verify a SessionId is to be the party that produced it.

## Decision

The canonical SessionId formula is **deterministic over ceremony inputs plus a fresh nonce**:

```
SessionId = SHA256(
    "calhoun-binary-mpc-session-v1"  // 29-byte ASCII domain separator
    || initiator_identity_33B          // BRC-31 identity pubkey of coordinator
    || sorted_participant_identities    // each 33B compressed, lex-ascending
    || threshold_u16_LE
    || ceremony_kind_byte               // 0x01 dkg | 0x02 sign | 0x03 presign | ...
    || nonce_32B                        // OsRng routine; recent BSV blockhash for high-value
    || payload_digest_32B               // ceremony-kind-specific
)
```

Detail in [`§04-session-id.md`](../04-session-id.md). For high-value ceremonies (Notary onboarding, key refresh), the nonce SHOULD be the SHA-256 of a recent BSV block hash — provides on-chain freshness witness.

## Rationale

Three properties drive the choice:

1. **Audit recoverability.** Given the inputs (recorded in the BRC-18 proof and the audit log), any third party can recompute SessionId and verify the audit record. With random SessionIds, this verification path requires trusting the producer.

2. **Replay binding.** ExecutionId derives from SessionId + joint_pubkey + phase. Deterministic SessionId means deterministic ExecutionId — a malicious party cannot fabricate plausible ExecutionIds for ceremonies that didn't happen.

3. **Session collision avoidance.** The fresh `nonce_32B` provides freshness; the deterministic input-binding provides input-uniqueness. Two ceremonies with otherwise-identical inputs but different nonces produce distinct SessionIds.

## Consequences

- **`bsv-mpc`:** Implement deterministic SessionId per §04. Replace ad-hoc string production with the canonical SHA-256. ~4 hours of work.
- **`rust-mpc`:** Replace `new_session_id("sign")` with the deterministic formula. Same on the keygen path. ~4 hours of work.
- **`bsv-messagebox-cloudflare`:** No change.
- **Spec:** [`§04-session-id.md`](../04-session-id.md) codifies the formula and per-kind `payload_digest_32B`.
- **Test vectors:** Vectors A (routine 2-of-3 sign), B (DKG with on-chain anchor) land in `conformance/test-vectors/04-session-id.json`.

## Alternatives considered

- **Pure random SessionId** — rejected; breaks audit recoverability.
- **Coordinator-chosen string SessionId** — rejected; vulnerable to malicious coordinators forging valid-looking SessionIds for ceremonies that didn't happen.
- **UUIDv4** — rejected; same problems as pure random plus weaker domain separation.
- **Time-prefixed deterministic** — considered; rejected because timestamp granularity is implementation-dependent and adds little vs OsRng nonce.

## See also

- Spec: [`§04-session-id.md`](../04-session-id.md)
- Consumed by: [`§02-execution-id.md`](../02-execution-id.md), [`§05-message-envelope.md`](../05-message-envelope.md), [`§10-audit.md`](../10-audit.md).

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
