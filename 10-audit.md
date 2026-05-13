# 10 — Audit (Embedded Rekor + Witness Cosigning + BSV Anchoring)

**Status:** DRAFT
**Version:** v1
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

## 10.5 STH publication to BSV (PushDrop chain)

Every **60 seconds** (default, configurable per cosigner — minimum 30s, maximum 300s), the cosigner MUST publish their current STH as a **PushDrop output** (BRC-23) on BRC-22 overlay topic `tm_mpc_audit`. The publication is a Bitcoin transaction that:

1. **Spends the cosigner's previous STH PushDrop** (or, for the initial publication, any UTXO the cosigner controls — the genesis tx of the chain).
2. **Creates a new PushDrop output** locked to the cosigner's audit identity key, containing the new STH fields.

The chain of spends across time IS the audit log. Chain continuity is enforced by UTXO consensus: only the holder of the audit identity private key can spend the previous output and create the next one. Tamper requires double-spending a UTXO — consensus-impossible, not merely detectable.

### 10.5.1 PushDrop field layout

The locking script follows the BRC-23 PushDrop pattern:

```
<bstr "mpc-audit-sth">              // canonical prefix (13 ASCII bytes)
<bstr 0x01>                          // version byte: mpc-spec-v1
<bstr cosigner_audit_identity_33B>   // BRC-31 audit identity pubkey
<bstr tree_size_8B_BE>               // monotonically increasing u64
<bstr root_hash_32B>                 // current Merkle tree root
<bstr timestamp_ms_8B_BE>            // u64 Unix milliseconds
<bstr brc77_signature>               // signature over (prefix||version||tree_size||root_hash||timestamp)
OP_DROP OP_DROP OP_DROP OP_DROP OP_DROP OP_DROP OP_DROP   // drop all 7 push fields
<bstr cosigner_audit_identity_33B>   // locking pubkey (same as above)
OP_CHECKSIG
```

The output value SHOULD be `dust + 50 sats` (~50 sats) to minimize stranded value while remaining above the BSV dust threshold.

### 10.5.2 Genesis transaction

The first STH PushDrop in a cosigner's chain has no prior PushDrop to spend. It MAY consume any UTXO the cosigner controls. The `tree_size` MUST be 1 (one leaf in the audit log) and the prior-chain field MUST be absent.

Implementations SHOULD publish the genesis tx as part of cosigner provisioning (alongside the BRC-52⊕ cert issuance in §08).

### 10.5.3 Subsequent transactions

Every subsequent STH publication is a transaction that:

