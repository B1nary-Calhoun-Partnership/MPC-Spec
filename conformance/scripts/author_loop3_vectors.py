#!/usr/bin/env python3.12
"""
Author the 4 loop-3 conformance vectors:
- 05-message-envelope-diff.cbor.hex (parser-diff pair, accepted + rejected)
- 06-presig-bundle-encryption.json (BRC-2 self-encryption byte-lock; cross-validates against rust-mpc)
- 09-rendered-text.json (ADR-0044 wallet-renderer canonicalization)
- 18-recovery-kdf.json (Argon2id known-passphrase → known-KEK)

Run: /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 author_loop3_vectors.py
"""

import cbor2
import argon2
import hashlib
import hmac
import json
import os

OUT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/test-vectors"
os.makedirs(OUT, exist_ok=True)


def write_json(name, data):
    path = os.path.join(OUT, name)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"wrote {path}")


def write_text(name, content):
    path = os.path.join(OUT, name)
    with open(path, 'w') as f:
        f.write(content)
    print(f"wrote {path}")


# ============================================================================
# 09-rendered-text.json — wallet-renderer canonicalization (ADR-0044)
# ============================================================================

def rendered_text_vectors():
    vectors = []

    # Vector 1: Payment intent, en-US, USD
    v1 = {
        "name": "payment-en-US-USD",
        "intent": {
            "kind": "payment",
            "amount_satoshis": 100_000_000,
            "recipient_outputs": [
                {"script": "76a914abcdef...88ac", "value_sats": 100_000_000}
            ],
            "fee_sats": 333,
            "counterparty_identity": {
                "pubkey": "02abcd123456789012345678901234567890123456789012345678901234567890",
                "cert_name": None,  # anonymous
            },
            "fiat_estimate": "$50.00",
            "fiat_currency": "USD",
            "human_locale": "en-US",
        },
        "expected_rendered_text": (
            "Send 100000000 sats (~$50.00 USD) to 1A1zP1...EQK... "
            "with fee 333 sats. Counterparty: anonymous + 0x02abcd12..."
        ),
    }
    # Compute request_view_hash for this vector
    rvh_preimage = {
        1: v1["intent"]["amount_satoshis"],
        2: v1["intent"]["recipient_outputs"][0]["script"],
        3: "deadbeef" + "00" * 28,  # mock sighash
        4: "f25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b",  # ExecutionId
        5: "00" * 32,  # policy_id
        6: "00" * 64,  # manifest_ack (BRC-77 sig over policy_id, 64 hex bytes)
        7: "en-US",
        8: v1["expected_rendered_text"],
    }
    rvh_cbor = cbor2.dumps(rvh_preimage, canonical=True)
    v1["request_view_hash_preimage_cbor_hex"] = rvh_cbor.hex()
    v1["request_view_hash"] = hashlib.sha256(rvh_cbor).hexdigest()
    vectors.append(v1)

    # Vector 2: Token transfer, en-US
    v2 = {
        "name": "token-transfer-en-US",
        "intent": {
            "kind": "token_transfer",
            "token_amount": 100,
            "token_symbol": "USDT-on-BSV",
            "recipient": "1B2y3z4a5b6c...K",
            "fiat_estimate": "$100.00",
            "fiat_currency": "USD",
            "token_contract_hash": "0x123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef0",
            "human_locale": "en-US",
        },
        "expected_rendered_text": (
            "Transfer 100 USDT-on-BSV tokens to 1B2y3z4a5b6c...K "
            "(value ~$100.00 USD). Token contract: 0x12345678..."
        ),
    }
    rvh_preimage = {
        1: 100,  # token_amount
        2: v2["intent"]["recipient"],
        3: "cafebabe" + "00" * 28,  # mock sighash
        4: "f25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b",
        5: "00" * 32,  # policy_id
        6: "00" * 64,  # manifest_ack
        7: "en-US",
        8: v2["expected_rendered_text"],
    }
    rvh_cbor = cbor2.dumps(rvh_preimage, canonical=True)
    v2["request_view_hash_preimage_cbor_hex"] = rvh_cbor.hex()
    v2["request_view_hash"] = hashlib.sha256(rvh_cbor).hexdigest()
    vectors.append(v2)

    # Vector 3: sCrypt covenant spend
    v3 = {
        "name": "script-spend-en-US",
        "intent": {
            "kind": "script_spend",
            "covenant_address": "1C3z4a5b6c7d...K",
            "amount_satoshis": 10000,
            "function_name": "settle",
            "function_args_hash": "sha256:" + "ab" * 32,
            "human_locale": "en-US",
        },
        "expected_rendered_text": (
            "Execute sCrypt covenant spend at contract 1C3z4a5b6c7d...K. "
            "Output value: 10000 sats. Covenant function: settle. "
            "Function args summary: sha256:abababababababababababababababababababababababababababababababab."
        ),
    }
    rvh_preimage = {
        1: 10000,
        2: v3["intent"]["covenant_address"],
        3: "5e7c5e56" + "00" * 28,
        4: "f25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b",
        5: "00" * 32,
        6: "00" * 64,
        7: "en-US",
        8: v3["expected_rendered_text"],
    }
    rvh_cbor = cbor2.dumps(rvh_preimage, canonical=True)
    v3["request_view_hash_preimage_cbor_hex"] = rvh_cbor.hex()
    v3["request_view_hash"] = hashlib.sha256(rvh_cbor).hexdigest()
    vectors.append(v3)

    # Vector 4: BRC-100 internalizeAction
    v4 = {
        "name": "brc100-internalize-en-US",
        "intent": {
            "kind": "brc100_internalize",
            "action_description": "payment-received",
            "source": "payee@example.com",
            "destination": "1D4y5z6a7b8c...K",
            "protocol_notes": "invoice 12345 paid",
            "human_locale": "en-US",
        },
        "expected_rendered_text": (
            "Internalize action: payment-received. "
            "From: payee@example.com. To: 1D4y5z6a7b8c...K. "
            "Notes: invoice 12345 paid."
        ),
    }
    rvh_preimage = {
        1: 0,  # no satoshi value for internalize-only
        2: v4["intent"]["destination"],
        3: "11223344" + "00" * 28,
        4: "f25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b",
        5: "00" * 32,
        6: "00" * 64,
        7: "en-US",
        8: v4["expected_rendered_text"],
    }
    rvh_cbor = cbor2.dumps(rvh_preimage, canonical=True)
    v4["request_view_hash_preimage_cbor_hex"] = rvh_cbor.hex()
    v4["request_view_hash"] = hashlib.sha256(rvh_cbor).hexdigest()
    vectors.append(v4)

    # Vector 5: Multi-output transaction
    v5 = {
        "name": "multi-output-en-US",
        "intent": {
            "kind": "multi",
            "outputs": [
                {"kind": "payment", "amount_satoshis": 50_000_000, "recipient": "1A..."},
                {"kind": "payment", "amount_satoshis": 25_000_000, "recipient": "1B..."},
                {"kind": "fee", "amount_satoshis": 333},
            ],
            "human_locale": "en-US",
        },
        "expected_rendered_text": (
            "Compound transaction with 3 outputs: "
            "Send 50000000 sats to 1A...; "
            "Send 25000000 sats to 1B...; "
            "Fee output 333 sats."
        ),
    }
    rvh_preimage = {
        1: 75_000_000,  # total non-fee output sum
        2: ["1A...", "1B..."],
        3: "deadc0de" + "00" * 28,
        4: "f25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b",
        5: "00" * 32,
        6: "00" * 64,
        7: "en-US",
        8: v5["expected_rendered_text"],
    }
    rvh_cbor = cbor2.dumps(rvh_preimage, canonical=True)
    v5["request_view_hash_preimage_cbor_hex"] = rvh_cbor.hex()
    v5["request_view_hash"] = hashlib.sha256(rvh_cbor).hexdigest()
    vectors.append(v5)

    data = {
        "spec_section": "09.5.1 + ADR-0044",
        "spec_title": "Wallet-renderer canonicalization vectors (request_view_hash byte-lock)",
        "description": "Byte-locks the canonical `rendered_text` per ADR-0044 intent-kind dispatch and the SHA-256(canonical_CBOR(...)) request_view_hash per ADR-0032.",
        "notes": [
            "All strings are NFC-normalized UTF-8.",
            "request_view_hash preimage uses numeric CBOR keys 1-8 for compactness:",
            "  1: amount_satoshis (or token_amount)",
            "  2: recipient_outputs (or recipient address(es))",
            "  3: sighash (hex 32 bytes)",
            "  4: ExecutionId (hex 32 bytes)",
            "  5: policy_id (hex 32 bytes)",
            "  6: manifest_ack (BRC-77 sig over policy_id; hex 64 bytes)",
            "  7: human_locale (BCP-47 tag)",
            "  8: rendered_text (canonical per ADR-0044 intent-kind dispatch)",
            "Test vectors fix sighash, ExecutionId, policy_id, manifest_ack to deterministic test-only values for reproducibility.",
            "Both implementations MUST produce identical CBOR bytes for the preimage AND identical request_view_hash output.",
        ],
        "vectors": vectors,
    }
    write_json("09-rendered-text.json", data)


