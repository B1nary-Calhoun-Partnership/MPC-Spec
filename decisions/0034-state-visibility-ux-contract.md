# ADR-0034: State-visibility UX contract — manifest diff + presig fall-off + recovery health

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — UI/UX F4 (recovery health) + F5 (presig / manifest visibility) + Speed F3 (cold-WS state).

## Context

Three state transitions in the wallet are invisible to the user today:

1. **Manifest rotation** (§09.9) — when `policy_id` changes for a `jointPubkey` the user transacts under, the presig pool is invalidated (§06.18) and next sign falls off the sub-second path into 4-round cold-start (~1 second over WS). The wallet has no requirement to surface that the user just transitioned.
2. **Presig pool fall-off** (§06.18) — same transition, triggered by share refresh / subset change / joint-pubkey change. Same invisibility.
3. **Recovery health** (§18) — §18.7 IR-009 runbook gives operator timestamps but no requirements on what the wallet shows at T+0 of user-panic. ZenGo-style "always-on recovery health" indicator is absent.

Plus from Speed: cold-WS handshake adds 60-150ms; user sees the penalty as "felt slow" without explanation.

## Decision

### 1. Manifest-change UX gate (§09.9a)

When `policy_id` changes for a `jointPubkey` the user transacts under, the wallet MUST surface a one-time diff before the first sign under the new manifest. Silent rollouts violate the "presig invalidation is real" guarantee.

The diff MUST include:
- Rule changes (added / removed / modified)
- Approver-quorum changes (k changes; eligible-list changes)
- Rate-limit changes
- Amount-cap changes

User MUST acknowledge before the first sign proceeds (or the wallet refuses to consume a presig under the new manifest).

### 2. Presig-path fall-off signal (§06.18a)

When a sign falls off the presig path due to invalidation, wallet SHOULD surface "cold-start (~1 sec)" vs the typical sub-RTT. Display reason: "Policy updated" / "Share refresh" / "Cosigner change" / "Joint key change" per §06.18 triggers.

This is a latency-budget UX requirement, not just an internal state-machine event.

### 3. Cold-WS handshake signal (§06.10.2 supplement)

On first-sign-of-the-day when the WS is cold, the wallet SHOULD display "warming up..." with the expected 60-150ms (broadband) or 250-600ms (cellular) penalty. After warm, subsequent signs go silent.

### 4. Recovery health indicator (§18.4a)

Wallet MUST expose `recovery_health` for all three §18 recovery paths:

```
recovery_health = {
    passkey_present: bool,                    // §18.5.1 path
    backup_synced_age_secs: u64,              // freshness of encrypted backup at BRC-100 wallet
    trustees_reachable: u8/u8,                // §18.5.2 escrow / §18.6 trustees
    last_refresh_age_days: u32,               // §16.5.1 routine refresh cadence
}
```

Always-visible (or one-tap-away from main wallet screen). Status-good (green) / status-degraded (yellow) / status-critical (red) per per-field thresholds (TBD in implementation per design choice).

### 5. `RateLimited` UX (§09.5)

`Verdict::RateLimited` returning `retry_after_secs` MUST surface a human-readable wait state ("Try again in 30 minutes"). Silent rate-limiting is non-conformant.

### 6. `Verdict::Deny` UX (per 2026-05-13 divergence-risk swarm — Q19 resolution)

When `Verdict::Deny` fires, wallet MUST display ONE OF: (a) the reason string verbatim, OR (b) a categorized code from the spec-canonical enumeration `{policy_violation, rate_limit, jurisdiction_block, signature_failure, operator_paused, manifest_mismatch, attestation_failed, unspecified}`. **Silent denial is non-conformant** — the user MUST receive some signal.

Operators choose verbatim-vs-categorized per their security-through-obscurity posture, but the choice MUST be declared in the operator's CHIP capabilities JSON as `denial_ux_mode: "verbatim" | "categorized"`. The choice is daily-CI-checked for stability (operators flipping the mode silently is itself a drift signal).

## Rationale

- **No invisible state transitions.** Every event that changes user-experienced latency or correctness MUST have a wallet-surface signal.
- **Recovery health = real product differentiator.** ZenGo's "always-on indicator" is one of their highest-rated UX features; institutional users will demand similar.
- **Manifest-diff acknowledgment closes the "stale presig under new policy" expectation gap.** Even though §06.18 invalidation is enforced cryptographically, the user-perceived "why did sign get slower?" needs answer.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Wallet SDK surfaces a `state_change` event stream (new addition; not yet in §15.4 method set).
- Manifest-change handshake added to onboarding flow.
- `recovery_health` query added to SDK (sub-method of existing surface, or 8th SDK method).

### `MPC-Spec`

- §06.18a added (presig fall-off signal).
- §09.9a added (manifest-change UX gate).
- §18.4a added (recovery health indicator).
- §15.4 implicitly extended (state_change events).
- Q19 added: Denial UX symmetry (reason verbatim vs categorized code).

## M1 dependency

**v1.5.** Not M1-blocking. Lands in M2 window.

## See also

- Spec: [§06.18a](../06-transport.md), [§09.9a](../09-policy.md), [§15.4](../15-notary-product.md), [§18.4a](../18-recovery.md)
- ADR-0030 (presig lifecycle — the invalidation events trigger UX surface)
- ADR-0031 (sign-time confirmation contract)
- Reference: ZenGo "ChillStorage" indicator UX
- 2026-05-13 swarm: UI/UX F4 + F5, Speed F3

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
