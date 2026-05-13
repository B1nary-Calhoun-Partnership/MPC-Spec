# 17 — Supply Chain

**Status:** DRAFT
**Version:** v1
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

**(NEW per ADR-0040, proposed)** Beyond startup, re-verification MUST run **at least once every 15 minutes** AND immediately before any presig consumption that crosses a configurable burn threshold (default: every 1000 sigs or every share-refresh window, whichever first). Re-verify failure MUST trip presig invalidation per §06.18 and MUST cause the cosigner to refuse further presig consumption until re-verify passes. Each re-verify event (success or failure) MUST emit an `AuditEntry` with `event_kind = "BinaryReverified"` (success) or `"BinaryReverifyFailed"` (failure).

**Rationale.** §17.6 startup verification alone leaves a runtime gap: between startup and presig consumption, a memory-corruption exploit (eBPF, dlopen, ptrace, container-escape, supply-chain compromise of a transitively-loaded shared library not covered by `binary_hash`) can inject a malicious `set_additive_shift` value (§01.2.2), causing every subsequent signature to commit to attacker-chosen BRC-42 offsets while audit/BRC-18 records remain superficially valid. The 15-minute cadence + presig-burn-trigger closes this gap. See [ADR-0040](decisions/0040-continuous-runtime-self-attestation.md).

### 17.6.1 Library allowlist (NEW per ADR-0040)

The build attestation's `materials` list enumerates every static dependency. Implementations MUST:

- Forbid loading any shared library not enumerated in `materials`.
- SHOULD ship with `-static-pie` or equivalent (musl-static, fully-statically-linked Rust binaries) to minimize dlopen attack surface.
- WHERE dynamic linking is unavoidable, MUST gate via seccomp / landlock policies that block late `dlopen` (`mmap PROT_EXEC` of files not in the allowlist).

This complements §17.6 — a re-verify cycle catches an exploit that survives the boot-time check; the library allowlist catches an exploit that introduces unauthorized code at runtime via `dlopen`.

## 17.7 TEE attestation cross-check (v2 reserved)

**Not applicable in v1.** v1 ships without TEE per §16.1 — cost-benefit doesn't justify it.

When v2 adds TEE deployment as an option, the TEE attestation will include the binary measurement (SHA-256 / PCR / MRTD), and counterparties will verify both the TEE attestation (signed by TEE root keys) AND the binary measurement matching the Rekor entry. Together that proves "this code was produced by an authorized CI run AND is currently running in a genuine TEE."

For v1, supply-chain provenance is **build-time only** via the §17.1–§17.6 chain. Runtime cross-check is bounded by share-refresh cadence (§16.5).

## 17.8 Revocation

When a binary version is found vulnerable:

1. Maintainer publishes a Rekor annotation: `revoked: true, reason: "CVE-XXXX-NNNNN"`.
2. On next start, every cosigner re-verifies its Rekor entry.
3. Revoked entries cause fail-closed (refuse to start).
4. Operators are notified (via PagerDuty + BRC-22 audit).

Time-to-revoke globally: bounded by cosigner restart interval (typically <24h with operator practices).

## 17.9 Conformance

A cosigner MUST present, on request, the pair `(binary_hash, rekor_uuid)`. v2 deployments additionally present `attestation_doc`.

Counterparties MAY refuse to participate if either:
- Doesn't verify (Rekor signature invalid).
- Is revoked (per §17.8).
- (v2 only) Attestation says different binary than the one we're talking to.

`RuleKind::RequireAttestation` in policy (§09) is reserved for v2; v1 deployments do not use it.

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
- bsv-messagebox-cloudflare has manual quality gates per CLAUDE.md. Add CI + Sigstore.
- Both implementations MUST commit `Cargo.lock` and ensure `cargo --locked` is used in CI.

## 17.15 Vulnerability disclosure program + bug bounty (normative, per CHANGES-PROPOSED #11)

### 17.15.1 v1.5 launch — HackerOne managed program

Calhoun and Binary jointly fund a HackerOne managed program for v1.5 (post-Notary-MVP launch). Scope:

- bsv-mpc (Calhoun stack) + rust-mpc (Binary stack) source code
- bsv-rs + bsv-sdk + bsv-wallet-toolbox + bsv-wallet-toolbox-rs (per-stack SDKs)
- rust-message-box CF Worker (Calhoun) + Binary's Railway-hosted message-box server
- MPC-Spec itself (cryptographic-correctness findings on spec text)

Out of scope: third-party dependencies (Sigstore Rekor, CF Workers infrastructure, cggmp24 upstream — those have their own VDPs).

**Annual bounty budget:** ~$50,000 (split 50/50 between Calhoun and Binary).

**Severity buckets:**
- Critical (key extraction, forged signature on mainnet, audit-chain rewrite): $10k-25k
- High (privilege escalation, IR-class bypass): $2k-8k
- Medium (denial-of-service amplification, parser-diff with exploit path): $500-2k
- Low (informational, hardening recommendations): $100-500

Researchers contact: security disclosure at hackerone.com/calhoun-binary-partnership (handle TBD). 90-day coordinated disclosure window per ISO/IEC 30111 + 29147.

