# Appendix A — Transport

> Full report from the Transport zone agent of the god-tier-design swarm (2026-05-10).
> Preserved verbatim as supporting depth for [`§06-transport.md`](../../06-transport.md).

---

## §A — God-tier definition for transport

A god-tier MPC transport for a vendor-neutral threshold-signing network must satisfy, *as ground rules and not aspirations*:

| Axis | God-tier bar | Production precedent |
|---|---|---|
| **Security** | Message-level integrity (BRC-31 mutual-auth + BRC-78 ECIES envelope) **independent of any TLS terminator**. No relay can read protocol bytes; no relay can usefully replay or reorder; metadata exposure capped at *coarse-grained* "X talked to Y at minute T". ExecutionId binding closes cross-session replay. | Matrix Olm/Megolm: encryption deliberately layered *above* the federation transport, so a hostile homeserver can drop or delay but cannot read or forge. We adopt the same separation. |
| **UX** | DKG ≤ 1 s p50 / 3 s p99 globally; presign ≤ 500 ms; sign-with-presig ≤ 150 ms; sign-no-presig ≤ 800 ms — *all four at 50 ms inter-party RTT*. Cold-start ≤ 200 ms (no per-ceremony WS handshake). Stuck ceremonies surface as one of three named states (`waiting_for_party N`, `relay_unreachable`, `policy_denied`). | Sodot/DKLS23 demonstrate millisecond-scale signing once nonces are pre-generated; Lit Protocol publishes ~100-300 ms PKP signing as a product baseline. |
| **Vendor-neutrality** | No operator (Babbage, Binary, Calhoun, ...) is load-bearing for *any* ceremony with willing peers. Every cosigner pair can pin a different relay. The protocol survives the disappearance of any single relay operator at any moment, including mid-DKG. | Matrix federation: Alice's homeserver going down does not stop Bob and Charlie from talking via theirs. Tor v3 onion services: relays carry traffic but cannot be coerced into censoring a specific hidden service without breaking the network. |
| **Operability** | Per-ceremony correlation IDs that traverse all relays. Stuck-ceremony forensics from any party's local logs alone. Deployable as: CF Worker (relay), Linux server (relay or cosigner), iOS/Android app (cosigner), browser tab (cosigner). | Fireblocks Co-Signer ships in cloud, on-prem, AWS Nitro, GCP Confidential Space — *one wire format, many enclaves*. We replicate that "one wire, many hosts" stance. |
| **Composability** | Nested MPC works: a 2-of-3 wallet acting as one party in another 2-of-3 routes the inner ceremony's messages through *its* transport without leaking that it is an MPC group. BRC-100 surface unchanged. | Lit's "Lit Actions" call PKPs from inside other PKPs; the transport hides the recursion. We need the same opacity: from the outer ceremony's view, an inner-MPC party is just another peer with one identity key. |

## §B — Option 1: Async E2E-encrypted message bus over federated relays

**One-line summary.** Every cosigner publishes one canonical *MessageBox URL* on its CHIP token. The transport is asynchronous, end-to-end encrypted, sender-signed message envelopes routed via whichever MessageBox the recipient pinned. The wire format is the same on the relay regardless of how the *receiver* listens (WS, FCM, poll). Direct-P2P (QUIC/WebTransport) is an opportunistic accelerator after first contact, never a precondition.

This is essentially "Matrix-style federation, but for MPC ceremony messages, with rust-message-box and `message.b1nary.cloud` as the first two homeservers."

**Wire shape:** the canonical CBOR `MessageEnvelope` per spec §05 — BRC-78 inner encryption + BRC-31 outer signature + ExecutionId binding + correlation_id + traceparent.

**Edge transport choices, server-decoupled:**

| Edge | Used by | How it works |
|---|---|---|
| **Native WebSocket (Socket.IO/EngineIO)** | Linux/desktop cosigners; Binary's `bsv-messagebox-client` already does this | Persistent authed socket, server pushes envelopes by `(recipient_identity, mailbox)` |
| **FCM push** | Mobile cosigners; rust-message-box already implements `/registerDevice` + the FCM v1 pipeline | Server hits FCM with a wakeup notification when an envelope lands in a registered mailbox; client then issues one HTTP `/listMessages` to drain it |
| **HTTP poll** | Browser (no FCM), CF Worker→CF Worker, or paranoid environments that don't want WS | `/listMessages` at adaptive cadence (5 Hz active, 0.5 Hz idle) |
| **Direct QUIC/WebTransport (post-DKG accelerator)** | Established cosigner pairs after a successful DKG | Each party caches the other's `quic_endpoint` from the CHIP token; falls back to relay on hole-punch failure |

**Concretely:** the user's WebSocket steering update means rust-message-box adds Socket.IO/EngineIO over CF Worker DOs in Phase 1 to restore parity with `b1nary.cloud`. The core wire shape *does not change* whether the server pushes via WS, FCM, or poll. **This is the key vendor-neutrality lever**: a cosigner's choice of edge transport is local; it does not propagate into the protocol.

**Discovery & bootstrap.** Per-cosigner pinned URL (in their CHIP token PushDrop on `tm_mpc_signing`) is the source of truth. The CHIP token already carries an identity key, capabilities JSON, and reputation; we extend it with a MessageBox URL (or list, for failover).

For *unknown* cosigners, the BSV overlay (SLAP/CHIP, already wired in `bsv-mpc-overlay/discovery.rs` against 4 mainnet trackers) is the directory. No DHT, no bootnodes, no operator. **The blockchain is the registry.**

