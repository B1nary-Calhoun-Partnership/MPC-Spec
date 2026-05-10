# Appendix F — Operations & SRE

> Full report from the Operations zone agent of the god-tier-design swarm (2026-05-10).
> Preserved verbatim as supporting depth for [`§13-federation.md`](../../13-federation.md), [`§16-operations.md`](../../16-operations.md), [`§17-supply-chain.md`](../../17-supply-chain.md).

---

> **Note on v1 vs v2 (2026-05-10):** This report's recommended Option 3 (hybrid hot-TEE + cold-HSM via resharing) was de-prioritized for v1 per [`ADR-0016`](../../decisions/0016-v1-ops-topology-no-tee-no-hsm.md). Cost analysis: AWS Nitro at ~$300/mo per cosigner + AWS CloudHSM at ~$1K/mo cluster is excessive for v1's per-signature-pricing thesis. v1 ships with standard cloud cosigners; cryptographic invariants (threshold + refresh + audit + witness cosigning + share encryption) provide v1 security posture without enclave hardware. The hybrid topology described below is the v2 institutional target when regulatory pressure for hardware-backed key custody appears. Forward-compat hooks (cert `attestation` field, policy `RequireAttestation` rule) remain in v1 spec but are not activated.

---

## §A: God-Tier Definition (Ops/SRE Layer)

**God-tier ops for an MPC threshold-signing network** is: *a debuggable, blameless, vendor-neutral choreography of cryptographic ceremonies across mutually-distrusting operators, with cryptographic supply-chain provenance from source to running enclave, where every share-touching action is observable from a public-facing SLO dashboard but no observer ever learns a share, and where any single operator can be replaced with sub-hour MTTR without cooperation from the others.*

**Production reference points (cited per option below):**
- **Fireblocks** — co-signer model: dedicated SGX/Nitro Enclave appliances, "policy engine" as separate quorum, governance-grade key rotation runbooks, SOC 2 Type II audited; their public SOC 2 bridge letter and the Fireblocks Co-Signer datasheet are the operational template.
- **Coinbase Custody / Anchorage** — geographically distributed quorum, M-of-N HSM-backed signers, NYDFS BitLicense-shaped IR, off-line cold tier with timed unsealing.
- **HashiCorp Vault** — Raft replication, Performance Standby, leader/follower DR replication, sealed/unsealed lifecycle, audit log streaming via Sentinel — the active-passive multi-region archetype.
- **AWS Nitro Enclaves / GCP Confidential VMs / Azure Confidential Computing** — vTPM/SEV-SNP/Nitro attestation docs.
- **OpenTelemetry** — semantic conventions for `messaging.*` and the in-flight `crypto.*` SIG; W3C Trace-Context propagation.
- **TUF / in-toto / Sigstore (cosign + Rekor)** — the supply-chain triad. SLSA Level 3+ (hermetic, isolated, signed provenance).
- **Google SRE Workbook** — SLOs, error budgets, blameless postmortems.
- **Chaos Mesh / Litmus** — Kubernetes-native fault injection; AWS FIS for cloud chaos.
- **Datadog APM / Honeycomb** — production tracing patterns; Honeycomb's BubbleUp is gold for ceremony-failure root cause.

## §B: Option 1 — "Cloud-Native, OTel-traced, TEE-enclaved, Sigstore-attested"

**Shape:** Each cosigner runs in a confidential VM (AWS Nitro Enclave, GCP Confidential VM with AMD SEV-SNP, or Azure Confidential Computing). MessageBox is the data plane; OpenTelemetry over OTLP is the observability plane (separate egress, separate trust). Binaries are reproducibly built, signed with `cosign`, logged to Rekor; the cosigner refuses to start unless its own image's Rekor entry verifies. Operators are paged via PagerDuty with runbook links to `docs/runbooks/`.

**Cross-party tracing.** A new `traceparent` field is added to the `MessageEnvelope` (CBOR map key 12). Every cosigner injects `traceparent` into outbound MPC messages and continues the trace span on receipt. Each span uses **only the OpenTelemetry semantic conventions plus a new `mpc.*` namespace** that the spec defines exhaustively. **What's allowed in a span:** `mpc.session_id` (UUID), `mpc.execution_id` (32-byte hex of canonical ExecutionId), `mpc.phase`, `mpc.round`, `mpc.party_index`, `mpc.threshold`, `mpc.joint_pubkey_fingerprint` (first 8 bytes of SHA-256 of the compressed pubkey — *not* the pubkey itself, to avoid linking sessions to addresses in the trace store), `mpc.message_size_bytes`, `mpc.outcome`, `mpc.aborted_party` (party_index, only on identifiable abort), `error.type`. **What's forbidden:** any scalar, any commitment, any nonce, any partial signature, any Paillier ciphertext, the joint pubkey itself, the sighash, the user identity key, the BRC-31 nonce. The spec ships a *redaction linter* that fails CI if a span attribute matches a forbidden regex.

