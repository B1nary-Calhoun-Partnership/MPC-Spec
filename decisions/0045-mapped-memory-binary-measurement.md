# ADR-0045: Mapped-memory binary measurement for runtime self-attestation

**Status:** Proposed
**Date:** 2026-05-13
**Stewards:** John Calhoun (Calhoun), Mitch Burcham (Binary)
**Credit:** 2026-05-13 loop-2 god-tier swarm Security L2-S1 — surfaced the threat-model-vs-mechanism mismatch in ADR-0040.

## Context

ADR-0040 specified that cosigners SHA-256 their "binary" against a Rekor-anchored reference. The original spec text (§17.6) implied `/proc/self/exe` or equivalent on-disk measurement.

Loop-2 Security flagged the correctness gap: the threat model ADR-0040 defends (eBPF / dlopen / ptrace / container-escape / runtime memory tamper of `set_additive_shift`) operates on **mapped executable memory**, not the on-disk file. An on-disk hash would pass while the live process is exploited.

This ADR specifies the correct primitive.

## Decision

Binary measurement for re-attestation (per ADR-0040 §1, §17.6) MUST be computed over **executable mapped memory** (`r-xp` regions enumerated by `/proc/self/maps` on Linux, or platform-equivalent):

```
binary_measurement = SHA-256(
    concat(
        for each r-xp region in /proc/self/maps, ordered by mapping start address:
            mmap(region, PROT_READ).contents  // OR process_vm_readv()
    )
)
```

Platform-specific equivalents:
- **Linux**: read `/proc/self/maps`, filter `r-xp` permissions
- **macOS**: `vm_region` API with `MACH_VM_REGION_INFO`
- **Windows**: `VirtualQuery` loop with `MEM_IMAGE | PAGE_EXECUTE_READ`

### Reference value

The reference `runtime_text_segment_hash` is computed at build time as part of the §17.5 SLSA L3 attestation `materials` list:

```
runtime_text_segment_hash = SHA-256(executable text segments of the static binary)
```

Reproducibility: this hash MUST be reproducible across SLSA L3 build runs. The §17.3 reproducible-Cargo + `-static-pie` constraints make the text segment content deterministic; ASLR offsets don't affect content hash (ASLR randomizes virtual addresses, not bytes).

### Implementation

For Linux:
```rust
fn measure_running_text() -> [u8; 32] {
    let mut h = Sha256::new();
    let mut regions: Vec<(u64, u64)> = parse_proc_self_maps()
        .filter(|m| m.perms.contains("r-xp"))
        .map(|m| (m.start, m.end))
        .collect();
    regions.sort_by_key(|&(start, _)| start);
    for (start, end) in regions {
        let len = (end - start) as usize;
        let ptr = start as *const u8;
        let region_bytes = unsafe { std::slice::from_raw_parts(ptr, len) };
        h.update(region_bytes);
    }
    h.finalize().into()
}
```

The implementation MUST handle:
- Pages locked / unreadable (skip with warning; partial measurement is non-conformant)
- Multiple text segments (linker can split text across regions for code separation)
- VDSO and runtime injected regions (these are part of the live process and MUST be included; reference hash records the expected set)

### Failure modes

- **Measurement mismatch** (computed ≠ reference): ADR-0040's "proven mismatch" path. Sev-1; presig pool invalidation.
- **Reference lookup transient failure**: ADR-0040's "transient lookup" path. Sev-3; retry with cached result valid for 24h.
- **Partial measurement** (e.g., one r-xp region unreadable): treat as proven mismatch (fail-closed).

## Rationale

- **Defends the actual threat.** eBPF, ptrace, dlopen, container-escape attacks all modify mapped memory in the running process. On-disk hashing misses them; mapped-memory hashing catches them.
- **`-static-pie` compatibility.** Statically-linked Rust binaries have a single text segment (or small number of named segments per linker script); reproducible across SLSA L3 builds.
- **Defense-in-depth with library allowlist** (ADR-0040 §17.6.1). Library allowlist prevents NEW shared libs from being loaded; mapped-memory hash catches modifications to ALREADY-loaded text.

## Consequences

### `bsv-mpc` + `rust-mpc`

- Replace any `/proc/self/exe` SHA-256 with mapped-memory measurement per Linux algorithm above.
- Cross-platform shim for macOS / Windows (or pin to Linux-only deployment).
- Build pipeline: compute `runtime_text_segment_hash` as part of SLSA L3 build provenance.
- ~200 LOC of measurement code + 100 LOC build-pipeline integration.

### `MPC-Spec`

- ADR-0040 §1a updated (text already applied per loop-2 fix).
- §17.10 BRC-18 audit binding includes `runtime_text_segment_hash` in addition to the existing `binary_hash` (on-disk).

## Alternatives considered

- **Hash on-disk binary only.** Rejected — wrong threat model.
- **Use TEE attestation only.** Defers to v2 (ADR-0016); not v1 path.
- **Periodically re-load binary from disk and compare to memory.** Too expensive (10s of MB re-read per cycle); doesn't catch all attack classes (ptrace can write to memory after the re-load).

## M1 dependency

**v1.5** (alongside ADR-0040 implementation work). M1 demo doesn't require runtime re-attestation; the M1 demo signs once on healthy quorum.

## See also

- ADR-0040 (continuous runtime self-attestation; this ADR is the correctness fix for §1a)
- ADR-0046 (Rekor caching budget; complementary)
- 2026-05-13 loop-2 swarm Security L2-S1
- LinuxPMI memory-introspection precedents (Volatility framework, OSSEC HIDS rootkit detection)

## Sign-off

- [ ] Calhoun (John Calhoun)
- [ ] Binary (Mitch Burcham)
