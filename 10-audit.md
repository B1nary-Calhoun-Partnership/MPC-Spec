# 10 — Audit (Embedded Rekor + Witness Cosigning + BSV Anchoring)

**Status:** DRAFT
**Phase:** 1
**Decided by:** ADR-0010 (proposed)
**Last updated:** 2026-05-10

## 10.1 Purpose

The audit layer answers:

> *Given a (joint_pubkey, sighash) pair, can a third party prove which cosigners participated, under which policy, and that the audit log itself has not been retroactively rewritten?*

A god-tier audit:
1. Logs every protocol-significant event in an append-only Merkle log.
2. Anchors the log to BSV every 60s (BRC-18 OP_RETURN), making "signed but not anchored" a detectable lie.
3. Cross-cosigners witness-co-sign each STH on every signing ceremony, so retroactive log rewriting is detected on the next ceremony.
4. Generates BRC-18 participation proofs as projections of the audit log (single source of truth).

## 10.2 Substrate

Each cosigner runs an **embedded append-only Merkle audit log** (Sigstore Rekor / Trillian / RFC 6962-compatible).

- **Format:** Merkle Mountain Range (MMR) or static Merkle tree per RFC 6962.
- **Leaf:** SHA-256 of canonical CBOR of `AuditEntry` (§10.4).
- **Persistence:** Local SQLite (or equivalent), append-only by API contract (writes never UPDATE existing rows).
- **Replication:** Each STH is published on-chain, providing public anchoring.

## 10.3 Required event set

Every cosigner MUST emit and record audit entries for the following events:

| Event | Trigger |
|---|---|
| `DkgInitiated` | DKG ceremony starts (party receives `SessionInit`) |
| `DkgCompleted` | DKG ceremony succeeds (joint pubkey finalized) |
| `PresigGenerated` | Each presig appended to the local pool |
| `PresigConsumed` | Each presig consumed from the local pool |
| `SignRequested` | Signing request received (before policy evaluation) |
| `PolicyEvaluated` | Policy verdict produced |
| `SignatureEmitted` | Signature partial computed and emitted |
| `FeeOutputDecided` | Fee output structure determined |
| `Brc18ProofPublished` | BRC-18 participation proof emitted |
| `PolicyManifestRotated` | New manifest version installed |
| `PartyAborted` | Identifiable abort raised against another party |
| `WitnessCosignedSth` | This cosigner co-signed another's STH |
| `WitnessCosignFailed` | Expected witness cosign did not arrive (peer down or misbehaving) |

## 10.4 AuditEntry schema

```
AuditEntry = {
  1:  u64,        // timestamp_ms (Unix milliseconds)
  2:  bstr32,     // session_id (per §04)
  3:  bstr33,     // joint_pubkey
  4:  tstr,       // phase ("dkg-keygen" | ... )
  5:  bstr32,     // policy_id
  6:  bstr32,     // request_hash (SHA-256 of the canonical-CBOR request that triggered this event)
  7:  tstr,       // event_kind (one of §10.3)
  8:  tstr_or_null, // verdict (for PolicyEvaluated): "Allow" | "Deny:reason" | ...
  9:  u16,        // party_index (this cosigner's index in the ceremony)
  10: bstr32,     // transcript_hash (SHA-256 of the cggmp24 transcript fragment relevant to this event)
  11: bstr,       // cosigner_signature_brc77 (BRC-77 signature over fields 1-10 by cosigner identity key)
  12: bstr32?     // witness_cosign_root (for WitnessCosigned event: the STH root being witnessed)
}
```

Canonical CBOR encoding per RFC 8949 §4.2.

## 10.5 STH publication to BSV

Every **60 seconds** (default, configurable per cosigner — minimum 30s, maximum 300s), the cosigner MUST:

1. Compute the current Merkle tree root.
2. Sign a Signed Tree Head:
   ```
   STH = {
     tree_size:  u64,
     root_hash:  bstr32,
     timestamp_ms: u64,
     signature:  bstr (BRC-77 over canonical CBOR of fields 1-3)
   }
   ```
3. Publish a BRC-18 OP_RETURN on BRC-22 overlay topic `tm_mpc_audit`:
   ```
   OP_FALSE OP_RETURN
     "mpc-audit-sth"     // canonical prefix
     0x01                // version
     cosigner_identity_33B
     tree_size_8B (BE u64)
     root_hash_32B
     timestamp_ms_8B (BE u64)
     brc77_signature
   ```

The on-chain cost is ~0.001¢ per epoch — negligible at scale.

## 10.6 Witness cosigning

This is the cross-cosigner cross-check that gives non-repudiation in the asymmetric setting.

**Mechanism:**
- On every signing ceremony, AFTER the signature is emitted, each participating cosigner MUST request and receive an STH from every OTHER participating cosigner.
- Each cosigner verifies the received STH (signature + Merkle root + tree_size monotonically increasing).
- Each cosigner co-signs the received STH (`WitnessCosignedSth` event in their own audit log).
- A cosigner that fails to provide an STH on request triggers `WitnessCosignFailed` in the requester's log.

