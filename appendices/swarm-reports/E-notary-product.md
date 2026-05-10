# Appendix E — Notary Product, Fees, Discovery, UX

> Full report from the Notary/fees/discovery zone agent of the god-tier-design swarm (2026-05-10).
> Preserved verbatim as supporting depth for [`§11-fees.md`](../../11-fees.md), [`§12-discovery.md`](../../12-discovery.md), [`§15-notary-product.md`](../../15-notary-product.md).

---

## §A. God-tier definition + 5-axis rubric anchor

The user-facing layer is *the* differentiator. CGGMP'24 is commodity cryptography; threshold signing is becoming a feature, not a moat (Coinbase's `cb-mpc` is open-source, Lit's PKPs are open, BitGo and Fireblocks both have MPC). What is **not** commodity is: a permissionless, vendor-neutral marketplace of signing co-parties that an end user can discover, trust on first use, route around when one fails, and pay for at the granularity of a single signature. Today only Sigstore (for software supply chain) and Helium (for wireless coverage) have built that primitive at scale. We're building the BSV-native version of it.

**God-tier definition for this layer:** a Notary is a *publicly discoverable, per-signature-priced cosigner whose policy and price are committed on-chain*, not a custodian. The user is always majority of their own quorum. The Notary is fungible: any of N notaries can fulfill the role, swap is one DKG-resharing away. Onboarding takes ≤60 seconds from cold start (cf. Fireblocks' multi-week enterprise contract). Fee per signature is in the 100–1,000 sat range — one to four orders of magnitude cheaper than Fireblocks' 0.20% overage (a $1,000 transfer costs Fireblocks $2.00 = 200,000 sats at $50/BSV; ours costs ~$0.0002).

## §B. Option 1 — "Paid Cosigner in user-controlled 2-of-3" (RECOMMENDED)

**Architecture.** The user holds shares A and B (one on their device, one on a passkey-protected cloud backup or paired phone — see WebAuthn PRF pattern). The Notary holds share C. Signing requires 2-of-3, so the user can sign without the Notary (with both their devices) **and** the Notary cannot sign without the user. The Notary is a **paid cosigner**, not an oracle: it co-signs only when the user's coordinator presents a valid policy-conforming request. The Notary's value is (a) replacement for the user's "second device" when only the primary is online, (b) policy enforcement (rate limits, allowlists), (c) audit trail, (d) recovery anchor.

**Economic role.** Per-signature fee, market-driven floor 100 sats, default 333 sats per node × 3 = 1,000-sat tx-level fee (BRC-mpc-fees). At $50/BSV that's $0.00017 per transaction. Compare:

| Provider | Per-sig cost (USD) | Notes |
|---|---|---|
| Fireblocks Essentials | ~$0.10–$2.00 effective | $699/mo + 0.20% overage on outbound |
| Fireblocks Custom | $1,500/mo+ amortized | $18k/yr min |
| Coinbase CDP MPC | "Free tier + usage at scale" — undisclosed | bundled into Base/x402 |
| Lit Protocol PKP | Capacity-credit NFT, ~$0.001–0.01 effective | reserved-RPS, not per-sig |
| **This network** | **~$0.0002** | per-sig fee floor 100 sats |

That's the economic moat: **3–4 orders of magnitude lower per-sig cost than Fireblocks** because the Notary has zero custody liability (no SOC-2, no insurance reserve, no compliance overhead — the user holds 2 of 3 shares, the Notary holds 1).

**Fee output structure.** Level 2 (P2MS bare multisig of the participating node pubkeys, t+1-of-n) is the god-tier default. Level 1 splits into multiple P2PKHs at sign-time which is wasteful; Level 3 (sCrypt covenant) is correct but premature optimization. Level 2 settles weekly via existing 2-of-3 ceremony (POC 11 validated mainnet). **Fix the spec/code mismatch in `fee_injector.rs`: change default from L1 split-P2PKH to L2 P2MS.** Settle weekly (not per-tx) — saves on-chain fees.

**Discovery.** Overlay (BRC-22 SHIP / `tm_mpc_signing` topic, CHIP token PushDrop). Sybil resistance: every node's CHIP token is a real on-chain output (~1,000 sats). The reputation score in `discovery.rs` (proof_score 0.40, age 0.20, abort 0.25, fee 0.15) is correct in shape but `query_proofs` is stubbed — un-stub before MVP launch or replace with a simpler "block-height-of-CHIP × successful-settlement-count" interim.

**Trust on first use.** Borrow Sigstore's TUF + transparency-log model: the Notary's CHIP token references a *signed capability manifest* (canonical CBOR, signed by its identity key), the manifest's hash is committed to a transparency log (BRC-18 OP_RETURN topic `tm_mpc_notary_manifest`). First-time user verifies (1) manifest hash matches what overlay returns, (2) manifest signature chains to identity key advertised in the CHIP token, (3) that identity key has been on-chain for ≥30 days and has ≥N successful settlements. This is the Fulcio analog: short-lived attestation + long-lived identity, with no CA gatekeeping.

**Onboarding UX.** Cold-start: (1) user's wallet (Tauri/browser) calls `discover_nodes` filtered by `max_fee_sats=1000, region=US`, gets ranked list; (2) user picks (or wallet auto-picks #1), wallet runs 2-of-3 DKG (POC 12); (3) wallet stores share A locally + share B in passkey-encrypted iCloud/Google backup (PRF extension); (4) Notary holds C. **One DKG, not two** — the BRC-mpc-fees draft's "two DKGs" requirement (user wallet + node fee pool) is wrong as a UX position; the node fee pool is a one-time setup *between operators*, not a per-user concern. Total cold-start: 1 DKG (~800ms over MessageBox poll path, ~200ms over WS) + capability verification = sub-1-second.

**Recovery UX.** When Notary disappears: user authenticates via passkey on second device (recovers share B), runs key-refresh + DKG with a *new* Notary (POC 13: same joint key, no on-chain move, 0 sats). Compromised Notary: same flow, plus blacklist the bad CHIP identity in wallet's local denylist + publish abort proof to overlay. **No funds move; no address changes.** This is dramatically better than Fireblocks (custodial recovery via support ticket) or seed-phrase wallets (catastrophic if lost).

**Composability.** Yes — and it's a feature. A 2-of-3 wallet using a Notary as one party where the user-side is *itself* a 2-of-3 (split across two of the user's devices) is just a 2-of-3 from the Notary's perspective. The Notary doesn't need to know its counterparty is itself MPC. Per-sig fee is paid once per outer signature. Nested MPC is composable because cggmp24's threshold-of-thresholds composes (you sign as one party using your own 2-of-2; the joint pubkey of the inner ceremony participates as one share of the outer).

