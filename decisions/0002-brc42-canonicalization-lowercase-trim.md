# ADR-0002: BRC-42 invoice canonicalization is `.to_lowercase().trim()`

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)

## Context

BRC-42 derivation requires an HMAC over an "invoice number" string (`{security_level}-{protocol_id}-{key_id}`). Byte-for-byte agreement on this string is mandatory across implementations — even a single-byte difference produces different child keys, different addresses, irreconcilable signatures.

The two implementations diverge:

- **bsv-mpc** (`crates/bsv-mpc-core/src/hd.rs:122`): `format!("{}-{}-{}", security_level, protocol_name, key_id)` — no normalization.
- **rust-mpc** (`crates/brc42/src/derivation.rs:24`): `format!("{security_level}-{protocol_lower_trimmed}-{key_id}")` — applies `.to_lowercase().trim()` on the protocol name.

The BSV TS SDK (`KeyDeriver.computeInvoiceNumber`) applies `.toLowerCase().trim()`. **bsv-mpc is incompatible with the SDK contract; rust-mpc is correct.**

bsv-mpc's existing tests pass only because they happen to use already-lowercase protocol names ("worm memory", "auth message signature"). The bug is unmasked the first time someone uses a mixed-case protocol_id.

## Decision

The canonical BRC-42 invoice format is:

```
invoice = "{security_level}-{protocol_id.to_lowercase().trim()}-{key_id}"
```

`key_id` is verbatim (no normalization). Single ASCII hyphen-minus delimiters. UTF-8 encoding for HMAC input.

bsv-mpc MUST update `compute_invoice` to apply `.to_lowercase().trim()`. Tests MUST include vectors with mixed-case protocol names that exercise the normalization.

## Rationale

The BSV TS SDK is the de jure spec for BRC-42 in the BSV ecosystem. `bsv-worm`, every BRC-100 wallet, and every existing on-chain key derived per BRC-42 use the SDK's canonicalization.

There is no alternate canonicalization that wins on technical merit — the SDK contract is the contract. bsv-mpc's current behavior is a latent bug.

## Consequences

- **`bsv-mpc`:** Apply `.to_lowercase().trim()` in `crates/bsv-mpc-core/src/hd.rs::compute_invoice`. Add SDK-parity test vectors (the 5 public + 5 private vectors from `~/bsv/BRCs/key-derivation/0042.md`). ~1 hour of work.
- **`rust-mpc`:** No change required.
- **`bsv-messagebox-cloudflare`:** No change.
- **Spec:** §03-brc42-invoice codifies the canonicalization with stress-test vectors (mixed case, Unicode, empty key_id).
- **Test vectors:** SDK round-trip + stress vectors land in `conformance/test-vectors/03-brc42-invoice.json`.

This is a one-side bug fix. No coordination overhead beyond agreement on the spec language.

## Alternatives considered

- **rust-mpc adopts bsv-mpc's no-normalization form** — rejected; would break SDK compat for everyone, including non-MPC users of BRC-42.
- **Define a new canonicalization (e.g., NFC normalization)** — rejected; over-engineered. Lower-and-trim is what the SDK does.

## See also

- Spec: [`§03-brc42-invoice.md`](../03-brc42-invoice.md)
- BRC-42: `~/bsv/BRCs/key-derivation/0042.md`

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
