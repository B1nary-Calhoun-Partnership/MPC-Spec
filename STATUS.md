# Status — 2026-05-17 (PM, late-late)

> Hand-maintained snapshot. Whoever sees this drift edits + commits. No bot.

## Current sprint: M1 (2026-05-29, 12 days out)

**M1 — Cross-impl mainnet signing demo:** https://github.com/B1nary-Calhoun-Partnership/MPC-Spec/milestone/1 · **6 of 16 closed (37.5%)**

**Partnership Roadmap project (all repos):** https://github.com/orgs/B1nary-Calhoun-Partnership/projects/1

## Closed this sprint

| # | Title | Closed via |
|---|---|---|
| #14 | conformance.yml CI workflow | [`439d4a4`](https://github.com/B1nary-Calhoun-Partnership/MPC-Spec/commit/439d4a4) (MPC-Spec) |
| #1  | bsv-mpc: BRC-42 dedup → bsv-rs canonical | [`1ec89d1`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/1ec89d1) (bsv-mpc) |
| #5  | bsv-mpc: enable insecure-assume-preimage-known | [`2b70997`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/2b70997) (bsv-mpc) |
| #34 | bsv-mpc: real-mainnet e2e for Path A CHIP | [`0423aad`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/0423aad) (bsv-mpc) |
| #35 | bsv-mpc: C2 (proxy↔KSS wire swap) — closed as misscoped (subsumed by #2) | (closed in GitHub) |
| #3  | bsv-mpc: canonical ExecutionId + SessionId + CBOR envelope | [`c7355e4`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/c7355e4) + [`92793a8`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/92793a8) + [`870f3a3`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/870f3a3) (bsv-mpc) |

Also landed (no MPC-Spec issue gating these but spec-affecting):
- **bsv-mpc [PR #1](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/pull/1) MERGED (`870f3a3`)** — canonical types + formulas + envelope module for MPC-Spec #3 parts A/B/C. §02 / §04 / §05 vectors reproduce byte-for-byte; all 8 §05.9.1 rejection cases caught. Closes #3 (typed types + canonical formulas + canonical CBOR envelope all on `main`).
- **bsv-mpc MessageBox transport — #2 parts 1–4 of 5 absorbed into `main`** (no PR; impl-only Calhoun-side work, gated by live-relay proof). Commits [`815156a`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/815156a) (scaffold + wire), [`17ea329`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/17ea329) (BRC-31 auth + HTTP routes + first live-relay proof), [`21b6cd3`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/21b6cd3) (`/ws` WebSocket subscribe with backfill + heartbeat + reconnect per §06.4 + §06.12), [`b0afed5`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/b0afed5) (**typed `MessageBoxClient` public API + `EnvelopeSubscription` + graceful `leaveRoom` on shutdown + cargo fmt CI gate fix**). Crate `bsv-mpc-messagebox` now ships `MessageBoxClient`, `EnvelopeSubscription`, `DecodedEnvelope` at the root; **3 live-relay scenarios all byte-exact in ~16s**. Part 5 (bridge integration into proxy + within-stack mainnet ceremony e2e with a real BSV txid) remains.
- **ADR-0050** CHIP token = canonical signed SHIP + `/capabilities` side-channel (Path A). §12.2 / §12.3 updated. Awaiting Mitch sign-off.
- **MPC-Spec #11** (joint ADR-0037 byte-equivalent CBOR re-encode) — **bsv-mpc half complete** in `870f3a3`'s `envelope.rs::decode_strict`. Leaving open until rust-mpc half lands (Ishaan's territory).
- `bsv-mpc` CI fully gated: build + clippy strict (-D warnings) + workspace tests + doctests + wasm32. Node 24 opt-in ahead of GH's 2026-06-02 forced switch. fmt locked. **396 tests green** (up from 367 at PR #1; +25 in `bsv-mpc-messagebox` lib alone — BRC-104 byte-shape vectors, server-event parser, `next_backoff` §06.12 sequence, ws URL scheme swap, `MessageBoxClient` construct/identity/clone, `decode_event` envelope fixture vector, `generate_message_id` shape). The prior CI run on commit `21b6cd3` failed `cargo fmt --check`; fix landed in `b0afed5` along with #14.
- `bsv-mpc` dep tree unblocked (bsv-rs 0.3.7 + generic-ec 0.5 + Cargo.lock committed + cggmp21-fork submodule dropped → upstream PR #200 branch via git URL).

## Who's doing what

| | Active | Next up | Blocked on |
|---|---|---|---|
| **John** (Calhoun) | M1 #2 MessageBox transport (auth + send + list + ack + WS subscribe + **typed `MessageBoxClient` API with `leaveRoom` on shutdown all live-proven**; remaining: bridge integration into proxy + within-stack mainnet ceremony e2e) | #4 presig lifecycle (~600-900 LOC) · #6 deploy 1 cosigner · #J1 cggmp21-fork org transfer/visibility | Ishaan #9 (only blocks #4) |
| **Ishaan** (Binary) | #7 cggmp24 pin · #8 canonical wire | **#9 byte-lock 3 ciphertexts** ← critical path · #10 deploy 2 cosigners | nothing |
| **Mitch** (Binary) | review ADRs 0030-0050 | sign off on ADR-0050 (Path A) · flag any of the 12 design calls in `CHANGES-PROPOSED.md` that don't fit | nothing |

## Critical path to M1 demo

`Ishaan #9` → `John #4` → `John #6 + Ishaan #10` (deploy) → `#12` (demo ceremony 2026-05-29)

## Where to look

- **`decisions/`** — all ADRs (0001-0049)
- **`PARTNERSHIP-PLAYBOOK.md`** — operating model, per-person work streams, drift detection
- **`CHANGES-PROPOSED.md`** — 12 design choices resolved Calhoun-side; partnership confirmation
- **`OPEN-QUESTIONS.md`** — outstanding Qs (Q15-Q60 mostly v1.5/v2 territory)
- **`conformance/test-vectors/`** — byte-locked test vectors
- **GitHub milestones** — [M1](https://github.com/B1nary-Calhoun-Partnership/MPC-Spec/milestone/1) (5/29) · [M2](https://github.com/B1nary-Calhoun-Partnership/MPC-Spec/milestone/2) (6/12)
- **Issue labels** — `impl:bsv-mpc` (John) · `impl:rust-mpc` (Ishaan) · `impl:joint` · `impl:spec`

## Upcoming

- **2026-05-29** — M1 cross-impl signing demo (mainnet TXID)
- **2026-06-12** — M2 Notary MVP launch + Phase 0 spec lock (8 ADRs)
- **v1.5** — post-M2 hardening
- **v2** — institutional tier (SOC2 Type II w/ Schellman; HSM/TEE reopens; Pro tier beta)
- **v3** — PQ migration triggers + multi-Notary marketplace

## What to do if you see this is stale

Edit + commit. That's the whole protocol.
