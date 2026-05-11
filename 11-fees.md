# 11 — Fees

**Status:** DRAFT
**Version:** v1
**Phase:** 2
**Decided by:** ADR-0011 (proposed)
**Last updated:** 2026-05-10

## 11.1 Three levels (per BRC-mpc-fees)

| Level | Mechanism | Trust model | Status |
|---|---|---|---|
| **L1** | Single P2PKH output to a settlement address per cosigner; off-chain accountant settles. | Trust the accountant. | Drafted, partial code. **NOT the spec default.** |
| **L2** | Bare P2MS multisig (t-of-n of cosigner identity pubkeys); cosigners co-sign settlement at epoch boundary. | Honest majority of cosigners (same as signing). | **Mainnet-validated POC 11. Spec default for v1.** |
| **L3** | sCrypt covenant enforces proportional distribution in Script. | Trustless. | Phase 2 (Runar Rust compiler), out of v1 scope. |

## 11.2 Default — Level 2 P2MS

The canonical v1 fee output is a bare `t`-of-`n` P2MS script of the participating cosigners' BRC-31 identity pubkeys, with `t` matching the ceremony's signing threshold.

Example for a 2-of-3 ceremony with cosigners holding pubkeys `02aa…`, `02bb…`, `02cc…`:
```
fee_output_script = OP_2  <02aa…>  <02bb…>  <02cc…>  OP_3  OP_CHECKMULTISIG
```

**This contradicts bsv-mpc's `fee_injector.rs` current default** (Level 1 split-P2PKH when `MPC_FEE_THRESHOLD` is unset). Spec mandates Level 2 P2MS as the default; bsv-mpc MUST update its `ProxyConfig` default to require `MPC_FEE_THRESHOLD` and produce P2MS unless explicitly opted out.

## 11.3 Per-signature fee schedule

- **Default fee floor:** 100 sats per signing operation, total.
- **Default fee:** 333 sats × number of nodes (e.g., 1000 sats for 3-node 2-of-3) — published in CHIP token (§12) `fee_sats` field.
- **Maximum:** unbounded; up to operator. Notary tier (§15) typically 1000-5000 sats.

The fee output is added to the user's transaction by the proxy/coordinator (see `bsv-mpc/crates/bsv-mpc-proxy/src/fee_injector.rs`):

1. After UTXO selection but BEFORE sighash computation.
2. Reduces change output by `fee_sats`.
3. Inserts `fee_output_script` at index appended after change.
4. If change < `fee_sats` after reduction, `createAction` returns an error with `INSUFFICIENT_FEE_BUDGET`.

The fee is bundled in the user's signed transaction — paid in BSV at sign-time, on-chain.

## 11.4 Settlement (epoch boundary)

By default, **weekly settlement** at midnight UTC Sunday:

1. Accumulated P2MS UTXOs from the past epoch are queried.
2. Participation proofs (§10) for the same epoch are queried from BRC-22 `tm_mpc_audit`.
3. `calculate_settlement(proofs)` (per `bsv-mpc-overlay/src/proofs.rs`) computes proportional distribution.
4. Cosigners co-sign a settlement transaction with one P2PKH output per recipient.
5. Settlement tx is broadcast.

For v1 MVP, settlement MAY be operator-driven (a manual command run weekly). Automation (cron-based) is OPTIONAL for v1, REQUIRED for v2.

For high-volume Notary deployments, daily settlement is RECOMMENDED. Per-tx settlement is RESERVED for institutional configurations.

## 11.5 Fee disclosure

Every `createAction` response MUST include a `mpc_fee` field:
```json
"mpc_fee": {
  "sats": 1000,
  "level": 2,
  "output_script_asm": "OP_2 <02aa..> <02bb..> <02cc..> OP_3 OP_CHECKMULTISIG",
  "settlement_topic": "tm_mpc_audit"
}
```

So that integrators (bsv-worm, Tauri client, etc.) can log the cost. Failure to disclose is a spec violation.

## 11.6 Cosigner-side fee enforcement (`min_fee_sats`)

The Notary advertises a fee in the CHIP token. **Cosigners MUST verify the proxy honored the advertised fee** by checking that the sighash includes a fee output to the expected P2MS script of expected sats.

This is a new policy rule (`min_fee_sats`, see §09.2 Rule field 8). Without this enforcement, a malicious proxy could omit the fee output. Mandatory for v1.

## 11.7 Forbidden

- L1 split-P2PKH as default. The BRC-mpc-fees draft says L2 multisig is recommended; the spec aligns with the draft (not with `fee_injector.rs`'s current default).
- Per-tx P2PKH split when `MPC_FEE_THRESHOLD` is set (it should produce P2MS).
- Skipping fee disclosure in `createAction` response.
- Cosigner accepting a signing request without verifying `min_fee_sats` policy rule (when present).

## 11.8 Implementation notes

- bsv-mpc `fee_injector.rs` — default mismatch with BRC draft. Update default to L2 P2MS (require `MPC_FEE_THRESHOLD`).
- bsv-mpc `bsv-mpc-overlay/src/proofs.rs::calculate_settlement` — implemented and mainnet-validated. Reuse.
- bsv-mpc `bsv-mpc-overlay/src/proofs.rs::publish_proof` / `query_proofs` / `count_proofs_by_node` — STUBBED. MUST implement (this is the §10 audit log integration).
- rust-mpc `crates/policy/src/rules.rs` — needs `min_fee_sats` field added to `AutoApproveRule`.

## 11.9 Test vectors

`conformance/test-vectors/11-fees.json`. Examples:
- L2 P2MS output construction for 2-of-3, 3-of-5.
- `calculate_settlement` proportional distribution from 100 mock proofs.
- Insufficient-change error path.

## See also

- [`decisions/0011-l2-p2ms-fee-default.md`](decisions/0011-l2-p2ms-fee-default.md) — ADR.
- [`09-policy.md`](09-policy.md) — `min_fee_sats` rule.
- [`12-discovery.md`](12-discovery.md) — `fee_sats` in CHIP token capability.
- [`15-notary-product.md`](15-notary-product.md) — Notary fee economics.
- bsv-mpc `brc-drafts/brc-mpc-fees.md` — full BRC draft.
