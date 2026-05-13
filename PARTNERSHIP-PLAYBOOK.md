# Partnership Playbook — Calhoun ↔ Binary — 2026-05-13

> **Audience:** John (Calhoun-side: spec steward + bsv-mpc implementor), Mitch (Binary-side: spec steward), Ishaan (Binary-side: rust-mpc implementor).
> **Purpose:** the operational handbook for working through M1 (2026-05-29 cross-impl signing demo) → M2 (2026-06-12 Notary MVP) → v2 → v3, **without going in different directions** and without scheduled meetings.
> **Operating rule:** strictly async. Slack + GitHub + code + proofs + tests. No bridge calls / no syncs / no handoff meetings. (Sev-1 IR war-room Slack threads are async-but-real-time — that's not a meeting.)
> **Synthesized from:** 4 collab-readiness swarm agents (modularity / trackability / convergence / divergence-risk), each output at `~/bsv/mpc/swarm-2026-05-13/collab-*.md`.

---

## Quick-reference: what each person works on this week

### John (Calhoun side) — ship these independently, no Ishaan dep

Highest priority (M1-critical):
- **#B1** Delete duplicate `compute_invoice` in `bsv-mpc-core/src/hd.rs:175-183`; route through `bsv-rs::KeyDeriver::compute_invoice_number`. ~30 LOC. (ADR-0002, §03.9)
- **#B3** Swap ad-hoc `WireMessage`/`RoundMessage` for canonical CBOR envelope + canonical ExecutionId + SessionId. Pure wire layer; conformance vectors already exist for §02/§04/§05. (ADRs 0003-0005)
- **#B5** Flip `insecure-assume-preimage-known` cargo feature.
- **ADR-0037 impl** in `bsv-mpc-core/src/transport/envelope.rs` — byte-equivalent re-encode check (M1-critical wire-compat). Hand-author vector `05-message-envelope-diff` is Calhoun-side (already in `MPC-Spec/conformance/test-vectors/`).
- **#J1** Transfer `bsv-mpc` + `cggmp21-fork` to `B1nary-Calhoun-Partnership` org. Flip both public.

Parallel (M2 / v1.5, but can start now):
- **#B6/B7** PushDrop STH chain + audit-identity keypair (§10.5 / ADR-0019).
- **#B8** Chase cggmp21 PR #200 maintainer.
- **#B10** Scrub stale THREAT-MODEL + fix silent-skip e2e.
- **#R1 / #W1** API-stability hold on bsv-rs `KeyDeriver` + bsv-wallet-toolbox-rs `ProtoWallet` BRC-2 `mpcpresig` path.
- Stand up Slack channels + GitHub Project + CI (per §"Tooling" below). ~2 days of work; once landed, ~30min Monday for the rest of the M1 sprint.

Blocked, waiting on Ishaan:
- **#B4** Presig lifecycle in bsv-mpc (~600-900 LOC; ADR-0030 §06.15-§06.21). **Blocked until #M9 lands** — Ishaan must byte-lock `06-presig-bundle-encryption.json`. This is the longest sequential chain to M1.

### Ishaan (Binary side) — ship these independently, no John dep

Highest priority (unblocks John's #B4 → critical-path M1):
- **#M9** Run rust-mpc's reference impl against the pinned inputs in `06-presig-bundle-encryption.json` and byte-lock the three `__TBD-by-ref-impl__` ciphertexts. Inputs already canonicalized; this is "run + paste."

M1 wire-compat (Phase 0):
- **#M1** Pin cggmp24 ≥ 0.7.0-alpha.2 + `[patch]` directive (ADR-0001).
- **#M2** Swap ad-hoc ExecutionId/SessionId/envelope for canonical in `rust-mpc/dkg.rs:154` etc. (ADRs 0003-0005)
- **ADR-0037 impl** in `rust-mpc/crates/transport/` — byte-equivalent re-encode check.

M2 / v1.5:
- **#M3** Rustdoc cross-refs to ADR-0030 in `crates/brc42/src/{presig_encryption,presignature}.rs` + `crates/coordinator/src/presign.rs`.
- **#M4** Progressive deprecation of `core::identity::Certificate` → BRC-52⊕.
- **#M5** Move Lagrange combine into `mpc-brc42`.
- **#M6** Certifier hardening (BRC-31 gate, OsRng nonce, sqlite).
- **#M7** Emit `audit_identity` field in BRC-52⊕ certs (§08).
- **#M8** PushDrop STH chain on rust-mpc side (§10.5 / ADR-0019).
- **#BSDK1/2** Binary SDK API-stability hold + conformance-vector pass.

### Mitch (Binary steward) — review-and-sign-off only (no coding per his 2026-05-12 note)

- ADR sign-off pass on **0030-0049** (19 ADRs). Phase 0 critical path: **0001-0006 + 0032 + 0037** by 2026-06-12.
- Confirm or push back on the 12 design-choice resolutions in `CHANGES-PROPOSED.md` (Calhoun-side resolved; Binary-side confirmation needed).
- Standing review of any cross-impl spec PR (especially `wire-compat` labeled).

### Joint — requires both sides to land

- **ADR-0044 wallet-renderer canonicalization** — co-authored design doc; **hard bottleneck for ADR-0032** (M1-critical). Initiate as a Calhoun-side draft PR; Ishaan reviews; converge async in PR comments. M1-DRAFT acceptable if full intent-kind coverage slips to 2026-06-12.
- **M1 demo ceremony (#B9 + #M10):** 1 bsv-mpc + 2 rust-mpc cosigners deployed; 2-of-3 mainnet signature emitted; both impls log to shared BRC-22 audit topic. 2026-05-29.
- **#S3 cross-stack conformance CI:** both runners must exist for the GitHub Action to mean anything.

---

## Critical paths

### To M1 demo (2026-05-29)

```
Ishaan: #M9 byte-lock 06-presig-bundle-encryption.json
   ↓
John: #B4 implement presig lifecycle in bsv-mpc (~600-900 LOC)
   ↓
John: #W1 verify ProtoWallet BRC-2 mpcpresig path produces matching ciphertext
   ↓
John: #B9 deploy 1 bsv-mpc cosigner

In parallel:
Ishaan: #M10 deploy 2 rust-mpc cosigners
Both: ADR-0037 implementation + #S3 conformance CI green
Both: M1 mainnet 2-of-3 ceremony
```

**Longest single-blocker chain:** #M9 → #B4 → #B9. Mitigation: #M9 inputs are pinned today; "run + paste" effort.

**ADR-0044 escape hatch:** payment-intent-only renderer ships first; full intent-kind coverage by Phase 0 lock 2026-06-12. M1 can run with `request_view_hash` binding for payment intents only.

### To M2 / Notary MVP (2026-06-12)

```
M1 landed
   ↓
Phase 0 sign-off (8 ADRs: 0001-0006 + 0032 + 0037)
   ↓
ADRs 0031, 0033, 0034, 0035 (UI/UX contracts) impl
ADRs 0038, 0045, 0046 (recovery KDF + mapped-memory + Rekor caching)
ADR-0039 STH multi-source + ADR-0047 jittered timers
ADR-0042 IR runbooks markdown stubs → fleshed runbooks
ADR-0049 OOB cert revocation
   ↓
HackerOne managed VDP stood up
Trail of Bits joint pen-test scheduled (4-6 weeks; v1.5)
Public Notary cosigner: CHIP + policy manifest + STH chain live
   ↓
M2 launch 2026-06-12
```

---

## Tooling — keep it super simple

3-person partnership. Native GitHub features + 1 Slack channel + 1 CI workflow. No enterprise-grade scaffolding.

### Slack

**1 channel** (existing partnership channel, e.g. `#mpc-spec` or wherever the three of you already talk). If a Sev-1 IR happens and one channel feels too noisy, spin up a second channel ad-hoc for the war-room. That's it. No channel tree, no GitHub-bot firehoses, no auto-threading webhooks.

### GitHub Issues

Native GitHub Issues. Simple labels: `m1`, `m2`, `phase-0`, `wire-compat`, `signoff:calhoun`, `signoff:binary`. No Project boards with column lifecycles, no mandatory label taxonomies enforced by lint.

Status check = open GitHub, look at the issue list filtered by `m1` or `m2`. That's the dashboard.

### CI

**1 workflow:** `.github/workflows/conformance.yml`. Runs on every PR + push to main. Reads `conformance/test-vectors/*.json` and asserts byte-equality on round-trip across both stacks (via git-submodule pin or whatever's easiest). Fails the PR if any vector mismatches.

That's IT. No drift-watch / fuzz-corpus / Monday-digest / sign-off-bot / spec-pr-review workflows unless we hit concrete pain that those would solve.

### ADR sign-off

Native GitHub PR review approvals. Both stewards approve = signed off. Use a simple ADR-PR title convention `[ADR-XXXX] <title>` so it's greppable; that's all the process needed.

Status of ADR sign-off lives at the top of each ADR file (`## Sign-off` section with steward checkboxes filled in via PR commits, not bots). Audit trail = git log on the ADR file.

### Drift detection

The **conformance vectors are the drift canary.** If both stacks pass the conformance vectors, we're not drifting on wire format. If not, the CI fails.

For tunable drift (burn-rate, KDF profile, etc. — the 6 self-declared `/capabilities` knobs from ADR-0030/0034/0038/0040/0046/0047): trust operators to honor the spec. If we see weird production behavior, we'll add a check then. Don't pre-build infrastructure for problems we don't have.

---

## How we don't drift

### The conformance vectors ARE the drift detector

That's the primary mechanism. Both stacks run them in CI on every PR. Byte-mismatch = drift = fail. Simple.

### `/capabilities` tunables self-declaration (the only secondary mitigation)

Each cosigner's `/capabilities` JSON declares 6 tunables explicitly so operators commit publicly to their choices:

```json
{
  "burn_rate_algorithm": "baseline",          // per ADR-0030 §11
  "reverify_burn_threshold": 1000,             // per ADR-0040
  "reverify_time_cadence_minutes": 15,
  "rekor_cache_validity_seconds": 86400,       // per ADR-0046
  "kdf_profile": "server",                     // per ADR-0038
  "denial_ux_mode": "categorized"              // per ADR-0034
}
```

No automated diff job. If something behaves weird in production, we look at the capabilities JSONs and trace it. Don't pre-build the drift-watch infrastructure.

### Per-vector ownership matrix (per Q10 / ADR-0028 resolution)

Whoever has the reference implementation byte-locks; the other independently re-verifies. **No vector lands without two independent re-derivations.**

| Vector | Byte-lock author | Re-verifier |
|---|---|---|
| `02-execution-id` | Calhoun | Calhoun (Rust cross-validate) |
| `03-brc42-invoice` | Calhoun | Calhoun + Ishaan |
| `04-session-id` | Calhoun | Calhoun |
| `05-message-envelope` | Calhoun | Calhoun (3 CBOR paths) |
| `05-message-envelope-diff` | Calhoun (8 categories hand-authored) | Ishaan |
| `06-presig-bundle-encryption` | **Ishaan** (rust-mpc is ref impl) | Calhoun |
| `09-rendered-text` | Calhoun (ADR-0044) | Ishaan |
| `09-approval-quorum-flow` (NEW) | co-authored | both |
| `09-policy-verdict-matrix` (NEW) | **Ishaan** (rust-mpc closest) | Calhoun |
| `09-policy-manifest` (NEW) | Calhoun | Ishaan |
| `10-audit-entry` (NEW) | Calhoun | Ishaan |
| `10-sth-pushdrop` (NEW) | Calhoun | Ishaan |
| `10-audit-anomaly` (NEW) | Calhoun | Ishaan |
| `06-presig-bundle-cbor` (NEW) | Calhoun | Ishaan |
| `18-recovery-kdf` | Calhoun | Ishaan |

**8 new vectors to author** in M1 → M2 window. Highest priority: `09-approval-quorum-flow` (gated on ADR-0044 co-authoring) and completing `06-presig-bundle-encryption` ciphertext.

### Implicit-assumption locks applied 2026-05-13

Per divergence-risk swarm, 5 MAY→MUST tightenings applied:

- **ADR-0030 §11 burn-rate algorithm** → baseline is normative unless operator publishes deviation in CHIP capabilities (with public URL).
- **ADR-0040 §1 re-verify cadence** → per-profile table (edge 500/15min, server 1000/15min, mobile 100/30min). Loosening forbidden; tightening allowed.
- **ADR-0034 denial UX** → categorized enum OR verbatim; silent denial non-conformant; mode declared in capabilities.
- **§16.1.2 operator → profile binding** → no silent flipping; ADR or m-of-n approval required.

Pending tighten: ADR-0030 `policy_id` field MUST (already implied), ADR-0038 mobile-constrained scrypt fallback chain (Q59 partially resolved).

---

## Decision discipline (simple)

1. Hit ambiguity? Open a GitHub issue (`open-question` label) with the question + your recommended resolution. Optionally drop a link in Slack.
2. Other steward responds in the issue (or Slack thread). Within a couple days for blocking; whenever for non-blocking.
3. Once aligned, open an ADR PR (`decisions/TEMPLATE.md`, title `[ADR-XXXX] <title>`).
4. Both stewards approve the PR via native GitHub review. Squash-merge. The resolved issue closes automatically via PR `Closes #N`.

That's it. No bots, no sticky comments, no SLA timers. If something's blocking, the open issue + a Slack ping is enough.

---

## Sev-1 Incident Response (the one place async-real-time matters)

IR-005 (certifier-key compromise) and IR-008-with-broadcast (presig-pool poisoning with bad sig on mainnet) require coordinated cross-operator action. **NOT a scheduled call — a real-time Slack thread in `#mpc-spec-ir-bridge`.**

Procedure (per §13.15 + §16.5.5/§16.5.8):

1. **T+0:** Detection signal posted to `#mpc-spec-ir-bridge`. PagerDuty/Opsgenie routes to both stewards simultaneously.
2. **T+5min:** Both stewards (and retained external advisor per §16.16.2 when relevant) acknowledged in thread with initial assessment.
3. **T+15min:** Thread has classification (which IR class), affected scope, and proposed mitigation PR.
4. **T+30min:** Mitigation PR open + reviewed; revocation/rotation/hotfix landing.
5. **T+60min:** Resolution: PR merged + `AuditEntry` published + Slack postmortem thread started.
6. **T+24h:** Postmortem PR (per §16.12) on `tm_mpc_postmortems` overlay.

War-room thread is mid-bandwidth — every 5-15min status update is normal. NOT a call.

---

## Single-point-of-failure mitigations

### John (Calhoun-side: spec steward + bsv-mpc implementor) — **biggest SPOF**

If unavailable >2 weeks, bsv-mpc pauses AND spec edits stall. Mitigations:

- **Make ALL knowledge live in spec/PR comments/code/docs** — no John-only knowledge. Per the no-meetings rule, this is already forced.
- **bsv-mpc backup implementor** — identified before v1.5 launch.
- **Mitch can cover spec edits** during John absence (mutual cross-coverage on the steward role).

### Mitch (Binary steward) — sign-off SPOF

If unavailable >2 weeks, 19 ADRs (Proposed → Accepted) stalls; wire-compat ADRs 0032/0037/0044 block M1.

- **Ishaan non-wire backup** — Ishaan can sign off on non-wire-compat ADRs (governance, ops, supply-chain) during Mitch absence.
- **Governance README** names backup signer with date-of-effect.

### Ishaan (rust-mpc implementor)

If unavailable >2 weeks, rust-mpc stalls; cross-impl signing slips. Mitigations:

- **Knowledge silo lock**: ADR-0030 reference impl docs MUST be in spec, not Ishaan-only — explicit (raising line 126 of ADR-0030 from SHOULD→MUST is pending; currently advisory).
- Mitch can cover small fixes; large impl pauses.

### CISO recusal cascade

§16.16.3 specifies recusal when active CISO's stack is the IR target. Overlapping vacation → external advisor (§16.16.2) is sole IR actor. **Lock: cross-published calendars in `#mpc-spec-general`, no >3-day overlap.**

---

## Spec text changes still pending

After today's 3 swarm loops + this collab-readiness pass, these remain outstanding:

- **8 new conformance vectors** (per §"Per-vector ownership matrix" above). Highest priority: `09-approval-quorum-flow`, `06-presig-bundle-cbor`, complete `06-presig-bundle-encryption` ciphertext.
- **5 hand-author REJECTED vectors** in `05-message-envelope-diff` are done; the 8 categories are byte-locked. Independent re-verification by Ishaan is the open item.
- **CONTRIBUTING.md addition**: "Did this ADR add/change any field that appears in a test vector? If yes, the vector JSON MUST be regenerated in this PR."
- **`decisions/STATUS.md` generated tracker** — auto-update by `adr-signoff.yml`; needs initial scaffolding.
- **`conformance/runner-trait/` Rust crate** — 10-method trait per `collab-convergence.md` §4. Per-impl runners (`runner-bsv-mpc/`, `runner-rust-mpc/`) consume.
- **`conformance/otel-lint/` shared regex corpus** for telemetry standardization (per `collab-divergence-risk.md` §4).
- **`conformance/fuzz-corpus/`** — shared adversarial CBOR/BRC-78 corpus (Q26 resolution: co-owned, weekly CI).
- **`mpc-config-schema.json`** — both stacks validate against shared schema for config-file structure (env vars, default values, secret locations).

---

## What success looks like

- **By 2026-05-29**: 1 bsv-mpc + 2 rust-mpc cosigners produce a verified 2-of-3 mainnet signature; both stacks log to shared BRC-22 audit topic; M1 demo public.
- **By 2026-06-12**: Phase 0 lock (8 ADRs signed off); v1.5 ADRs in implementation; at least one publicly-discoverable Notary live (Calhoun-side, Binary-side, or both).
- **By v2 (3-6 months out)**: SOC2 Type II audit (Schellman) kicked off; HackerOne VDP live; Trail of Bits joint pen-test report in hand; Pro tier marketplace beta.

**Failure modes we won't get into:**
- Going in different directions on wire format (caught by conformance vectors + drift-watch).
- Going in different directions on operational tunables (caught by `/capabilities` daily-diff CI).
- Knowledge silos (forced into spec text by no-meetings rule).
- Scope creep (CHANGES-PROPOSED.md positions are bounded; M1 doesn't slip).
- Phase 0 sign-off delays (sticky PR comment makes it visible).

---

## Maintenance of this playbook

This playbook is itself spec text. Updates via PR; both stewards sign off (the playbook applies to both sides). Re-review quarterly (or after any swarm pass that touches operational structure).

The 4 collab-readiness swarm reports remain at `~/bsv/mpc/swarm-2026-05-13/collab-*.md` for reference — full detail beyond this synthesis.
