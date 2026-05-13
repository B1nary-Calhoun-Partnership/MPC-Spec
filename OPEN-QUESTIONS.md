# Open Questions

> Questions the partnership needs to settle. Each one becomes an ADR once resolved.

Status legend:
- 🟥 **Blocking** — Phase 0 cannot lock until resolved.
- 🟧 **Important** — Phase 1+ depends on this.
- 🟨 **Open** — design optionality; not blocking but worth deciding.

---

## Q1 🟥 — CGGMP CVE patches

**Question:** Will Binary pin `rust-mpc` to LFDT-Lockness `cggmp24/m` ≥ 0.7.0-alpha.2 (post-CVE-2025-66016 + post-CVE-2025-66017) before any joint mainnet ceremony?

**Context:** CGGMP'21/24 had two CVEs disclosed in late 2025: [GHSA-m95p-425x-x889](https://github.com/LFDT-Lockness/cggmp21/security/advisories/GHSA-m95p-425x-x889) (CVE-2025-66016, missing ZK proof check) and [GHSA-8frv-q972-9rq5](https://github.com/LFDT-Lockness/cggmp21/security/advisories/GHSA-8frv-q972-9rq5) (CVE-2025-66017, presignature forgery via altered presigs). Both implementations must pin past these.

**Recommended resolution:** Yes. Both repos pin same commit. Calhoun's fork rebased on top.

**Becomes:** ADR-0001 (already drafted in [`decisions/0001-cggmp24-pin-past-cve-2025.md`](decisions/0001-cggmp24-pin-past-cve-2025.md))

---

## Q2 🟥 — Lagrange canonicalization location

**Question:** `rust-mpc/crates/brc42::aggregate_ecdh_partials` does a naive point sum today. The threshold-correct Lagrange combine lives one layer up in `protocol/src/signer.rs::pre_derive`. Should we move Lagrange into the `brc42` crate so the function is correct-by-construction?

**Context:** Naive-sum is correct only for additive sharing (vss=None). With Verifiable Secret Sharing (VSS, what cggmp24 produces from DKG), the threshold combine requires Lagrange interpolation at x=0. The current placement works but is fragile — any caller that bypasses `pre_derive` and uses `aggregate_ecdh_partials` directly produces wrong results silently.

**Recommended resolution:** Move into `brc42` crate as `combine_ecdh_partials_lagrange(partials, vss_setup)`. Force the canonical form.

**Becomes:** ADR-0021 (TBD)

---

## Q3 🟥 — Presigning over MessageBox (RESOLVED — ADR-0030)

**Question:** What's the intended fast-path for cross-implementation signing — and where does the presig material live between generation and consumption?

**Resolution:** **Resolved by [ADR-0030](decisions/0030-presig-coordinator-storage.md)** at the 2026-05-12 partnership sync. Cosigner-encrypted presig shares stored at coordinator via BRC-2 self-encryption (`mpcpresig` protocol). Coordinator runs burn-rate-driven parallel regeneration; mandatory invalidation on share refresh / subset change / policy update / rekey. Spec §06.15-§06.20 carries the normative text. `rust-mpc` reference implementation: `crates/brc42/src/presig_encryption.rs`, `crates/brc42/src/presignature.rs`, `crates/coordinator/src/presign.rs` (already shipped).

**Becomes:** Resolved by ADR-0030. See Resolution log below. The earlier "ADR-0022 (TBD)" reservation is released; the canonical resolution is ADR-0030.

---

## Q4 🟧 — Cert format consolidation

