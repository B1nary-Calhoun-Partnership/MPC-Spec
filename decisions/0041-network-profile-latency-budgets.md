# ADR-0041: Network-profile-conditioned latency budgets + Paillier safe-prime pool + WS pre-warm

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Speed dimension F1+F2+F3 converged.

## Context

§06.10 originally specified a single-row latency budget conditioned on "50ms inter-party RTT." The Speed-dimension swarm identified three structural budget errors:

1. **§06.10 missing mobile-cellular row.** Sign-without-presig over 150ms/500ms cellular is ~2.0s p50 / ~3.0s p99, well above the 400ms / 1.5s budget. Notary product (§15) targets users on mobile; budget should reflect.
2. **Auxinfo is compute-bound, not wire-bound.** Paillier 2048-bit safe-prime keygen takes 1-3s on desktop / 5-15s on ARM mobile. Add ~64KB `paillier-blum` + ~32KB Pedersen `prm` ZK proofs per round. Mobile p99 is ~30s vs the current 5s budget — **the single biggest budget error.**
3. **Sign-with-presig "~50ms warm path" assumes pre-warmed WS.** Socket.IO/EngineIO cold handshake adds 60-150ms broadband / 250-600ms cellular. ADR-0030's headline only holds with a wallet-open WS warm; first-sign-of-the-day on a cold WS is closer to 250-400ms.

Additionally, presig pool sizing (§06.19) has no warm-path-hit-rate SLI; Pro tier's C(10,2)=45 subset combinations systematically miss the warm path on each new subset draw.

## Decision

### 1. Replace §06.10 single-row table with network-profile matrix

Profiles: LAN 10ms / Same-region 50ms (canonical) / Cross-region 250ms / Mobile 150-500ms. Per-profile p50 + p99 for: DKG keygen + auxinfo, Presign, Sign-with-presig (warm-WS), Sign-with-presig (cold-WS additive penalty), Sign-without-presig, ECDH partial, Burn-rate regen, Refresh ceremony, Audit STH publish.

Auxinfo p99 on `profile-mobile` is **33 seconds** (compute-dominated), with a normative footnote requiring background-queue offload of Paillier safe-prime generation.

The matrix lives in §06.10 spec text (already applied per this swarm's clear-win pass).

### 2. Paillier safe-prime pool (RECOMMENDED)

Implementations SHOULD maintain an at-rest-encrypted pool of pre-generated 2048-bit Paillier safe-prime keypairs, consumed by auxinfo and refresh ceremonies:

- Floor: 2 keypairs per profile
- Regenerated at idle (when CPU is otherwise unused)
- Pool drain triggers a backfill task
- At-rest encryption via §16.1 share-encryption pattern (AES-256-GCM with BRC-42-derived key)

This converts the auxinfo p99 mobile budget from 33s to ~6s — a 5-6× speedup for the dominant compute term.

§06.10.1 normative text added.

### 3. WebSocket pre-warm at wallet-open (RECOMMENDED)

The WS connection SHOULD be brought up at wallet-open (or app-resume), not at sign-time. Heart-beat aggressively (15s on mobile to survive carrier NAT timeouts).

Combined with a `signing_intent` signal (proposed predictive presig regen — see CHANGES-PROPOSED.md for the design choice on whether to add this as a protocol primitive), the warm WS + warm presig pool keep the first-sign-of-the-day on the sub-RTT warm path.

§06.10.2 normative text added.

### 4. Warm-path-hit-rate SLI

Add to §16.3 SLI catalog: `presig.warm_path_hit_rate ≥ 0.95` for `profile-server` and `profile-edge` Notaries.

Pro tier (§15.2.3, C(n,k) subset marketplace) — see CHANGES-PROPOSED.md for the design choice on whether to require pre-warming per subset combination.

### 5. Sign-intent predictive regen (RECOMMENDED, see CHANGES-PROPOSED)

A `signing_intent` signal at wallet "intent to sign" (user tap on Send, before final approve gesture) primes the pool ahead of the EWMA-reactive trigger. Drives warm-hit-rate from ~80% (EWMA) to ~99% (intent-anticipatory).

This is the only protocol-shape change in this ADR; left as a design choice for user steering.

## Rationale

- **Mobile is a first-class deployment.** Notary product targets consumer wallets; mobile cosigner is the dominant case. Budget understatement misleads operators about real user experience.
- **Compute vs wire is the diagnostic.** The single-row budget conflated them. Separating profiles clarifies where to optimize (LAN: wire; cellular: wire+compute; mobile: compute dominates).
- **Paillier pool is the highest-leverage v1 optimization.** Pure local change. 5-6× speedup on mobile DKG with no protocol change.
- **WS pre-warm is free.** Open the WS at wallet-launch, heartbeat it. Costs nothing operationally; saves 60-150ms per first-sign UX.

## Consequences

### `bsv-mpc` (Calhoun)

- Implement Paillier safe-prime pool (at-rest-encrypted, ~2-keypair floor, idle regen). Likely `crates/bsv-mpc-core/src/paillier_pool.rs` (new).
- Implement WS pre-warm hook in `bsv-mpc-service` startup.
- Add `presig.warm_path_hit_rate` metric to §16.4 OTel spans.
- ~200-300 LOC + tests.

### `rust-mpc` (Binary; impl Ishaan)

- Same Paillier pool addition in `crates/cggmp24-glue` or equivalent location.
- Same WS pre-warm in messagebox-client startup.
- Same OTel metric.

### `MPC-Spec`

- §06.10 matrix + §06.10.1 Paillier pool + §06.10.2 WS pre-warm (already applied).
- §16.3 SLI catalog adds `presig.warm_path_hit_rate`.
- Q36-Q41 OPEN-QUESTIONS added (auxinfo compute measurement per profile; Pro-tier pool warming; DKG split for mobile; STH publish for TOFU; iroh activation criterion; pool-depth drift alarm).

## Alternatives considered

- **Smaller Paillier modulus.** Would violate cggmp24 security parameters (2048 is the standard); rejected.
- **DKG split (online keygen + deferred aux).** Tempting UX win on mobile but requires sign-time fallback if user signs before aux completes. Deferred to CHANGES-PROPOSED for steering (Q38).
- **Iroh QUIC fast-path now.** §06.6 reserves iroh for v2; current v1 fix is sufficient without protocol-substrate change.

## Status of M1 dependency

**M1 (matrix only).** §06.10 budget matrix lands in spec by 2026-05-29 (markdown). Paillier pool + WS pre-warm are v1.5 implementation work (target M2 / 2026-06-12). Warm-path SLI is M2.

## See also

- Spec: [§06.10](../06-transport.md), [§06.10.1](../06-transport.md), [§06.10.2](../06-transport.md), [§16.3](../16-operations.md)
- ADR-0030 (presig lifecycle; warm-path enabler)
- 2026-05-13 swarm: Speed F1+F2+F3
- Reference: CGGMP'24 paper (auxinfo proof sizes); LFDT-Lockness cggmp21 benchmarks; OpenSSL `genrsa` reference timings

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
