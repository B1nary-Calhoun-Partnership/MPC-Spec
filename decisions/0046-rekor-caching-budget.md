# ADR-0046: Rekor caching budget + transient-failure distinction

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 loop-2 god-tier swarm Speed L2 (Rekor cost) + Self-Critique #2 (transient-vs-permanent failure).

## Context

ADR-0040's runtime self-attestation fetches a Rekor entry on every 15-minute timer AND on every 1000-sig presig consumption trigger. Two issues surfaced by loop-2:

1. **Latency cost.** Rekor fetch + OIDC verify + materials-chain verify = 200-1500ms. At 10 sigs/sec sustained, the per-1000-sigs trigger fires every 100s, gating sigma emission. §06.10 signing budgets don't account for this. The §16.3 `signing.latency.p99 ≤ 250ms` target is breakable by Rekor's own p99.

2. **Failure-mode collapse.** ADR-0040's original text said "Re-verify failure MUST trip presig invalidation." It conflated proven mismatch (real attack) with transient lookup failure (Rekor outage). A Sigstore Rekor outage during a high-burn period would invalidate the entire pool, breaking ADR-0041's warm-path SLI for the duration of the outage.

This ADR establishes a caching policy that bounds latency cost AND distinguishes failure modes.

## Decision

### 1. Cached Rekor verification

After a successful Rekor verification, the result is cached with the following parameters:

- **Cache validity window: 24 hours.** Within this window, subsequent re-verify calls use the cached `(binary_measurement, oidc_identity, materials_chain_state)` triple without re-fetching from Rekor.
- **Cache invalidated on**: binary measurement change (per ADR-0045), elapsed 24h, or explicit operator-initiated cache flush (e.g., post-CVE disclosure).

### 2. Failure-mode distinction

Failure handling diverges:

| Failure | Action | Severity |
|---|---|---|
| **Proven mismatch** (measurement ≠ reference AND Rekor confirms reference) | Trip presig invalidation per §06.18, emit `BinaryReverifyFailed`, refuse further sigma emission | Sev-1 |
| **Cached value valid; no fetch needed** | Continue normally; emit `BinaryReverifyCacheHit` audit event (informational) | n/a |
| **Cache expired AND Rekor unreachable (transient)** | Continue with last-known-good cached state for grace window (default 6h); emit `BinaryReverifyDeferred`; escalate to Sev-3 if outage persists past grace | Sev-3 initially; Sev-2 at 6h; Sev-1 at 24h |
| **Cache expired AND Rekor returns 404** (proven revocation) | Trip presig invalidation immediately | Sev-1 |
| **Cache expired AND Rekor returns "revoked" annotation** | Trip presig invalidation; binary is forbidden | Sev-1 |
| **OIDC identity verifier unreachable** | Same as Rekor transient failure (Sev-3 → 2 → 1 escalation) | Sev-3 / 2 / 1 |

### 3. Pre-consumption hot-path optimization

For presig consumption (the per-1000-sigs trigger from ADR-0040):

- If the cache is hit and the cached result is `valid_within_24h`: emit immediately, no Rekor fetch. Adds ~5µs (cache lookup).
- If the cache is in grace window post-expiry but `last_known_good`: emit immediately with deferred audit event. Adds ~5µs.
- If the cache requires a fresh fetch: queue an async pre-fetch (don't block sigma emission); use cached result for the current emission. Sigma emission tolerates one extra burn against a possibly-stale-but-not-revoked binary.

Net: per-consumption Rekor cost is ~5µs hot-path + ~200-1500ms amortized once per 24h.

## Rationale

- **Latency budget protected.** ADR-0041's warm-path SLI holds with cached-result hot path.
- **Outage tolerance.** Sigstore Rekor SLA is not 100%; a 24-hour grace window absorbs reasonable outages without invalidating the entire presig pool.
- **Security preserved.** Cache invalidation on binary-measurement-change catches the threat-model gap (live exploit modifies memory → measurement diverges → cache invalidated → fresh Rekor fetch). Proven mismatch is still Sev-1.
- **Revocation honored.** Explicit Rekor revocation (404 or `revoked` annotation) bypasses the cache.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Implement cache layer between binary-measurement (ADR-0045) and Rekor lookup.
- Cache MUST be at-rest-encrypted (shares the AES-256-GCM with BRC-42-derived key pattern from §16.1).
- Add `BinaryReverifyCacheHit` / `BinaryReverifyDeferred` audit event kinds.
- ~150 LOC of caching logic.

### `MPC-Spec`

- ADR-0040 §1b references ADR-0046 for transient-failure handling (text already applied per loop-2 fix).
- §16.3 SLI `audit.cache_hit_rate` (new): RECOMMENDED target ≥ 0.99 for binary re-verify (cache should hit on nearly all consumption-time checks).

## Alternatives considered

- **No cache (Rekor every re-verify).** Rejected — latency cost.
- **Infinite cache (only invalidate on measurement change).** Rejected — misses Rekor revocation.
- **Shorter cache TTL (e.g., 1h).** Considered, but adds Rekor load without security benefit. 24h matches Rekor's own staleness expectations.

## M1 dependency

**v1.5** (alongside ADR-0040 + ADR-0045 implementation). Not M1-critical.

## See also

- ADR-0040 (continuous runtime self-attestation)
- ADR-0045 (mapped-memory binary measurement)
- ADR-0017 (Sigstore Rekor anchoring — the underlying primitive)
- 2026-05-13 loop-2 swarm Speed + Self-Critique

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
