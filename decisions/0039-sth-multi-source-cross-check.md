# ADR-0039: Verifier-side STH multi-source cross-check + 60s unconditional witness cadence

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Security S3 (audit-chain eclipse).

## Context

§10.5 PushDrop STH chain anchors STHs as a chain of single-input/single-output PushDrop spends on overlay topic `tm_mpc_audit`. The chain's tamper-evidence assumes verifiers can find the chain tip.

A network attacker — ISP-level MITM, hostile overlay tracker, BRC-22 lookup-host compromise, or a malicious MessageBox in the verifier's BRC-31 path (§07.5) — can return a **stale tip** to the verifier: older than the cosigner's actual current STH, but still validly signed by the audit identity. The cosigner is honest; the verifier is fed a consistent-but-frozen past.

Witness-cosigning (§10.6) detects retroactive **rewrite** (cosigner #2 can't shrink tree_size that #3 has previously witnessed) but does NOT detect **withholding from a specific verifier**. If the attacker only feeds stale tips to verifier-X while serving fresh tips to #2 and #3, witness-cosigning between cosigners proceeds normally while verifier-X is selectively eclipsed.

Selective service of `tm_mpc_certs_v1` STHs is the equivalent attack on the cert-rotation chain.

## Decision

### 1. Multi-source STH lookup at verification time (normative)

A verifier (per §10.5.7) MUST, BEFORE acting on any cosigner-claimed-current STH:

**Step 0:** Fetch the cosigner's latest STH tip from **at least two independent BRC-22 lookup hosts**. The hosts MUST satisfy:

- Distinct operators (different `inbox_url` domains per §06.7 federation)
- Distinct network paths (different ASNs where verifiable; SHOULD pin via well-known third-party reachability checks)
- At least one host SHOULD be operated by the verifier's own infrastructure where possible

AND cross-check against any STH the verifier itself has directly witnessed from the target cosigner in the prior 5 minutes (via §10.6 witness-cosign exchange or direct §06 envelope receipt).

**Disagreement** among these sources (different tree_size or different root_hash for the same audit_identity at approximately the same wall-clock) MUST:
- Raise an `audit-anomaly` event published to `tm_mpc_audit`
- Refuse signature acceptance from the target cosigner until reconciled
- Trigger IR-006 (audit-chain censorship / eclipse) per ADR-0042 §16.5.6

### 2. Unconditional 60-second witness cadence (normative)

Cosigners MUST exchange STHs on a **60-second schedule independent of ceremony activity** (in addition to per-ceremony exchanges per §10.6). The unconditional cadence ensures that a verifier-side eclipse remains detectable from the cosigner side even during low-ceremony periods. A cosigner that fails to participate in the 60-second exchange triggers a `WitnessCosignFailed` event in its peers' logs.

### 3. Verifier reconciliation procedure

When STH sources disagree, the verifier MUST attempt reconciliation in this order:

1. Query additional independent BRC-22 hosts (≥3 total sources).
2. Direct cosigner-to-verifier WS query (§06.5) for the cosigner's current STH.
3. Cross-check against the most-recent STH the verifier has directly witnessed.
4. If reconciliation fails after 2 minutes, escalate to IR-006 and refuse signature acceptance from the target cosigner for the next 24 hours.

## Rationale

- **UTXO-consensus alone isn't enough.** PushDrop chain integrity assumes verifiers see the actual tip, not a withheld older tip. Eclipse attacks operate at the lookup-service layer, below consensus.
- **Multi-source defeats single-host MITM.** Any single attacker controlling a single BRC-22 host fails when the verifier queries a second host.
- **Direct verifier-witness gives ground truth.** If the verifier has its own witness history, it's not dependent on third parties for that history.
- **60s cadence gives unconditional fresh signal.** Without it, an attacker that pins low-ceremony periods (overnight, off-cycle) has a long window to feed stale tips.
- **Audit-anomaly publish is the failsafe.** Even if reconciliation fails, the discrepancy is publicly visible to peer cosigners + operators, who can investigate via IR-006.

## Consequences

### `bsv-mpc` (Calhoun)

- Add multi-source STH lookup to verifier path (`crates/bsv-mpc-overlay/src/sth_verify.rs` or new module).
- Implement 60s witness-cosign timer independent of ceremony triggers.
- Add `audit-anomaly` event emission on disagreement.
- ~300 LOC + tests covering disagreement scenarios.

### `rust-mpc` (Binary; impl Ishaan)

- Same multi-source verifier behavior.
- Same 60s witness cadence.
- Coordinate with Binary's audit-overlay implementation.

### `MPC-Spec`

- §10.5.7 step 0 added (already applied).
- §10.6 cadence tightened to 60s unconditional (already applied).
- IR-006 (audit-chain censorship / eclipse) added to §16.5.6 (ADR-0042).
- Q30 added: Multi-source STH lookup trust model — should the spec mandate one host operated by the verifier's own infrastructure?

## Alternatives considered

- **Trust a single BRC-22 host.** Status quo; rejected because of the eclipse vector demonstrated.
- **Cosigner-side push of STHs to all known verifiers.** Doesn't scale; verifier set is open. Rejected.
- **Block-by-block on-chain confirmation polling (instead of UTXO lookup).** Higher latency, doesn't change the lookup trust model. Rejected as not improving the security property.
- **Witness-cosign on every signing ceremony only (status quo §10.6).** Rejected per the eclipse-during-low-activity vector.

## Status of M1 dependency

**v1.5.** STH multi-source isn't a wire-compat blocker for M1 demo signing. Audit chain is published and verified post-sign; correctness of single-sign signature is unaffected. Spec edit lands in M2 window; implementation pre-Notary-MVP.

## See also

- Spec: [§10.5.7](../10-audit.md), [§10.6](../10-audit.md)
- ADR-0019 (PushDrop STH chain)
- ADR-0042 (IR-006 runbook)
- 2026-05-13 swarm: Security S3

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
