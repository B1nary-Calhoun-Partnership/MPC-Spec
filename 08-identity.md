# 08 — Identity, Certificates, Federation (BRC-52⊕)

**Status:** DRAFT
**Version:** v1
**Phase:** 1
**Decided by:** ADR-0008 (proposed)
**Last updated:** 2026-05-10

## 08.1 Identity primitive

Every cosigner has a **long-lived BRC-100 identity key** (compressed secp256k1, hex-encoded). Where hardware is available, this key MUST be hardware-bound (TPM, TEE, Secure Enclave, FIDO2 token).

The identity key is used solely for:
1. BRC-31 mutual auth (§07)
2. Signing CSRs for cert issuance (§08.3)

The identity key is NOT the joint pubkey. The joint pubkey is the threshold output of DKG; the identity key is the cosigner's persistent on-network identity.

## 08.2 Certificate format — BRC-52⊕

Wire format: **BRC-52 binary serialization** per `~/bsv/BRCs/peer-to-peer/0052.md`. This profile mandates the following extension fields inside the BRC-52 `fields` map:

### Required fields

- `notAfter` — RFC-3339 UTC timestamp. Maximum 24h for cosigner certs, 1h for human-approver certs, 7d for federation root certs.
- `policy_hash` — REQUIRED for cosigner certs. Hex SHA-256 of canonical-CBOR policy manifest (§09).
- `ctlog_proof` — REQUIRED. Base64 inclusion proof against transparency log topic `tm_mpc_certs_v1` (§08.7).
- `audit_identity` — REQUIRED for cosigner certs. Compressed secp256k1 pubkey (33B hex) of the cosigner's audit identity key, distinct from the cert's `subject` signing key. Used to lock STH PushDrops (§10.5).

### Optional fields

- `subjectScheme` — `"single"` (default) or `"threshold"`. `"threshold"` indicates `subject` is a joint pubkey from MPC; the certificate was signed by a threshold signature from the inner MPC group. Verification is plain ECDSA either way.
- `attestation` — Base64-encoded TPM/TEE quote, AWS Nitro NSM attestation document, AMD SEV-SNP attestation report, Intel TDX TDREPORT, or WebAuthn attestation object. Format declared by `attestation_format` field.
- `attestation_format` — `"nitro_v1"` | `"sev_snp_v1"` | `"tdx_v1"` | `"webauthn_v1"` | absent.
- `binary_hash` — Hex SHA-256 of the cosigner binary that produced this cert. Cross-checked against Sigstore Rekor (§17).
- `root_set` — Comma-separated certifier pubkeys this subject accepts as equivalent issuers. Enables cross-signing federation.

### Standard BRC-52 fields

- `type` — 32 bytes; type identifier for "MPC cosigner cert".
- `serialNumber` — 32 bytes; SHA-256 of `(clientNonce ‖ serverNonce)`.
- `subject` — 33 bytes; for `subjectScheme="single"`, the cosigner identity key; for `"threshold"`, the joint pubkey.
- `certifier` — 33 bytes; the certifier's identity key.
- `revocationOutpoint` — txid:vout. Populated for federation root certs (long-lived); zeroed for ephemeral cosigner certs (TTL is sufficient).
- `signature` — DER-encoded ECDSA signature over the cert body, by the certifier's BRC-42-derived signing key (protocolID `[2, "certificate signature"]`, counterparty `Anyone`).

## 08.3 Issuance protocol

```
1. Subject prepares CSR:
   {
     subjectKey:       compressed pubkey 33B,
     requestedFields:  { policy_hash, ttlSec, attestation?, ... },
     clientNonce:      OsRng-drawn 32B
   }

2. Subject signs CSR with their BRC-100 identity key (BRC-31 over POST /signCertificate).

3. Certifier verifies BRC-31 (REQUIRED — fix rust-mpc certifier today; see Q4).

4. Certifier generates serverNonce via OsRng (REQUIRED — fix rust-mpc; currently
   deterministic SHA256(clientNonce || identity || "server-nonce")).

5. Certifier computes serial = SHA256(clientNonce || serverNonce).

6. Certifier signs cert per BRC-52 §Signing using BRC-42 derived key:
     - protocolID: [2, "certificate signature"]
     - counterparty: Anyone
   Output is DER-encoded ECDSA signature.

7. Certifier appends cert binary hash to tm_mpc_certs_v1 BRC-22 transparency log
   (Merkle Mountain Range; STH commitment published every 60s).

8. Certifier returns cert + ctlog_proof (Merkle inclusion proof).
```

