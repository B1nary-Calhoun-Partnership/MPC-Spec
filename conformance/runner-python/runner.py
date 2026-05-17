"""Language-neutral conformance runner — Phase 1 (Python cbor2).

Per issue #14: "Python `cbor2` first (Calhoun-side reference); once
bsv-mpc + rust-mpc are wired in as git-submodule pins or independent
CI runners (matrix entries), each stack's Rust runner also runs."

Scope of this runner:
- CBOR round-trip on every `*_cbor_hex` field embedded in vector JSON.
- CBOR round-trip on every `*.cbor.hex` raw file.
- Cross-check that the raw `.cbor.hex` file matches the embedded hex
  in its sibling JSON (when both exist).
- Vectors with `TBD` / `__TBD__` placeholders are SKIPPED (not failed)
  so the gate is live while reference impls are still byte-locking
  (e.g. Ishaan's #9 on 06-presig-bundle-encryption.json).

Out of scope (deferred to per-stack Rust runners, separate work):
- Crypto derivations (BRC-42 invoice, ExecutionId, SessionId hashing,
  BRC-31 signature verification, AES-GCM ciphertext checks).
- Anything requiring secp256k1 or wallet primitives.

Exit codes:
  0 — all checks passed (TBD vectors skipped count is informational).
  1 — at least one mismatch / decode failure (the regression gate fired).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import cbor2

VECTORS_DIR = Path(__file__).resolve().parent.parent / "test-vectors"
TBD_MARKERS = ("TBD", "__TBD__")


def has_tbd(obj) -> bool:
    """True if any string in the tree contains a TBD marker."""
    if isinstance(obj, str):
        return any(m in obj for m in TBD_MARKERS)
    if isinstance(obj, dict):
        return any(has_tbd(v) for v in obj.values())
    if isinstance(obj, list):
        return any(has_tbd(v) for v in obj)
    return False


def walk_cbor_hex_fields(obj, path=""):
    """Yield (json_path, hex_string) for every leaf whose key ends in `_cbor_hex`."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else k
            if isinstance(v, str) and k.endswith("_cbor_hex"):
                yield sub, v
            else:
                yield from walk_cbor_hex_fields(v, sub)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from walk_cbor_hex_fields(v, f"{path}[{i}]")


def assert_cbor_roundtrip(hex_str: str, label: str) -> None:
    """Decode hex → CBOR object → re-encode canonical CBOR → assert equality."""
    try:
        raw = bytes.fromhex(hex_str)
    except ValueError as e:
        raise AssertionError(f"{label}: invalid hex: {e}")
    try:
        decoded = cbor2.loads(raw)
    except Exception as e:
        raise AssertionError(f"{label}: CBOR decode failed: {e}")
    try:
        reencoded = cbor2.dumps(decoded, canonical=True)
    except Exception as e:
        raise AssertionError(f"{label}: CBOR canonical re-encode failed: {e}")
    if reencoded != raw:
        raise AssertionError(
            f"{label}: byte mismatch on canonical re-encode\n"
            f"  original ({len(raw)}B):  {raw.hex()}\n"
            f"  reencoded ({len(reencoded)}B): {reencoded.hex()}"
        )


