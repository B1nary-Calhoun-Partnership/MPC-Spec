# ADR-0040: Continuous runtime self-attestation + library allowlist

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 god-tier swarm — Security S5 (post-build runtime exploit). Mitch explicitly flagged this attack class in the 2026-05-12 partnership sync.

## Context

§17.6 originally specified that each cosigner verifies its own SHA-256 against Rekor at **startup only**. The build-attestation chain (§17.5 SLSA L3) is checked once; then the binary runs for hours / days / weeks until a share refresh or operator-driven restart.

Between the startup check and the moment a presig share is decrypted (ADR-0030 step 9), nothing re-attests the running process. Attack surface:

- **eBPF / dlopen / ptrace** memory corruption injects malicious code into the running cosigner process.
- **Container-escape** to host OS, then process memory tamper.
- **Supply-chain compromise of a transitively-loaded shared library** not enumerated in `binary_hash`'s materials — e.g., a libssl or libpython transitive dep that opens a `dlopen` hook.
- **Process hot-patch by a privileged sibling** (sysadmin / co-tenant on shared infrastructure).

A specifically nasty injection target is the `set_additive_shift` value passed into cggmp24 signing (§01.2.2 — the 4-line method our fork adds). An attacker that modifies the shift between Rekor-verify-at-startup and the actual signing emits signatures committing to **attacker-chosen BRC-42 offsets** — every subsequent signature signs under a key the attacker controls, while the audit log shows superficially valid `binary_hash` matches (the build artifact hash). The cosigner's running memory has been replaced; the on-disk binary is still legitimate.

§17.10 records `binary_hash` on chain; §17.7 reserves TEE attestation for v2. Both are useful but neither closes the runtime gap.

## Decision

### 1. Continuous re-attestation cadence (normative)

Beyond the §17.6 startup check, each cosigner MUST:

- **Re-verify at least once every 15 minutes (jittered ±2 minutes per ADR-0047 to avoid timer collisions).** A timer fires; re-compute the binary measurement (per §1a below); fetch the corresponding Rekor entry; verify the OIDC identity + build-attestation chain.
- **Re-verify immediately before any presig consumption that crosses a configurable burn threshold.** The threshold is **normative per profile** (per 2026-05-13 divergence-risk swarm — closes Q28 OPEN):

  | Profile | Burn threshold (sigs between re-verify) | Time-based cadence |
  |---|---|---|
  | `profile-edge` (CF Worker, Notary) | 500 | 15 min (jittered ±2min per ADR-0047) |
  | `profile-server` (Railway / dedicated host) | 1000 | 15 min (jittered) |
  | `profile-mobile` (cosigner-on-phone) | 100 | 30 min (jittered) |

  Implementations MAY tighten (lower threshold) but NOT loosen. Rekor fetch overhead is bounded by the caching policy in ADR-0046 (transient-failure tolerance).

### 1a. Binary measurement: hash mapped-memory r-xp regions (NOT `/proc/self/exe`)

**Per ADR-0045** (correctness fix surfaced by 2026-05-13 swarm loop-2 Security S1):

The threat model defended is **runtime memory tampering** (eBPF probe writes, dlopen injecting a shared lib, ptrace-attached patch, container-escape memory edits, hot-patch of `set_additive_shift`). These attacks modify **mapped executable memory**, not the on-disk binary. Hashing `/proc/self/exe` measures the on-disk file, which the attacker has not necessarily touched — leaving the live exploit undetected.

The correct primitive is to hash all **executable (`r-xp`) regions enumerated by `/proc/self/maps`**:

```
SHA-256(concat of all r-xp regions' contents, ordered by mapping start address)
```

Implementation:
- Read `/proc/self/maps` (Linux) or equivalent (macOS: vm_region; Windows: VirtualQuery loop).
- For each region with `r-xp` perms (read + execute + private), `mmap` it read-only or `process_vm_readv` it into the hasher.
- Concatenate in mapping-start-address order; hash with SHA-256.
- Compare result to a build-time-computed reference hash recorded in the build attestation's `materials` list under `runtime_text_segment_hash`.

A reference hash must be reproducibly computable at build time (the toolchain MUST produce identical r-xp content across build runs, which is the SLSA L3 reproducible-Cargo property §17.3 already establishes).

This closes the threat-model error introduced by ADR-0040's original `/proc/self/exe` text. See ADR-0045.

### 1b. Transient lookup failure vs proven mismatch