**Key rotation choreography.** 30-day cadence is automated via a `RefreshOrchestrator` running on each cosigner. RR-001 routine choreography:

> `T-72h`: Initiating operator publishes `refresh.proposed` signed under its BRC-52⊕ cert.
> `T-48h`: Each other cosigner publishes `refresh.acked`. Quorum check.
> `T-0`: t parties run threshold resharing.
> `T+0`: `refresh.completed` event with the new commitment. Old shares are cryptographically dead.

**Disaster recovery.**
- **(a) one cosigner data-destroyed**: The other `t` execute *party-replacement resharing*. The replacement cosigner can be a brand-new operator. User-facing impact: ~5 min unavailability if presig pool drains; otherwise 0 (presigs cover the gap).
- **(b) one cosigner compromised but online**: An *attested* compromise (e.g. Nitro PCR change detected) triggers `IR-002` — the other `t` parties immediately run resharing *without* the compromised party. User-facing: status page goes amber; signing continues with `t-1`-fault-tolerance until the new party is provisioned. p99 latency may rise.
- **(c) two of three fail simultaneously**: This is a *quorum loss event*. No new signatures can be produced. The spec mandates each operator hold an *encrypted share backup* sealed to the user's recovery key (BRC-42-derived from a recovery passphrase) AND a separate encrypted-to-jurisdictional-escrow backup. Restoration runbook `IR-009` defines the user-driven recovery path.

**Deployment topology.** The spec recognizes **four deployment classes** as conformance profiles:
- `profile-edge`: Cloudflare Worker (bsv-mpc-worker today).
- `profile-server`: k8s pod or VM (rust-mpc backend).
- `profile-mobile`: iOS app via uniffi (rust-mpc native).
- `profile-desktop`: Tauri client.

A Notary MUST be `profile-edge` or `profile-server`. A user-side cosigner MAY be any.

**TEE story.** Recommended (not mandated, to preserve neutrality). The cosigner cert includes optional `tee_attestation` field — a Nitro PCR0/PCR8 measurement, or SEV-SNP attestation report, or absent. Counterparties' policy engines may *require* a non-empty attestation. The spec defines `attestation.format = "nitro_v1" | "sev_snp_v1" | "tdx_v1" | "none"` and a verification procedure for each.

**Supply chain.** Reproducible Cargo builds (`SOURCE_DATE_EPOCH`, `--locked`, vendored deps); `cosign sign-blob` against the binary; transparency log entry to Rekor. SLSA L3 via GitHub Actions reusable workflow with hermetic builders. Runtime check: each cosigner on startup re-verifies its own Rekor entry via `cosign verify-blob --certificate-identity=...`. **The `tee_attestation` includes a SHA-256 of the attested binary; counterparties verify both the TEE measurement and the Rekor entry match.**

**SLOs.** Published externally:
- *Sign latency p99* ≤ 250 ms (presigned path), ≤ 1500 ms (4-round).
- *Sign availability* ≥ 99.9% monthly (43 min budget).
- *Identifiable-abort rate* ≤ 0.05% of attempts.
- *Presig pool depletion incidents* = 0 per quarter.
- *DKG success rate* ≥ 99.5% on first attempt.

