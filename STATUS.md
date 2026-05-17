# Status — 2026-05-17 (PM)

> Hand-maintained snapshot. Whoever sees this drift edits + commits. No bot.

## Current sprint: M1 (2026-05-29, 12 days out)

**M1 — Cross-impl mainnet signing demo:** https://github.com/B1nary-Calhoun-Partnership/MPC-Spec/milestone/1 · **3 of 14 closed**

**Partnership Roadmap project (all repos):** https://github.com/orgs/B1nary-Calhoun-Partnership/projects/1

## Closed this sprint

| # | Title | Closed via |
|---|---|---|
| #14 | conformance.yml CI workflow | [`439d4a4`](https://github.com/B1nary-Calhoun-Partnership/MPC-Spec/commit/439d4a4) (MPC-Spec) |
| #1 | bsv-mpc: BRC-42 dedup → bsv-rs canonical | [`1ec89d1`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/1ec89d1) (bsv-mpc) |
| #5 | bsv-mpc: enable insecure-assume-preimage-known | [`2b70997`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc/commit/2b70997) (bsv-mpc) |

Also landed (no MPC-Spec issue gating these but spec-affecting):
- **ADR-0050** CHIP token = canonical signed SHIP + `/capabilities` side-channel (Path A). §12.2 / §12.3 updated. Awaiting Mitch sign-off.
- `bsv-mpc` CI fully gated: build + clippy strict (-D warnings) + workspace tests + doctests + wasm32. Node 24 opt-in ahead of GH's 2026-06-02 forced switch. fmt locked.
- `bsv-mpc` dep tree unblocked (bsv-rs 0.3.7 + generic-ec 0.5 + Cargo.lock committed + cggmp21-fork submodule dropped → upstream PR #200 branch via git URL).
- Path A end-to-end implemented on bsv-mpc: signed SHIP token emit + validate, `/capabilities` endpoint, discovery side-channel fetch.

## Who's doing what

| | Active | Next up | Blocked on |
|---|---|---|---|
| **John** (Calhoun) | M1 #3 canonical wire · M1 #2 MessageBox transport · real-mainnet e2e of Path A CHIP | #4 presig lifecycle (~600-900 LOC) · #6 deploy 1 cosigner · #J1 cggmp21-fork org transfer/visibility | Ishaan #9 (only blocks #4) |
| **Ishaan** (Binary) | #7 cggmp24 pin · #8 canonical wire | **#9 byte-lock 3 ciphertexts** ← critical path · #10 deploy 2 cosigners | nothing |
| **Mitch** (Binary) | review ADRs 0030-0050 (added ADR-0050 today) | sign off on ADR-0050 (Path A) · flag any of the 12 design calls in `CHANGES-PROPOSED.md` that don't fit | nothing |

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
