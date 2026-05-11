# MPC-Spec Roadmap

> What ships in v1, what waits for v2, what's reserved for v3. The spec describes the full vision; this doc says when each piece is in scope.
> Last updated: 2026-05-10

## How this doc works

Every numbered spec section (`§00`–`§18`) has a `**Version:**` line at the top declaring its target version. This roadmap is the index that groups them.

- **v1** — the partnership's first ship target. Goal: cross-impl mainnet signing test + Notary MVP. Scope is deliberately narrow to keep both implementations focused and reviewable.
- **v2** — hardening and product expansion. 3-6 months after v1. Builds on v1 primitives.
- **v3** — future-prep and market expansion. 6-12+ months after v1. Includes protocol migrations, multi-Notary marketplace, institutional features.

A section in v1 may have subsections that defer to v2 — those are called out inline within the section. The version line at the top reflects the section's *baseline* target.

## Moving things between versions

Promotion (v2 → v1) or demotion (v1 → v2) of any section requires:
1. A PR updating the section's `**Version:**` line and this roadmap.
2. A new ADR documenting the rationale.
3. Both partnership stewards' sign-off on the ADR.

The default move is **demote rather than promote** when v1 scope is at risk of slipping. Better to ship a tight v1 and add in v2 than ship a sprawling v1 late.

## v1 — Cross-impl signing test + Notary MVP

Targets: the partnership's 2-week cross-impl test (1 bsv-mpc party + 2 rust-mpc cosigners produce mainnet signature) and the 30-day Notary MVP.

| Section | Topic | What v1 covers | What's deferred |
|---|---|---|---|
| §00 | Overview | Spec TOC, conventions, glossary | — |
| §01 | TSS protocol pin | cggmp24 ≥ 0.7.0-alpha.2 + `set_additive_shift` patch + CVE patches | Scheme migration (DKLs23, FROST) is v2/v3 via algorithm_tag |
| §02 | ExecutionId | Canonical formula + test vectors | algorithm_tag values 0x02/0x03 reserved for v2/v3 |
| §03 | BRC-42 invoice | Canonical canonicalization (`.to_lowercase().trim()`) + validation rules + test vectors | — |
| §04 | SessionId | Deterministic input-hash formula | — |
| §05 | MessageEnvelope | Canonical CBOR + BRC-78 + BRC-31 + ExecutionId binding + `traceparent` | — |
| §06 | Transport | Federated MessageBox + WebSocket canonical + HTTP poll + FCM | Iroh QUIC direct-P2P accelerator (§06.6) → **v2**; Tor v3 onion (§06.9) → **v2** |
| §07 | BRC-31 auth | Per-message mutual auth, identity-key derivation | — |
| §08 | Identity (BRC-52⊕) | Basic profile with `notAfter` + `policy_hash` + `ctlog_proof` + `audit_identity` | Threshold-subject (nested MPC) → **v2**; full cross-signing federation → **v2** |
| §09 | Policy engine | Protocol whitelist + amount cap + per-hour rate + `min_fee_sats` + manifest format | Jurisdiction rules, k-of-m approval quorum, time-of-day windows, cumulative daily caps, dry-run mode → **v2** |
| §10 | Audit | Append-only Merkle log + PushDrop STH chain (ADR-0019) + BRC-18 OP_RETURN proofs | Witness co-signing (§10.6) → **v2**; Runar covenant variant → **v3** |
| §11 | Fees | L2 P2MS default + per-tx fee output + manual weekly settlement | Automation, L3 sCrypt covenant → **v3** |
| §12 | Discovery | CHIP token + capability JSON + basic reputation scoring | Full TUF-style trust-on-first-use UX → **v2** |
| §13 | Federation | Partial cross-signing in v1 (mutual root certs); §13.7 operator replacement → **v2** | Operator-quorum signing, replacement choreography → **v2** |
| §14 | Conformance tests | Phase 0 test vectors (§01-05) + runner architecture | Phase 1+ vectors → **v2**; live cross-impl harness → **v2** |
| §15 | Notary product | Default tier (2-of-3 paid cosigner) + minimal BRC-100 surface + SDK 5 methods | Express x402 tier → **v2**; Pro 2-of-5 marketplace → **v3** |
| §16 | Operations | Standard cloud cosigners + share refresh + OTel discipline (no TEE/HSM per ADR-0016) | TEE attestation → **v2** (ADR-0016 reopens); HSM cold tier → **v2**; full chaos engineering → **v2** |
| §17 | Supply chain | Reproducible Cargo + cosign + Rekor + runtime self-verification | SLSA L3 attestations → **v2**; TEE attestation cross-check → **v2** |
| §18 | Recovery | Threshold resharing (POC 13) + encrypted backup via passkey | Social recovery (k-of-n trustees), jurisdictional escrow, nested-MPC social recovery → **v2** |

