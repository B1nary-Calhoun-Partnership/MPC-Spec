# 18 — Recovery

**Status:** DRAFT
**Version:** v1
**Phase:** 2
**Decided by:** ADR-0018 (proposed)
**Last updated:** 2026-05-10

## 18.1 Three recovery paths

| Scenario | Mechanism | On-chain cost |
|---|---|---|
| Routine refresh (30-day cadence) | Threshold resharing (POC 13) | 0 sats |
| Single party loss/compromise | Party replacement via resharing | 0 sats |
| Threshold change (Hot ↔ HotPlusCold ↔ ColdOnly) | Cross-(t,n) resharing | 0 sats |
| Catastrophic recovery (quorum loss) | Encrypted backup + jurisdictional escrow | Variable |

The first three preserve the joint pubkey (same on-chain BSV address; no funds move). The last is the genuine "lost the keys" recovery.

## 18.2 Threshold resharing (POC 13)

CGGMP'24 supports resharing primitives natively. Both implementations expose:

- `reshare_routine(participants, t, n)` — same `(t, n)`, fresh polynomial. 30-day cadence (§16, RR-001).
- `reshare_replace_party(old, new, participants, t, n)` — same `(t, n)`, swap one identity. Operator replacement (§13.7).
- `reshare_change_threshold(old_t, old_n, new_t, new_n, participants)` — cross-(t,n) transition. Quorum profile transitions.

All three preserve the joint pubkey. Cost on-chain: 0 sats. Cost off-chain: ~1 second on WebSocket transport.

## 18.3 Quorum profiles

```
QuorumProfile = "Hot" | "HotPlusCold" | "ColdOnly"
```

- **`Hot`**: 2-of-3 across hot cosigners (TEE-hosted edge / server). Sub-second signing. Routine.
- **`HotPlusCold`**: 2-of-5, where {2 hot, 1 hot, 0 hot, 1 cold (HSM), 1 cold (HSM)}. Daily / weekly signing. The hot subset (2-of-3) signs; cold tier participates only in resharing/recovery.
- **`ColdOnly`**: 2-of-2 cold (HSM). Vault tier, no daily signing. Used by institutional users / treasuries.

Users transition between profiles via `reshare_change_threshold`. **No on-chain transactions, no address changes.** This is unique to BSV-MPC; Fireblocks fixes threshold at vault creation.

Profile transition example:
```
Hot (2-of-3) → HotPlusCold (2-of-5):
  - User invokes mpc.reshare(joint_pubkey, new_profile = "HotPlusCold").
  - Existing 3 hot cosigners + 2 cold cosigners run a 5-party resharing.
  - Old shares die; new (t=2, n=5) shares live.
  - Joint pubkey preserved.
```

## 18.4 Encrypted backup (default user-side)

Each user's wallet stores share B (the second-of-three) encrypted with a key derived from the user's WebAuthn passkey PRF.

```
backup_key   = hkdf_extract(passkey_prf_output, "mpc-backup-v1")
share_B_enc  = AES-256-GCM(backup_key, share_B || metadata)
```

Stored in iCloud / Google Drive / similar synced storage. Restorable from any device the user has paired their passkey with.

Recovery flow:
1. User's primary device fails.
2. User authenticates passkey on second device.
3. PRF re-derives `backup_key`.
4. Decrypts `share_B`.
5. User now has 2 of 3 (their device share + restored backup); can sign.

## 18.4a Recovery health indicator (normative UX, per ADR-0034)

