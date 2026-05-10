# Appendix B — Identity, Certificates, Federation

> Full report from the Identity zone agent of the god-tier-design swarm (2026-05-10).
> Preserved verbatim as supporting depth for [`§07-brc31-auth.md`](../../07-brc31-auth.md), [`§08-identity.md`](../../08-identity.md), [`§13-federation.md`](../../13-federation.md).

---

## §A. God-tier definition by 5-axis rubric

A god-tier cosigner-identity primitive for a vendor-neutral threshold-signing network must satisfy all five axes simultaneously. None of the existing repos do today; rust-mpc has two non-interoperable cert types (`core::identity::Certificate` JSON struct vs BRC-52 from the certifier), and bsv-mpc has no cert at all. The target shape:

1. **Security.** Each cosigner's signing authority is bound to a *short-lived* certificate (hours-to-days, not the BRC-52 default of "until revocation outpoint is spent"), rooted in a *long-lived* identity key that lives in hardware where possible (TPM/TEE/Secure Enclave/YubiKey). Compromise of an online key cannot exceed the cert's TTL window. Sybil resistance comes from staking via BRC-22 reputation + on-chain CHIP token + at least one cross-signing root. **Precedent:** SPIFFE SVIDs default to ~1 hour rotation; Sigstore Fulcio issues 10-minute certs from OIDC identity.

2. **UX.** A user (not operator) onboards via a BRC-100 wallet identity key; cold-start is "scan QR or pick from overlay → wallet signs a CertificateSigningRequest → cosigner publishes cert into transparency log." Recovery is *not* coupled to one issuer: any of N roots can re-issue, and the user's personal wallet root can self-cross-sign the new cosigner cert. State is visible in the BRC-100 wallet's certificate manager.

3. **Vendor-neutrality.** No certifier is load-bearing. Multiple roots ("Calhoun root", "Binary root", any third party) can issue equivalent certs; cross-signing between roots is a primitive, not an exception. A user can self-certify (sign their own cosigner cert with their BRC-100 identity key) and put that on the overlay — discovery + reputation, not certification, is the trust gate. **Precedent:** Web PKI's cross-signing (Let's Encrypt's ISRG Root X1 was cross-signed by IdenTrust DST X3 for years).

4. **Operability.** Issuance is throughput-bound only by the certifier's BRC-42 derived signing rate (tens of certs/sec on commodity hardware). Revocation is *primarily TTL-driven* (no propagation problem within TTL window), with a fast-path on-chain revocation (BRC-52's revocation outpoint) for emergencies. Audit trail is an append-only Merkle log on BRC-22 overlay (Trillian-style; see Sigstore Rekor and CT logs).

5. **Composability.** A 2-of-3 wallet acting as a cosigner has an identity that *is itself* a threshold pubkey. The cert binds to the joint pubkey; the "subject signed" the CSR via a *threshold signature* — round-tripped through the same MPC stack. Recursive signing is native. **Precedent:** Fireblocks Vault Accounts and SPIFFE federation both support sub-identity hierarchies; nothing in BRC-52 today expresses this — we must add a `subjectScheme` field.

## §B. Option 1 — "BRC-52⊕": short-lived BRC-52 certs, transparency-log-anchored, threshold-subject capable

**Design.** Keep BRC-52 as the wire format (rust-mpc certifier already issues it; SDK parity), but constrain it with a profile:

