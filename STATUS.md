# Status — 2026-05-17

> Hand-maintained snapshot. Whoever sees this drift edits + commits. No bot.

## Current sprint: M1 (2026-05-29, 12 days out)

**M1 — Cross-impl mainnet signing demo:** https://github.com/B1nary-Calhoun-Partnership/MPC-Spec/milestone/1 · 14 issues

## Who's doing what

| | Active | Next up | Blocked on |
|---|---|---|---|
| **John** (Calhoun) | #14 conformance.yml CI · §06.14 ✓ (439d4a4) | #1 BRC-42 dedup · #3 canonical wire · #5 cargo feature · #J1 repo transfer; then #4 presig lifecycle (~600-900 LOC) | Ishaan #9 (only blocks #4) |
| **Ishaan** (Binary) | #7 cggmp24 pin · #8 canonical wire | **#9 byte-lock 3 ciphertexts** ← critical path | nothing |
| **Mitch** (Binary) | review ADRs 0030-0049 | flag any of the 12 design calls in `CHANGES-PROPOSED.md` that don't fit | nothing |

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
