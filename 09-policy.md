# 09 — Policy Engine

**Status:** DRAFT
**Version:** v1
**Phase:** 1
**Decided by:** ADR-0009 (proposed)
**Last updated:** 2026-05-10

## 09.1 Purpose

A policy engine for an MPC cosigner answers a single question deterministically and verifiably:

> *Given a signing request, the requester's identity, the proposed transaction, and the cosigner's signed policy manifest — is this signature operation authorized?*

A god-tier engine answers that question:
1. **Before any presigning material is consumed.**
2. **Identically across vendor implementations** (byte-equivalent on rule evaluation).
3. **With a signed, versioned, replayable trace** any third party can verify after the fact without re-running the ceremony.
4. **Per-cosigner, asymmetric, and composable** — cosigner #2 cannot be forced into cosigner #3's policy.

## 09.2 PolicyManifest format

The PolicyManifest is **canonical CBOR** (RFC 8949 §4.2), embedded as a CBOR `bstr` inside the cosigner's BRC-52⊕ certificate (§08, field `policy_hash` is SHA-256 of this CBOR).

```
PolicyManifest = {
  1:  u32,             // version (monotonically increasing per cosigner)
  2:  bstr32,          // policy_id = SHA-256(canonical CBOR of fields 3+)
  3:  bstr33,          // cosigner_identity (pins manifest to one cosigner)
  4:  bstr33,          // group_key (pins to one joint pubkey)
  5:  [+ Rule],        // rules (ordered, first-match-wins)
  6:  DefaultAction,   // action when no rule matches
  7:  u64,             // effective_after_ms (staged-rollout deny gate)
  8:  u64?,            // expires_after_ms (auto-rollback)
  9:  bstr32?,         // prev_policy_id (rollback chain, append-only)
  10: [+ bstr33],      // approver_keys (m-of-n approvers required to sign manifest update)
  11: [+ bstr72],      // approver_sigs (BRC-77 signatures over policy_id)
  12: bool             // dry_run (shadow-mode evaluation; decisions logged but not enforced)
}

Rule = {
  1:  tstr,            // protocol_pattern (glob: "*", "agent/*", "agent/api-*")
  2:  u64?,            // max_amount_sats
  3:  u32?,            // max_per_hour (sliding 1-hour window)
  4:  u64?,            // cumulative_daily_cap_sats
  5:  TimeWindow?,     // allowed_window (cron-style, UTC)
  6:  [* tstr]?,       // counterparty_allowlist (identity keys, hex)
  7:  [* tstr]?,       // counterparty_denylist
  8:  u64?,            // min_fee_sats (Notary requirement)
  9:  Jurisdiction?,   // ISO 3166 list, allow/deny
  10: ApprovalSpec?,   // require_approval (k-of-m if matched)
  11: AttestationSpec? // require_attestation (TEE/HSM/none)
}

DefaultAction = "Deny" / { "RequireApproval": [bstr33] } / "EscalateToHuman"

ApprovalSpec = {
  k: u32,                     // approvals required (k-of-m)
  eligible: [+ bstr33]        // approver identity keys
}

AttestationSpec = {
  formats: [+ tstr]           // "nitro_v1" | "sev_snp_v1" | "tdx_v1" | "any"
}

TimeWindow = {
  cron: tstr,                 // standard 5-field cron, UTC
  duration_secs: u32          // window length once cron fires
}

Jurisdiction = {
  allow: [* tstr]?,           // ISO 3166-1 alpha-2 codes
  deny: [* tstr]?
}
```

## 09.3 Three-hook engine

The policy engine MUST fire on **three hooks**, not one. Critical: rust-mpc's current `engine.rs:236-239` allows all presigning unconditionally; this is the bypass to fix.

| Hook | When | Bypass effect |
|---|---|---|
| `check_derivation` | BRC-42 child-key derivation | Wrong child key issued |
| `check_presigning` | Before each presig consumed (per-presig, not per-pool) | Presig burned; no signature emitted but resources spent |
| `check_signing` | Before final SIGN round | Signature emitted in violation |

## 09.4 Presig binding to policy_id

**Presigs MUST be bound to `policy_id` at generation time.** The presig's cggmp24 ExecutionId (§02) includes a 32-byte hash that incorporates `policy_id`; a presig generated under v=7 cannot be consumed under v=6.

This means policy rotations invalidate the presig stockpile. Implementations SHOULD generate new presigs immediately after a policy rotation to maintain pool depth.

The ExecutionId formula in §02 takes `algorithm_tag` and `phase_tag`; for presigning specifically, the ExecutionId additionally hashes `policy_id` into `payload_digest_32B` of the SessionId (§04.5).

## 09.5 Verdict types

```
Verdict = "Allow"
        | { "Deny": tstr }                      // reason string for audit
        | { "RequireApproval": ApprovalQuorum }
        | { "RateLimited": { retry_after_secs: u64 } }
```

`RequireApproval` returns a quorum spec; the coordinator MUST collect `k` approvals from `eligible` before proceeding.

`RateLimited` is returned when a sliding-window check would exceed the cap; implementations SHOULD return the time-until-next-budget-window in `retry_after_secs`.

