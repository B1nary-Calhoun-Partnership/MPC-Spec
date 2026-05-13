# 16 — Operations & SRE

**Status:** DRAFT
**Version:** v1
**Phase:** 2
**Decided by:** ADR-0016 (proposed)
**Last updated:** 2026-05-10

## 16.1 v1 deployment posture (the headline)

**v1 ships without TEE and without HSM cold tier.** Cosigners run on standard cloud infrastructure (CF Workers, k8s pods, VMs). Runtime integrity comes from the cryptographic stack already in place:

- Threshold security (CGGMP'24 UC-IA, §01)
- Share encryption at rest (AES-256-GCM with BRC-42-derived keys)
- 30-day share refresh cadence (§16.5, POC 13 pattern)
- Audit log + witness cosigning (§10)
- Per-cosigner policy enforcement (§09)
- Build-time supply-chain provenance via cosign + Rekor + SLSA L3 (§17)

TEE attestation and HSM cold tier are reserved for **v2 institutional tier**. Cost analysis driving this decision:

| Component | Cost | v1 verdict |
|---|---|---|
| AWS Nitro Enclave | ~$0.40/hr/cosigner ≈ $300/mo | Excessive for v1 cost-benefit |
| AWS CloudHSM | ~$1.45/hr/cluster ≈ $1K/mo | Excessive for v1 cost-benefit |
| Multi-region multi-vendor TEE | $1K+/mo | Excessive for v1 cost-benefit |

The cryptographic invariants we have without enclave hardware are sufficient for v1 threat model. TEE adds defense-in-depth against host-OS root compromise; this is bounded by the share refresh window even without TEE. HSM adds regulatory-grade custody assurance; not v1 audience.

**Forward-compat hooks are preserved.** Cert format keeps `attestation` and `binary_hash` fields as OPTIONAL (§08). Policy engine keeps `RuleKind::RequireAttestation` schema. When v2 ships, no wire changes are required.

### 16.1.1 Customer-facing disclosure obligation (NEW per ADR-0036)

The v1 deployment posture is explicitly **not** a regulated-custody product. Operators marketing the v1 stack to:
- NYDFS Part 500 -licensed entities,
- MiCA Art.75 CASP custody customers,
- OCC trust-charter applicants,
- Anyone subject to SOC2 Type II strict scope on the cryptographic key-material control,

MUST disclose ADR-0016 deferrals (no v1 TEE, no v1 HSM cold tier) in their customer-facing security documentation BEFORE onboarding the customer. The disclosure MUST cite the v2 institutional-tier roadmap as the customer-targeted upgrade path. Operators that conceal the v1 posture in marketing materials are non-conformant.

This obligation does NOT apply to operators marketing to:
- MSB-licensed fintech treasury (signing own keys, not custodying customer keys).
- Web2.5 self-custody products where the user accepts the v1 posture per onboarding flow.
- AI-agent / x402 paid-signing use cases at sub-cent value transactions (§15.2.2 Express tier).

The customer-onboarding doc MUST include a "shared-responsibility model" diagram per ADR-0042 §17.14 vendor matrix.

## 16.1.2 Operator → profile binding (normative, per 2026-05-13 divergence-risk swarm)

Each cosigner MUST advertise its profile (per §16.2 below) in the CHIP capabilities JSON as `profile: "<profile-name>"`. Once advertised, the operator MUST NOT silently flip the profile — profile change is a §09.9 policy event requiring m-of-n approver sign-off.

Reference bindings:

- **`bsv-mpc-worker`** (Calhoun CF Worker Notary) → `profile-edge`
- **`bsv-mpc-service`** (Calhoun dedicated host) → `profile-server`
- **`rust-mpc` cosigner backend** (Binary Railway-hosted) → `profile-server`
- Cosigner-on-phone (any stack) → `profile-mobile` or `profile-mobile-constrained`

CI gates: the daily drift-watch workflow asserts profile binding matches the cosigner's advertised host (via DNS + `/capabilities` declaration). Profile flips fail the build and require an ADR or m-of-n policy-update.

## 16.2 Conformance profiles

The spec defines four deployment profiles. A cosigner declares its profile in CHIP token capabilities.

| Profile | Target | SLI focus |
|---|---|---|
| `profile-edge` | CF Worker (bsv-mpc-worker) | Cold-start latency, DO contention |
| `profile-server` | k8s pod / VM (rust-mpc backend) | Pod restart impact on presig pool |
| `profile-mobile` | iOS / Android (rust-mpc native) | Backgrounding, FCM wakeup reliability |
| `profile-desktop` | Tauri client | Laptop sleep, network change |

A Notary MUST be `profile-edge` or `profile-server` (high-availability requirement). A user-side cosigner MAY be any.

**Diversification.** A 2-of-3 deployment SHOULD spread cosigners across distinct cloud vendors / accounts / jurisdictions. Cloud-correlation risk (AWS us-east-1 outage, single-account credential compromise) is a meaningful threat in v1's "no TEE" posture. Recommended pattern: cosigner A on Cloudflare, cosigner B on AWS, cosigner C on GCP — or any two-of-three split that doesn't share single-vendor failure modes.

## 16.3 SLI catalog (15 SLIs)

| SLI | Target | Profile applicability |
|---|---|---|
| `signing.latency` (p50/p99) | p99 ≤ 250ms (presigned), ≤ 1500ms (4-round) | All |
| `signing.availability` | ≥ 99.9% monthly (43 min budget) | Edge, Server |
| `dkg.success_rate` | ≥ 99.5% on first attempt | All |
| `presig.pool_depth` | ≥ 5 at all times | Edge, Server |
| `presig.drain_rate` | < replenishment rate | Edge, Server |
| `refresh.cadence_compliance` | refresh.last_age ≤ 30d | All |
| `identifiable_abort.rate` | ≤ 0.05% of attempts | All |
| `attestation.failure_rate` | ≤ 0.01% of attestation checks | (v2; TEE-enabled deployments only) |
| `cert.expiry_runway` | ≥ 6h to notAfter | All |
| `transport.queue_depth` | < 100 | Edge, Server |
| `transport.poll_lag` | < 1s | (poll-mode receivers) |
| `audit.publish_lag` | STH publish ≤ 60s past schedule | All |
| `operator.cert_age` | < 90d (rotation due) | All |
| `fee.injection_failure_rate` | ≤ 0.01% | All |
| `recovery.drill_success_rate` | quarterly drill passes | Edge, Server |
| `presig.warm_path_hit_rate` | ≥ 0.95 (per ADR-0041) | Edge, Server |
| `audit.retrieval_latency_p99` | ≤ 5s (per ADR-0042 / §10.12) | All |

### 16.3.1 SLO publication

Each operator MUST publish a `health.json` consumable by `compose_sla()`:

```json
{
  "operator": "calhoun",
  "cosigner_identity": "0299aa...",
  "profile": "profile-edge",
  "version": "0.1.0",
  "binary_hash": "sha256-hex",
  "sli": {
    "signing.latency.p50_ms": 80,
    "signing.latency.p99_ms": 240,
    "signing.availability_30d": 0.9994,
    "dkg.success_rate": 0.999,
    "presig.pool_depth": 12,
    "refresh.last_age_days": 17,
    "attestation.format": "nitro_v1",
    "audit.last_sth_age_seconds": 42
  },
  "ts": 1730000000
}
```

Wallets and SDK consumers query `health.json` periodically and degrade gracefully.

A reference Rust crate `sla.compose()` returns the joint SLA of any quorum.

## 16.4 Cross-party tracing — OpenTelemetry with whitelist

`traceparent` (W3C Trace Context) rides as MessageEnvelope field 12 (§05.4.11). Each cosigner injects `traceparent` into outbound MPC messages and continues the trace span on receipt.

**Allowed span attributes** (the whitelist):
- `mpc.session_id` (UUID-like 32-byte hex)
- `mpc.execution_id` (32-byte hex of canonical ExecutionId)
- `mpc.phase` (`"dkg-keygen"` | `"dkg-auxinfo"` | `"presign"` | `"sign"` | `"ecdh"` | `"refresh"`)
- `mpc.round` (u8)
- `mpc.party_index` (u16)
- `mpc.threshold` (e.g. `"2-of-3"`)
- `mpc.joint_pubkey_fingerprint` (first 8 bytes of SHA-256 of joint_pubkey — *not* the pubkey itself, to prevent linking sessions to addresses)
- `mpc.message_size_bytes`
- `mpc.outcome` (`"ok"` | `"abort"` | `"timeout"` | `"identifiable_abort"`)
- `mpc.aborted_party` (party_index, only on identifiable abort)
- `error.type`

**Forbidden span attributes** (any of these in a span fails CI):
- Any scalar (key share, partial signature, nonce)
- Any commitment (Paillier ciphertext, Schnorr commitment, ZK proof element)
- The joint pubkey itself (only the 8-byte fingerprint is allowed)
- The sighash (for sign-phase spans)
- BRC-31 nonces or session tokens
- User identity keys (only `from_party` index is allowed)

The spec ships a **redaction linter** (`mpc-otel-lint`) that fails CI if a span attribute matches a forbidden regex. Both implementations MUST integrate the linter into their CI.

## 16.5 Refresh choreography

### 16.5.1 RR-001: Routine 30-day refresh

```
T-72h: Initiating operator (lowest party index that is online) publishes
       refresh.proposed signed under its BRC-52⊕ cert.
       Event posted to MessageBox + announced on BRC-22 tm_mpc_signing.
       All operator on-calls receive Slack-bot ack request, 24h SLA.

T-48h: Each other cosigner publishes refresh.acked. If quorum (t total ack-ers)
       not reached, alert OPS_REFRESH_QUORUM_PENDING fires.

T-0:   t parties (need not be all n) run threshold resharing.
       Offline party catches up via §13.8.

T+0:   refresh.completed event with the new commitment.
       Old shares cryptographically dead.
```

### 16.5.2 IR-002: Suspected compromise (sub-30-min)

Detection signals:
- Failed Rekor reverification.
- Unexpected attestation PCR.
- Anomalous policy decline rate.
- BRC-22 reputation drop.
- Peer's `audit-anomaly` BRC-22 post.

```
T+0:    Suspecting party's on-call files IR-002 in Slack.
        Proposes refresh-without-the-suspect.

T+5m:   Bridge call. Sev-2 channel.

T+10m:  t-1 other operators ack via signed BRC-22 message.

T+15m:  Resharing fires. Suspected party excluded from polynomial.

T+30m:  New cosigner provisioned + cross-signed.
        Old cert revoked (BRC-22 tm_mpc_revocations).
        New CHIP token published.

T+60m:  Status page green; presig pool back to depth 5+.
```

### 16.5.3 IR-003: Coordinator compromise

**STUB per ADR-0042; full text in upcoming spec PR.** Detection: coordinator state-machine anomalies (wrong-order rounds emitted, presig bundle deletions outside §06.18 triggers, audit-log writes that don't witness-cosign). Response shape: full coordinator quarantine + secondary coordinator activation + audit-anomaly publication + Sev-1 escalation. Distinguishes coordinator-as-cosigner vs coordinator-as-pure-router compromises. T+0/T+5m/T+15m/T+30m structure.

### 16.5.4 IR-004: MessageBox / relay compromise

**STUB per ADR-0042.** Detection: BRC-31 signature failures spiking on a single relay; envelope-loss patterns; relay return-codes inconsistent with cosigner-witnessed history; impossible-time-ordering envelopes. Response: switch to backup relay (per §06.7 federation), revoke compromised relay's CHIP token, audit-anomaly publish, customer notification. Does NOT require ceremony abort — by §06.2 layering, relay compromise can drop / reorder / observe but not forge envelopes if §05.9.1 re-encode check is implemented.

### 16.5.5 IR-005: Certifier-key compromise

**STUB per ADR-0042.** Detection: unauthorized BRC-52⊕ cert issuance; Sigstore Rekor-log anomaly; root-of-trust event signal. Response: revoke root cert (BRC-22 `tm_mpc_revocations`), re-issue cosigner certs under successor root, mandatory force-refresh across all cosigners under the compromised root, Sev-1 status page red. Highest impact — root-key compromise invalidates the whole trust chain. T+0/T+1h/T+24h/T+72h escalation (slower because cross-operator coordination required).

### 16.5.6 IR-006: Audit-chain censorship / eclipse

**STUB per ADR-0042.** Detection (per §10.5.7 step 0): multi-source STH lookup disagreement; witness-cosign failures spike; BRC-22 host returns stale tip on cross-check. Response: failover to second BRC-22 host, force witness-cosign cadence to 10s, customer notification, audit-anomaly publish. Distinguishes wide eclipse (network) vs selective (one operator). Sev-2 escalation.

### 16.5.7 IR-007: Policy-manifest poisoning

**STUB per ADR-0042.** Detection: PolicyManifest hash mismatch (BRC-52⊕ `policy_hash` vs locally-fetched manifest); approver-quorum signatures don't verify; rule additions that lack m-of-n approver sigs. Response: refuse-to-load on hash mismatch, fall back to prior manifest version, alert approvers via separate channel, audit-anomaly. Sev-2.

### 16.5.8 IR-008: Presig-pool poisoning

**STUB per ADR-0042 (newly relevant after ADR-0030).** Detection: presig consumption produces sigs that don't verify under joint pubkey; cosigner-encrypted presig blobs fail BRC-2 decrypt; coordinator's pool serves bundles bound to stale `policy_id` or `joint_pubkey`. Response: atomic pool deletion per §06.18, audit-anomaly, force-refresh of all bundles, presig regen from clean slate. Sev-1 (a single bad sig that broadcasts is unrecoverable).

### 16.5.9 Sev-1/Sev-2/Sev-3/Sev-4 classification matrix

**STUB per ADR-0042.** Triggers per severity:
- **Sev-1**: key-material compromise (IR-005, IR-008-with-broadcast), quorum loss (§16.6.3), audit-chain rewrite proven.
- **Sev-2**: single-cosigner compromise (IR-002), coordinator anomaly (IR-003), relay failure (IR-004), policy poisoning (IR-007), audit eclipse (IR-006).
- **Sev-3**: presig-pool depth degraded, share-refresh missed deadline, OTel signal loss.
- **Sev-4**: latency budget breach (§06.10), warm-path hit rate below SLI target, vendor-status changes (§17.14).

Mapping to PagerDuty / Opsgenie severity tiers is implementation-specific; this matrix is the spec contract.

## 16.6 Disaster recovery

### 16.6.1 Case (a): One cosigner data-destroyed

Other `t` execute party-replacement resharing with brand-new operator. ~5 min unavailability if presig pool drains; otherwise 0.

### 16.6.2 Case (b): One compromised but online

IR-002 immediately reshares without them. Status page goes amber. Signing continues with `t-1`-fault-tolerance until the new party is provisioned.

### 16.6.3 Case (c): Two of three fail simultaneously

Quorum loss. No new signatures. v1 has no HSM cold tier, so restoration depends on:
- User recovery passphrase (BRC-42-derived) if user-side share lost — works in v1.
- Encrypted backup at user's BRC-100 wallet (§18) — works in v1.
- ~~Jurisdictional escrow backup~~ — v2 (depends on cold-tier infra).
- ~~HSM cold-tier party~~ — v2.

For v1 high-value users who want belt-and-suspenders, the recommendation is to spread cosigners across maximally diverse infrastructure (different cloud vendors, regions, jurisdictions, BRC-31 identity-key custody) to reduce simultaneous-failure probability. Runbook: IR-009. See §18.

## 16.7 TEE attestation — v2 reserved (NOT v1)

Cosigner cert reserves `tee_attestation` + `attestation_format` fields (Nitro PCR0/PCR8 / SEV-SNP report / TDX TDREPORT / `none`). Policy engine reserves `RuleKind::RequireAttestation { format }`. **Both are OPTIONAL in v1; default `none`.**

v1 implementations MAY ignore these fields entirely. v2 institutional deployments will activate them when regulatory pressure for hardware-backed key custody appears.

The decision to defer is cost-driven (§16.1). A v2 ADR will supersede this section when the cost-benefit changes (e.g., Nitro Enclave pricing drops, or the partnership signs an institutional customer who requires it).

## 16.8 Operator credentials rotation

Every 90 days:

1. New BRC-52⊕ operator cert issued.
2. Advertised via overlay.
3. Old cert sunset over 7-day overlap.
4. CF account / k8s cluster credentials rotated quarterly with two-person rule (PR review + on-call ack).

## 16.9 Chaos engineering — quarterly drills

Required drills:

| Drill | What it tests |
|---|---|
| Transport partition | Cosigner fails over to inbox_url_fallback |
| Single-cosigner kill | Surviving `t` parties continue signing |
| Refresh under load | Signing during refresh succeeds |
| Presig-drain attack | Rate limiting prevents pool exhaustion |
| Compromise simulation | IR-002 fires correctly; new cosigner provisioned |

Use Chaos Mesh (k8s) or AWS Fault Injection Simulator (cloud).

## 16.10 Capacity planning

Presig pool sizing formula:

```
pool_size_min = 2 × p99_signing_RPS × presig_generation_seconds
```

For a Notary at 10 sigs/sec with 1s presig generation: `pool_size_min = 20`.

Background replenishment runs as soon as pool drops below 80% of `pool_size_min`.

## 16.11 On-call structure

Single-operator deployments use a 1-deep rota.

Multi-operator deployments MUST share an "operator bridge" channel for IR coordination. PagerDuty/Opsgenie escalation policies on each side route to the bridge.

## 16.12 Postmortems

Required within 5 business days of any SEV-1 / SEV-2 incident. Published to BRC-22 `tm_mpc_postmortems` (digest + URL). Body lives at the operator's URL; URL hash is on-chain for tamper-evidence.

Use Google SRE Workbook blameless template.

## 16.14 Audit retention + legal hold (normative, per ADR-0042 Part C)

### 16.14.1 Retention period

- **Local Merkle leaves MUST be retained ≥5 years** to satisfy NYDFS §500.06 + MiCA Art.68 + SOC2 CC7.2 + GLBA Safeguards Rule.
- Implementations MAY tighten (e.g., to 7 or 10 years) per per-deployment regulatory minimum.
- The on-chain STH chain (per §10.5) is permanently retained by definition (UTXO + spend history is immutable).

### 16.14.2 Legal hold

- A per-customer **legal-hold flag** AND a per-record legal-hold flag MUST be supported.
- When set, pruning of in-scope records is FROZEN regardless of the 5-year baseline.
- Legal-hold lift MUST emit an `AuditEntry` with `event_kind = "LegalHoldLifted"`.

### 16.14.3 Right-to-erasure (GDPR Art.17)

- Handled via **tombstone-with-hash, NEVER leaf-deletion** — preserves Merkle root + audit-chain integrity.
- The leaf preimage is removed; the leaf hash remains in the Merkle tree.
- §10.12.1 specifies the retrieval API's tombstone response.
- **PII forbidden in `request_hash` preimage** — only hashes of customer identifiers may be included in audit leaves. PII in the preimage would be permanently anchored on-chain via STH, defeating GDPR Art.17 compliance.

Right-to-erasure handling is detailed in CHANGES-PROPOSED.md item 7. The hashed-not-personal-data legal posture is being pursued per Q47.

## 16.15 SLA framework — composed-quorum guarantees (normative, per ADR-0042 Part D)

### 16.15.1 SLO vs SLA distinction

- §16.3 SLIs define **SLO** (operator targets, internal). e.g., `signing.latency.p99 ≤ 250ms`.
- §16.15 SLAs are the **contractual customer-facing targets** for institutional-tier deployments. Tighter or looser than SLOs per contract.

### 16.15.2 Joint SLA composition

For multi-operator deployments (e.g., Pro tier 2-of-5 marketplace), the joint SLA is the **quorum-fault-tolerant minimum** of individual operator SLAs:

```
joint_availability = P(at_least_t_operators_meet_their_SLO)
joint_latency_p99  = max(operator_latency_p99 over the t-quorum)
```

Implementations MAY expose this composition via a `sla.compose(operator_slos: [Slo], threshold: t)` library function (informative — not normatively required).

### 16.15.3 Error-budget burn-rate alerts

Operator dashboards MUST surface error-budget burn-rate alerts as a third column alongside SLI (current) and SLO (target). Burn-rate algorithm RECOMMENDED: Google SRE Workbook 2/5 (fast burn: 2% of monthly budget in 1 hour; slow burn: 5% in 6 hours).

## 16.16 CISO governance (normative, per CHANGES-PROPOSED #8)

Operational chief-information-security-officer (CISO) function is structured per the 2026-05-13 partnership resolution as follows.

### 16.16.1 Operational CISO — quarterly rotation

- Calhoun and Binary alternate the operational CISO role on a quarterly cadence.
- The active CISO is the single point of contact for:
  - Sev-2 and Sev-3 incidents (per §16.5.9)
  - Vendor-risk review (per §17.14)
  - Policy-manifest sign-off (per §09.8)
  - Operator credential rotation cadence (per §16.8)
  - SLA composition decisions (per §16.15)
  - Pen-test scope (per ROADMAP v1.5)
- Quarterly handoff is **strictly async** (per partnership operating model: no scheduled calls). Outgoing CISO writes a **handoff PR** to `MPC-Spec/governance/ciso-handoff-YYYY-Q.md` covering: (a) open incidents + status, (b) vendor-risk register state + outstanding actions, (c) pending policy-manifest reviews, (d) ADR sign-off backlog. Incoming CISO reviews the PR; approval = formal handoff. Two-week shadow period = collaborative PR review on in-flight items in `#mpc-spec-*` Slack channels (no "shadow calls"; the PR comment thread is the handoff record).

### 16.16.2 External advisor — retained for Sev-1 highest-impact incidents

An external security advisor is retained on a monthly retainer (~$2-4k/mo) for engagement on:

- **IR-005 (Certifier-key compromise)** — root-of-trust event affects partnership-wide trust
- **IR-008 with broadcast (Presig-pool poisoning where a bad signature broadcast to mainnet)** — unrecoverable forged signature; trust-restoration critical
- Optional engagement for IR-001/002 (cosigner compromise) when both stewards mutually agree

Advisor MUST have demonstrated MPC / threshold-signing experience (preferred: ToB / NCC / Cure53 senior consultant, or independent with comparable public track record).

Advisor signs an NDA covering audit-substrate access, cert chains, and operator IR procedures. Advisor does NOT hold any cosigner share or have signing capability.

### 16.16.3 Conflict-of-interest discipline

The active CISO MUST recuse from decisions where their own operator's stack is the subject (e.g., post-IR-002 cosigner-compromise on Calhoun side, the active CISO is Binary even if it's a Calhoun-quarter rotation; rotation timer pauses).

## 16.13 Implementation notes

- bsv-mpc has no formal SLI/SLO instrumentation today. Add via `tracing` crate + Prometheus exporter.
- rust-mpc has more structured logging (per `crates/policy/src/audit.rs`); extend to OpenTelemetry semantic conventions.
- Both implementations MUST adopt the OTel attribute whitelist + redaction linter.
- Refresh choreography is new functionality. Coordinate the BRC-22 event format before implementing.

## See also

- [`decisions/0016-operations-otel-runbooks.md`](decisions/0016-operations-otel-runbooks.md) — ADR.
- [`13-federation.md`](13-federation.md) — operator-replacement choreography.
- [`17-supply-chain.md`](17-supply-chain.md) — attestation + binary_hash.
- [`18-recovery.md`](18-recovery.md) — IR-009 quorum loss.
- [`appendices/swarm-reports/F-operations.md`](appendices/swarm-reports/F-operations.md) — full design rationale.
- Google SRE Book / Workbook
- OpenTelemetry semantic conventions
