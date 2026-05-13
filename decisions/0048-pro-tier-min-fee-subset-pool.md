# ADR-0048: Pro tier minimum-fee floor + subset-aware pool sizing

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 loop-2 god-tier swarm Cost (race-to-the-bottom in Pro tier) + Speed (C(n,k) subset combinations systematically miss warm path).

## Context

§15.2.3 Pro tier ("2-of-5 multi-Notary marketplace") allows wallets to pick any 2 healthy Notaries from a pool of 5 advertised in the marketplace. Loop-2 surfaced two issues:

1. **Race to the bottom on fee.** "Wallet picks cheapest 2 healthy" creates economic pressure to underprice. Operators that cut corners on §16/§17 infrastructure (vendor diversification, IR readiness, supply-chain provenance) can underbid operators that don't. Spec has no minimum-fee floor; Pro tier could destabilize the operator economics.
2. **Subset-combinatorial pool miss.** C(5,2) = 10 subset combinations. Each subset has its own warm presig pool. Wallets that rotate subsets (e.g., for fault-tolerance testing, or for spreading load) systematically miss the warm path on each new subset combination — cold-start 4-round penalty per draw.

## Decision

### 1. Pro tier minimum-fee floor (normative)

Pro tier operators MUST declare a `min_fee_sats` field in their capabilities JSON (§12.3) that satisfies:

```
min_fee_sats ≥ ceil(fixed_monthly_cost / target_sigs_per_month)
```

The `fixed_monthly_cost` is the operator's published fully-loaded monthly cost per cosigner (per ADR-0036 §15.9.2). The `target_sigs_per_month` is the operator's published break-even volume. Operators that cannot articulate a defensible `fixed_monthly_cost` MUST NOT enter the Pro tier marketplace.

The wallet's discovery filter (`fee_sats_max` per §12.4) is bounded BELOW by the maximum advertised `min_fee_sats` across all participants in a given threshold config:

```
discovery_filter.fee_sats_max ≥ max(operator.min_fee_sats for operator in candidates)
```

If a wallet specifies `fee_sats_max` below the floor, discovery returns empty + emits a `discovery-floor-violation` warning.

### 2. Subset-aware pool sizing (RECOMMENDED for Pro tier)

For Pro tier deployments (`threshold_config = "2-of-N"` with N ≥ 5), the coordinator's presig pool MUST be sized to cover the top-K likely subset combinations rather than just the last-used subset. K is implementation-tunable:

- Default: K = 3 (cover the top-3 subsets by 30-day-frequency consumption)
- High-availability profile: K = ceil(C(N, threshold) / 2) — i.e., half the combinatorial space
- Maximum: C(N, threshold) — full coverage (only sensible for N ≤ 5)

The pool sizing formula extends ADR-0030's §06.19:

```
pool_size = sum over top-K subsets of: max(8, burn_rate_per_subset × 30)
```

Pool depth per-subset metric is exposed via §16.3 SLI `presig.subset_pool_depth{subset_id}`.

### 3. Subset rotation policy

Pro tier wallets SHOULD rotate subsets across signings to spread load and surface latent operator issues (a malfunctioning operator that's always-cold-pathed). Recommended rotation:

- Round-robin across the top-K warm subsets (deterministic)
- Random selection weighted by `1 - subset_recent_consumption_rate` (load balancing)
- Bias toward less-recently-used subsets to surface latent operator issues

Wallets MUST NOT pin to a single subset for >24h continuously (forces rotation discipline).

## Rationale

- **Min-fee floor protects honest operators.** Race-to-the-bottom undermines the security-investment incentive that the partnership's whole moat (3-4 OOM cheaper at scale) is supposed to enable. Without a floor, operators that cut SOC2 / IR / supply-chain corners win on price.
- **Subset-aware pool sizing closes the cold-path-on-each-draw vector.** Pre-warming the top-K subsets keeps warm-path-hit-rate ≥0.95 (§16.3 SLI) even with rotation.
- **Bounded combinatorial cost.** K is tunable; pool storage scales linearly with K, not combinatorially.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Implement `min_fee_sats` declaration in capabilities JSON emission.
- Implement subset-aware pool sizing in coordinator (ADR-0030 extension).
- Add `presig.subset_pool_depth{subset_id}` metric.
- Wallet-side: implement subset rotation policy (round-robin + load-balanced).
- ~300 LOC across both stacks.

### `MPC-Spec`

- §12.3 capabilities JSON adds `min_fee_sats` + `fixed_monthly_cost` + `target_sigs_per_month` fields (operator transparency).
- §06.19 pool-sizing extends to Pro tier per this ADR.
- §15.2.3 Pro tier text updated to reference this floor.
- §16.3 new SLI `presig.subset_pool_depth`.

## Alternatives considered

- **No floor; let market dynamics work.** Rejected per the security-investment-undermining argument.
- **Min-fee fixed at protocol level (e.g., 333 sats).** Rejected — too inflexible; operators in low-cost regions can offer less.
- **Subset-aware pool sizing as MUST, not RECOMMENDED.** Considered, but Default tier doesn't need this; only Pro tier (N ≥ 5) does. Keeping RECOMMENDED for Default + MUST for Pro tier.

## M1 dependency

**v2** (Pro tier itself is v3 per ROADMAP; this ADR is forward-prep for the marketplace). Not M1 critical.

## See also

- §15.2.3 (Pro tier definition)
- §06.19 (burn-rate regen — extended here)
- ADR-0030 (presig lifecycle)
- ADR-0041 (warm-path SLI)
- 2026-05-13 loop-2 swarm Cost + Speed

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