## 09.6 Asymmetric per-cosigner enforcement

Each cosigner runs its own engine with its own manifest. A coordinator's manifest MUST NOT override a cosigner's verdict. Cosigners MAY enforce strictly tighter rules than the coordinator.

Example asymmetric 2-of-3:
- Cosigner A (user device): `{ default: "Allow" }` — permissive (the user is presumed legitimate).
- Cosigner B (hosted backup): `{ rules: [{ protocol_pattern: "agent/*", max_amount_sats: 50000, max_per_hour: 20 }], default: "Deny" }`.
- Cosigner C (Notary, high-value-only): `{ rules: [{ protocol_pattern: "treasury/*", max_amount_sats: 100_000_000, require_approval: { k: 1, eligible: [user_key] } }], default: "Deny" }`.

A signing request hits all three; if any returns `Deny`, the ceremony aborts (cryptographically — cggmp24 cannot proceed without all parties' signing-round messages).

## 09.7 Pattern matcher

`protocol_pattern` glob syntax (minimal):
- `"*"` — match any protocol_id.
- `"prefix/*"` — match any protocol_id starting with `prefix/`.
- `"prefix/middle/*"` — match any starting with `prefix/middle/`.
- `"exact"` — exact match.

No regex. No leading `*`. No multi-segment wildcards. Matcher MUST be a constant-time-in-pattern-length implementation; reject invalid patterns at manifest load time, not at evaluation time.

## 09.8 Manifest signing

The manifest is signed by `approver_keys` (m-of-n) via BRC-77 signatures over `policy_id`. The required signature count is implied by `approver_keys.len()` and a separate `min_approvals` field (TBD — DRAFT addition).

Signatures MUST be over the *canonical CBOR encoding* of fields 1-10 (`approver_sigs` itself is field 11; obviously not self-referential).

## 09.9 Versioning, rollout, rollback

- `version` is monotonic. Downgrades are forbidden — verifiers reject manifests with version less than the last-seen version for the same `cosigner_identity`.
- `effective_after_ms` allows staged rollout: a manifest published now is enforceable starting at this timestamp.
- `expires_after_ms` allows auto-rollback: an experimental manifest can self-deactivate.
- `prev_policy_id` forms an append-only chain: each manifest references the prior one. Auditors verify the chain.

## 09.10 Dry-run / shadow mode

When `dry_run = true`, the engine evaluates every request and **logs decisions to the audit log (§10) without enforcing them**. Allows operators to validate a new manifest before promotion to enforcement.

The audit log marks dry-run decisions distinctly so they don't confuse compliance review.

## 09.11 TOML transpiler (operator UX)

Operators MAY write policy in TOML (more readable than CBOR). The certifier MUST provide a transpilation tool: `mpc-policy-transpile <input.toml> -o <output.cbor>`. The TOML schema is a 1:1 mapping of the CBOR schema in §09.2.

Example TOML:
```toml
version = 7
cosigner_identity = "0299aa..."
group_key = "02bbcc..."

[[rules]]
protocol_pattern = "agent/*"
max_amount_sats = 50000
max_per_hour = 20

[[rules]]
protocol_pattern = "treasury/*"
max_amount_sats = 100_000_000
[rules.require_approval]
k = 1
eligible = ["02ccdd..."]

[default]
action = "Deny"
```

## 09.12 Cedar migration path

The CBOR schema is intentionally Cedar-shaped so a migration to Cedar (AWS Verified Permissions, Rust-native, Dafny-verified) is mechanical when Cedar's `wasm32-unknown-unknown [no_std]` story matures. See [`OPEN-QUESTIONS.md` Q5](OPEN-QUESTIONS.md) and ADR-0012.

## 09.13 Implementation notes

- rust-mpc has the closest-to-spec engine today (`crates/policy/`). Required deltas: add `min_fee_sats` rule, `RequireAttestation` rule kind, `cumulative_daily_cap_sats`, `allowed_window`, `counterparty_allow/denylist`, `jurisdiction`, k-of-m `ApprovalSpec`. Move `PolicyDecision` type to spec-defined `Verdict` enum.
- bsv-mpc has no policy crate. Port from rust-mpc as `mpc-policy-shared` crate.
- Both implementations MUST link the same evaluator implementation as a CI-gated conformance test (test vector run through both, byte-equivalent verdicts required).

## 09.14 Test vectors

In `conformance/test-vectors/09-policy.json`. Examples:
- Permissive policy + signing request → Allow.
- Rate-limited policy at cap → RateLimited.
- Whitelist miss → Deny.
- Min-fee mismatch → Deny.
- Approval-required → RequireApproval.
- Dry-run mode: same request → Allow but logged as dry-run.

## See also

- [`decisions/0009-canonical-policy-manifest.md`](decisions/0009-canonical-policy-manifest.md) — ADR.
- [`08-identity.md`](08-identity.md) — `policy_hash` binds to manifest.
- [`02-execution-id.md`](02-execution-id.md) — presig binding via ExecutionId.
- [`10-audit.md`](10-audit.md) — policy decisions are audit events.
- [`appendices/swarm-reports/C-policy-audit.md`](appendices/swarm-reports/C-policy-audit.md) — full design rationale.
