# ADR-0020: Versioning policy — v1 / v2 / v3 spec versions

**Status:** Proposed
**Date:** 2026-05-10
**Stewards:** John Calhoun (Calhoun), TBD (Binary)

## Context

The initial MPC-Spec scaffold was written as one coherent vision document with 18 numbered sections plus 6 ADRs and 6 appendices. Every section was either `LOCKED`, `DRAFT`, or `PLACEHOLDER` — but no section was tagged with a target version. This created two problems:

1. **Binary's review surface is unbounded.** Every DRAFT section implicitly reads as "this could ship soon," forcing engagement with the entire spec to evaluate the partnership.
2. **Scope creep risk on v1 deliverables.** Sections written at institutional grade (§13 federation, §16 ops, §17 supply chain) could be misread as gating for the 2-week cross-impl test and 30-day Notary MVP.

The partnership v1 scope is narrow: ship the cross-impl signing test + Notary MVP. Several spec sections describe primitives that don't need to be implemented for v1 to ship. Without versioning, that ambiguity slows down review and creates scope creep risk.

## Decision

The spec is versioned into three increments: **v1**, **v2**, **v3**. Each numbered section (`§00`–`§18`) declares a target version in a `**Version:**` line near the top, alongside `**Status:**`, `**Phase:**`, and `**Decided by:**`. The canonical scope-vs-version mapping lives in `ROADMAP.md` at the repo root.

- **v1** ships the partnership's first deliverable: cross-impl mainnet signing test + Notary MVP.
- **v2** ships hardening and product expansion 3-6 months post-v1.
- **v3** ships future-prep, multi-Notary marketplace, and institutional/estate features 6-12+ months post-v1.

A section in v1 MAY have subsections that defer to v2 or v3; those subsections are called out inline. The version line reflects the section's *baseline* target.

## Rationale

Three-tier versioning balances scope discipline against vision clarity:

- **A narrow v1 keeps Binary's review tractable.** Engaging with 30% of the spec for v1 sign-off is dramatically easier than engaging with 100%. Faster sign-off = faster shipping.
- **The spec preserves the full vision.** Future versions are documented now, but explicitly as "not yet." Anyone reading the spec sees both what ships and what's coming, without confusing the two.
- **ROADMAP.md as a single index.** Easier to maintain than scattering version markers across each section (though both exist for redundancy). The roadmap is the table-of-contents for "what ships when."
- **Demote-by-default policy on movement between versions.** If a v1 section is at risk of slipping the partnership timeline, the default move is to demote to v2, not to slip v1. Better tight v1 late shippable than sprawling v1 indefinitely delayed.

## Consequences

- **Spec:**
  - Every numbered section gets a `**Version:**` line.
  - `ROADMAP.md` lives at repo root; documents v1/v2/v3 split with per-section justification.
  - README.md "Phases" table gains a Version column.
  - PROPOSAL.md frames v1 deliverables explicitly.
- **ADRs:** This ADR (0020) becomes the policy reference for any future version-axis decision.
- **Implementations:** Both `bsv-mpc` and `rust-mpc` need to conform to v1 of the spec to ship the partnership v1 deliverable. v2/v3 implementations layer on top of v1 — they don't replace it. Wire format and protocol primitives in v1 are stable; v2/v3 add capabilities, they don't break existing ones.

## Promotion / demotion procedure

Moving any section between versions requires:

1. PR updating the section's `**Version:**` line and the `ROADMAP.md` table.
2. A new ADR explaining the rationale (e.g., "ADR-00XX: Promote §09.X cumulative daily cap to v1 because [reason]").
3. Both stewards' sign-off on the ADR.

A promotion (v2 → v1) is a scope expansion of v1 and should be carefully justified — preferably with a concrete blocking case from a v1 implementation. A demotion (v1 → v2) requires similar justification but is the default safe move.

## Alternatives considered

- **Per-section version tag only, no ROADMAP.** Cluttered to navigate; harder for new readers. Rejected.
- **Three separate spec branches (v1-spec, v2-spec, v3-spec).** Triple maintenance burden; hard to cross-reference. Rejected.
- **No versioning; just labels like "MVP / hardening / future".** Too informal; doesn't carry the same scope-discipline weight as numbered versions tied to ADRs. Rejected.
- **Two-tier (v1 / v2) only.** Tempting for simplicity, but the "institutional/estate/multi-Notary marketplace" features have a different horizon than the "hardening" features and benefit from being grouped separately. Three tiers reflects the actual rollout shape.

## Open questions

- **Cadence for v2 / v3 cuts.** v1 cadence is partnership-driven (2-week test + 30-day MVP). v2 / v3 cadences are not yet defined and depend on adoption signals.
- **Backward compatibility guarantee across versions.** v1 spec defines wire format. v2 should be backward-compatible with v1 wire format (additive only). v3 may include protocol migrations (DKLs23, FROST) that are not byte-compatible but are bridgeable via threshold resharing — same joint pubkey, different signing protocol on top. Specifying the compatibility commitment is a future ADR.

## See also

- [`ROADMAP.md`](../ROADMAP.md) — the canonical v1/v2/v3 section-by-section mapping
- [`CONTRIBUTING.md`](../CONTRIBUTING.md) — PR process; version moves follow the same flow

## Sign-off

- [ ] Calhoun (John Calhoun, [@Calgooon](https://github.com/Calgooon))
- [ ] Binary (TBD)
