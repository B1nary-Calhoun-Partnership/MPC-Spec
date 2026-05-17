# ADR-0050: CHIP token architecture — canonical signed SHIP + `/capabilities` side-channel (Path A)

**Status:** Proposed
**Date:** 2026-05-17
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)

## Context

The MPC partnership needs cosigners to be discoverable on the BSV overlay so any client (wallet, other cosigner, indexer) can find them by topic `tm_mpc_signing`. Standard SHIP admin tokens (BRC-23 / BRC-48 PushDrop, 5 fields) carry only `(protocol, identity_key, domain, topic, signature)`. MPC-specific metadata — supported curves, threshold configurations, per-signing fee, software version, optional limits — does not fit in that surface.

Pre-Path-A, `bsv-mpc-overlay/src/chip.rs` worked around this by emitting a 5-field PushDrop where **field[4] was a capabilities JSON blob** (not a signature) and the script was **locked with the identity key directly** (not the BRC-42 child). The canonical TS validators (`@bsv/overlay-discovery-services`) enforce `fields.length === 5` AND require field[4] to be a DER ECDSA signature over `sha256(concat(fields[0..3]))` signed by the BRC-42 child of the identity key (protocol `[2, "service host interconnect"]`, key_id `"1"`, counterparty `Anyone`, `forSelf=true`), AND require the script's locking pubkey to equal that same BRC-42 child. See `SHIPTopicManager.ts:30-41` and `utils/isTokenSignatureCorrectlyLinked.ts`. The pre-Path-A shape satisfied **none** of these — mainnet validators silently rejected every bsv-mpc cosigner advertisement. Discovery was broken end-to-end while local tests passed.

This ADR resolves how to advertise MPC-specific capabilities **without forking the canonical SHIP wire format** that the partnership and external overlay operators depend on.

## Decision

