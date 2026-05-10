# ADR-0006: Federated MessageBox with WebSocket as canonical receive transport

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)

## Context

The two implementations and the relay infrastructure are out of step on transport:

- **rust-mpc** uses Binary's `bsv-messagebox-client` 0.1.1, which speaks Socket.IO/EngineIO over WebSocket against the BSV `message-box-server` protocol.
- **`message.b1nary.cloud`** (Binary's deployed MessageBox) supports WebSocket via its parent Node.js implementation.
- **`rust-message-box`** (Calhoun's CF Worker port) deliberately deleted WebSocket support in v2 (`MessageRoom` Durable Object class deleted) to match `go-messagebox-server`'s HTTP-only scope. CLAUDE.md states: *"HTTP REST only, no WebSocket. Clients poll `/listMessages` or rely on FCM push."*

Federation (per cosigner pinning their preferred relay) was the original design. With `rust-message-box` HTTP-only, federating produces an asymmetric experience: cosigners pinning `b1nary.cloud` get sub-second signing; cosigners pinning `rust-message-box` get poll-bound latency (5 Hz hardcoded in `MessageBoxCosignerTransport`).

The user (Calhoun) confirmed unlimited resources for the partnership and explicitly committed to making `rust-message-box` WebSocket-compliant if WebSocket is the right answer.

## Decision

WebSocket (Socket.IO/EngineIO compatible) is the **canonical receive transport** for v1. Both production relays support it:

- `message.b1nary.cloud` — already supports it.
- `rust-message-box` — Calhoun extends it with Socket.IO over CF Worker Durable Objects in Phase 1, restoring parity with `b1nary.cloud`'s WS surface.

HTTP polling and FCM-triggered HTTP remain MUST-support fallbacks for environments where WebSocket is unavailable (browser-without-WS, mobile background, edge runtimes without Durable Object equivalents).

Federation is preserved: each cosigner pins its preferred relay in CHIP token `transport.inbox_url`. The protocol does not require any single relay to be reachable by all parties; only that each party's chosen relay is reachable by every other party.

## Rationale

WebSocket-canonical wins on two axes that matter:

1. **Latency.** WebSocket signing-with-presig is ~50ms at 50ms RTT vs ~200ms for poll. For a Notary product competing on sub-second UX, this matters.
2. **Wire alignment.** rust-mpc's existing transport is already WebSocket-shaped. Adopting WebSocket-canonical means no client code changes on Binary's side; just the spec lock.

The cost is on Calhoun's side: ~1500 LOC to add Socket.IO/EngineIO compatibility over CF Worker Durable Objects. With unlimited resources framing, this is acceptable. Reverses the v2-scope decision in `rust-message-box` deliberately — that decision was constraint-driven (match go-messagebox-server scope), and the unlimited-resources framing makes the constraint inapplicable.

The fallback transports (HTTP poll, FCM) remain because (a) some environments genuinely cannot do WebSocket, (b) bsv-mpc-worker conformance to the BRC-100 surface needs to work on edge runtimes that may not support DO + WebSocket, and (c) defense in depth — if WS is broken on one side, parties can fall through to poll without ceremony abort.

## Consequences

- **`rust-message-box`:** Add Socket.IO/EngineIO over CF Worker Durable Objects. ~1500 LOC. Add `MessageRoom` (or equivalent) Durable Object class back. Phase 1 work item.
- **`bsv-mpc`:** Add MessageBox transport client (port from rust-mpc). `bsv-mpc-proxy` optionally routes MPC sessions via MessageBox instead of direct HTTP. ~4-5 days of work. Required for any joint ceremony.
- **`rust-mpc`:** No transport-layer change. One required fix: implement `presign_round` and `collect_presig_share` over MessageBox (currently `TransportError::Protocol("...not supported via MessageBox")`). See ADR-0010 / OPEN-QUESTIONS Q3.
- **Spec:** [`§06-transport.md`](../06-transport.md) codifies WebSocket-canonical + HTTP-poll/FCM fallbacks + federation rules.
- **Test vectors:** Cross-relay test fixture in `conformance/test-vectors/06-transport/` once both relays are WS-capable.

This ADR reverses the implicit position from the first swarm's `SWARM-CONVERGENCE.md` recommendation that `rust-message-box` stay HTTP-only. The reversal is correct in light of unlimited-resources framing.

## Alternatives considered

- **Keep `rust-message-box` HTTP-only; users pinning it get slow ceremonies** — rejected; asymmetric UX undermines federation. The 5Hz polling floor (~800ms sign-no-presig) is unacceptable for the Notary product.
- **Native WebSocket only (no Socket.IO compat)** — rejected; would force Binary to change `bsv-messagebox-client`. ~600 LOC saved on Calhoun side at the cost of disrupting Binary's existing client. Not the right trade.
- **libp2p gossipsub** — rejected; doesn't run in CF Workers, weak browser support. Park as v3 (2027+) when the ecosystem matures.
- **Replace MessageBox entirely with iroh QUIC** — rejected; iroh doesn't run in CF Workers (no UDP). MessageBox runs everywhere; iroh as accelerator only.

## See also

- Spec: [`§06-transport.md`](../06-transport.md)
- Open question: [`OPEN-QUESTIONS.md` Q3](../OPEN-QUESTIONS.md), [`Q6`](../OPEN-QUESTIONS.md)
- Appendix: [`appendices/swarm-reports/A-transport.md`](../appendices/swarm-reports/A-transport.md)
- Reference: BSV `message-box-server` protocol, `bsv-messagebox-client` 0.1.1.

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