## v2 — Hardening + product expansion

Targets: institutional-tier signing, federated multi-operator network, multi-tier Notary product, hardware attestation, SLSA L3 supply chain.

| Pulled forward to v2 | Rationale |
|---|---|
| §06.6 Iroh QUIC accelerator | Direct-P2P fast path for established cosigner pairs |
| §06.9 Tor v3 onion | Max-privacy profile for high-stakes wallets |
| §08 threshold-subject cert | Nested MPC composability |
| §08 full cross-signing federation | Multi-operator trust network |
| §09 extended policy rules | Jurisdiction, k-of-m approval, time windows, cumulative caps, dry-run |
| §10.6 witness co-signing | Cross-cosigner non-repudiation primitive |
| §13.7 operator replacement choreography | Cosigner replacement via cross-(t,n) resharing |
| §15.2.2 Express tier (x402 paid oracle) | Sub-cent ephemeral signing for low-value AI agents |
| §16.7 TEE attestation | Cost-benefit revisited per ADR-0016 trigger conditions |
| §17 SLSA L3 attestations | Build provenance for regulated deployments |
| §17 TEE attestation cross-check | Runtime code-provenance verification |
| §18 social recovery (trustees) | k-of-n trustee model with recovery shares cryptographically distinct from signing shares |
| §18 jurisdictional escrow | High-value users distribute backup shares across jurisdictions |

## v3 — Future-prep + market expansion

Targets: protocol migrations, marketplace dynamics, institutional/estate features.

| Reserved for v3 | Rationale |
|---|---|
| DKLs23 protocol migration | `algorithm_tag = 0x02`; no Paillier, sub-second DKG; once a 2nd-implementation Rust DKLs23 reaches CGGMP'24's maturity |
| FROST Schnorr forward-prep | `algorithm_tag = 0x03`; only if BSV consensus adds Schnorr |
| §10 Runar covenant for STH chain | Consensus-enforced chain monotonicity in Bitcoin Script |
| §15.2.3 Pro tier (2-of-5 multi-Notary marketplace) | Reputation-driven Notary selection per signing |
| §09 Cedar policy DSL migration | When Cedar's `wasm32 [no_std]` story matures |
| Q13 BRC-18 reputation tokens (PushDrop) | Per-proof token semantics; product surface for cosigner-stake economics |
| §18 nested-MPC social recovery | Trustees are themselves MPC groups |
| §11 L3 sCrypt fee covenant | Trustless on-chain fee distribution |
| HSM cold tier (institutional) | Regulated key custody for $250k+ users |
| Inheritance / dead-man's switch | Time-locked Notary release for estate handling |

## Decision log

Versioning decisions are recorded in ADRs:

| ADR | Decision |
|---|---|
| ADR-0016 | TEE/HSM deferred from v1 to v2 (cost-driven) |
| ADR-0019 | STH publication via PushDrop chain (v1) |
| ADR-0020 | This versioning policy itself |

## See also

- [`PROPOSAL.md`](PROPOSAL.md) — what the partnership is shipping in v1 specifically
- [`DESIGN.md`](DESIGN.md) — why each layer's v1 choice is made
- [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) — questions that affect future-version scope
- [`CONTRIBUTING.md`](CONTRIBUTING.md) — how to propose moving sections between versions
