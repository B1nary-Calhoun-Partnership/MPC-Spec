# 07 — BRC-31 Mutual Authentication

**Status:** DRAFT
**Version:** v1
**Phase:** 1
**Decided by:** ADR-0007 (proposed)
**Last updated:** 2026-05-10

## 07.1 Purpose

Every interaction between cosigners (over MessageBox, over direct iroh/QUIC, between proxy and Notary) MUST be mutually authenticated via BRC-31 (Authrite). BRC-31 provides:

- **Identity attribution** — every message is provably from a specific identity key.
- **Replay protection** — per-session nonce + per-message counter.
- **Independence from TLS** — message-level integrity survives TLS terminator compromise, CA breach, or transport substitution (HTTP↔WebSocket).

## 07.2 Reference implementation

The canonical reference is [`bsv-middleware-cloudflare`](https://github.com/Calhooon/bsv-middleware-cloudflare) (`~/bsv/Calhooon/bsv-middleware-cloudflare/`), an MIT-licensed CF Worker middleware crate. Both implementations SHOULD reuse it (or re-derive it for non-Worker hosts) without modification to the wire-level handshake.

bsv-mpc's `crates/bsv-mpc-worker/src/auth.rs` is a 963-LOC port of this reference, with full handshake + session storage + response signing + 13 unit tests. Treat this as a high-quality second reference.

## 07.3 BRC-31 spec

The full BRC-31 specification is at `~/bsv/BRCs/peer-to-peer/0031.md`. This file profiles BRC-31 for MPC use; it does not replace the BRC.

## 07.4 Identity-key derivation

Each party uses their **long-lived BRC-100 identity key** (compressed secp256k1) for BRC-31. This is the same key that signs BRC-52 cosigner certs (§08) and signs envelope outer-signatures (§05).

For nested-MPC (a 2-of-3 wallet acting as a cosigner), the identity key is the **joint pubkey** of the inner ceremony, and the BRC-31 signature is itself produced via threshold signing. The outer protocol does not observe the recursion.

## 07.5 Required mutual-auth

The following operations MUST require BRC-31 mutual authentication:

| Operation | Endpoint | Notes |
|---|---|---|
| Connect WebSocket to MessageBox | `WS upgrade` | BRC-31 handshake on connection |
| `POST /sendMessage` | MessageBox | Per-request BRC-31 |
| `POST /listMessages` | MessageBox | Per-request BRC-31 |
| `POST /acknowledgeMessage` | MessageBox | Per-request BRC-31 |
| `POST /signCertificate` | Certifier | Per-request BRC-31 — MUST gate (rust-mpc certifier currently does NOT) |
| Direct iroh QUIC connection | post-DKG fast path | BRC-31 handshake on connection |
| All MPC ceremony envelopes | inside MessageEnvelope.field_9 | Per-envelope BRC-31 |

## 07.6 Anonymous endpoints

The following MAY be unauthenticated:

- `GET /` and `GET /health` (liveness probes)
- `GET /api-docs` (public OpenAPI spec)
- BRC-22 overlay queries that require no identity binding

All other endpoints MUST gate on BRC-31. Falling back to "trust the network" or "trust localhost" is forbidden.

## 07.7 Session caching

Implementations MAY cache BRC-31 session state (per the reference middleware's KV-backed approach) for a TTL of 1 hour. Caching reduces handshake overhead for high-volume signing.

A cached session MUST be invalidated immediately if:
- The cached identity key's BRC-52 cert (§08) expires or is revoked.
- The cosigner's policy manifest (§09) is rotated.
- The cosigner is replaced via §13.7 operator-replacement choreography.

## 07.8 Identity-key rotation

Each operator MUST rotate their BRC-31 identity-key on a 90-day cadence (§16):

1. New identity-key generated.
2. New BRC-52 cert issued by the certifier covering the new key.
3. CHIP token (§12) refreshed to advertise the new key.
4. Old key sunset with a 7-day overlap window.
5. After sunset, old key MUST NOT be used for any new sessions.

Compromised key rotation is on the IR-002 path (§16, sub-30-min).

## 07.9 Forbidden

- Skipping BRC-31 verification on a "trusted" endpoint (no endpoint is trusted by location).
- Caching session state for longer than 1 hour without re-authentication.
- Using TLS as the sole authentication mechanism. TLS protects the transport; BRC-31 protects the *message*.
- Sharing identity keys across cosigners. Each operator runs distinct keys.

## 07.10 Implementation notes

- bsv-mpc `bsv-mpc-worker/src/auth.rs` — full BRC-31 implementation. Use as reference.
- bsv-mpc `bsv-mpc-service` — same auth.rs reused.
- bsv-mpc THREAT-MODEL.md A4/A7 — currently labels BRC-31 as TODO; the doc is stale. MUST scrub.
- rust-mpc `bins/certifier/src/handlers.rs` — `/signCertificate` currently accepts unauthenticated requests. MUST gate behind BRC-31. See [`OPEN-QUESTIONS.md` Q4 / ADR-0011](OPEN-QUESTIONS.md).
- rust-mpc `crates/transport/` — already uses BRC-31 via Binary's `bsv-messagebox-client`. No change.

## 07.11 Test vectors

In `conformance/test-vectors/07-brc31-auth.json`. Examples:
- A valid request/response handshake.
- A replay attempt (re-using a stale nonce) — MUST be rejected.
- A signature with wrong identity key — MUST be rejected.
- A malformed handshake — MUST be rejected.

## See also

- [`decisions/0007-brc31-canonical-reference.md`](decisions/0007-brc31-canonical-reference.md) — ADR.
- [`05-message-envelope.md`](05-message-envelope.md) — envelope outer-signature is BRC-31.
- [`08-identity.md`](08-identity.md) — BRC-31 identity keys are bound to BRC-52 certs.
- BRC-31: `~/bsv/BRCs/peer-to-peer/0031.md`
- Reference: `~/bsv/Calhooon/bsv-middleware-cloudflare/src/middleware/auth.rs`
- bsv-mpc port: `~/bsv/mpc/bsv-mpc/crates/bsv-mpc-worker/src/auth.rs`
