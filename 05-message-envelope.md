# 05 — Canonical Message Envelope

**Status:** LOCKED (pending ADR-0005 sign-off)
**Version:** v1
**Phase:** 0
**Decided by:** ADR-0005
**Last updated:** 2026-05-10

## 05.1 Purpose

The canonical Message Envelope is the wire format for every MPC ceremony message between cosigners. It composes:

1. **Outer authentication** (BRC-31) — sender's identity-key signature over the envelope. Defends against relay forgery and CA-breach MITM.
2. **Inner encryption** (BRC-78 ECIES) — payload encrypted to the recipient's identity-key. Defends against relay observation of ceremony content.
3. **Session binding** — ExecutionId prefix in the envelope binds it to a specific ceremony; cross-session replay impossible by construction.
4. **Trace propagation** — `traceparent` field carries OpenTelemetry W3C Trace Context across parties for cross-cosigner ceremony forensics (§16).

## 05.2 Encoding

The envelope is encoded as **canonical CBOR** per RFC 8949 §4.2 (deterministic encoding):

- Integer encodings are minimal-length.
- Map keys are sorted lexicographically.
- Indefinite-length strings/arrays are forbidden.
- Floats are forbidden.

## 05.3 Schema

CBOR map. Numeric keys for compactness. All keys are required unless marked OPTIONAL.

```
MessageEnvelope = {
    1:  u8,       // version: MUST be 0x01 for mpc-spec-v1
    2:  bstr32,   // session_id (per §04)
    3:  bstr33,   // joint_pubkey (compressed; all-zeros during DKG keygen)
    4:  tstr,     // phase: "dkg-keygen" | "dkg-auxinfo" | "presign" | "sign" | "ecdh" | "refresh"
    5:  u8,       // round (1-based; cggmp24 round number for the phase)
    6:  u16,      // from_party (party_index of sender, 0-based)
    7:  u16,      // to_party (0xFFFF for broadcast; otherwise party_index of recipient)
    8:  bstr,     // inner: BRC-78 ECIES envelope wrapping the cggmp24 inner Msg (CBOR-encoded)
    9:  bstr,     // sender_sig_brc31: BRC-31 signature over canonical CBOR encoding of fields 1..8
    10: bstr8,    // execution_id_prefix: first 8 bytes of canonical ExecutionId (per §02)
    11: tstr,     // OPTIONAL: correlation_id (UUIDv7 or similar; coordinator-set at ceremony init)
    12: tstr,     // OPTIONAL: traceparent (W3C Trace Context value, per §16)
}
```

## 05.4 Field semantics

### 05.4.1 Field 1: `version`

`0x01` for `mpc-spec-v1`. Future spec versions bump this. Mismatched versions cause envelope rejection at round 0.

### 05.4.2 Field 2: `session_id`

The 32-byte SessionId per §04. Same value across all envelopes in a ceremony.

### 05.4.3 Field 3: `joint_pubkey`

The 33-byte compressed secp256k1 joint pubkey for the ceremony. For DKG keygen, this is all-zero (joint key not yet known); for all other phases, it is the joint key produced by the prior DKG.

### 05.4.4 Field 4: `phase`

UTF-8 string. One of:

- `"dkg-keygen"`
- `"dkg-auxinfo"`
- `"presign"`
- `"sign"`
- `"ecdh"`
- `"refresh"`

This MUST be consistent with the phase byte fed into ExecutionId. Mismatch is an invalid envelope.

### 05.4.5 Field 5: `round`

1-based round number for the phase. CGGMP'24 phases have specific round counts (DKG keygen: 4 rounds; DKG auxinfo: 3 rounds; presigning: 3 rounds; signing: 1 round with presig, 4 rounds without). `round = 0` is forbidden.

### 05.4.6 Fields 6, 7: `from_party`, `to_party`

`from_party` is the 0-based party_index of the sender. `to_party` is the recipient's party_index OR `0xFFFF` for broadcast (envelope addressed to all participants).

For broadcast envelopes, the relay distributes one copy per recipient (relay-side fan-out). The relay MAY de-dup via the `(session_id, from_party, round, to_party)` tuple.

### 05.4.7 Field 8: `inner`

