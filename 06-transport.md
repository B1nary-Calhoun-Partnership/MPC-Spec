# 06 — Transport

**Status:** DRAFT
**Phase:** 1
**Decided by:** ADR-0006 (proposed)
**Last updated:** 2026-05-10

## 06.1 Goals

The MPC transport SHALL provide reliable, asynchronous, end-to-end-authenticated, end-to-end-encrypted message delivery between cosigners and a coordinator, without requiring any single operator (relay, certifier, directory) to be load-bearing for ceremony correctness.

## 06.2 Layering principle

Per the principle adopted from Matrix Olm/Megolm, security is layered *above* the transport. Implementations MUST treat all relays as untrusted: a relay is permitted to drop, reorder, delay, or duplicate envelopes; a relay is NOT permitted to read or modify envelope payloads (either property is enforced cryptographically per §05).

## 06.3 Canonical envelope

All MPC ceremony messages MUST be wrapped in the canonical `MessageEnvelope` (§05). The envelope:

1. Carries the inner cggmp24 message encrypted to the recipient's BRC-31 identity key (BRC-78 ECIES).
2. Is signed by the sender's BRC-31 identity key over fields 1–8.
3. Embeds the first 8 bytes of the canonical ExecutionId (§02), allowing relays to bucket messages by ceremony without learning ceremony state.

## 06.4 Receive transports

A conforming implementation MUST support, *for receiving messages*, **at least one** of:

- **WebSocket** (canonical for v1) — Socket.IO/EngineIO compatible WebSocket subscription per the BSV `message-box-server` protocol. Relay pushes envelopes by `(recipient_identity, mailbox)` pair. Authenticated via BRC-31 mutual handshake on connection.
- **HTTP polling** of `/listMessages` — for environments without WebSocket support (some browsers, edge runtimes without Durable Object equivalents). Adaptive cadence: 5 Hz active, 0.5 Hz idle.
- **FCM (or platform-equivalent) push** — for mobile cosigners. Relay sends FCM wakeup; client issues one HTTP `/listMessages` to drain. RECOMMENDED for mobile profile (`profile-mobile` per §16).

WebSocket is the canonical receive transport for v1. HTTP polling and FCM are MUST-support fallbacks for environments where WebSocket is unavailable or undesirable.

## 06.5 Send transport

All implementations MUST support `POST /sendMessage` per the BSV `message-box-server` API. Sends are HTTP POST with the canonical envelope (CBOR-encoded `MessageEnvelope`) as the body, BRC-31 mutual auth on the request.

## 06.6 Direct-P2P fallback for established pairs (OPTIONAL)

Following a successful DKG, each cosigner MAY publish an `iroh_endpoint` in a refreshed CHIP token (§12). Subsequent ceremonies between the same `joint_pubkey`'s parties SHOULD attempt the iroh path before falling back to the relay path. Iroh's relay-fallback is transparent to the MPC layer; the MPC layer SHALL NOT observe whether a direct or relayed QUIC path was used.

Direct-P2P MUST NOT be a precondition for ceremony progress; failure to establish a direct path MUST fall back to the relay path silently.

The reservation of QUIC/iroh as the post-DKG accelerator is an OPTIONAL implementation; spec-conformance does not require it. See [`OPEN-QUESTIONS.md` Q6](OPEN-QUESTIONS.md).

## 06.7 Federation

Each cosigner SHALL publish in its CHIP token (§12) a `transport.inbox_url` and zero or more `transport.inbox_url_fallback`. A coordinator routing to that cosigner MUST attempt the primary URL first, then each fallback in order.

Cosigners MAY pin different MessageBox operators (e.g., `<binary-messagebox-host-tbd>`, `<calhoun-messagebox-deploy-tbd>`); the protocol does not require any single relay to be reachable by all parties simultaneously, only that each party's chosen relay is reachable by *every other party*.

Both production relays MUST support the WebSocket receive transport (Socket.IO/EngineIO compatible) for v1 conformance:

