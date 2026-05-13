# ADR-0035: SDK surface v1.1 — add `listSignedActions` + `approve`

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — UI/UX F1 (component of).

## Context

§15.4 currently lists 5 SDK methods: `discover`, `onboard`, `sign`, `replaceNotary`, `recover`. The 5-method count is too narrow for the spec's own primitives:

- **Audit trail (§10, ADR-0019)** publishes a PushDrop STH chain. The "what did my wallet sign last week?" UX is a first-class wallet feature but has no SDK method. Sigstore Rekor inclusion-proof viewer is the precedent.
- **Approval quorum (§09.5, ADR-0032)** delivers `RequireApproval` to eligible approvers. Approver-side has no SDK method to participate; they're expected to "go through the BRC-100 wallet" with no spec contract.

Without `listSignedActions` and `approve` as first-class methods, two implementations will invent divergent solutions to the same product needs.

## Decision

Expand `mpc.*` SDK surface from 5 to 7 methods. Add:

### 6. `mpc.listSignedActions(opts)`

```rust
let entries = mpc::list_signed_actions(ListOpts {
    since: u64,                        // Unix timestamp, secs
    joint_pubkey: &PublicKey,          // filter
}).await?;
```

Returns the wallet's view of its STH-anchored signing history (per ADR-0019 + §10.5). Each entry includes:
- `audit_index` — Merkle leaf index
- `audit_root_at_signing` — STH root at time of signing
- `request_view_hash` — per ADR-0032 (or None for pre-ADR-0032 signings)
- `sighash`
- `joint_pubkey`
- `timestamp_secs`
- `inclusion_proof: Vec<bstr32>` — Merkle inclusion proof against `audit_root_at_signing`
- `sth_chain_pointer` — UTXO ref to the STH PushDrop on `tm_mpc_audit`

The wallet MAY locally cache + offline-display; verification against the published STH chain is queryable on demand.

Per Q18: subset of sighashes / policy_ids exposed publicly vs privately is an open question. Default: only display in the wallet's local UI; do NOT publish a directory of "this user signed X" without explicit user opt-in.

### 7. `mpc.approve(opts)`

```rust
mpc::approve(ApproveOpts {
    session_id: SessionId,
    decision: Decision,           // Allow | Deny(reason)
}).await?;
```

Invoked when an approver receives an approval-request envelope (per ADR-0032 §09.5.1). Produces the BRC-77 signature over `request_view_hash || "mpc-approval-v1" || session_id` and emits via §06 envelope back to the requesting coordinator.

WebAuthn-bound approvers (per §08.11) MUST call `approve()` after WebAuthn `userVerification=required` gesture; the `clientDataJSON.challenge` field is `request_view_hash`.

## Rationale

- **Audit-trail UX is a product feature.** Users want to see their signing history. Without an SDK method, every integrator builds their own; cross-wallet portability suffers.
- **Approver UX is symmetric to requester UX.** A 2-of-3 approval flow needs both sides to be spec'd. Without `approve()`, the approver side is silently per-implementation.
- **Forward-compatibility.** Adding methods at v1.1 (vs. waiting for v2) keeps the SDK clean. The 5-method count is a number, not a constraint.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Implement `mpc.listSignedActions()` against local audit log + cross-check against `tm_mpc_audit` STH chain.
- Implement `mpc.approve()` per ADR-0032 §09.5.1 semantics.
- Update SDK documentation + reference UI.

### `MPC-Spec`

- §15.4 expanded to 7 methods (already applied).
- §15.4 includes Rust + TS code examples (already applied).
- Q18 added (audit-trail privacy).

## Alternatives considered

- **Don't add — let integrators invent.** Rejected per the "two products" risk.
- **Add only `approve` (defer listSignedActions to v2).** Considered but the audit-trail UX is part of the v1 product promise; deferring sends the wrong signal about audit being a real feature.
- **Add 4 or more methods (signed-tx broadcast wrapper, recovery-health query, etc.).** Some are valid candidates but warrant their own ADRs; this one stays focused on the two highest-leverage gaps.

## M1 dependency

**v1.5.** Not M1-blocking. Lands in M2 window.

## See also

- Spec: [§15.4](../15-notary-product.md)
- ADR-0019 (PushDrop STH chain — `listSignedActions` consumer)
- ADR-0032 (`request_view_hash` — `approve` participant)
- 2026-05-13 swarm: UI/UX F1

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
