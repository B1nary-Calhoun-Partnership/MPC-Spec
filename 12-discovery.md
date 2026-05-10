# 12 — Discovery (CHIP token, BRC-22 overlay)

**Status:** DRAFT
**Phase:** 3
**Decided by:** ADR-0012 (proposed)
**Last updated:** 2026-05-10

## 12.1 Overlay topic

Cosigner discovery uses the BSV SLAP/CHIP overlay on topic `tm_mpc_signing`.

Reputation-related events use `tm_mpc_audit` (§10), `tm_mpc_certs_v1` (§08), and `tm_mpc_revocations_v1` (§08.10).

Notary capability manifests use `tm_mpc_notary_manifest` (§15).

## 12.2 CHIP token format

Each cosigner publishes a 5-field PushDrop output on topic `tm_mpc_signing`:

```
PushDrop fields:
  0: "CHIP"                      // marker (4 ASCII bytes)
  1: identity_key_33B            // BRC-31 identity pubkey
  2: service_url                 // UTF-8 string (full URL with scheme)
  3: "tm_mpc_signing"            // topic (16 ASCII bytes)
  4: capabilities_json           // canonical JSON, see §12.3
```

The locking key is the identity_key in field 1; only the operator can revoke by spending the PushDrop UTXO.

## 12.3 Capabilities JSON

Canonical JSON (sorted keys). Schema:

```json
{
  "version": "mpc-spec-v1",
  "curves": ["secp256k1"],
  "algorithms": ["cggmp24"],
  "threshold_configs": ["2-of-3", "3-of-5"],
  "max_presignatures": 100,
  "min_balance_sats": 0,
  "fee_sats": 333,
  "policy_hash": "0x...",
  "policy_manifest_url": "https://notary.example.com/policy.cbor",
  "transport": {
    "inbox_url": "https://message.b1nary.cloud",
    "inbox_url_fallback": ["https://rust-message-box.dev-a3e.workers.dev"],
    "iroh_endpoint": "iroh:peer:abc...",
    "tor_onion_url": null,
    "ws_supported": true,
    "fcm_supported": false
  },
  "accepted_cert_roots": ["02aa...", "02bb..."],
  "cert_serials": ["base64-of-serial-A", "base64-of-serial-B"],
  "audit_log_url": "https://audit.example.com/cosigner-01",
  "tee_attestation_format": "nitro_v1",
  "binary_hash": "sha256-hex-of-cosigner-binary",
  "jurisdiction": "US",
  "support_url": "https://example.com/support"
}
```

Required fields: `version`, `curves`, `algorithms`, `threshold_configs`, `fee_sats`, `policy_hash`, `transport.inbox_url`, `accepted_cert_roots`.

Optional fields: everything else.

Future-compat: parsers MUST tolerate unknown fields (forward compatibility).

## 12.4 Discovery query

A user (or wallet, or coordinator) discovers cosigners via the BSV SDK `LookupResolver` against the overlay:

```
results = LookupResolver(
  topic    = "tm_mpc_signing",
  filters  = {
    curves:                 contains "secp256k1",
    threshold_configs:      contains "2-of-3",
    fee_sats_max:           1000,
    policy_hash:            (optional, exact match for known policy),
    jurisdiction:           "US"
  }
)
```

Results are PushDrop-decoded CHIP tokens with the capabilities JSON parsed.

## 12.5 Reputation scoring

Discovered cosigners SHOULD be ranked by reputation. The default formula (per `bsv-mpc-overlay/src/discovery.rs`):

```
score = 0.40 * proof_score    // count of successful BRC-18 proofs (last 30d, normalized)
      + 0.20 * age_score      // age of CHIP token in days (capped at 365)
      + 0.25 * abort_score    // 1 - (aborts / signings) for last 30d
      + 0.15 * fee_score      // 1 - (fee / max_fee_in_results)
```

Range: 0.0 to 1.0. Higher is better.

