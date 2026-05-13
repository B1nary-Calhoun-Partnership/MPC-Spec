# ADR-0049: Out-of-band cert revocation primer for IR-005 chicken-and-egg

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 loop-2 god-tier swarm Security L2-S3 — surfaced the IR-005 cert-revocation chicken-and-egg: `tm_mpc_revocations` is signed under the very root being revoked.

## Context

ADR-0042 §16.5.5 IR-005 (Certifier-key compromise) says "revoke root cert (BRC-22 `tm_mpc_revocations`), re-issue cosigner certs under successor root, mandatory force-refresh." Loop-2 Security flagged the chicken-and-egg: the revocation event itself is signed under the root being revoked. If the root is compromised, an attacker can issue valid-looking revocations of other things, OR refuse to sign the revocation of itself.

§07.7 BRC-31 sessions accept certs signed by any valid root. Without an out-of-band signal for successor commitment, a fresh successor root is indistinguishable from an attacker-issued root.

## Decision

### 1. Out-of-band successor commitment (normative)

Before any cosigner's root cert reaches its `notAfter`, the operator MUST publish a **successor commitment** out-of-band:

- **On-chain anchored**: a successor commitment is a PushDrop on overlay topic `tm_mpc_certs_v1` containing:
  - `successor_root_pubkey_hash: bstr32` — SHA-256 of the new root pubkey
  - `published_at: u64` — Unix timestamp
  - `notBefore: u64` — when the successor becomes valid
  - `current_root_pubkey: bstr33` — current root for cross-validation
  - `BRC-77 signature by the current root`
- **Operator's public webpage**: the same commitment is published on a well-known URL (e.g., `https://operator.example/successor-commitment.json`) with TLS cert pinning. The webpage MUST be served from a domain with a published security.txt.

The successor commitment is published AT LEAST 30 days before the current root's `notAfter`. This gives all relying parties time to learn the successor's pubkey via the on-chain anchor OR the operator's webpage.

### 2. Revocation requires successor pre-commit

For IR-005 (cert compromise), the revocation event MUST be:

1. **Signed by the successor root** (if pre-committed per §1 above) — this is the trust-bootstrap.
2. **Cross-published** on operator's TLS-pinned webpage (operator owns the DNS + TLS, separate trust anchor).
3. **Cross-signed by an external trust anchor** if available (e.g., another partnership root, or a third-party CA).

If the successor was NOT pre-committed (compromise happens in the first 30 days of root operation), the revocation falls back to:

1. Operator publishes new successor commitment via TLS-pinned webpage IMMEDIATELY.
2. All relying parties verify the operator's domain ownership via DNSSEC + Certificate Transparency log (cross-check).
3. Relying parties accept the new successor's first signed message as the trust-bootstrap.

This is weaker than the pre-committed case (it relies on DNS + TLS-CT to bootstrap trust) but unblocks the recovery flow.

### 3. Verifier acceptance procedure

When a relying party (cosigner or verifier) sees a `RevocationAnnouncement` for a root:

1. Look up the successor commitment for the to-be-revoked root.
2. If commitment exists AND is on-chain anchored AND `notBefore < now()`: accept the revocation AS LONG AS the new successor's signature is on the revocation announcement.
3. If no commitment exists: refuse the revocation; treat as suspicious. Operator must publish a successor commitment via the fallback procedure above.
4. Emit `RevocationProcessed` audit event with full chain of trust verified.

### 4. Quarterly successor pre-commit

To minimize the unprepared-compromise window, operators MUST pre-commit a successor root every 90 days regardless of need. The committed successor is dormant (unused for signing) but pre-established as the next root. This makes the "no commitment exists" case rare in practice.

## Rationale

- **Closes the chicken-and-egg.** Successor pre-commit means the recovery trust-bootstrap is established BEFORE the compromise, not derived from the very thing being recovered.
- **Multi-channel trust.** On-chain + TLS-pinned webpage + cross-signed gives 3 independent trust anchors; an attacker compromising 1 doesn't compromise all 3.
- **Quarterly pre-commit is cheap.** 30 days operational lead time + 90-day pre-commit cadence = always a successor ready.
- **DNS/TLS fallback when no pre-commit.** Slower trust-bootstrap but unblocks recovery.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Implement successor commitment emission (90-day cadence).
- Implement revocation acceptance procedure per §3 above.
- ~200 LOC + tests.

### Calhoun + Binary operations

- Operate 90-day successor pre-commit cadence.
- Maintain TLS-pinned webpage for fallback revocation publication.
- Cross-publish successor commitments with the peer operator (third-party trust anchor).

### `MPC-Spec`

- §16.5.5 IR-005 references this ADR for the trust-bootstrap procedure.
- §08 cert format reserves `successor_commitment_url: tstr` field (RECOMMENDED) in BRC-52⊕.
- Q33 (operator credential rotation overlap) resolved by 90-day pre-commit cadence.

## Alternatives considered

- **Trust the on-chain `tm_mpc_revocations` event signed by current root.** Rejected per the chicken-and-egg.
- **External CA-anchored revocation.** Rejected — adds vendor dependency (a CA we don't control).
- **Federation cross-revocation only (peer operator co-signs).** Acceptable as a secondary trust anchor but not sufficient alone (peer compromise compounds).

## M1 dependency

**v1.5.** Not M1-critical; M1 demo doesn't exercise certifier-key recovery. Implementation alongside §08 + §16.5.5 implementation work.

## See also

- §16.5.5 (IR-005 runbook)
- §08 (BRC-52⊕ cert format)
- Q33 (operator credential rotation — resolved here)
- ADR-0042 (IR taxonomy)
- 2026-05-13 loop-2 swarm Security L2-S3

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
