# 14 — Conformance Tests

**Status:** PLACEHOLDER
**Version:** v1
**Phase:** 4
**Decided by:** ADR-0014 (TBD)
**Last updated:** 2026-05-10

## 14.1 Why this is a placeholder

Conformance tests cement the spec but cannot exist without:

1. **Phase 0 LOCKED** — the test vectors for §01–§05 must be settled first.
2. **Both implementations agree on the test runner protocol** — JSON test files? Per-language runners? Shared CI?

Both prerequisites are open. See [`OPEN-QUESTIONS.md` Q10](OPEN-QUESTIONS.md).

## 14.2 Test categories (drafting outline)

When this section unblocks, it will cover:

| Category | What it tests | Who runs |
|---|---|---|
| **Cryptographic primitives** | ExecutionId, SessionId, BRC-42 invoice, BRC-78, BRC-31 sigs | Both implementations, byte-equivalent |
| **Wire format** | MessageEnvelope CBOR round-trip; canonical-CBOR tie-break | Both implementations, byte-equivalent |
| **Protocol correctness** | DKG produces matching joint pubkey; signing produces verifiable signature; presigning + signing produces 1-round signature | Cross-implementation pairs |
| **Identity / certs** | BRC-52⊕ issuance, verification, CT inclusion, threshold-subject | Both implementations |
| **Policy** | PolicyManifest evaluation on canonical request set; verdicts byte-equivalent | Both implementations |
| **Audit** | Audit log Merkle root computation; STH signing; BRC-18 proof emission + verification | Both implementations |
| **Federation** | Cross-signed certs accepted by both verifiers; operator replacement | Cross-implementation |
| **End-to-end** | 1-bsv-mpc-party + 2-rust-mpc-cosigners 2-of-3 DKG → mainnet signature | Cross-implementation, mainnet |

## 14.3 Test runner architecture (proposed)

```
conformance/
├── test-vectors/        Language-neutral JSON / CBOR / hex
│   ├── 01-cggmp24-pin.json
│   ├── 02-execution-id.json
│   ├── 03-brc42-invoice.json
│   ├── 04-session-id.json
│   ├── 05-message-envelope.cbor
│   ├── ...
├── runner-rust/         Shared Rust runner (shipped as a binary)
│   └── (loads vectors, asserts both implementations match)
├── runner-impl-A/       Wrapper that drives bsv-mpc against vectors
└── runner-impl-B/       Wrapper that drives rust-mpc against vectors
```

CI runs both runners against the canonical vector set. A vector that one implementation cannot reproduce blocks the LOCKED status of the corresponding spec section until reconciled.

## 14.4 End-to-end mainnet test (the gate)

The gate for "Phase 0 + Phase 1 fully proven" is:

```
Setup:
  - Calhoun deploys bsv-mpc-service (or proxy + KSS) with one identity key.
  - Binary deploys rust-mpc backend + 2 cosigners with two identity keys.
  - Federation: Calhoun and Binary roots cross-signed.
  - Each side joins their own MessageBox; federation routes envelopes.

Test:
  1. Discovery: bsv-mpc identity discovers 2 rust-mpc cosigners via overlay.
  2. DKG: 1-bsv-mpc + 2-rust-mpc 2-of-3 DKG succeeds.
  3. Joint pubkey published, BSV address derived, address funded with 1000 sats.
  4. Sign: BSV transaction signed via 2-of-3 ceremony.
  5. Broadcast: tx accepted by mainnet.
  6. Audit: BRC-18 participation proof published and verifiable on-chain.
  7. Witness cosigning: each cosigner co-signs the others' STHs successfully.

Pass criteria:
  - Mainnet TXID confirmed.
  - All audit invariants hold.
  - Both implementations log byte-equivalent events for the same ceremony.
```

This is the milestone that closes the v1 cross-impl gate. Until this passes, both implementations are tentative.

## 14.5 To be fleshed out

- Language-neutral vector format (JSON for hex, CBOR for binary, both).
- Runner protocol (stdin/stdout JSON contract).
- CI integration (GitHub Actions reusable workflow).
- Failure-attribution rules (which side gets the bug when bytes differ).
- Performance benchmarks (latency targets per §06.10).

These will be filled in once Phase 0 LOCKED and both implementations have agreed on the runner architecture.

## See also

- [`OPEN-QUESTIONS.md` Q10](OPEN-QUESTIONS.md) — conformance test ownership.
- All §01–§13 sections — each has a `Test vectors` subsection that points here.
