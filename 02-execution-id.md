# 02 — Canonical ExecutionId

**Status:** LOCKED (pending ADR-0003 sign-off)
**Version:** v1
**Phase:** 0
**Decided by:** ADR-0003
**Last updated:** 2026-05-10

## 02.1 What ExecutionId is

ExecutionId is a 32-byte tag fed into every CGGMP'24 transcript hash, zero-knowledge proof challenge, and reliable-broadcast commitment. It binds a cggmp24 ceremony to a specific `(spec_version, algorithm, phase, session, joint_pubkey)` tuple. Mismatched ExecutionIds across parties cause round-1 abort.

## 02.2 Formula

```
ExecutionId = SHA256(
    domain_separator        ‖   // 18 ASCII bytes, no terminator: "calhoun-binary-mpc"
    version                  ‖   // u8: 0x01 = mpc-spec-v1
    algorithm_tag            ‖   // u8: 0x01 = cggmp24, 0x02 = dkls23 (v2), 0x03 = frost (v3)
    phase_tag                ‖   // u8: see §02.3
    session_id_32B           ‖   // SessionId per §04
    joint_pubkey_33B             // compressed secp256k1; all-zeros during keygen
)
```

Length of input: 18 + 1 + 1 + 1 + 32 + 33 = **86 bytes**.
Length of output: **32 bytes**.

## 02.3 Phase tag values

| Tag | Phase |
|---|---|
| `0x01` | DKG keygen |
| `0x02` | DKG auxinfo |
| `0x03` | Presigning |
| `0x04` | Signing |
| `0x05` | ECDH (BRC-42 partial-ECDH for Self_/Other counterparty derivation) |
| `0x06` | Refresh (POC 13 threshold resharing) |
| `0x07` | Reserved (party-replacement resharing) |
| `0x08`–`0xFF` | Reserved for future spec versions; MUST NOT be used in `mpc-spec-v1`. |

## 02.4 Joint pubkey carve-out for keygen

For phase `0x01` (DKG keygen), the joint pubkey is not yet known — the keygen ceremony produces it. In this phase only, `joint_pubkey_33B` MUST be set to 33 zero bytes (`0x00 * 33`).

For all other phases, `joint_pubkey_33B` MUST be the canonical compressed encoding (33 bytes, prefix `0x02` or `0x03`) of the joint public key produced by the prior DKG.

Implementations MUST NOT use the joint pubkey from a *prior* ceremony as a placeholder during keygen. The all-zero carve-out is the only acceptable placeholder.

## 02.5 Domain separator

The 18-byte ASCII string `"calhoun-binary-mpc"`:

```
hex: 63 61 6c 68 6f 75 6e 2d 62 69 6e 61 72 79 2d 6d 70 63
```

No null terminator. No length prefix. No surrounding whitespace. Implementations that prepend a `b""` byte literal in Rust source MUST verify the byte count is exactly 18.

## 02.6 Test vectors

These are the canonical test vectors. Both implementations MUST reproduce these byte-for-byte. Failure to match is a P0 conformance bug.

The locked machine-readable values live in [`conformance/test-vectors/02-execution-id.json`](conformance/test-vectors/02-execution-id.json) and are cross-validated by two independent implementations (Python `hashlib` and Rust `sha2`) — see [`conformance/test-vectors/README.md`](conformance/test-vectors/README.md) for the reproduction commands.

### 02.6.1 Vector A — Sign phase, joint key known

```
domain_separator = "calhoun-binary-mpc"
version          = 0x01
algorithm_tag    = 0x01  (cggmp24)
phase_tag        = 0x04  (sign)
session_id       = SHA256("test-vector-A")
                 = 0xf25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b
joint_pubkey     = secp256k1 generator G, SEC1 compressed
                 = 0x0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798

ExecutionId      = 0x7286fe7b26a8ef9af0f42c517f53963d642602965b341cc0002084b1e801e883
```