## 08.4 Verification

A verifier MUST, in order:

1. Parse the BRC-52 binary; verify the certifier's signature.
2. Verify `ctlog_proof` against the latest `tm_mpc_certs_v1` STH the verifier holds (max staleness: 5 minutes).
3. Check `current_time < notAfter`.
4. If `revocationOutpoint != all-zeros`, query overlay for spent status; if spent, REJECT.
5. Check overlay topic `tm_mpc_revocations` (§08.10) for sub-TTL revocation announcements within the last 60s.
6. If `subjectScheme="threshold"`, verify `subject` is a known joint pubkey from a recorded DKG.
7. If `attestation` is present and the verifier's policy requires it, verify per the format spec (Nitro, SEV-SNP, TDX, WebAuthn).
8. For policy-gated operations, verify `policy_hash` matches the running manifest.

A verifier MAY cache certificate validity decisions for `min(60s, time_to_notAfter)`.

## 08.5 Lifecycle

| Stage | Action |
|---|---|
| Issuance | §08.3 |
| Renewal | Subject renews cert at `notAfter - 25% of TTL`. Triggers fresh CSR. |
| Identity-key rotation | Subject generates new identity key; CSR includes the new key; old cert ages out via TTL or is revoked early. |
| Refresh-induced rotation | Share-refresh ceremonies (§18) MUST atomically issue a new cert binding the new share's joint pubkey. |
| Revocation | §08.10 |

## 08.6 Federation

Two operators (e.g. Calhoun, Binary) establish federation by:

1. Each issues a BRC-52 cert to the other's root pubkey (`subjectScheme="single"`, `ttl=7d`, root cert flag).
2. Both certs published to the shared `tm_mpc_certs_v1` log.
3. Cosigners under either root MAY be cross-signed by the other root on request.
4. CHIP token (§12) advertises `accepted_cert_roots = [self_root, peer_root, …]`.
5. Verifiers accept any cert that chains to any root in their trust store.

There is no privileged "primary" root. New roots may be added at any time by mutual cross-signing. **Self-issued (subject == certifier) cosigner certs are PERMITTED**; trust is delegated to the discovery+reputation layer (§12), not certificate issuance.

## 08.7 Transparency log

The shared transparency log lives on BRC-22 overlay topic `tm_mpc_certs_v1`.

- **Format:** Merkle Mountain Range (RFC 6962 / Trillian-compatible).
- **Leaf:** SHA-256 of the canonical BRC-52 binary cert.
- **STH publication:** Every 60 seconds, the certifier publishes a Signed Tree Head (root + tree size + signature) as a BRC-18 OP_RETURN on `tm_mpc_certs_v1`.
- **Auditability:** Any party can fetch the log, replay leaves, and verify the STH. Discrepancies indicate certifier misbehavior.
- **Federation:** Multiple certifiers MAY publish to the same log topic; each STH is signed by the issuing certifier. Cross-checking happens by BRC-22 readers.

## 08.8 Threshold-subject (nested MPC)

A cosigner that is itself an MPC group (joint pubkey JK, threshold t-of-n) MAY obtain a cert with `subjectScheme="threshold"`, `subject=JK_compressed_hex`. The CSR signature is a threshold signature produced by the inner MPC group via the same wire protocol (§01–§07). The outer cert is verifiable as plain ECDSA.

This is the primitive that makes Mitch's "MPC wallet exposes BRC-100 → infinite composition" real. A 2-of-3 wallet has an identity. That identity can participate in another 2-of-3 wallet. Recursive.

## 08.9 Hardware attestation

Where the cosigner host supports it, the cert SHOULD include `attestation` + `attestation_format`. Counterparties' policies (§09) MAY require non-empty attestation via `RuleKind::RequireAttestation`.