The wallet MUST expose a `recovery_health` query (callable via the wallet's BRC-100 surface; also surfacable as an always-on UI indicator) returning the following fields for all three §18 recovery paths:

```
RecoveryHealth = {
    passkey_present: bool,                      // §18.5.1 Path 1 — encrypted backup KEK derivability
    backup_synced_age_secs: u64,                // freshness of the user's BRC-100 wallet sync
    trustees_reachable: { current: u8, total: u8 },  // §18.5.2 escrows / §18.6 trustees pingable
    last_refresh_age_days: u32,                 // §16.5.1 routine refresh recency
    overall_status: tstr,                       // "healthy" | "degraded" | "critical"
}
```

Per-field freshness thresholds (RECOMMENDED defaults; operator may tighten):

- `healthy`: passkey_present=true AND backup_synced_age_secs<3600 AND trustees_reachable.current ≥ ceil(total/2)+1 AND last_refresh_age_days<35
- `degraded`: any one threshold breached
- `critical`: passkey_present=false OR trustees_reachable.current<2 (recovery quorum at risk) OR last_refresh_age_days>60

The wallet SHOULD surface the `overall_status` as a persistent indicator (green/yellow/red). ZenGo's "always-on recovery health" UX is the reference precedent.

A `critical` status MUST trigger an in-app onboarding flow nudging the user to repair the recovery posture (re-sync backup, re-provision trustees, force refresh). Wallets that hide `critical` status from users are non-conformant.

## 18.5 Catastrophic recovery (case (c) of §16.6)

**Scenario:** two of three cosigners simultaneously fail. User has share A, but B and C are both gone.

Recovery requires *adding new shares* without breaking the joint pubkey. This is possible via threshold resharing if at least `t` shares exist, but with only 1 share remaining, resharing alone is insufficient.

The user MUST have prepared one of:

### 18.5.1 Path 1 — Encrypted backup at user's BRC-100 wallet

User pre-encrypts shares B and C with a recovery passphrase. Backup is at the user's primary BRC-100 wallet (e.g., BabbageWAB). Recovery:
1. User authenticates the BRC-100 wallet via standard means.
2. Wallet decrypts B and C with the passphrase.
3. User now has 3 of 3; provisions new cosigners; runs resharing to fresh `(2, 3)`.

This is the **default** recovery path for the Default product tier (§15).

**Normative parameters (per ADR-0038, proposed):**

- **Memory-hard KDF.** Recovery passphrase derivation MUST use Argon2id (NOT plain HKDF / HMAC). Default parameters:
  - `profile-server`: `m = 256 MiB, t = 3, p = 1`
  - `profile-mobile`: `m = 64 MiB, t = 4, p = 1`
- **Per-blob random salt.** Encrypted backup blobs MUST include a per-blob random `kdf_salt: bstr32`. Same passphrase across users / devices yields different KEKs.
- **Online unwrap ceremony.** Backup unwrap MUST be a single online ceremony with the user's BRC-100 wallet that:
  - Rate-limits to **≤5 attempts per UTC hour**, enforced server-side at the BRC-100 wallet (not just client-side).
  - Emits an `AuditEntry` with `event_kind = "RecoveryAttempted"` and outcome (`"Success"` | `"InvalidPassphrase"` | `"RateLimited"`) on each attempt — successful or not.
  - Witness-cosigns the recovery event on `tm_mpc_audit` (§10.6 pattern) before producing share plaintext.

**Rationale.** Plain HKDF / HMAC + offline backup + no rate-limit = offline-grindable single-passphrase KEK. Memory-hard Argon2id makes the GPU-grind expensive; rate-limited online ceremony makes silent grinding impossible (every attempt produces an audit event the user/operator can monitor). The whole MPC threshold collapse to "user types passphrase" must not become a soft underbelly. See [ADR-0038](decisions/0038-memory-hard-recovery-kdf.md).

### 18.5.2 Path 2 — Jurisdictional escrow

For high-value users, shares are pre-encrypted to *jurisdiction-distributed escrow agents*. The user must convince `m` of `n` jurisdictional escrows to release.

Example: 3-of-3 escrow split: USA escrow + EU escrow + Asia escrow. Each holds an encrypted share that decrypts only with the user's recovery passphrase + escrow's release key.

This is **opt-in** for power users; not part of the Default tier.

**Normative escrow obligations (per ADR-0038):**

- Each escrow release MUST be a §10 audit event published to `tm_mpc_audit` BEFORE the share plaintext is produced.
- Release request MUST be BRC-31-authenticated with a fresh per-attempt nonce signed by the user's BRC-100 wallet (defeats replay).
- Escrows MUST refuse silent release. A release-attempt notice on `tm_mpc_audit` is a precondition for the release ceremony; absence of the notice is itself an `audit-anomaly`.
- Escrow operators MUST individually verify caller identity (the BRC-31 sender) and MUST throttle release attempts (≤3 per UTC day per user-identity).
- An m-of-n escrow MUST NOT enable silent collusion: any 1 honest escrow refusing release publishes an `EscrowReleaseRefused` event; m-of-n release without a corresponding `EscrowReleaseAttempted` audit chain is a detectable anomaly.

## 18.6 Nested-MPC social recovery

For users who want trustless social recovery, the recovery passphrase itself can be threshold-shared among trustees:

1. User picks `m` trustees (friends, family, advisors).
2. Recovery passphrase is split via Shamir's secret sharing or threshold MPC into `n` shares, requires `k` of `n` to reconstruct (e.g., 3-of-5).
3. Trustees each hold one share.
4. On catastrophic loss, user contacts `k` trustees; trustees collectively co-sign a recovery transaction.
5. The "recovery transaction" is itself a threshold MPC ceremony among trustees. Recursive.

Status: out of v1 scope; spec defines the primitive; UX is post-v1.

## 18.7 IR-009 runbook (catastrophic recovery)

```
T+0:    User invokes recovery flow on remaining device.
        Shows: "Quorum loss detected. Provide recovery passphrase."

T+5m:   User enters passphrase.
        Wallet decrypts backup shares (Path 1) or contacts escrow agents (Path 2).

T+30m:  All shares restored.

T+60m:  User picks new cosigners via overlay discovery.
        Wallet runs DKG with new cosigners → new (t,n) → same joint pubkey via resharing.

T+90m:  Old cosigner CHIP tokens revoked.
        New cosigners' CHIP tokens published.
        Wallet operational.
```

Total time bounded by user response. No on-chain transactions required for recovery itself.

## 18.8 Forbidden

- Recovery flows that move funds (to a new joint pubkey). Any such flow violates the "preserve joint pubkey" property. Use resharing.
- Single-party recovery (any one party can independently restore). The threshold property MUST be preserved.
- Storing recovery passphrase in plaintext anywhere — always BRC-42-derived encryption.

## 18.9 Implementation notes

- bsv-mpc-core `crates/bsv-mpc-core/src/refresh.rs` — implements POC 13 routine refresh. Extend with `reshare_replace_party` and `reshare_change_threshold`.
- WebAuthn PRF integration is browser/Tauri client work — not in either MPC implementation directly. Spec defines the interface.
- BRC-100 wallet integration for encrypted backup is the wallet layer's responsibility, not MPC's.
- Recovery passphrase derivation uses BRC-42 protocolID `[2, "mpc recovery"]` for HKDF input.
- **Presig invalidation at refresh commit.** Every successful refresh ceremony (routine resharing per §18.2, party replacement per §18.3, threshold change per §18.4, or catastrophic recovery per §18.5) MUST trigger the presig invalidation rules in §06.18. The coordinator MUST delete all `PresigBundle` rows for the affected `joint_pubkey` atomically with the refresh commit; bundles MUST NOT be consumable across the refresh boundary. Implementations SHOULD trigger immediate burn-rate-driven regeneration (§06.19) post-refresh to restore pool depth.

## 18.10 Test vectors

`conformance/test-vectors/18-recovery.json`. Examples:
- Routine refresh: same joint pubkey, new shares verifiable, old shares cryptographically dead.
- Party replacement: new identity participates, old identity excluded.
- Threshold change: 2-of-3 → 2-of-5, joint pubkey unchanged.
- Catastrophic recovery: 1 share remaining → restore from backup → new 3-share state.

## See also

- [`decisions/0018-recovery-three-paths.md`](decisions/0018-recovery-three-paths.md) — ADR.
- [`13-federation.md`](13-federation.md) — operator replacement uses resharing.
- [`16-operations.md`](16-operations.md) — refresh choreography RR-001 / IR-002.
- [`OPEN-QUESTIONS.md` Q9](OPEN-QUESTIONS.md) — recovery-key escrow strategy.
