# 01 — TSS Protocol Pin

**Status:** LOCKED (pending ADR-0001 sign-off)
**Phase:** 0
**Decided by:** ADR-0001
**Last updated:** 2026-05-10

## 01.1 The protocol

The threshold signature scheme (TSS) for protocol-version `mpc-spec-v1` is **CGGMP'24** as published by Canetti, Gennaro, Goldfeder, Makriyannis, and Peled (ePrint 2021/060, refresh 2024). Curve is **secp256k1**. Security level is **128-bit** (`SecurityLevel128`).

## 01.2 Pin

Both implementations MUST use LFDT-Lockness `cggmp21` repository, branch `cggmp24/m`, at a commit ≥ **0.7.0-alpha.2** (or whatever commit first carries both patches below).

### 01.2.1 Required CVE patches

The pin MUST include patches for both:

- **CVE-2025-66016** — missing zero-knowledge proof check in cggmp24 signing path. Pre-patch versions are vulnerable to malicious peer constructions.
- **CVE-2025-66017** — presignature forgery via altered presig field. Pre-patch versions allow a malicious party to substitute presigs.

Source: GHSA-8frv-q972-9rq5 (LFDT-Lockness/cggmp21 security advisory, 2025).

**A release build MUST NOT depend on cggmp24 < 0.7.0-alpha.2.** CI of both implementations SHOULD enforce this via `cargo deny` rule.

### 01.2.2 BRC-42 additive shift

CGGMP'24 upstream exposes `set_derivation_path(path)` for SLIP-10/BIP-32-style HD derivation. BRC-42 derives offsets via HMAC-SHA256 of an invoice string, not via SLIP-10 paths, so the SLIP-10 entry point cannot supply the offset.

A 4-line public method `set_additive_shift(scalar)` is required to expose the existing internal `additive_shift` field directly. Until upstream merges:

