# Appendix C — Policy Engine + Audit

> Full report from the Policy & Audit zone agent of the god-tier-design swarm (2026-05-10).
> Preserved verbatim as supporting depth for [`§09-policy.md`](../../09-policy.md), [`§10-audit.md`](../../10-audit.md).

---

## §A. God-tier definition

A **policy engine** for an MPC cosigner answers a single question deterministically and verifiably: *given a signing request, the requester's identity, the proposed transaction, and the cosigner's signed policy manifest, is this signature operation authorized?* A **god-tier** engine answers that question (i) **before any presigning material is consumed**, (ii) **identically across vendor implementations** (Calhoun's Rust + Binary's Rust are byte-for-byte equivalent on rule evaluation), (iii) **with a signed, versioned, replayable trace** that any third party — including the *other* cosigners and the user — can verify after the fact without re-running the ceremony, and (iv) **per-cosigner, asymmetric, and composable** — cosigner #2 cannot be forced into cosigner #3's policy and vice versa. Audit is the persistence layer: every policy decision and every protocol-significant event lands in a tamper-evident, append-only log whose head is signed by the cosigner identity key, witness-co-signed by other cosigners, and **anchored to BSV**, so that "signed but not anchored" is a detectable lie.

**Precedents**: Fireblocks TAP encodes 8 fields per rule (initiator/source/destination/asset/amount/whitelist/time/approver) and is the institutional gold standard for rule expressivity; Cedar (AWS Verified Permissions, written in Rust, Dafny-verified, differentially fuzzed against the production engine) demonstrates that a small declarative DSL can be formally proven sound and runs in milliseconds; OPA/Rego is the most-deployed declarative policy engine in production at Capital One/Cloudflare/Pinterest but is heavyweight (Wasm sidecar, ~MB binary) and turing-incomplete only by convention; Cubist's CubeSigner explicitly rejects "set-menu" and "limited DSL" approaches, running Wasm policies inside a TEE because *policy is the security boundary*. For audit: Sigstore Rekor is the canonical append-only Merkle-tree transparency log with periodic signed checkpoints (STH); Trillian/RFC 6962 Certificate Transparency is its parent; immudb provides verifiable SQL/KV with `VerifiableGet` proofs; AWS CloudTrail is the production reference for immutable cloud audit.

## §B. Option 1 (RECOMMENDED) — Canonical-CBOR Policy Manifest + Rekor-style Transparency Log + BSV anchoring

**Policy.** Each cosigner publishes a **PolicyManifest** as canonical-CBOR (RFC 8949 §4.2), embedded as a CBOR `bstr` inside its BRC-52 certificate so it is signed-by-the-certifier and bound to the cosigner identity. The schema is a typed extension of rust-mpc's `AutoApproveRule` plus the gaps catalogued in convergence §1.3 — including `min_fee_sats`, `cumulative_daily_cap_sats`, `allowed_window`, `counterparty_allowlist/denylist`, `jurisdiction`, k-of-m `ApprovalSpec`.

Evaluation is a pure function `(manifest, request) -> Verdict` over canonical CBOR — both implementations compile to the same byte-for-byte decision table, which is the *test vector seam* the convergence doc demands. Crucially, the engine fires on **three hooks**, not one (this fixes `engine.rs:236-239` allowing all presigning):

| Hook | When | Worst-case effect of bypass |
|------|------|------------------------------|
| `check_derivation` | BRC-42 child-key derivation | Wrong child key issued |
| `check_presigning` | Before each presig consumed | Presig is burned; no signature |
| `check_signing` | Before the final SIGN round | Signature emitted in violation |

A presig is **bound to a policy_id at generation time** (added to cggmp24 `ExecutionId` per §1.4 — already a P0 fix). Thus a presig generated under v=7 cannot be consumed under v=6; rollbacks invalidate stockpile. This is the missing presig gate.

