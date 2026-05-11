# Conformance Test Suite

Both implementations (`bsv-mpc`, `rust-mpc`) MUST produce byte-equivalent results against the test vectors in this directory. This is the spec's enforcement mechanism — the spec is the contract, conformance tests prove it.

## Status

**Phase 0 / DRAFT.** Test vector files are placeholders until both implementations cross-validate them. ADR-0028 will lock the runner architecture once both stewards agree.

See [`OPEN-QUESTIONS.md` Q10](../OPEN-QUESTIONS.md) for the runner-ownership question.

## Structure

```
conformance/
├── README.md              This file.
├── test-vectors/          Language-neutral inputs + expected outputs.
│   ├── 01-cggmp24-pin.json
│   ├── 02-execution-id.json
│   ├── 03-brc42-invoice.json
│   ├── 04-session-id.json
│   ├── 05-message-envelope.cbor + .diag.txt
│   └── ...                Per spec section.
├── runner-rust/           Shared Rust runner (planned).
│   └── (loads vectors, asserts both implementations match.)
├── runner-bsv-mpc/        Wrapper that drives bsv-mpc against vectors.
└── runner-rust-mpc/       Wrapper that drives rust-mpc against vectors.
```

## Test categories

| Category | What it tests |
|---|---|
| Cryptographic primitives | ExecutionId, SessionId, BRC-42 invoice, BRC-78, BRC-31 sigs |
| Wire format | MessageEnvelope CBOR round-trip; canonical-CBOR tie-break |
| Protocol correctness | DKG produces matching joint pubkey; signing produces verifiable signature; presigning + signing produces 1-round signature |
| Identity / certs | BRC-52⊕ issuance, verification, CT inclusion, threshold-subject |
| Policy | PolicyManifest evaluation on canonical request set; verdicts byte-equivalent |
| Audit | Audit log Merkle root computation; STH signing; BRC-18 proof emission + verification |
| Federation | Cross-signed certs accepted by both verifiers; operator replacement |
| End-to-end | 1-bsv-mpc + 2-rust-mpc 2-of-3 DKG → mainnet signature |

## Vector format

JSON for human-readable inputs (hex strings for binary), CBOR for binary outputs:

```json
{
  "name": "execution-id-vector-A-sign-phase",
  "description": "Sign phase, joint key known",
  "inputs": {
    "domain_separator": "calhoun-binary-mpc",
    "version": 1,
    "algorithm_tag": 1,
    "phase_tag": 4,
    "session_id_hex": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "joint_pubkey_hex": "027a01a45fbef62f2f7a14fb4c1ad9e9b9f2f5d8c60c7a3a3c2f5e0bafe19f8cca"
  },
  "expected": {
    "execution_id_hex": "TBD"
  }
}
```

## Running the suite

(Once the runner architecture is locked.)

```bash
# Run conformance against bsv-mpc
cd conformance/runner-bsv-mpc
cargo test --release

# Run conformance against rust-mpc
cd conformance/runner-rust-mpc
cargo test --release

# CI runs both runners against the same vectors;
# any divergence fails the build.
```

## End-to-end mainnet test (the gate)

The single test that closes the v1 cross-impl gate:

1. Calhoun deploys bsv-mpc-service with one identity key.
2. Binary deploys rust-mpc backend + 2 cosigners with two identity keys.
3. Federation: Calhoun and Binary roots cross-signed.
4. Each side joins their own MessageBox; federation routes envelopes.
5. bsv-mpc identity discovers 2 rust-mpc cosigners via overlay.
6. 1-bsv-mpc + 2-rust-mpc 2-of-3 DKG succeeds.
7. Joint pubkey published, BSV address derived, address funded with 1000 sats.
8. BSV transaction signed via 2-of-3 ceremony.
9. Tx accepted by mainnet.
10. BRC-18 participation proof published and verifiable on-chain.
11. Each cosigner co-signs the others' STHs successfully.

Until this passes, both implementations are tentative.

## Failure attribution

When two implementations disagree on a vector:

1. Both teams reproduce locally to confirm.
2. Read the spec section together; identify which interpretation matches.
3. Whichever side's interpretation is wrong files a fix-up PR.
4. If the spec is ambiguous, file a PR clarifying the spec; cross-validate vectors against the new clarification.

This process is co-owned. Neither team is "the reference" — the spec is.
