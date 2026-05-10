# Appendix D — Protocol / Crypto

> Full report from the Protocol/Crypto zone agent of the god-tier-design swarm (2026-05-10).
> Preserved verbatim as supporting depth for [`§01-cggmp24-pin.md`](../../01-cggmp24-pin.md), [`§02-execution-id.md`](../../02-execution-id.md), [`§03-brc42-invoice.md`](../../03-brc42-invoice.md), [`§04-session-id.md`](../../04-session-id.md).

---

A vendor-neutral BSV threshold-signing network needs the protocol layer to be (a) interoperable byte-for-byte across two independent Rust implementations, (b) provably secure against a malicious dishonest majority, (c) composable with BSV-specific quirks (sighash flags, OP_CODESEPARATOR, BRC-42 derivation), (d) survivable across at least two protocol-version migrations in the next 5 years (post-quantum, possible Schnorr/Taproot adoption on BSV), and (e) debuggable when one of three operationally-distinct cosigners cheats.

## §A — God-tier definition + 5-axis rubric

A "god-tier" crypto choice for this network must clear all five axes simultaneously, not optimise one:

| Axis | Concrete bar |
|---|---|
| **1. Security** | UC-secure against malicious t-1 corruptions; identifiable abort (UC-IA); proven against the TSSHOCK-class of attacks (c-split, ZK-omission, presig forgery — Verichains @ BlackHat'23); audited by an external lab; immune to or hardened against side-channel timing leaks; PQ-migration story exists. |
| **2. UX** | DKG ≤ 2 s at 50 ms RTT; presigned signing ≤ 1 RTT; full signing ≤ 4 RTT; presign-pool refill amortises to free; recovery via threshold-resharing on existing key (POC 13 pattern), 0 on-chain cost. |
| **3. Vendor-neutrality** | Spec is byte-defined; both implementations produce identical bytes from identical inputs; ≥2 mature library implementations across ≥2 languages exist for each scheme; no patents; no vendor-controlled trust roots. |
| **4. Operability** | Aborts pinpoint the cheating party with cryptographic evidence consumable by the policy/audit layer; refresh, threshold-change, and scheme-migration all defined; spec versioning embedded in every transcript. |
| **5. Composability** | BRC-42 derivation works without per-derivation MPC round-trips for the common case; sighash flags (0x41 ALL\|FORKID, etc.) and OP_CODESEPARATOR don't require protocol changes; nested MPC (notary co-signing a fee-pool key that itself is MPC) is possible; Schnorr/Taproot dual-protocol forward-prep. |

Mandatory comparators per the brief:

| Protocol | Year | Rounds (sign) | Rounds (preproc) | Crypto basis | Audit | Identifiable abort |
|---|---|---|---|---|---|---|
| GG18 / GG20 | 2018/2020 | 6–9 | — | Paillier + range proofs | multiple, TSSHOCK-broken in many impls | partial |
| **CGGMP'21 / CGGMP'24** | 2021/2024 | 1 (with presig) / 4 (no presig) | 3 (presig) + DKG + AuxInfo | Paillier + ZK + PSS | Kudelski (LFDT-Lockness) + Trail of Bits; **2 CVEs in late 2025** (CVE-2025-66016 missing ZK check, CVE-2025-66017 presig forgery) | **yes (UC-IA)** |
| **DKLs23** | 2023 | 3 (no preproc, OT-based) | optional VOLE preproc | OT/VOLE, **no Paillier**, no safe primes | Trail of Bits 2025 Silence Labs review found "serious flaws… key destruction attacks" — fixed | yes |
| FROST | 2020 | 1 + 1 preproc | 0 | Schnorr (BIP-340 sig shape) | RFC 9591 standardised; ROAST robustness wrapper | yes |
| cb-mpc (Coinbase) | 2025 OSS | C++ library; supports ECDSA + Schnorr/EdDSA | C++, no WASM | partial |

**Headline:** for BSV today, with secp256k1 the only signature curve in consensus, **CGGMP'24 is still the right baseline** — but only on the post-CVE'25 patched series, with explicit hardening, and with an explicit migration on-ramp to DKLs23 once a production-grade pure-Rust implementation matches CGGMP'24's library maturity.

## §B — Option 1: "CGGMP'24 + BRC-42 done right" (RECOMMENDED for v1)

Pin the LFDT-Lockness `cggmp21` repo's `cggmp24/m` branch at a commit **on or after the patches for CVE-2025-66016 and CVE-2025-66017** (≥ v0.7.0-alpha.2 of the cggmp24 line). Calhoun's fork (`Calgooon/cggmp21-fork#brc42-additive-shift`) is rebased on top of that commit. The fork adds exactly one public method behind the existing `hd-wallet` cfg — `set_additive_shift(scalar)`. Open the upstream PR week 1.

**Derivation:** keep BRC-42, fix it. The current divergence (bsv-mpc skips `.to_lowercase().trim()`, rust-mpc applies it — convergence §1.4) is a P0 wire break. The canonical invoice is the one that matches the BSV TS SDK contract, which both `bsv-worm` and the existing wallet ecosystem are bound to. So bsv-mpc's `hd.rs::compute_invoice` adopts rust-mpc's normalization, full stop.

**Partial-ECDH for Self/Other:** unavoidable structurally. BRC-42's `Self_` and `Other(pubkey)` counterparties require an ECDH between the wallet's own private key and the counterparty pubkey, *and* the wallet's private key is split — so one MPC round-trip per derivation is fundamental, not a design flaw. POC 8 measured this at ~16 ms over the production CF Worker KSS, which is acceptable.

Lock canonical aggregation: **rust-mpc's `aggregate_ecdh_partials` is naive sum** (correct only for additive sharing, not VSS). bsv-mpc's `combine_partials_lagrange` is the correct threshold form. The spec mandates Lagrange interpolation at x=0 — rust-mpc's "naive sum is fine because the layer above does Lagrange in `protocol/src/signer.rs::pre_derive`" pattern is fragile and easy to misuse; force the canonical form into the brc42 crate itself.

**Identifiable abort, concretely:** CGGMP'24 produces, on every cheating event, a verifiable transcript that names a specific party index. The spec requires that:
1. On any `MpcError::Signing` or `MpcError::Dkg` containing a cggmp24 protocol error variant of type `BadParty(i, evidence)`, both the local protocol-error handler AND the policy/audit layer write a BRC-22 audit record `{session_id, eid, accused_party_index, accused_identity_pubkey, evidence_blob, transcript_hash}`.
2. Aborts that are *not* attributable (network drop, transport timeout, malformed envelope before SM dispatch) have a separate error class and DO NOT name a party.
3. The cosigner cert (BRC-52) carries the `accused_party_index → identity_pubkey` mapping at session-start time so a transcript-only auditor can re-derive who was accused without trusting the coordinator.

**Side-channel defense:** the threat is a malicious cosigner who watches its own transcript and tries to extract bits of an honest party's key share. CGGMP'24 is UC-secure under simulation, so semantically this is impossible *if the implementation is correct*. The TSSHOCK class (Verichains BlackHat'23) showed that "audited" ≠ "correct" — most GG18/20/CGGMP'21 implementations were broken. Mitigations the spec mandates:
- All scalar operations use `generic-ec`/`generic-ec-zkp` constant-time backends (already in cggmp24 upstream).
- No serde_json error messages may leak share bytes.
- The `insecure-assume-preimage-known` feature (rust-mpc enables it, bsv-mpc does not) is **explicitly allowed** in the spec because BSV sighashes are pre-hashed (SHA-256d) before the protocol sees them; the "insecure" name is misleading in the BSV context. Spec mandates both implementations enable it.

**Grading:**
- Security 8/10 — UC-IA proven; CVE'25 patches apply; TSSHOCK-class implementation flaws still possible (auditing the Calhoun fork is mandatory before mainnet GA).
- UX 7/10 — DKG is multi-round and AuxInfo is Paillier-prime-heavy. Presigned-1-round signing is ≤ 1 RTT; full 4-round is ~200 ms over MessageBox.
- Vendor-neutrality 9/10 — only one mature pure-Rust implementation today (LFDT-Lockness), but the protocol is pinned to a named ePrint paper, the fork patch is 15 lines, and we can ship reproducible test vectors.
- Operability 8/10 — UC-IA gives clean abort attribution. Refresh works (POC 13). Threshold change works. Migration story to DKLs23 is "regenerate from the same seed via key refresh" — same joint pubkey, same on-chain identity preserved.
- Composability 8/10 — BRC-42 plugs in via `set_additive_shift`; nested MPC works (KSS is itself a multi-party operator); BSV sighash flags don't change the protocol because cggmp24 takes a 32-byte digest. OP_CODESEPARATOR is handled at the BSV-tx layer, not here.

## §C — Option 2: "DKLs23 + BRC-42 unchanged" (Strong contender for v2)

DKLs23 (Doerner-Kondi-Lee-Shelat ePrint 2023/765) achieves **3 rounds for malicious-secure threshold ECDSA against a dishonest majority, with no Paillier, no safe primes, and no homomorphic encryption** — purely OT/VOLE. Round-count and DKG cost both improve dramatically; the Silence Labs production library is real and Trail-of-Bits-reviewed.

Concrete deltas vs Option 1:
- DKG: no Paillier prime gen → DKG drops from 30–60 s to sub-second.
- Signing: 3 rounds always; presigning still optional but presig-pool replenishment is cheaper (no MtA-with-Paillier).
- Bandwidth: DKLs23 with VOLE is competitive with all prior schemes per the paper.
- Side-channel posture: better — no Paillier means no Paillier-specific attack surface (and TSSHOCK's c-split is Paillier-specific).

Why **not** Option 1 today:
- BRC-42's `set_additive_shift` analogue in DKLs23 doesn't exist as a public API in the Silence Labs library yet — would be a fork analogous to Calhoun's cggmp21 fork but harder (DKLs23's nonce structure is different).
- DKLs23 in Rust today is the Silence Labs library only; CGGMP'24 has the LFDT-Lockness production library used by Dfns and others. Two-implementation-neutrality is weaker on DKLs23 in May 2026.
- The Trail-of-Bits audit found *fixable but real* "key destruction" flaws — DKLs23 implementations are younger.
- Migration story: same as Option 1 — refresh-then-rotate-protocol.

**Recommendation:** Option 2 is the v2 target. Spec design choice: pick a **"protocol envelope"** that names the underlying TSS scheme as a tagged variant, so v1 ships as `tss = "cggmp24-v1"` and v2 ships as `tss = "dkls23-v1"` over the same envelope, transport, and identity layers.

## §D — Option 3: "Dual-protocol with Schnorr forward-prep" (Hedge)

BSV consensus today supports only ECDSA via OP_CHECKSIG. There is no live Schnorr/Taproot proposal on BSV (as of May 2026). But the spec must contemplate "what if it does" because a 5-year horizon with the network's current design momentum makes BSV-Schnorr non-zero probability.

In that future, **FROST3 is the right Schnorr threshold scheme** (RFC 9591, with ROAST as a robustness wrapper). FROST is *much* simpler than CGGMP'24 — 1+1 rounds, no Paillier, no safe primes, no MtA. It has identifiable abort natively (PartialSigVerify). Its output is a standard BIP-340 signature.

The dual-protocol story:
- **Spec defines `algorithm = "ecdsa-cggmp24" | "ecdsa-dkls23" | "schnorr-frost"`** in the protocol envelope.
- The joint pubkey on-chain is identical for both ECDSA and Schnorr (same secp256k1 point) — same DKG, different signing protocol on top. POC 13's threshold-resharing pattern lets us migrate the signing protocol without moving funds.
- Both ECDSA flavours and FROST share the `set_additive_shift` style BRC-42 hook.

This is **not the v1 recommendation** — it's a forward-compatibility constraint on the spec language. The spec defines the algorithm tag now so we don't have to break the message envelope when BSV-Schnorr ships.

## §E — Cross-layer dependencies

The protocol choice constrains four other layers:

1. **Transport latency budget:** Option 1 (CGGMP'24) needs 4 round-trips for full signing without presig and 1 with. With presigning over MessageBox missing in rust-mpc today, presigning is on the v1 critical path.

2. **Identity binding:** ExecutionId binds the protocol transcript to (a) the joint pubkey, (b) the BRC-52 cosigner cert chain, (c) the spec version. A change of TSS protocol must therefore be visible inside the `algorithm_tag` byte of the ExecutionId formula, so a cross-protocol replay attack is impossible.

3. **Audit format:** BRC-18 participation proofs include a `session_hash`. Spec mandates this hash binds to the *full* ExecutionId, not just the session-id string — so the on-chain proof is unforgeable evidence that *this* specific protocol version with *this* specific joint key signed *this* specific sighash.

4. **Policy / cert binding:** the cosigner certificate (BRC-52) MUST list which `algorithm_tag` values the cosigner is approved to participate in. A v1-only cosigner that receives a `dkls23-v1` ceremony rejects pre-DKG. This makes scheme-migration a per-cosigner opt-in, not a network-wide flag day.

## §F — Direct answers to the brief's required questions

**1. Is cggmp24 right for 5 years?** Yes for v1 (post-CVE'25 patches), no for v3+. Migration target is DKLs23 once a 2nd-implementation Rust DKLs23 reaches CGGMP'24's maturity. Migration mechanism: protocol-envelope `algorithm_tag` + per-cosigner cert opt-in + threshold-resharing on the same key.

**2. BRC-42 right derivation scheme?** Yes — it is the BSV ecosystem standard and incompatible with anything else without breaking BRC-100 wallet compat. The "TSS-friendlier" alternative (SLIP-10/BIP-32) does not match BSV semantics. The 1-RTT cost for Self_/Other counterparties is structural, not an artifact, and is bounded ~16 ms over production KSS — acceptable.

**3. ExecutionId formula?** Per [`§02-execution-id.md`](../../02-execution-id.md) — locked, with test vectors.

**4. SessionId scheme?** Per [`§04-session-id.md`](../../04-session-id.md) — deterministic hash of inputs, optional on-chain anchor for high-value ceremonies. Not random.

**5. Schnorr forward-prep?** Yes — bake `algorithm_tag` into ExecutionId today; FROST3 is the implementation if BSV ever ships Schnorr. No code change in v1.

**6. PQ migration?** Hybrid (classical + lattice) threshold sigs are research-grade only as of May 2026 (RACCOON, etc.). The spec's PQ migration story is the same as the DKLs23 migration story — protocol envelope + threshold-resharing. Don't hard-code a PQ choice today.

**7. Identifiable abort, concretely:** §B above.

**8. Side-channel threat model:** malicious cosigner trying to extract bits from honest party's transcripts. Defense: UC-secure protocol + constant-time arithmetic + redacted error strings + no debug-print of secret types. Mandate periodic refresh (POC 13 pattern) so any slow side-channel leak is bounded.

## Sources

- DKLs23 paper (ePrint 2023/765)
- TSSHOCK BlackHat'23 paper
- Verichains TSSHOCK page
- LFDT-Lockness cggmp21 repo
- GHSA-8frv-q972-9rq5 (CVE-2025-66016 + CVE-2025-66017)
- Coinbase cb-mpc release blog
- Trail of Bits review of Silence Labs DKLs23
- silence-laboratories/dkls23
- RFC 9591 — FROST
- ROAST paper (ePrint 2022/550)
- BRC-42 spec
- Dfns CGGMP21-in-Rust article
