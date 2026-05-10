# Design Rationale

> The "why" behind every spec decision. Read this if `PROPOSAL.md` left you wanting more depth.
> Detailed per-zone analysis is in [`appendices/swarm-reports/`](appendices/swarm-reports/).

## How this document is organized

- **§A** — design rubric (the 5 axes every choice grades against)
- **§B** — per-layer picks, why they win, what alternatives survive as profiles
- **§C** — cross-layer dependencies (which choice constrains which)
- **§D** — production-system precedents informing each choice
- **§E** — notable rejected designs and why

## §A. The 5-axis rubric

Every layer's recommended option grades against:

1. **Security** — defense in depth, formal guarantees, threat-model coverage, supply-chain integrity.
2. **UX** — latency budgets, onboarding friction, recovery friction, error visibility.
3. **Vendor-neutrality** — no operator load-bearing; substitutability; multi-deploy; censorship resistance.
4. **Operability** — observability, debuggability, key rotation, disaster recovery, monitoring.
5. **Composability** — nested MPC (Mitch's "MPC wallet exposes BRC-100"); BRC-100 surface; SDK story.

A "god-tier" choice clears all five simultaneously. Single-axis-optimized designs (e.g., max-security but unusable; max-UX but custodial) are rejected.

## §B. Per-layer picks

### B.1 Transport (§06) — federated MessageBox + edge-local receive + Iroh accelerator

**Pick.** Async, end-to-end-encrypted, sender-signed canonical CBOR envelope routed via per-cosigner-pinned MessageBox relays. Edge transport (native WebSocket / FCM-triggered HTTP / HTTP poll) is the receiver's local choice; spec doesn't force one. Iroh QUIC reserved as post-DKG accelerator. Tor v3 onion as max-privacy profile.

**Why this wins.**
- Only architecture that runs in CF Workers, browsers, mobile, and servers today (matters for BRC-100 surface).
- **WebSocket is the canonical receive transport on both relays.** `bsv-messagebox-cloudflare` (Calhoun) adds Socket.IO/EngineIO compatibility over CF Worker Durable Objects, restoring parity with `<binary-messagebox-host-tbd>`'s existing WS surface. HTTP poll and FCM remain as MUST-support fallbacks for constrained edges (browser without WS, mobile background, edge runtimes without DOs). The unlimited-resource framing makes this the right call vs my earlier constraint-driven proposal to leave `bsv-messagebox-cloudflare` HTTP-only.
- Federation lets each cosigner pick its preferred relay; envelope is identical regardless of which relay carries it.
- BRC-22 SLAP/CHIP overlay is the directory; no DHT, no bootnodes — the blockchain is the registry.
- Three-axis metadata privacy: default (relay sees `from→to`), Tor (relay sees `tor→tor`), one-hop mix-via-cosigner (intermediate ring).

**Alternative profile preserved.** Iroh QUIC for post-DKG fast path. Once two cosigners DKG together and cache each other's iroh nodeids in CHIP token refresh, subsequent ceremonies attempt direct QUIC first; relay fallback is transparent at the QUIC layer.

**Production precedents.** Lit Protocol's relay-mesh; Matrix Olm/Megolm's "encryption layered above transport" pattern; Iroh's "dial keys not IPs" thesis; SPIFFE federation.

**See appendix:** [`appendices/swarm-reports/A-transport.md`](appendices/swarm-reports/A-transport.md)

### B.2 Identity & certificates (§08) — BRC-52⊕

**Pick.** BRC-52 binary cert (rust-mpc certifier already issues this) profiled with three mandatory extensions:
- **`notAfter`** — short TTL (24h cosigner / 1h human-approver / 7d federation root). Bounds compromise window.
- **`ctlog_proof`** — Merkle inclusion proof against BRC-22 transparency log topic `tm_mpc_certs_v1`. Mis-issuance detectable externally.
- **`subjectScheme: "single" | "threshold"`** — `"threshold"` lets a 2-of-3 wallet have a cert whose subject IS a joint pubkey, signed by a threshold signature. **Recursive MPC native.**

Plus: `policy_hash` binds cert to canonical-CBOR PolicyManifest (§09); `attestation` field optional for TPM/TEE/WebAuthn provenance; `root_set` declares accepted cross-signing roots.

**Why this wins.** Short TTL bounds compromise window (SPIFFE SVIDs default ≤1 hour; Sigstore Fulcio uses 10 minutes). Transparency log makes mis-issuance externally detectable (CT logs, Sigstore Rekor are the precedents). Threshold-subject is the missing primitive for nested MPC. Reuses rust-mpc's existing BRC-52 certifier; deprecates the parallel `core::identity::Certificate` JSON struct cleanly.

**Alternative profile preserved.** Fulcio-style ephemeral certs (per-ceremony fresh keypair generated in TEE, 10-min cert, single-use) for institutional/regulated tier. Strictly stronger security; over-engineered for routine 2-of-3 agent wallets. Same wire format, different TTL semantics.

**Federation mechanism.** Mutually issue BRC-52 root certs to each other (subject = peer root, ttl = 7d, root cert), publish to shared `tm_mpc_certs_v1` log, list in cosigners' `accepted_cert_roots`. **No privileged primary root.** Self-issued (subject == certifier) cosigner certs PERMITTED — trust is delegated to discovery + reputation, not certification.

**Mandatory rust-mpc certifier hardening:** `OsRng` for `serverNonce` (currently deterministic); BRC-31 auth on `/signCertificate` (currently unauthenticated); `mpc_storage::sqlite` persistence (currently in-memory wipes on restart).

**Rejected: W3C VC / DID as primary.** Forces W3C-VC layering for marginal vendor-neutrality gain when BRC-52⊕ already delivers. Use DIDs/VCs as an *export adapter* for cross-ecosystem interop. Canonical wire format stays BRC-52.

**See appendix:** [`appendices/swarm-reports/B-identity.md`](appendices/swarm-reports/B-identity.md)

### B.3 Policy & audit (§09, §10) — Canonical-CBOR manifest + embedded Rekor + BSV anchoring + witness co-signing

**Pick.** PolicyManifest is canonical-CBOR (RFC 8949 §4.2) embedded as a CBOR `bstr` inside the BRC-52 cert. Schema is a typed extension of rust-mpc's `AutoApproveRule` plus the gap fixes: `min_fee_sats`, `cumulative_daily_cap_sats`, `allowed_window`, `counterparty_allowlist/denylist`, `jurisdiction`, `require_approval(k-of-m)`. **Engine fires on three hooks**: `check_derivation`, `check_presigning`, `check_signing`. **Presigs are bound to `policy_id` at generation time** (added to ExecutionId per §02) — rollbacks invalidate stockpile.

**Audit substrate.** Each cosigner runs an embedded Sigstore Rekor-style append-only Merkle log (RFC 6962 / Trillian-compatible). Required event set: 11 events from `DkgInitiated` through `PartyAborted`. Every 60 seconds, sign STH and publish hash to BSV as BRC-18 OP_RETURN under topic `tm_mpc_audit`. **Other cosigners witness-co-sign each STH on every signing ceremony** — non-repudiation primitive. BRC-18 participation proof becomes a *projection* of the audit log (cites `audit_root + audit_index`).

**Why this wins.**
- Three-hook engine fixes rust-mpc's current `engine.rs:236-239` allow-all-presigning gap.
- Presig-binding-to-policy_id is the missing presig gate.
- Witness co-signing is the strongest practical audit-integrity guarantee available without TEE.
- BSV anchoring resolves the three-way OP_RETURN prefix conflict (draft / core / overlay disagree).

**Rejected for v1: Cedar.** Strongest competitor — Rust-native, Dafny-verified, formally proven sound, AWS Verified Permissions in production. Today Cedar requires `std`, kills bsv-mpc-worker WASM. **Schema is intentionally Cedar-shaped so migration is mechanical when Cedar's `[no_std]` matures.** See ADR-0012 path.

**Rejected for v1: OPA/Rego.** ~30MB, doesn't run in CF Workers. Park as v2 federation upgrade if WASM-OPA matures.

**TOML→CBOR transpiler.** Operators write TOML (operator-friendly); certifier transpiles to canonical CBOR + signs. Best-of-both-worlds for authoring UX.

**See appendix:** [`appendices/swarm-reports/C-policy-audit.md`](appendices/swarm-reports/C-policy-audit.md)

### B.4 Crypto/protocol (§01–05) — CGGMP'24 patched (v1), DKLs23 reserved (v2), Schnorr forward-prep (v3)

**Pick for v1.** Both implementations pin LFDT-Lockness `cggmp21` `cggmp24/m` ≥ 0.7.0-alpha.2 (post-CVE-2025-66016 + post-CVE-2025-66017). Calhoun's `cggmp21-fork#brc42-additive-shift` rebases the 4-line `set_additive_shift` patch on top. Upstream PR opens week 1.

**Required cargo features:** `hd-wallet`, `insecure-assume-preimage-known` (BSV sighashes are pre-hashed; feature name is misleading for our use case), `num-bigint` (NOT `rug` — GMP is LGPL, doesn't target wasm32). secp256k1 only. SecurityLevel128.

**Forbidden:** disabling `enforce_reliable_broadcast`, skipping aux-info generation, using cggmp24 < 0.7.0-alpha.2 in any release build.

**BRC-42 derivation — fix bsv-mpc, lock canonical:**
```
invoice = "{security_level}-{protocol_id.to_lowercase().trim()}-{key_id}"
hmac    = HMAC-SHA256(key=compressed_shared_secret_33B, data=invoice.as_bytes())
offset  = Scalar::from_be_bytes_mod_order(hmac)
```
**rust-mpc is right; bsv-mpc must apply `.to_lowercase().trim()`** to match the BSV TS SDK contract.

**Force Lagrange into the brc42 crate.** rust-mpc's `aggregate_ecdh_partials` does naive sum (correct only for additive sharing); the threshold-correct combine is one layer up in `protocol/src/signer.rs::pre_derive`. Spec mandates Lagrange at x=0 inside the brc42 crate itself — same math, prevents misuse.

**Canonical ExecutionId** (replaces both implementations' formulas):
```
ExecutionId = SHA256(
    "calhoun-binary-mpc"     // 18-byte ASCII domain separator
    || 0x01                   // version (mpc-spec-v1)
    || algorithm_tag          // 0x01=cggmp24, 0x02=dkls23 (v2), 0x03=frost (v3)
    || phase_tag              // 0x01=keygen, 0x02=auxinfo, 0x03=presign, 0x04=sign, 0x05=ecdh
    || session_id_32B
    || joint_pubkey_33B       // all-zeros during keygen (joint key not yet known)
)
```

**Canonical SessionId:**
```
SessionId = SHA256(
    "calhoun-binary-mpc-session-v1"
    || initiator_identity_33B
    || sorted_participant_identities_concat
    || threshold_u16_LE
    || ceremony_kind_byte
    || nonce_32B                // OsRng routine; recent BSV blockhash for high-value
    || payload_digest_32B       // dkg=SHA256("genesis"||policy_manifest); sign=sighash; presig=pool_id
)
```

**v2 path (DKLs23 — Doerner-Kondi-Lee-Shelat 2023).** 3 rounds malicious-secure, **no Paillier, no safe primes** → DKG drops from 30–60s to sub-second. Silence Labs has production library, Trail-of-Bits-reviewed in 2025. Migration via `algorithm_tag = 0x02` + threshold-resharing on same key (POC 13 pattern). Not v1 because (a) `set_additive_shift` analogue not yet upstream in DKLs23, (b) two-implementation neutrality weaker, (c) audit history younger.

**v3 forward-prep (FROST3 + ROAST).** Bake `algorithm_tag = 0x03` into ExecutionId today. Zero v1 code change. Activates if/when BSV consensus adds Schnorr (BIP-340 shape). FROST is much simpler than CGGMP — 1+1 rounds, no Paillier. Joint pubkey on-chain identical for ECDSA and Schnorr — same DKG, different signing protocol on top.

**Identifiable abort, concretely.** Spec mandates: every aborted ceremony either produces `(party_index, identity_pubkey, evidence_blob, transcript_hash)` (cryptographic accusation, written to BRC-22 audit) OR is classified as a non-attributable infrastructure error. Policy/audit layer treats these differently — accusations trigger reputation hits + IR-002.

**Side-channel discipline.**
- All scalar ops via `generic-ec` constant-time backends (cggmp24 default).
- `Debug` on key-material types prints `<redacted>` — no share bytes in error strings.
- 30-day refresh cadence (POC 13 pattern) bounds slow side-channel leaks.

**See appendix:** [`appendices/swarm-reports/D-protocol-crypto.md`](appendices/swarm-reports/D-protocol-crypto.md)

### B.5 Notary product, fees, discovery, UX (§11, §12, §15) — three tiers preserved

This is the one layer where **multiple options legitimately survive** — they're different product tiers, not competing answers.

**Default tier — Paid Cosigner in 2-of-3.** User holds 2 shares (one device + one passkey-encrypted backup via WebAuthn PRF), Notary holds 1. Per-sig fee 333 sats × 3 = 1000 sats default. **Single DKG** for onboarding (BRC-mpc-fees draft's "two DKGs" was wrong — node fee pool is a one-time setup *between operators*, not a per-user concern). Cold-start sub-1-second over WS, sub-2-seconds over MessageBox poll. **Level 2 P2MS fee output** (fix `fee_injector.rs` default — currently Level 1 split-P2PKH, contradicts BRC draft). Weekly settlement via 2-of-3 ceremony (POC 11 validated). Recovery via threshold-resharing + new Notary, 0 sats on-chain, no address change.

**Express tier — x402 paid signing oracle.** No DKG, custodial, BRC-29/x402 micropayment per call. **Strictly worse Lit Protocol PKP** for security — but useful as a sub-cent-tier ephemeral signer for low-value AI agents that accept custody risk for sub-cent transactions. Same Notary infrastructure runs both tiers; user opts in.

**Pro tier — Multi-Notary 2-of-5 reputation marketplace.** User holds 3 shares; 2 Notaries hold the other 2 of 5, drawn from a pool of 10+ overlay-registered Notaries. Wallet picks cheapest 2 healthy per signing. Maximum vendor-neutrality + Sybil resistance. Slow onboarding (5-of-5 DKG with strangers). 90-day graduation path post-MVP.

**Sybil resistance.** Every node's CHIP token is a real on-chain output (~1000 sats). Reputation: `discovery.rs` formula (proof_score 0.40, age 0.20, abort 0.25, fee 0.15). **`query_proofs` un-stub** before MVP — or replace with simpler "block-height-of-CHIP × successful-settlement-count" interim.

**Trust-on-first-use.** Borrow Sigstore's TUF + transparency-log model: Notary's CHIP token references a signed capability manifest (canonical CBOR, identity-key-signed); manifest hash committed to BRC-18 OP_RETURN topic `tm_mpc_notary_manifest`. First-time user verifies (1) manifest hash matches overlay, (2) signature chains to advertised identity, (3) identity has ≥30-day on-chain age + ≥N successful settlements.

**SDK surface (TypeScript + Rust):**
```
mpc.discover({ maxFeeSats, threshold: '2-of-3', region })
mpc.onboard({ notary, userShares: 2 })          → jointPubkey
mpc.sign({ tx, jointPubkey })                    → signedTx + feeReceipt
mpc.replaceNotary({ jointPubkey, newNotary })    → resharing, no on-chain move
mpc.recover({ passkey, jointPubkey })            → restore from backup
```

**Defensible economic moat.** The moat is the *marketplace of replaceable Notaries with on-chain capability advertisements and key-refresh-based switching*. Fireblocks structurally cannot follow.

**See appendix:** [`appendices/swarm-reports/E-notary-product.md`](appendices/swarm-reports/E-notary-product.md)

### B.6 Operations & supply chain (§16, §17) — Standard cloud + threshold + refresh + audit (v1)

**Pick for v1.** Three hot cosigners on standard cloud infrastructure (CF Worker / k8s pod / VM), each operator on diverse vendors/regions to reduce cloud-correlation risk. **No TEE, no HSM cold tier.** Runtime integrity from: share encryption at rest (AES-256-GCM with BRC-42-derived keys), 30-day share refresh (POC 13), audit log + witness cosigning (§10), per-cosigner policy enforcement (§09).

**Why no TEE in v1.** Cost: ~$0.40/hr extra on AWS Nitro = ~$300/mo per cosigner; multi-region multi-vendor = $1K+/mo just in enclave overhead. The cryptographic invariants we already have (threshold + refresh + audit + witness cosigning + share encryption) give strong properties without enclave hardware. TEE specifically defends host-OS root compromise; this is bounded by the share refresh cadence even without TEE. The cost-benefit argues for v2.

**Why no HSM cold tier in v1.** AWS CloudHSM is ~$1.45/hr/cluster (~$1K/mo) — same calculus. Reserved for v2 institutional tier when regulatory pressure for hardware-backed key custody appears.

**Forward-compat hooks preserved.** Cert format keeps `attestation` and `binary_hash` fields as OPTIONAL (§08). Policy engine keeps `RuleKind::RequireAttestation` schema (§09). When v2 adds TEE/HSM, no wire change needed.

**The unique BSV-MPC primitive (still holds).** Users move between `quorum_profile`s via resharing — no on-chain move, same joint pubkey. **v1 ships with one profile (`Hot`); v2 adds `HotPlusCold` (HSM cold tier) and `ColdOnly` (vault).** The mechanism is the same; v1 just doesn't activate cold-tier infrastructure.

Fireblocks fixes threshold at vault creation. We don't, even in v1 (refresh-and-rotate-quorum-shape works on hot-only too).

**Cross-party tracing.** OTel `traceparent` rides as MessageEnvelope field 12. **Strict attribute whitelist:** `mpc.session_id`, `mpc.execution_id` (32-byte hex), `mpc.phase`, `mpc.round`, `mpc.party_index`, `mpc.threshold`, `mpc.joint_pubkey_fingerprint` (first 8 bytes only — *not* the pubkey, to prevent linking sessions to addresses), `mpc.message_size_bytes`, `mpc.outcome`, `mpc.aborted_party` (only on identifiable abort), `error.type`. **Forbidden:** any scalar, commitment, nonce, partial signature, Paillier ciphertext, joint pubkey itself, sighash, BRC-31 nonces. **Spec ships a redaction linter that fails CI** if a span attribute matches a forbidden regex.

**Refresh choreography.**
- **RR-001 (Routine 30-day):** `RefreshOrchestrator` on lowest-online-party-index publishes `refresh.proposed` to MessageBox + BRC-22 with 24h ack SLA → `t` parties ack → resharing fires at T-0 → `refresh.completed` event.
- **IR-002 (Suspected compromise, 30-min):** detection signals (failed Rekor reverification, anomalous PCR, abnormal policy-decline rate, BRC-22 reputation drop) → on-call files IR → `t-1` other operators ack → resharing without the suspect → CHIP token revoked via `tm_mpc_revocations`.

**Catch-up resharing.** If a party is offline at refresh time, polynomial includes their *new* share evaluation, sealed to their BRC-52 cert pubkey, decryptable on next online. No operator can be coerced "in real time" to participate or block.

**Disaster recovery.**
- **(a) one cosigner data-destroyed:** other `t` execute party-replacement resharing with brand-new operator. ~5 min unavailability if presig pool drains; otherwise 0.
- **(b) one compromised online:** IR-002 immediately reshares without them; status amber; signing continues with `t-1` fault tolerance.
- **(c) two of three fail simultaneously:** quorum loss. Restoration via user recovery passphrase + jurisdictional escrow backup (runbook IR-009).

**TEE attestation — v2 reserved.** Cert format includes `tee_attestation` field (Nitro PCR0/PCR8 / SEV-SNP report / TDX TDREPORT) but is OPTIONAL in v1 and typically `none`. Counterparty policies MAY require non-empty attestation via `RuleKind::RequireAttestation` (also reserved). v2 institutional tier activates these.

**Supply chain — reproducible Cargo + Sigstore + SLSA L3.** `cargo --locked` with `SOURCE_DATE_EPOCH`, vendored deps, pinned `rust-toolchain.toml`, CI verifies bit-for-bit reproducibility on a second runner. `cosign sign-blob` per release; OIDC-keyless via Fulcio; entry to Rekor. **Cosigner refuses to start unless its own Rekor entry verifies.** Build-time provenance only (no TEE runtime cross-check in v1).

**See appendix:** [`appendices/swarm-reports/F-operations.md`](appendices/swarm-reports/F-operations.md)

## §C. Cross-layer dependency map

What each layer's choice constrains in others. Reading order matters: ExecutionId is the cryptographic anchor; transport assumes it; identity binds it; policy binds to identity; audit binds to identity + policy; ops binds across all.

| Choice | Constrains |
|--------|-----------|
| **ExecutionId formula** (§02) | All transport envelopes bind to it. Replay impossible across sessions/phases/algorithms. **Lock first.** |
| **BRC-42 canonicalization** (§03) | Derived keys diverge if not byte-identical. **bsv-mpc applies `.to_lowercase().trim()` to fix.** |
| **Transport envelope** (§05–06) | Identity (BRC-31 sigs over envelope), Audit (correlation_id propagation), Ops (`traceparent` field 10). |
| **BRC-52⊕ cert format** (§08) | Policy (manifest embedded), Audit (cert serial in BRC-18), Discovery (CHIP references serials), Federation (cross-signing roots). |
| **PolicyManifest schema** (§09) | Policy_id binds into ExecutionId (presig invalidation on rotation). Cert binds policy_hash. CHIP advertises policy_id. |
| **Audit log substrate** (§10) | Witness co-signing requires every cosigner emits + verifies STHs. BRC-18 proof becomes audit-log projection. |
| **Quorum profiles** (§16) | Resharing must support cross-(t,n) transitions. Cert binding must survive threshold change. |
| **TEE attestation** (§16, §17) | Cert format adds `tee_attestation` + `binary_hash` fields. Policy adds `RequireAttestation` rule. BRC-18 proof carries `binary_hash` for on-chain code-provenance. |
| **OTel traceparent** (§16) | MessageEnvelope CBOR field 10 reserved permanently. Relays must propagate. Redaction linter is a CI gate. |

## §D. Production-system precedents

| Layer | Inspired by |
|---|---|
| Transport | Lit Protocol relay-mesh; Matrix Olm/Megolm (encryption above transport); Iroh "dial keys not IPs"; SPIFFE federation |
| Identity | SPIFFE SVIDs (≤1h rotation); Sigstore Fulcio (10-min OIDC certs); Web PKI cross-signing; Certificate Transparency (Trillian/RFC 6962) |
| Policy | Fireblocks Transaction Authorization Policy (8-field rules); Cedar (AWS Verified Permissions, Dafny-verified); Cubist programmable policies |
| Audit | Sigstore Rekor (Merkle-tree transparency log); CloudTrail (immutable audit); immudb (verifiable KV); Witness Cosigning (Sigstore pattern) |
| Crypto | LFDT-Lockness CGGMP'24 (post-CVE'25 patches); DKLs23 (no Paillier); Coinbase cb-mpc; Silence Labs DKLs23 production lib |
| Notary | Sigstore (signing notary in software supply chain); Fireblocks pricing model; Lit Protocol PKP product surface; Helium DePIN reputation |
| Ops | Google SRE Workbook; Fireblocks Co-Signer ops; Coinbase Custody / Anchorage; HashiCorp Vault HA; AWS Nitro / GCP Confidential VMs |
| Supply chain | Sigstore (cosign + Fulcio + Rekor); SLSA framework; TUF; reproducible Cargo |

## §E. Notable rejected designs

| Rejected | Why |
|---|---|
| ~~WebSocket-on-DO retrofit to `bsv-messagebox-cloudflare`~~ | ~~Reverses v2 scope decision; federate instead.~~ **Reversed 2026-05-10:** with unlimited-resource framing, Calhoun adds Socket.IO over CF Worker DOs (~1500 LOC). WebSocket becomes the canonical receive transport; HTTP poll + FCM stay as fallbacks. Federation is unaffected. |
| libp2p gossipsub primary transport | Heavyweight (~MB), no clean WASM/CF Worker story, no clean browser story. Park as v3. |
| W3C VC / DID as primary identity | Marginal vendor-neutrality gain over BRC-52⊕; large implementation cost. Use as export adapter only. |
| OPA/Rego as policy DSL | ~30MB; doesn't run in CF Workers. Park as v2 if WASM-OPA matures. |
| Cedar as v1 policy DSL | Requires `std`; doesn't target wasm32-unknown-unknown today. **Schema is Cedar-shaped for future migration.** |
| `core::identity::Certificate` (rust-mpc custom struct) | Doesn't interoperate with anything; parallel to BRC-52. Deprecate. |
| Two DKGs per Notary onboarding (per BRC-mpc-fees draft) | Wrong UX position. Node fee pool is one-time setup *between operators*, not per-user. |
| Fee default = Level 1 (split P2PKH) | Contradicts BRC-mpc-fees draft (Level 2 recommended). Fix `fee_injector.rs`. |
| Random SessionId | Breaks audit-recoverability (given inputs, anyone recomputes). Spec uses deterministic `SHA256(domain \|\| inputs)`. |
| Logging joint_pubkey directly in OTel spans | Links sessions to addresses. Spec uses first-8-bytes fingerprint only. |

## §F. Phase order rationale

```
Phase 0 (Wks 1-2):  §01-05    Lock cryptographic foundation. Cross-impl gate.
Phase 1 (Wks 3-6):  §06-10    Transport, BRC-31, BRC-52⊕ identity, policy, audit.
Phase 2 (Wks 5-8):  §11,13,16-18  Fees, federation, ops, supply chain, recovery.
Phase 3 (Wks 7-9):  §12, 15   Discovery, Notary product surface.
Phase 4 (Wks 8-10): §14       Conformance suite both implementations run.
```

Phases 1-4 can pipeline once Phase 0 locks. The cryptographic foundation is the gate — until §01-05 lock, no joint ceremony produces a verified mainnet signature.

## See also

- [`PROPOSAL.md`](PROPOSAL.md) — short version, "what we're asking Binary"
- [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) — twelve questions, status-tagged
- [`decisions/`](decisions/) — per-decision ADRs
- [`appendices/swarm-reports/`](appendices/swarm-reports/) — full per-zone analysis (~1000 words each)