**Audit.** Each cosigner runs an embedded **Sigstore Rekor-style append-only Merkle log** (re-using Trillian's verifiable-log spec, RFC 6962). Every 60 seconds (or per-N-entries), the cosigner signs a **Signed Tree Head (STH)** and **publishes its hash to BSV** as a BRC-18 OP_RETURN under topic `tm_mpc_audit` — a single 32-byte root + 8-byte tree size + 64-byte signature, ~0.001¢ per epoch. This is the convergence §1.3 fix for `publish_proof = stub`: the participation proof becomes a *consequence* of the audit log existing on-chain, not a separate primitive. Other cosigners **co-sign each other's STH on a witness schedule** (Sigstore's "witness cosigning" pattern), which is what gives non-repudiation in the asymmetric setting — cosigner #2 cannot retroactively rewrite its log without cosigner #3 noticing on the next witness round.

**Verifying another cosigner's compliance after the fact** (prompt Q6): given (manifest_id, transcript_hash, request_hash), any party fetches the manifest from the certifier (BRC-52-signed), the audit entry from the peer's Rekor (Merkle-inclusion-proven against the on-chain anchor), and runs the pure evaluation function locally. Bytes match → verified. This is replay without re-ceremony.

**On-chain proof format (Q7).** Generalize BRC-18 by absorbing the bsv-mpc draft fields and adding the audit binding. Fixes the three convergence problems (weak session_hash, prefix-string conflict, missing version + BRC-77 sig):

```
OP_FALSE OP_RETURN
  "mpc-proof"  (single canonical prefix, locks 3-way conflict)
  0x02         (version — bumped because v1 was bsv-mpc-only)
  session_hash  = SHA256(joint_pubkey || ExecutionId || sighash)   ; per convergence §3
  audit_root    = STH at proof-emission time (32B)
  audit_index   = leaf index in Rekor (8B BE)
  agent_identity_33B
  participants_count_u8 + sorted_participants_33B*
  policy_id_32B
  fee_txid_32B (or zeros)
  timestamp_8B
  brc77_signature
```

**Grading (Option 1, /5):** Security 5 (deny-by-default; presig bound to policy_id; insider can't tamper because witness-cosigned + on-chain anchored; non-repudiation via BRC-77 sigs); UX 4 (CBOR is operator-hostile, but a TOML→CBOR transpiler keeps `config.example.toml` readable; "why" answer is a single inclusion proof); Vendor-neutrality 5 (each cosigner runs *its own* manifest, embedded in *its own* cert; coordinator cannot override); Operability 5 (versioned, expiring, staged-rollout via `effective_after_ms`, dry-run via shadow-mode flag, queryable Merkle log); Composability 4 (nested-MPC: child cosigner's manifest references parent's policy_id; modules are CBOR includes — but no formal composition algebra). **Total 23/25.**

## §C. Option 2 — Cedar (Rust-native, Dafny-verified) + immudb as audit substrate

**Policy.** Replace the imperative TOML/CBOR rule list with **Cedar policy files**. Cedar was designed for AWS Verified Permissions, is written in Rust, runs in milliseconds, has a Dafny formal model, and is differentially fuzzed against the production engine. Each cosigner ships its `.cedar` file in BRC-52 cert (hash-bound). Both implementations link the same `cedar-policy` crate, so evaluation is byte-identical *by construction* — no test-vector seam needed. The schema is also formally validated, so "max_amount_sats but no `<=`" is a load-time error, not a runtime surprise. This is what Cedar buys that hand-rolled CBOR can't: **soundness theorems**.

**Audit.** Use **immudb** as the local audit substrate. Every policy decision is a `VerifiableSet`; queries return Merkle inclusion + consistency proofs. immudb does ~1M tx/s, handles SQL queries (`SELECT * FROM audit WHERE party='02ab' AND ts > X`) which OPA-style log files can't, and has built-in tamper detection. The on-chain anchor is the same Rekor-style STH→OP_RETURN approach as Option 1.

**Trade-offs vs Option 1:** Cedar has 18-month delivery risk on `[no_std]` / wasm32-unknown-unknown (bsv-mpc-worker compiles to Wasm); Cedar's evaluator currently requires `std`. immudb is a separate process — a heavier op burden than the embedded Rekor of Option 1. But Cedar's correctness theorems and the SQL query surface for forensics are real wins for regulated Notary deployments.

**Grading (Option 2, /5):** Security 5; UX 5 (Cedar is human-readable, has IDE tooling, formal schemas catch typos); Vendor-neutrality 4; Operability 4; Composability 5. **Total 23/25** — different shape than Option 1.

## §D. Option 3 — OPA/Rego + Sigstore Rekor (federated transparency log)

The maximalist option: use upstream **OPA/Rego** as the policy DSL. Cost: OPA is ~30MB, doesn't run in CF Workers (bsv-mpc-worker constraint) — one cosigner runs OPA, the other runs a Rego→cggmp24-context shim, which is the same "two non-shared traits" problem the convergence doc already calls out at §1.3. **Grading: Security 4 (Rekor sound, but Rego decision logs aren't cryptographically bound to ExecutionId by default — needs custom binding); UX 5 (Rego ecosystem); Vendor-neutrality 3 (one engine = trust-the-OPA-version); Operability 5; Composability 5. Total 22/25.** Recommendation: keep as v2 path if/when CF Worker constraint relaxes.

## §E. Cross-layer dependencies

- **Identity**: PolicyManifest is embedded in BRC-52 cert. Forces convergence task #10 (deprecate `core::identity::Certificate`). Certifier MUST gate `/signCertificate` (§1.2 P1) — otherwise an attacker mints a cert with a permissive manifest.
- **Discovery**: CHIP token MUST advertise `policy_id` (32B) so a user discovering a Notary can fetch its manifest *before* DKG. Adds field 6 to bsv-mpc-overlay's `ChipCapabilities`.
- **Fees**: `min_fee_sats` rule lives in policy, not transport; the convergence-doc concern that "Notary advertises fee but cosigner doesn't gate on it" is resolved here (§1.5).
- **Transport**: PolicyManifest rotations are themselves audit events that flow over MessageBox — they need replay protection (the same nonce/timestamp pattern signing rounds use).
- **cggmp24 ExecutionId**: must include `policy_id` per phase to prevent presig replay across rotations (extends convergence §3.2 ExecutionId with a 4th input).

## §F. Recommendation

Ship Option 1 for the 30-day Notary MVP (CBOR + embedded Rekor + BSV anchor) — it satisfies all convergence-doc P0/P1 fixes, is wasm-clean for bsv-mpc-worker, and preserves the BRC-18 work that bsv-mpc has already validated. Re-evaluate Cedar (Option 2) when bsv-mpc-worker can drop the wasm-only constraint or when Cedar's `[no_std]` story matures; OPA (Option 3) is a v2.0 federation-friendly upgrade path.

## Sources

- Fireblocks Configure Policies / TAP rule fields
- Cedar policy language (AWS open-source) / Lean verification / differential testing
- Open Policy Agent docs / Capital One: Policy-Enabled Kubernetes
- Cubist programmable key management policies
- Coinbase open-sources cb-mpc
- Sigstore Rekor overview
- Trillian: Verifiable Data Structures
- RFC 6962: Certificate Transparency
- immudb (codenotary/immudb)

Internal references:
- `/Users/johncalhoun/bsv/mpc/rust-mpc/crates/policy/src/engine.rs`
- `/Users/johncalhoun/bsv/mpc/rust-mpc/crates/policy/src/cosigner_policy.rs`
- `/Users/johncalhoun/bsv/mpc/rust-mpc/crates/policy/src/rules.rs`
- `/Users/johncalhoun/bsv/mpc/rust-mpc/config.example.toml:137-150`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/crates/bsv-mpc-core/src/proof.rs`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/crates/bsv-mpc-overlay/src/proofs.rs:68-78`
- `/Users/johncalhoun/bsv/mpc/bsv-mpc/brc-drafts/brc-mpc-proofs.md`
