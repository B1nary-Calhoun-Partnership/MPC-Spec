# ADR-0030: Presignature lifecycle — cosigner-encrypted shares stored at coordinator

**Status:** Proposed
**Date:** 2026-05-12
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** Mitch Burcham (Binary partnership) — designed the coordinator-encrypted presig storage model; Ishaan Lahoti (Binary partnership) — implemented it in `rust-mpc/crates/brc42/src/presig_encryption.rs` and `crates/coordinator/src/presign.rs`. Confirmed in the 2026-05-12 partnership sync as the canonical model.

## Context

CGGMP'24 presignatures are the fast-path enabler: with a valid presig, signing collapses from 4 rounds to 1 round (§06.10 latency budgets). To sustain the fast path, cosigners must continuously generate presigs at a rate that meets the wallet's signing burn rate.

Two design choices were open:

1. **Where the presig material lives between generation and consumption.**
   - Option A: each cosigner stores its own share locally; coordinator stores only its share.
   - Option B: each cosigner encrypts its share to itself, ships the ciphertext to the coordinator, and the coordinator holds the encrypted blob alongside its own plaintext share.

2. **Who decides when to regenerate.**
   - Option A: cosigners self-pace based on local heuristics.
   - Option B: coordinator computes a burn-rate-driven schedule and triggers presigns.

Mitch's `rust-mpc` implementation has been running Option B + Option B for several months. It removes the need for the coordinator to sync presig state across cosigners (the coordinator IS the single state holder), trades a small storage cost for a large operational simplification, and keeps the security property that no party can read another party's share at rest.

The 2026-05-12 partnership sync agreed to make this the spec-canonical lifecycle.

## Decision

The presignature lifecycle SHALL be:

### Generation (3-round cggmp24 presign)

1. The coordinator runs the standard cggmp24 3-round presigning protocol with the chosen cosigner subset (§01).
2. At the end of round 3, each cosigner holds its own `tilde_chi_i` (presig share) plus public commitment data (`tilde_Delta_j`, `tilde_S_j`).

### Encryption (cosigner side)

3. Each cosigner MUST encrypt its presig share to itself using **BRC-2 self-encryption via the ProtoWallet `encrypt()` API**, with:
   - `counterparty = CounterpartyType::Self_`
   - `protocol_id.security_level = 2`
   - `protocol_id.protocol = "mpcpresig"` (BRC-43-compliant protocol name; no hyphens)
   - `key_id = presig_id` (the unique presigniture identifier — typically the presign session id)

   This produces a unique encryption key per presig (the key_id differs), derived deterministically from the cosigner's wallet identity. The wallet handles BRC-42 invoice canonicalization (per §03), ECDH-self shared-secret derivation, and AES-256-GCM encryption internally.

