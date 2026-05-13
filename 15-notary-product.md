# 15 — Notary Product

**Status:** DRAFT
**Version:** v1
**Phase:** 3
**Decided by:** ADR-0015 (proposed)
**Last updated:** 2026-05-10

## 15.1 What a Notary is

A **Notary** is a publicly discoverable cosigner that participates in user-controlled `t`-of-`n` key shares for a per-signature fee. The user is always majority of their own quorum; the Notary is fungible.

The Notary product competes directly with Fireblocks' custodial product, with structurally lower per-signature cost due to the absence of custody liability. The economic moat is **scenario-conditional** (per ADR-0036): **3-4 OOM cheaper at sustained ≥1M sigs/mo aggregate volume**; **narrows to 1-2 OOM** at low-volume or regulated-tier configurations; **can invert for self-hosted single-cosigner below ~50 sigs/mo** where fixed cost dominates marginal BSV fee. See §15.9 for the full moat-by-scenario table.

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

**Custody disclosure (normative, per CHANGES-PROPOSED #4 / ADR-0036):**

Express tier is **CUSTODIAL** — the operator holds the signing key. This is a fundamentally different security model than Default tier (where the user holds 2-of-3 shares). Wallets MUST surface this clearly:

#### 15.2.2.1 First-use consent flow (normative)

Before the user's FIRST Express-tier signing, the wallet MUST display a consent flow:

```
Express tier is a CUSTODIAL signing oracle.
The Notary operator holds the signing key.
If the operator is compromised, your Express-tier signatures
may be forged. This tier is appropriate for sub-cent transactions
where DKG overhead exceeds value.

Default tier (non-custodial, 2-of-3) is RECOMMENDED for all
transactions above sub-cent value.

Type "I understand" to enable Express tier signing for this account.
[I understand][Cancel]
```

The user MUST type the operator-localized equivalent of "I understand" (NOT just tap a checkbox) — captured intent is the consent record. Consent emits an `AuditEntry` with `event_kind = "ExpressTierEnabled"` recording the user-identity + operator-identity + timestamp.

#### 15.2.2.2 Tier-comparison table at every sign-time (normative)

For every Express-tier signing (UNTIL the user dismisses-permanently with a separate consent step), the wallet MUST display a tier-comparison side-by-side:

| Property | Default tier | Express tier (current) |
|---|---|---|
| Custody | Non-custodial (user holds 2-of-3) | **CUSTODIAL** (operator holds key) |
| Operator-compromise impact | Survives (user holds quorum) | **Catastrophic** (sig forgery possible) |
| Per-sig fee | ~1000 sats | 100-500 sats |
| Audit trail | PushDrop STH chain per cosigner | Operator's audit log only |
| Recovery | Threshold refresh + new Notary | Operator-side only |
| Suitable for | All transaction values | Sub-cent value only |

A "switch to Default" CTA is required adjacent to the comparison table.

#### 15.2.2.3 Dismiss-permanently flow

After at least one successful Express signing, the user MAY dismiss the table permanently. Dismiss flow MUST require a separate gesture (e.g., long-press) and emit `ExpressTierComparisonDismissed` audit event with the user-identity + acknowledgement.

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
let entries = mpc::list_signed_actions(ListOpts { since, joint_pubkey: &joint_pubkey }).await?;  // ADR-0035
mpc::approve(ApproveOpts { session_id, decision: Decision::Allow }).await?;                       // ADR-0035
```

**Seven methods** (expanded from 5 per ADR-0035 to expose audit-trail UX and approval-quorum participation). The two new methods:

- **`listSignedActions({since, jointPubkey})`** — returns the wallet's view of its own STH-anchored signing history (per ADR-0019 / §10.5). Promotes the audit-trail UX from internal-only to first-class SDK surface. Required for the "what did my wallet sign last week?" UX.
- **`approve({sessionId, decision})`** — the eligible-approver side of `Verdict::RequireApproval` (§09.5.1). Invoked when an approver receives an approval-request envelope; produces the BRC-77 signature over `request_view_hash` per §09.5.1 step 3.

Anything else is internal to the wallet's BRC-100 surface.

## 15.5 Onboarding UX

Cold-start (default tier):

1. User's wallet (Tauri/browser) calls `discover(filter)`, gets ranked list.
2. User picks (or wallet auto-picks #1 by reputation × cheapest).
3. Wallet runs **single 2-of-3 DKG** ceremony. The "node fee pool" DKG mentioned in BRC-mpc-fees draft is a one-time setup *between operators*, not a per-user concern.
4. Wallet stores share A locally + share B in passkey-encrypted iCloud/Google backup (WebAuthn PRF).
5. Notary holds C.
6. Wallet displays joint pubkey + BSV address; user is ready to fund.

Total time: ~1 second over WebSocket, ~2 seconds over HTTP poll.

## 15.5a Sign-time confirmation contract (normative, per ADR-0031)

Before consuming a presig (per §06.17) and emitting any sigma share toward the joint signature, a conformant wallet MUST display to the user the following fields. Field names are normative; rendering style is integrator's choice (per ADR-0031).

| Field | Source | Notes |
|---|---|---|
| `counterparty_identity` | BRC-31 pubkey of the recipient's MPC wallet; name from BRC-52⊕ cert if present | If anonymous (e.g., payment-only), display as "anonymous recipient + 0x{pubkey-first-8-hex}…" |
| `amount_sats` | Tx output sum to non-self addresses | Plus `fee_output` separately |
| `fiat_estimate` | `amount_sats × bsv_usd_rate` per Q17 oracle | Locale-aware (ISO 4217 minor units). Staleness bound: 300s. |
| `fee_output` | L2 P2MS fee output per §11 | Shows operator fee distribution |
| `notary_id` | The Notary cosigner's BRC-31 pubkey | Cross-referenced with §12 discovery row |
| `policy_manifest_version` | `policy_id` + version indicator | Shown only if manifest is newer than prior sign session |
| `verdict` | Output of policy engine eval per §09.5 | `Allow` / `RequireApproval` / `RateLimited` |
| `expected_latency_ms` | Function of (network profile per §06.10 matrix, presig pool depth, cold/warm WS) | Selected from the §06.10 matrix row matching current profile. SHOULD update live as conditions change. |
| `presig_path_used` | `true` if a valid presig was found in pool; `false` if 4-round fallback | Surfaces the cold-start branch from §06.18 |

### 15.5a.1 Hybrid rendering contract (per CHANGES-PROPOSED #1)

The wallet MUST expose a `confirmationView(intent) → ConfirmationSurface` API. Integrators MAY call this to obtain a structured rendering of the §15.5a fields and present them in their own UI. If integrators do NOT call `confirmationView()` before invoking `mpc.sign()`, the wallet MUST render the default UI itself before consuming any presig.

The two paths produce **identical field content** (per §15.5a table); only the visual presentation differs.

```
type ConfirmationSurface = {
    fields: [Field; 9]   // exactly the §15.5a normative fields, in stable order
    intent_summary_text: String  // optional rendered_text per ADR-0044 for ADR-0032 binding
}
```

Implementations MUST NOT auto-sign without one of these paths displaying the surface, unless a session policy explicitly grants `headless: true` (agent profile, see Q15 in OPEN-QUESTIONS — consent capture at onboarding is still the open design choice).

### 15.5a.2 Fiat oracle (per CHANGES-PROPOSED #3)

The `fiat_estimate` field MUST be computed by querying ≥2 of the following oracle sources and taking the median:

- BSV-overlay-published rate (topic `tm_bsv_rates_v1` if available)
- CoinGecko `bsv/usd` (or locale equivalent)
- CoinMarketCap `bsv/usd`
- BitGo public price feed
- Other operator-approved sources (operator MAY extend the list)

Display the median value with a confidence interval if any two source values disagree by >2%. The estimate MUST be no older than **300 seconds** since last fresh query. Stale-bound estimates MUST display "rate stale" indicator + the last-known value.

The estimate is **advisory, not security-load-bearing** — `amount_sats` is the source of truth; `fiat_estimate` is a usability convenience.

When `Verdict::RequireApproval` is the result of policy eval, the confirmation surface MUST also surface a "pending approval" state and the requester real-time view per §09.5.1.

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

## 15.9 Economic model — scenario-conditional (per ADR-0036)

### 15.9.1 Headline per-sig cost (marginal BSV fee only)

| Provider | Per-sig cost (USD, $50/BSV) | Custody model |
|---|---|---|
| Fireblocks Essentials | ~$0.10–$2.00 effective | Custodial |
| Fireblocks Custom | ~$0.50–$5.00 amortized | Custodial |
| Coinbase CDP MPC | bundled-into-Base | Custodial / partial |
| Lit Protocol PKP | ~$0.001-0.01 (RPS-credits) | Custodial / threshold |
| **This network — Default tier (marginal BSV fee only)** | **~$0.0002** | **Non-custodial (user holds 2-of-3)** |
| **This network — Express tier (marginal)** | ~$0.00005 | Custodial |

The `$0.0002` cell is the **marginal on-chain BSV fee** (333 sats × 3 nodes × $50/BSV ≈ $0.0002). It is NOT the fully-loaded per-sig cost when fixed infrastructure costs are amortized.

### 15.9.2 Fully-loaded moat by scenario

| Scenario | Sigs/mo | Calhoun stack $/sig (loaded) | Fireblocks $/sig equiv | Moat |
|---|---|---|---|---|
| Cold-storage (1/wk) | ~4 | **$5–$15** (fixed-dominated) | $175 (Essentials ÷ 4) | **1-2 OOM** |
| AI-agent burst | 100-1000/sec ≈ 260M/mo | **$0.0003** | $0.001–$0.05 | **2-3 OOM vs Lit; 3 OOM vs FB** |
| Regulated institutional (HSM v2 + multi-region + SLAs) | 10K/mo | **$0.20–$0.30** | $1.50–$5 | **~1 OOM** |
| Self-hosted single-cosigner | 100/mo personal | **$1–$5** (user eats ops) | $7 (Essentials ÷ 100) | **<1 OOM; INVERTS at <50/mo** |
| Multi-tenant Notary marketplace | 10M/mo across tenants | **$0.0003** | n/a (no marketplace product) | **3-4 OOM (robust)** |
| Mobile-first consumer | 10/mo | **$0.0002 + ~$0 (ops externalized)** | $70 (Essentials ÷ 10) | **3-5 OOM (apples vs oranges)** |

### 15.9.3 Scoped moat claim

**The Default tier is 3-4 orders of magnitude cheaper than Fireblocks at sustained ≥1M sigs/mo aggregate volume.** The ratio narrows to 1-2 OOM at low volume / regulated tiers, and can invert below ~50 sigs/mo self-hosted where fixed cost dominates marginal BSV fee. Fireblocks structurally cannot follow at high volume without giving up its compliance product; structurally beats us at low volume + regulated requirements because their flat fee amortizes ops cost the user would otherwise eat. See [ADR-0036](decisions/0036-cost-claim-conditional-scoping.md).

### 15.9.4 Customer-facing disclosure obligation

Operators marketing the v1 stack to NYDFS-licensed entities, MiCA CASPs, OCC trust customers, or anyone subject to SOC2 Type II strict scope MUST disclose ADR-0016 deferrals (no v1 TEE/HSM) in their customer-facing security documentation. Marketing the moat without scenario qualifications violates §15.9.3.

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
