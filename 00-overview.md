# 00 — Overview

**Status:** LOCKED
**Last updated:** 2026-05-10

## Purpose

This file is the spec's table of contents and orientation. The rest of the numbered files (`01-…` through `18-…`) are the spec proper.

## Document conventions

### Status line

Every numbered file begins with one of:

- **`Status: LOCKED`** — Both stewards have signed an ADR. Changes require an ADR-update with both-party sign-off.
- **`Status: DRAFT`** — One drafter has proposed; awaiting the other party's review/redline. Promotion requires both-party OK and an ADR.
- **`Status: PLACEHOLDER`** — File exists but content depends on an `OPEN-QUESTIONS.md` resolution.

### Normative language

This spec uses RFC 2119 terminology:

- **MUST** / **MUST NOT** — absolute requirement / prohibition.
- **SHOULD** / **SHOULD NOT** — recommended / discouraged unless particular reason.
- **MAY** — truly optional.

### Cryptographic notation

- `||` — byte concatenation.
- `bstr32` — fixed-length 32-byte CBOR byte string.
- `tstr` — UTF-8 text string.
- `u<N>` — unsigned integer of N bits, network/big-endian unless `_LE` suffix specifies little-endian.
- `bytes33` — compressed secp256k1 point (33 bytes, 02/03 prefix).
- `SHA256(x)` — SHA-256 over the byte sequence `x`. 32-byte output.
- `HMAC-SHA256(key, data)` — RFC 2104 with SHA-256. 32-byte output.

## Spec structure

| # | File | Status | Phase | Purpose |
|---|---|---|---|---|
| 00 | `00-overview.md` | LOCKED | 0 | This file. |
| 01 | `01-cggmp24-pin.md` | LOCKED | 0 | TSS protocol pin. cggmp24 ≥ 0.7.0-alpha.2 + `set_additive_shift` patch. |
| 02 | `02-execution-id.md` | LOCKED | 0 | Canonical ExecutionId formula + test vectors. |
| 03 | `03-brc42-invoice.md` | LOCKED | 0 | Canonical BRC-42 invoice canonicalization (lowercase + trim). |
| 04 | `04-session-id.md` | LOCKED | 0 | Canonical SessionId formula. |
| 05 | `05-message-envelope.md` | LOCKED | 0 | Canonical CBOR MessageEnvelope. |
| 06 | `06-transport.md` | DRAFT | 1 | Federated MessageBox + Iroh accelerator. |
| 07 | `07-brc31-auth.md` | DRAFT | 1 | Per-message BRC-31 mutual auth. |
| 08 | `08-identity.md` | DRAFT | 1 | BRC-52⊕ certificate profile. |
| 09 | `09-policy.md` | DRAFT | 1 | Canonical-CBOR PolicyManifest, 3-hook engine. |
| 10 | `10-audit.md` | DRAFT | 1 | Embedded Rekor, witness cosigning, BSV anchoring. |
| 11 | `11-fees.md` | DRAFT | 2 | Level 2 P2MS fee output, weekly settlement. |
| 12 | `12-discovery.md` | DRAFT | 3 | CHIP token capabilities + reputation. |
| 13 | `13-federation.md` | DRAFT | 2 | Cross-signed roots + operator replacement. |
| 14 | `14-conformance-tests.md` | PLACEHOLDER | 4 | Test vectors + suite both implementations run. |
| 15 | `15-notary-product.md` | DRAFT | 3 | Notary product tiers + SDK surface. |
| 16 | `16-operations.md` | DRAFT | 2 | SLI catalog, runbooks, OTel discipline. |
| 17 | `17-supply-chain.md` | DRAFT | 2 | Reproducible Cargo + Sigstore + SLSA L3. |
| 18 | `18-recovery.md` | DRAFT | 2 | Threshold resharing + encrypted backup + nested-MPC social recovery. |

## Phase definitions

| Phase | What it locks | Dependency |
|---|---|---|
| **0** | Cryptographic foundation (§01–05) | None. The cross-impl gate. |
| **1** | Security-critical layers (§06–10) | Phase 0 LOCKED. |
| **2** | Operational stack (§11, 13, 16–18) | Phase 1 substantially DRAFTed. |
| **3** | Product surface (§12, 15) | Phase 2 substantially DRAFTed. |
| **4** | Conformance suite (§14) | All other phases LOCKED. |

## Glossary

- **Calhoun / Binary** — the two implementation teams.
- **Coordinator** — the party in an MPC ceremony that orchestrates the rounds (elected per session, deterministic from `session_id mod n`).
- **Cosigner** — any party that holds a share. Spec is symmetric; "cosigner" and "party" are interchangeable.
- **Notary** — a specialty cosigner with a public policy posture, discoverable via overlay, monetized per-signature.
- **DKG** — Distributed Key Generation. CGGMP'24's keygen + auxinfo phases.
- **Presigning** — ceremony that produces single-use presignatures, consumed during signing for sub-RTT signature production.
- **Joint pubkey** — the on-chain BSV public key produced by DKG. Same address regardless of which threshold subset signs.
- **Identity key** — long-lived BRC-100 secp256k1 keypair used for BRC-31 mutual auth and BRC-52 cert subject. Distinct from the joint pubkey.
- **MessageBox** — a relay endpoint exposing the BSV `message-box-server` HTTP API. Federation: any operator runs one; cosigners pin theirs in CHIP token.
- **CHIP token** — a 5-field PushDrop output on the `tm_mpc_signing` BRC-22 overlay topic that advertises a cosigner's identity, capabilities, fees.
- **STH** — Signed Tree Head. The 32-byte root + tree size of an append-only Merkle audit log, signed by the cosigner.
- **TEE** — Trusted Execution Environment. Examples: AWS Nitro Enclave, AMD SEV-SNP, Intel TDX, Apple Secure Enclave.
- **HSM** — Hardware Security Module. Examples: AWS CloudHSM, YubiHSM2, Thales Luna.
- **Quorum profile** — a `(threshold, n, party_kinds)` configuration. Spec defines `Hot`, `HotPlusCold`, `ColdOnly`.

## Out of scope (for v1)

- BSV Schnorr / Taproot support (BSV consensus is ECDSA-only as of 2026; FROST3 is reserved as `algorithm_tag = 0x03` for v3).
- Post-quantum threshold signatures (research-grade only as of 2026).
- Custodial recovery (this network is non-custodial by construction).
- KYC/sanctions/compliance (spec defines protocol; per-Notary policy can layer compliance via the policy engine).
- BSV smart-contract fee covenant Level 3 (deferred to Phase 2 per BRC-mpc-fees; spec defines Levels 1 and 2 only for v1).
