# 18 — Recovery

**Status:** DRAFT
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

### 18.5.2 Path 2 — Jurisdictional escrow

For high-value users, shares are pre-encrypted to *jurisdiction-distributed escrow agents*. The user must convince `m` of `n` jurisdictional escrows to release.

Example: 3-of-3 escrow split: USA escrow + EU escrow + Asia escrow. Each holds an encrypted share that decrypts only with the user's recovery passphrase + escrow's release key.

This is **opt-in** for power users; not part of the Default tier.

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