| Format | Source | Verification |
|---|---|---|
| `nitro_v1` | AWS Nitro Enclave NSM `nsm_get_attestation_doc` | Verify against AWS Nitro root cert chain; check PCR0/PCR8 values match expected binary hash. |
| `sev_snp_v1` | AMD SEV-SNP attestation report | Verify against AMD root keys; check measurement against expected. |
| `tdx_v1` | Intel TDX TDREPORT | Verify against Intel root certs; check MRTD measurement. |
| `webauthn_v1` | WebAuthn attestation object | Verify against the attestation CA chain from the manufacturer. |

The `attestation` field is bound by inclusion in the BRC-52 cert signature, which the certifier validates at issuance time (the certifier MUST verify the attestation matches the subject's `binary_hash` claim).

## 08.10 Revocation

TTL expiry is the primary revocation mechanism (no propagation problem within TTL window).

For sub-TTL revocation:

- **Federation root certs**: spend the `revocationOutpoint` UTXO. Standard BRC-52 mechanism.
- **Cosigner certs**: emit a revocation announcement to BRC-22 overlay topic `tm_mpc_revocations_v1`. The announcement is itself a signed BRC-22 record from the certifier:
  ```
  RevocationRecord = {
    cert_serial:     bstr32,
    revoked_at:      u64 (unix timestamp),
    reason:          tstr ("compromised" | "rotated" | "operator_request" | ...),
    revoker_signature: bstr (BRC-77 over fields above)
  }
  ```
  Verifiers MUST poll `tm_mpc_revocations_v1` within 60s freshness window for high-value (> threshold sat) signing requests.

## 08.11 User identity (vs cosigner-operator identity)

A *user* (not cosigner-operator) authenticates via BRC-100 wallet identity key. Their participation in a ceremony does NOT require a BRC-52 cert — only BRC-31 session auth. Optional: WebAuthn passkey attestation in `attestation` field for human-approver roles.

User identity rotation is handled by the BRC-100 wallet (out of scope for this spec).

## 08.12 Deprecations

- **rust-mpc's `core::identity::Certificate` custom JSON struct: DEPRECATED.** Replace with the BRC-52 binary format defined here. Policy engine's `verify_party_certificate` (`engine.rs:259-305`) moves to verify BRC-52. See [`OPEN-QUESTIONS.md` Q4](OPEN-QUESTIONS.md) and ADR-0011.
- **bsv-mpc has no certificate today.** MUST add BRC-52 verifier in `bsv-mpc-worker/src/auth.rs` alongside the existing BRC-31 session check.

## 08.13 Implementation notes — required rust-mpc certifier hardening

- `serverNonce` MUST use `OsRng` (currently deterministic — BRC-52 expects fresh randomness).
- `/signCertificate` MUST gate behind BRC-31 (currently any HTTP request accepted). See [`OPEN-QUESTIONS.md` Q4 hardening].
- Persistence MUST wire to `mpc_storage::sqlite` (currently in-memory `HashMap`, wiped on restart).
- Add `notAfter`, `policy_hash`, `ctlog_proof`, `subjectScheme`, `attestation`, `attestation_format`, `binary_hash`, `root_set` fields per §08.2.

## 08.14 Test vectors

In `conformance/test-vectors/08-identity.json`. Examples:
- Cosigner cert issued, signed, transparency-log-included, verified.
- Threshold-subject cert (2-of-3 → joint key as subject).
- Cross-signed cert under two roots.
- Rejected: expired (notAfter past).
- Rejected: ctlog proof invalid.
- Rejected: revoked (outpoint spent).
- Rejected: revoked via tm_mpc_revocations_v1 announcement.

## See also

- [`decisions/0008-brc52-plus-identity-format.md`](decisions/0008-brc52-plus-identity-format.md) — ADR.
- [`07-brc31-auth.md`](07-brc31-auth.md) — auth that consumes these certs.
- [`09-policy.md`](09-policy.md) — policy manifest hash bound by `policy_hash` field.
- [`13-federation.md`](13-federation.md) — federation mechanism.
- [`16-operations.md`](16-operations.md), [`17-supply-chain.md`](17-supply-chain.md) — attestation and binary_hash.
- BRC-52: `~/bsv/BRCs/peer-to-peer/0052.md`
- [`appendices/swarm-reports/B-identity.md`](appendices/swarm-reports/B-identity.md) — full design rationale.
