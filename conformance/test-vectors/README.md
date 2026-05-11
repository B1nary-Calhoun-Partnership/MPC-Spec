# MPC-Spec — canonical test vectors

This directory holds the byte-locked test vectors for Phase 0 of the spec. Every byte in every JSON file below was produced by code that is committed alongside, and every byte has been cross-validated by **at least two independent implementations** before being committed. The conformance gate (§14) requires both `bsv-mpc` and `rust-mpc` to reproduce these values byte-for-byte.

## Files

| File | Spec ref | What's locked |
|---|---|---|
| `02-execution-id.json` | [§02](../../02-execution-id.md) | 3 ExecutionId vectors (sign / keygen-zero-carve-out / refresh) |
| `03-brc42-invoice.json` | [§03](../../03-brc42-invoice.md) | 10 BRC-42 spec vectors (5 priv + 5 pub) + 3 stress vectors |
| `04-session-id.json` | [§04](../../04-session-id.md) | 2 SessionId vectors (sign / DKG with on-chain anchor) |
| `05-message-envelope.json` | [§05](../../05-message-envelope.md) | 1 full envelope vector (sign-phase, all 12 fields populated) |
| `05-message-envelope.cbor.hex` | [§05](../../05-message-envelope.md) | Single-line canonical CBOR bytes for the envelope |
| `05-message-envelope.diag.txt` | [§05](../../05-message-envelope.md) | RFC 8949 §8 diagnostic notation |

## Scripts

| File | Role |
|---|---|
| `scripts/compute_vectors.py` | Primary path. Python 3 + `ecdsa` (pure-Python secp256k1) + `pycryptodome` (AES-GCM) + `cbor2`. Writes the JSON/CBOR/diag files. |
| `scripts/cross_validate_rs/` | Independent Rust crate. Reads the JSON outputs, recomputes every value using `sha2` / `hmac` / `k256` / hand-rolled deterministic CBOR encoder, and asserts byte-equality with each `expected` field. Exits non-zero on any disagreement. |

The two paths are independent:

- Different EC libraries (`ecdsa` Python vs `k256` Rust).
- Different HMAC implementations (Python stdlib vs `hmac` crate).
- Different CBOR encoders (Python `cbor2 canonical=True` AND a hand-rolled deterministic encoder AND a hand-rolled Rust encoder — three CBOR paths that all agree).
- Different ECDSA verifiers (Python `ecdsa` and Rust `k256::ecdsa`).

## How to reproduce

### Primary path (Python)

```bash
# One-time: create a venv with the crypto deps.
python3 -m venv /tmp/mpc-venv
/tmp/mpc-venv/bin/pip install ecdsa cbor2 pycryptodome

# Compute all vectors. Writes the four files above.
cd MPC-Spec/conformance/test-vectors/scripts
/tmp/mpc-venv/bin/python3 compute_vectors.py
```

### Cross-validation path (Rust)

```bash
cd MPC-Spec/conformance/test-vectors/scripts/cross_validate_rs
cargo run --release
```

Expected last line on success:

```
All vectors AGREE byte-for-byte across Python and Rust paths.
```

Exit code 0 ⇒ every JSON `expected` value was independently reproduced. Exit code 2 ⇒ at least one disagreement (in which case the JSON files MUST NOT be trusted).

## What the vectors cover

### §02 ExecutionId — `02-execution-id.json`

Three vectors per §02.6:

| Name | Phase | joint_pubkey | ExecutionId |
|---|---|---|---|
| Vector A | sign (0x04) | secp256k1 G compressed | `0x7286fe7b26a8ef9af0f42c517f53963d642602965b341cc0002084b1e801e883` |
| Vector B | keygen (0x01) | `0x00 * 33` (carve-out per §02.4) | `0x3bf98ecfaaabc27c71aabfd5d1a41533df7b8e5421f24ca2df5e200f82b0040a` |
| Vector C | refresh (0x06) | secp256k1 G compressed | `0x163ca28a96cee2da1c572c58be0bad3d501099a31f81cd4b3753f8bd02faa5c3` |

