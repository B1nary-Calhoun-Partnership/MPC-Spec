# Partnership Proposal — MPC-Spec v1

> The headline document. Read this first. ~10-minute read.

## What this is

A draft specification for a vendor-neutral BSV threshold-signing network, jointly developed by Calhoun and Binary. Two independent Rust implementations (`bsv-mpc`, `rust-mpc`), one shared protocol, conformance-tested.

This document proposes the **god-tier design** the spec encodes, surfaces the **five highest-leverage findings** that emerged from a 6-agent design review, and lists the **seven open design questions** the partnership needs to settle before implementation begins.

## Why

> *"We're competing with Fireblocks via per-signature pricing and flexible cosigner arrangements."* — Binary's strategy doc.

> *"A cosigner is just a BRC-100 wallet, and an MPC wallet exposes BRC-100."* — Mitch.

The product thesis is a **marketplace of replaceable Notaries** with on-chain capability advertisements and key-refresh-based switching. Fireblocks structurally cannot follow this — they hold custody, so they pay for SOC-2 + insurance + compliance overhead. We don't, because the user holds 2 of 3 shares.

## The five highest-leverage findings

### 1. 🚨 P0 SECURITY: CGGMP'21/24 had two CVEs in late 2025

Both implementations must pin to LFDT-Lockness `cggmp21` `cggmp24/m` ≥ 0.7.0-alpha.2 (post-CVE-2025-66016 missing-ZK-check + CVE-2025-66017 presig-forgery — see [GHSA-8frv-q972-9rq5](https://github.com/LFDT-Lockness/cggmp21/security/advisories/GHSA-8frv-q972-9rq5)). Calhoun's `cggmp21-fork#brc42-additive-shift` rebases on top of the patched commit. **No mainnet ceremony before this lands on both sides.**

ADR: [`decisions/0001-cggmp24-pin-past-cve-2025.md`](decisions/0001-cggmp24-pin-past-cve-2025.md)

### 2. The economic moat is real and quantifiable — 3-4 OOM cheaper than Fireblocks

| Provider | Per-sig cost (USD) |
|---|---|
| Fireblocks Essentials | ~$0.10–$2.00 effective ($699/mo + 0.20% overage on outbound) |
| Fireblocks Custom | $1,500/mo+ amortized |
| Coinbase CDP MPC | bundled-into-Base lock-in |
| Lit Protocol PKP | ~$0.001–0.01 (RPS-reserved capacity credits) |
| **This network** | **~$0.0002** (333 sats × 3 nodes at $50/BSV) |

Structural, not a price war. Fireblocks can't lower their price 4 OOM without giving up their compliance product.

### 3. Quorum-profile reconfiguration via resharing is uniquely BSV-MPC

POC 13 lets a user move between `Hot` (2-of-3, fast), `HotPlusCold` (2-of-5, recovery-capable), and `ColdOnly` (vault, 2-of-2 HSM) **without moving funds, with 0 on-chain cost**. Same joint pubkey, same BSV address. Fireblocks fixes threshold at vault-creation. We don't. Real product differentiator.

### 4. Witness co-signing of audit STHs gives non-repudiation in the asymmetric setting

Borrowed from Sigstore: every cosigner's append-only Merkle audit log emits a Signed Tree Head every 60s; **other cosigners co-sign each STH on every signing ceremony**. Cosigner #2 cannot retroactively rewrite its log without #3 noticing on the next witness round. Combined with on-chain BRC-18 anchoring, strongest practical audit-integrity guarantee available without TEE.

### 5. `insecure-assume-preimage-known` is misleadingly named for BSV

Both implementations should enable. BSV sighashes are pre-hashed (SHA-256d) before the protocol sees them; the "insecure" name applies to use-cases where the protocol sees plaintext, not BSV's. This unblocks the 1-round signed-with-presig path and resolves the divergence (rust-mpc has it, bsv-mpc doesn't).

## What's locked vs what's open

### LOCKED (Phase 0 — cryptographic foundation, both parties agree before any joint ceremony)

| File | Lock |
|---|---|
| §01 cggmp24 pin | LFDT-Lockness `cggmp24/m` ≥ 0.7.0-alpha.2 + Calhoun fork's `set_additive_shift` |
| §02 ExecutionId | `SHA256("calhoun-binary-mpc" \|\| version \|\| algorithm_tag \|\| phase_tag \|\| session_id \|\| joint_pubkey)` |
| §03 BRC-42 invoice | `"{level}-{protocol_id.to_lowercase().trim()}-{key_id}"` (rust-mpc form; bsv-mpc fixes its bug) |
| §04 SessionId | Deterministic `SHA256(domain \|\| initiator \|\| sorted_participants \|\| threshold \|\| kind \|\| nonce \|\| payload_digest)` |
| §05 Message envelope | Canonical CBOR with BRC-78 inner + BRC-31 outer + ExecutionId binding + `traceparent` field 10 |

### DRAFT (Phase 1+ — open for Binary review and edit)

| File | Direction |
|---|---|
| §06 Transport | Federated MessageBox + per-cosigner-pinned relays. **WebSocket (Socket.IO/EngineIO compatible) is the canonical receive transport — both relays support it.** HTTP poll + FCM are MUST-support fallbacks for constrained edges (browser-without-WS, mobile background). Iroh QUIC reserved as post-DKG accelerator. Tor v3 as max-privacy profile. **Calhoun extends `bsv-messagebox-cloudflare` to add Socket.IO over CF Worker Durable Objects** — restores parity with `<binary-messagebox-host-tbd>`'s WS surface. |
| §07 BRC-31 auth | Unchanged from the canonical `bsv-middleware-cloudflare` reference. |
| §08 Identity | "BRC-52⊕": short-lived (24h cosigner / 1h human / 7d root) + transparency-log anchor + threshold-subject capable. **Deprecate rust-mpc's `core::identity::Certificate` custom struct.** |
| §09 Policy | Canonical-CBOR PolicyManifest in cert. Engine fires on 3 hooks (derivation/presigning/signing). Presigs bound to `policy_id`. |
| §10 Audit | Embedded Sigstore Rekor + 60s STH publishing to BSV (`tm_mpc_audit`) + witness co-signing. BRC-18 proof = audit-log projection. |
| §11 Fees | Level 2 P2MS default (fix `fee_injector.rs` Level 1 mismatch). Weekly settlement. |
| §12 Discovery | CHIP token capabilities incl. `policy_hash`, `transport` block. |
| §13 Federation | Cross-signed BRC-52 roots. Operator replacement via resharing. |
| §15 Notary product | Three tiers preserved: Default 2-of-3 / Express x402 / Pro 2-of-5 marketplace. |
| §16 Operations | **v1: standard cloud cosigners, no TEE, no HSM cold tier.** Runtime integrity from share refresh + audit + witness cosigning. OTel `traceparent` with strict whitelist + CI redaction linter. TEE / HSM cold tier reserved for v2 institutional. |
| §17 Supply chain | Reproducible Cargo + cosign + Rekor + SLSA L3 + optional TEE attestation. |
| §18 Recovery | Threshold resharing + encrypted backup + nested-MPC social recovery. |

### PLACEHOLDER

| File | Reason |
|---|---|
| §14 Conformance tests | Test vectors must come last — needs LOCKED §01-05 first, then both implementations contribute test cases. |

## Seven open design questions for Binary

These are in [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). The most consequential:

1. **CGGMP CVE patches** — confirm pin past 0.7.0-alpha.2 before any joint mainnet ceremony.
2. **Lagrange canonicalization** — `mpc-brc42::aggregate_ecdh_partials` does naive sum today; threshold-correct logic lives in `protocol/src/signer.rs`. Move into the brc42 crate to prevent misuse?
3. **Presigning over MessageBox** — `messagebox_cosigner.rs` returns `TransportError::Protocol("...not supported via MessageBox")`. Blocks sub-second cross-impl signing. What's the intended path?
4. **Cert format consolidation** — deprecate `core::identity::Certificate` (custom JSON) in favor of BRC-52⊕? Policy engine moves to verify BRC-52.
5. **Cedar migration** — willing to ship canonical-CBOR PolicyManifest now with a Cedar-shaped schema for future migration when Cedar's `wasm32 [no_std]` matures?
6. **Iroh QUIC accelerator** — willing to take the bet on iroh (one project, one team, but the right shape) for post-DKG fast path, or wait for a more standardized substrate?
7. **Schnorr forward-prep** — `algorithm_tag = 0x03` (FROST3) reservation is cheap; want a real implementation experiment to de-risk migration if BSV adds Schnorr?

## Sequencing (logical dependency order)

```
Phase 0 (Wks 1-2):  §01-05    Lock cryptographic foundation. Cross-impl gate.
Phase 1 (Wks 3-6):  §06-10    Transport, BRC-31, BRC-52⊕ identity, policy, audit.
Phase 2 (Wks 5-8):  §11,13,16-18  Fees, federation, ops, supply chain, recovery.
Phase 3 (Wks 7-9):  §12, 15   Discovery, Notary product surface.
Phase 4 (Wks 8-10): §14       Conformance suite both implementations run.

Mainnet 2-of-3 cross-impl signature: end of Phase 1.
Notary MVP: end of Phase 3.
```

No resource constraint stated by the partnership; this sequencing reflects logical dependency, not engineering capacity. Phases 1-4 can pipeline once Phase 0 locks.

## How we got here

This proposal is the synthesis of two design swarms (May 2026):

- **First swarm (gap analysis)** found 20+ wire-incompatibility issues between the two implementations (preserved as historical context).
- **Second swarm (god-tier design)** redesigned each layer drawing freely from production peers (Fireblocks, Lit Protocol, Coinbase MPC, Sigstore, SPIFFE, Cedar, Iroh, Matrix, etc.) and academic literature (CGGMP'24, DKLs23, FROST3, TSSHOCK).

Per-zone analysis is preserved in [`appendices/swarm-reports/`](appendices/swarm-reports/) — the depth that didn't fit here.

## What we're asking

1. Read this proposal + skim [`DESIGN.md`](DESIGN.md) (the why behind every pick).
2. Engage on [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md). Seven questions; each becomes an ADR.
3. Redline any DRAFT section. Phase 0 (LOCKED) needs explicit OK or counter-proposal.
4. Once Phase 0 is signed off (both stewards on the ADRs), implementation starts. Phase 1+ co-evolves.

## Stewards

- **Calhoun side:** John Calhoun ([@Calgooon](https://github.com/Calgooon)) — public org [@Calhooon](https://github.com/Calhooon).
- **Binary side:** TBD — Binary to assign on first review.

Targeted Phase 0 sign-off: 14 days from first review.