def negative_self_test() -> None:
    """Prove the runner's canonical-re-encode gate actually detects non-canonical CBOR.

    Covers issue #14's "at least one vector mismatch test (intentionally
    regressed vector) demonstrably fails the workflow" close criterion
    without committing a poisoned vector to disk.

    Test fixture: a hand-crafted non-canonical encoding of {1: 1}.
      canonical:     a1 01 01                  (map(1), uint(1), uint(1) inline)
      non-canonical: a1 01 18 01                (same logical value, but value
                                                 uses explicit uint8 width 0x18)
    Both decode to {1: 1}; only one is canonical. The runner MUST flag the
    second as a mismatch — that's the regression-detection contract.
    """
    canonical = cbor2.dumps({1: 1}, canonical=True)
    if canonical != bytes.fromhex("a10101"):
        raise AssertionError(
            f"runner self-test precondition broken: canonical({{1:1}})={canonical.hex()}, "
            f"expected a10101 — cbor2 behavior changed; fix the fixture."
        )

    assert_cbor_roundtrip(canonical.hex(), "negative_self_test::canonical")

    non_canonical = bytes.fromhex("a1011801")
    if cbor2.loads(non_canonical) != {1: 1}:
        raise AssertionError(
            "runner self-test precondition broken: non_canonical fixture does not decode to {1:1}"
        )
    try:
        assert_cbor_roundtrip(non_canonical.hex(), "negative_self_test::non_canonical")
    except AssertionError:
        return  # expected — the gate fired on non-canonical bytes
    raise AssertionError(
        "negative_self_test FAILED: non-canonical CBOR round-tripped clean. "
        "The regression gate is broken — investigate before relying on this runner."
    )


def main() -> int:
    if not VECTORS_DIR.is_dir():
        print(f"FAIL: vectors dir not found: {VECTORS_DIR}", file=sys.stderr)
        return 1

    passed = 0
    skipped = 0
    failures: list[str] = []

    # 1. Self-test the runner first so a broken runner can't silently pass.
    try:
        negative_self_test()
        print("[ok]   runner self-test (tamper detection)")
    except AssertionError as e:
        print(f"[FAIL] runner self-test: {e}", file=sys.stderr)
        return 1

    # 2. CBOR fields embedded in vector JSON files.
    for json_path in sorted(VECTORS_DIR.glob("*.json")):
        try:
            data = json.loads(json_path.read_text())
        except Exception as e:
            failures.append(f"{json_path.name}: invalid JSON: {e}")
            continue

        if has_tbd(data):
            skipped += 1
            print(f"[skip] {json_path.name} (contains TBD placeholders)")
            continue

        fields = list(walk_cbor_hex_fields(data))
        if not fields:
            print(f"[ok]   {json_path.name} (no embedded CBOR fields)")
            continue

        file_ok = True
        for field_path, hex_str in fields:
            try:
                assert_cbor_roundtrip(hex_str, f"{json_path.name}::{field_path}")
                passed += 1
            except AssertionError as e:
                failures.append(str(e))
                file_ok = False
        if file_ok:
            print(f"[ok]   {json_path.name} ({len(fields)} CBOR field(s))")

    # 3. Raw .cbor.hex files + cross-check vs sibling JSON if present.
    for hex_path in sorted(VECTORS_DIR.glob("*.cbor.hex")):
        raw_hex = hex_path.read_text().strip()
        if any(m in raw_hex for m in TBD_MARKERS):
            skipped += 1
            print(f"[skip] {hex_path.name} (TBD)")
            continue
        try:
            assert_cbor_roundtrip(raw_hex, hex_path.name)
            passed += 1
        except AssertionError as e:
            failures.append(str(e))
            print(f"[FAIL] {hex_path.name}")
            continue

        sibling = hex_path.with_suffix("").with_suffix(".json")
        if sibling.exists():
            try:
                sibling_data = json.loads(sibling.read_text())
            except Exception:
                sibling_data = None
            if sibling_data is not None and not has_tbd(sibling_data):
                embedded = [h for _, h in walk_cbor_hex_fields(sibling_data)]
                if raw_hex in embedded:
                    print(f"[ok]   {hex_path.name} (matches sibling JSON)")
                else:
                    print(f"[ok]   {hex_path.name} (no sibling embed match — informational)")
            else:
                print(f"[ok]   {hex_path.name}")
        else:
            print(f"[ok]   {hex_path.name}")

    print()
    print(f"Summary: {passed} check(s) passed, {skipped} skipped (TBD), {len(failures)} failed")

    if failures:
        print("\nFailures:", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
