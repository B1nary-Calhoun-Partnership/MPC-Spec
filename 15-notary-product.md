# 15 — Notary Product

**Status:** DRAFT
**Phase:** 3
**Decided by:** ADR-0015 (proposed)
**Last updated:** 2026-05-10

## 15.1 What a Notary is

A **Notary** is a publicly discoverable cosigner that participates in user-controlled `t`-of-`n` key shares for a per-signature fee. The user is always majority of their own quorum; the Notary is fungible.

The Notary product competes directly with Fireblocks' custodial product, with structurally lower per-signature cost (3-4 OOM lower) due to the absence of custody liability.

## 15.2 Three product tiers (preserved as deployment archetypes)

### 15.2.1 Default — Paid Cosigner in 2-of-3

User holds 2 shares (one device + one passkey-encrypted backup via WebAuthn PRF), Notary holds 1.

- Per-sig fee: 333 sats × 3 nodes = **1000 sats default** (~$0.0002 at $50/BSV).
- **Single DKG ceremony** for onboarding.
- Cold-start: <1 sec over WebSocket.
- L2 P2MS fee output (§11).
- Weekly settlement.
- Recovery: threshold resharing + new Notary, 0 sats on-chain, no address change.

This is the default offering. Most users want this.

### 15.2.2 Express — x402 paid signing oracle

No DKG, custodial Notary, BRC-29/x402 micropayment per call.

- Strictly worse Lit Protocol PKP for security — sub-cent per signing for low-value AI agents that accept custody risk.
- Same Notary infrastructure runs both tiers; user opts in.
- Per-sig: 100-500 sats (lower than Default; reflects sub-cent value transactions).
- Useful for ephemeral agent use cases where DKG overhead exceeds the value transacted.

### 15.2.3 Pro — Multi-Notary 2-of-5 marketplace

User holds 3 shares; 2 Notaries hold the other 2 of 5, drawn from a pool of 10+ overlay-registered Notaries. Wallet picks cheapest 2 healthy per signing.

- Maximum vendor-neutrality + Sybil resistance.
- Slow onboarding (5-of-5 DKG with strangers).
- 90-day graduation path post-MVP.

## 15.3 Notary BRC-100 endpoint surface (minimum)

A Notary MUST expose:

| Endpoint | Purpose |
|---|---|
| `GET /health` | Liveness probe. |
| `GET /capabilities` | Notary's capability JSON (mirrors CHIP token, served via HTTPS). |
| `POST /api/session/dkg-init` | Initiate DKG with this Notary as one party. |
| `POST /api/session/dkg-round` | Process DKG round messages. |
| `POST /api/session/sign-init` | Initiate signing with cached presig if available. |
| `POST /api/session/sign-round` | Process signing round messages. |
| `POST /api/session/presign-init` | Initiate presigning. |
| `POST /api/session/presign-round` | Process presigning round messages. |
| `POST /api/session/ecdh` | Process partial-ECDH for BRC-42 derived signing. |
| `GET /api/cosigner/<id>` | Cosigner share metadata (BRC-31 auth required). |

Notaries do NOT need full BRC-100 wallet endpoints (`createAction`, `internalizeAction`, `listOutputs`, `listActions`, certificate flows, key linkage). The Notary is a co-signing co-party, not a wallet.

bsv-mpc-service is essentially this Notary surface today (9 protocol handlers + health + share metadata). Extend it with `/capabilities`.

## 15.4 SDK surface

Integrators (Tauri client, browser wallet, mobile wallet, server agent) call:

```typescript
// TypeScript
const notaries = await mpc.discover({ maxFeeSats: 1000, threshold: '2-of-3', region: 'US' });
const { jointPubkey } = await mpc.onboard({ notary: notaries[0], userShares: 2 });
const { signedTx, feeReceipt } = await mpc.sign({ tx, jointPubkey });
await mpc.replaceNotary({ jointPubkey, newNotary: notaries[1] });  // resharing
const restored = await mpc.recover({ passkey, jointPubkey });
```

```rust
// Rust
let notaries = mpc::discover(DiscoverOpts { max_fee_sats: 1000, threshold: "2-of-3", region: "US" }).await?;
let joint_pubkey = mpc::onboard(OnboardOpts { notary: &notaries[0], user_shares: 2 }).await?;
let (signed_tx, fee_receipt) = mpc::sign(&tx, &joint_pubkey).await?;
mpc::replace_notary(&joint_pubkey, &notaries[1]).await?;
let restored = mpc::recover(&passkey, &joint_pubkey).await?;
```

Five methods. Anything else is internal to the wallet's BRC-100 surface.

## 15.5 Onboarding UX

Cold-start (default tier):

