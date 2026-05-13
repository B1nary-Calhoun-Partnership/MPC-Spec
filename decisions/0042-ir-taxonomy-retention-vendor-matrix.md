# ADR-0042: IR taxonomy + IR-003..IR-008 runbooks + retention/legal-hold + vendor matrix

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Quality dimension G2 (IR coverage), G3 (retention/legal-hold), G4 (vendor concentration) consolidated. Auditor's view: SOC2 CC7.3 + NYDFS §500.16 + DORA Art.28 all required.

## Context

§16.5 originally specified two runbooks: RR-001 (routine 30-day refresh) and IR-002 (suspected-cosigner-compromise). One threat actor (rogue cosigner). The Quality-dimension swarm flagged that this is insufficient for institutional onboarding — a Big-4 SOC2 auditor would mark the IR coverage as "incident classification matrix incomplete."

Missing runbook coverage:

- IR-003 Coordinator compromise (post-ADR-0030 the coordinator holds the presig pool)
- IR-004 MessageBox / relay compromise (§06)
- IR-005 Certifier-key compromise (root-of-trust)
- IR-006 Audit-chain censorship / eclipse (closed by ADR-0039 detection; needs runbook)
- IR-007 Policy-manifest poisoning (§09)
- IR-008 Presig-pool poisoning (newly relevant after ADR-0030)

Additionally:
- No severity taxonomy. Sev-1/2/3/4 mentioned in §16.5.2 / §16.12 but never enumerated.
- §10 silent on audit-log retention period, legal-hold, right-to-erasure (GDPR Art.17 vs immutable on-chain anchoring tension).
- No vendor-risk register. The v1 stack chains CF Workers, Sigstore, GitHub Actions, cggmp24 LFDT, BSV miners, Iroh — diversification is SHOULD, institutional audit needs MUST + explicit matrix.

## Decision

This is a **multi-part operational ADR** addressing three convergent gaps. Each part is normative.

### Part A: IR runbook expansion (§16.5.3 – §16.5.9)

Add six new runbook stubs (with T+0 / T+5m / T+15m / T+30m structure where applicable; longer cadence for cross-operator coordination cases). Full runbook text to land in spec PR alongside this ADR sign-off; stubs are normative now per §16.5 (clear-win pass applied):

- **§16.5.3 IR-003 — Coordinator compromise.** Detection: coordinator state-machine anomalies, presig bundle deletions outside §06.18 triggers, audit-log writes that don't witness-cosign. Response: quarantine + secondary coordinator activation + Sev-1.
- **§16.5.4 IR-004 — MessageBox / relay compromise.** Detection: BRC-31 sig failures spiking on a single relay, envelope-loss patterns. Response: relay failover (§06.7 federation), revoke CHIP token, audit-anomaly publish, Sev-2. Per §06.2 layering this is NOT ceremony-abort.
- **§16.5.5 IR-005 — Certifier-key compromise.** Detection: unauthorized BRC-52⊕ cert issuance, Sigstore Rekor anomaly. Response: root cert revocation (BRC-22 `tm_mpc_revocations`), successor-root issuance, force-refresh across all cosigners. Sev-1. T+0 / T+1h / T+24h / T+72h escalation (slow because cross-operator).
- **§16.5.6 IR-006 — Audit-chain censorship / eclipse.** Detection: multi-source STH disagreement (per ADR-0039), witness-cosign failure spike. Response: failover BRC-22 host, force witness cadence to 10s, customer notification, audit-anomaly publish. Sev-2.
- **§16.5.7 IR-007 — Policy-manifest poisoning.** Detection: PolicyManifest hash mismatch (BRC-52⊕ `policy_hash` vs locally-fetched), approver-quorum signature failures. Response: refuse-to-load, fall back to prior version, separate-channel alert to approvers. Sev-2.
- **§16.5.8 IR-008 — Presig-pool poisoning.** Detection: presig consumption produces sigs that don't verify, cosigner-encrypted blobs fail BRC-2 decrypt. Response: atomic pool deletion per §06.18, force-refresh of all bundles, regen from clean slate. Sev-1 (any bad sig that broadcasts is unrecoverable).

### Part B: Severity classification matrix (§16.5.9)

Sev-1 / Sev-2 / Sev-3 / Sev-4 trigger taxonomy (already in §16.5.9 per clear-win pass). Maps to PagerDuty / Opsgenie tiers. Sev-1 covers key-material compromise + quorum loss + audit-rewrite. Sev-2 covers single-cosigner compromise + coordinator anomaly + relay failure. Sev-3 covers pool-depth degradation + missed-refresh. Sev-4 covers SLI breach + vendor-status changes.

### Part C: Audit-log retention + legal hold (§16.14)

- **Local Merkle leaves retained ≥5 years** to satisfy NYDFS §500.06 + MiCA Art.68 + SOC2 CC7.2.
- **Legal-hold flag** freezes pruning of in-scope records. Per-customer legal-hold + per-record legal-hold both supported.
- **Right-to-erasure (GDPR Art.17)** handled by tombstone-with-hash, NEVER leaf-deletion — preserves Merkle root + audit-chain integrity. The hashed-not-personal-data legal posture is documented in Q47 as the v2 legal-review decision.
- **PII forbidden in `request_hash` preimage** — only hashes of customer identifiers may be included.

