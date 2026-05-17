# 12 — Discovery (CHIP token, BRC-22 overlay)

**Status:** DRAFT
**Version:** v1
**Phase:** 3
**Decided by:** ADR-0012 (proposed)
**Last updated:** 2026-05-10

## 12.1 Overlay topic

Cosigner discovery uses the BSV SLAP/CHIP overlay on topic `tm_mpc_signing`.

Reputation-related events use `tm_mpc_audit` (§10), `tm_mpc_certs_v1` (§08), and `tm_mpc_revocations_v1` (§08.10).

Notary capability manifests use `tm_mpc_notary_manifest` (§15).

## 12.2 CHIP token format (canonical signed SHIP — Path A, per [ADR-0050](decisions/0050-chip-token-architecture-path-a.md))

A cosigner's CHIP token is **byte-identical to a canonical 5-field signed SHIP admin token** as defined by `@bsv/overlay-discovery-services` (`SHIPTopicManager.ts`) and produced by `@bsv/sdk` 1.10.1's `pushdrop.lock(fields, [2, "service host interconnect"], "1", "anyone", true, true, "before")` path:

```
PushDrop fields:
  0: "SHIP"                    // protocol marker (4 ASCII bytes)
  1: identity_key_33B          // BRC-31 identity pubkey (33-byte compressed secp256k1)
  2: service_url               // UTF-8 string (full URL with scheme; e.g. "https://mpc.example.com")
  3: "tm_mpc_signing"          // topic (16 ASCII bytes)
  4: signature_DER             // DER ECDSA over sha256(concat(fields[0..3]))
                               // signed with BRC-42 child of identity_key:
                               //   protocol_id = [2, "service host interconnect"]
                               //   key_id      = "1"
                               //   counterparty = Anyone
                               //   forSelf     = true
```

The locking key MUST equal the same BRC-42 child as the signing key. Implementations MUST reject any token where (a) `fields.length != 5`, (b) field[4] is not a valid DER ECDSA signature linked to field[1] via the BRC-42 derivation above, or (c) the locking key does not equal the derived child. The canonical validation routine is the Rust port at `bsv-overlay-discovery::validation::is_token_signature_correctly_linked`; both stacks SHOULD delegate to it or to an equivalent byte-for-byte port.

**MPC-specific capabilities are NOT in this script.** They are served off-chain via the `/capabilities` side-channel — see §12.3 below. Per ADR-0050, embedding capabilities in any PushDrop field makes the token invisible to every canonical overlay validator on the network.

Revocation: the cosigner spends the PushDrop UTXO with the BRC-42 child key (which it controls because it controls `identity_key`).

## 12.3 Capabilities side-channel — `GET /capabilities` (per [ADR-0050](decisions/0050-chip-token-architecture-path-a.md))

Each cosigner MUST serve a JSON response at `GET https://{service_url_host}/capabilities`. Discovery clients fetch this endpoint **after** validating the cosigner's signed SHIP token (§12.2) and merge the response with `(identity_key, service_url)` from the token to assemble a complete `MpcNodeInfo`.

Response: `Content-Type: application/json`. Recommended `Cache-Control: max-age=300`. Canonical JSON (sorted keys). Schema:

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
    "inbox_url": "https://<binary-messagebox-host-tbd>",
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

**v1 minimum subset (per ADR-0050):** for cross-impl interop in the M1 demo, both stacks MUST emit at minimum `{ curves, threshold_configs, fee_sats, version, max_presignatures?, min_balance_sats? }`. The richer fields above (`policy_hash`, `transport`, `accepted_cert_roots`, `cert_serials`, `audit_log_url`, etc.) become required at v1.5 / M2 once their producing infrastructure lands. Until then, parsers MUST tolerate their absence.

**Per-cosigner failure handling:** discovery clients fetching `/capabilities` from multiple cosigners in parallel MUST treat per-cosigner fetch failures (timeout, non-2xx, unparseable JSON) as a node-skip with warn-log — they MUST NOT abort the entire discovery on one bad cosigner. Reference impl: `bsv-mpc-overlay::discovery::discover_nodes` uses `futures::future::join_all` with per-request 5-second timeout.

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

## 12.5a Discovery result display contract (normative, per ADR-0033)

For every result row returned by `mpc.discover(filter)` (§15.4 SDK method), the conformant wallet MUST surface to the user:

| Field | Source | Notes |
|---|---|---|
| `fee_sats` | capabilities JSON `signing_fee_sats` | Per-signing fee |
| `fee_fiat_estimate` | `fee_sats × bsv_usd_rate` per Q17 oracle | Locale-aware (ISO 4217 minor units); staleness bound 300s |
| `chip_age_days` | (now - chip_token_created_at) / 86400 | On-chain age signal |
| `abort_rate_30d` | `mpc.aborted_30d / mpc.total_attempts_30d` | Recent abort rate |
| `successful_settlements_30d` | Count of successful sign ceremonies in last 30d | Volume signal |
| `jurisdiction` | Notary's declared `jurisdiction` field | E.g., "US-CA", "EU-DE", "global" |
| `support_url` | Notary's `support_url` capability field | Operator contact |
| `tofu_checks: [pass/fail × 7]` | Per §15.7 TOFU check results | Visible verification matrix |
| `reputation_score` | Per §12.5 formula (0.40 proofs + 0.20 age + 0.25 abort + 0.15 fee) | Single normalized scalar 0.0-1.0 |

Implementations SHOULD NOT collapse to "auto-picked." The `mpc.discover()` result MUST be a structured list, not just an opaque handle. Auto-pick (e.g., wallet picks highest reputation × cheapest) MAY be exposed as a one-tap convenience but the per-row data MUST remain accessible to the user.

Operators that omit `support_url` or `jurisdiction` fields in their capabilities JSON MUST be displayed with explicit `unavailable` markers — failing to render them at all is non-conformant (creates an asymmetric trust signal).

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
