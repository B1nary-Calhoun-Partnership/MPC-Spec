# 03 — Canonical BRC-42 Invoice

**Status:** LOCKED (pending ADR-0002 sign-off)
**Phase:** 0
**Decided by:** ADR-0002
**Last updated:** 2026-05-10

## 03.1 BRC-42 derivation, summary

BRC-42 (`~/bsv/BRCs/key-derivation/0042.md`) defines the BSV ecosystem's hierarchical-deterministic key derivation:

```
child_priv = root_priv + offset
child_pub  = root_pub  + offset · G
offset     = HMAC-SHA256(key=ECDH(root_priv, counterparty_pub), data=invoice_bytes)
invoice    = canonical invoice number string (this section)
```

The "invoice number" is the data argument to the HMAC. **Byte-for-byte agreement on the invoice string is mandatory** — even a single-byte difference produces different child keys, different addresses, and irreconcilable signatures.

## 03.2 Canonical invoice format

```
invoice = "{security_level}-{normalized_protocol_id}-{key_id}"
```

where:

- **`security_level`** is the ASCII decimal representation of the BRC-42 security level integer:
  - `0` → App scope
  - `1` → Counterparty scope
  - `2` → Anyone scope
- **`normalized_protocol_id`** is `protocol_id.to_lowercase().trim()`:
  - `to_lowercase()` is Unicode case folding via `str::to_lowercase` (Rust) / `String.toLowerCase()` matching the BSV TS SDK contract.
  - `trim()` removes leading and trailing ASCII whitespace per `str::trim` (Rust) / `String.trim()`.
  - **No interior whitespace removal.** "auth message signature" stays "auth message signature" with the spaces.
- **`key_id`** is verbatim, no normalization. Whitespace, case, and Unicode preserved exactly.
- **`-`** is a single ASCII hyphen-minus byte (`0x2D`). Two delimiters per invoice. No other surrounding whitespace.

The string is encoded as **UTF-8** for HMAC input.

## 03.2.1 Input validation

Implementations MUST reject inputs that violate the following constraints, matching the BSV TS SDK `KeyDeriver.computeInvoiceNumber` contract (`bsv-blockchain/ts-sdk/src/wallet/KeyDeriver.ts`):

- **Security level** MUST be one of `{0, 1, 2}`. Any other value MUST be rejected before HMAC computation.
- **Key ID** length MUST satisfy `1 ≤ len ≤ 800` (byte length of the UTF-8 encoding).
- **Protocol name** (after `.to_lowercase().trim()`) length MUST satisfy `len ≤ 400`, with one carve-out: if `normalized_protocol_id.starts_with("specific linkage revelation ")` (note trailing space), then `len ≤ 430` is permitted. The carve-out exists because the "specific linkage revelation" protocol can encapsulate another protocol ID inside its name.

Rejection MUST occur before any HMAC computation. Implementations SHOULD return a structured error identifying which constraint failed so callers can debug. Test vectors covering each rejection path are included in `conformance/test-vectors/03-brc42-invoice.json` (§14).

## 03.3 HMAC computation

```
shared_secret_33B = compressed_point( root_priv * counterparty_pub )
                  = the 33-byte 02/03-prefixed compressed encoding of the ECDH point.
                  // For "Anyone" counterparty: counterparty_pub = G (curve generator).
                  // For "Self_": both sides are root_pub; partial-ECDH ceremony required (see §03.6).
                  // For "Other(pubkey)": counterparty_pub = pubkey; partial-ECDH ceremony required.

hmac_offset_32B   = HMAC-SHA256(
    key  = shared_secret_33B,        // FULL 33 bytes, including the 0x02/0x03 prefix byte
    data = invoice.as_bytes()        // UTF-8 encoding of §03.2 string
)

offset_scalar     = Scalar::<Secp256k1>::from_be_bytes_mod_order(hmac_offset_32B)
                  // Standard reduction; rejection-sampling not required at this size.
```

## 03.4 Forbidden / common errors

- **Skipping `to_lowercase().trim()`.** Result: derived keys diverge from BSV SDK, from `bsv-worm`, from any wallet that follows the SDK contract. **bsv-mpc has this bug today** (`bsv-mpc/crates/bsv-mpc-core/src/hd.rs:122`); MUST fix.
- **Using only the X coordinate (32 bytes) of the shared secret as HMAC key.** The BRC-42 spec mandates the full 33-byte compressed encoding (with the parity prefix byte). Truncating to 32 bytes produces different child keys.
- **Stripping interior whitespace from `protocol_id`.** Only leading/trailing whitespace is removed.
- **Normalizing `key_id`.** `key_id` is verbatim. Two distinct key_ids that differ only in case or whitespace are distinct keys.
- **Using a different separator** (e.g., `_`, `:`, multi-byte). Single ASCII hyphen-minus only.
- **Adding a length prefix** to fields. The format is plain string concatenation.

