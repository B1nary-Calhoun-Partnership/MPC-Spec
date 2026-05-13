# ADR-0047: Jittered timer cadence + per-peer rate-limit on STH-pull

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 loop-2 god-tier swarm Security L2 — three unconditional unjittered timers collide on same Unix-second; WitnessCosignFailed DoS amplification unmitigated.

## Context

The spec now mandates several unconditional periodic activities:

| Cadence | Source |
|---|---|
| 30s WebSocket heartbeat | §06.12 |
| 60s witness-cosign STH exchange (post-ADR-0039) | §10.6 |
| 15-min binary re-attestation (post-ADR-0040) | §17.6 |

Loop-2 Security flagged that none of these specify jitter. At a deployment of, say, 5 cosigners across 3 operators, every multiple-of-30s wall-clock second has all heartbeats firing simultaneously. Every 60s, all witness-cosign STH exchanges fire. Every 900s, all re-attestation timers fire. Network bursts; coordinator inboxes spike; observability dashboards show synchronized blips that mask real anomalies.

Plus a related concern: ADR-0039 + §10.6 unconditional 60s witness cadence creates a `WitnessCosignFailed` event class that an attacker can amplify via spam STH-pull requests — drowning a peer in failed-witness entries. No per-peer rate-limit was specified.

## Decision

### 1. Mandatory jitter on unconditional timers (normative)

Each unconditional periodic activity MUST jitter its scheduling. Jitter parameters:

| Activity | Base period | Jitter | Method |
|---|---|---|---|
| WS heartbeat | 30s | ±5s | Random uniform on each cycle |
| Witness-cosign STH exchange | 60s | ±10s | Random uniform on each cycle |
| Binary re-attestation | 15 min | ±2 min | Random uniform on each cycle |

Jitter MUST be sampled from a CSPRNG-equivalent source (not `time(NULL) % N` or similar) so that operators running multiple cosigners cannot have correlated jitter that collapses to synchronized firing.

The jitter source MAY be deterministic per (cosigner_identity, day) for reproducibility in tests, as long as cross-cosigner schedules are de-correlated within a deployment.

### 2. Per-peer rate-limit on STH-pull (normative)

A cosigner MUST rate-limit incoming witness-cosign STH-pull requests from each peer to **≤ 1 request per 30 seconds per peer**. Excess requests:

- Return `429 Too Many Requests` (HTTP) or the message-box equivalent
- Emit a single `WitnessRequestRateLimited` audit event per minute per peer (not per request — avoids audit spam)
- Do NOT count toward `WitnessCosignFailed` against the requesting peer

The rate-limit is per-peer (keyed by requester BRC-31 pubkey), not global. A misbehaving peer is throttled; honest peers are unaffected.

### 3. WitnessCosignFailed scoring

A peer's `WitnessCosignFailed` count for a given audit period (e.g., 24h) MUST be computed:

```
failure_score = (failed_pulls × 1.0) - (rate_limited_pulls × 0.0)
```

That is: rate-limited pulls do NOT count toward the failed-witness reputation score. This closes the DoS amplification vector — an attacker spamming a peer cannot push the peer's WitnessCosignFailed count up.

### 4. Optional jitter audit event

Implementations MAY emit a `JitterScheduleEmitted` audit event documenting the scheduled wall-clock times for the upcoming N cycles. Useful for operator debugging; not security-critical.

## Rationale

- **Decorrelated timer fire times** spread network and compute load smoothly; observability dashboards show smooth curves instead of synchronized spikes that mask real anomalies.
- **Per-peer rate-limit closes the DoS amplification.** A coordinated attacker cannot game the WitnessCosignFailed metric against a target peer.
- **Backward-compatible.** Existing implementations adopting jitter add no new behavior visible to peers — peers still see STHs on a roughly-60s cadence.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Implement CSPRNG-based jitter on the three timer types.
- Implement per-peer STH-pull rate-limit (~50 LOC + state per-peer).
- Adjust audit scoring to exclude rate-limited pulls.
- ~150 LOC + tests.

### `MPC-Spec`

- §06.12 amended for jittered WS heartbeat (apply during M1 sprint as wire-compat-safe change).
- §10.6 amended for jittered witness cadence + per-peer rate-limit.
- §17.6 amended for jittered re-attestation cadence (already partially in ADR-0040 §1).
- Q34 (witness-cosign DoS) resolved by this ADR.

## Alternatives considered

- **No jitter (status quo).** Rejected per the synchronized-burst issue.
- **Operator-set jitter rather than mandatory.** Rejected — partnership deployments are mixed-operator; correlated firing is the default without mandate.
- **Global rate-limit on STH-pulls.** Rejected — punishes honest peer floods (e.g., post-incident hyper-monitoring). Per-peer is the correct scope.

## M1 dependency

**v1.5.** Not M1-critical; M1 demo doesn't exercise sustained witness-cosign or re-attest. Implementation alongside §10.6 + §17.6 work.

## See also

- §06.12 (WS heartbeat), §10.6 (witness-cosign), §17.6 (re-attestation)
- Q23 (WitnessCosignFailed DoS — resolved here), Q34 (witness-cosign DoS — also resolved)
- ADR-0039 (60s unconditional witness cadence)
- ADR-0040 (15-min re-attestation)
- 2026-05-13 loop-2 swarm Security

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
