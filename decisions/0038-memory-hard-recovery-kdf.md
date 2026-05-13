# ADR-0038: Memory-hard recovery KDF + rate-limited online unwrap + escrow audit obligations

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Security S2; UX F4 (always-on recovery health) is the companion finding deferred to ADR-0034.

## Context

§18.5 catastrophic recovery (case (c): 2 of 3 cosigners simultaneously fail; user has only share A) is the highest-trust path in the system. The whole MPC threshold collapses to "user types a recovery passphrase." The spec text prior to this ADR was thin:

- §18.5.1 Path 1 (encrypted backup at user's BRC-100 wallet): no KDF specified, no rate-limit, no audit-on-attempt.
- §18.5.2 Path 2 (jurisdictional escrow): no per-attempt audit, no individual-identity verification, no throttle.

Attack surfaces:
- **Offline grind.** Attacker exfiltrates the encrypted backup blob (iCloud, Google Drive, BabbageWAB sync, or BRC-100 wallet sync). With no memory-hard KDF, a GPU farm grinds the passphrase. Plain HKDF/HMAC is ~10^8 attempts/sec on consumer GPUs.
- **Silent escrow collusion.** 2-of-3 escrows that collude silently reconstruct the wallet with zero on-chain or audit-log trace. No `tm_mpc_audit` event, no `EscrowReleaseAttempted`. The user has no signal until funds drain.
- **No rate-limit on online ceremony.** Even if grind is hard, repeated attempts against a recovery server without rate-limit is denial-of-service vector and brute-force surface.

BitGo recovery-tool exploit (2023) was a real-world case in this class.

## Decision

### 1. Memory-hard KDF for passphrase derivation (normative)

Recovery passphrase derivation MUST use **Argon2id** (RFC 9106), not plain HKDF or HMAC. Default parameters:

- `profile-server` (desktop / web wallet recovery): `m = 256 MiB, t = 3, p = 1`
- `profile-mobile` (mobile recovery flows where 256MiB is prohibitive): `m = 64 MiB, t = 4, p = 1`

The mobile profile trades reduced memory cost for higher iteration count, keeping the GPU/ASIC grinding cost approximately equivalent. Implementations MAY use scrypt (RFC 7914, N=2^17, r=8, p=1) for mobile as an alternative if Argon2id memory bound is infeasible (left as a design choice per Q29).

### 2. Per-blob random salt (normative)

Encrypted backup blobs MUST include a per-blob random `kdf_salt: bstr32`. The same passphrase across users / devices yields different KEKs. The salt is plaintext alongside the ciphertext.

### 3. Online unwrap ceremony (normative)

Backup unwrap MUST be a single online ceremony with the user's BRC-100 wallet that:

- **Rate-limits to ≤5 attempts per UTC hour**, enforced server-side at the BRC-100 wallet (not just client-side). Implementations MUST track attempts by user-identity (BRC-31 pubkey) AND by encrypted-blob-hash (so the rate-limit isn't bypassed by re-uploading the blob).
- **Emits an `AuditEntry`** with `event_kind = "RecoveryAttempted"` and outcome (`"Success"` | `"InvalidPassphrase"` | `"RateLimited"`) on each attempt — successful or not.
- **Witness-cosigns** the recovery event on `tm_mpc_audit` (§10.6 pattern) BEFORE producing share plaintext.

### 4. Escrow obligations (normative, applies to §18.5.2 Path 2)

For jurisdictional escrow:

- Each escrow release MUST be a §10 audit event published to `tm_mpc_audit` BEFORE the share plaintext is produced.
- Release request MUST be BRC-31-authenticated with a fresh per-attempt nonce signed by the user's BRC-100 wallet (defeats replay).
- Escrows MUST refuse silent release; a release-attempt notice on `tm_mpc_audit` is a precondition for the release ceremony.
- Escrow operators MUST individually verify caller identity (BRC-31 sender) and MUST throttle release attempts (≤3 per UTC day per user-identity).
- An m-of-n escrow MUST NOT enable silent collusion: any 1 honest escrow refusing release publishes an `EscrowReleaseRefused` event. An m-of-n release without a corresponding `EscrowReleaseAttempted` audit chain is itself an `audit-anomaly` requiring IR-005 escalation.

## Rationale

- **Argon2id memory-hardness defeats commodity GPU grinding.** 256MiB memory cost forces an attacker to use rare-and-expensive hardware (custom ASIC). Per-GPU throughput drops from 10^8 attempts/sec to ~10 attempts/sec.
- **Per-blob salt eliminates precomputation.** Rainbow tables across users / dictionaries become useless.
- **Rate-limited online ceremony makes silent grinding impossible.** Every attempt produces an audit event the user / operator can monitor. Sub-detection-threshold attacker activity becomes detectable.
- **Audit-mandated escrow.** Collusion among m-of-n escrows requires falsifying audit events, which §10.6 witness-cosigning catches. The release isn't silent.
- **Bounded UX impact.** Argon2id at desktop parameters takes ~1-2 seconds on commodity hardware. User-facing latency tradeoff is acceptable for a once-per-disaster recovery flow.

## Consequences

### `bsv-mpc` (Calhoun)

- Implement Argon2id-based KDF in `crates/bsv-mpc-core/src/recovery.rs` (or new module).
- Wire rate-limit enforcement into `bsv-mpc-service` recovery endpoint.
- Add `RecoveryAttempted` + `RecoveryAttemptOutcome` audit event kinds.
- ~250 LOC + integration tests.

### `rust-mpc` (Binary; impl Ishaan)

- Same KDF + rate-limit + audit additions in Binary's stack.
- If Binary's MPC client (Mitch transferring per partnership) hosts the user-side BRC-100 wallet recovery surface, the enforcement is there.

### `MPC-Spec`

- §18.5.1 + §18.5.2 expanded (already applied per this swarm's clear-win pass).
- Q29 added: Argon2id m=256MiB collision with mobile recovery; profile-conditional KDF design choice.
- Conformance test vector for known-passphrase → known-KEK derivation (Argon2id with pinned salt + parameters) added to `conformance/test-vectors/18-recovery-kdf.json`.

## Alternatives considered

- **PBKDF2 with 10M iterations.** Rejected — PBKDF2 is memory-cheap, GPU-friendly. Memory-hard is the correct primitive.
- **scrypt as default.** Considered but Argon2id is the current best-practice (RFC 9106, NIST SP 800-208 successor); scrypt allowed as mobile fallback per Q29.
- **No online unwrap (purely offline).** Rejected — gives up rate-limit + audit-event surface. Silent grinding becomes possible.
- **Hardware-bound (TEE/HSM) recovery key wrapping.** v2 reopens (ADR-0016 deferred); not v1.

## Status of M1 dependency

**v1.5.** Catastrophic recovery is not exercised by the M1 cross-impl signing demo (M1 demonstrates standard signing on healthy quorum). Spec edit lands in M2 window (2026-06-12) with implementation pre-Notary-MVP.

## See also

- Spec: [§18.5](../18-recovery.md), [§10.6](../10-audit.md) (witness-cosigning pattern)
- RFC 9106 (Argon2id)
- RFC 7914 (scrypt)
- 2026-05-13 swarm: Security S2
- Reference: BitGo recovery-tool exploit (2023)

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
