# ADR-0003: Canonical ExecutionId formula

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)

## Context

ExecutionId is the 32-byte tag fed into every cggmp24 transcript hash, ZK proof challenge, and reliable-broadcast commitment. It binds a ceremony to a specific `(spec, algorithm, phase, session, joint_pubkey)` tuple. **Mismatched ExecutionIds across parties cause round-1 abort.**

Today's two implementations diverge:

- **bsv-mpc** (`crates/bsv-mpc-core/src/signing.rs:175-183`): `SHA256(b"bsv-mpc-signing-" || session_id.0.as_bytes())`. Domain-separated, but algorithm-agnostic, phase-agnostic, joint-pubkey-agnostic.
- **rust-mpc** (`crates/coordinator/src/dkg.rs:154` et al): `ExecutionId::new(keygen_session_id.as_bytes())` — raw UTF-8 bytes of session_id, no SHA-256 wrap, no domain separator.

Cross-implementation ceremonies abort at round 1 today. **This is the single most important wire-compat fix in Phase 0.**

## Decision

The canonical ExecutionId formula is:

```
ExecutionId = SHA256(
    "calhoun-binary-mpc"     // 18-byte ASCII domain separator
    || 0x01                   // version byte: mpc-spec-v1
    || algorithm_tag          // u8: 0x01 cggmp24 / 0x02 dkls23 / 0x03 frost (reserved for v2/v3)
    || phase_tag              // u8: 0x01 keygen / 0x02 auxinfo / 0x03 presign / 0x04 sign / 0x05 ecdh / 0x06 refresh / 0x07 reserved
    || session_id_32B
    || joint_pubkey_33B       // all-zeros during keygen (joint key not yet known)
)
```

86-byte input → 32-byte output.

For DKG keygen specifically (phase 0x01), `joint_pubkey_33B` is 33 zero bytes (carve-out, since joint key isn't known yet).

## Rationale

The formula closes four threats:

1. **Cross-protocol replay.** Domain separator prevents an envelope captured on this network from being accepted on another deployment using cggmp24 with a different domain.
2. **Cross-scheme replay.** `algorithm_tag` ensures a captured cggmp24 envelope cannot be replayed on a future DKLs23 ceremony. Forward-prep for v2/v3 migration.
3. **Cross-phase replay.** `phase_tag` ensures a DKG-round-2 message cannot be reinjected as a sign-round-2 message. Each phase has distinct ExecutionIds even within the same session.
4. **Cross-key replay.** `joint_pubkey` ties ExecutionId to a specific key. Two ceremonies for two different wallets with otherwise-identical inputs produce distinct ExecutionIds.

The all-zero carve-out for keygen is the unique exception — keygen produces the joint key, so it can't be in the input.

## Consequences

- **`bsv-mpc`:** Replace `signing.rs:175-183` and equivalent `dkg.rs` lines with the §02 formula. Generate test vectors. ~3 hours of work.
- **`rust-mpc`:** Replace `coordinator/src/dkg.rs:154` and equivalent files with the §02 formula. Generate test vectors. ~3 hours of work.
- **`bsv-messagebox-cloudflare`:** No change.
- **Spec:** [`§02-execution-id.md`](../02-execution-id.md) codifies the formula.
- **Test vectors:** Vector A (sign), Vector B (keygen carve-out), Vector C (refresh) land in `conformance/test-vectors/02-execution-id.json`. Both implementations MUST produce byte-identical results.

This ADR is the single most important wire-compat fix in Phase 0. **Until both implementations land this change, any joint ceremony aborts at round 1.**

## Alternatives considered

- **bsv-mpc's existing formula** — rejected; lacks algorithm/phase/joint-pubkey binding.
- **rust-mpc's existing formula** — rejected; no domain separator, no algorithm binding.
- **Random ExecutionId** — rejected; loses input→id binding, breaks audit-recoverability.
- **Plain `cggmp24::ExecutionId::default()`** — rejected; the cggmp24 default has zero domain separation.

## See also

- Spec: [`§02-execution-id.md`](../02-execution-id.md)
- Cross-references: §01 (algorithm_tag), §04 (SessionId), §05 (envelope binding).

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