**CHIP token = canonical 5-field signed SHIP admin token, byte-identical to `bsv-rs::create_signed_overlay_admin_token` (which itself is byte-identical to `@bsv/sdk 1.10.1`'s `pushdrop.lock(fields, [2, "service host interconnect"], "1", "anyone", true, true, "before")` path).**

**MPC-specific capabilities are served off-chain at `GET https://{domain}/capabilities` by each cosigner. Discovery clients fetch this endpoint after validating the SHIP token's signature linkage, and merge `(identity_key, domain)` from the token with the capabilities response to assemble a full `MpcNodeInfo`.**

The `bsv-mpc-overlay::chip::create_chip_token` function is a thin wrapper over `bsv-rs::create_signed_overlay_admin_token` with the MPC topic (`tm_mpc_signing`) baked in. The wire format is **the canonical SHIP token, unchanged** — bsv-mpc emits exactly what the canonical TS validators admit.

## Rationale

The canonical `@bsv/overlay-discovery-services` validator suite is the wire-format spec for SHIP / SLAP overlay advertisements across the BSV ecosystem. Babbage and every overlay operator depend on its stability; partnership policy treats canonical TS as immutable from our side (we change consumers to conform; we do not modify canonical). Embedding capabilities in the script — at field[4] (which canonical validators reserve for the signature) or in a hypothetical field[5] (which canonical validators reject because `fields.length !== 5`) — would isolate bsv-mpc adverts from every conformant overlay validator on the network.

The side-channel pattern is well-precedented: SHIP/SLAP itself bootstraps discovery; service-specific metadata (rate limits, pricing, supported features) is conventionally served by the advertised service over HTTP. Adding `/capabilities` next to the cosigner's existing `/health` endpoint reuses the same HTTPS surface clients already need to reach to actually use the cosigner. The cost is one additional HTTP round-trip per cosigner during discovery, parallelizable across cosigners (`futures::future::join_all` in `discover_nodes`).

Choosing this path also preserves the **single-source-of-truth** for token bytes: bsv-mpc, rust-mpc, and any future implementation can all use the same `create_signed_overlay_admin_token` (or the equivalent in their SDK) and produce identical SHIP tokens. Cross-impl wire-compat is automatic.

## Consequences

- **`bsv-mpc`:**
  - `bsv-mpc-overlay/src/chip.rs` — refactored 2026-05-17 (commit `4565bd7`). `create_chip_token(identity_priv: &PrivateKey, domain: &str)` wraps `bsv::overlay::create_signed_overlay_admin_token`. `parse_chip_token` returns `ChipTokenInfo { identity_key, domain }` (signature linkage validated via `bsv-overlay-discovery::validation::is_token_signature_correctly_linked`). 11 new tests cover byte-parity, signature linkage, and the 5 negative cases (4-field legacy / wrong protocol / wrong topic / tampered sig / wrong locking key).
  - `bsv-mpc-proxy/src/wallet_api.rs` — `capabilities_impl` + `GET /capabilities` route added (commit `d21bd6c`). Config knobs `MPC_THRESHOLD_CONFIGS` + `MPC_MIN_BALANCE_SATS` added.
  - `bsv-mpc-overlay/src/discovery.rs` — Stage 2 parallel `/capabilities` fetch added (commit `b88ac68`). Per-cosigner fetch failure → node skipped with warn-log; partial discovery preferred over abort.
- **`rust-mpc`:** Likely no change — Binary's stack uses the canonical signed format already (per partnership stack diagram). Confirmation needed: verify `rust-mpc` cosigner advertisement code emits exactly the canonical `pushdrop.lock(..., includeSignature=true)` shape; if any custom path exists, switch to canonical. Ishaan to confirm via reply on this ADR. **Add a `GET /capabilities` endpoint on the rust-mpc cosigner HTTP surface** matching the schema in §12 (new sub-section).
- **`bsv-messagebox-cloudflare`:** No change.
- **Spec:** Add §12.x sub-section specifying the canonical CHIP-token contract (= 5-field signed SHIP token, byte-identical to `@bsv/sdk 1.10.1` `pushdrop.lock` with `[2, "service host interconnect"]`, key_id `"1"`, counterparty `Anyone`, `forSelf=true`, `includeSignature=true`, `lockPosition="before"`) and the `/capabilities` side-channel JSON schema. Update §15 (Notary product) to reference `/capabilities` as a publishable capability surface.
- **Test vectors:**
  - `conformance/test-vectors/12-chip-token-canonical.json` — byte-locked example: a CHIP token built from a pinned identity privkey + domain, asserted byte-identical to the `bsv-rs` parity fixture in `~/bsv/bsv-rs/tests/vectors/overlay_admin_token_ts_parity.json`. Both stacks MUST round-trip this vector.
  - `conformance/test-vectors/12-capabilities-response.json` — JSON schema + canonical example for the `/capabilities` response. Both stacks MUST emit conformant JSON.

No breaking changes for external SHIP/SLAP consumers (canonical adverts were always required). Breaking change for any bsv-mpc consumer that depended on the pre-fix CHIP token parser accepting 4-field legacy tokens — those are now rejected with a specific `OverlayError::InvalidChipToken("canonical signed CHIP token must have exactly 5 fields...")` error.

## Alternatives considered

- **Path B: 6-field CHIP variant + extend canonical TS+Rust validators to admit variable-field tokens with signature at last position.** Rejected: forks the SHIP wire spec, requires Mitch/Ishaan approval + ADR sign-off + external overlay operators (Babbage, every other validator deployment) to upgrade. Per [`feedback_canonical_ts_immutable`](../../bsv-mpc/CLAUDE.md) — the canonical TS reference is immutable from our side.
- **Capabilities in a separate, second on-chain token.** Rejected: doubles the per-cosigner mainnet cost, introduces ordering dependency (which token to trust if they disagree?), and forces ad-hoc topic-management on cosigners.
- **Capabilities embedded in the `domain` field via query string.** Rejected: stuffs structured data into a URI surface, hits URI-length validators, and breaks the principle that the script field has one semantic meaning.
- **Capabilities served via DNS TXT records.** Rejected: DNS TTL semantics + lack of TLS auth make this strictly worse than HTTPS GET on a domain the client is already going to TLS-connect to.

## See also

- Spec section: `§12 Discovery` (sub-section addition pending — same PR)
- Conformance vectors (pending — same PR): `conformance/test-vectors/12-chip-token-canonical.json`, `12-capabilities-response.json`
- bsv-rs reference: `~/bsv/bsv-rs/src/overlay/overlay_admin_token_template.rs` (commit-locked at `create_signed_overlay_admin_token`)
- Rust validator (canonical port of TS): `~/bsv/rust-overlay-public/crates/overlay-discovery/src/validation.rs::is_token_signature_correctly_linked`
- TS canonical validator: `~/bsv/overlay-discovery-services/src/SHIP/SHIPTopicManager.ts`, `src/utils/isTokenSignatureCorrectlyLinked.ts`
- bsv-mpc commits implementing this ADR: `4565bd7` (chip.rs Path A refactor), `d21bd6c` (proxy /capabilities), `b88ac68` (discovery side-channel fetch)

## Sign-off

- [x] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (Mitch Burcham, [@mitch-burcham](https://github.com/mitch-burcham))
