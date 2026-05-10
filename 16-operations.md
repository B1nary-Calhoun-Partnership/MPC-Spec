# 16 — Operations & SRE

**Status:** DRAFT
**Phase:** 2
**Decided by:** ADR-0016 (proposed)
**Last updated:** 2026-05-10

## 16.1 Conformance profiles

The spec defines four deployment profiles. A cosigner declares its profile in CHIP token capabilities.

| Profile | Target | SLI focus |
|---|---|---|
| `profile-edge` | CF Worker (bsv-mpc-worker) | Cold-start latency, DO contention |
| `profile-server` | k8s pod / VM (rust-mpc backend) | Pod restart impact on presig pool |
| `profile-mobile` | iOS / Android (rust-mpc native) | Backgrounding, FCM wakeup reliability |
| `profile-desktop` | Tauri client | Laptop sleep, network change |

A Notary MUST be `profile-edge` or `profile-server` (high-availability requirement). A user-side cosigner MAY be any.

## 16.2 SLI catalog (15 SLIs)

| SLI | Target | Profile applicability |
|---|---|---|
| `signing.latency` (p50/p99) | p99 ≤ 250ms (presigned), ≤ 1500ms (4-round) | All |
| `signing.availability` | ≥ 99.9% monthly (43 min budget) | Edge, Server |
| `dkg.success_rate` | ≥ 99.5% on first attempt | All |
| `presig.pool_depth` | ≥ 5 at all times | Edge, Server |
| `presig.drain_rate` | < replenishment rate | Edge, Server |
| `refresh.cadence_compliance` | refresh.last_age ≤ 30d | All |
| `identifiable_abort.rate` | ≤ 0.05% of attempts | All |
| `attestation.failure_rate` | ≤ 0.01% of attestation checks | (TEE-enabled) |
| `cert.expiry_runway` | ≥ 6h to notAfter | All |
| `transport.queue_depth` | < 100 | Edge, Server |
| `transport.poll_lag` | < 1s | (poll-mode receivers) |
| `audit.publish_lag` | STH publish ≤ 60s past schedule | All |
| `operator.cert_age` | < 90d (rotation due) | All |
| `fee.injection_failure_rate` | ≤ 0.01% | All |
| `recovery.drill_success_rate` | quarterly drill passes | Edge, Server |

## 16.3 SLO publication

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

## 16.6 Disaster recovery

### 16.6.1 Case (a): One cosigner data-destroyed

Other `t` execute party-replacement resharing with brand-new operator. ~5 min unavailability if presig pool drains; otherwise 0.

### 16.6.2 Case (b): One compromised but online

IR-002 immediately reshares without them. Status page goes amber. Signing continues with `t-1`-fault-tolerance until the new party is provisioned.

### 16.6.3 Case (c): Two of three fail simultaneously

Quorum loss. No new signatures. Restoration via:
- User recovery passphrase (BRC-42-derived) if user-side share lost.
- Jurisdictional escrow backup if operator-side shares lost.

Runbook: IR-009. See §18.

## 16.7 TEE attestation (optional)

Cosigner cert includes `tee_attestation` field (Nitro PCR0/PCR8 / SEV-SNP report / TDX TDREPORT / `none`).

- Counterparty policies MAY require non-empty attestation via `RuleKind::RequireAttestation { format }`.
- Cost: ~$0.40/hr extra on AWS Nitro; fewer GCP regions; complicates debugging.
- Benefit: defends host-OS root, container pivots, supply-chain attacks.

Mandate: NONE. Notaries SHOULD support TEE attestation for institutional users.

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