# ============================================================================
# 18-recovery-kdf.json — Argon2id KDF byte-lock (ADR-0038)
# ============================================================================

def recovery_kdf_vectors():
    """Compute known-passphrase → known-KEK via Argon2id with pinned salt + params."""

    # We compute the byte-lock value using the argon2 library directly,
    # bypassing the high-level PasswordHasher (which adds its own encoding).
    from argon2.low_level import hash_secret_raw, Type

    vectors = []

    # Vector 1: profile-server (m=256MiB, t=3, p=1)
    salt_1 = bytes.fromhex("0102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f20")
    passphrase_1 = b"correct horse battery staple"
    kek_1 = hash_secret_raw(
        secret=passphrase_1,
        salt=salt_1,
        time_cost=3,
        memory_cost=262144,  # 256 MiB in KiB
        parallelism=1,
        hash_len=32,
        type=Type.ID,  # Argon2id
    )
    vectors.append({
        "name": "argon2id-profile-server-256MiB",
        "inputs": {
            "passphrase_utf8_bytes_hex": passphrase_1.hex(),
            "passphrase_human": passphrase_1.decode(),
            "salt_hex": salt_1.hex(),
            "memory_cost_kib": 262144,
            "memory_cost_human": "256 MiB",
            "time_cost": 3,
            "parallelism": 1,
            "hash_len": 32,
            "algorithm": "Argon2id",
            "profile": "profile-server",
        },
        "expected_kek_hex": kek_1.hex(),
    })

    # Vector 2: profile-mobile (m=64MiB, t=4, p=1)
    salt_2 = bytes.fromhex("2122232425262728292a2b2c2d2e2f303132333435363738393a3b3c3d3e3f40")
    passphrase_2 = b"alice loves bob"
    kek_2 = hash_secret_raw(
        secret=passphrase_2,
        salt=salt_2,
        time_cost=4,
        memory_cost=65536,  # 64 MiB
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )
    vectors.append({
        "name": "argon2id-profile-mobile-64MiB",
        "inputs": {
            "passphrase_utf8_bytes_hex": passphrase_2.hex(),
            "passphrase_human": passphrase_2.decode(),
            "salt_hex": salt_2.hex(),
            "memory_cost_kib": 65536,
            "memory_cost_human": "64 MiB",
            "time_cost": 4,
            "parallelism": 1,
            "hash_len": 32,
            "algorithm": "Argon2id",
            "profile": "profile-mobile",
        },
        "expected_kek_hex": kek_2.hex(),
    })

    # Vector 3: Unicode passphrase (stress-test NFC normalization)
    salt_3 = bytes.fromhex("4142434445464748494a4b4c4d4e4f505152535455565758595a5b5c5d5e5f60")
    passphrase_3 = "Café Société Δοκιμή".encode("utf-8")  # NFC-pre-normalized
    kek_3 = hash_secret_raw(
        secret=passphrase_3,
        salt=salt_3,
        time_cost=3,
        memory_cost=262144,
        parallelism=1,
        hash_len=32,
        type=Type.ID,
    )
    vectors.append({
        "name": "argon2id-unicode-stress",
        "inputs": {
            "passphrase_utf8_bytes_hex": passphrase_3.hex(),
            "passphrase_human": passphrase_3.decode("utf-8"),
            "salt_hex": salt_3.hex(),
            "memory_cost_kib": 262144,
            "memory_cost_human": "256 MiB",
            "time_cost": 3,
            "parallelism": 1,
            "hash_len": 32,
            "algorithm": "Argon2id",
            "profile": "profile-server",
            "_unicode_note": "Passphrase MUST be NFC-normalized before encoding to UTF-8. Implementations MUST NOT re-normalize to NFD/NFKC.",
        },
        "expected_kek_hex": kek_3.hex(),
    })

    data = {
        "spec_section": "18.5 + ADR-0038",
        "spec_title": "Recovery KDF Argon2id byte-lock vectors",
        "description": "Byte-locks the Argon2id parameters and passphrase → KEK derivation per ADR-0038. Both implementations MUST produce identical 32-byte KEKs for the pinned inputs.",
        "notes": [
            "Argon2id (RFC 9106) is REQUIRED; PBKDF2 / plain HMAC are non-conformant.",
            "profile-server: m=256MiB, t=3, p=1; profile-mobile: m=64MiB, t=4, p=1 (per ADR-0038).",
            "Salt MUST be per-blob random in production; vectors here use deterministic test-only salts.",
            "Passphrase MUST be NFC-normalized UTF-8 bytes; the implementation MUST NOT re-normalize to NFD/NFKC.",
            "Output is the raw Argon2id hash (32 bytes) used directly as the AES-256-GCM key for backup-blob decrypt.",
        ],
        "vectors": vectors,
    }
    write_json("18-recovery-kdf.json", data)


