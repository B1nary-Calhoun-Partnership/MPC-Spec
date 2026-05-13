# ADR-0033: Discovery result display contract

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — UI/UX dimension F3.

## Context

§12.5 defines a Notary reputation score formula (0.40 successful_proofs + 0.20 CHIP age + 0.25 abort rate + 0.15 fee competitiveness). §15.7 enumerates seven trust-on-first-use checks. But the spec never says the wallet MUST display these signals to the user. §15.5 says "wallet auto-picks #1 by reputation × cheapest" — which hides every trust signal the spec worked to construct.

Real consumer-vendor-marketplace UX (Booking.com, Uber, Doordash) surfaces trust signals explicitly: rating + count + recency + price + verified-badge. A signing-Notary marketplace needs the same discipline.

## Decision

§12.5 adds §12.5a "Discovery display contract." For every result row returned by `mpc.discover(filter)`, the wallet MUST surface to the user:

- `fee_sats` — Notary's per-signing fee
- `fee_fiat_estimate` — converted to user locale (Q17 fiat oracle dependency)
- `chip_age_days` — Notary's on-chain age
- `abort_rate_30d` — recent abort rate
- `successful_settlements_30d` — recent successful signings (volume signal)
- `jurisdiction` — operator's claimed jurisdiction
- `support_url` — operator's support contact
- `tofu_checks: [pass/fail × 7]` — the seven §15.7 checks individually pass/failed

Implementations SHOULD NOT collapse to "auto-picked"; the `mpc.discover()` result MUST be a structured list. Auto-pick MAY be exposed as a convenience but MUST be opt-in per session.

## Rationale

- **Exposes the vendor-neutrality story.** Hiding trust signals hides the differentiator from Fireblocks.
- **Forces operator transparency.** Operators that don't fill `support_url` / `jurisdiction` look worse in the comparison; market pressure for honesty.
- **Composes with reputation scoring.** Surface gives the user the same signals the auto-pick algorithm uses; reduces opaque-AI feeling.

## Consequences

### `bsv-mpc` + `rust-mpc`

- `mpc.discover()` returns structured rows, not opaque handles.
- Reference UI (in §15 SDK example) shows the field list.

### `MPC-Spec`

- §12.5a added (normative).
- Q17 added: fiat estimate oracle — where + staleness bound?
- Q20 added: Notary incident transparency — should past-incident records be required surfacable?

## Status of M1 dependency

**v1.5.** Not M1-blocking. Lands in M2 window pre-Notary-MVP.

## See also

- Spec: [§12.5a](../12-discovery.md), [§15.5](../15-notary-product.md), [§15.7](../15-notary-product.md)
- 2026-05-13 swarm: UI/UX F3

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
