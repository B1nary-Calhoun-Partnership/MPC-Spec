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
- **bsv-mpc MessageBox transport — #2 absorbed into `main` through Phase D** (no PR; impl-only Calhoun-side work, gated by live-relay proof at each step). Chain of commits:
  - [`815156a`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/815156a) — scaffold + wire
  - [`17ea329`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/17ea329) — BRC-31 auth + HTTP routes + first live-relay proof
  - [`21b6cd3`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/21b6cd3) — `/ws` WebSocket subscribe + backfill + heartbeat + reconnect per §06.4 + §06.12
  - [`b0afed5`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/b0afed5) — typed `MessageBoxClient` + `EnvelopeSubscription` + graceful `leaveRoom` on shutdown
  - [`83612b1`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/83612b1) — Phase A: canonical `wrap_round_message` / `unwrap_envelope_to_round_message` in `bsv-mpc-core` (byte-locked vector tests for round-translation per §05.4.5 + broadcast-expansion per §05.4.7)
  - [`1dbcf2c`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/1dbcf2c) — Phase B: typed `send_round_message` / `subscribe_round_messages` on `MessageBoxClient`
  - [`067ce2a`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/067ce2a) — Phase C: `MessageBoxListener` dispatcher primitive in `bsv-mpc-service` (within-stack echo e2e byte-exact in 8.39s)
  - [`3f4865c`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/3f4865c) — Phase D: real `DkgCoordinator` wired in — 2-of-2 CGGMP'24 DKG over MessageBox e2e with byte-identical `joint_pubkey` on both cosigners. Joint pubkey = `023060dabc995235559b60fa6fe2a59a27d021a5ff80412418d6b5a97948281686`. BSV address = `1A7EDx3TrKWEwCHjm5Z6CD81ih8eyi3YyP`. DKG wall-clock 20.7s; total 71.6s (prime-dominated).
  - [`b18d2a6`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/b18d2a6) — Phase E code: `SigningHandler` (mirrors `DkgHandler`, wraps `SigningCoordinator`), within-stack mainnet TX harness (E2E_MAINNET-gated).
  - [`ed7feaf`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/ed7feaf) — wallet:3321 admin-Origin fix + `docs/WALLET-3321.md` reference (every claim cited to file:line in cousin repos, empirically verified).
  - **Phase E LIVE on mainnet** — two independent bsv-mpc-service cosigners executed full DKG → fund → sign → broadcast cycle through the live Calhoun MessageBox relay. Real BSV mainnet TX **[`82ccb15c49985a32b355a618f417bb7a09ec4ee5cf34e539e9baaebb74dadc29`](https://whatsonchain.com/tx/82ccb15c49985a32b355a618f417bb7a09ec4ee5cf34e539e9baaebb74dadc29)** broadcast 2026-05-17 with ARC status SEEN_ON_NETWORK, 192-byte P2PKH→P2PKH single-input single-output, signed by the joint 2-of-2 key produced through MessageBox-routed cggmp24 (byte-identical DER on both cosigners, pre-flight bsv-rs ECDSA verify passed). Wall-clock 132.5s (72s prime gen + 18s DKG + 9s WoC index + 5s sign + broadcast). Joint pubkey `02dac1fb9219fba1855d1ece48161b15094c1f01bed1de4a8edcb98f674c2f3884`, joint address `1hWpbcKqZnFYdxLczCQQXjFudnkihnUjy`. Funding tx `a5ce607f98b9ba000a09421ab68d54306888c3881f0af6b338cb509a1b94da0b`.
  - Plus [`5c2110a`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/5c2110a) test-only `TEST_LOCK` for env-mutating proxy tests (CI race that surfaced during Phase A's run).
  - **All of #2 (parts A-E) shipped + live-proven on mainnet.** Cross-stack #17 (1-bsv-mpc + 1-rust-mpc 2-of-2 over MessageBox) remains the only outstanding piece, gated on Ishaan's canonical landing.
- **ADR-0050** CHIP token = canonical signed SHIP + `/capabilities` side-channel (Path A). §12.2 / §12.3 updated. Awaiting Mitch sign-off.
- **MPC-Spec #11** (joint ADR-0037 byte-equivalent CBOR re-encode) — **bsv-mpc half complete** in `870f3a3`'s `envelope.rs::decode_strict`. Leaving open until rust-mpc half lands (Ishaan's territory).
- `bsv-mpc` CI fully gated: build + clippy strict (-D warnings) + workspace tests + doctests + wasm32. Node 24 opt-in ahead of GH's 2026-06-02 forced switch. fmt locked. **396 tests green** (up from 367 at PR #1; +25 in `bsv-mpc-messagebox` lib alone — BRC-104 byte-shape vectors, server-event parser, `next_backoff` §06.12 sequence, ws URL scheme swap, `MessageBoxClient` construct/identity/clone, `decode_event` envelope fixture vector, `generate_message_id` shape). The prior CI run on commit `21b6cd3` failed `cargo fmt --check`; fix landed in `b0afed5` along with #14.
- `bsv-mpc` dep tree unblocked (bsv-rs 0.3.7 + generic-ec 0.5 + Cargo.lock committed + cggmp21-fork submodule dropped → upstream PR #200 branch via git URL).

## Who's doing what

| | Active | Next up | Blocked on |
|---|---|---|---|
| **John** (Calhoun) | **M1 #2 MessageBox transport DONE — Phases A-E all live-proven; Phase E mainnet TXID [`82ccb15c…`](https://whatsonchain.com/tx/82ccb15c49985a32b355a618f417bb7a09ec4ee5cf34e539e9baaebb74dadc29) broadcast SEEN_ON_NETWORK.** Within-stack proof complete. | #4 presig lifecycle (~600-900 LOC) · #6 deploy 1 cosigner · #J1 cggmp21-fork org transfer/visibility | Ishaan #9 (only blocks #4) |
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