**Question:** `rust-mpc` has two non-interoperable cert types: `core::identity::Certificate` (custom JSON struct, used by `policy/engine.rs::verify_party_certificate`) and BRC-52 binary (issued by `bins/certifier/`). Will Binary deprecate the custom struct in favor of BRC-52⊕ (this spec's profile)?

**Context:** Federation between Calhoun and Binary roots requires one canonical cert format. BRC-52 is the BSV ecosystem standard; the custom struct doesn't interoperate with anything. Spec §08 mandates BRC-52⊕.

**Recommended resolution:** Yes. Move policy engine's `verify_party_certificate` to verify BRC-52. Migrate cosigner identities. Deprecation can be progressive (accept both for one release, then drop the custom struct).

**Becomes:** ADR-0023 (TBD)

---

## Q5 🟧 — Cedar policy DSL migration plan

**Question:** Will Binary ship the canonical-CBOR PolicyManifest schema now (Spec §09) understanding that the schema is intentionally Cedar-shaped, so we can migrate to Cedar (AWS Verified Permissions, Rust-native, Dafny-verified) when Cedar's `wasm32-unknown-unknown` `[no_std]` story matures?

**Context:** Cedar is the strongest competitor as a policy DSL — formally verified, differentially fuzzed, Rust-native. Today Cedar requires `std`, which kills the bsv-mpc-worker WASM use case. Canonical CBOR is the ship-now answer; the schema is laid out so a Cedar migration is mechanical (not a rewrite).

**Recommended resolution:** Yes. Schema lives in `mpc-policy-shared` crate. Migrate when Cedar WASM lands.

**Becomes:** ADR-0024 (TBD)

---

## Q6 🟨 — Iroh QUIC as direct-P2P accelerator

**Question:** Spec §06.8 reserves Iroh QUIC + holepunch for post-DKG direct-P2P signing (sub-100 ms). Iroh is one project, one team (n0-computer); the protocol isn't IETF-standardized. Are we OK taking the bet, or wait for a more standardized substrate?

**Context:** Iroh's "dial keys instead of IPs" model fits BRC-31 identity-key routing exactly. WebTransport is the IETF-standard alternative but lacks holepunch + relay-fallback. libp2p QUIC is more mature but heavier and has poor browser/CF Worker support.

**Recommended resolution:** Reserve Iroh in §06 as opportunistic accelerator. Spec language allows substitution with WebTransport or libp2p QUIC at implementation discretion. The MPC layer doesn't observe the substrate — only that envelope delivery happened.

**Becomes:** ADR-0025 (TBD)

---

## Q7 🟨 — Schnorr forward-prep

**Question:** `algorithm_tag = 0x03` is reserved for FROST3 in §02 ExecutionId. Cheap reservation — zero v1 code change. Do we want a real implementation experiment to de-risk migration if BSV ever adds Schnorr?

**Context:** BSV consensus is ECDSA-only today. Probability BSV follows Bitcoin's BIP-340/341/342 over the next 5 years is non-zero. FROST3 is dramatically simpler than CGGMP'24 (1+1 rounds, no Paillier). Same DKG → same joint pubkey → ECDSA *or* Schnorr signing on top.

**Recommended resolution:** Reserve `0x03`. Do not implement v1. Revisit when/if BSV proposes Schnorr support.

**Becomes:** ADR-0026 (TBD; may stay in OPEN-QUESTIONS if BSV doesn't move)

---

## Q8 🟨 — Cold-tier HSM operator role (RESOLVED — DEFERRED to v2 by ADR-0016)

**Question:** Spec §16 originally recommended a hybrid hot-TEE + cold-HSM topology. Who operates the cold tier?

**Resolution:** **Resolved by [ADR-0016](decisions/0016-v1-ops-topology-no-tee-no-hsm.md).** v1 ships without HSM cold tier (cost: ~$1K/mo CloudHSM cluster) and without TEE (cost: ~$300/mo per cosigner Nitro). v1 runtime integrity is from threshold + share refresh + audit + witness cosigning. The v2 reopen of this question (when institutional users appear) will be filed as a successor ADR at that time — number to be assigned then, not pre-allocated here.

Forward-compat: cert format reserves `attestation` field; policy engine reserves `RuleKind::RequireAttestation`. No wire change needed when v2 activates.

**Becomes:** Resolved by ADR-0016. See Resolution log below. A v2 successor ADR (number TBD when filed) reopens the cold-tier operator role question.

---

## Q9 🟨 — Recovery-key escrow for quorum-loss DR

**Question:** Spec §18 covers normal recovery (threshold resharing). Catastrophic recovery (DR case (c): two of three cosigners simultaneously fail) requires user-driven encrypted backup. Where does the backup live?

Options:
- (a) **User's BRC-100 wallet storage** — encrypted with a key derived from the user's identity. User-only restore.
- (b) **Jurisdiction-distributed escrow** — one share at user's wallet, one at jurisdiction-A escrow, one at jurisdiction-B escrow. User must convince 2 of 3 to release.
- (c) **Both (a) and (b) — user picks per-account.**

**Recommended resolution:** (c). Default (a). Power users opt into (b) via spec extension.

**Becomes:** ADR-0027 (TBD)

---

## Q10 🟨 — Conformance test suite ownership

**Question:** Conformance tests in `conformance/` must be runnable by both implementations. Who writes the test runner?

**Recommended resolution:** Co-owned. Test vectors are language-neutral (JSON / hex). Each implementation writes its own runner that loads the vectors and asserts. CI in this repo runs both runners against the canonical vectors.

**Becomes:** ADR-0028 (TBD)

---

## Q11 🟨 — Steward assignment (RESOLVED)

**Question:** Who is the Binary-side steward of this repo?

**Resolution:** Mitch Burcham (confirmed 2026-05-12 partnership sync). Ishaan Lahoti is the Binary-side implementor (rust-mpc); Calhoun is the Calhoun-side implementor (bsv-mpc); both implementations conform to this same shared spec.

**Becomes:** governance note in README.

---

## Q12 🟨 — Initial Phase 0 sign-off date

**Question:** What's the target date for Phase 0 sign-off (both stewards OK on ADRs 0001-0005)?

**Recommended resolution:** 14 days from Binary's first acknowledgment of this repo.

**Becomes:** governance note, tracked in `OPEN-QUESTIONS.md` until resolved.

---

## Q13 🟨 — Should BRC-18 participation proofs also be PushDrop tokens?

**Question:** §10.5 changed STH publication from OP_RETURN to PushDrop chain (ADR-0019). §10.7 BRC-18 participation proofs remain OP_RETURN. Should they also move to PushDrop, with "unspent proof = reputation token" semantics (Mitch's interpretation B from the original Slack thread)?

**Context:** Each successful signing emits a BRC-18 proof. If proofs were PushDrops locked to the cosigner identity, the unspent set would be a verifiable reputation count. Cosigners could "spend" reputation for various purposes (fee settlement, dispute resolution, etc.). Adds product surface but requires careful design.

**Recommended resolution:** v1 keeps BRC-18 as OP_RETURN (no chain semantics needed for independent per-ceremony attestations). Revisit in v1.5 if a concrete reputation/staking use case emerges.

**Becomes:** ADR-0029 (v1.5+).

---

## Q15 🟨 — Headless / agent sign profile

**Question:** Should §15.4 / ADR-0031 define a `headless: true` opt-in that bypasses the sign-time confirmation contract (§15.5a) for agent wallets, and how is consent captured at onboarding?

**Source:** 2026-05-13 god-tier swarm UI/UX.

**Becomes:** ADR-TBD (post-CHANGES-PROPOSED user steering).

---

## Q16 🟨 — Approval channel pluralism

**Question:** Must approver delivery support push (FCM / APNs / Web Push) in addition to MessageBox (per ADR-0032), given mobile cosigners (§06.4) and 300s TTLs (§09.5)?

**Source:** 2026-05-13 god-tier swarm UI/UX + Speed.

---

## Q17 🟨 — Fiat estimate oracle

**Question:** Where does the wallet get the BSV/USD rate referenced in §15.5a (ADR-0031) and §12.5a (ADR-0033), and what is the staleness bound the spec mandates?

**Source:** 2026-05-13 god-tier swarm UI/UX.

---

## Q18 🟨 — Audit-trail privacy for `listSignedActions`

**Question:** STH chain (ADR-0019) is public; what subset of sighashes / policy_ids does the wallet expose locally vs publicly via `mpc.listSignedActions` (ADR-0035)?

**Source:** 2026-05-13 god-tier swarm UI/UX.

---

## Q19 🟨 — Denial UX symmetry

**Question:** When `Verdict::Deny` fires (§09.5), is the user shown the reason string verbatim, a categorized code, or silence (security-through-obscurity)?

**Source:** 2026-05-13 god-tier swarm UI/UX. Per ADR-0034: ONE of verbatim or categorized MUST be shown; choice between left to operator policy.

---

## Q20 🟨 — Notary marketplace incident transparency

**Question:** Should past-incident records (IR-002 reshares, IR-003..IR-008 per ADR-0042) be required surfacable in discovery (§12.5a per ADR-0033) so users can avoid recently-incidented Notaries?

**Source:** 2026-05-13 god-tier swarm UI/UX.

---

## Q21 🟨 — Express tier x402 routing overhead

**Question:** Express tier (§15.2.2) uses BRC-29 / x402 micropayments. What is the per-call cost upper bound? Estimate today: BRC-29 adds ~1 round-trip + ~250-byte inner payment envelope; at $0.0001 amortized per call, dominates Express marginal cost for sub-cent transactions.

**Source:** 2026-05-13 god-tier swarm Cost.

---

## Q22 🟨 — `fully_loaded_cost_estimate` field in `/capabilities`

**Question:** Should §12 discovery surface a Notary's published `fully_loaded_cost_estimate` (per ADR-0036), so the comparison surface shows break-even bar, not just `fee_sats`?

**Source:** 2026-05-13 god-tier swarm Cost.

---

## Q23 🟨 — Multi-region Notary cost model

**Question:** If a Notary advertises multi-region (§16.2 diversification), does the per-sig fee rise to cover the extra cosigner instances? Spec is silent; relevant for institutional bids.

**Source:** 2026-05-13 god-tier swarm Cost.

---

## Q24 🟨 — CHIP token mint amortization across tiers

**Question:** ~1000 sats × quarterly rotation × scale factor — who pays, operator or user? §16.8 silent.

**Source:** 2026-05-13 god-tier swarm Cost.

---

## Q26 🟧 — Parser-differential fuzz corpus ownership (per ADR-0037)

**Question:** Who maintains the shared adversarial CBOR / BRC-78 corpus that both implementations CI-fuzz against weekly?

**Recommended resolution:** Co-owned in `MPC-Spec/conformance/fuzz-corpus/` with both stewards committing canonical adversarial inputs as they're discovered. CI runs both implementations' parsers against the corpus on every PR.

**Becomes:** Implementation guidance in §14 conformance-tests.

**Source:** 2026-05-13 god-tier swarm Security S1.

---

## Q27 🟧 — `request_view_hash` canonicalization for non-payment intents (per ADR-0032)

**Question:** ADR-0032 specifies the canonical CBOR shape for payment intents. Token transfers, sCrypt covenant spends, and BRC-100 `internalizeAction` flows render very differently. What is the canonical shape across all approver UIs?

**Source:** 2026-05-13 god-tier swarm Security S4.

---

## Q28 🟧 — Continuous re-Rekor cadence vs. presig-pool latency budget (per ADR-0040)

**Question:** Re-verifying on every Nth presig consumption adds ~50–200 ms tail latency. What is the right N for the Notary SLI (§16.3) — 1000 sigs? Every refresh window? Configurable per operator?

**Source:** 2026-05-13 god-tier swarm Security S5 + Speed.

---

## Q29 🟧 — Memory-hard KDF parameters at scale (per ADR-0038)

**Question:** Argon2id m=256MiB collides with mobile recovery flows. Do we accept profile-conditional KDFs (`profile-mobile` uses scrypt N=2^17 OR Argon2id m=64MiB t=4)?

**Source:** 2026-05-13 god-tier swarm Security S2.

---

## Q30 🟧 — Multi-source STH lookup trust model (per ADR-0039)

**Question:** Two BRC-22 hosts is the minimum. Should the spec mandate that one host is operated by the verifier's own infrastructure?

**Source:** 2026-05-13 god-tier swarm Security S3.

---

## Q31 🟧 — Cosigner-side malicious-dep policy

**Question:** `bsv-rs` (Calhoun) and `bsv-sdk`-derived crates (Binary) have non-overlapping Cargo.lock trees. Should both stacks adopt a shared `cargo-deny` policy + crev review bar for any new dependency? (Typosquat precedent: `event-stream` 2018, `ua-parser-js` 2021, `colors.js` 2022, multiple Rust crate typosquats 2023-2024.)

**Source:** 2026-05-13 god-tier swarm Security.

---

## Q32 🟨 — Post-quantum migration trigger (per ADR-0043)

**Question:** When NIST FIPS 204 (ML-DSA) and FIPS 205 (SLH-DSA) move into BSV consensus discussion, what is the partnership's migration trigger? Specific BSV-consensus milestone, NIST adoption date, or both? Hash-based signatures for the cert-chain layer can land *now*; threshold ECDSA-equivalent PQ schemes are still research-grade.

**Source:** 2026-05-13 god-tier swarm Security S/PQ.

---

## Q33 🟨 — Operator credential rotation overlap window

**Question:** §16.8 specifies 7-day overlap. During overlap, *both* keys are valid. Should §07.7 BRC-31 sessions be force-invalidated on the *new* cert's first use, or only on the old cert's sunset?

**Source:** 2026-05-13 god-tier swarm Security.

---

## Q34 🟨 — Witness-cosign DoS exploitability

**Question:** §10.6 makes "failure to provide STH on request" an audit event. Can an attacker spam witness requests to drown a peer in `WitnessCosignFailed` entries and force IR-002 false positives?

**Source:** 2026-05-13 god-tier swarm Security.

---

## Q35 🟨 — AI-agent wallet UX threat model

**Question:** §08.11 mentions "BRC-100 wallet identity." For an LLM-mediated wallet, what is the minimal binding (signed `request_view_hash` per ADR-0032 + on-device WebAuthn) that preserves the §09 approval semantics?

**Source:** 2026-05-13 god-tier swarm Security S4.

---

## Q36 🟨 — Auxinfo compute measurement per profile (per ADR-0041)

**Question:** Should §06.10 carry a published `auxinfo_compute_seconds` measurement per profile, refreshed by CI on representative hardware? Today's matrix conflates wire and compute in a single number; CI-measured-per-profile would tighten the budget claim.

**Source:** 2026-05-13 god-tier swarm Speed.

---

## Q37 🟨 — Pro tier C(n,k) presig pool pre-warming

**Question:** Should Pro tier (§15.2.3) require pre-warming the C(n,k) presig pools, or accept cold-path penalty on first signing per subset combination?

**Source:** 2026-05-13 god-tier swarm Speed.

---

## Q38 🟨 — DKG split for `profile-mobile`

**Question:** For `profile-mobile`, should DKG split into "online" (sign-ready) and "deferred" (auxinfo finishes in background within 30s)? If yes, what is the sign-time fallback if a user tries to sign before aux completes?

**Source:** 2026-05-13 god-tier swarm Speed.

---

## Q39 🟨 — STH publish latency for Notary TOFU

**Question:** Should §10 STH publish latency (mainnet 1-conf, ~10 min / ~60 min p99) be normative for Notary TOFU (§15.7), or is the 10-settlement floor sufficient as a wall-clock proxy?

**Source:** 2026-05-13 god-tier swarm Speed.

---

## Q40 🟨 — Iroh QUIC v2 activation criterion

**Question:** §06.6 reserves iroh as MAY. At what measured-relay-tail-latency does the protocol layer SHOULD prefer iroh? Today's spec is "MAY"; never "SHOULD on cellular."

**Source:** 2026-05-13 god-tier swarm Speed.

---

## Q41 🟨 — Pool-depth drift alarm

**Question:** Should the burn-rate algorithm (§06.19) be extended with a "depth-of-pool drift" alarm so SRE sees when consumption-vs-regen falls behind BEFORE users see latency?

**Source:** 2026-05-13 god-tier swarm Speed.

---

## Q42 🟨 — Partnership CISO function

**Question:** Who owns the partnership-level CISO function? Calhoun, Mitch, rotating, or external advisor?

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q43 🟨 — SOC2 Type II pursuit timeline

**Question:** Will either side pursue SOC2 Type II for v2, and if so, with which audit firm and on what timeline?

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q44 🟨 — Pen-test ownership

**Question:** Trail of Bits vs. NCC Group vs. Mandiant vs. Cure53; budget owner; scope (joint or per-impl).

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q45 🟨 — Vendor-risk register maintenance

**Question:** Per §17.14 (ADR-0042), who maintains the vendor matrix, where is it published, how often reviewed?

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q46 🟨 — Public VDP / bug-bounty platform

**Question:** Per ADR-0042 §Part E disclosure, HackerOne / Immunefi / self-hosted?

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q47 🟨 — GDPR Art.17 erasure posture vs on-chain anchoring

**Question:** Right-to-erasure conflict with on-chain `request_hash` anchoring under GDPR Art.17 — legal posture (data-controller framing, hashed-not-personal-data argument, or out-of-scope-for-EU-customers)?

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q48 🟨 — Insurance posture

**Question:** Does either operator carry crime / cyber / E&O coverage, and is it portable to the joint network?

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q49 🟨 — Regulatory perimeter / qualified-custodian threshold

**Question:** At what AUM / volume threshold does the Notary become a "qualified custodian" under SEC custody rule / MiCA / NYDFS, regardless of architectural non-custody claims?

**Source:** 2026-05-13 god-tier swarm Quality.

---

## Q50 🟧 — Approver display field-set symmetry with §15.5a (per 2026-05-13 loop-2 UI/UX)

**Question:** §09.5.1 covers requester-side binding via `request_view_hash`. Should the approver's display field set match §15.5a (sign-time confirmation contract) exactly, or carry approval-specific fields (e.g., `requesting_user_identity`, `urgency_indicator`, `expires_in_secs`)?

**Source:** 2026-05-13 loop-2 UI/UX G2.

---

## Q51 🟧 — Stale `expected_latency_ms` policy

**Question:** If pool invalidation (§06.18) fires AFTER §15.5a confirmation display but BEFORE user gesture, which timeline "wins"? Refresh display + re-tap, OR roll through with possibly-stale latency expectation?

**Source:** 2026-05-13 loop-2 UI/UX G3.

---

## Q52 🟨 — WebAuthn gesture timeout

**Question:** ADR-0032 mandates `userVerification=required` for WebAuthn-bound approvers. What's the gesture-completion timeout (between display and signature emission)? Affects mobile UX where user may navigate away.

**Source:** 2026-05-13 loop-2 UI/UX.

---

## Q53 🟨 — `JitterScheduleEmitted` exposure

**Question:** Per ADR-0047, implementations MAY emit jitter schedule audit events. Should this be MUST for operator transparency, or stay MAY for operator privacy?

**Source:** 2026-05-13 loop-2 Security.

---

## Q54 🟨 — Rekor cache flush triggers (beyond CVE)

**Question:** Per ADR-0046 §1, cache flushes on binary-measurement-change, 24h, or operator-initiated. Should it also flush on Rekor `revoked` annotation (independent of expiration)?

**Source:** 2026-05-13 loop-2 Security.

---

## Q55 🟨 — `manifest_ack` revocation semantics

**Question:** Per the §09.9a + ADR-0032 manifest_ack binding, what happens to in-flight approval requests when a user revokes their manifest_ack between display and gesture? Race condition equivalent to Q51.

**Source:** 2026-05-13 loop-2 UI/UX + Security.

---

## Q56 🟨 — Successor commitment cross-publication policy

**Question:** Per ADR-0049, operators publish successor commitments via on-chain + TLS-pinned webpage. Should partnership require cross-publication on the peer operator's `tm_mpc_certs_v1` too (third-party trust anchor)?

**Source:** 2026-05-13 loop-2 Security L2-S3.

---

## Q57 🟨 — Pro tier min-fee enforcement layer

**Question:** ADR-0048 § min-fee floor is operator-declared. Should the wallet's discovery filter ALSO enforce against an aggregate floor (e.g., 80th percentile of all operator-declared floors)? Race-to-the-bottom resistant.

**Source:** 2026-05-13 loop-2 Cost.

---

## Q58 🟨 — IR-005 successor pre-commit cadence

**Question:** ADR-0049 mandates 90-day successor pre-commit. Should this be tightened for high-stakes operators (Pro tier marketplace participants)? E.g., 30-day cadence for Pro tier.

**Source:** 2026-05-13 loop-2 Security.

---

## Q59 🟨 — Argon2id mobile resource gating

**Question:** Per ADR-0038 §18.5, mobile uses m=64MiB Argon2id. On constrained mobile (e.g., older Android <2GB RAM), 64MiB may still be infeasible. Should the spec define a fallback chain (m=64MiB → m=32MiB → scrypt N=2^16) with explicit security degradation acknowledgment?

**Source:** 2026-05-13 loop-2 Security (mobile resource constraint).

---

## Q60 🟨 — Conformance vector authoring ownership

**Question:** Loop-3 conformance-vector authoring sprint (post-loop-2 plan): who byte-locks each of the 4 outstanding vectors (`05-message-envelope-diff`, `06-presig-bundle-encryption`, `09-rendered-text`, `18-recovery-kdf`)? Co-owned per Q10 / ADR-0028, but cadence + ownership matrix not yet defined.

**Source:** 2026-05-13 loop-2 (cross-dimension).

---

## Q14 🟨 — AuthSocket extraction as separate crate

**Question:** Should the BRC-31-authenticated WebSocket layer (currently `~/bsv/rust-message-box/src/engineio/auth.rs` + `engineio/codec.rs`, ~1.3k LOC) be extracted as a standalone `bsv-authsocket` crate, mirroring the TS ecosystem's split between `@bsv/authsocket-server`, `@bsv/authsocket-client`, and `@bsv/message-box-client`?

**Context:** Surfaced by Mitch in the 2026-05-12 partnership sync. The TS reference is cleanly split (server 261 LOC, client 168 LOC, zero messagebox dependencies) and earns its keep because multiple TS consumers exist. The Rust auth/codec modules are already a messagebox-free island (zero `MessageHub` references in `auth.rs`/`codec.rs`) — extraction is mechanical. But `rust-mpc`'s `bsv-messagebox-client@0.1.1` does NOT consume an authsocket abstraction (Binary owns the WebSocket+BRC-103 bytes inline at `websocket.rs` + `socket_transport.rs`), and no other crate in `~/bsv/` currently needs BRC-103-authenticated WebSocket.

**Recommended resolution:** **Defer.** Spec §06 documents the boundary; promote to `bsv-authsocket` crate when (a) the partnership agrees to standardize a single Rust AuthSocket type across `rust-mpc` and `rust-message-box`, or (b) a second BSV Rust service needs BRC-103-authed WS. Sizing when triggered: ~1.4k LOC lift + ~1 day Cargo.toml/CI work; 2 import-path changes in `rust-message-box`; no external library consumer breaks (it's a Worker binary).

**Becomes:** ADR-TBD (no number reserved; assign when triggered).

---

## Resolution log

(Each Q closes here when its ADR is accepted.)

| Q | Resolution | ADR | Date |
|---|---|---|---|
| Q8 | Cold-tier HSM operator role deferred to v2; v1 ships without HSM/TEE. v2 successor ADR to be filed (number TBD) when institutional users appear. | [ADR-0016](decisions/0016-v1-ops-topology-no-tee-no-hsm.md) | 2026-05-10 |
| Q3 | Presigning over MessageBox: cosigner-encrypted shares stored at coordinator with burn-rate regen + mandatory invalidation. Reference impl shipped on `rust-mpc` side; `bsv-mpc` impl outstanding. | [ADR-0030](decisions/0030-presig-coordinator-storage.md) | 2026-05-12 |
