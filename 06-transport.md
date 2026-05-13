# 06 — Transport

**Status:** DRAFT
**Version:** v1
**Phase:** 1
**Decided by:** ADR-0006 (proposed); ADR-0030 (proposed, §06.15-§06.20)
**Last updated:** 2026-05-12

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

Cosigners MAY pin different MessageBox operators (e.g., `rust-message-box.dev-a3e.workers.dev`, `<binary-messagebox-host-tbd>`); the protocol does not require any single relay to be reachable by all parties simultaneously, only that each party's chosen relay is reachable by *every other party*.

Both production relays MUST support the WebSocket receive transport (Socket.IO/EngineIO compatible) for v1 conformance:

- **`<binary-messagebox-host-tbd>`** (Binary): supports WebSocket. No change required.
- **`rust-message-box.dev-a3e.workers.dev`** (Calhoun, repo: [`Calhooon/bsv-messagebox-cloudflare`](https://github.com/Calhooon/bsv-messagebox-cloudflare)): supports WebSocket via the `/ws` endpoint on a per-identity hibernatable `MessageHub` Cloudflare Durable Object. Event surface is byte-compatible with `@bsv/authsocket`. WebSocket parity + Socket.IO compatibility over BRC-103 mutual auth shipped in v0.2.0 (M9 / M10 #61 / M11; merge `278cf07`). See [ADR-0006](decisions/0006-federated-messagebox-with-websocket.md).

## 06.8 Discovery and bootstrap

Long-term cosigner discovery SHALL use the BSV SLAP/CHIP overlay on topic `tm_mpc_signing` (§12). No transport-layer bootstrap nodes, DHTs, or directory services are required.

## 06.9 Metadata privacy tiers

Implementations MUST implement Tier 0 (relay sees `from`, `to`, `session_id_prefix`, `phase`, `round`, `timestamp`).

Implementations SHOULD support Tier 1: `tor_onion_url` field in the CHIP token's `transport` block, accepted in lieu of `inbox_url`. The relay still sees `tor → tor`, but the IP-level metadata is shielded by Tor v3 onion routing.

Tier 2 (one-hop relay-via-cosigner mixing) is OPTIONAL. Not part of v1 conformance.

## 06.10 Latency budgets (network-profile matrix)

Conformant implementations SHOULD meet the budgets in the matrix below. Budgets are **network-profile-conditioned** because:
- Auxinfo is **compute-bound** on `profile-mobile` (Paillier safe-prime keygen + ~64-128KB ZK proofs per round dominate), not wire-bound.
- Sign-with-presig assumes a **warm WebSocket**. Cold-WS first-sign adds a one-shot Socket.IO/EngineIO handshake (60-150ms broadband; 250-600ms cellular).
- Cross-region and mobile profiles have materially different tail behavior.

| Operation | LAN 10ms | Same-region 50ms (canonical) | Cross-region 250ms | Mobile 150/500ms |
|---|---|---|---|---|
| DKG keygen + auxinfo | p50 2.0s / p99 4.7s | p50 2.5s / p99 5.6s | p50 3.9s / p99 9.0s | **p50 17s / p99 33s** ‡ |
| Presign (3 rounds) | p50 35ms / p99 120ms | p50 165ms / p99 600ms | p50 800ms / p99 1.8s | p50 500ms / p99 1.8s |
| Sign with presig (1 round) — warm WS | p50 15ms / p99 50ms | p50 60ms / p99 250ms | p50 280ms / p99 700ms | p50 200ms / p99 700ms |
| Sign with presig — cold-WS additive penalty | +60-150ms one-shot | +60-150ms one-shot | +120-300ms one-shot | +250-600ms one-shot |
| Sign without presig (4 rounds) | p50 60ms / p99 200ms | p50 280ms / p99 1.1s | p50 1.1s / p99 2.6s | p50 2.0s / p99 3.0s |
| ECDH partial (1 round) | p50 15ms / p99 40ms | p50 60ms / p99 250ms | p50 280ms / p99 700ms | p50 200ms / p99 700ms |
| Burn-rate regen (8 parallel presigns) | p50 80ms / p99 250ms | p50 220ms / p99 800ms | p50 900ms / p99 2.0s | p50 600ms / p99 2.0s |
| Refresh ceremony (full) | p50 2.5s / p99 5.0s | p50 3.0s / p99 6.0s | p50 5.0s / p99 12.0s | p50 20s / p99 40s |
| Audit STH publish (mainnet 1-conf) | n/a | p50 10 min / p99 60 min | same | same |

‡ **Auxinfo on `profile-mobile` is compute-dominated.** Implementations on mobile MUST off-load Paillier safe-prime generation to a background queue (see §06.10.1) and gate user-visible DKG completion on completion of that queue. Naive on-foreground keygen blocks the UI for 10-30 seconds on commodity ARM mobile chips.

### 06.10.1 Paillier safe-prime pool (RECOMMENDED for `profile-mobile`, `profile-edge`)

Implementations SHOULD maintain an at-rest-encrypted pool of pre-generated 2048-bit Paillier safe-prime keypairs, consumed by auxinfo and refresh ceremonies. Recommended pool floor: 2 keypairs per profile; regenerated at idle. This converts the auxinfo p99 mobile budget from 33s to ~6s. See [ADR-0041](decisions/0041-network-profile-latency-budgets.md).

### 06.10.2 WebSocket pre-warm (RECOMMENDED)

The WS connection SHOULD be brought up at wallet-open (or app-resume), not at sign-time, to mask the 60-150ms Socket.IO/EngineIO handshake on the first sign. The wallet-open WS warm event MAY be combined with a `signing_intent` signal (proposed predictive presig regen, see ADR-0041) to also pre-warm the presig pool. Implementations targeting `profile-mobile` SHOULD heart-beat the WS aggressively (15s) to survive carrier NAT timeouts.

### 06.10.3 Source notes for the budget matrix

| Element | Source |
|---|---|
| cggmp24 round counts | LFDT-Lockness `cggmp21` repo + Canetti/Gennaro/Goldfeder/Makriyannis/Peled ePrint 2021/060 |
| Auxinfo byte sizes (64-128KB / round) | `paillier-blum` proof ~ 80 × (2048/8) = ~64 KB; Pedersen `prm` proof ~ 32 KB at 128-bit security |
| Paillier safe-prime gen (compute) | OpenSSL `genrsa 2048` reference: 1-3s desktop, 5-15s ARM mobile |
| Socket.IO/EngineIO handshake | Socket.IO docs, "upgrade handshake" 2-4 packets |
| Mainnet 1-conf wall-clock | BSV mainnet mean ~10 min, long tail to 60 min |

Receive transport assumptions: WebSocket primary per §06.4. HTTP-poll receivers add up to ~200ms per round (0.5 Hz idle polling); FCM receivers add up to ~500ms wakeup amortized over the first message of a ceremony, after which subsequent messages use HTTP fast-path.

**Notary product (§15) SHOULD advertise the network profile they operate under** in their CHIP token (§12); a `profile-server`-only Notary cannot be expected to meet `profile-mobile` cosigner constraints.

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

## 06.15 Presignature lifecycle — overview

CGGMP'24 presignatures are the v1 fast-path enabler: a valid presig collapses signing from 4 rounds to 1 round (§06.10 budgets). To sustain the fast path, each `(joint_pubkey, cosigner_subset)` pair MUST maintain a pool of fresh presigs at the coordinator. Sections §06.15–§06.20 specify the canonical lifecycle: generation, encryption, storage, consumption, burn-rate regeneration, and mandatory invalidation.

The normative content of these sections is decided by [ADR-0030](decisions/0030-presig-coordinator-storage.md).

## 06.16 Generation and encryption

A presign session is a standard cggmp24 3-round protocol (§01) coordinated by the coordinator (typically party 0 in `parties_at_keygen` for the active subset). At the end of round 3:

1. Each cosigner holds its own `tilde_chi_i` and the shared public commitment data (`tilde_Delta_j`, `tilde_S_j` per party).
2. Each cosigner MUST encrypt its `tilde_chi_i` (and any other secret presig material it must retain) using **BRC-2 self-encryption via the ProtoWallet `encrypt()` API** with the following canonical parameters:

| Parameter | Value |
|---|---|
| `counterparty.counterparty_type` | `Self_` |
| `protocol_id.security_level` | `2` |
| `protocol_id.protocol` | `"mpcpresig"` (BRC-43-compliant; no hyphens; lowercase) |
| `key_id` | the presig identifier (`presig_id`, see §06.17) |
| `privileged` | `false` |

The wallet computes the BRC-42 invoice per §03 (`2-mpcpresig-{presig_id}`), derives the ECDH-self shared secret, derives the AES-256-GCM key, and emits the ciphertext. The cosigner MUST NOT bypass the wallet primitive (no hand-rolled AES) — this guarantees both implementations encrypt to the same canonical key derivation.

3. The cosigner MUST send the ciphertext to the coordinator via the return mailbox allocated for the session (§06.17.2). The cosigner MUST zeroize its plaintext share from working memory once the coordinator has acknowledged receipt.

## 06.17 PresigBundle and session orchestration

### 06.17.1 PresigBundle structure

The coordinator MUST construct and persist, for each successful presign session:

```
PresigBundle = {
    presig_id:                tstr,    // unique per presig; canonical form = the presign session_id
    presig_bytes:             bstr,    // coordinator's own serialized presig share (plaintext at rest under coordinator's at-rest encryption)
    cosigner_encrypted_shares:[bstr],  // one ciphertext per cosigner (hex or raw bytes)
    gamma_hex:                tstr,    // shared Gamma commitment (hex)
    commitments:              bstr,    // serialized PresignaturePublicData commitments (CBOR)
    policy_id:                bstr32,  // canonical policy hash this presig is bound to (per §09)
    joint_pubkey:             bstr33,  // joint pubkey this presig is bound to
    parties_at_keygen:        [u16],   // cosigner subset (party indices) this presig is bound to
    generated_at:             u64,     // unix timestamp seconds (operational only; not security-load-bearing)
}
```

When multiple cosigners participate (`n > 2`), the bundle contains one `cosigner_encrypted_shares[i]` entry per cosigner, indexed positionally by the party order in `parties_at_keygen`.

`policy_id`, `joint_pubkey`, and `parties_at_keygen` are the **binding triple**: a presig is consumable only when all three match the current ceremony's binding. §06.18 enumerates the invalidation conditions.

### 06.17.2 Session mailboxes

For each presign session, the coordinator MUST allocate two transient mailboxes on its MessageBox:

- `mpc_{session_id}` — round-trip channel for the 3-round cggmp24 protocol traffic.
- `presig_return_{session_id}` — one-way return channel for the cosigner-encrypted ciphertexts.

The session_id is the canonical SessionId per §04 with `purpose = "presign"`.

Both mailboxes MUST be deleted by the coordinator once the bundle is persisted (or once the session-timeout expires for stranded mailboxes). RECOMMENDED stranded-mailbox expiry: 5 minutes.

### 06.17.3 Single-use enforcement

A `PresigBundle` MUST be consumed at most once. Once a sign-ceremony begins consuming a bundle (the coordinator has shipped the cosigner's encrypted share back for decryption), the coordinator MUST atomically mark the bundle as in-use; on successful sign completion it MUST remove the bundle from the available pool. If a sign ceremony aborts mid-flight, implementations MAY allow the bundle to return to the pool only if no plaintext sigma share has been emitted by any cosigner (RECOMMENDED: do not return; treat all in-flight aborts as consumed).

Single-use enforcement is the spec-level mitigation for the CVE-2025-66017 presignature-forgery class (§01).

## 06.18 Mandatory invalidation

The coordinator MUST delete all `PresigBundle` rows where ANY of the following invalidation triggers fires:

| Trigger | Scope of deletion | Trigger source |
|---|---|---|
| **Share refresh commit** | All bundles for the refreshed joint_pubkey | §18 refresh ceremony |
| **Cosigner subset change** | All bundles whose `parties_at_keygen` matches the prior subset | §13.7 operator replacement |
| **Policy manifest update** | All bundles whose `policy_id` no longer matches the current manifest | §09 policy update procedure |
| **Joint pubkey change** | All bundles for the prior joint_pubkey | §18 post-recovery rekeying |

Deletion MUST be atomic with the trigger event. A bundle MUST NOT be consumable across an invalidation boundary even momentarily; implementations MUST take the trigger before processing any sign request that would use a now-stale bundle.

Deletion MUST be best-effort zeroize: storage backends MUST overwrite the bytes (truncate-and-rewrite, secure-erase syscall, or equivalent). Pure mark-as-deleted (logical-only) is non-conformant. Implementations using object stores without erase semantics MUST encrypt-at-rest with rotated keys so a key-rotation operation effectively zeroizes the prior generation.

### 06.18a Presig-path fall-off signal (normative UX, per ADR-0034)

When a sign falls off the warm-path (presig pool depleted, or a §06.18 invalidation trigger fired between confirmation and signing), the wallet SHOULD surface the cold-start latency penalty to the user with a reason code. Required signal fields:

```
PresigPathFallOff = {
    1: tstr,    // reason: "policy_update" | "share_refresh" | "subset_change" | "joint_pubkey_change" | "pool_empty"
    2: u32,     // new_expected_latency_ms (cold-start budget per §06.10 matrix)
    3: u32,     // previous_expected_latency_ms (warm path that was projected)
    4: bool,    // resign_required: did the user need to re-tap, or was the fall-off transparent?
}
```

When `resign_required: false`, the wallet SHOULD update the live `expected_latency_ms` field in the §15.5a confirmation surface. When `true`, the wallet MUST re-display the §15.5a surface with updated values before consuming the cold-path bundle.

This complements the §06.18 invalidation enforcement (which is wire-level mandatory). §06.18a is the user-visibility companion.

## 06.19 Burn-rate-driven regeneration

The coordinator MUST maintain a regeneration loop per `(joint_pubkey, cosigner_subset)` pair. The RECOMMENDED baseline algorithm:

```
burn_rate(t)        = EWMA over the last 60s of presig consumptions per second
target_pool_size(t) = max(8, ceil(burn_rate(t) * 30))    // 30s runway, floor 8
low_water           = ceil(target_pool_size(t) * 0.5)
high_water_cap      = target_pool_size(t) * 2
```

On each consumption (or on a 1-second tick), if `available_pool_size < low_water`, the coordinator MUST launch (`target_pool_size - available_pool_size`) presign sessions in parallel up to a maximum of `high_water_cap - available_pool_size` to bound storage. Parallel sessions MUST use independent SessionIds and independent MessageBox mailbox pairs.

Implementations MAY substitute alternative pacing algorithms. They MUST NOT exceed `high_water_cap` bundles in storage (operational cost bound) and SHOULD NOT operate below `low_water` for sustained periods (UX guarantee).

The pool MUST be observable via the operator's metrics surface (§16). At minimum, the metrics MUST include:

- `mpc.presig.pool_size{joint_pubkey, cosigner_subset}` (gauge)
- `mpc.presig.burn_rate{joint_pubkey, cosigner_subset}` (gauge, per-second)
- `mpc.presig.regen_in_flight{joint_pubkey, cosigner_subset}` (gauge)
- `mpc.presig.bundles_consumed_total{joint_pubkey, cosigner_subset}` (counter)
- `mpc.presig.bundles_invalidated_total{joint_pubkey, cosigner_subset, reason}` (counter; reason ∈ refresh|subset|policy|rekey)

## 06.20 Cosigner availability and cold-path fallback

The presig lifecycle requires cosigners to be online at TWO points:

1. **Generation** (§06.16): for the 3-round cggmp24 presign protocol.
2. **Consumption** (§06.17.3): to decrypt the cosigner's stored ciphertext at sign-time and produce a sigma share.

The coordinator MUST be online continuously (it holds the bundle pool and runs regen).

When the available pool is empty AND a cosigner is online for an immediate sign, the coordinator MUST fall back to the 4-round signing path (§06.10 "Sign without presig" budget: ~400ms p50). The fallback path SHOULD opportunistically trigger a presig backfill if pool conditions warrant.

When a cosigner is offline at sign-time, the coordinator MUST queue or reject the sign request per the wallet's configured policy (§09). The presig pool does NOT enable signing-without-cosigner-presence; it only accelerates signing-with-cosigner-presence by 3 rounds.

## 06.21 Conformance and implementation status

### 06.21.1 Conformance test vector

The byte-locked BRC-2 self-encryption vector for §06.16 lives at [`conformance/test-vectors/06-presig-bundle-encryption.json`](conformance/test-vectors/06-presig-bundle-encryption.json). The vector pins wallet identity, `presig_id`, plaintext share, and AES-GCM IV; both implementations MUST produce byte-identical ciphertexts. Negative tests cover wrong-`presig_id`, wrong-wallet, tampered-ciphertext, and per-`presig_id` key-uniqueness paths.

As of 2026-05-12 the vector is a skeleton (`__TBD__` placeholders for the ciphertext + intermediates). It will be byte-locked by the reference `rust-mpc` impl run during the M1 sprint (see ADR-0030 / partnership action items) and validated by an independent `bsv-mpc` run.

### 06.21.2 Implementation status

- **`rust-mpc` (Binary; implementor: Ishaan Lahoti):** §06.15-§06.20 fully implemented as of partnership-meeting baseline 2026-05-12. Reference modules: `crates/brc42/src/presig_encryption.rs` (encryption), `crates/brc42/src/presignature.rs` (offset application), `crates/coordinator/src/presign.rs` (orchestration). Rustdoc SHOULD cite ADR-0030.
- **`bsv-mpc` (Calhoun; implementor: John Calhoun):** §06.15-§06.20 to be implemented. Existing in-process presigning (POC results) must move to the MessageBox-mediated lifecycle per these sections.

## See also

- [`decisions/0006-federated-messagebox-with-websocket.md`](decisions/0006-federated-messagebox-with-websocket.md) — Transport ADR.
- [`decisions/0030-presig-coordinator-storage.md`](decisions/0030-presig-coordinator-storage.md) — Presignature lifecycle ADR (normative for §06.15-§06.20).
- [`05-message-envelope.md`](05-message-envelope.md) — the envelope this transport carries.
- [`09-policy.md`](09-policy.md) — policy_id binding; policy-update invalidation trigger.
- [`12-discovery.md`](12-discovery.md) — CHIP token format, including `transport` block.
- [`18-recovery.md`](18-recovery.md) — share refresh; refresh invalidation trigger.
- [`appendices/swarm-reports/A-transport.md`](appendices/swarm-reports/A-transport.md) — full design rationale.