4. The cosigner MUST send the encrypted ciphertext to the coordinator via a dedicated return mailbox (`presig_return_{session_id}` in `rust-mpc`'s implementation). The mailbox name MUST be allocated by the coordinator at presign-session init and conveyed to each cosigner via the presign `MpcOp` envelope.

5. The cosigner MUST delete its plaintext share from local memory immediately after the ciphertext is acknowledged by the coordinator (best-effort zeroize).

### Storage (coordinator side)

6. The coordinator MUST construct and persist a `PresigBundle`:

```rust
struct PresigBundle {
    presig_id: String,                  // unique per presig (== presign session_id)
    presig_bytes: Vec<u8>,              // coordinator's OWN serialized presig share (plaintext)
    cosigner_encrypted_share: String,   // hex-encoded BRC-2 ciphertext from cosigner
    gamma_hex: String,                  // shared Gamma commitment
    commitments: Vec<u8>,               // serialized PresignaturePublicData commitments
}
```

7. The coordinator MUST NOT attempt to decrypt the cosigner's ciphertext at storage time. The ciphertext is opaque to the coordinator until signing-time consumption (when the cosigner is online and can decrypt with its own wallet).

8. Storage MUST be encrypted at rest. The coordinator's plaintext `presig_bytes` field is the coordinator's own share — equivalent in sensitivity to its DKG key share — and inherits the same at-rest protection.

### Consumption (signing)

9. At sign-time, the coordinator MUST send the cosigner's stored `cosigner_encrypted_share` back to the cosigner along with the BRC-42 derivation offset and message-to-sign. The cosigner decrypts via the inverse BRC-2 self-decryption (same protocol_id + key_id), then applies the BRC-42 additive shift per §03.8 / `crates/brc42/src/presignature.rs::apply_brc42_offset`, then emits its signature share.

10. A presig is single-use. Once consumed (the cosigner has applied the offset and shipped its sigma share), the coordinator MUST mark the bundle as consumed and remove it from the available pool.

### Burn-rate regeneration

11. The coordinator MUST track per-`(joint_pubkey, cosigner_subset)` presig consumption and trigger regeneration in parallel before the available pool drops below a configured low-water mark.

**The baseline burn-rate algorithm is normative (per 2026-05-13 divergence-risk swarm) unless deviation is published in the operator's CHIP capabilities JSON** (per §12.3) as `burn_rate_algorithm: "<variant-name>"` with a public description URL. Default baseline:

- **Burn rate** = exponentially-weighted moving average of presig consumptions/sec over the last N=60 seconds.
- **Target pool size** = `max(8, ceil(burn_rate * 30))` (30-second runway).
- **Trigger** = launch new presign sessions in parallel whenever the available pool falls below `0.5 * target_pool_size`.
- **Cap** = no more than `target_pool_size * 2` presigs in storage at any time, to bound storage cost and rotation surface.

Operators that deviate from the baseline without publishing in their CHIP capabilities are non-conformant. The `/capabilities` declaration is checked daily by the CI drift-watch workflow (per `~/bsv/mpc/swarm-2026-05-13/collab-tracking.md` §7 + `collab-divergence-risk.md` §5).

12. Multiple parallel presign sessions on different threads/tasks are RECOMMENDED to amortize round-trip latency. Each parallel session uses its own `presig_id` / session_id; sessions are independent.

### Deletion (mandatory invalidation)

13. The coordinator MUST delete all stored `PresigBundle` rows whenever ANY of the following occurs:
    - **Share refresh** (per §18): a successful refresh ceremony invalidates all presigs derived from the pre-refresh shares. Implementations MUST delete the entire bundle pool atomically on refresh commit.
    - **Cosigner subset change**: a presig is bound to the `parties_at_keygen` it was generated for. If the active subset changes (e.g., one cosigner is removed or replaced per §13.7), all bundles bound to the prior subset MUST be deleted.
    - **Policy manifest update**: any change to the PolicyManifest (§09) — including amount caps, protocol whitelist, rate limits — invalidates all bundles bound to the prior `policy_id`. The coordinator MUST track which `policy_id` each bundle was generated under (RECOMMENDED: as an additional field in `PresigBundle`) and delete bundles whose `policy_id` no longer matches the current manifest.
    - **Joint pubkey change** (e.g., post-recovery rekeying): all bundles for the prior joint_pubkey MUST be deleted.

14. Deletion MUST be best-effort zeroize. Storage backends MUST overwrite the rows; pure mark-as-deleted (without erasure) is non-conformant.

### Mailbox lifecycle

15. The `presig_return_{session_id}` mailbox MUST be deleted by the coordinator after the cosigner's encrypted share is acknowledged. Stranded mailboxes (cosigner never replied within the timeout) MUST be garbage-collected by the coordinator after a configurable expiry (RECOMMENDED: 5 minutes).

## Rationale

### Security

- **No party can read another party's presig share at rest.** Coordinator holds only its own plaintext + cosigner ciphertext. A coordinator compromise leaks the coordinator's share (same as DKG key compromise) but does NOT leak cosigner shares. A cosigner compromise leaks only that cosigner's share.
- **Single state holder eliminates sync race conditions.** Coordinator is canonical; no two-phase commit or distributed locking between cosigners needed for presig pool state.
- **Deletion-on-policy-change closes the "stale presig with stale policy" gap.** A presig generated under a permissive policy cannot be consumed under a stricter policy — both because the bundle is deleted at policy-update time and because the signing-time policy check re-validates against the current manifest.
- **Single-use enforcement at the coordinator** removes the CVE-2025-66017-class attack surface (presignature forgery via altered presigs). The coordinator marks consumed; replay attempts get no bundle. Defense-in-depth with the cosigner-side ZK consistency checks.

### UX

- **Sub-second signing on the warm path** (~50 ms at 50 ms RTT on WebSocket): the bundle is already in the coordinator; sign-time round-trip is just "fetch bundle, ship encrypted share + offset + message to cosigner, receive sigma share." One round.
- **Cold-start signing falls back to the 4-round path** (~400 ms): no degradation when the pool is empty; the system self-heals via burn-rate regen.
- **No user-visible state.** Burn rate adapts to actual usage; no manual configuration required.

### Operability

- **Coordinator failure model is well-understood.** Coordinator is online + stateful; cosigner can be intermittently offline (only needs to be online during ceremony rounds and at sign-time decrypt). Matches the "MessageBox is always online; cosigner has wakeup discipline" pattern from §06.
- **Pool sizing is observable.** Burn rate + pool size + regen latency are first-class metrics for operations dashboards (§16.6 OTel).

### Vendor-neutrality, composability

- Vendor-neutral: BRC-2 self-encryption is a standard wallet primitive available to any BRC-100-compliant wallet. Both `bsv-mpc` and `rust-mpc` cosigners can adopt without protocol changes.
- Composable: the `PresigBundle` shape is wire-stable (CBOR-encoded for any cross-instance migration). Operator replacement (§13.7) can hand off bundle storage along with coordinator state.

## Consequences

### `rust-mpc` (Binary)

- **No code change.** `crates/brc42/src/presig_encryption.rs`, `crates/brc42/src/presignature.rs`, `crates/coordinator/src/presign.rs` already implement this design. Documentation pointing to ADR-0030 SHOULD be added in those modules' rustdoc.

### `bsv-mpc` (Calhoun)

- **Implement presign-over-MessageBox path** (currently the proxy/KSS topology does in-process presigning per POC results).
- **Implement BRC-2 self-encryption of presig shares** using `ProtoWallet` (the same primitive `rust-wallet-toolbox` exposes).
- **Implement `PresigBundle` coordinator storage** with at-rest encryption + per-`policy_id` indexing for the deletion rules.
- **Implement burn-rate-driven regen loop.**
- ~600-900 LOC in `bsv-mpc-core` / `bsv-mpc-service` / a new `bsv-mpc-presig` crate. Reuses BRC-42 and CGGMP'24 primitives already integrated.

### `MPC-Spec`

- **§06 extended** with §06.15–§06.20 (presignature lifecycle subsections) — this is the normative spec text.
- **§09 cross-reference added** at the policy-update procedure: "policy update MUST trigger presig invalidation per §06.18."
- **§18 cross-reference added** at refresh: "refresh commit MUST trigger presig invalidation per §06.18."
- **OPEN-QUESTIONS Q3** updated: the "presigning over MessageBox" question now has its canonical resolution in §06.15+; this ADR closes Q3.

## Alternatives considered

- **Each cosigner keeps its own presig store.** Rejected: requires distributed sync between cosigners, surfaces inconsistency races, and forces every cosigner to be online during burn-rate decisions. Simpler than the chosen design only at first glance — the sync logic eats the savings and adds attack surface.
- **Coordinator holds plaintext cosigner shares.** Rejected: a coordinator compromise then leaks every cosigner's share. The encryption overhead is small (AES-256-GCM on ~100-byte blobs); the security benefit is large.
- **Push deletion responsibility to cosigners on policy update.** Rejected: cosigners may be offline at policy-update time; bundle invalidation must happen at the canonical state holder (coordinator) immediately. Cosigners learn of the change at next ceremony.
- **Self-pacing regeneration (no coordinator-side schedule).** Rejected: each cosigner would need to model burn rate independently; pool sizing would drift. Coordinator has the consumption signal natively.

## Open implementation question

The recommended burn-rate algorithm (§11 of this ADR's spec text) is a baseline. Implementations MAY tune the EWMA window, low-water threshold, and cap multipliers. Different deployment profiles (high-volume Notary vs. low-volume personal vault) may warrant different tunings. Spec text in §06.18 leaves the algorithm as "RECOMMENDED baseline, MAY substitute."

## See also

- Spec: [`§06-transport.md`](../06-transport.md) §06.15-§06.20 (normative spec text)
- Spec: [`§09-policy.md`](../09-policy.md) (policy-update invalidation cross-ref)
- Spec: [`§18-recovery.md`](../18-recovery.md) (refresh invalidation cross-ref)
- Open question: [`OPEN-QUESTIONS.md` Q3](../OPEN-QUESTIONS.md) — resolved by this ADR
- Reference implementation: `rust-mpc/crates/brc42/src/presig_encryption.rs`, `crates/brc42/src/presignature.rs`, `crates/coordinator/src/presign.rs`
- BRC-2 (wallet encrypt/decrypt primitives), BRC-42 (key derivation; consumed via BRC-2 internally), BRC-43 (protocol name format — `mpcpresig` is BRC-43-compliant)
- CVE-2025-66017 (presignature forgery; single-use enforcement is the spec-level mitigation)

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (Mitch Burcham)
