# 04 — Canonical SessionId

**Status:** LOCKED (pending ADR-0004 sign-off)
**Version:** v1
**Phase:** 0
**Decided by:** ADR-0004
**Last updated:** 2026-05-10

## 04.1 What SessionId is

SessionId is a 32-byte ceremony-unique identifier, computed deterministically from the inputs that distinguish this ceremony from any other. It is consumed by ExecutionId (§02) and threaded through every transport envelope (§05) so that audit logs (§10) can reconstruct ceremony identity from on-chain BRC-18 proofs without trusting any single party.

## 04.2 Formula

```
SessionId = SHA256(
    "calhoun-binary-mpc-session-v1"  ‖   // 29 ASCII bytes, no terminator
    initiator_identity_33B            ‖   // BRC-31 identity pubkey of the coordinator
    sorted_participant_identities     ‖   // each 33B compressed, lex-ascending
    threshold_u16_LE                  ‖   // unsigned 16-bit, little-endian
    ceremony_kind_byte                ‖   // u8: see §04.3
    nonce_32B                         ‖   // see §04.4
    payload_digest_32B                    // ceremony-kind-specific: see §04.5
)
```

Length of input: 29 + 33 + (33 × n) + 2 + 1 + 32 + 32 bytes, where `n` is the participant count (variable).
Length of output: **32 bytes**.

## 04.3 Ceremony kind byte

| Byte | Kind |
|---|---|
| `0x01` | DKG (full keygen + auxinfo as one logical ceremony) |
| `0x02` | Sign |
| `0x03` | Presign (presignature generation) |
| `0x04` | ECDH (BRC-42 partial-ECDH for Self_/Other) |
| `0x05` | Refresh (POC 13 threshold resharing — same `(t,n)`) |
| `0x06` | Party replacement (same `(t,n)`, swap one identity) |
| `0x07` | Threshold change (`(t1,n1) → (t2,n2)`) |
| `0x08`–`0xFF` | Reserved. |

## 04.4 Nonce

The 32-byte `nonce_32B` provides ceremony freshness, ensuring distinct ceremonies of the same kind with otherwise-identical inputs produce distinct SessionIds.

- For routine ceremonies, `nonce_32B` SHALL be drawn from `OsRng` (or `getrandom/js` in WASM environments).
- For high-value ceremonies (Notary onboarding DKG, key-refresh on a high-value joint key), `nonce_32B` SHOULD be `SHA-256` of a recent BSV block hash (within the last 100 blocks) — provides on-chain freshness witness consumable by auditors. The block hash MUST be one whose Merkle root is publicly verifiable via WhatsOnChain or any other BSV light-client API.

The choice of nonce strategy is a per-ceremony policy, set by the initiator and propagated in the ceremony-init message (§05). Verifiers MUST accept either form.

## 04.5 Payload digest

The 32-byte `payload_digest_32B` binds the SessionId to the ceremony's content:

| Ceremony kind | `payload_digest_32B` |
|---|---|
| DKG (`0x01`) | `SHA-256("genesis" ‖ canonical_cbor(policy_manifest))` — binds the DKG to the policy manifest the new joint key will be governed under (§09). |
| Sign (`0x02`) | The 32-byte sighash being signed. |
| Presign (`0x03`) | `SHA-256("presig-pool" ‖ pool_id_32B)` — pool_id is the cosigner's local pool identifier, persisted across presig replenishment cycles. |
| ECDH (`0x04`) | `SHA-256("ecdh" ‖ counterparty_pub_33B ‖ canonical_cbor(invoice_string))` — binds the ECDH to the BRC-42 derivation it will service. |
| Refresh (`0x05`) | `SHA-256("refresh" ‖ joint_pubkey_33B ‖ epoch_u64_LE)` — `epoch` is the refresh count, monotonically increasing. |
| Party replacement (`0x06`) | `SHA-256("replace" ‖ old_party_identity_33B ‖ new_party_identity_33B ‖ epoch_u64_LE)`. |
| Threshold change (`0x07`) | `SHA-256("threshold" ‖ old_t_u16_LE ‖ old_n_u16_LE ‖ new_t_u16_LE ‖ new_n_u16_LE ‖ epoch_u64_LE)`. |

## 04.6 Sorted participant identities

`sorted_participant_identities` is the lex-ascending concatenation of each participating cosigner's BRC-31 identity pubkey, in canonical 33-byte compressed form.

- Sort order is byte-lex over the 33-byte compressed encodings (i.e., `Vec<[u8; 33]>::sort()`).
- Including the initiator's own identity is REQUIRED — the initiator is a participant.
- Duplicates are forbidden.

