# Contributing to MPC-Spec

This is a two-party specification, not a typical OSS repo. Two implementation teams ship independently; this spec is what makes them interoperable. Contributions follow a structured process.

## Who can contribute

Anyone can open issues, raise questions, or propose changes via PR. Acceptance requires steward review.

- **Calhoun-side steward:** [@Calgooon](https://github.com/Calgooon)
- **Binary-side steward:** TBD

## Spec sections — three statuses

Every numbered spec file (`01-…` through `18-…`) starts with a `**Status:**` line:

- **LOCKED** — both parties have agreed; ADR exists. Changes require an ADR-update with both-party sign-off.
- **DRAFT** — proposed by one drafter, open for the other party to redline. Promotion to LOCKED requires both-party OK and a new ADR.
- **PLACEHOLDER** — file exists; content depends on a question still open in `OPEN-QUESTIONS.md`.

## Change types

### A. Editing a DRAFT section

1. Open a PR with the proposed change.
2. Tag the *other* implementation's steward as reviewer.
3. Discussion happens in PR comments.
4. Merge requires the other steward's OK (a `LGTM` comment is sufficient for DRAFT).
5. Major changes (anything affecting the wire format, threat model, or cross-implementation behavior) should reference an ADR draft in the same PR.

### B. Promoting DRAFT → LOCKED

1. Spec text must be reviewed by both implementation teams.
2. A test vector exists where applicable (hashes, formulas, byte-layout sections).
3. An ADR is filed under `decisions/` with both stewards explicitly signing off.
4. Both implementations confirm they can implement to the spec without further changes.

### C. Editing a LOCKED section

1. **Avoid this.** LOCKED means the spec is the contract.
2. If unavoidable: open a PR with a new ADR superseding the original.
3. Both stewards must sign off in writing.
4. Affected implementations must have a migration plan in the ADR.

### D. Raising an open question

1. Add an entry to `OPEN-QUESTIONS.md`.
2. Tag both stewards.
3. Discussion happens in the linked issue or partnership sync.
4. Resolution becomes an ADR.

## Architectural Decision Records (ADRs)

ADRs live in `decisions/`. Format follows MADR (Markdown Any Decision Record) lite:

```
# ADR-XXXX: <Title>

**Status:** Proposed | Accepted | Superseded by ADR-YYYY
**Date:** 2026-MM-DD
**Stewards:** John Calhoun (Calhoun), <TBD> (Binary)

## Context
What problem are we solving? Why now?

## Decision
What did we decide? (One paragraph, maximum.)

## Rationale
Why this option, given the alternatives?

## Consequences
What changes for each implementation? What's the migration path?

## Alternatives considered
(Brief — keep evidence in the design doc, not here.)
```

Numbering is monotonic. Use `0001`, `0002`, …, padded to 4 digits.

## PR conventions

- Title format: `[spec/§XX] Concise description` or `[ADR-XXXX] Concise description`.
- Body should reference the relevant section, the ADR (if any), and the implementation impact for both repos.
- Squash-merge by default; keep `main` history readable.

## Test vectors

Test vectors are spec artifacts. Both implementations MUST produce byte-identical results against the canonical vectors in `conformance/test-vectors/`.

- Adding/changing a vector requires the same review process as a spec change.
- A vector that one implementation cannot reproduce blocks LOCKED status until reconciled.

## Disagreement → resolution

If consensus stalls on a PR or ADR:

1. Add the question to `OPEN-QUESTIONS.md`.
2. Schedule a partnership sync (45 min, both stewards + implementation engineers).
3. The spec does not move forward on the disputed section until resolution.
4. If neither side will yield, document the impasse in the ADR's `Status` field as `Stalled`, and re-open after a cooling period.

The protocol is more important than any single technical preference. Where both options are workable, default to the one that minimizes implementation churn for *both* teams.