- **`<binary-messagebox-host-tbd>`** (Binary): currently supports WebSocket. No change required.
- **`<calhoun-messagebox-deploy-tbd>`** (Calhoun): currently HTTP-only (v2 scope). Calhoun extends with Socket.IO over CF Worker Durable Objects in Phase 1 to restore parity. Reverses the prior v2 scope decision; ADR-0006 records the design change.

## 06.8 Discovery and bootstrap

Long-term cosigner discovery SHALL use the BSV SLAP/CHIP overlay on topic `tm_mpc_signing` (§12). No transport-layer bootstrap nodes, DHTs, or directory services are required.

## 06.9 Metadata privacy tiers

Implementations MUST implement Tier 0 (relay sees `from`, `to`, `session_id_prefix`, `phase`, `round`, `timestamp`).

Implementations SHOULD support Tier 1: `tor_onion_url` field in the CHIP token's `transport` block, accepted in lieu of `inbox_url`. The relay still sees `tor → tor`, but the IP-level metadata is shielded by Tor v3 onion routing.

Tier 2 (one-hop relay-via-cosigner mixing) is OPTIONAL. Not part of v1 conformance.

## 06.10 Latency budgets

Conformant implementations SHOULD meet, at 50ms inter-party RTT:

| Operation | p50 budget | p99 budget |
|---|---|---|
| DKG keygen + auxinfo | 2 s | 5 s |
| Presign (3 rounds) | 200 ms | 800 ms |
| Sign with presig (1 round) | 100 ms | 400 ms |
| Sign without presig (4 rounds) | 400 ms | 1.5 s |
| ECDH partial (1 round) | 100 ms | 400 ms |

These budgets assume the WebSocket receive transport. HTTP-poll receivers add up to ~200ms per round (0.5 Hz idle polling); FCM receivers add up to ~500ms wakeup amortized over the first message of a ceremony, after which subsequent messages use HTTP fast-path.

## 06.11 Forensic correlation

Every envelope SHOULD carry the `correlation_id` field set by the coordinator at ceremony init (UUIDv7 RECOMMENDED). Logs at any party MUST include this correlation_id when present, enabling stuck-ceremony reconstruction from any single party's logs alone.

## 06.12 Heartbeats and reconnection

WebSocket connections MUST send heartbeat pings every 30 seconds; relays MUST disconnect idle sockets after 60 seconds without traffic. Reconnection logic MUST use exponential backoff with cap (initial 1s, double, cap 30s).

After reconnection, the receiver MUST re-fetch missed messages via `/listMessages` (the WS path is for new messages only; backfill is HTTP).

## 06.13 Acknowledgement

Receivers SHOULD acknowledge envelope receipt via `POST /acknowledgeMessage` with the relay-assigned message_id. Relays MAY treat unacknowledged messages as undelivered and retry up to 3 times before purging.

Acknowledgement is best-effort; protocol correctness does NOT depend on relay-side ack handling.

## 06.14 Implementation notes

- bsv-mpc currently uses direct HTTP between proxy and KSS (`bridge.rs`). MUST add MessageBox transport client (port from rust-mpc) to participate in cross-impl ceremonies.
- rust-mpc currently uses Binary's `bsv-messagebox-client` 0.1.1 (Socket.IO/EngineIO over WebSocket). No change required for transport; one fix needed for presigning round handling (see [`OPEN-QUESTIONS.md` Q3](OPEN-QUESTIONS.md)).
- bsv-messagebox-cloudflare currently HTTP-only (v2 scope, `MessageRoom` Durable Object class deleted). Calhoun adds Socket.IO over CF Worker DOs to restore WebSocket parity with `<binary-messagebox-host-tbd>`.

## See also

- [`decisions/0006-federated-messagebox-with-websocket.md`](decisions/0006-federated-messagebox-with-websocket.md) — ADR.
- [`05-message-envelope.md`](05-message-envelope.md) — the envelope this transport carries.
- [`12-discovery.md`](12-discovery.md) — CHIP token format, including `transport` block.
- [`appendices/swarm-reports/A-transport.md`](appendices/swarm-reports/A-transport.md) — full design rationale.
