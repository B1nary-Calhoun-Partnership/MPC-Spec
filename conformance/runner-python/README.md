# Conformance runner — Python (Phase 1)

Per issue #14, the first runner is Python `cbor2` as the Calhoun-side reference. Rust runners (`runner-bsv-mpc/`, `runner-rust-mpc/`) plug in as matrix entries in `.github/workflows/conformance.yml` once both stacks are ready.

## What it checks

- CBOR round-trip on every `*_cbor_hex` field embedded in vector JSON files.
- CBOR round-trip on every `*.cbor.hex` raw file.
- Cross-check that raw `.cbor.hex` files match embedded hex in sibling JSON when present.
- Runner self-test: tampers a known-good CBOR blob in memory and asserts the gate detects it (covers issue #14's "intentionally regressed vector" close criterion).

## What it does NOT check (deferred to Rust runners)

- BRC-42 invoice derivation, ExecutionId / SessionId hashing.
- BRC-31 signature verification (secp256k1).
- AES-GCM ciphertext byte-equality (needs ProtoWallet primitives).

These need crypto primitives best validated by each implementation's own runner against the same vectors.

## TBD handling

Vectors containing `TBD` or `__TBD__` placeholders are **skipped, not failed** — the gate is live now while reference impls byte-lock (e.g. Ishaan's #9 on `06-presig-bundle-encryption.json`).

## Running locally

```bash
cd conformance/runner-python
python3 -m pip install -r requirements.txt
python3 runner.py
```

Exit code 0 = pass. Non-zero = regression — fix or update the vector.