**Per ADR-0046** (correctness fix surfaced by 2026-05-13 swarm loop-2 Self-Critique #2):

- **Proven mismatch** (binary measurement ≠ reference hash, signed Rekor entry confirms reference, OIDC chain valid): MUST trip presig invalidation per §06.18 and emit `BinaryReverifyFailed`. Severity Sev-1.
- **Transient lookup failure** (Rekor service unavailable, network timeout, OIDC verifier unreachable): MUST NOT invalidate the presig pool. Wallet emits `BinaryReverifyDeferred` audit event with retry-after; re-attempt within the cached-result-validity window (default 24h). If failures persist past the validity window AND the next scheduled cadence is missed, escalate to `BinaryReverifyFailed` → Sev-1.

### 2. Failure handling (normative)

A re-verify failure MUST:

1. **Trip presig invalidation** per §06.18 (delete all stored `PresigBundle` rows; atomic, zeroize).
2. **Refuse further presig consumption** until re-verify passes.
3. **Emit an `AuditEntry`** with `event_kind = "BinaryReverifyFailed"` recording the deviation (computed-hash vs expected-hash) + timestamp.
4. **Escalate to Sev-1 IR** via §16.5 runbooks (this is the same severity as cosigner-compromise; IR-002 cascade).

A re-verify success MUST emit `event_kind = "BinaryReverified"` so the audit log shows the cadence held.

### 3. Library allowlist (normative)

The build attestation's `materials` list enumerates every static dependency. Implementations MUST:

- **Forbid loading any shared library not enumerated in `materials`.**
- **SHOULD ship with `-static-pie`** or equivalent (musl-static, fully statically linked Rust binaries) to minimize `dlopen` attack surface at all.
- **Where dynamic linking is unavoidable, MUST gate via seccomp / landlock policies** that block late `dlopen` (`mmap PROT_EXEC` of files not in the allowlist).

§17.11 "Forbidden" gets the new entry "Loading any shared library not enumerated in the build attestation's `materials` list."

## Rationale

- **Closes the boot-to-presig window.** §17.6 startup check + 15-minute re-verify + immediate-on-burn-threshold check together leave at most ~15 minutes of runtime between attestation events; any successful exploit must complete within that window AND survive the next re-verify.
- **Library allowlist closes `dlopen` injection.** Late-binding shared libraries are the primary live-runtime injection vector on Linux. Eliminating them (`-static-pie`) or whitelist-gating them with seccomp closes the class.
- **`set_additive_shift` injection is specifically caught.** The cggmp24 patched library's `set_additive_shift` function is in the binary's text segment; tampering with it requires writing to read-only memory or relinking. Both detectable by SHA-256 re-verify.
- **Composable with v2 TEE.** When v2 ships TEE attestation (§17.7), the continuous self-verify becomes a cheaper sibling of TEE PCR cross-check. The 15-min cadence + library allowlist are still useful even in TEE deployments as defense-in-depth.

## Consequences

### `bsv-mpc` (Calhoun)

- Implement re-attestation timer in `bsv-mpc-service` startup. Hook into cgroup / process supervisor.
- Wire `BinaryReverified` + `BinaryReverifyFailed` audit events.
- Ship `-static-pie` Cargo profile (with `+crt-static` for static C-runtime linking on Linux).
- Implement seccomp gate (cosigner refuses to start without seccomp filter loaded — fail-closed).
- ~400 LOC + integration tests covering re-verify failure paths.

### `rust-mpc` (Binary; impl Ishaan)

- Same re-attestation behavior in `crates/cosigner/`.
- Same `-static-pie` + seccomp posture.
- Audit event hooks identical.

### `MPC-Spec`

- §17.6 extended (already applied).
- §17.6.1 library allowlist added (already applied).
- §17.11 forbidden list updated (already applied).
- Q28 added: continuous re-Rekor cadence vs. presig-pool latency budget — what is the right N for the Notary SLI (§16.3)?

## Alternatives considered

- **TEE attestation only.** Defers to v2; doesn't help v1 stack.
- **One-shot startup check + share-refresh-cadence-only re-verify.** Status quo; window is up to 30 days (refresh cadence). Insufficient.
- **Continuous full re-attestation every signing.** Too expensive; adds 50-200ms per signature. The 15-min + burn-threshold compromise is the right tradeoff.
- **`-static` instead of `-static-pie`.** `-static-pie` provides ASLR (PIE) on a statically linked binary; better defense-in-depth.

## Status of M1 dependency

**v1.5.** Not a wire-compat blocker. Spec edit lands M2 window. Implementation post-Notary-MVP launch (the attack class is meaningful only at scale, where high-volume cosigners are juicy targets).

## See also

- Spec: [§17.6](../17-supply-chain.md), [§17.6.1](../17-supply-chain.md), [§17.11](../17-supply-chain.md)
- ADR-0030 (presig consumption — re-verify gate)
- ADR-0042 (IR-008 presig-pool poisoning, downstream of failed re-verify)
- 2026-05-13 swarm: Security S5

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
