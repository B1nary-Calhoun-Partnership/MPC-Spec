# ADR-0005: Canonical Message Envelope (CBOR + BRC-78 + BRC-31 + ExecutionId)

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)

## Context

The two implementations wrap cggmp24 round messages in different envelopes:

- **bsv-mpc** uses `WireMessage { sender, is_broadcast, msg }` (HTTP/JSON) plus an outer `RoundMessage { session_id, round, from, to, payload }` (`crates/bsv-mpc-core/src/dkg.rs:73`, `types.rs:150`).
- **rust-mpc** uses `MpcEnvelope` from `mpc_core::envelope` with fields `{ session_id, vault_id, coordinator, originator, op: MpcOp::{Keygen|Auxinfo|Sign|...} }` carrying a typed operation tagged enum.

The cggmp24 inner Msg (`Msg<Secp256k1, Sha256>`) IS wire-compatible — both pin to the same curve+digest. **The outer envelopes are not interchangeable.** An adapter is required for cross-implementation ceremonies.

This ADR locks the canonical envelope to replace both.

## Decision

All MPC ceremony messages MUST be wrapped in the canonical `MessageEnvelope`, encoded as canonical CBOR per RFC 8949 §4.2:

```
MessageEnvelope = {
    1:  u8,       // version (0x01 for mpc-spec-v1)
    2:  bstr32,   // session_id (per §04)
    3:  bstr33,   // joint_pubkey (compressed; all-zeros during DKG keygen)
    4:  tstr,     // phase ("dkg-keygen" | "dkg-auxinfo" | "presign" | "sign" | "ecdh" | "refresh")
    5:  u8,       // round (1-based; cggmp24 round number for the phase)
    6:  u16,      // from_party
    7:  u16,      // to_party (0xFFFF for broadcast)
    8:  bstr,     // inner: BRC-78 ECIES envelope wrapping cggmp24 inner Msg (CBOR)
    9:  bstr,     // sender_sig_brc31 over canonical CBOR encoding of fields 1..8
    10: bstr8,    // execution_id_prefix (first 8 bytes of canonical ExecutionId per §02)
    11: tstr,     // OPTIONAL: correlation_id (UUIDv7)
    12: tstr,     // OPTIONAL: traceparent (W3C Trace Context, per §16)
}
```

Both implementations adopt this format. The transport (§06) carries this envelope identically over WebSocket, HTTP poll, FCM-triggered fetch, or direct iroh QUIC.

## Rationale

Three layers compose:

1. **BRC-78 ECIES inner encryption** — payload encrypted to recipient's identity-key. Defends against relay observation of ceremony content.
2. **BRC-31 outer signature** — sender's identity-key signature over the envelope. Defends against relay forgery, replay, MITM.
3. **ExecutionId prefix binding** — relays can bucket envelopes by ceremony without learning ceremony state.

The "encryption above the transport" pattern is borrowed from Matrix Olm/Megolm, where security is deliberately layered above federation so a hostile homeserver can drop or delay messages but cannot read or forge.

Canonical CBOR (RFC 8949 §4.2) provides deterministic encoding — both implementations produce byte-identical envelopes from identical inputs. This is the test-vector seam.

The `traceparent` field reservation (CBOR map key 12) lets distributed tracing across federation boundaries work without further envelope changes.

## Consequences

- **`bsv-mpc`:** Implement the canonical envelope. Replace `WireMessage` + `RoundMessage`. Generate test vectors. ~2 days of work (CBOR encoding + BRC-78 wrapper + BRC-31 signing/verifying).
- **`rust-mpc`:** Replace `MpcEnvelope` with the canonical form. Generate test vectors. ~2 days.
- **`bsv-messagebox-cloudflare`:** Add CBOR-aware passthrough (relays MUST NOT modify envelopes; today they pass arbitrary bodies, so this may be a no-op).
- **Spec:** [`§05-message-envelope.md`](../05-message-envelope.md) codifies the schema and canonical CBOR encoding.
- **Test vectors:** Concrete envelope examples in `conformance/test-vectors/05-message-envelope.cbor` (binary) and `.diag.txt` (CBOR diagnostic).

This is the wire format both implementations adopt. After landing, an adapter layer between implementations is no longer required.

## Alternatives considered

- **JSON envelope** — rejected; non-canonical (key ordering, whitespace), larger size, harder to test for byte-equivalence.
- **Protobuf** — rejected; both implementations are Rust, neither has protobuf in their stack today, adds dependency burden for marginal gain.
- **Keep both envelopes + adapter** — rejected; perpetual maintenance burden, two test vector sets, harder to reason about.
- **Flatbuffers** — rejected; same reasoning as protobuf.

## See also

- Spec: [`§05-message-envelope.md`](../05-message-envelope.md)
- Cross-references: §02 (ExecutionId), §04 (SessionId), §07 (BRC-31), §16 (traceparent), BRC-78 (ECIES).

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
