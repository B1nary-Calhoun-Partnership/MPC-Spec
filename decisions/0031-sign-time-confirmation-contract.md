# ADR-0031: Sign-time confirmation display contract

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — UI/UX dimension F1.

## Context

§15.4 names five SDK methods (now seven per ADR-0035) but the spec says nothing about what info the wallet MUST display before the user gestures yes/no to a signing request. bsv-mpc and rust-mpc integrators will invent divergent confirmation surfaces — same protocol, two products. Reference precedent: Fireblocks Transaction Authorization Policy (TAP) display contract; Ledger "trusted display" doctrine.

## Decision

§15 adds a new §15.5a "Sign-time confirmation contract." Normative MUST list of fields the wallet displays before signing:

- `counterparty_identity` — BRC-31 pubkey + name from cert if present
- `amount_sats` + `fiat_estimate` (per Q17 fiat oracle)
- `fee_output` — the L2 P2MS fee output per §11
- `notary_id` — the Notary cosigner whose CHIP token is being consumed
- `policy_manifest_version` — current `policy_id` + "v" indicator
- `verdict` — `Allow` / `RequireApproval` / `RateLimited` from §09.5
- `expected_latency_ms` — selected from the §06.10 network-profile matrix (per ADR-0041) for the current profile + warm/cold WS state; SHOULD update live as conditions change. Replaces the older "~1s cold-start" handwave; the matrix is the canonical reference.
- `presig_path_used: bool` — surfaces the cold-start fall-off

Implementations MUST NOT auto-sign without displaying this surface unless a session policy explicitly grants `headless: true` (agent profile, see Q15).

## Rationale

- **Eliminates divergent confirmation UIs** between bsv-mpc and rust-mpc integrators.
- **Makes the cold-start UX visible** — user sees `expected_latency_ms` jump from 60ms to 1s when presig pool is empty, with the reason in `presig_path_used: false`.
- **Composes with ADR-0032 `request_view_hash`** — the displayed fields are the same fields canonicalized into the hash that approvers sign.
- **`headless: true` opt-in** preserves agent-wallet use cases (AI agents that sign autonomously per policy) without compromising the default user-protection contract.

## Consequences

### `bsv-mpc` + `rust-mpc`

- SDK `mpc.sign()` MUST display the field list OR fail with `error: confirmation_surface_required` unless `headless: true`.
- Wallet integrations adopt the contract uniformly.

### `MPC-Spec`

- §15.5a added (normative).
- Q15 (Headless/agent sign profile) added — design choice on consent-capture at onboarding.

## Alternatives considered

- **Pure SDK convention, no spec.** Rejected — divergence is the whole problem.
- **Pixel-level UI mandate.** Rejected — pixels are integrator's job. Fields are the spec's job.

## M1 dependency

**v1.5.** Not blocking M1 cross-impl signing demo (the demo is wire-compat, not UX). Land in M2 window.

## See also

- Spec: [§15.5a](../15-notary-product.md)
- ADR-0032 (`request_view_hash` — same field set canonicalized for approval)
- ADR-0035 (SDK v1.1)
- Reference: Fireblocks TAP, Ledger trusted-display doctrine
- 2026-05-13 swarm: UI/UX F1

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
