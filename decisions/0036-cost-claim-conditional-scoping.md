# ADR-0036: Cost-claim conditional scoping + customer-facing disclosure obligation

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Cost dimension F1 + Quality dimension G1 converged on this gap.

## Context

PROPOSAL.md §2 and §15.9 stated "3-4 OOM cheaper than Fireblocks" without scenario qualification. The underlying math — `333 sats × 3 nodes × $50/BSV = $0.0002/sig` — is the **marginal BSV fee only**. It excludes:

- Cosigner compute (CPU, memory, storage)
- MessageBox transport (CF Worker requests, Durable Object compute, WebSocket hours)
- STH PushDrop chain (ADR-0019, ~$0.40/yr/cosigner)
- 30-day refresh ceremony cost
- Presig pool storage at coordinator (ADR-0030)
- KMS / secrets management
- Supply-chain pipeline (Sigstore + cosign + Rekor; v1 ~$0; private CI $50/mo)
- Incident response staffing
- TEE/HSM (v2 only)

Pressure-tested across 6 deployment scenarios, the moat varies from **3-5 OOM (mobile consumer, AI-agent burst, multi-tenant marketplace)** through **1-2 OOM (cold-storage, regulated institutional)** to **inverted (self-hosted single-cosigner at <50 sigs/mo)**. An unconditional "3-4 OOM" headline is misleading at the low-volume / regulated end.

In parallel, the Quality swarm flagged that ADR-0016's explicit v1 deferral of TEE/HSM creates a regulated-customer-disclosure obligation that the spec did not codify. Marketing the v1 stack to NYDFS / MiCA / OCC tier-1 custody customers without disclosing the deferral would be non-conformant.

## Decision

### Cost-claim scoping (normative)

The "3-4 OOM cheaper than Fireblocks" claim MUST be scoped to **sustained ≥1M signatures per month aggregate volume**. Below that volume:

- 100K–1M sigs/mo: 2-3 OOM
- 10K–100K sigs/mo (regulated institutional): ~1 OOM
- <10K sigs/mo: <1 OOM, can invert below ~50 sigs/mo self-hosted

PROPOSAL.md §2 and §15.9 are updated to expose the per-scenario table. Operator-facing material that cites the moat figure MUST include the scenario context.

### Customer-facing disclosure obligation (normative)

Operators marketing the v1 stack to:
- NYDFS Part 500 -licensed entities
- MiCA Art.75 CASP custody customers
- OCC trust-charter applicants
- Anyone subject to SOC2 Type II strict scope on key-material control

MUST disclose ADR-0016 deferrals (no v1 TEE, no v1 HSM cold tier) in their customer-facing security documentation BEFORE onboarding the customer. The disclosure MUST cite the v2 institutional-tier roadmap as the upgrade path.

This obligation does NOT apply to:
- MSB-licensed fintech treasury (signing own keys, not custodying customer keys)
- Web2.5 self-custody products where the user accepts the v1 posture per onboarding
- AI-agent / x402 paid-signing at sub-cent value (§15.2.2 Express tier)

The customer-onboarding doc MUST include a "shared-responsibility model" diagram referencing the §17.14 vendor matrix (added by ADR-0042).

### Cost regimes (informative)

§11.3 adds §11.3.1 distinguishing:
- **Marginal BSV fee** ($0.0002, defensible at any volume)
- **Fully-loaded amortized** ($0.0003 – $15, scenario-dependent)

The economic-model table in §15.9.2 enumerates 6 scenarios with both Calhoun-stack and Fireblocks-equivalent loaded cost.

## Rationale

- **Honest moat marketing.** The "3-4 OOM" headline is true at high volume and false at low volume / regulated tiers. Unconditional usage hurts long-term credibility when an institutional buyer's CFO does the math.
- **Regulatory protection.** Operators that conceal v1 stack limitations in marketing materials risk customer-deception claims under NYDFS §500.17 (CISO certification), FTC Act §5, and EU MiCA Art.84 (transparent + non-misleading marketing).
- **Cost-component visibility.** The fully-loaded breakdown lets operators size their own break-even (§15.2.1 "do not self-host below N sigs/mo" implied by the math).
- **Doesn't weaken the actual product.** At the high-volume case the moat IS structural — Fireblocks can't follow without giving up its compliance product. The scoping just stops over-claiming at the low-volume edge.

## Consequences

### `MPC-Spec`

- PROPOSAL §2 updated with scenario table.
- §15.9 expanded to §15.9.1 (marginal), §15.9.2 (fully-loaded by scenario), §15.9.3 (scoped claim), §15.9.4 (disclosure obligation).
- §15.2.1 adds break-even guidance (~100K sigs/mo per cosigner instance to amortize CF Worker cost below 1000 sat fee).
- §15.2.3 Pro tier notes that 2-of-5 marketplace multiplies fixed cost ~67% over Default.
- §16.1.1 added (disclosure obligation, normative).

### Calhoun + Binary operations

- Marketing materials (website, decks, partnerships docs) MUST cite the per-scenario context when referencing the moat.
- Customer onboarding (when v1 stack is sold to regulated customers) MUST include the disclosure paragraph.
- No code change required.

## Alternatives considered

- **Keep unconditional moat claim.** Rejected — unsustainable when buyer's CFO does the math.
- **Drop the moat claim entirely.** Rejected — the high-volume moat IS the product thesis; soft-pedaling it gives up the wedge.
- **Disclose only at v2 institutional launch.** Rejected — v1 operators are already onboarding fintech customers; the deferral matters to them now.

## Status of M1 dependency

**M1 (markdown-only).** Customer-facing disclosure obligation can land in spec by 2026-05-29 with zero code lift. Operator marketing materials updated in same window.

## See also

- Spec: [PROPOSAL §2](../PROPOSAL.md), [§11.3.1](../11-fees.md), [§15.9](../15-notary-product.md), [§16.1.1](../16-operations.md)
- ADR-0016 (TEE/HSM deferral)
- ADR-0042 (vendor matrix; customer-onboarding doc reference)
- 2026-05-13 swarm: Cost F1, Quality G1

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