# ============================================================================
# 05-message-envelope-diff.cbor.hex — parser-diff pair (ADR-0037)
# ============================================================================

def message_envelope_diff_vectors():
    """Author the parser-differential conformance pair.

    Vector A: a canonical-CBOR envelope that re-encodes byte-identically.
    Vector B: a minimally-non-canonical variant that MUST be rejected
              (the 8 §05.9.1 rejection categories, one per sub-vector).
    """

    # Use a synthetic envelope (fields 1-8) — sender_sig_brc31 (field 9) is
    # not included in the parse-equivalence check.
    canonical_envelope = {
        1: 1,                                      # version
        2: bytes.fromhex("f25e7c5e560e01926dfbfd70f3940352c1349e1e69a2f17c1668bda988014e0b"),  # session_id
        3: bytes.fromhex("0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"),  # joint_pubkey
        4: "sign",                                 # phase
        5: 1,                                      # round
        6: 0,                                      # from_party
        7: 1,                                      # to_party
        8: bytes.fromhex("0102030405060708"),      # inner (mock 8-byte BRC-78 envelope; not real)
    }

    canonical_bytes = cbor2.dumps(canonical_envelope, canonical=True)
    canonical_hex = canonical_bytes.hex()
    canonical_re = cbor2.dumps(cbor2.loads(canonical_bytes), canonical=True).hex()
    assert canonical_hex == canonical_re, "Round-trip failed for canonical vector!"

    accepted = {
        "name": "accepted-canonical-envelope",
        "description": "A canonical-CBOR envelope; recipient MUST accept after byte-equivalent re-encode check.",
        "cbor_hex": canonical_hex,
        "expected_recipient_action": "ACCEPT",
        "re_encode_check": "PASS (cbor_hex round-trips to itself under canonical encoding)",
    }

    # Non-canonical rejections — each one minimally violates one §05.9.1 rule.
    rejections = []

    # R1: Non-minimal integer encoding of version field (0x18 0x01 instead of 0x01)
    # CBOR map header + key 1 (0x01) + non-min value (0x18 0x01 — uses 1 byte length for unsigned int < 24)
    # Construct manually: a3 (map of 3 — partial); for simplicity show a small example
    # Easier: take canonical and replace 0x01 (version=1) with 0x18 0x01
    # Canonical: a8  01 01  02 58 20 ...
    # Index 2-3 (key 1 → value 1) becomes "01 18 01"
    nm_bytes = bytearray(canonical_bytes)
    # find pattern "01 01" early in the encoding (key=1, value=1 unsigned-int)
    # In a CBOR map, keys come before values. Canonical small-int 1 = 0x01.
    # Map header 0xa8 (map(8)), then key 0x01 (unsigned 1), then value 0x01 (unsigned 1).
    # So bytes 1,2,3 = a8, 01, 01.
    # Replace value at index 2 with 0x18 0x01 (non-minimal encoding of 1).
    if nm_bytes[0] == 0xa8 and nm_bytes[1] == 0x01 and nm_bytes[2] == 0x01:
        # Insert non-minimal encoding of 1
        nm_bytes = nm_bytes[:2] + bytearray([0x18, 0x01]) + nm_bytes[3:]
        # NOTE: cbor2 will still parse this back to {1: 1} but re-encode as canonical (01) → byte-mismatch
        rejections.append({
            "name": "non-minimal-integer-version",
            "description": "Version field encoded with explicit length byte (0x18 0x01) instead of minimal (0x01). Parses to same value; canonical re-encode produces different bytes.",
            "cbor_hex": bytes(nm_bytes).hex(),
            "expected_recipient_action": "REJECT",
            "re_encode_check": "FAIL — re-encoded canonical bytes differ at offset 2",
            "violated_rule": "§05.9.1 #1 Non-minimal integer encoding",
        })

    # R2: Indefinite-length byte string for field 8 (inner)
    # Canonical CBOR forbids indefinite-length items (§05.2).
    # Build manually: replace field 8's "48 0102030405060708" with indefinite-length variant:
    #   5f (start indef bstr) 44 01020304 (chunk 1, 4 bytes) 44 05060708 (chunk 2, 4 bytes) ff (break)
    # Original encoding of field 8 value: 48 0102030405060708 (def-length bstr of 8 bytes)
    # Need to find "48 0102030405060708" in canonical_bytes and replace.
    target = bytes.fromhex("480102030405060708")
    indef_replacement = bytes.fromhex("5f44010203044405060708ff")
    if target in canonical_bytes:
        indef_variant = canonical_bytes.replace(target, indef_replacement)
        rejections.append({
            "name": "indefinite-length-bstr-inner",
            "description": "Field 8 (inner) encoded as indefinite-length byte string (0x5f...0xff). Forbidden by §05.2.",
            "cbor_hex": indef_variant.hex(),
            "construction_note": "Replaced canonical def-length bstr 48|01020304050607080 with indef-length pair 5f|44|01020304|44|05060708|ff.",
            "expected_recipient_action": "REJECT",
            "re_encode_check": "REJECT before re-encode (CBOR strict-mode decoder MUST refuse indef-length per spec §05.2)",
            "violated_rule": "§05.9.1 #2 Indefinite-length items",
        })

    # R3: Duplicate map key — two entries with key 1.
    # Original: a8 (map of 8) ... canonical_envelope is a8|01|01|02|58|20|...|...
    # Construct: a9 (map of 9) 01 01 01 02 [rest of original starting from 02 58 20 ...]
    # i.e., bump map-len to 9 AND insert an extra "01 02" key-value pair after the first "01 01"
    if canonical_bytes[0] == 0xa8 and canonical_bytes[1] == 0x01 and canonical_bytes[2] == 0x01:
        dup_variant = (
            bytes([0xa9])              # map(9) instead of map(8)
            + canonical_bytes[1:3]     # original key=1, value=1
            + bytes([0x01, 0x02])      # second key=1, value=2 (DUPLICATE KEY)
            + canonical_bytes[3:]      # rest of original
        )
        rejections.append({
            "name": "duplicate-map-key",
            "description": "Two entries with key 1 (version). Forbidden by canonical CBOR. Map header bumped to 9; second `01 02` inserted after first key-value pair.",
            "cbor_hex": dup_variant.hex(),
            "construction_note": "Map-len byte changed a8→a9; inserted extra (01, 02) pair at offset 3.",
            "expected_recipient_action": "REJECT",
            "re_encode_check": "REJECT during canonical re-encode (canonical CBOR enforces unique keys)",
            "violated_rule": "§05.9.1 #3 Duplicate map keys",
        })

    # R4: Trailing bytes
    rejections.append({
        "name": "trailing-bytes",
        "description": "Canonical envelope followed by trailing 0xFF byte. Forbidden by §05.9.1 #4.",
        "cbor_hex": canonical_hex + "ff",
        "expected_recipient_action": "REJECT",
        "re_encode_check": "REJECT — input length exceeds parsed length",
        "violated_rule": "§05.9.1 #4 Trailing bytes after canonical termination",
    })

    # R5: Float for round field (5).
    # Original: ...05 01... (key 5, value 1 as small unsigned int).
    # Replace value 0x01 with half-precision float 0xf9 3c00 (= 1.0 in float16) — or 32-bit float 0xfa 3f800000.
    # We use float16: f9 3c 00.
    target = bytes([0x05, 0x01])  # key=5, value=1
    float_repl = bytes([0x05, 0xf9, 0x3c, 0x00])  # key=5, value=float16(1.0)
    if target in canonical_bytes:
        float_variant = canonical_bytes.replace(target, float_repl, 1)
        rejections.append({
            "name": "float-in-round-field",
            "description": "Field 5 (round) encoded as float16(1.0) instead of unsigned int 1. Forbidden by §05.2.",
            "cbor_hex": float_variant.hex(),
            "construction_note": "Replaced canonical (05, 01) with (05, f9, 3c, 00) — float16 encoding of 1.0.",
            "expected_recipient_action": "REJECT",
            "re_encode_check": "REJECT — float forbidden per §05.2",
            "violated_rule": "§05.9.1 #5 Floats",
        })

    # R6: Unsorted map keys.
    # Canonical CBOR (RFC 8949 §4.2) requires map keys in ascending lexicographic order of their canonical encoding.
    # For uint keys 1..8, this is just numeric order: 01 02 03 04 05 06 07 08.
    # Construct a variant with keys in order 02 01 03 04 05 06 07 08.
    # We rebuild the map by extracting each key-value pair via cbor2 and re-emitting with a swap.
    # cbor2 doesn't expose ordering control directly; we hand-build.
    # Map header: a8.
    # Then 8 key-value pairs. For our envelope (keys 1-8, all small uints), the encoding is:
    #   01 01            key=1 (uint 1), value=1 (uint 1)
    #   02 58 20 <32B>   key=2, value=bstr32
    #   03 58 21 <33B>   key=3, value=bstr33
    #   04 64 73 69 67 6e  key=4, value=tstr "sign"
    #   05 01            key=5, value=1
    #   06 00            key=6, value=0
    #   07 01            key=7, value=1
    #   08 48 <8B>       key=8, value=bstr8

    def cbor_skip_pair(buf, i):
        """Skip one key-value pair starting at index i; return new index."""
        # key
        kt = buf[i]
        i += 1
        if kt < 0x18:
            pass  # uint <24
        elif kt == 0x18:
            i += 1
        elif kt == 0x19:
            i += 2
        elif kt == 0x1a:
            i += 4
        elif kt == 0x1b:
            i += 8
        # value
        vt = buf[i]
        i += 1
        major = vt >> 5
        info = vt & 0x1f
        if major == 0 or major == 1:  # uint / nint
            if info == 24: i += 1
            elif info == 25: i += 2
            elif info == 26: i += 4
            elif info == 27: i += 8
        elif major == 2 or major == 3:  # bstr / tstr
            if info < 24:
                ln = info
            elif info == 24:
                ln = buf[i]; i += 1
            elif info == 25:
                ln = int.from_bytes(buf[i:i+2], 'big'); i += 2
            elif info == 26:
                ln = int.from_bytes(buf[i:i+4], 'big'); i += 4
            else:
                raise ValueError("unsupported bstr len")
            i += ln
        else:
            raise ValueError(f"unsupported major type {major}")
        return i

    # Parse all 8 pairs:
    body = canonical_bytes[1:]  # skip a8
    pairs = []
    i = 0
    for _ in range(8):
        start = i
        i = cbor_skip_pair(body, i)
        pairs.append(body[start:i])

    # Swap pairs[0] (key=1) and pairs[1] (key=2)
    unsorted = bytes([0xa8]) + pairs[1] + pairs[0] + b''.join(pairs[2:])
    rejections.append({
        "name": "unsorted-map-keys",
        "description": "Map keys in order 2,1,3..8 instead of canonical 1,2,3..8. Canonical CBOR §4.2 mandates ascending key order.",
        "cbor_hex": unsorted.hex(),
        "construction_note": "Swapped first two key-value pairs (key=1 and key=2) in the canonical envelope.",
        "expected_recipient_action": "REJECT",
        "re_encode_check": "FAIL — re-encoded canonical-order bytes differ at offset 1",
        "violated_rule": "§05.9.1 #6 Unsorted map keys",
    })

    # R7: Unknown tag on session_id (field 2).
    # Original: 02 58 20 <32B>  (key=2, value=bstr32)
    # Insert tag 0xc0 (datetime) before the bstr: 02 c0 58 20 <32B>
    # Tag 0xc0 is for tstr-as-datetime; applying it to a bstr is semantically nonsense AND not in §05.10 whitelist.
    target = bytes([0x02, 0x58, 0x20])
    tagged_repl = bytes([0x02, 0xc0, 0x58, 0x20])
    if target in canonical_bytes:
        tag_variant = canonical_bytes.replace(target, tagged_repl, 1)
        rejections.append({
            "name": "unknown-tag-on-session-id",
            "description": "Field 2 (session_id bstr32) wrapped in CBOR tag 0xc0 (datetime). Tag not whitelisted in §05.10.",
            "cbor_hex": tag_variant.hex(),
            "construction_note": "Inserted tag byte 0xc0 between key 0x02 and value-header 0x58.",
            "expected_recipient_action": "REJECT",
            "re_encode_check": "REJECT — tag not whitelisted in §05.10 reserved fields",
            "violated_rule": "§05.9.1 #7 Tags not whitelisted",
        })

    # R8: bstr map key (forbidden — keys MUST be uint or tstr per §05.3).
    # Construct: replace first pair "01 01" (key=uint 1) with "41 ff 01" (key=bstr 1-byte 0xff, value=uint 1)
    # Note: this produces an 8-pair map structurally but with invalid key type.
    target = bytes([0xa8, 0x01, 0x01])
    bstr_key_repl = bytes([0xa8, 0x41, 0xff, 0x01])
    if canonical_bytes[:3] == target:
        bstr_key_variant = bstr_key_repl + canonical_bytes[3:]
        rejections.append({
            "name": "bstr-map-key",
            "description": "Map uses bstr key (0x41 0xff) instead of unsigned integer. §05.3 requires keys be uint.",
            "cbor_hex": bstr_key_variant.hex(),
            "construction_note": "Replaced first key 0x01 (uint 1) with 0x41 0xff (bstr 1-byte value 0xff).",
            "expected_recipient_action": "REJECT",
            "re_encode_check": "REJECT — key type not allowed per §05.3 schema",
            "violated_rule": "§05.9.1 #8 Map keys not uint or tstr",
        })

    data = {
        "spec_section": "05.9.1 + ADR-0037",
        "spec_title": "Canonical CBOR re-encode equivalence (parser-differential conformance)",
        "description": "Byte-locks the parser-differential conformance test per ADR-0037 §05.9.1.",
        "notes": [
            "The `cbor_hex` field is the raw envelope bytes (fields 1-8 only; sender_sig_brc31 omitted for byte-equivalence focus).",
            "ACCEPTED vector round-trips byte-identically through canonical encoder.",
            "REJECTED vectors fail re-encode equivalence OR fail strict-parser admission BEFORE re-encode.",
            "Hand-authored REJECTED vectors marked TBD will be byte-locked in the second loop-3 sub-pass.",
            "Recipient action on each vector MUST match `expected_recipient_action`.",
            "Implementations MUST emit `EnvelopeReencodeMismatch` audit event on REJECTED outcomes per ADR-0037.",
        ],
        "vectors_accepted": [accepted],
        "vectors_rejected": rejections,
    }
    write_json("05-message-envelope-diff.json", data)
    # Also write the hex companion
    write_text("05-message-envelope-diff.cbor.hex", canonical_hex + "\n")


