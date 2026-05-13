# ADR-0037: Canonical CBOR re-encode equivalence as wire-conformance requirement

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Security dimension S1. Direct precedent: Fireblocks BGM_DKG (2023) parser/transcript-binding gap; Trail of Bits diff-fuzzing methodology against TSS libraries.

## Context

The MPC-Spec wire format (§05 envelope, §10 AuditEntry, §08 BRC-52⊕) is canonical CBOR per RFC 8949 §4.2. The §05.9 spec text enumerates per-side rejection rules (CBOR decoding errors, indefinite-length items, floats, size bound).

But bsv-mpc and rust-mpc parse independently — bsv-mpc uses `serde_cbor`-flavored extraction; rust-mpc uses Binary's parser stack. Two independent strict-mode parsers can still accept asymmetric inputs:

- Non-minimal integer encoding (e.g., `0x18 0x05` for integer 5 instead of `0x05`)
- Duplicate map keys with one parser silently overriding
- Indefinite-length items rejected by one but the other accepting a sub-case
- Trailing bytes past the canonical termination
- Unsorted map keys
- Sub-spec-conformant tag usage

A single asymmetric case lets an attacker craft an envelope that **bsv-mpc accepts as round-N from party-A** but **rust-mpc rejects** (or vice-versa). With asymmetric acceptance:

- The attacker steers **identifiable-abort blame** onto the honest party.
- Audit logs go split-brain (bsv-mpc records the round; rust-mpc records the abort).
- The `sender_sig_brc31` (field 9) covers the original bytes, but the receiver's parse-tree may not match what the signer believed they signed.

Real-world precedent: Fireblocks BGM_DKG (2023) was a transcript-binding gap in GG18/20-family DKG that enabled key extraction; ToB / Verichains coordinated disclosure. The mechanism in our spec is different but the class of bug is the same.

## Decision

A recipient MUST, in addition to the §05.9 rejection rules already specified:

**Re-encode** the parsed envelope (fields 1 through 8) as canonical CBOR per RFC 8949 §4.2 and **verify byte-equivalence** with the original bytes covered by `sender_sig_brc31` (field 9).

**Mismatch MUST be treated as a signature failure** and the envelope MUST be rejected. The failure MUST emit an `AuditEntry` with `event_kind = "EnvelopeReencodeMismatch"` recording the deviation offset.

The following MUST cause rejection at the FIRST byte of deviation, without partial processing:

1. Non-minimal integer encoding
2. Indefinite-length strings, arrays, or maps
3. Duplicate map keys
4. Trailing bytes after the canonical termination
5. Floats (forbidden per §05.2)
6. Unsorted map keys (canonical CBOR mandates lexicographic byte ordering)
7. Tag values not whitelisted in §05.10 "Reserved fields"
8. Map keys that are not unsigned integers or text strings (per spec §05.3)

## Rationale

- **Closes the parser-differential class entirely.** Byte-equivalence is a stronger property than "both strict." Two strict parsers can disagree on edge cases; byte-equivalence forces agreement at the wire.
- **Cheap to implement.** Most modern Rust CBOR libraries (`ciborium`, `minicbor`) expose a canonical-encode path. The check is `original_bytes == canonical_reencode(parsed_value)` — O(n) over the message.
- **Audit-detectable.** Every re-encode mismatch emits an `AuditEntry`, so even attacker probing is visible in audit. Witness-cosigning (§10.6) means mismatched envelopes from one cosigner are visible to others.
- **Conformance-enforceable.** Adds a test-vector pair (one accepted, one minimally-rejected) to the canonical conformance harness (#S3 in action items).

## Consequences

### `bsv-mpc` (Calhoun)

- Add re-encode-and-compare to envelope receive path (`crates/bsv-mpc-core/src/transport/envelope.rs` or equivalent location post-MessageBox-port).
- Add `EnvelopeReencodeMismatch` audit event.
- Validate against new conformance vector `conformance/test-vectors/05-message-envelope-diff.cbor.hex`.

### `rust-mpc` (Binary)

- Same changes in `crates/transport/`.
- Coordinate with Ishaan on shared adversarial CBOR fuzz corpus (Q26 in OPEN-QUESTIONS).

### `MPC-Spec`

- §05.9 expanded with §05.9.1 (normative text in spec).
- Conformance vector pair added to `conformance/test-vectors/05-message-envelope-diff.cbor.hex` (and `.json` companion).
- Q26 added: shared adversarial corpus ownership + CI fuzz cadence.

## Alternatives considered

- **Only enforce strict per-side parsing rules.** Rejected — two strict parsers can still diverge on edge cases that don't match the spec exactly. Byte-equivalence is the strict-equivalent.
- **Verify the canonical hash of fields 1-8 inside `sender_sig_brc31`.** Effectively the same as re-encode + memcmp; less efficient and not what BRC-31 specifies.
- **Cross-reference parsing by shipping decoded JSON alongside CBOR.** Doubles wire size + still has a JSON parser-diff problem. Rejected.

## Status of M1 dependency

**M1 critical (wire-compat).** Without this, the cross-impl signing demo at 2026-05-29 runs with a known parser-diff attack surface. Phase 0 sign-off (slipped to 2026-06-12) MUST include this ADR. The conformance vector pair MUST be byte-locked + cross-validated before 2026-05-22 internal review.

## See also

- Spec: [§05.9](../05-message-envelope.md), [§05.9.1](../05-message-envelope.md)
- Conformance: `conformance/test-vectors/05-message-envelope-diff.cbor.hex` (to be authored)
- 2026-05-13 swarm: Security S1
- Reference: Fireblocks BGM_DKG (2023), ToB diff-fuzzing methodology, RFC 8949 §4.2

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
