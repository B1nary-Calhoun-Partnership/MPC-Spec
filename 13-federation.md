# 13 — Federation

**Status:** DRAFT
**Version:** v2 (partial cross-signing in v1 via §13.2; operator-replacement §13.7 is v2)
**Phase:** 2
**Decided by:** ADR-0013 (proposed)
**Last updated:** 2026-05-10

## 13.1 Purpose

Federation is the mechanism by which two (or more) operators run independently, each with their own root cert authority and infrastructure, while their cosigners can interoperate seamlessly.

For Calhoun ↔ Binary specifically: each runs their own certifier, MessageBox, audit log; cosigners under either root can be cross-signed; federation is mutual, not hierarchical.

## 13.2 Mutual cross-signing

Two operators establish federation by mutually issuing BRC-52⊕ root certs to each other:

1. Operator A's certifier issues a cert with `subject = operator_B_root_pubkey`, `subjectScheme = "single"`, `ttl = 7d`, root cert flag set.
2. Operator B does the same in reverse.
3. Both certs are published to the shared transparency log `tm_mpc_certs_v1`.
4. Each operator's cosigners list the other operator's root in `accepted_cert_roots` of their CHIP tokens.

Federation is symmetric. New operators join by mutual cross-signing with at least one existing root.

## 13.3 Trust composition

A verifier accepts a cosigner cert if it chains to ANY root in the verifier's trust store. Trust stores are local to each verifier; a wallet might trust:
- Calhoun root only (most conservative)
- Calhoun + Binary roots (default for the partnership)
- Calhoun + Binary + others (open federation)

There is **no privileged primary root**. New roots are added at any time by mutual cross-signing.

## 13.4 Self-issued certs

A cosigner MAY self-issue (subject == certifier). Self-issued certs are cryptographically valid; trust is delegated to the discovery + reputation layer (§12), not certificate issuance.

In practice, self-issued certs are rare — most cosigners get cross-signed by a federation root for default-trust UX. Self-issued is the escape hatch for operators who don't want any external trust authority.

## 13.5 Shared transparency log

Both operators publish to the same transparency log topic `tm_mpc_certs_v1` (§08.7).

- Each STH is signed by its issuing certifier.
- Cross-checking happens by BRC-22 readers — anyone can replay leaves, verify the chain.
- A discrepancy (one certifier publishing certs that another's STH doesn't witness) is detectable by audit.

## 13.6 Operator-level audit federation

Each operator runs their own audit log (§10), but all STHs are anchored to the same BSV chain. Cross-cosigner witness-cosigning (§10.6) operates *across* federation boundaries:

- A bsv-mpc cosigner can witness-cosign a rust-mpc cosigner's STH.
- A rust-mpc cosigner can witness-cosign a bsv-mpc cosigner's STH.
- Witness-cosigning across operators is the strongest signal of cross-implementation health.

## 13.7 Operator replacement choreography

A cosigner operator MAY be replaced via threshold resharing.

**Routine departure:**

1. Departing operator publishes `op_replacement.proposed` to BRC-22 `tm_mpc_signing` with the proposed new operator's BRC-52⊕ cert.
2. At least `t` of the remaining `n-1` operators (the "operator quorum") publish `op_replacement.acked` within 24h, signed under their BRC-52⊕ certs.
3. Once `t` acks accumulate, the surviving operators run threshold resharing per cggmp24 resharing primitive. The new operator receives a fresh share evaluated at a fresh polynomial; the joint public key is preserved.
4. The departing operator's CHIP token is revoked via `tm_mpc_revocations_v1`.
5. The new operator publishes a fresh CHIP token. Reputation starts at zero; participation proofs accrue.

**Compromise-driven replacement (IR-002, sub-30-min):**

Same choreography, faster timeline. Detection signals (failed Rekor reverification, anomalous attestation PCR, anomalous policy decline rate, BRC-22 reputation drop) trigger IR. `t-1` other operators ack within 30 minutes (one-vote-veto avoided; one-vote-pause respected by the operator-quorum gate). Resharing fires immediately on quorum.

## 13.8 Catch-up resharing

If an operator is offline at refresh time, the polynomial is constructed to include their *new* share evaluation, **sealed to that operator's BRC-52⊕ cert pubkey**, decryptable on next online.

This is critical: it means no operator can be coerced "in real time" to participate in a resharing or block one. The decision to refresh is taken by the on-line quorum; the offline party catches up asynchronously.

## 13.9 Disagreement → freeze

If federation peers disagree on a refresh proposal (e.g., one operator insists on replacing another, but the third doesn't ack), the proposal stalls.

Stalled proposals do NOT abort the existing ceremony state — the existing key shares remain valid until a successful resharing happens. Stalled state is published to BRC-22 for transparency.

## 13.10 Adding a new federation root

To add a third operator (e.g., a new Notary tier provider) to the federation:

1. Existing operators agree (off-spec — partnership decision).
2. New operator generates root pubkey + identity infra.
3. Each existing operator issues a root cert to the new operator.
4. New operator issues root certs back to each existing operator.
5. Cosigners under any root may now be cross-signed by any other.

There is no enrollment ceremony beyond mutual cross-signing.

## 13.11 Removing a federation root

A federation root removal is by:

1. Existing operators agree to revoke.
2. Each operator spends the revocationOutpoint UTXO of the cross-signed cert they issued to the leaving operator.
3. Cosigners under the leaving root remain valid until their own certs expire (max 24h cosigner cert TTL).
4. New cosigners under that root are not cross-signed.

Total removal time: max 24h (TTL bound).

## 13.12 Forbidden

- A privileged "primary" root that other roots defer to. The architecture is symmetric.
- Hardcoded root trust in implementations. Trust stores MUST be configurable per deployment.
- Federation extension to a root without mutual cross-signing. Unilateral cross-signing (root A signs root B without root B reciprocating) does not constitute federation.

## 13.13 Implementation notes

- rust-mpc certifier (`bins/certifier`) has the cert issuance machinery. Add the `op_replacement.*` event handlers to BRC-22 client.
- bsv-mpc has no certifier today. For Calhoun side, decision pending: stand up a certifier in bsv-mpc, or use rust-mpc's certifier with a Calhoun-controlled root key. Latter is faster; spec is agnostic.
- Both implementations MUST support reading the shared `tm_mpc_certs_v1` log and accepting certs from any root.

## 13.14 Test vectors

`conformance/test-vectors/13-federation.json`. Examples:
- Two-root federation: cross-signing succeeds; verifier accepts certs from either root.
- Operator replacement: routine flow with `t=2`, `n=3`.
- Compromise replacement: IR-002 flow, `t-1=2` acks.
- Catch-up resharing: offline party absorbs new share on reconnect.
- Stalled proposal: insufficient acks; existing state preserved.

## See also

- [`decisions/0013-mutual-cross-signing-federation.md`](decisions/0013-mutual-cross-signing-federation.md) — ADR.
- [`08-identity.md`](08-identity.md) — BRC-52⊕ + transparency log.
- [`16-operations.md`](16-operations.md) — RR-001 / IR-002 runbooks.
- [`18-recovery.md`](18-recovery.md) — recovery scenarios that invoke federation primitives.
