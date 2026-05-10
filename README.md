# MPC-Spec

> The shared specification for a vendor-neutral BSV threshold-signing network, jointly developed and independently implemented by **Calhoun** (`bsv-mpc`) and **Binary** (`rust-mpc`).

## Goal

Two independent Rust implementations. One protocol. **A vendor-neutral, composable threshold-signing network on BSV that competes with Fireblocks via per-signature pricing and flexible cosigner arrangements.**

Mitch's framing: *"a cosigner is just a BRC-100 wallet, and an MPC wallet exposes BRC-100"* — enabling infinite composition. Both implementations adhere to this spec; both ship at their own cadence; either implementation can drop in as any party in any ceremony.

## How to navigate this repo

Read in this order. Each doc is short and has a clear purpose.

| File | Purpose |
|---|---|
| [`PROPOSAL.md`](PROPOSAL.md) | The headline proposal. **Read this first.** Five highest-leverage findings + seven open design questions for the partnership to agree on. |
| [`DESIGN.md`](DESIGN.md) | Full god-tier design rationale, per-layer picks, cross-layer dependencies. The "why" behind every spec decision. |
| [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) | The questions for the partnership to settle. Each links to a future ADR. |
| `01-cggmp24-pin.md` … `18-recovery.md` | The spec itself, 18 numbered files. Each starts with a STATUS line: **LOCKED** / **DRAFT** / **PLACEHOLDER**. |
| [`decisions/`](decisions/) | Architectural Decision Records. Each is a single locked choice, dated and signed by both parties when agreed. |
| [`appendices/swarm-reports/`](appendices/swarm-reports/) | Detailed per-zone analysis from the design swarm — depth that didn't fit in the spec proper. |
| [`conformance/`](conformance/) | Test vectors and conformance harness scaffold. Both implementations run this. |

## Status legend

Every spec file begins with one of:

- **LOCKED** — agreed by both parties, ADR exists. Changes require an ADR-update with both-party sign-off.
- **DRAFT** — proposed by the drafter, open for the other party to react / edit / redline. Promotes to LOCKED via PR + ADR.
- **PLACEHOLDER** — file exists; content TBD. Usually because it depends on a question still in `OPEN-QUESTIONS.md`.

## Two-party decision process

This repo has two stewards: one from each implementation team.

1. **Proposing a change.** Open a PR. Include rationale or link to the ADR.
2. **Reviewing.** A change to a LOCKED section requires explicit OK from both stewards. A change to a DRAFT section requires OK from at least the *other* implementation's steward.
3. **ADRs.** Every LOCKED spec section has a corresponding ADR. ADRs are immutable once accepted; superseded by a new ADR with explicit reference.
4. **Disagreement.** If consensus stalls, raise a question in `OPEN-QUESTIONS.md` and discuss in a partnership sync. The spec doesn't move forward on disputed sections.

## Implementations

| Repo | Owner | Language | Status |
|---|---|---|---|
| [`bsv-mpc`](https://github.com/B1nary-Calhoun-Partnership/bsv-mpc) | Calhoun | Rust | 5 crates, ~21.7K LOC, 15/15 mainnet POCs |
| Binary's MPC implementation (URL TBD by Binary) | Binary | Rust | 8 lib crates + 3 binaries, ~24K LOC, full CI |
| [`bsv-messagebox-cloudflare`](https://github.com/Calhooon/bsv-messagebox-cloudflare) | Calhoun | Rust → WASM | Deployed CF Worker, BRC-31 + D1 + FCM |

Both MPC repos will conform to this spec. Federation between them is the v1 deliverable.

Calhoun's open-source reference repos live at [github.com/Calhooon](https://github.com/Calhooon) — including [`bsv-rs`](https://github.com/Calhooon/bsv-rs) (BSV SDK), [`bsv-wallet-toolbox-rs`](https://github.com/Calhooon/bsv-wallet-toolbox-rs), [`bsv-middleware-cloudflare`](https://github.com/Calhooon/bsv-middleware-cloudflare) (BRC-31 + BRC-29 middleware), [`bsv-messagebox-cloudflare`](https://github.com/Calhooon/bsv-messagebox-cloudflare) (the Calhoun-operated MessageBox), [`bsv-wallet-cli`](https://github.com/Calhooon/bsv-wallet-cli), [`bsv-overlay-cloudflare`](https://github.com/Calhooon/bsv-overlay-cloudflare), and others. Binary is welcome to swap any references in this spec to their own canonical URLs.

## Phases

| Phase | Files | What it locks |
|---|---|---|
| **Phase 0** — cryptographic foundation | §01–05 | TSS pin, ExecutionId, SessionId, BRC-42 canonicalization, message envelope. **The cross-impl gate.** No joint ceremony works until these lock. |
| **Phase 1** — security-critical layers | §06–10 | Transport, BRC-31 auth, BRC-52⊕ identity, policy, audit. |
| **Phase 2** — operational stack | §11, 13, 16–18 | Fees, federation, operations, supply chain, recovery. |
| **Phase 3** — product surface | §12, 15 | Discovery, Notary product. |
| **Phase 4** — compliance | §14 | Conformance test suite both implementations run. |

## License

MIT OR Apache-2.0. Consistent with both implementation repos.

## Stewards

- **Calhoun side:** John Calhoun ([@Calgooon](https://github.com/Calgooon)) — public org [@Calhooon](https://github.com/Calhooon).
- **Binary side:** TBD — to be assigned by Binary on first review of this repo.
