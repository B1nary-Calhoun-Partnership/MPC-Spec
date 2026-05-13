# ADR-0044: Wallet-renderer canonicalization for `rendered_text` across intent types

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 loop-2 god-tier swarm Self-Critique — surfaced that ADR-0032's `request_view_hash` references `rendered_text` but no renderer canonicalization exists. User decision: keep ADR-0032 in M1, author renderer spec in parallel.

## Context

ADR-0032 binds approval signatures to `request_view_hash` which includes a `rendered_text` field — the human-visible string the wallet displayed. The 2026-05-13 swarm Self-Critique noted that ADR-0032's M1 classification is unworkable without a canonical wallet-renderer spec for `rendered_text`: payment / token-transfer / sCrypt-covenant / BRC-100 `internalizeAction` flows render very differently, and divergent integrator implementations produce divergent `rendered_text` for the same underlying intent.

This ADR specifies the canonical renderer surface so both bsv-mpc and rust-mpc produce byte-identical `rendered_text` for the same intent.

## Decision

### 1. Renderer scope

A conformant wallet MUST produce `rendered_text` per the canonical algorithm below for each of the following intent types:

- **Payment intent** (P2PKH or P2MS output to non-self addresses)
- **Token transfer intent** (BRC-22/27/76 token output)
- **sCrypt covenant spend** (P2SH-equivalent output with embedded `scriptPubKey`)
- **BRC-100 `internalizeAction` intent** (`internalizeAction` description from BRC-100 spec)
- **Multi-purpose intent** (transaction with mixed outputs)

### 2. Canonical renderer algorithm

```
rendered_text = canonical_render(intent) where:

intent.kind == "payment":
    "Send <amount_satoshis> sats (~<fiat_estimate> <fiat_currency>) to <human_address_or_alias> "
    "with fee <fee_sats> sats. Counterparty: <counterparty_identity>."

intent.kind == "token_transfer":
    "Transfer <token_amount> <token_symbol> tokens to <human_address_or_alias> "
    "(value ~<fiat_estimate> <fiat_currency>). Token contract: <token_contract_hash>."

intent.kind == "script_spend":
    "Execute sCrypt covenant spend at contract <covenant_address>. "
    "Output value: <amount_satoshis> sats. Covenant function: <function_name>. "
    "Function args summary: <hash_of_args_argv-style>."

intent.kind == "brc100_internalize":
    "Internalize action: <action_description>. "
    "From: <source>. To: <destination>. Notes: <protocol_notes>."

intent.kind == "multi":
    "Compound transaction with N outputs: <output_1_summary>; <output_2_summary>; ..."
```

All strings MUST be NFC-normalized UTF-8. `<amount_satoshis>` is the integer sat count; `<fiat_estimate>` is the locale-aware ISO 4217 minor-units string (e.g., "$1,234.56" for `en-US` USD); `<human_address_or_alias>` resolves to BRC-100 cert name if a cert chain to a known root exists, else the first-8-hex-chars of the pubkey.

### 3. Locale + language

`human_locale` field in `request_view_hash` preimage is the BCP-47 language tag (e.g., `en-US`, `de-DE`, `ja-JP`, `zh-Hans`). The renderer MUST produce text in the named locale. For locale-aware decimal/currency formatting, implementations use ICU or equivalent.

A wallet displays `rendered_text` in the user's chosen locale; the canonical preimage hash binds both the locale and the rendered text. If the user changes locale between view and approval, the approval re-issues with a new `request_view_hash`.

### 4. Conformance vector

`conformance/test-vectors/09-rendered-text.json` includes one canonical vector per intent type:

- Payment, en-US, USD: `"Send 100000000 sats (~$50.00 USD) to 1A1zP1...EQK... with fee 333 sats. Counterparty: anonymous + 0x02abcd1234..."`
- Token transfer, en-US: `"Transfer 100 USDT-on-BSV tokens to 1B2y...K... (value ~$100.00 USD). Token contract: 0x123456..."`
- sCrypt spend, en-US: `"Execute sCrypt covenant spend at contract 1C3z...K.... Output value: 10000 sats. Covenant function: settle. Function args summary: sha256:abcdef..."`
- BRC-100 internalizeAction, en-US: `"Internalize action: payment-received. From: payee@example.com. To: 1D4y...K.... Notes: invoice 12345 paid."`
- Multi-output, en-US: `"Compound transaction with 3 outputs: Send 50000000 sats to 1A...; Send 25000000 sats to 1B...; Fee output 333 sats."`

Each vector includes the canonical CBOR serialization of `request_view_hash` preimage for byte-locking.

### 5. Out of scope (future ADRs)

- NFT metadata rendering (ADR-future)
- Streaming-payment intent (ADR-future)
- Cross-chain bridge intent (out of scope; not a BSV-native intent)
- L3 sCrypt fee covenant (deferred to v3 per ROADMAP)

## Rationale

- **Closes ADR-0032's M1 dependency** (renderer-spec-required) without dropping the security gap mitigation.
- **Byte-locked across implementations** via `09-rendered-text.json` vectors; defeats divergent integrator interpretations.
- **Locale-aware** without sacrificing canonical-binding; user-facing UX adapts; cryptographic binding doesn't.
- **Extensible** via the intent-kind switch; new intent types added per future ADRs without breaking existing.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Implement canonical-render functions per the intent-kind dispatch.
- Wire ICU or equivalent for locale-aware formatting.
- Conformance vector validation in CI.
- ~400-600 LOC across both stacks (mostly the locale/currency formatting + intent classification).

### `MPC-Spec`

- §09.5.1 normative `rendered_text` clause references ADR-0044 for canonical algorithm.
- §15 SDK uses canonical-render before display to ensure WYSIWYG between display and approval-hash.
- Conformance vector `conformance/test-vectors/09-rendered-text.json` added (loop-3 deliverable).

## Alternatives considered

- **Free-form `rendered_text` (status quo before this ADR).** Rejected — divergent integrator impls.
- **Single canonical intent format (no intent-kind dispatch).** Rejected — sCrypt covenant rendering can't be forced into a "Send X to Y" template.
- **Defer renderer spec to v1.5 (drop ADR-0032 from M1).** Rejected per user direction (2026-05-13 swarm decision).

## M1 dependency

**M1 critical** (unblocks ADR-0032). Renderer impl can ship as a fixed-format-only first cut (payment intent only) for the 2026-05-29 demo; full intent-kind coverage by 2026-06-12 Phase 0 lock.

## See also

- ADR-0032 (approval-quorum `request_view_hash` — consumer)
- ADR-0031 (sign-time confirmation contract — display surface)
- 2026-05-13 loop-2 swarm Self-Critique
- BCP-47 (language tag spec); ICU formatting library

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