1. User's wallet (Tauri/browser) calls `discover(filter)`, gets ranked list.
2. User picks (or wallet auto-picks #1 by reputation × cheapest).
3. Wallet runs **single 2-of-3 DKG** ceremony. The "node fee pool" DKG mentioned in BRC-mpc-fees draft is a one-time setup *between operators*, not a per-user concern.
4. Wallet stores share A locally + share B in passkey-encrypted iCloud/Google backup (WebAuthn PRF).
5. Notary holds C.
6. Wallet displays joint pubkey + BSV address; user is ready to fund.

Total time: ~1 second over WebSocket, ~2 seconds over HTTP poll.

## 15.6 Recovery UX

**Notary disappears or compromise suspected:**

1. User authenticates via passkey on second device (recovers share B).
2. Wallet runs key-refresh + DKG with a *new* Notary (POC 13: same joint key, no on-chain move, 0 sats).
3. New Notary holds C'; old Notary's C invalidated by resharing polynomial.
4. Wallet adds bad CHIP identity to local denylist + publishes abort proof to overlay (if compromise).

**No funds move; no address changes.**

**Two of three fail simultaneously:**

User invokes catastrophic recovery via §18. Out of normal Notary flow.

## 15.7 Trust-on-first-use

For an unknown Notary discovered via overlay, the wallet MUST verify (per §12.6):

1. CHIP token PushDrop signature.
2. Capabilities JSON.
3. Policy manifest hash matches `policy_hash`.
4. Cert chain to an accepted root.
5. ≥30-day on-chain age + ≥10 successful settlements.

Failing any check → reject. Passing → proceed to DKG.

## 15.8 Notary as a policy

Every Notary publishes a **PolicyManifest** (§09) signed by its identity key. Manifests bind the Notary to:

- What protocols it will sign for (`protocol_pattern`).
- Maximum amount per signing (`max_amount_sats`).
- Rate limit per hour (`max_per_hour`).
- Minimum fee it requires (`min_fee_sats`).
- Approval requirements above thresholds (`require_approval`).

Notaries with stricter policies typically charge more. The manifest is the contract.

## 15.9 Economic model

| Provider | Per-sig cost (USD, $50/BSV) | Custody model |
|---|---|---|
| Fireblocks Essentials | ~$0.10–$2.00 effective | Custodial |
| Fireblocks Custom | ~$0.50–$5.00 amortized | Custodial |
| Coinbase CDP MPC | bundled-into-Base | Custodial / partial |
| Lit Protocol PKP | ~$0.001-0.01 (RPS-credits) | Custodial / threshold |
| **This network — Default tier** | **~$0.0002** | **Non-custodial (user holds 2-of-3)** |
| **This network — Express tier** | ~$0.00005 | Custodial |

The Default tier is 3-4 orders of magnitude cheaper than Fireblocks because the Notary has no custody liability. Fireblocks structurally cannot follow without giving up its compliance product.

## 15.10 Notary host: bsv-mpc-service vs rust-mpc-backend

For v1 MVP, **bsv-mpc-service is the recommended Notary host**:

- Production KSS already deployed (CF Worker, $5/mo, 16ms RTT, validated POC 10).
- Fee infrastructure validated end-to-end on mainnet (POC 7, POC 11).
- Overlay discovery wired to BSV SDK `LookupResolver` (POC 14).
- WASM-clean for global edge deployment.
- Smaller surface area than rust-mpc backend (single-purpose Notary vs full wallet).

Strategy: host the Notary on bsv-mpc-service, port rust-mpc's `StandardPolicyEngine` into bsv-mpc-core as the cosigner gate.

This is a v1 deployment recommendation, not a spec requirement. Both implementations CAN host Notaries.

## 15.11 Implementation notes

- bsv-mpc-service — minimum viable Notary surface. Extend with `/capabilities`.
- bsv-mpc `fee_injector.rs` — fix L2 default (§11).
- bsv-mpc `proofs.rs::publish_proof / query_proofs` — un-stub (§10).
- bsv-mpc `chip.rs::revoke_chip_token` — implement (§12).
- bsv-mpc `bsv-mpc-overlay/src/discovery.rs` — un-stub `query_proofs` for reputation.
- Port `StandardPolicyEngine` from rust-mpc to bsv-mpc as `mpc-policy-shared`.
- Add `min_fee_sats` rule to both implementations' policy engines.

## 15.12 Test vectors

`conformance/test-vectors/15-notary.json`. End-to-end:
- Onboard a user with a Notary; verify joint pubkey computation.
- Sign a tx; verify fee output is L2 P2MS.
- Replace a Notary; verify joint pubkey unchanged.
- Recover from passkey backup; verify shares restored.

## See also

- [`decisions/0015-notary-product-tiers.md`](decisions/0015-notary-product-tiers.md) — ADR.
- [`09-policy.md`](09-policy.md) — Notary publishes its policy manifest.
- [`11-fees.md`](11-fees.md) — fee economics.
- [`12-discovery.md`](12-discovery.md) — discovery + reputation.
- [`18-recovery.md`](18-recovery.md) — recovery flows.
- [`appendices/swarm-reports/E-notary-product.md`](appendices/swarm-reports/E-notary-product.md) — full design rationale.