**Why this matters:** if cosigner #2 retroactively rewrites their own audit log to remove a signing event, the next time #2 participates in a ceremony with #3, #3 demands the current STH. If #2's tree_size is now smaller than what #3 has previously witnessed, #3 detects the rewrite. The cosigner that has been actively rewriting cannot continue to participate in ceremonies with witnessing peers without detection.

**Witness-cosign cadence:** at minimum, on every signing ceremony. Implementations MAY witness more frequently (e.g., on a 60s schedule even without active ceremonies). Lapses in witness-cosigning are themselves audit events.

## 10.7 BRC-18 participation proofs

A BRC-18 participation proof is a **projection** of the audit log: it cites `(audit_root, audit_index)` and the relevant `AuditEntry` rather than re-encoding the participants.

```
OP_FALSE OP_RETURN
  "mpc-proof"          // canonical prefix (locks 3-way string conflict)
  0x02                 // version (v1 was bsv-mpc-only)
  session_hash_32B     // SHA-256(joint_pubkey || ExecutionId || sighash)
  audit_root_32B       // STH root at proof emission time
  audit_index_8B (BE)  // leaf index of the SignatureEmitted event
  cosigner_identity_33B
  participants_count_u8 + sorted_participants_33B*  // each 33B compressed
  policy_id_32B
  fee_txid_32B (or 32 zeros if none)
  timestamp_ms_8B (BE)
  brc77_signature      // signature over preceding bytes
```

A verifier:
1. Parses the OP_RETURN.
2. Fetches the cited `AuditEntry` from the cosigner's log.
3. Verifies Merkle inclusion against the cited `audit_root`.
4. Verifies the `audit_root` was anchored on-chain via `tm_mpc_audit` STH.
5. Verifies `session_hash` matches the entry's `(joint_pubkey, ExecutionId, sighash)`.

## 10.8 Verifying compliance after the fact

Given `(manifest_id, transcript_hash, request_hash)`, any party can:

1. Fetch the manifest from the certifier (BRC-52⊕-signed).
2. Fetch the audit entry from the peer's Merkle log + Merkle inclusion proof.
3. Verify the on-chain STH anchor for the cited audit_root.
4. Run the deterministic policy evaluator (§09) on the request and the manifest.
5. Compare the evaluator's verdict to the recorded verdict.

Bytes match → compliance verified. Replay without re-ceremony.

## 10.9 Audit-publishing failure modes

| Mode | Detection |
|---|---|
| Signed but didn't publish STH | Overlay query `tm_mpc_audit` returns count below sign count from coordinator audit_log. Cross-checked at next witness round. |
| Wrong proof published | `verify_participation_proof` checks structural fields; mismatch between proof.signing_hash and known sighash detectable. |
| Proof for ceremony that didn't happen | Coordinator's audit_log records valid ceremony SessionIds; verifier checks proof's session_hash against this. Combined with witness-cosigning, fabrication is detectable on next witness round. |
| Honest-loser abort | `PartyAborted` event in audit log + identifiable-abort evidence (§01.6) attribute the abort. |

## 10.10 Implementation notes

- bsv-mpc currently has `crates/bsv-mpc-core/src/proof.rs` with BRC-18 proof structure but `publish_proof` / `query_proofs` / `count_proofs_by_node` / `parse_proof_from_script` are stubbed (return errors / empty / `InvalidProof`). MUST implement.
- bsv-mpc currently uses `session_hash = SHA-256(session_id_string)` — too weak. MUST replace with `SHA-256(joint_pubkey || ExecutionId || sighash)`.
- bsv-mpc has 3-way OP_RETURN prefix conflict: draft (`mpc-signing-proof`), core (`bsv-mpc-participation`), overlay (`mpc-proof`). Spec locks `"mpc-proof"`. Update all three call sites.
- rust-mpc has audit logging in `crates/policy/src/audit.rs`. Required: extend to emit Merkle log + STH publication.
- Witness-cosigning is new functionality in both implementations. Coordinate the wire format in §10.6 before implementing.

## 10.11 Test vectors

In `conformance/test-vectors/10-audit.json` and `.cbor`. Examples:
- Audit log with 100 entries; verify Merkle root.
- STH signed; verify signature.
- BRC-18 proof emitted; verify against on-chain STH.
- Witness cosign valid; verify monotonic tree_size.
- Witness cosign invalid (tree_size went backward); reject.

## See also

- [`decisions/0010-embedded-rekor-witness-cosigning.md`](decisions/0010-embedded-rekor-witness-cosigning.md) — ADR.
- [`08-identity.md`](08-identity.md) — cosigner identity for STH signing.
- [`09-policy.md`](09-policy.md) — policy decisions are audit events.
- [`02-execution-id.md`](02-execution-id.md) — `session_hash` includes ExecutionId.
- [`appendices/swarm-reports/C-policy-audit.md`](appendices/swarm-reports/C-policy-audit.md) — full design rationale.
- Sigstore Rekor: https://docs.sigstore.dev/logging/overview/
- Trillian: https://transparency.dev/verifiable-data-structures/
- RFC 6962: https://www.rfc-editor.org/rfc/rfc6962.html
