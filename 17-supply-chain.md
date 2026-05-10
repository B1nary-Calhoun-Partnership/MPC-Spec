# 17 — Supply Chain

**Status:** DRAFT
**Phase:** 2
**Decided by:** ADR-0017 (proposed)
**Last updated:** 2026-05-10

## 17.1 Goal

Cryptographic provenance of every running cosigner binary, from source to running enclave. A user must be able to verify "what code produced this signature" without trusting either operator.

## 17.2 The triad

| Layer | What it provides |
|---|---|
| **Reproducible builds** | Anyone can rebuild from source and get bit-identical binaries. |
| **Sigstore (cosign + Fulcio + Rekor)** | Releases are signed; signatures and binaries are logged in a public transparency log. |
| **SLSA Level 3** | Build provenance (where, by whom, with what inputs) is signed and linkable from the Rekor entry. |

## 17.3 Reproducible builds

Both implementations MUST:

- `cargo --locked` builds with `Cargo.lock` checked in.
- `SOURCE_DATE_EPOCH` set in CI for deterministic timestamps.
- Vendored dependencies (`cargo vendor`) committed for any non-crates.io source.
- Pinned `rust-toolchain.toml` to a specific stable release.
- CI verifies bit-for-bit reproducibility on a second runner (different OS, different machine).

A non-reproducible build is a CI failure.

## 17.4 Sigstore signing

Each release:

1. CI builds the binary (above).
2. `cosign sign-blob --keyless` — OIDC-keyless flow via Fulcio.
3. Fulcio issues a 10-minute cert tied to the OIDC identity (the GitHub Actions workflow ID).
4. Cosign uploads the signature + cert to Rekor.
5. Rekor returns a `tlog_uuid`.

Both signature and the Rekor entry are public.

## 17.5 SLSA Level 3 attestations

CI MUST produce in-toto attestations:

- **`build-attestation`** — `(builder, source_repo, commit_sha, build_steps, output_hash)`. Signed.
- **`provenance-attestation`** — links the attestation to the cosign signature.

Both attestations are uploaded to Rekor as separate entries linked by `tlog_uuid`.

The CI workflow MUST be a hermetic builder (GitHub Actions reusable workflow with `permissions: contents: read, id-token: write`).

## 17.6 Runtime self-verification

On startup, each cosigner MUST:

1. Compute SHA-256 of its own binary.
2. Look up the binary's Rekor entry by hash.
3. Verify the Rekor entry exists and is signed by an expected OIDC identity.
4. Verify the build-attestation links to a known-good source commit.

Failure to verify MUST cause the cosigner to refuse to start (fail-closed). Logs a clear error and exits non-zero.

## 17.7 TEE attestation cross-check

When the cosigner runs in a TEE (§16.7), the TEE attestation includes the binary measurement (SHA-256 / PCR / MRTD).

Counterparties MUST verify both:
- The TEE attestation is valid (signed by the TEE root keys).
- The binary measurement in the attestation matches the binary's Rekor entry.

Together, this proves: "this code was produced by an authorized CI run AND is currently running in a genuine TEE."

## 17.8 Revocation

When a binary version is found vulnerable:

1. Maintainer publishes a Rekor annotation: `revoked: true, reason: "CVE-XXXX-NNNNN"`.
2. On next start, every cosigner re-verifies its Rekor entry.
3. Revoked entries cause fail-closed (refuse to start).
4. Operators are notified (via PagerDuty + BRC-22 audit).

Time-to-revoke globally: bounded by cosigner restart interval (typically <24h with operator practices).

## 17.9 Conformance

A cosigner MUST present, on request, the triple `(binary_hash, rekor_uuid, attestation_doc)`.

Counterparties MAY refuse to participate if any of the three:
- Doesn't verify (Rekor signature invalid).
- Is revoked (per §17.8).
- Doesn't match (attestation says different binary than the one we're talking to).

This is enforced via `RuleKind::RequireAttestation` in policy (§09).

## 17.10 BRC-18 audit binding

Participation proofs (§10) include `binary_hash`. This pins the on-chain audit record to the *specific code* that produced the signature.

If a vulnerability is later disclosed in version `X`, every signature produced by version `X` is identifiable by the BRC-18 records on-chain. This is the supply-chain equivalent of certificate revocation: detectable by anyone reading the chain.

## 17.11 Forbidden

- Skipping CI signing for a release.
- Using `cosign sign` (not `--keyless`) — keyless OIDC flow is mandatory.
- Logging full attestation documents in OTel spans (the document may contain binary contents).
- Shipping a binary without a corresponding Rekor entry. Pre-release / development builds MUST be marked `pre-release` so verifiers can refuse them.

## 17.12 Implementation notes

- bsv-mpc currently has no Sigstore integration. Add GitHub Actions reusable workflow.
- rust-mpc has Docker matrix builds + GHCR push. Extend to add cosign + Rekor + SLSA attestation.
- rust-message-box has manual quality gates per CLAUDE.md. Add CI + Sigstore.
- Both implementations MUST commit `Cargo.lock` and ensure `cargo --locked` is used in CI.

## 17.13 Test vectors

`conformance/test-vectors/17-supply-chain/`. Examples:
- A sample binary with valid Rekor entry; verify.
- A sample binary with invalid signature; reject.
- A revoked binary; reject.
- TEE attestation cross-check (Nitro example).

## See also

- [`decisions/0017-supply-chain-sigstore-slsa.md`](decisions/0017-supply-chain-sigstore-slsa.md) — ADR.
- [`16-operations.md`](16-operations.md) — TEE attestation policy.
- [`08-identity.md`](08-identity.md) — `binary_hash` field in cert.
- [`10-audit.md`](10-audit.md) — BRC-18 proof includes `binary_hash`.
- Sigstore docs: https://docs.sigstore.dev
- SLSA framework: https://slsa.dev
- TUF: https://theupdateframework.io
