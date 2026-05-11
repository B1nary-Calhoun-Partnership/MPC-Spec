# Open Questions

> Questions the partnership needs to settle. Each one becomes an ADR once resolved.

Status legend:
- 🟥 **Blocking** — Phase 0 cannot lock until resolved.
- 🟧 **Important** — Phase 1+ depends on this.
- 🟨 **Open** — design optionality; not blocking but worth deciding.

---

## Q1 🟥 — CGGMP CVE patches

**Question:** Will Binary pin `rust-mpc` to LFDT-Lockness `cggmp24/m` ≥ 0.7.0-alpha.2 (post-CVE-2025-66016 + post-CVE-2025-66017) before any joint mainnet ceremony?

**Context:** CGGMP'21/24 had two CVEs disclosed in late 2025 ([GHSA-8frv-q972-9rq5](https://github.com/LFDT-Lockness/cggmp21/security/advisories/GHSA-8frv-q972-9rq5)): missing ZK proof check, presignature forgery. Both implementations must pin past these.

**Recommended resolution:** Yes. Both repos pin same commit. Calhoun's fork rebased on top.

**Becomes:** ADR-0001 (already drafted in [`decisions/0001-cggmp24-pin-past-cve-2025.md`](decisions/0001-cggmp24-pin-past-cve-2025.md))

---

## Q2 🟥 — Lagrange canonicalization location

**Question:** `rust-mpc/crates/brc42::aggregate_ecdh_partials` does a naive point sum today. The threshold-correct Lagrange combine lives one layer up in `protocol/src/signer.rs::pre_derive`. Should we move Lagrange into the `brc42` crate so the function is correct-by-construction?

**Context:** Naive-sum is correct only for additive sharing (vss=None). With Verifiable Secret Sharing (VSS, what cggmp24 produces from DKG), the threshold combine requires Lagrange interpolation at x=0. The current placement works but is fragile — any caller that bypasses `pre_derive` and uses `aggregate_ecdh_partials` directly produces wrong results silently.

**Recommended resolution:** Move into `brc42` crate as `combine_ecdh_partials_lagrange(partials, vss_setup)`. Force the canonical form.

**Becomes:** ADR-0009 (TBD)

---

## Q3 🟥 — Presigning over MessageBox

**Question:** `rust-mpc/crates/transport/src/messagebox_cosigner.rs:207,217` returns `TransportError::Protocol("...not supported via MessageBox")` for `presign_round` and `collect_presig_share`. Presigning currently goes through a different code path. What's the intended fast-path for cross-implementation signing?

**Context:** Without presigs over MessageBox, cross-impl signing must take the 4-round path every time. With **WebSocket as canonical** (per ADR-0006 / §06), the 4-round path is ~200 ms over WS at 50 ms RTT — usable but not great. With presigs, signing is 1 round (~50 ms over WS). For a Notary product, sub-second is the difference between "feels like Stripe" and "feels like a Citrix client." This question is no longer transport-blocked (WebSocket-canonical removes the poll-latency objection), but presigning round-handling over MessageBox is still missing in `rust-mpc`.

**Recommended resolution:** Implement `presign_round` over MessageBox using the same envelope as DKG/sign rounds. ExecutionId already binds the ceremony, so round-binding is straightforward. With WebSocket-canonical receive, presig rounds match DKG/sign rounds in shape.

**Becomes:** ADR-0010 (TBD)

---

## Q4 🟧 — Cert format consolidation