Example for a 2-of-3 ceremony with identity keys `02aa...`, `02bb...`, `02cc...`:
```
sorted_participant_identities = 02aa…(33) ‖ 02bb…(33) ‖ 02cc…(33)
                              = 99 bytes total
```

## 04.7 Why deterministic, not random

We deliberately reject pure-random SessionIds because:

1. **Audit recoverability.** Given the inputs (recorded in the BRC-18 participation proof and the audit log), any third party can recompute SessionId and verify the audit record. With random SessionIds, this verification path requires trusting whoever produced the SessionId.
2. **Replay binding.** ExecutionId derives from SessionId + joint_pubkey + phase. With a deterministic SessionId, ExecutionId is too — a malicious party cannot fabricate plausible ExecutionIds for ceremonies that didn't happen, because they don't have a valid set of inputs that hash to a SessionId someone else committed to.
3. **Session collision avoidance.** The fresh `nonce_32B` (§04.4) provides the freshness; deterministic input-binding provides the input-uniqueness.

## 04.8 Lifetime

A SessionId is valid for the ceremony only. Persistent identifiers (the joint pubkey, the BRC-22 audit record, the BRC-18 OP_RETURN proof) reference the SessionId by hash, but the SessionId itself is not reused.

## 04.9 Forbidden

- Reusing a SessionId across ceremonies (even of different kinds).
- Using a `nonce_32B` of all-zeros (zero-entropy is dangerously close to a deterministic SessionId; flag it).
- Skipping the lex-sort on `sorted_participant_identities` (different sort orders → different SessionIds → ceremony aborts at round 1).
- Using a different domain separator than `"calhoun-binary-mpc-session-v1"` (e.g., a per-implementation tweak). The string is byte-locked.

## 04.10 Test vectors

The locked machine-readable values live in [`conformance/test-vectors/04-session-id.json`](conformance/test-vectors/04-session-id.json) and are cross-validated by Python (`hashlib`) and Rust (`sha2`).

For both vectors, the three participant byte-strings are 33-byte test identities (`0x02` || 31 zero bytes || sequence byte). They are NOT valid curve points — these vectors exercise the formula's byte-mechanics only.

```
p1 = 0x02 00 00 ... 00 01    (33 bytes)
p2 = 0x02 00 00 ... 00 02    (33 bytes)
p3 = 0x02 00 00 ... 00 03    (33 bytes)
```

### 04.10.1 Vector A — Routine 2-of-3 sign

```
initiator_identity   = p1
participants_sorted  = [p1, p2, p3]
threshold            = 2     (LE: 0x0200)
kind                 = 0x02  (sign)
nonce                = SHA-256("nonce-A")
                     = 0x4e1ce45a65d9ba8655a1bacd9d9ec348dbf7a8ab2b719f1b1bb0cf3897c0a2ab
payload_digest       = SHA-256("sighash-A")
                     = 0x3bcda18f91ced5eade648ac7f132dbef019bd3590d204734af97713532b63525

SessionId            = 0x5be3c18ab094f090c92be1bac47bee388ab8ead59b987679d9bef53547a16108
```

### 04.10.2 Vector B — DKG with on-chain anchor

```
initiator_identity   = p1
participants_sorted  = [p1, p2, p3]
threshold            = 2
kind                 = 0x01  (dkg)
nonce                = SHA-256("block-800000-anchor")
                     = 0x39cd67fde05918566d9c5bac114b79af09d67edd50155a44e4b41603433c0210
                     (stand-in for a real block hash; production usage hashes
                      a recent BSV block hash per §04.4)
payload_digest       = SHA-256("genesis" || canonical_cbor({}))
                     = SHA-256("genesis" || 0xa0)
                     = 0xf7dc1bd2af02a533ab389c8f67eb4c9c5c49d9c40932129bc2bf6f07b111f232
                     where canonical_cbor({}) = 0xa0  (empty CBOR map)

SessionId            = 0xe0af05e32667e3553df110a1ff621a5fe7b449b5c515e6886b4b2e38270e6a0f
```

## See also

- [`decisions/0004-canonical-session-id.md`](decisions/0004-canonical-session-id.md) — ADR.
- [`02-execution-id.md`](02-execution-id.md) — ExecutionId consumes SessionId.
- [`05-message-envelope.md`](05-message-envelope.md) — envelope carries SessionId.
- [`10-audit.md`](10-audit.md) — audit records bind to SessionId.