### 02.6.2 Vector B — Keygen phase, joint key unknown

```
domain_separator = "calhoun-binary-mpc"
version          = 0x01
algorithm_tag    = 0x01
phase_tag        = 0x01  (keygen)
session_id       = SHA256("test-vector-B")
                 = 0x8bf9d11c1663da8567389511bdf497a9a3c815c38df2a940f5a396c71465b406
joint_pubkey     = 0x00 * 33  (carve-out per §02.4)

ExecutionId      = 0x3bf98ecfaaabc27c71aabfd5d1a41533df7b8e5421f24ca2df5e200f82b0040a
```

### 02.6.3 Vector C — Refresh phase

```
domain_separator = "calhoun-binary-mpc"
version          = 0x01
algorithm_tag    = 0x01
phase_tag        = 0x06  (refresh)
session_id       = SHA256("test-vector-C")
                 = 0x8997d07b34f5031f5fc8b00ddc4776120c5bd652923da947c6f2c04c43a05ccd
joint_pubkey     = secp256k1 generator G, SEC1 compressed
                 = 0x0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798

ExecutionId      = 0x163ca28a96cee2da1c572c58be0bad3d501099a31f81cd4b3753f8bd02faa5c3
```

Full vectors in [`conformance/test-vectors/02-execution-id.json`](conformance/test-vectors/02-execution-id.json).

## 02.7 Why this formula

- **Domain separator** prevents cross-protocol replay. CGGMP'24's internal ExecutionId is plain bytes; the protocol does not domain-separate itself across deployments. We must.
- **Version + algorithm_tag** protect against scheme-migration replay. A captured DKG message from a v1 (cggmp24) ceremony cannot be replayed in a v2 (dkls23) ceremony; the algorithm_tag byte differs, ExecutionId differs, all transcript hashes differ.
- **Phase tag** prevents a captured DKG-round-2 message from being replayed as a sign-round-2 message of a different ceremony. Each phase has a distinct ExecutionId even within the same session.
- **session_id** prevents replay across ceremonies of the same kind (per §04, session_id is itself bound to participants, threshold, kind, nonce, payload).
- **joint_pubkey** ties ExecutionId to a specific key. Two ceremonies for two different wallets — even with the same `algorithm_tag`, `phase_tag`, and identical participants — produce different ExecutionIds.

## 02.8 Implementation notes

- bsv-mpc currently uses `SHA256(b"bsv-mpc-signing-" || session_id.0.as_bytes())` (`bsv-mpc/crates/bsv-mpc-core/src/signing.rs:175-183`). MUST replace with §02.2 formula.
- rust-mpc currently uses `ExecutionId::new(keygen_session_id.as_bytes())` — raw UTF-8 of session_id string (`rust-mpc/crates/coordinator/src/dkg.rs:154` et al). MUST replace.

The formulas differ by enough that a 1-bsv-mpc-party + 2-rust-mpc-cosigners ceremony will abort at round 1 today. **This is the single most important wire-compat fix in Phase 0.**

## 02.9 Forbidden

- Using a random ExecutionId (loses input→id binding; breaks audit-recoverability).
- Hashing ASCII representations of fields when the spec calls for binary (e.g., `format!("{:x}", session_id)` instead of raw bytes).
- Adding extra fields. The formula is closed; future additions go via spec version bump.
- Truncating to fewer than 32 bytes. CGGMP'24 expects a full 32-byte ExecutionId.

## See also

- [`decisions/0003-canonical-execution-id.md`](decisions/0003-canonical-execution-id.md) — the ADR.
- [`01-cggmp24-pin.md`](01-cggmp24-pin.md) — algorithm_tag values are reserved here too.
- [`04-session-id.md`](04-session-id.md) — SessionId formula consumed by ExecutionId.
- [`14-conformance-tests.md`](14-conformance-tests.md) — test vector files.