- **Mandatory short TTL** via a new field `notAfter` (ISO-8601) inside `fields`. Default 24h for cosigner certs, 1h for human-approver certs, 7d for federation root certs.
- **Mandatory transparency-log anchor** via a new `fields["ctlog_proof"]` containing an inclusion proof against a public BRC-22 overlay topic `tm_mpc_certs_v1` (Merkle Mountain Range, like Trillian/CT). All issuers must log every cert; verifiers reject certs without a valid proof.
- **`subjectScheme` field**: `"single"` (existing — `subject` is one secp256k1 key) or `"threshold"` (`subject` is the joint pubkey of an underlying MPC group, and the certificate's signature is *also* a threshold signature; verification is plain ECDSA either way thanks to the `secp256k1`-flat output).
- **Policy manifest binding.** A canonical-CBOR policy manifest hash sits in `fields["policy_hash"]`. Bind once, ratchet on rotation.
- **Cross-signing.** A cosigner publishes *one cert per root they accept*. The CHIP token in `tm_mpc_signing` references the set of cert serial numbers; verifiers pick the cert under the root they trust. No single point of trust failure.
- **Revocation.** TTL is primary. BRC-52 revocation outpoint is the kill-switch (zeroed for ephemeral certs to disable; populated for federation roots). Plus an overlay "revocation announcement" topic for sub-TTL emergencies, gossiped via BRC-22.
- **Hardware binding.** `fields["attestation"]` optional: TPM/TEE quote signed over the cosigner's identity key. WebAuthn attestation for human approvers.

**5-axis grading.**
1. **Security: A.** Short TTL bounds compromise window. Transparency log makes mis-issuance externally detectable. Hardware attestation closes host-compromise. Sybil resistance via overlay reputation + stake.
2. **UX: A−.** Onboarding piggybacks on existing BRC-100 wallet flows. Recovery via any cross-signing root. Slight cost: certs rotate, so wallets must auto-renew (SPIRE Helper pattern); UX hidden behind the wallet, but it's another cron.
3. **Vendor-neutrality: A.** Multiple roots; cross-signing first-class; users can self-issue. No certifier load-bearing.
4. **Operability: B+.** Issuance throughput high (just BRC-42 signs). Revocation propagates within TTL automatically; emergency revocation is overlay+outpoint. Audit trail via Merkle log = strong. Mild cost: every issuer must log to overlay (new infra, but cheap on BSV).
5. **Composability: A.** `subjectScheme=threshold` lets a 2-of-3 wallet be a cosigner with a cert. Recursive MPC just works.

## §C. Option 2 — "Fulcio-for-BSV": ephemeral keys, OIDC-equivalent (BRC-31 + BRC-100), cert lifetime = single ceremony

**Design.** Bolder. Cosigner has *no* long-lived signing-authority key. Each MPC ceremony begins with a fresh ephemeral keypair generated *inside* the cosigner's TEE. The cosigner authenticates via BRC-31 (their long-lived BRC-100 identity), submits a CSR for the ephemeral key + ceremony parameters, the certifier issues a 10-minute BRC-52 cert, and the cert + ephemeral key are used for that one ceremony only. After the ceremony, the ephemeral key is destroyed. Every issued cert lands in a Rekor-equivalent log.

**Precedent.** Sigstore Fulcio + Rekor — ephemeral keys, OIDC identity, transparency log; widely deployed (npm, PyPI, GitHub Actions, Kubernetes).

**Trade-offs vs Option 1.** Strictly stronger on security, strictly weaker on latency and recursive-MPC composability. Right answer for a high-stakes corporate vault; over-engineered for a 2-of-3 agent wallet.

## §D. Option 3 — "DID-rooted": DID:web/DID:bsv, VC for cosigner cert, BRC-52 deprecated

**Design.** Use W3C DIDs as the identity primitive. Each cosigner is a DID — `did:bsv:<txid>:<index>` (UTXO-rooted, like did:btcr) or `did:web:cosigner.example.com`. The cosigner's "cert" becomes a W3C Verifiable Credential, with proof type `EcdsaSecp256k1Signature2019`.

**Why we don't recommend this as primary.** BSV ecosystem is BRC-natively. Forcing W3C-VC layering for marginal vendor-neutrality gain when BRC-52 (with our profile) already gets us there is not worth the implementation cost. **Use DIDs as an *exit ramp*** — every BRC-52 cert SHOULD also be expressible as a VC for interop with non-BSV systems, but the canonical wire format stays BRC-52.

## §E. Cross-layer dependencies

- **Policy.** Cert binds `policy_hash` → policy engine MUST verify the cert hash matches the running manifest. Constrains §09: manifest must canonicalize (CBOR §4.2) and hash match the field.
- **Audit.** Cert serial numbers go into BRC-18 participation proofs (`session_hash` should include them). Constrains §10 to add `cert_serial_32B` to the hash input.
- **Discovery.** CHIP token in `tm_mpc_signing` references cert serials. Constrains §12: CHIP capability JSON adds `accepted_cert_roots: [pubkey]` and `cert_serials: [base64]` fields.
- **Federation.** §13: cross-signed BRC-52 certs + shared `tm_mpc_certs_v1` transparency log between Calhoun and Binary roots; both publish, both verify.
- **Recovery.** Refresh ceremonies (POC 13) MUST rotate the cert atomically with the share. Operationally: the certifier must hold a short-lived "refresh capability" that proves it can re-issue a cert under the same root post-rotation.

## Surprises / red flags from the swarm

- **THREAT-MODEL.md A4/A7 says BRC-31 is TODO — it is not.** `bsv-mpc-worker/auth.rs` is 963 LOC with full handshake, session storage, response signing. Doc must be updated before any audit.
- **Certifier in `rust-mpc/bins/certifier` has no auth gate.** Anyone who reaches port 3322 can request signing. Ironic given rust-mpc's policy crate is the strict one. Must wrap with the BRC-31 verifier before mainnet.
- **Certifier state is volatile.** All `CertRecord`s vanish on restart; `/checkVerification` will lie. Must wire to `mpc_storage::sqlite` (already loaded for key share) before federation.
- **`serverNonce` is deterministic** (`SHA256(clientNonce || identity || "server-nonce")`). BRC-52 expects fresh randomness; with deterministic nonce the same client request always yields the same serial. Replay/dup risk.
- **Two certifier flavors collide:** rust-mpc's `core::identity::Certificate` is a custom JSON shape. The certifier binary issues BRC-52-shaped certs. The policy engine's `verify_party_certificate` checks the **custom** shape, not BRC-52. **These two cert types do not interoperate** — pick one before federating.

## Recommendation

**Option 1 (BRC-52⊕)** as the canonical primitive, with Option 2 (Fulcio-style ephemeral) reserved as a profile for high-value institutional use, and Option 3 (DID/VC) supported only as an export adapter for cross-ecosystem interop. This minimizes the implementation delta from today's rust-mpc certifier (which already issues BRC-52), kills the second cert type cleanly, and gives bsv-mpc a concrete spec to build against.

## Sources

- SPIFFE SVIDs (https://spiffe.io/docs/latest/deploying/svids/)
- Sigstore Security Model (https://docs.sigstore.dev/about/security/)
- Sigstore Fulcio (https://github.com/sigstore/fulcio)
- W3C Verifiable Credentials Data Model 2.0 (https://www.w3.org/TR/vc-data-model-2.0/)

Internal references:
- `/Users/johncalhoun/bsv/mpc/rust-mpc/bins/certifier/src/{main,handlers,state,wallet_wrapper}.rs`
- `/Users/johncalhoun/bsv/mpc/rust-mpc/crates/core/src/identity.rs`
- `/Users/johncalhoun/bsv/mpc/rust-mpc/crates/policy/src/{engine,cosigner_policy}.rs`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/crates/bsv-mpc-worker/src/auth.rs`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/crates/bsv-mpc-overlay/src/chip.rs`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/docs/THREAT-MODEL.md` (lines 120-162, stale)
- `/Users/johncalhoun/bsv/rust-middleware/bsv-auth-cloudflare/src/middleware/auth.rs`