**Direct-P2P fallback for established pairs.** After DKG, each cosigner publishes (signed by its identity key, in the next refresh of its CHIP token or via a sticky session record on the relay) its **iroh nodeid** (`iroh:peer:<pubkey>`). Subsequent ceremonies attempt iroh's QUIC-with-holepunch first (Iroh handles relay-vs-direct internally); on failure, fall back to the MessageBox path.

**Metadata privacy.** Three concentric rings:

1. *Default (full-fat metadata).* Relays see `from → to` identity keys (needed to route). Tradeoff: you trust your relay not to publish a social graph.
2. *Per-pair onion.* Cosigners can opt into routing through *another* cosigner's MessageBox as a one-hop mixnet. Costs one extra hop of latency (≈50 ms WAN) and is only meaningful if you have a friend running a relay.
3. *Tor onion v3.* Either party can publish a `.onion` URL in their CHIP token. Relay still sees `tor → tor`, which is the strongest privacy/operability tradeoff we can offer. Latency cost: ~3x baseline (well-known Tor figure).

## §C — Option 2: Pubsub overlay over libp2p (gossipsub)

Replace MessageBox with a libp2p gossipsub topic *per ceremony*, anchored by Kad-DHT for peer routing, bootstrapped from the existing BSV SLAP overlay. Every party joins a transient pubsub topic `mpc/<session_id>`; envelopes flow through gossipsub mesh peers.

**Why this is meaningfully different.** Option 1 has *named relays*. Option 2 has *no named relays*: every cosigner is a libp2p node, and the ceremony's "router" is the gossipsub mesh that self-organizes.

**Killer issue (Operability 4/10):** libp2p stack is heavy for a CF Worker (no WASM gossipsub runtime today; rust-libp2p in WASM is alpha-quality). Doesn't run in browsers without `js-libp2p` (different stack, partial features). Mobile is workable but battery-hostile.

**Verdict:** the right architecture for a *future* network with thousands of nodes and high churn. Wrong for the 2-week deliverable and probably wrong for the next year. Park as v3 (2027+).

## §D — Option 3: Direct-P2P-first via iroh (QUIC + holepunch + relay-fallback)

Invert Option 1's defaults. Direct iroh QUIC connection between parties is the *primary* path. MessageBox is a fallback for cold-start and for parties that genuinely cannot establish QUIC.

**Why this precedent.** iroh's headline thesis is *"IP addresses break, dial keys instead"* — exactly what BRC-31 identity keys give us.

**Killer issue (Operability 7/10):** CF Workers don't expose UDP sockets — QUIC is impossible inside a CF Worker. rust-message-box's whole *raison d'être* is that it runs on CF Workers. **It's a "burn the boats" architecture relative to what's deployed today.**

**Verdict:** right answer for a network without CF Worker operators. Wrong for ours. Use as an *opportunistic accelerator* for established pairs (Option 1's §06.8 reservation), not as primary.

## §E — Cross-layer dependencies

| Layer | Constraint imposed by Option 1 |
|---|---|
| **Identity (07)** | BRC-31 over the envelope is mandatory. Each cosigner's identity key is the routing key — same as today. |
| **Policy (09)** | Policy decisions are emitted as `policy_denied` envelopes — already the rust-mpc shape (`messagebox_cosigner.rs:166`). |
| **Protocol (05) — message envelope** | Envelope shape is canonical, transport-agnostic. Both implementations adopt. **This is the spec lock that makes all options interchangeable later.** |
| **Discovery (12)** | CHIP token carries `inbox_url` (+ optional `quic_endpoint`). |
| **Composability (BRC-100)** | Proxy absorbs all transport variability; clients see unchanged 28-endpoint API. |

**Key dependency on the cggmp24 layer**: ExecutionId binding (P0 #1 in the convergence doc) is the cryptographic anchor that lets us treat the transport as *adversarial*. Without canonical ExecutionId, none of these options is secure under a malicious relay. **Spec-lock ExecutionId before locking transport.**

## §F — Recommendation

**Option 1 is the god-tier answer for the next 12 months.** It is the *only* option that runs in CF Workers, browsers, mobile, and servers today; preserves the production deployments on both sides; makes vendor-neutrality real (per-cosigner-pinned relays); and composes naturally with the BSV overlay we already use.

**Option 3 (iroh direct-P2P) is the right post-DKG accelerator** — bolt it onto Option 1 as the §06.8 fast path. Cosigner pairs that have completed DKG and both have public-ish endpoints get sub-100 ms signing essentially for free.

**Option 2 (libp2p gossipsub) should be the v3 (2027+) story** when the network is at scale and operability tooling for libp2p in CF Worker/browser environments has matured. Lock the canonical envelope now so we can switch substrate later without changing the cggmp24 transcript.

The single most important spec-lock is §06.3 (the canonical envelope) and §06.5/§06.7 (federation by per-cosigner pinned URL). Those two together give us all three options' optionality without forcing the choice.

## Sources

- Lit Protocol Node Architecture / PKP Overview
- Fireblocks API Co-signers Architecture / MPC Library on GitHub
- Sodot MPC Infrastructure
- Iroh — Direct UDP Connections / Relay Connections / noq (QUIC) / Tor custom transport
- Matrix — Olm & Megolm Specification / IETF MIMI Matrix Transport draft
- libp2p / GossipSub spec
- Filecoin libp2p usage
- W3C WebTransport / WebTransport vs WebSockets, 2026

Internal references:
- `/Users/johncalhoun/bsv/mpc/SWARM-CONVERGENCE.md` §1.1
- `/Users/johncalhoun/bsv/rust-message-box/src/lib.rs`, `CLAUDE.md`
- `/Users/johncalhoun/bsv/mpc/rust-mpc/crates/transport/src/{traits,messagebox_transport,messagebox_cosigner,mpc_transport}.rs`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/crates/bsv-mpc-proxy/src/bridge.rs`