### §03 BRC-42 — `03-brc42-invoice.json`

- **All 5 private-key-derivation vectors** from `~/bsv/BRCs/key-derivation/0042.md` round-trip. (Compute path: `recipient_priv * sender_pub` → compressed → HMAC over invoice string → add to recipient_priv mod N. The computed `child_priv` equals the spec's `privateKey` field for every vector.)
- **All 5 public-key-derivation vectors** from `~/bsv/BRCs/key-derivation/0042.md` round-trip. (Compute path: `sender_priv * recipient_pub` → compressed → HMAC over invoice string → reduce mod N → `recipient_pub + G * offset`. The computed `child_pub` equals the spec's `publicKey` field for every vector.)
- **3 stress vectors** for the §03.2 invoice format (mixed case + whitespace, Unicode, empty key_id). These pin `shared_secret = G compressed` (test-only) so the HMAC offsets are reproducible without real ECDH material.

The Python primary computes every vector with `ecdsa` (pure-Python secp256k1). The Rust cross-validator uses `k256`. They produce byte-equal HMACs, child private keys, and child public keys for all 13 vectors.

### §04 SessionId — `04-session-id.json`

Two vectors per §04.10:

| Name | kind | SessionId |
|---|---|---|
| Vector A — 2-of-3 sign | 0x02 (sign) | `0x5be3c18ab094f090c92be1bac47bee388ab8ead59b987679d9bef53547a16108` |
| Vector B — DKG, on-chain anchor | 0x01 (dkg) | `0xe0af05e32667e3553df110a1ff621a5fe7b449b5c515e6886b4b2e38270e6a0f` |

The participant byte-strings used here are 33-byte test identities (`0x02 ‖ 0x00 * 31 ‖ 0xNN`); they are NOT valid curve points. These vectors exercise the formula's byte-mechanics, not the curve. Production usage MUST feed real BRC-31 identity pubkeys.

### §05 MessageEnvelope — `05-message-envelope.json`

One full envelope vector with all 12 fields populated:

- **Pinned test-only keys** committed alongside (`sender_priv = 0x01 * 32`, `recipient_priv = 0x02 * 32`, `eph_priv = 0x03 * 32`, AES-GCM IV = `0x0a..15`).
- BRC-78 ECIES inner (91 bytes total): eph_pub_33 ‖ iv_12 ‖ ct ‖ tag_16.
- BRC-31 outer signature: deterministic ECDSA (RFC 6979), DER-encoded, low-s normalized.
- Canonical CBOR per RFC 8949 §4.2: integer-keyed map, keys sorted by bytewise lex order of *encoded* keys.
- Total envelope: 361 bytes.

The signature verifies in both Python (`ecdsa`) and Rust (`k256::ecdsa`) against the recomputed canonical pre-signature CBOR.

## Negative tests (planned)

Phase 0 commits one happy-path envelope vector. Phase 1 adds:

- A broadcast envelope (`to_party = 0xFFFF`, replicated per recipient).
- A presign-phase envelope with `traceparent` set.
- A signature-mismatch envelope (verifier MUST reject; §05.9).
- An envelope with an unknown CBOR key (verifier MUST reject or log warn; §05.10).

Track in [`../../14-conformance-tests.md`](../../14-conformance-tests.md).

## Disagreement protocol

If a future change causes the Python and Rust paths to produce different bytes for *any* vector:

1. The cross-validator exits with code 2 and prints the diff.
2. Do **not** commit the changed JSON files until the disagreement is resolved.
3. Read the relevant spec section together; identify which path matches the spec text byte-for-byte.
4. The path whose interpretation deviates from the spec is wrong. File a fix.
5. If the spec is ambiguous, file a clarification PR first, then regenerate.

Both implementations and both validators are co-owned. Neither team is "the reference" — the spec is.