**Question:** `rust-mpc` has two non-interoperable cert types: `core::identity::Certificate` (custom JSON struct, used by `policy/engine.rs::verify_party_certificate`) and BRC-52 binary (issued by `bins/certifier/`). Will Binary deprecate the custom struct in favor of BRC-52⊕ (this spec's profile)?

**Context:** Federation between Calhoun and Binary roots requires one canonical cert format. BRC-52 is the BSV ecosystem standard; the custom struct doesn't interoperate with anything. Spec §08 mandates BRC-52⊕.

**Recommended resolution:** Yes. Move policy engine's `verify_party_certificate` to verify BRC-52. Migrate cosigner identities. Deprecation can be progressive (accept both for one release, then drop the custom struct).

**Becomes:** ADR-0011 (TBD)

---

## Q5 🟧 — Cedar policy DSL migration plan

**Question:** Will Binary ship the canonical-CBOR PolicyManifest schema now (Spec §09) understanding that the schema is intentionally Cedar-shaped, so we can migrate to Cedar (AWS Verified Permissions, Rust-native, Dafny-verified) when Cedar's `wasm32-unknown-unknown` `[no_std]` story matures?

**Context:** Cedar is the strongest competitor as a policy DSL — formally verified, differentially fuzzed, Rust-native. Today Cedar requires `std`, which kills the bsv-mpc-worker WASM use case. Canonical CBOR is the ship-now answer; the schema is laid out so a Cedar migration is mechanical (not a rewrite).

**Recommended resolution:** Yes. Schema lives in `mpc-policy-shared` crate. Migrate when Cedar WASM lands.

**Becomes:** ADR-0012 (TBD)

---

## Q6 🟨 — Iroh QUIC as direct-P2P accelerator

**Question:** Spec §06.8 reserves Iroh QUIC + holepunch for post-DKG direct-P2P signing (sub-100 ms). Iroh is one project, one team (n0-computer); the protocol isn't IETF-standardized. Are we OK taking the bet, or wait for a more standardized substrate?

**Context:** Iroh's "dial keys instead of IPs" model fits BRC-31 identity-key routing exactly. WebTransport is the IETF-standard alternative but lacks holepunch + relay-fallback. libp2p QUIC is more mature but heavier and has poor browser/CF Worker support.

**Recommended resolution:** Reserve Iroh in §06 as opportunistic accelerator. Spec language allows substitution with WebTransport or libp2p QUIC at implementation discretion. The MPC layer doesn't observe the substrate — only that envelope delivery happened.

**Becomes:** ADR-0013 (TBD)

---

## Q7 🟨 — Schnorr forward-prep

**Question:** `algorithm_tag = 0x03` is reserved for FROST3 in §02 ExecutionId. Cheap reservation — zero v1 code change. Do we want a real implementation experiment to de-risk migration if BSV ever adds Schnorr?

**Context:** BSV consensus is ECDSA-only today. Probability BSV follows Bitcoin's BIP-340/341/342 over the next 5 years is non-zero. FROST3 is dramatically simpler than CGGMP'24 (1+1 rounds, no Paillier). Same DKG → same joint pubkey → ECDSA *or* Schnorr signing on top.

**Recommended resolution:** Reserve `0x03`. Do not implement v1. Revisit when/if BSV proposes Schnorr support.

**Becomes:** ADR-0014 (TBD; may stay in OPEN-QUESTIONS if BSV doesn't move)

---

## Q8 🟨 — Cold-tier HSM operator role (DEFERRED to v2)

**Question:** Spec §16 originally recommended a hybrid hot-TEE + cold-HSM topology. Who operates the cold tier?

**Resolution:** **Deferred to v2.** ADR-0016 confirmed v1 ships without HSM cold tier (cost: ~$1K/mo CloudHSM cluster) and without TEE (cost: ~$300/mo per cosigner Nitro). v1 runtime integrity is from threshold + share refresh + audit + witness cosigning. When v2 institutional users appear, this question reopens.

Forward-compat: cert format reserves `attestation` field; policy engine reserves `RuleKind::RequireAttestation`. No wire change needed when v2 activates.

**Becomes:** ADR-0019 or later (when v2 begins).

---

## Q9 🟨 — Recovery-key escrow for quorum-loss DR

**Question:** Spec §18 covers normal recovery (threshold resharing). Catastrophic recovery (DR case (c): two of three cosigners simultaneously fail) requires user-driven encrypted backup. Where does the backup live?

Options:
- (a) **User's BRC-100 wallet storage** — encrypted with a key derived from the user's identity. User-only restore.
- (b) **Jurisdiction-distributed escrow** — one share at user's wallet, one at jurisdiction-A escrow, one at jurisdiction-B escrow. User must convince 2 of 3 to release.
- (c) **Both (a) and (b) — user picks per-account.**

**Recommended resolution:** (c). Default (a). Power users opt into (b) via spec extension.

**Becomes:** ADR-0016 (TBD)

---

## Q10 🟨 — Conformance test suite ownership

**Question:** Conformance tests in `conformance/` must be runnable by both implementations. Who writes the test runner?

**Recommended resolution:** Co-owned. Test vectors are language-neutral (JSON / hex). Each implementation writes its own runner that loads the vectors and asserts. CI in this repo runs both runners against the canonical vectors.

**Becomes:** ADR-0017 (TBD)

---

## Q11 🟨 — Steward assignment

**Question:** Who is the Binary-side steward of this repo?

**Recommended resolution:** Binary picks. Default suggestion: Ishaan Lahoti (per the partnership doc's identification of him as production-hardening lead).

**Becomes:** governance note in README, not an ADR.

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

**Becomes:** ADR-0020 or later (v1.5+).

---

## Resolution log

(Each Q closes here when its ADR is accepted.)

| Q | Resolution | ADR | Date |
|---|---|---|---|
| (none yet) | | | |
