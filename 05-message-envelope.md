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

A recipient MUST log envelope rejection (with `correlation_id` if present) for forensic forensics. The recipient MUST NOT respond to the malformed envelope; the protocol-level identifiable-abort handler decides whether to attribute the failure to a specific party.

## 05.10 Reserved fields

CBOR map keys not listed in §05.3 are RESERVED for future spec versions. Implementations MUST NOT emit unknown keys and SHOULD reject (or log a warning for) envelopes with unknown keys to enable forward-compatible spec evolution.

## 05.11 Test vectors

In `conformance/test-vectors/05-message-envelope.cbor` (binary) and `conformance/test-vectors/05-message-envelope.diag.txt` (CBOR diagnostic notation).

Examples include:
- A signing-round-1 envelope from party 0 to party 1.
- A DKG-keygen broadcast envelope (`to_party = 0xFFFF`, replicated per recipient).
- A presign envelope with `traceparent` set.
- An invalid envelope (signature mismatch) for negative-test.

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