## 03.5 Test vectors

The 5 "Public Key Derivation" and 5 "Private Key Derivation" test vectors from `~/bsv/BRCs/key-derivation/0042.md` MUST round-trip in both implementations as a CI gate. They are reproduced in `conformance/test-vectors/03-brc42-invoice.json`.

Additionally, the spec adds these stress vectors:

### 03.5.1 Mixed-case + whitespace stress

```
security_level   = 2
protocol_id      = "  AUTH MESSAGE SIGNATURE  "
key_id           = " AbC123 "
normalized       = "auth message signature"
key_id_kept      = " AbC123 "    // verbatim, including spaces and case
invoice          = "2-auth message signature- AbC123 "
                   // single-hyphen delimiters; key_id whitespace preserved
```

### 03.5.2 Unicode stress

```
security_level   = 2
protocol_id      = "Café Société"          // U+00E9, NFC normalized as input
key_id           = "Δοκιμή"                  // Greek
invoice          = "2-café société-Δοκιμή"
```

Implementations MUST process the inputs without renormalizing Unicode. Lowercase folding follows Unicode standard rules but no NFC/NFD normalization is applied beyond what the input already is.

### 03.5.3 Empty key_id

```
security_level   = 2
protocol_id      = "test"
key_id           = ""
invoice          = "2-test-"
                   // trailing hyphen + empty key_id; legal
```

## 03.6 Counterparty cases

| Counterparty kind | Shared secret derivation | Network rounds |
|---|---|---|
| `Anyone` | `shared_secret = G * 1` (= the curve generator). Local computation. | 0 |
| `Self_` | `shared_secret = root_priv * root_pub`. **Cannot be computed by any single party in MPC** — requires partial-ECDH ceremony. | 1 (per §03.7) |
| `Other(pubkey)` | `shared_secret = root_priv * pubkey`. Same partial-ECDH ceremony. | 1 (per §03.7) |

For `Self_` and `Other`, the partial-ECDH ceremony is a 1-round MPC operation. POC 8 measured ~16ms over the production CF Worker KSS — acceptable cost for the security benefit.

## 03.7 Partial-ECDH for `Self_` / `Other`

Each party computes a *raw* partial:

```
partial_i = share_i * counterparty_pub
```

The coordinator collects partials from a `t+1` subset and combines via Lagrange interpolation at x=0 over the responding subset's VSS evaluation points:

```
λ_i           = ∏_{m ∈ S, m ≠ i} (-I_m / (I_i - I_m))     // Lagrange coefficients
shared_secret = Σ_{i ∈ S} λ_i · partial_i                 // = root_priv · counterparty_pub
```

- Lagrange weighting MUST be performed in the canonical position. **Spec mandates the Lagrange combine lives inside the BRC-42 / partial-ECDH crate**, not in a higher layer. Naive sum (no Lagrange) is **forbidden**: it is correct only for additive sharing, not for VSS as produced by CGGMP'24's DKG.
  - rust-mpc's `mpc-brc42::aggregate_ecdh_partials` currently does naive sum; threshold-correct logic lives in `protocol/src/signer.rs::pre_derive`. MUST move the Lagrange combine into `mpc-brc42`.
  - See [`OPEN-QUESTIONS.md` Q2](OPEN-QUESTIONS.md).

## 03.8 Use in signing

Once `offset_scalar` is computed, it is supplied to cggmp24's signing builder via `set_additive_shift(offset_scalar)` (§01.2.2). The signing ceremony produces a signature for `child_pub = root_pub + G·offset_scalar` without ever materializing `child_priv` in any party's memory.

## 03.9 Implementation notes

- bsv-mpc `crates/bsv-mpc-core/src/hd.rs:122` — `compute_invoice` lacks `to_lowercase().trim()`. **MUST fix.**
- rust-mpc `crates/brc42/src/derivation.rs:24` — `build_invoice_number` correctly applies `to_lowercase().trim()`. No change.
- rust-mpc `crates/brc42/src/ecdh.rs:47` — `aggregate_ecdh_partials` does naive sum. **MUST be replaced with Lagrange combine** that takes VSS setup as a parameter.
- bsv-mpc `crates/bsv-mpc-core/src/ecdh.rs:235+` — `combine_partials_lagrange` is correct. Reuse pattern.

## See also

- [`decisions/0002-brc42-canonicalization-lowercase-trim.md`](decisions/0002-brc42-canonicalization-lowercase-trim.md) — ADR.
- [`01-cggmp24-pin.md`](01-cggmp24-pin.md) — `set_additive_shift` exposure.
- [`14-conformance-tests.md`](14-conformance-tests.md) — full test vector suite.
- BRC-42 spec: `~/bsv/BRCs/key-derivation/0042.md`.
- BSV TS SDK `KeyDeriver.computeInvoiceNumber` — the canonical reference implementation.