For v1 MVP, where `query_proofs` is freshly un-stubbed, fall back to:
```
score_v0 = 0.5 * age_score + 0.5 * fee_score
```

## 12.6 Trust-on-first-use

For an unknown cosigner discovered via overlay, a wallet MUST:

1. Verify the CHIP token's PushDrop signature (locking key matches `identity_key`).
2. Fetch and verify the capabilities JSON.
3. If `policy_manifest_url` is set, fetch the manifest and verify SHA-256 matches `policy_hash`.
4. If `cert_serials` is set, fetch each cert from the certifier; verify chain to `accepted_cert_roots`; verify CT inclusion proof.
5. Verify the cosigner has ≥30-day on-chain age (CHIP token published ≥30 days ago) AND ≥N successful settlements (`N=10` default; configurable per wallet).

If any check fails, the cosigner is rejected. The 30-day-age requirement is the Sybil-resistance gate.

## 12.7 Sybil resistance

Every CHIP token costs ~1000 sats to publish (one BSV transaction). Sybil-creating 1000 fake cosigners costs ~$0.50 — not enough.

The 30-day on-chain age + ≥N-settlements requirements (§12.6) compound: even with ~$0.50 to publish, an attacker waits 30 days and accumulates 10 successful settlements before being usable. Practical Sybil floor: 30 days + several thousand sats of legitimate activity per fake.

For high-value applications, wallets SHOULD use **pre-vetted cosigner lists** (allowlist of trusted operators) rather than overlay discovery. Discovery is for low-to-medium-value general use.

## 12.8 Revocation

Cosigners revoke their own CHIP tokens by spending the PushDrop UTXO. Spent CHIP tokens are filtered out by the overlay (BRC-22 mechanism).

Revoking a CHIP token is one path; the cert revocation path (§08.10) is another. Both should fire on operator decommissioning.

`bsv-mpc-overlay/src/chip.rs::revoke_chip_token` is currently TODO. MUST implement.

## 12.9 Forbidden

- Publishing a CHIP token with stale `policy_hash` (not matching the cert's `policy_hash`). Verifiers reject.
- Publishing CHIP tokens with `fee_sats < 100` (the floor). Verifiers reject.
- Filtering on overlay-claimed properties without verifying via the cert (e.g., trusting `jurisdiction` without a cert that binds it).

## 12.10 Implementation notes

- bsv-mpc `bsv-mpc-overlay/src/{discovery,chip}.rs` — fully implemented. Add `policy_manifest_url`, `policy_hash`, `transport` block, `accepted_cert_roots`, `cert_serials`, `tee_attestation_format`, `binary_hash` fields to `ChipCapabilities`.
- bsv-mpc `chip.rs::revoke_chip_token` — TODO. MUST implement.
- bsv-mpc `bsv-mpc-overlay/src/proofs.rs::query_proofs` — STUBBED (returns empty Vec). MUST implement; reputation scoring depends on it.
- rust-mpc has no overlay code. Port from bsv-mpc.

## 12.11 Test vectors

`conformance/test-vectors/12-discovery.json`. Examples:
- Valid CHIP token round-trip (publish, query, verify).
- Reputation scoring across 10 mock cosigners.
- Trust-on-first-use rejection: cosigner with <30-day age.
- Revocation: spend the UTXO, query overlay, confirm filtered out.

## See also

- [`decisions/0012-overlay-discovery-trust-on-first-use.md`](decisions/0012-overlay-discovery-trust-on-first-use.md) — ADR.
- [`08-identity.md`](08-identity.md) — `cert_serials`.
- [`09-policy.md`](09-policy.md) — `policy_hash`.
- [`10-audit.md`](10-audit.md) — proof history feeds reputation.
- [`15-notary-product.md`](15-notary-product.md) — Notary discovery.
- BRC-22: SHIP/SLAP/CHIP overlay protocol.
- bsv-mpc `brc-drafts/brc-mpc-discovery.md`.