**Grading.** Security 9/10 (fee-theft resistance via P2MS, sybil-resistant via on-chain CHIP cost, recovery via threshold + passkey is industry-best). UX 9/10 (one DKG, sub-second cold start, passkey recovery). Vendor-neutrality 10/10 (overlay-discovered, replaceable in one resharing, self-hostable via `bsv-mpc-service`). Operability 8/10 (weekly P2MS settlement is simple; ops runbook needs writing). Composability 9/10 (nested MPC works; SDK is small). **Average 9.0.**

## §C. Option 2 — "x402 paid signing oracle, no DKG, per-sig BRC-29 micropayment"

**Architecture.** No DKG. The user posts a sighash to the Notary's HTTP endpoint with a BRC-29/x402 payment header (per-call micropayment, 100–1,000 sats). The Notary is a stateless ECDSA *oracle* on a key it holds custodially. Like Lit Protocol PKPs but per-sig priced.

**Pros.** Zero onboarding latency (no DKG ceremony). Direct fit with x402 (Coinbase x402 had 119M txs by March 2026; pattern is proven). SDK is one method: `mpc.sign(sighash) → signature`, payment is HTTP 402 negotiation. Operability is highest of the three options (stateless server, no key shares, just keys + policy).

**Cons (severe).** This is *custody*, not threshold signing. The Notary holds the key, can sign arbitrarily, can be hacked or coerced. Recovery is custodial. Vendor-neutrality is a fiction — switching means moving funds. **It's a strictly worse Lit Protocol PKP.** Loses the entire "your key never exists" pitch.

**Grading.** Security 4/10 (custody risk, no threshold). UX 10/10 (instant). Vendor-neutrality 3/10 (switching means funds move). Operability 9/10 (stateless). Composability 5/10 (oracle, no nesting). **Average 6.2.**

Useful as a **secondary product tier** — "ephemeral signing" for low-value AI agents that want zero setup and accept custody risk for sub-cent value transactions. Recommend offering both Option 1 (default, secure) and Option 2 (express lane, opt-in) on the same Notary infrastructure.