### Part D: SLA framework (§16.15)

- §16.3 SLIs already define **SLO** (operator targets). §16.15 adds **SLA** (contractual customer-facing targets) for institutional-tier deployments.
- For multi-operator deployments: joint SLA = quorum-fault-tolerant minimum of individual operator SLAs. Implementations MAY expose this via `sla.compose()` (informative).
- Error-budget burn-rate alerts MUST be surfaced as the third column in operator dashboards.

### Part E: Vendor / SPOF matrix (§17.14)

Already added per clear-win pass. Enumerates every external trust anchor with failure mode + mitigation owner + diversification status. Forms the basis of the §16.1.1 customer-onboarding "shared-responsibility model" diagram (ADR-0036 dependency).

### Part F: Audit retrieval API (§10.12)

`GET /audit/entry/{leaf_index}` returns leaf + inclusion proof + STH chain pointer within 5s p99. Required of any cosigner participating in a multi-party deployment. Forensic-request friendly.

### Part G: Operator-bridge IR coordination (§13.15)

RACI matrix for who is accountable / consulted on each IR class across the partnership. Calhoun and Mitch are jointly Responsible for cross-operator IR-005 (certifier key); Calhoun is Responsible for IR-004 (rust-message-box) with Mitch Consulted; Ishaan is Responsible for IR-004 on Binary side, etc.

## Rationale

- **Coverage matches reality.** Post-ADR-0030 the coordinator is a state holder; IR-003 + IR-008 are now first-order classes. Pre-ADR-0030 they were less important.
- **Severity taxonomy is a SOC2 prerequisite.** CC7.3 requires explicit incident-severity criteria. Without the matrix, every incident is ad-hoc; auditors flag.
- **Retention closes a regulatory hole.** Without a 5-year retention claim, NYDFS Part 500 + MiCA Art.68 onboarding is blocked.
- **Vendor matrix is institutional-onboarding table stakes.** DORA Art.28 (EU) + NYDFS §500.11 (NY) require third-party-risk documentation. Spec-level matrix gives operators a starting point.
- **SLA framework lets institutional ops sell** with confidence — joint SLA composition makes the multi-operator-quorum value proposition explicit.

## Consequences

### Calhoun + Binary operations

- Operator on-call rotations expand to cover IR-003..IR-008 (existing IR-002 rotation is the baseline).
- Quarterly DR drill (per §18.11) required — output is a signed attestation usable as SOC2 evidence.
- Vendor-risk register maintained at `~/bsv/mpc/MPC-Spec/decisions/vendor-matrix.md` (or §17.14 in-spec).

### `bsv-mpc` (Calhoun) + `rust-mpc` (Binary)

- Implement audit-log local Merkle retention with 5-year purge policy (configurable down to regulatory minimum per deployment).
- Implement legal-hold flag + per-record purge inhibition.
- Implement `GET /audit/entry/{leaf_index}` endpoint with 5s p99 SLO.
- ~400-600 LOC across audit + retention modules.

### `MPC-Spec`

- §16.5 expanded to §16.5.3 – §16.5.9 (already applied as stubs per clear-win pass).
- §16.14 retention + legal hold (new).
- §16.15 SLA framework (new).
- §17.14 vendor matrix (already applied).
- §10.12 audit retrieval API (new).
- §13.15 operator-bridge RACI (new).
- Q42-Q47 OPEN-QUESTIONS added.

## Alternatives considered

- **Single mega-IR-runbook covering all classes.** Rejected — different severity, different cadence, different cross-operator-coordination needs. Per-class runbook is auditor-favored.
- **Defer all to v2.** Rejected — Quality swarm noted that markdown-only IR additions are M1-deliverable. v1.5 launches Notary publicly; can't ship without IR coverage.
- **Outsource to a generic IR platform (PagerDuty templates).** Templates inform but the partnership-specific runbooks are non-replaceable.

## Status of M1 dependency

**Mixed.** Markdown spec edits (IR runbook stubs, severity matrix, vendor matrix) are M1-deliverable (already applied). Audit retention 5-year storage cost-model is v2 (sizing decision). Right-to-erasure (Q47) is v2 legal review.

## See also

- Spec: [§16.5.3-§16.5.9](../16-operations.md), [§16.14, §16.15](../16-operations.md), [§17.14](../17-supply-chain.md)
- ADR-0036 (customer-onboarding disclosure)
- ADR-0039 (eclipse detection feeds IR-006)
- ADR-0040 (re-attestation failure feeds IR-002/IR-008)
- 2026-05-13 swarm: Quality G2 + G3 + G4
- Reference: SOC2 TSP CC7.3; NYDFS Part 500 §500.06/500.11/500.16/500.17; MiCA Art.68/70/75; DORA Art.28; GDPR Art.5/17; ISO/IEC 27001:2022 Annex A.5/A.8

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