# ============================================================================
# 06-presig-bundle-encryption.json — refresh existing skeleton with derivable
# intermediate values (BRC-42 invoice + bytes + shared_secret for known inputs)
# ============================================================================

def presig_bundle_partial_lock():
    """For each vector, compute everything derivable without a full BRC-2 wallet impl.

    What we CAN compute:
    - BRC-42 invoice string (per §03.2 canonicalization)
    - UTF-8 bytes of the invoice
    - wallet_identity_pub (priv * G compressed)
    - shared_secret for Self_ case (priv * pub = priv^2 * G compressed)
    - HMAC-SHA256(shared_secret, invoice) → BRC-42 offset

    What we CANNOT compute without rust-mpc's ProtoWallet:
    - The actual AES-256-GCM key (BRC-2 has a specific derivation we don't have)
    - The ciphertext
    """
    from ecdsa import SigningKey, SECP256k1

    def compress_pub(pub_x, pub_y):
        prefix = b'\x02' if pub_y % 2 == 0 else b'\x03'
        return (prefix + pub_x.to_bytes(32, 'big')).hex()

    def derive_for(priv_bytes_hex, presig_id, protocol_name_raw="mpcpresig"):
        priv_bytes = bytes.fromhex(priv_bytes_hex)
        sk = SigningKey.from_string(priv_bytes, curve=SECP256k1)
        vk = sk.verifying_key
        pub_x = vk.pubkey.point.x()
        pub_y = vk.pubkey.point.y()
        pub_compressed_hex = compress_pub(pub_x, pub_y)

        # For Self_, shared_secret = priv * pub = priv * (priv * G) = priv^2 * G compressed
        n = SECP256k1.order
        priv_int = int.from_bytes(priv_bytes, 'big')
        priv_sq_int = (priv_int * priv_int) % n
        priv_sq_bytes = priv_sq_int.to_bytes(32, 'big')
        sk2 = SigningKey.from_string(priv_sq_bytes, curve=SECP256k1)
        vk2 = sk2.verifying_key
        shared_x = vk2.pubkey.point.x()
        shared_y = vk2.pubkey.point.y()
        shared_compressed_hex = compress_pub(shared_x, shared_y)
        shared_bytes = bytes.fromhex(shared_compressed_hex)

        # BRC-42 canonicalization: protocol_name.to_lowercase().trim()
        protocol_name_canon = protocol_name_raw.lower().strip()
        invoice = f"2-{protocol_name_canon}-{presig_id}"
        invoice_bytes = invoice.encode('utf-8')

        # HMAC-SHA256
        offset = hmac.new(shared_bytes, invoice_bytes, hashlib.sha256).digest()

        return {
            "wallet_pub_compressed_hex": pub_compressed_hex,
            "brc42_invoice_string": invoice,
            "brc42_invoice_bytes_hex": invoice_bytes.hex(),
            "shared_secret_compressed_hex": shared_compressed_hex,
            "hmac_offset_hex": offset.hex(),
        }

    # Vector 1 inputs
    v1 = derive_for("01" * 32, "presig-test-vector-001")
    # Vector 2 inputs (mixed-case protocol)
    v2 = derive_for("02" * 32, "presig-test-vector-002", protocol_name_raw="  MPCPresig  ")
    # Vector 3 inputs (round-trip)
    v3 = derive_for("03" * 32, "presig-test-vector-003")

    data = {
        "spec_section": "06.16",
        "spec_title": "Presignature share — BRC-2 self-encryption byte-lock",
        "adr": "0030",
        "status": "intermediate-values-locked; ciphertext requires reference rust-mpc impl run",
        "description": "Byte-locks the deterministic intermediate values (wallet pub, BRC-42 invoice, shared_secret, HMAC offset) for the BRC-2 self-encryption derivation. Full AES-GCM ciphertext byte-lock requires a reference rust-mpc impl run because BRC-2's specific AES-key derivation from the HMAC offset is implementation-defined.",
        "vectors": [
            {
                "name": "presig-bundle-vector-1-basic",
                "inputs": {
                    "wallet_identity_priv_hex": "0101010101010101010101010101010101010101010101010101010101010101",
                    "presig_id": "presig-test-vector-001",
                    "presig_share_plaintext_hex": "70726573696720737061726520706c61696e7465787420333220627974657378",
                    "aes_gcm_iv_hex": "0a0b0c0d0e0f101112131415",
                    "protocol_security_level": 2,
                    "protocol_name": "mpcpresig",
                    "counterparty": "Self_",
                },
                "intermediate_byte_locked": v1,
                "expected": {"ciphertext_with_tag_hex": "__TBD-by-ref-impl__"},
                "computed_by_loop3": {
                    "wallet_pub_compressed_hex": v1["wallet_pub_compressed_hex"],
                    "brc42_invoice_string": v1["brc42_invoice_string"],
                    "brc42_invoice_bytes_hex": v1["brc42_invoice_bytes_hex"],
                    "shared_secret_compressed_hex": v1["shared_secret_compressed_hex"],
                    "hmac_offset_hex": v1["hmac_offset_hex"],
                },
            },
            {
                "name": "presig-bundle-vector-2-mixed-case-protocol-id",
                "inputs": {
                    "wallet_identity_priv_hex": "0202020202020202020202020202020202020202020202020202020202020202",
                    "presig_id": "presig-test-vector-002",
                    "presig_share_plaintext_hex": "70726573696720737061726520706c61696e7465787420333220627974657378",
                    "aes_gcm_iv_hex": "1b2c3d4e5f6071829384a5b6",
                    "protocol_security_level": 2,
                    "protocol_name": "  MPCPresig  ",
                    "_canonicalized_to": "mpcpresig (after .to_lowercase().trim() per §03.2)",
                    "counterparty": "Self_",
                },
                "intermediate_byte_locked": v2,
                "expected": {"ciphertext_with_tag_hex": "__TBD-by-ref-impl__"},
            },
            {
                "name": "presig-bundle-vector-3-roundtrip-decrypt",
                "inputs": {
                    "wallet_identity_priv_hex": "0303030303030303030303030303030303030303030303030303030303030303",
                    "presig_id": "presig-test-vector-003",
                    "presig_share_plaintext_hex": "deadbeefcafebabe0011223344556677889900aabbccddeeff0123456789abcd",
                    "aes_gcm_iv_hex": "2c3d4e5f6071829384a5b6c7",
                    "counterparty": "Self_",
                },
                "intermediate_byte_locked": v3,
                "expected": {
                    "ciphertext_with_tag_hex": "__TBD-by-ref-impl__",
                    "roundtrip_decrypt_plaintext_hex": "deadbeefcafebabe0011223344556677889900aabbccddeeff0123456789abcd",
                },
            },
        ],
        "negative_tests": [
            {"name": "wrong-presig_id-fails-decrypt", "description": "Encrypt with presig_id='presig-aaa'; decrypt with 'presig-bbb' MUST fail."},
            {"name": "wrong-wallet-fails-decrypt", "description": "Encrypt with wallet A; decrypt with wallet B MUST fail."},
            {"name": "tampered-ciphertext-fails-decrypt", "description": "Encrypt normally; flip last byte; decrypt MUST fail (AES-GCM tag)."},
            {"name": "different-presig_id-different-ciphertext", "description": "SAME plaintext, two different presig_ids → ciphertexts MUST differ."},
        ],
    }
    write_json("06-presig-bundle-encryption.json", data)


if __name__ == "__main__":
    rendered_text_vectors()
    recovery_kdf_vectors()
    message_envelope_diff_vectors()
    presig_bundle_partial_lock()
    print("\nLoop-3 vectors authored.")