## §D. Option 3 — "Reputation-marketplace with auto-routed multi-Notary"

**Architecture.** Like Option 1, but the wallet maintains a 3-of-5 (user holds 3, Notaries hold 2 of 5 shares, drawn from a *pool* of 10+ overlay-registered Notaries). On each signing, the wallet picks the cheapest 2 healthy Notaries from the pool, runs the 2-of-5 ceremony with them. Closer to Helium's "any hotspot of N can witness" model. Fees flow to the participating Notaries via Level 2 P2MS, settled per-epoch by participation proofs.

**Pros.** Maximum vendor-neutrality (no single Notary load-bearing, even ephemerally). Highest Sybil resistance (must compromise multiple notaries). Natural price competition (cheapest wins each round).

**Cons.** Onboarding requires 5-of-5 DKG with pool members the user has never met — slow, complex, more failure modes. SDK becomes more complex (notary-set management). Cosigner-policy heterogeneity becomes a UX problem ("which policy will be enforced?"). 5-party DKG (POC 12) works but is brittle.

**Grading.** Security 10/10. UX 6/10. Vendor-neutrality 10/10. Operability 6/10 (epoch settlement across 5 nodes is harder). Composability 8/10. **Average 8.0.**

Recommend as **post-MVP graduation path**. Ship Option 1 (2-of-3 with one Notary) in 30 days; offer Option 3 (3-of-5 multi-Notary) as a Pro tier in 90.

## §E. Cross-layer dependencies

- **Policy:** Option 1 requires `min_fee_sats` rule kind in `StandardPolicyEngine` (rust-mpc) — confirms convergence doc §5 task 7. Notary's policy manifest must be canonical CBOR, embedded in the BRC-52 cert.
- **Identity:** BRC-52 cert is the canonical Notary identity. Cert references a CHIP token by txid:vout. Federation between certifiers must be locked before multi-Notary (Option 3).
- **Discovery:** CHIP token must add `policy_manifest_hash` field (32-byte SHA-256). Spec change to `brc-mpc-discovery.md` §2.
- **SDK:** integrator surface is 5 methods (discover/onboard/sign/replace/recover). All other BRC-100 methods proxy to local share via existing `bsv-mpc-proxy`.
- **Settlement:** Level 2 weekly P2MS; settle epoch boundary midnight UTC Sunday. Requires `query_proofs` un-stub.
- **Transport:** non-blocking — works on either MessageBox or direct HTTP per convergence §1.1.

## §F. Defensible economic moat (final word)

Fireblocks is $699–$18,000+/mo for custody+compliance. Lit is RPS-reserved capacity credits. Coinbase is bundled-into-Base (lock-in). This network is **per-signature, sub-cent, on-chain-priced, vendor-neutral, user-custodial**. The moat is not the cryptography; it's the *marketplace of replaceable Notaries with on-chain capability advertisements and key-refresh-based switching*. Fireblocks cannot lower its price 4 orders of magnitude without giving up its compliance product. We can.

## Sources

- Fireblocks Pricing — Essentials $699/mo + 0.20% overage; Custom $18k/yr+
- Lit Protocol Capacity Credits — RPS-reserved NFT pricing
- Coinbase x402 Welcome — 119M txs by March 2026, $600M annualized
- BSV BRC-105 / BRC-29 — HTTP 402 + BRC-29 derivation
- Sigstore Security Model — ephemeral cert + Rekor transparency log
- Sigstore Fulcio docs — short-lived cert avoids revocation
- Coinbase Agentic Wallets / cb-mpc — programmable session caps, x402 native
- Helium Proof of Coverage — DePIN reputation/incentive precedent
- Corbado on Passkey PRF — WebAuthn PRF for E2EE share backup
- Para — why passkey-only fails — confirms hybrid MPC + passkey is the convergent answer

Internal references:
- `/Users/johncalhoun/bsv/mpc/SWARM-CONVERGENCE.md` (§1.5)
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/brc-drafts/brc-mpc-fees.md`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/brc-drafts/brc-mpc-discovery.md`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/crates/bsv-mpc-overlay/src/discovery.rs` (filter/rank/health-check)
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/crates/bsv-mpc-proxy/src/fee_injector.rs` (default-mismatch fix needed)
- `/Users/johncalhoun/bsv/mpc/rust-mpc/crates/policy/src/cosigner_policy.rs` (add `min_fee_sats` rule)