- The fork lives at [`B1nary-Calhoun-Partnership/cggmp21-fork`](https://github.com/B1nary-Calhoun-Partnership/cggmp21-fork) on the partnership org. The default branch is `brc42-additive-shift`, rebased on upstream `cggmp24/m` at version `cggmp24-v0.7.0-alpha.4` — the latest CVE-patched release at time of writing. **The repo is currently private; an org admin needs to flip visibility to public** (Settings → Danger Zone → Change visibility) so Binary can clone without authentication. The upstream PR opened week 1 is the path to retiring this fork entirely.
- Both implementations MUST point at Calhoun's fork via Cargo `[patch."https://github.com/LFDT-Lockness/cggmp21"]` directive:
  ```toml
  [patch."https://github.com/LFDT-Lockness/cggmp21"]
  cggmp24        = { git = "https://github.com/B1nary-Calhoun-Partnership/cggmp21-fork", branch = "brc42-additive-shift" }
  cggmp24-keygen = { git = "https://github.com/B1nary-Calhoun-Partnership/cggmp21-fork", branch = "brc42-additive-shift" }
  key-share      = { git = "https://github.com/B1nary-Calhoun-Partnership/cggmp21-fork", branch = "brc42-additive-shift" }
  paillier-zk    = { git = "https://github.com/B1nary-Calhoun-Partnership/cggmp21-fork", branch = "brc42-additive-shift" }
  ```
- The fork MUST be rebased on top of the CVE-patched commit (§01.2.1).
- Calhoun opens an upstream PR to LFDT-Lockness/cggmp21 in Phase 0. Once merged and released, both implementations MAY drop the `[patch]` and pin upstream directly. ADR-0001 supersession will record the transition.

## 01.3 Cargo features

Both implementations MUST enable exactly the following cargo features for `cggmp24`:

| Feature | Why required |
|---|---|
| `curve-secp256k1` | The only curve in the BSV consensus signature path. |
| `hd-wallet` | Enables the `additive_shift` field used by `set_additive_shift()`. |
| `insecure-assume-preimage-known` | BSV sighashes are pre-hashed (SHA-256d) before the protocol sees them. The feature's "insecure" name applies to use cases where the protocol receives plaintext, not BSV's. Required to enable the 1-round signed-with-presig path. |
| `backend-num-bigint` | Required for both supply-chain hygiene (`rug` is GMP, LGPL — copyleft contamination) and WASM compilation (`rug` does not target `wasm32-unknown-unknown`). |
| `std` | Required by both implementations for the canonical CBOR + transport stack. `[no_std]` is not a v1 goal. |

Feature `hd-slip10` is OPTIONAL. Implementations MAY enable it for BIP-32-style derivation alongside BRC-42; the SLIP-10 codepath is not used at runtime if both parties call `set_additive_shift`.

Feature `rug` is FORBIDDEN.

## 01.4 Forbidden behaviors

- Disabling `enforce_reliable_broadcast` in any cggmp24 builder. The reliable-broadcast property is part of the UC-IA security argument.
- Skipping aux-info generation. An `IncompleteKeyShare` from keygen MUST be combined with `AuxInfo` from the auxinfo phase before any signing.
- Using cggmp24 < 0.7.0-alpha.2 in any release build (per §01.2.1).
- Using `Debug` formatting that prints scalar bytes. Key-material types MUST implement `Debug` as `<redacted>`.

## 01.5 Refresh, threshold change, scheme migration

CGGMP'24 supports **threshold resharing** primitives natively. Both implementations MUST expose:

- **Routine refresh** — same `(t, n)`, fresh polynomial, same joint pubkey. POC 13 pattern. 30-day cadence (see §16).
- **Party replacement** — same `(t, n)`, swap one party's identity, same joint pubkey. Required for cosigner replacement (§13.7).
- **Threshold change** — `(t1, n1) → (t2, n2)`, same joint pubkey. Required for `quorum_profile` transitions (§16).
- **Scheme migration** — same DKG output → different `algorithm_tag`. Required for v2 (DKLs23) and v3 (FROST) migrations. The joint pubkey is preserved; the signing protocol on top changes.

A scheme migration MUST be invoked by an ADR superseding ADR-0001 with explicit migration plan.

## 01.6 Side-channel discipline

- All scalar operations MUST use `generic-ec`'s constant-time backend (cggmp24 default; do not override).
- Error strings (e.g. `MpcError::Signing { source: ... }`) MUST NOT contain scalar bytes, commitments, or partial signatures. Error messages MAY contain `session_id`, `phase`, `round`, party indices, and counterparty identity keys.
- 30-day refresh cadence (§16, RR-001) bounds slow side-channel leaks.

## 01.7 Implementation notes

- bsv-mpc currently depends on the fork via submodule at `./cggmp21-fork`. Spec compliance requires the submodule URL be updated from `Calgooon/cggmp21-fork` to `B1nary-Calhoun-Partnership/cggmp21-fork` and the pointer bumped to the rebased commit (the rebase produced a new SHA on `brc42-additive-shift`).
- rust-mpc currently pins commit `117cab37f0c54e96ff3e1c2048c82d5864e90e74` on `cggmp24/m` (pre-CVE-patch). MUST update.
- bsv-mpc currently does NOT enable `insecure-assume-preimage-known` (per `bsv-mpc/crates/bsv-mpc-core/src/signing.rs:18`). MUST enable.
- rust-mpc currently DOES enable `insecure-assume-preimage-known`. No change required.

## 01.8 Verification

A verifier checking implementation conformance to this section SHOULD:

1. Inspect `Cargo.toml` and `Cargo.lock` for the cggmp24 git revision; confirm ≥ 0.7.0-alpha.2.
2. Confirm `[patch]` (if present) points to `B1nary-Calhoun-Partnership/cggmp21-fork#brc42-additive-shift`.
3. Confirm enabled cargo features match §01.3.
4. Run conformance test vector `01.cggmp24.set_additive_shift_round_trip` (see §14).

## See also

- [`decisions/0001-cggmp24-pin-past-cve-2025.md`](decisions/0001-cggmp24-pin-past-cve-2025.md) — the ADR.
- [`02-execution-id.md`](02-execution-id.md) — ExecutionId formula (consumes `algorithm_tag` to allow scheme migration).
- [`appendices/swarm-reports/D-protocol-crypto.md`](appendices/swarm-reports/D-protocol-crypto.md) — full design rationale.