### 17.15.2 v2 expansion — Immunefi (crypto-specialist bounty)

Starting v2, also list on Immunefi to attract crypto-specialist researchers with bigger per-finding bounties.

**Annual bounty budget v2:** ~$100,000 (Immunefi-side).

**Severity buckets:** higher than HackerOne, reflecting crypto market norms — Critical findings up to $100k each.

Researchers submit either platform; per-finding researcher chooses (no double-payout). Operator triages on either.

### 17.15.3 Security disclosure obligations

Each operator's customer-onboarding docs (per §16.1.1) MUST include:
- VDP contact information (HackerOne + Immunefi handles)
- Coordinated disclosure timeline expectation (90 days standard)
- Post-resolution publication policy (CVE assignment via MITRE or Sigstore-numbering; public advisory)

### 17.15.4 security.txt

Both operators MUST publish a `/.well-known/security.txt` (RFC 9116) at their public-facing endpoints (Notary URLs, message-box hostnames, public-facing wallets). The security.txt MUST include:
- VDP contact
- Encryption (PGP key fingerprint OR alternative secure-channel)
- Acknowledgments URL (list of past contributors)
- Preferred-Languages
- Canonical URL

## 17.14 Vendor / single-point-of-failure matrix (NEW per ADR-0042)

The v1 stack chains several external trust anchors. Each is enumerated below with its in-scope failure mode and the mitigation owner. Institutional-onboarding diligence (per §16.1.1) requires the operator to maintain a current copy of this matrix as part of their customer-facing security documentation.

| Trust anchor | Role | Failure mode | Mitigation owner | Diversification status |
|---|---|---|---|---|
| **Cloudflare Workers / Durable Objects** | rust-message-box relay host (Calhoun stack); some Notary hosts | DO eviction; Worker quota DoS; CF outage | Calhoun operator | **SPOF**: v2 adds second-vendor MessageBox (Fly.io / Railway / self-host). §06.7 federation already supports. |
| **Railway** | Binary message-box server host | Railway outage; container migration | Binary operator (Ishaan) | **SPOF** for Binary stack. Federated to CF via §06.7 partial mitigation. |
| **Sigstore Fulcio** | Short-lived signing cert issuance | Fulcio root key compromise; Fulcio service outage during a release | Calhoun + Ishaan (both consume) | **External SPOF** — Sigstore trust root. Mitigation: pinned root key set; Rekor inclusion proofs detect post-hoc rewrites. |
| **Sigstore Rekor** | Transparency log of build attestations | Rekor data loss; Rekor SLA breach | Sigstore project | **External SPOF**. Mitigation: §17.10 BRC-18 audit binding re-anchors `binary_hash` on BSV chain. |
| **GitHub Actions / GitHub OIDC** | CI build provenance + OIDC identity for Sigstore signing | GitHub outage; OIDC token compromise; account takeover | Calhoun + Ishaan (both rely on) | **External SPOF**. Mitigation: pinned action SHA, branch protection, mandatory 2FA, secrets-rotation cadence. |
| **`cggmp24` LFDT-Lockness upstream** | Threshold ECDSA library | Upstream maintainer absconds; subtle CVE not disclosed | Calhoun (fork maintainer; PR #200 upstreaming `set_additive_shift`) | **Critical dependency**. Mitigation: partnership fork at `cggmp21-fork`; reviewable diff (1 commit on upstream). |
| **BSV miners** | `tm_mpc_audit` PushDrop chain confirmations + `tm_mpc_revocations` | Miner censorship of audit PushDrops; reorg of audit chain | Implicit (miners) | **Decentralization-dependent**. Mitigation: §10.5.7 step 0 multi-source STH cross-check; reorg-tolerance bounded by 6-conf. |
| **Iroh / n0-computer** | Optional v2 QUIC direct-P2P (§06.6); NOT v1 | n0 abandons project; protocol-level vulnerabilities | Both operators (v2 only) | **v2 risk**. Q6 OPEN-QUESTIONS reserves WebTransport / libp2p substitute. |
| **`bsv-rs` (Calhoun's BSV SDK)** | Calhoun stack BSV primitives | Calhoun absconds; supply-chain attack on crates.io publish | Calhoun | **Partnership-internal SPOF**. Mitigation: Mitch maintains independent `bsv-sdk` stack; conformance vectors enforce wire-compat (#S3 in action items). |
| **`bsv-sdk` (Binary's BSV SDK)** | Binary stack BSV primitives | Mirror of `bsv-rs` risk on Binary side | Ishaan | **Partnership-internal SPOF**. Same mitigation. |

**Pen-test starting points (per §17.14 vendor matrix):** A Mandiant / NCC Group / Trail of Bits engagement would prioritize: (a) MessageBox relay BRC-31 auth path (§06), (b) un-stubbed `proofs.rs::publish_proof / query_proofs` calls (§10.10), (c) cert-chain parser at federation boundary (§13.7), (d) presig coordinator ciphertext-replay surface (ADR-0030 §06.17.3 single-use enforcement), (e) OTel redaction linter scope (§16.4 — does it cover all log sinks or only spans?), (f) `set_additive_shift` injection point (§01.2.2; ADR-0040 continuous re-attestation mitigates).

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