The cggmp24 inner Msg, encoded as CBOR (using cggmp24's standard `serde_cbor` serialization), then wrapped in a BRC-78 ECIES envelope addressed to `to_party`'s identity key.

For broadcast envelopes (`to_party == 0xFFFF`), the sender produces ONE encrypted copy *per recipient*; the relay distributes each. **There is no group encryption primitive in v1** — broadcast = N unicast envelopes with the same `(session_id, from_party, round)` and different `to_party` values.

### 05.4.8 Field 9: `sender_sig_brc31`

BRC-31 (Authrite) signature over canonical CBOR encoding of fields 1 through 8 (inclusive), produced with the sender's BRC-31 identity-key. Verifies the envelope was emitted by the claimed sender and not modified in transit.

The signature is over the *outer* envelope, not the *inner* cggmp24 message. This is intentional: a relay that re-orders or replays envelopes is detected by signature verification + ExecutionId binding, even without ever decrypting the inner.

### 05.4.9 Field 10: `execution_id_prefix`

The first 8 bytes of the canonical ExecutionId per §02. Allows relays to bucket envelopes by ceremony without learning the full ExecutionId (which would link the relay to the ceremony's joint pubkey).

8 bytes is sufficient for relay-side bucketing without collision in practice (collision probability ~2⁻⁶⁴ across all ceremonies on the relay).

### 05.4.10 Field 11: `correlation_id` (OPTIONAL)

A UUIDv7 (or similar time-sortable UUID) set by the coordinator at ceremony init, propagated unchanged across all envelopes in the ceremony.

Used for cross-party ceremony forensics: any party's local logs can be joined to any other party's logs by correlation_id, which lets ops reconstruct a stuck ceremony from a single-party log dump.

The correlation_id is NOT signed by individual parties. It is set by the coordinator and trusted-but-verified (a malicious party can lie about it; the value is for forensic correlation, not security).

### 05.4.11 Field 12: `traceparent` (OPTIONAL)

W3C Trace Context `traceparent` header value (e.g., `"00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"`). Propagated end-to-end through the ceremony for OpenTelemetry distributed tracing.

Implementations MAY include or omit this; relays MUST propagate it unchanged when present.

## 05.5 Encryption (BRC-78 inner)

The inner cggmp24 Msg is wrapped in BRC-78 ECIES:

1. Sender derives ephemeral keypair `(eph_priv, eph_pub)`.
2. Compute `shared = eph_priv * recipient_identity_pub`.
3. Derive `aes_key = SHA256(shared.compressed_33B)`.
4. Encrypt `cggmp24_msg_cbor` with AES-256-GCM, random 12-byte IV.
5. Field 8 = `eph_pub_33B ‖ iv_12B ‖ ciphertext ‖ tag_16B`.

Recipient reverses: extract `eph_pub`, compute `shared = recipient_identity_priv * eph_pub`, derive AES key, decrypt.

The full BRC-78 spec applies; this section summarizes for context.

## 05.6 Authentication (BRC-31 outer)

The sender_sig_brc31 (field 9) is computed as:

1. Encode fields 1 through 8 as canonical CBOR (RFC 8949 §4.2). This is the message-to-sign.
2. Sign with BRC-31 (Authrite) per `~/bsv/BRCs/peer-to-peer/0031.md`. The signing key is the sender's identity key.
3. Output is a DER-encoded ECDSA signature.

Verifier:
1. Re-encode fields 1 through 8 as canonical CBOR.
2. Verify the signature against the sender's identity key (looked up via the `from_party` index → BRC-52 cert chain).

A signature failure MUST cause envelope rejection without further processing.

## 05.7 Replay protection

Three layers compose:

1. **Transport replay** — relay MAY (but not MUST) de-dup envelopes by `(session_id, from_party, round, to_party)` tuple. Ceremonies tolerate duplicate delivery; protocol state machines reject duplicate rounds.
2. **Cross-session replay** — ExecutionId binding (§02) ensures captured envelopes from one session cannot be replayed in another. The `session_id` field itself is bound into the inner cggmp24 transcript hashes via ExecutionId.
3. **Cross-implementation replay** — algorithm_tag + version in ExecutionId prevent v1 (cggmp24) envelopes from being accepted as v2 (dkls23) envelopes.

## 05.8 Size bounds

- Maximum envelope size: **256 KiB** (uncompressed). cggmp24 round messages are typically 2–32 KB; the worst case is DKG auxinfo with Paillier ZK proofs (~64-128 KB). 256 KB provides headroom.
- Maximum field-1-through-8 size (the sign-protected portion): 256 KB minus overhead.
- Relays MUST NOT process envelopes exceeding the size bound; they SHOULD return an explicit error code.

## 05.9 Invalid envelope handling

A relay MUST reject envelopes that fail any of:
- CBOR decoding (e.g., invalid encoding, indefinite-length string, float present).
- Field presence (any required field missing).
- Size bound (§05.8).

A relay MAY return an error code or silently drop. Either is acceptable per spec.

A recipient MUST reject envelopes that fail any of:
- All relay-side checks above.
- BRC-31 signature verification.
- ExecutionId prefix matching the ceremony's expected ExecutionId.
- BRC-78 decryption (e.g., wrong recipient, malformed ciphertext).
- **Byte-equivalent re-encode check (per §05.9.1 below).**

A recipient MUST log envelope rejection (with `correlation_id` if present) for forensic forensics. The recipient MUST NOT respond to the malformed envelope; the protocol-level identifiable-abort handler decides whether to attribute the failure to a specific party.

### 05.9.1 Byte-equivalent re-encode requirement (parser-differential defense)

**Normative (per ADR-0037, proposed):** A recipient MUST re-encode the parsed envelope (fields 1 through 8) as canonical CBOR per RFC 8949 §4.2 and verify byte-equivalence with the original bytes covered by `sender_sig_brc31` (field 9). Any mismatch MUST be treated as a signature failure and the envelope MUST be rejected.

The following MUST cause rejection at the FIRST byte of deviation, without partial processing:

- Non-minimal integer encoding (e.g., `0x18 0x05` for the integer 5, which must encode as `0x05`)
- Indefinite-length strings, arrays, or maps (forbidden per §05.2)
- Duplicate map keys
- Trailing bytes after the canonical termination
- Floats (forbidden per §05.2)
- Unsorted map keys
- Tag values not whitelisted by this spec

**Rationale.** Two independent CBOR parsers (bsv-mpc / serde_cbor-flavored; rust-mpc / Binary's parser) may accept asymmetric inputs. An attacker that crafts an envelope which bsv-mpc accepts as round-N from party-A but rust-mpc rejects (or vice-versa) can steer identifiable-abort blame onto an honest party, cause split-brain audit logs, or replay bytes whose `sender_sig_brc31` covers a different parse-tree than the verifier reconstructs. Closing this gap requires byte-equivalence, not just "both parsers strict."

A conformance test vector pair (one accepted, one minimally-different-rejected) is committed to [`conformance/test-vectors/05-message-envelope-diff.cbor.hex`](conformance/test-vectors/05-message-envelope-diff.cbor.hex). Both implementations MUST round-trip both vectors per the rule above.

**Reference precedent:** Fireblocks BGM_DKG (2023) was a parser/transcript-binding gap of this class. Trail of Bits has published similar diff-fuzzing findings against TSS libraries. See [ADR-0037](decisions/0037-cbor-re-encode-equivalence.md).

## 05.10 Reserved fields

CBOR map keys not listed in §05.3 are RESERVED for future spec versions. Implementations MUST NOT emit unknown keys and SHOULD reject (or log a warning for) envelopes with unknown keys to enable forward-compatible spec evolution.

## 05.11 Test vectors

The canonical envelope vector — a sign-phase round-1 envelope from party 0 to party 1, with all 12 fields populated — is committed to:

- [`conformance/test-vectors/05-message-envelope.json`](conformance/test-vectors/05-message-envelope.json) — inputs, intermediates, and outputs
- [`conformance/test-vectors/05-message-envelope.cbor.hex`](conformance/test-vectors/05-message-envelope.cbor.hex) — the canonical CBOR bytes (hex)
- [`conformance/test-vectors/05-message-envelope.diag.txt`](conformance/test-vectors/05-message-envelope.diag.txt) — CBOR diagnostic notation

The vector uses pinned **test-only** ephemeral keys (committed alongside) so anyone can re-derive byte-for-byte:

```
sender_identity_priv      = 0x01 * 32       (test-only)
recipient_identity_priv   = 0x02 * 32       (test-only)
ephemeral_priv (BRC-78)   = 0x03 * 32       (test-only)
AES-GCM IV                = 0x0a0b0c0d0e0f101112131415  (12 B, test-only)
inner cggmp24 msg         = ASCII "cggmp24-test-inner-msg-round-1"

derived:
sender_identity_pub       = 0x031b84c5567b126440995d3ed5aaba0565d71e1834604819ff9c17f5e9d5dd078f
recipient_identity_pub    = 0x024d4b6cd1361032ca9bd2aeb9d900aa4d45d9ead80ac9423374c451a7254d0766
ephemeral_pub             = 0x02531fe6068134503d2723133227c867ac8fa6c83c537e9a44c3c5bdbdcb1fe337
```

The fields:

```
1  version            = 0x01
2  session_id         = 0xf25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b
                        (= SHA-256("test-vector-A"); reuses §02 vector A)
3  joint_pubkey       = 0x0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798
                        (secp256k1 generator G compressed)
4  phase              = "sign"
5  round              = 1
6  from_party         = 0
7  to_party           = 1
8  inner (BRC-78)     = eph_pub_33 ‖ iv_12 ‖ ct ‖ tag_16   (91 B total)
                      = 0x02531fe6068134503d2723133227c867ac8fa6c83c537e9a44c3c5bdbdcb1fe337
                        0a0b0c0d0e0f101112131415
                        f13be86e8433c4c68a15b37b91550a1d93ad2bb8ec287d52bbad7feac2d93d6
                        74cf36efa033da0a4ccd95546db30
9  sender_sig_brc31   = DER-encoded ECDSA, low-s normalized, deterministic (RFC 6979):
                        0x3045022100fc58dab9180a0df200d7e99b6bdeb3fdbce11454d842a8215d
                        6372ec698e64300220132d9efd5ba99f4b9e7a1ad19e369b33d7d8380c57d6
                        10619e42ff5e234bdab1
10 execution_id_prefix= 0x7286fe7b26a8ef9a
                        (first 8 bytes of §02 vector A ExecutionId)
11 correlation_id     = "01927f9f-7050-7a4d-a3c5-deadbeefcafe"  (fake UUIDv7)
12 traceparent        = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"
```

Full envelope CBOR: **361 bytes**, canonical per RFC 8949 §4.2. The exact hex is committed verbatim in [`conformance/test-vectors/05-message-envelope.cbor.hex`](conformance/test-vectors/05-message-envelope.cbor.hex) (single-line file; do not transcribe — read the file directly to avoid byte-level copy errors).

Cross-validation: two independent canonical-CBOR encoders (Python `cbor2 canonical=True` and a hand-rolled deterministic encoder) and an independent Rust encoder all produce the same byte string; the BRC-31 ECDSA signature verifies with both Python `ecdsa` and Rust `k256::ecdsa`.

Additional vectors (broadcast envelope with `to_party = 0xFFFF`, presign-phase envelope, negative-test envelope with signature mismatch) are planned for Phase 1; track in [`14-conformance-tests.md`](14-conformance-tests.md).

## See also

- [`decisions/0005-canonical-message-envelope.md`](decisions/0005-canonical-message-envelope.md) — ADR.
- [`02-execution-id.md`](02-execution-id.md) — ExecutionId formula consumed in field 10.
- [`04-session-id.md`](04-session-id.md) — SessionId in field 2.
- [`06-transport.md`](06-transport.md) — how envelopes are delivered.
- [`07-brc31-auth.md`](07-brc31-auth.md) — BRC-31 mutual auth details.
- [`16-operations.md`](16-operations.md) — `traceparent` propagation discipline.
- BRC-31: `~/bsv/BRCs/peer-to-peer/0031.md`
- BRC-78: ECIES envelope spec (referenced).
- RFC 8949 §4.2: Deterministic CBOR encoding.