- Has exactly one input spending the cosigner's previous STH PushDrop.
- Has exactly one PushDrop output with the new STH per §10.5.1.
- MAY have additional inputs / outputs (e.g., for fee top-up if the chain's sat balance drops too low; for fee output during routine signing — see §11.6).

### 10.5.4 Audit identity key

The audit identity is a **separate, long-lived** BRC-31 keypair distinct from the cosigner's signing identity. Required because:

- Signing identity rotates every 90 days (§16.8); breaking the audit chain at every rotation is unacceptable.
- Audit identity rotates only via the explicit chain-rotation ceremony (§10.5.6).
- Audit identity does NOT participate in MPC ceremonies and SHOULD be held in stricter custody (hardware-backed where possible).

The audit identity is bound to the cosigner via a BRC-52⊕ cert (§08) issued by the certifier, listing the audit identity pubkey in `fields["audit_identity"]`.

### 10.5.5 Stranded UTXO fallback

If a cosigner goes silent for an extended period, their final PushDrop is permanently locked under the audit identity key. To enable garbage collection, the PushDrop locking script MAY include a CHECKLOCKTIMEVERIFY fallback:

```
OP_IF
  <cosigner_audit_pubkey> OP_CHECKSIG       // primary spend path
OP_ELSE
  <timestamp + 90 days> OP_CHECKLOCKTIMEVERIFY OP_DROP
  OP_TRUE                                    // anyone-can-spend after timeout
OP_ENDIF
```

90 days is chosen as 3× the routine refresh cadence (§16.5, RR-001 = 30 days) — beyond this, the cosigner is unambiguously decommissioned.

Implementations MAY omit the fallback if they accept that the ~50 sats per decommissioned cosigner is permanently locked (acceptable cost in most operational models).

### 10.5.6 Chain rotation (audit identity key rotation)

If the cosigner needs to rotate their audit identity key (e.g., compromise, scheduled rotation), they MUST publish a **chain-rotation transaction**:

1. Spend the previous STH PushDrop with the OLD audit identity key.
2. Create a new PushDrop locked to the NEW audit identity, with `fields["prev_audit_identity"]` = old audit pubkey and a `BRC-77` signature from BOTH old and new keys.
3. Update the cosigner's BRC-52⊕ cert (§08) to reflect the new audit identity.

Verifiers follow the chain through the rotation by checking both signatures. The rotation is one transaction — it doesn't break chain continuity at the UTXO layer.

### 10.5.7 Verification procedure

Given `(joint_pubkey, sighash)`, a verifier:

0. **(NEW per ADR-0039)** Fetch the cosigner's latest STH tip from **at least two independent BRC-22 lookup hosts** AND cross-check against any STH the verifier itself has directly witnessed in the prior 5 minutes. Disagreement among sources MUST raise an `audit-anomaly` event and the verifier MUST refuse signature acceptance until reconciled (via additional independent lookups, direct cosigner-to-cosigner exchange per §10.6, or operator escalation). This closes the eclipse vector where a single BRC-22 host serves a stale-but-validly-signed tip.
1. Look up the cosigner's BRC-52⊕ cert to find their `audit_identity` field.
2. Find the cosigner's **latest unspent STH PushDrop** at `tm_mpc_audit` for that audit identity. This is a single UTXO lookup *per source* (multi-source per step 0).
3. Walk the chain backward via transaction inputs until reaching the genesis tx.
4. At each step, verify: monotonic `tree_size`, BRC-77 signature validity, audit identity continuity (with rotation-ceremony exceptions allowed per §10.5.6).
5. For a specific `AuditEntry`, fetch the Merkle inclusion proof from the cosigner's local Rekor log and verify against the appropriate STH on the chain.

### 10.5.8 Cost

Per-STH cost is **only the transaction fee** (~1–2 sats at current mainnet rates). Setup cost is one-time per cosigner (~50 sats for the genesis PushDrop). At 60s publication cadence (1,440 STHs/day, ~525K/year per cosigner), annual cost per cosigner is approximately:

- Genesis tx: 50 sats (~$0.000025 at $50/BSV)
- Per-STH tx fee: ~1.5 sats × 525,000 = ~787,500 sats (~$0.40)

Compared to OP_RETURN publication (~100 sats per STH = ~52M sats/yr = ~$22/yr), this is a **~50× cost reduction**.

## 10.6 Witness cosigning

This is the cross-cosigner cross-check that gives non-repudiation in the asymmetric setting.

**Mechanism:**
- On every signing ceremony, AFTER the signature is emitted, each participating cosigner MUST request and receive an STH from every OTHER participating cosigner.
- Each cosigner verifies the received STH (signature + Merkle root + tree_size monotonically increasing).
- Each cosigner co-signs the received STH (`WitnessCosignedSth` event in their own audit log).
- A cosigner that fails to provide an STH on request triggers `WitnessCosignFailed` in the requester's log.

**Why this matters:** if cosigner #2 retroactively rewrites their own audit log to remove a signing event, the next time #2 participates in a ceremony with #3, #3 demands the current STH. If #2's tree_size is now smaller than what #3 has previously witnessed, #3 detects the rewrite. The cosigner that has been actively rewriting cannot continue to participate in ceremonies with witnessing peers without detection.

**Witness-cosign cadence (per ADR-0039, proposed):** Cosigners MUST exchange STHs on a **60-second schedule independent of ceremony activity**, in addition to per-ceremony exchanges. The unconditional cadence ensures that a verifier-side eclipse (per §10.5.7 step 0) remains detectable from the cosigner side even during low-ceremony periods. Lapses in witness-cosigning are themselves audit events.

## 10.7 BRC-18 participation proofs

A BRC-18 participation proof is a **projection** of the audit log: it cites `(audit_root, audit_index)` and the relevant `AuditEntry` rather than re-encoding the participants.

BRC-18 proofs are published as **OP_RETURN** outputs (not PushDrop). Rationale: BRC-18 proofs are per-ceremony attestations with no chain semantics — each is independent, none needs to be spent later. The PushDrop chain pattern (§10.5) applies to per-cosigner STHs, not per-ceremony proofs. A future v1.5 question of "should BRC-18 proofs also be PushDrop tokens?" (reputation/stake semantics) is tracked in OPEN-QUESTIONS Q13.

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

## 10.12 Audit retrieval API (normative, per ADR-0042 Part F)

Every cosigner participating in a multi-party deployment MUST expose:

```
GET /audit/entry/{leaf_index}
```

Response within **5 seconds p99** (per §16.3 SLI `audit.retrieval_latency_p99 ≤ 5s`). Body:

```json
{
  "leaf_index": 42,
  "audit_entry": { ... §10.4 AuditEntry CBOR-decoded ... },
  "inclusion_proof": ["sha256-hex", "sha256-hex", ...],
  "sth_chain_pointer": {
    "audit_identity": "0x02abcd...",
    "utxo_outpoint": "txid:vout",
    "tree_size_at_inclusion": 4096
  },
  "retrieved_at": 1730000000
}
```

### 10.12.1 Tombstoned leaves (GDPR Art.17 compatibility per ADR-0042 Part C)

When a leaf has been tombstoned for right-to-erasure (per §16.14):

- The `audit_entry` field is replaced with `{"tombstone": true, "tombstoned_at": <unix_ts>, "leaf_hash": "sha256-hex-of-original-leaf"}`
- The `inclusion_proof` field is unchanged (the Merkle root is preserved by design)
- The `sth_chain_pointer` is unchanged
- Verifiers MUST treat `tombstone: true` as a valid leaf for inclusion-proof verification (the leaf hash is still in the Merkle tree); the leaf content is just not retrievable

This resolves the F-vs-C contradiction surfaced by Quality loop-2: audit-chain integrity is preserved (tombstone leaf is still in the tree); customer data erasure is satisfied (preimage is gone); retrieval API returns a structured "this was tombstoned" response rather than an error.

### 10.12.2 Authentication

The endpoint MUST require BRC-31 mutual auth (§07). Audit entries are NOT public-by-default; access is gated by operator policy (some operators may make `tm_mpc_audit` STH chain entries publicly queryable; the leaf-level `audit_entry` body is gated).

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