**Incident response.** When a cosigner is *suspected* compromised (signal sources: failed Rekor reverification, unexpected attestation PCR, anomalous policy decline rate, BRC-22 reputation drop, peer's `audit-anomaly` BRC-22 post): **the suspecting party's on-call** files an `IR-002` and proposes refresh-without-the-suspect. **Refresh fires after `t-1` other operators ack** (one-vote-veto avoided; one-vote-pause respected by the operator-quorum gate). Page → SEV-2 Slack channel → bridge call → resharing within 30 minutes of detection.

**Operator credentials.** Each operator runs an *operator identity rotation* every 90 days: new BRC-52⊕-issued operator cert, advertised via overlay, old cert sunset over a 7-day overlap. CF account / k8s cluster credentials are rotated quarterly, with the `secret_rotation` runbook gated on a "two-person rule" (PR review + on-call ack).

**Grade (5-axis):** Security 5, UX 4 (TEE debugging is painful), Vendor-neutrality 4 (cloud TEEs are vendor-specific), Operability 5, Composability 5. **Total 23/25.**

## §C: Option 2 — "Air-Gapped Cold-Cosigner / HSM-Backed"

**Shape:** Inspired by Coinbase Custody / Anchorage cold-tier and BitGo's enterprise model. `t-1` hot cosigners run in standard cloud; one cosigner is air-gapped HSM-backed (AWS CloudHSM, YubiHSM2, or Thales Luna). DKG is performed once via QR-code data-diode bootstrap; signing requests for the cold party are couriered via signed-and-encrypted "ceremony bundles" reviewed by humans. Tracing on hot side is OTel; cold side has paper-and-camera audit trail.

**Grade:** Security 5, UX 2 (cold-tier UX is painful by design), Vendor-neutrality 3 (HSMs lock you in but the protocol abstracts), Operability 3 (cold debugging is glacial), Composability 4. **Total 17/25** — but for institutional/regulated users this is the only acceptable design.

## §D: Option 3 — "Hybrid: Hot TEEs + Cold HSM Recovery Tier (RECOMMENDED)"

**Shape:** Three hot cosigners in TEEs (Option 1 design) form the *operational quorum* (2-of-3 with full Option 1 ops). Plus one or two *cold-tier recovery cosigners* in HSMs (Option 2 design) — these participate only in resharing and disaster recovery, never routine signing. The *effective threshold during operation is 2-of-3 hot*; the *effective threshold during recovery is 2-of-5* (any 2 of {3 hot ∪ 2 cold}). Resharing is the bridge — POC 13 validated cross-(t,n) resharing.

This composes the strengths: hot-quorum gives Option 1's UX, latency, and SLO; cold-tier gives Option 2's compromise-tolerance for the bottom of the stack. The cold tier is the user's "vault" — it is invoked only when the hot tier has suffered a quorum loss or when the user wants a multi-week-cooldown high-value transaction.

**The key insight:** resharing (POC 13) means *the threshold can be reconfigured without moving funds*. The spec exposes this as a first-class `quorum_profile` enum: `Hot` (3 hot only, 2-of-3, fast), `HotPlusCold` (5 parties, 2-of-5, recovery-capable), `ColdOnly` (cold-only, 2-of-2, vault). A user can move between profiles via resharing, with no on-chain transaction.

**Grade:** Security 5, UX 4, Vendor-neutrality 5 (operator can choose any TEE *or* HSM), Operability 4, Composability 5. **Total 23/25** — same numeric score as Option 1, but covers more failure modes and serves a wider user base. **This is the recommended design.**

## §E: Cross-Layer Dependencies

What ops choices constrain other layers:

- **Identity layer** must standardize **BRC-52** (per SWARM-CONVERGENCE §1.2); ops needs `tee_attestation` and `binary_hash` extension fields. Operator-cert rotation cadence forces identity layer to support cert overlap windows (≥7 days).
- **Transport (MessageBox)** must propagate `traceparent` header end-to-end, MUST NOT log message bodies (only sizes + `mpc.execution_id`). Polling-mode transports cannot deliver real-time alerts → the spec must add a `transport.health` SLI and a fallback DM channel for refresh proposals.
- **Policy layer** must accept a `min_attestation` rule (require `tee_attestation` non-empty), and each cosigner-side policy must enforce *its own* refresh cadence and revocation list. The `StandardPolicyEngine` (rust-mpc) needs a new `RuleKind::RequireAttestation { format }`.
- **Federation**: cosigner replacement choreography needs a cross-operator BRC-52 cross-signature; the *new* operator's cert must be signed by `t-1` *existing* operators. Spec must define "operator quorum signature" distinct from "signing quorum."
- **Audit**: participation proofs must include `binary_hash` and `attestation_digest` to give on-chain provenance of *what code produced the signature*.

## Summary

Recommend Option 3 (hybrid hot-TEE + cold-HSM via resharing). Two new spec files (`16-operations.md`, `17-supply-chain.md`) and an update to `13-federation.md` §13.7. Distributed tracing uses OTel with a strict attribute whitelist enforced by a redaction linter — `traceparent` rides in `MessageEnvelope` map key 12. Refresh on 30-day routine cadence (RR-001) and 30-min IR cadence (IR-002), driven by a `RefreshOrchestrator` and a BRC-22 op-quorum acks topic. SLOs published per-operator and composed via a reference `sla.compose()` crate. Supply-chain triad is reproducible Cargo + Sigstore (cosign+Rekor) + SLSA L3 + optional TEE attestation, all linkable from the cosigner's BRC-52 cert. Cross-layer impact: BRC-52 needs `tee_attestation`/`binary_hash` fields; policy engine needs `RuleKind::RequireAttestation`; transport must propagate `traceparent`; audit/BRC-18 proofs include `binary_hash`. Production references cited per option: Fireblocks (co-signer + IR), Coinbase Custody/Anchorage (cold-tier), HashiCorp Vault (HA topology), AWS Nitro/GCP CVM/Azure CC (TEE), OpenTelemetry (tracing), Sigstore + SLSA + TUF (supply chain), Google SRE Workbook (SLOs/error budgets), Chaos Mesh + AWS FIS (chaos), Datadog APM + Honeycomb (tracing UX).
