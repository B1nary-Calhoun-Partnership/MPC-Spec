# Test-vector computation + cross-validation scripts

Two independent paths. Both must agree byte-for-byte on every vector.

## Files

- `compute_vectors.py` — **primary** computation in Python. Writes `../02-execution-id.json`, `../03-brc42-invoice.json`, `../04-session-id.json`, `../05-message-envelope.json` (+ `.cbor.hex` and `.diag.txt`).
- `cross_validate_rs/` — **cross-validator** in Rust. Reads the JSON files above, recomputes every value from inputs using independent crates, asserts byte-equality.

## Run order

```bash
# 1. Install Python deps once.
python3 -m venv /tmp/mpc-venv
/tmp/mpc-venv/bin/pip install ecdsa cbor2 pycryptodome

# 2. Primary: compute all vectors and write to ../.
/tmp/mpc-venv/bin/python3 compute_vectors.py

# 3. Cross-validate.
cd cross_validate_rs && cargo run --release
```

Cross-validator exit code 0 ⇒ all vectors agree byte-for-byte. Exit 2 ⇒ disagreement found; do NOT trust the JSON files until the divergence is resolved.

## Why two paths?

Cryptographic test vectors locked into a spec are load-bearing: implementations will be conformance-graded against them. If a single implementation produces them, a bug in that implementation becomes a bug in the spec. The Python and Rust paths use different curve libraries (`ecdsa` vs `k256`), different HMAC implementations (stdlib vs `hmac` crate), and three different CBOR encoders (Python `cbor2`, hand-rolled Python, hand-rolled Rust) — a wrong byte would have to be wrong identically across all three, which is the cross-validation gate.
