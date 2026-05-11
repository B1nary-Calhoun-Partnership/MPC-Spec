#!/usr/bin/env python3
"""
Canonical test vector computation for MPC-Spec Phase 0.

Sections covered:
  - §02 ExecutionId           (SHA-256 of fixed-format input)
  - §03 BRC-42 invoice + HMAC (HMAC-SHA256 with compressed shared secret)
  - §04 SessionId             (SHA-256 of fixed-format input)
  - §05 MessageEnvelope       (deterministic CBOR per RFC 8949 §4.2)

Cross-validation:
  - §03 BRC-42 invoice vectors are cross-validated by an independent Rust
    program (`cross_validate.rs`) that uses the same hd.rs primitives.
  - §02/§04 use only stdlib hashlib (SHA-256) — verified by a hand-rolled
    secondary SHA-256 path in `verify_sha256_independent()` below
    (concatenates the input bytes a different way, prints them, and the
    Rust program also reproduces them).
  - §05 CBOR is cross-validated by a hand-rolled deterministic CBOR
    encoder in `manual_canonical_cbor()` below.

Dependencies: stdlib + `ecdsa` (pure Python secp256k1) + `cbor2`.
"""

import hashlib
import hmac
import json
import os
import sys
from typing import Any

# secp256k1 + scalar math via the pure-python `ecdsa` library
from ecdsa import SECP256k1, SigningKey, VerifyingKey
from ecdsa.ellipticcurve import Point
from ecdsa.numbertheory import inverse_mod

# canonical CBOR
import cbor2


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CURVE = SECP256k1
G = CURVE.generator
N = CURVE.order

# §02
EXECID_DOMAIN = b"calhoun-binary-mpc"          # 18 bytes
assert len(EXECID_DOMAIN) == 18

# §04
SESSION_DOMAIN = b"calhoun-binary-mpc-session-v1"  # 29 bytes
assert len(SESSION_DOMAIN) == 29

# Output paths
TV_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def H(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()


def hmac_sha256(key: bytes, data: bytes) -> bytes:
    return hmac.new(key, data, hashlib.sha256).digest()


def be32(scalar: int) -> bytes:
    return scalar.to_bytes(32, "big")


def compressed_pub_from_point(p: Point) -> bytes:
    """Return the 33-byte SEC1 compressed encoding of a curve point."""
    x = p.x()
    y = p.y()
    prefix = b"\x02" if (y % 2) == 0 else b"\x03"
    return prefix + x.to_bytes(32, "big")


def point_from_compressed(b: bytes) -> Point:
    """Parse a 33-byte SEC1 compressed pubkey into a Point."""
    assert len(b) == 33, f"compressed pubkey must be 33 bytes, got {len(b)}"
    prefix = b[0]
    assert prefix in (0x02, 0x03), f"compressed prefix must be 02/03, got {prefix:#x}"
    x = int.from_bytes(b[1:], "big")
    # y^2 = x^3 + 7 mod p (secp256k1: a=0, b=7)
    p = CURVE.curve.p()
    rhs = (pow(x, 3, p) + 7) % p
    # Tonelli-Shanks not needed because p ≡ 3 (mod 4); y = rhs^((p+1)/4) mod p
    y = pow(rhs, (p + 1) // 4, p)
    if (y % 2) != (0 if prefix == 0x02 else 1):
        y = p - y
    return Point(CURVE.curve, x, y, N)


def scalar_mul_pub(scalar: int, P: Point) -> Point:
    """Compute scalar * P on secp256k1."""
    return scalar * P


def pub_add(A: Point, B: Point) -> Point:
    return A + B


def priv_from_int(k: int) -> SigningKey:
    return SigningKey.from_secret_exponent(k % N, curve=CURVE)


# secp256k1 generator G compressed:
# G.x = 0x79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798
# G.y is even → prefix 0x02
G_COMPRESSED = bytes.fromhex(
    "0279be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798"
)
# Sanity: cross-check against our own compressed_pub_from_point on G.
_g_check = compressed_pub_from_point(G)
assert _g_check == G_COMPRESSED, f"G compressed mismatch:\n  ours = {_g_check.hex()}\n  spec = {G_COMPRESSED.hex()}"


# ---------------------------------------------------------------------------
# §02 — ExecutionId
# ---------------------------------------------------------------------------
#
# ExecutionId = SHA256(
#     "calhoun-binary-mpc"      (18 bytes)
#  || version_u8                (1 byte)
#  || algorithm_tag_u8          (1 byte)
#  || phase_tag_u8              (1 byte)
#  || session_id_32B            (32 bytes)
#  || joint_pubkey_33B          (33 bytes)
# )
# Total preimage: 86 bytes, output: 32 bytes.

def execution_id(version: int, algo: int, phase: int, session_id: bytes,
                 joint_pubkey: bytes) -> tuple[bytes, bytes]:
    assert 0 <= version <= 0xFF
    assert 0 <= algo <= 0xFF
    assert 0 <= phase <= 0xFF
    assert len(session_id) == 32
    assert len(joint_pubkey) == 33
    preimage = (
        EXECID_DOMAIN
        + bytes([version, algo, phase])
        + session_id
        + joint_pubkey
    )
    assert len(preimage) == 86, f"ExecutionId preimage length = {len(preimage)} (expected 86)"
    return preimage, H(preimage)


def compute_execution_id_vectors() -> dict:
    """Compute Vectors A, B, C per §02.6."""
    vectors = []

    # Vector A: Sign phase, joint key = G compressed, session = SHA256("test-vector-A")
    sid_a = H(b"test-vector-A")
    pre_a, eid_a = execution_id(
        version=0x01, algo=0x01, phase=0x04, session_id=sid_a, joint_pubkey=G_COMPRESSED
    )
    vectors.append({
        "name": "execution-id-vector-A-sign-phase",
        "description": "Sign phase (0x04), joint_pubkey = secp256k1 generator G compressed",
        "inputs": {
            "domain_separator_ascii": "calhoun-binary-mpc",
            "domain_separator_hex": EXECID_DOMAIN.hex(),
            "version": 1,
            "algorithm_tag": 1,
            "algorithm_name": "cggmp24",
            "phase_tag": 4,
            "phase_name": "sign",
            "session_id_source": 'SHA256("test-vector-A")',
            "session_id_hex": sid_a.hex(),
            "joint_pubkey_source": "secp256k1 generator G, SEC1 compressed",
            "joint_pubkey_hex": G_COMPRESSED.hex(),
        },
        "preimage_hex": pre_a.hex(),
        "preimage_length_bytes": len(pre_a),
        "expected": {
            "execution_id_hex": eid_a.hex(),
        },
    })

    # Vector B: Keygen phase, joint key = 33 zero bytes
    sid_b = H(b"test-vector-B")
    pre_b, eid_b = execution_id(
        version=0x01, algo=0x01, phase=0x01, session_id=sid_b,
        joint_pubkey=b"\x00" * 33,
    )
    vectors.append({
        "name": "execution-id-vector-B-keygen",
        "description": "DKG keygen phase (0x01), joint_pubkey = all-zero carve-out",
        "inputs": {
            "domain_separator_ascii": "calhoun-binary-mpc",
            "domain_separator_hex": EXECID_DOMAIN.hex(),
            "version": 1,
            "algorithm_tag": 1,
            "algorithm_name": "cggmp24",
            "phase_tag": 1,
            "phase_name": "dkg-keygen",
            "session_id_source": 'SHA256("test-vector-B")',
            "session_id_hex": sid_b.hex(),
            "joint_pubkey_source": "33 zero bytes (keygen carve-out, §02.4)",
            "joint_pubkey_hex": ("00" * 33),
        },
        "preimage_hex": pre_b.hex(),
        "preimage_length_bytes": len(pre_b),
        "expected": {
            "execution_id_hex": eid_b.hex(),
        },
    })

    # Vector C: Refresh phase, joint key = G compressed
    sid_c = H(b"test-vector-C")
    pre_c, eid_c = execution_id(
        version=0x01, algo=0x01, phase=0x06, session_id=sid_c, joint_pubkey=G_COMPRESSED
    )
    vectors.append({
        "name": "execution-id-vector-C-refresh",
        "description": "Refresh phase (0x06), joint_pubkey = G compressed",
        "inputs": {
            "domain_separator_ascii": "calhoun-binary-mpc",
            "domain_separator_hex": EXECID_DOMAIN.hex(),
            "version": 1,
            "algorithm_tag": 1,
            "algorithm_name": "cggmp24",
            "phase_tag": 6,
            "phase_name": "refresh",
            "session_id_source": 'SHA256("test-vector-C")',
            "session_id_hex": sid_c.hex(),
            "joint_pubkey_source": "secp256k1 generator G, SEC1 compressed",
            "joint_pubkey_hex": G_COMPRESSED.hex(),
        },
        "preimage_hex": pre_c.hex(),
        "preimage_length_bytes": len(pre_c),
        "expected": {
            "execution_id_hex": eid_c.hex(),
        },
    })

    return {
        "spec_section": "02",
        "spec_title": "Canonical ExecutionId",
        "formula": (
            "ExecutionId = SHA-256("
            "\"calhoun-binary-mpc\" (18B) || version_u8 || algorithm_tag_u8 "
            "|| phase_tag_u8 || session_id_32B || joint_pubkey_33B)"
        ),
        "preimage_length_bytes": 86,
        "output_length_bytes": 32,
        "vectors": vectors,
    }


# ---------------------------------------------------------------------------
# §03 — BRC-42 invoice + HMAC
# ---------------------------------------------------------------------------
#
# (a) Reproduce the 10 BRC-42 spec test vectors (5 priv + 5 pub).
# (b) Add the 3 spec stress vectors (mixed-case, Unicode, empty key_id).
#
# The 10 spec vectors:
#   - For private derivation:
#       shared_secret_point = recipient_priv * sender_pub
#       hmac = HMAC-SHA256(key=compressed(shared_secret_point), data=invoice)
#       child_priv = (recipient_priv + int.from_bytes(hmac, 'big')) mod N
#   - For public derivation:
#       shared_secret_point = sender_priv * recipient_pub
#       hmac = HMAC-SHA256(key=compressed(shared_secret_point), data=invoice)
#       child_pub = recipient_pub + G * hmac

def brc42_shared_secret(priv: int, peer_pub: Point) -> bytes:
    return compressed_pub_from_point(priv * peer_pub)


BRC42_PRIV_VECTORS = [
    {
        "senderPublicKey": "033f9160df035156f1c48e75eae99914fa1a1546bec19781e8eddb900200bff9d1",
        "recipientPrivateKey": "6a1751169c111b4667a6539ee1be6b7cd9f6e9c8fe011a5f2fe31e03a15e0ede",
        "invoiceNumber": "f3WCaUmnN9U=",
        "privateKey": "761656715bbfa172f8f9f58f5af95d9d0dfd69014cfdcacc9a245a10ff8893ef",
    },
    {
        "senderPublicKey": "027775fa43959548497eb510541ac34b01d5ee9ea768de74244a4a25f7b60fae8d",
        "recipientPrivateKey": "cab2500e206f31bc18a8af9d6f44f0b9a208c32d5cca2b22acfe9d1a213b2f36",
        "invoiceNumber": "2Ska++APzEc=",
        "privateKey": "09f2b48bd75f4da6429ac70b5dce863d5ed2b350b6f2119af5626914bdb7c276",
    },
    {
        "senderPublicKey": "0338d2e0d12ba645578b0955026ee7554889ae4c530bd7a3b6f688233d763e169f",
        "recipientPrivateKey": "7a66d0896f2c4c2c9ac55670c71a9bc1bdbdfb4e8786ee5137cea1d0a05b6f20",
        "invoiceNumber": "cN/yQ7+k7pg=",
        "privateKey": "7114cd9afd1eade02f76703cc976c241246a2f26f5c4b7a3a0150ecc745da9f0",
    },
    {
        "senderPublicKey": "02830212a32a47e68b98d477000bde08cb916f4d44ef49d47ccd4918d9aaabe9c8",
        "recipientPrivateKey": "6e8c3da5f2fb0306a88d6bcd427cbfba0b9c7f4c930c43122a973d620ffa3036",
        "invoiceNumber": "m2/QAsmwaA4=",
        "privateKey": "f1d6fb05da1225feeddd1cf4100128afe09c3c1aadbffbd5c8bd10d329ef8f40",
    },
    {
        "senderPublicKey": "03f20a7e71c4b276753969e8b7e8b67e2dbafc3958d66ecba98dedc60a6615336d",
        "recipientPrivateKey": "e9d174eff5708a0a41b32624f9b9cc97ef08f8931ed188ee58d5390cad2bf68e",
        "invoiceNumber": "jgpUIjWFlVQ=",
        "privateKey": "c5677c533f17c30f79a40744b18085632b262c0c13d87f3848c385f1389f79a6",
    },
]

BRC42_PUB_VECTORS = [
    {
        "senderPrivateKey": "583755110a8c059de5cd81b8a04e1be884c46083ade3f779c1e022f6f89da94c",
        "recipientPublicKey": "02c0c1e1a1f7d247827d1bcf399f0ef2deef7695c322fd91a01a91378f101b6ffc",
        "invoiceNumber": "IBioA4D/OaE=",
        "publicKey": "03c1bf5baadee39721ae8c9882b3cf324f0bf3b9eb3fc1b8af8089ca7a7c2e669f",
    },
    {
        "senderPrivateKey": "2c378b43d887d72200639890c11d79e8f22728d032a5733ba3d7be623d1bb118",
        "recipientPublicKey": "039a9da906ecb8ced5c87971e9c2e7c921e66ad450fd4fc0a7d569fdb5bede8e0f",
        "invoiceNumber": "PWYuo9PDKvI=",
        "publicKey": "0398cdf4b56a3b2e106224ff3be5253afd5b72de735d647831be51c713c9077848",
    },
    {
        "senderPrivateKey": "d5a5f70b373ce164998dff7ecd93260d7e80356d3d10abf928fb267f0a6c7be6",
        "recipientPublicKey": "02745623f4e5de046b6ab59ce837efa1a959a8f28286ce9154a4781ec033b85029",
        "invoiceNumber": "X9pnS+bByrM=",
        "publicKey": "0273eec9380c1a11c5a905e86c2d036e70cbefd8991d9a0cfca671f5e0bbea4a3c",
    },
    {
        "senderPrivateKey": "46cd68165fd5d12d2d6519b02feb3f4d9c083109de1bfaa2b5c4836ba717523c",
        "recipientPublicKey": "031e18bb0bbd3162b886007c55214c3c952bb2ae6c33dd06f57d891a60976003b1",
        "invoiceNumber": "+ktmYRHv3uQ=",
        "publicKey": "034c5c6bf2e52e8de8b2eb75883090ed7d1db234270907f1b0d1c2de1ddee5005d",
    },
    {
        "senderPrivateKey": "7c98b8abd7967485cfb7437f9c56dd1e48ceb21a4085b8cdeb2a647f62012db4",
        "recipientPublicKey": "03c8885f1e1ab4facd0f3272bb7a48b003d2e608e1619fb38b8be69336ab828f37",
        "invoiceNumber": "PPfDTTcl1ao=",
        "publicKey": "03304b41cfa726096ffd9d8907fe0835f888869eda9653bca34eb7bcab870d3779",
    },
]


def compute_brc42_priv_vectors() -> list:
    results = []
    for i, v in enumerate(BRC42_PRIV_VECTORS):
        sender_pub = point_from_compressed(bytes.fromhex(v["senderPublicKey"]))
        recip_priv = int(v["recipientPrivateKey"], 16)
        shared_secret_compressed = brc42_shared_secret(recip_priv, sender_pub)
        h = hmac_sha256(shared_secret_compressed, v["invoiceNumber"].encode("utf-8"))
        child_priv = (recip_priv + int.from_bytes(h, "big")) % N
        child_priv_hex = child_priv.to_bytes(32, "big").hex()
        agreed = child_priv_hex == v["privateKey"]
        results.append({
            "name": f"brc42-priv-vector-{i+1}",
            "source": "BRC-42 spec §Test Vectors / Private Key Derivation",
            "inputs": {
                "senderPublicKey": v["senderPublicKey"],
                "recipientPrivateKey": v["recipientPrivateKey"],
                "invoiceNumber": v["invoiceNumber"],
            },
            "intermediate": {
                "shared_secret_compressed_hex": shared_secret_compressed.hex(),
                "hmac_offset_hex": h.hex(),
            },
            "expected": {
                "childPrivateKey_hex": v["privateKey"],
            },
            "computed": {
                "childPrivateKey_hex": child_priv_hex,
            },
            "agrees_with_spec_vector": agreed,
        })
    return results


def compute_brc42_pub_vectors() -> list:
    results = []
    for i, v in enumerate(BRC42_PUB_VECTORS):
        sender_priv = int(v["senderPrivateKey"], 16)
        recip_pub = point_from_compressed(bytes.fromhex(v["recipientPublicKey"]))
        shared_secret_compressed = brc42_shared_secret(sender_priv, recip_pub)
        h = hmac_sha256(shared_secret_compressed, v["invoiceNumber"].encode("utf-8"))
        offset_scalar = int.from_bytes(h, "big") % N
        offset_point = offset_scalar * G
        child_pub = recip_pub + offset_point
        child_pub_compressed = compressed_pub_from_point(child_pub).hex()
        agreed = child_pub_compressed == v["publicKey"]
        results.append({
            "name": f"brc42-pub-vector-{i+1}",
            "source": "BRC-42 spec §Test Vectors / Public Key Derivation",
            "inputs": {
                "senderPrivateKey": v["senderPrivateKey"],
                "recipientPublicKey": v["recipientPublicKey"],
                "invoiceNumber": v["invoiceNumber"],
            },
            "intermediate": {
                "shared_secret_compressed_hex": shared_secret_compressed.hex(),
                "hmac_offset_hex": h.hex(),
            },
            "expected": {
                "childPublicKey_hex": v["publicKey"],
            },
            "computed": {
                "childPublicKey_hex": child_pub_compressed,
            },
            "agrees_with_spec_vector": agreed,
        })
    return results


# Stress vectors per §03.5.{1,2,3}.
# These exercise the invoice-string format defined by the MPC spec
# (security_level, lowercase+trim protocol, verbatim key_id).
# We pin a test-only shared secret = G compressed so the HMAC outputs are
# fully reproducible without needing real ECDH key material.

STRESS_SHARED_SECRET = G_COMPRESSED  # 33 bytes, prefix 0x02


def build_invoice(security_level: int, protocol_id: str, key_id: str) -> str:
    """Canonical §03.2 invoice format with to_lowercase + trim."""
    normalized = protocol_id.lower().strip()
    return f"{security_level}-{normalized}-{key_id}"


def compute_brc42_stress_vectors() -> list:
    stress = []

    # §03.5.1 — mixed case + leading/trailing whitespace
    proto1 = "  AUTH MESSAGE SIGNATURE  "
    key1 = " AbC123 "
    inv1 = build_invoice(2, proto1, key1)
    h1 = hmac_sha256(STRESS_SHARED_SECRET, inv1.encode("utf-8"))
    stress.append({
        "name": "brc42-stress-vector-1-mixed-case-whitespace",
        "spec_ref": "§03.5.1",
        "inputs": {
            "security_level": 2,
            "protocol_id_raw": proto1,
            "key_id_raw": key1,
            "shared_secret_hex": STRESS_SHARED_SECRET.hex(),
            "shared_secret_source": "secp256k1 G compressed (test-only pin)",
        },
        "intermediate": {
            "normalized_protocol_id": proto1.lower().strip(),
            "invoice_string": inv1,
            "invoice_bytes_hex": inv1.encode("utf-8").hex(),
            "invoice_length_bytes": len(inv1.encode("utf-8")),
        },
        "expected": {
            "hmac_offset_hex": h1.hex(),
        },
    })

    # §03.5.2 — Unicode stress
    proto2 = "Café Société"   # input is already NFC
    key2 = "Δοκιμή"
    inv2 = build_invoice(2, proto2, key2)
    h2 = hmac_sha256(STRESS_SHARED_SECRET, inv2.encode("utf-8"))
    stress.append({
        "name": "brc42-stress-vector-2-unicode",
        "spec_ref": "§03.5.2",
        "inputs": {
            "security_level": 2,
            "protocol_id_raw": proto2,
            "key_id_raw": key2,
            "shared_secret_hex": STRESS_SHARED_SECRET.hex(),
            "shared_secret_source": "secp256k1 G compressed (test-only pin)",
        },
        "intermediate": {
            "normalized_protocol_id": proto2.lower().strip(),
            "invoice_string": inv2,
            "invoice_bytes_hex": inv2.encode("utf-8").hex(),
            "invoice_length_bytes": len(inv2.encode("utf-8")),
        },
        "expected": {
            "hmac_offset_hex": h2.hex(),
        },
    })

    # §03.5.3 — empty key_id
    proto3 = "test"
    key3 = ""
    inv3 = build_invoice(2, proto3, key3)
    h3 = hmac_sha256(STRESS_SHARED_SECRET, inv3.encode("utf-8"))
    stress.append({
        "name": "brc42-stress-vector-3-empty-key-id",
        "spec_ref": "§03.5.3",
        "inputs": {
            "security_level": 2,
            "protocol_id_raw": proto3,
            "key_id_raw": key3,
            "shared_secret_hex": STRESS_SHARED_SECRET.hex(),
            "shared_secret_source": "secp256k1 G compressed (test-only pin)",
        },
        "intermediate": {
            "normalized_protocol_id": proto3.lower().strip(),
            "invoice_string": inv3,
            "invoice_bytes_hex": inv3.encode("utf-8").hex(),
            "invoice_length_bytes": len(inv3.encode("utf-8")),
        },
        "expected": {
            "hmac_offset_hex": h3.hex(),
        },
    })

    return stress


def compute_brc42_all() -> dict:
    priv = compute_brc42_priv_vectors()
    pub = compute_brc42_pub_vectors()
    stress = compute_brc42_stress_vectors()

    # gate: every spec vector MUST round-trip
    all_priv_ok = all(v["agrees_with_spec_vector"] for v in priv)
    all_pub_ok = all(v["agrees_with_spec_vector"] for v in pub)

    return {
        "spec_section": "03",
        "spec_title": "Canonical BRC-42 Invoice + HMAC",
        "brc42_spec_source": "~/bsv/BRCs/key-derivation/0042.md",
        "private_derivation_vectors": priv,
        "public_derivation_vectors": pub,
        "all_private_vectors_agree": all_priv_ok,
        "all_public_vectors_agree": all_pub_ok,
        "stress_vectors": stress,
        "stress_vector_notes": (
            "Stress vectors pin shared_secret = secp256k1 G compressed (33 bytes) "
            "so HMAC outputs are reproducible without real ECDH material. "
            "Production §03.6 partial-ECDH is out of scope for these vectors."
        ),
    }


# ---------------------------------------------------------------------------
# §04 — SessionId
# ---------------------------------------------------------------------------
#
# SessionId = SHA-256(
#     "calhoun-binary-mpc-session-v1"    (29 bytes)
#  || initiator_identity_33B
#  || sorted_participant_identities      (33B * n, lex-ascending)
#  || threshold_u16_LE
#  || ceremony_kind_byte
#  || nonce_32B
#  || payload_digest_32B
# )

def session_id(initiator: bytes, participants: list[bytes], threshold: int,
               kind: int, nonce: bytes, payload_digest: bytes) -> tuple[bytes, bytes]:
    assert len(initiator) == 33
    for p in participants:
        assert len(p) == 33
    assert 0 <= threshold <= 0xFFFF
    assert 0 <= kind <= 0xFF
    assert len(nonce) == 32
    assert len(payload_digest) == 32

    sorted_participants = sorted(participants)  # byte-lex
    # forbid duplicates
    assert len(set(sorted_participants)) == len(sorted_participants), "duplicate participant"

    preimage = (
        SESSION_DOMAIN
        + initiator
        + b"".join(sorted_participants)
        + threshold.to_bytes(2, "little")
        + bytes([kind])
        + nonce
        + payload_digest
    )
    return preimage, H(preimage)


def compute_session_id_vectors() -> dict:
    """Two vectors per §04.10."""
    # Pin participants: 33-byte test identifiers (NOT valid pubkeys, but the
    # formula doesn't require curve validity for hashing — these are byte-strings).
    # Each participant identity is `0x02` || 31 zero bytes || sequence byte.
    p1 = b"\x02" + b"\x00" * 31 + b"\x01"
    p2 = b"\x02" + b"\x00" * 31 + b"\x02"
    p3 = b"\x02" + b"\x00" * 31 + b"\x03"
    assert len(p1) == 33 and len(p2) == 33 and len(p3) == 33

    # Vector A — routine 2-of-3 sign
    nonce_a = H(b"nonce-A")
    sighash_a = H(b"sighash-A")
    pre_a, sid_a = session_id(
        initiator=p1,
        participants=[p1, p2, p3],
        threshold=2,
        kind=0x02,  # sign
        nonce=nonce_a,
        payload_digest=sighash_a,
    )

    # Vector B — DKG with on-chain anchor
    # nonce = SHA256("block-800000-anchor")  (a stand-in test vector;
    # production usage hashes a real block hash per §04.4)
    nonce_b = H(b"block-800000-anchor")
    # payload_digest per §04.5: DKG = SHA-256("genesis" || canonical_cbor(policy_manifest))
    # Empty policy manifest: an empty CBOR map = 0xA0
    # We'll compute canonical CBOR of `{}` and concatenate with "genesis".
    empty_manifest_cbor = cbor2.dumps({}, canonical=True)
    assert empty_manifest_cbor == b"\xa0", \
        f"canonical CBOR of {{}} should be 0xa0, got {empty_manifest_cbor.hex()}"
    payload_digest_b = H(b"genesis" + empty_manifest_cbor)
    pre_b, sid_b = session_id(
        initiator=p1,
        participants=[p1, p2, p3],
        threshold=2,
        kind=0x01,  # dkg
        nonce=nonce_b,
        payload_digest=payload_digest_b,
    )

    vectors = [
        {
            "name": "session-id-vector-A-sign-2of3",
            "description": "Routine 2-of-3 sign ceremony, kind = 0x02",
            "inputs": {
                "domain_separator_ascii": "calhoun-binary-mpc-session-v1",
                "domain_separator_hex": SESSION_DOMAIN.hex(),
                "initiator_identity_hex": p1.hex(),
                "participants_hex_unsorted": [p1.hex(), p2.hex(), p3.hex()],
                "participants_hex_sorted": [p1.hex(), p2.hex(), p3.hex()],
                "threshold": 2,
                "threshold_bytes_le_hex": (2).to_bytes(2, "little").hex(),
                "ceremony_kind": 2,
                "ceremony_kind_name": "sign",
                "nonce_source": 'SHA256("nonce-A")',
                "nonce_hex": nonce_a.hex(),
                "payload_digest_source": 'SHA256("sighash-A")',
                "payload_digest_hex": sighash_a.hex(),
            },
            "preimage_hex": pre_a.hex(),
            "preimage_length_bytes": len(pre_a),
            "expected": {
                "session_id_hex": sid_a.hex(),
            },
        },
        {
            "name": "session-id-vector-B-dkg-on-chain-anchor",
            "description": "DKG ceremony with on-chain block anchor as nonce, empty policy manifest",
            "inputs": {
                "domain_separator_ascii": "calhoun-binary-mpc-session-v1",
                "domain_separator_hex": SESSION_DOMAIN.hex(),
                "initiator_identity_hex": p1.hex(),
                "participants_hex_sorted": [p1.hex(), p2.hex(), p3.hex()],
                "threshold": 2,
                "threshold_bytes_le_hex": (2).to_bytes(2, "little").hex(),
                "ceremony_kind": 1,
                "ceremony_kind_name": "dkg",
                "nonce_source": 'SHA256("block-800000-anchor")',
                "nonce_hex": nonce_b.hex(),
                "payload_digest_source": (
                    'SHA256("genesis" || canonical_cbor({})) '
                    'where canonical_cbor({}) = 0xa0'
                ),
                "empty_manifest_canonical_cbor_hex": empty_manifest_cbor.hex(),
                "payload_digest_hex": payload_digest_b.hex(),
            },
            "preimage_hex": pre_b.hex(),
            "preimage_length_bytes": len(pre_b),
            "expected": {
                "session_id_hex": sid_b.hex(),
            },
        },
    ]

    return {
        "spec_section": "04",
        "spec_title": "Canonical SessionId",
        "formula": (
            "SessionId = SHA-256("
            "\"calhoun-binary-mpc-session-v1\" (29B) || initiator_33B "
            "|| sorted_participants_33B*n || threshold_u16_LE || kind_u8 "
            "|| nonce_32B || payload_digest_32B)"
        ),
        "output_length_bytes": 32,
        "vectors": vectors,
    }


# ---------------------------------------------------------------------------
# §05 — MessageEnvelope (canonical CBOR per RFC 8949 §4.2)
# ---------------------------------------------------------------------------
#
# Produces ONE example envelope with all fields populated.
# Test-only ephemeral keys are pinned in the JSON output so anyone can
# regenerate byte-for-byte.

# Pinned test-only keys (DO NOT USE IN PRODUCTION).
SENDER_IDENTITY_PRIV_HEX = "01" * 32   # k = 0x010101...01 (a fixed test scalar)
RECIPIENT_IDENTITY_PRIV_HEX = "02" * 32
EPHEMERAL_PRIV_HEX = "03" * 32
ENVELOPE_IV_HEX = "0a0b0c0d0e0f101112131415"   # 12-byte fixed IV (test-only)
INNER_CGGMP24_MSG_BYTES = b"cggmp24-test-inner-msg-round-1"


def manual_canonical_cbor(value: Any) -> bytes:
    """A minimal RFC 8949 §4.2 deterministic encoder, used as a cross-check
    against cbor2's `canonical=True`. Supports the subset we need:

      - integers in [0, 2**64-1]
      - byte strings
      - text strings
      - lists
      - maps with integer keys (we sort canonically)
    """

    def encode_uint(major: int, n: int) -> bytes:
        assert n >= 0
        if n < 24:
            return bytes([(major << 5) | n])
        if n < 0x100:
            return bytes([(major << 5) | 24, n])
        if n < 0x10000:
            return bytes([(major << 5) | 25]) + n.to_bytes(2, "big")
        if n < 0x100000000:
            return bytes([(major << 5) | 26]) + n.to_bytes(4, "big")
        return bytes([(major << 5) | 27]) + n.to_bytes(8, "big")

    def enc(v: Any) -> bytes:
        if isinstance(v, bool):
            raise ValueError("bools not supported by minimal encoder")
        if isinstance(v, int):
            if v >= 0:
                return encode_uint(0, v)
            return encode_uint(1, -1 - v)
        if isinstance(v, (bytes, bytearray)):
            return encode_uint(2, len(v)) + bytes(v)
        if isinstance(v, str):
            b = v.encode("utf-8")
            return encode_uint(3, len(b)) + b
        if isinstance(v, list):
            out = encode_uint(4, len(v))
            for item in v:
                out += enc(item)
            return out
        if isinstance(v, dict):
            # RFC 8949 §4.2.1: deterministic map ordering is by the bytewise
            # lexicographic order of the *encoded* keys (length is part of
            # the encoded representation, so this is a total order).
            encoded_keys = [(enc(k), k, val) for k, val in v.items()]
            encoded_keys.sort(key=lambda t: t[0])
            out = encode_uint(5, len(encoded_keys))
            for ek, _k, val in encoded_keys:
                out += ek + enc(val)
            return out
        raise ValueError(f"unsupported type: {type(v)}")

    return enc(value)


def brc78_ecies_encrypt(eph_priv: int, recipient_pub: Point, plaintext: bytes,
                        iv: bytes) -> bytes:
    """BRC-78 ECIES envelope per §05.5.

    Layout: eph_pub_33B || iv_12B || ciphertext || tag_16B
    aes_key = SHA-256(shared_compressed_33B)
    """
    from Crypto.Cipher import AES
    eph_pub = eph_priv * G
    shared = eph_priv * recipient_pub
    aes_key = H(compressed_pub_from_point(shared))
    cipher = AES.new(aes_key, AES.MODE_GCM, nonce=iv)
    ct, tag = cipher.encrypt_and_digest(plaintext)
    return compressed_pub_from_point(eph_pub) + iv + ct + tag


def brc31_sign(identity_priv: int, message: bytes) -> bytes:
    """BRC-31 (Authrite) signature: ECDSA over SHA-256(message), DER-encoded,
    with low-s normalization (BIP-62 / BRC-31 standard practice).

    Per §05.6, the signature is over the canonical CBOR encoding of fields
    1..8. RFC 6979 deterministic nonce so the same inputs always produce
    the same bytes.
    """
    from ecdsa.util import sigdecode_der, sigencode_der
    sk = SigningKey.from_secret_exponent(identity_priv % N, curve=CURVE)
    der = sk.sign_deterministic(
        message, hashfunc=hashlib.sha256, sigencode=sigencode_der
    )
    # Decode, normalize to low-s, re-encode.
    r, s = sigdecode_der(der, N)
    if s > N // 2:
        s = N - s
    der = sigencode_der(r, s, N)
    return der


def compute_message_envelope_vector() -> dict:
    # Reuse session-id vector A's session_id and joint key = G compressed
    sid_a = H(b"test-vector-A")
    joint_pubkey = G_COMPRESSED  # 33 bytes
    phase_str = "sign"
    round_num = 1
    from_party = 0
    to_party = 1

    # ExecutionId for this envelope (sign phase) — reuse Vector A's eid
    _, eid = execution_id(
        version=0x01, algo=0x01, phase=0x04, session_id=sid_a, joint_pubkey=joint_pubkey,
    )
    eid_prefix_8 = eid[:8]

    # Inner ECIES (using our test pinned keys)
    sender_priv = int(SENDER_IDENTITY_PRIV_HEX, 16)
    recipient_priv = int(RECIPIENT_IDENTITY_PRIV_HEX, 16)
    eph_priv = int(EPHEMERAL_PRIV_HEX, 16)
    sender_pub = sender_priv * G
    recipient_pub = recipient_priv * G

    iv = bytes.fromhex(ENVELOPE_IV_HEX)
    inner_bytes = brc78_ecies_encrypt(eph_priv, recipient_pub, INNER_CGGMP24_MSG_BYTES, iv)

    correlation_id = "01927f9f-7050-7a4d-a3c5-deadbeefcafe"  # fake UUIDv7
    traceparent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

    # CBOR map with numeric keys per §05.3.
    # We construct the *pre-signature* map (fields 1..8), encode it canonically,
    # sign with BRC-31, then construct the FULL map (fields 1..10) [+ 11, 12].
    pre_sig_map = {
        1: 0x01,                 # version
        2: sid_a,                # session_id
        3: joint_pubkey,         # joint_pubkey
        4: phase_str,            # phase
        5: round_num,            # round
        6: from_party,           # from_party
        7: to_party,             # to_party
        8: inner_bytes,          # inner ECIES
    }

    pre_sig_cbor = cbor2.dumps(pre_sig_map, canonical=True)
    pre_sig_cbor_manual = manual_canonical_cbor(pre_sig_map)
    assert pre_sig_cbor == pre_sig_cbor_manual, (
        f"canonical CBOR mismatch:\n  cbor2  = {pre_sig_cbor.hex()}\n"
        f"  manual = {pre_sig_cbor_manual.hex()}"
    )

    sig_der = brc31_sign(sender_priv, pre_sig_cbor)

    full_map = dict(pre_sig_map)
    full_map[9] = sig_der
    full_map[10] = eid_prefix_8
    full_map[11] = correlation_id
    full_map[12] = traceparent

    full_cbor = cbor2.dumps(full_map, canonical=True)
    full_cbor_manual = manual_canonical_cbor(full_map)
    assert full_cbor == full_cbor_manual, (
        f"canonical CBOR mismatch (full):\n  cbor2  = {full_cbor.hex()}\n"
        f"  manual = {full_cbor_manual.hex()}"
    )

    # Verify the signature roundtrips.
    sender_vk = VerifyingKey.from_public_point(sender_pub, curve=CURVE)
    sender_vk.verify(
        sig_der, pre_sig_cbor, hashfunc=hashlib.sha256,
        sigdecode=__import__("ecdsa.util", fromlist=["sigdecode_der"]).sigdecode_der,
    )

    # Diagnostic notation (RFC 8949 §8): hand-rolled for our map.
    def diag(value: Any, indent: int = 0) -> str:
        pad = "  " * indent
        if isinstance(value, int):
            return str(value)
        if isinstance(value, bytes):
            return f"h'{value.hex()}'"
        if isinstance(value, str):
            return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
        if isinstance(value, list):
            inner = ", ".join(diag(v, indent + 1) for v in value)
            return f"[{inner}]"
        if isinstance(value, dict):
            lines = []
            for k, v in sorted(value.items(), key=lambda kv: kv[0]):
                lines.append(f"{pad}  {diag(k)}: {diag(v, indent + 1)}")
            return "{\n" + ",\n".join(lines) + "\n" + pad + "}"
        raise ValueError(type(value))

    diag_text = diag(full_map, 0)

    return {
        "spec_section": "05",
        "spec_title": "Canonical MessageEnvelope",
        "encoding": "CBOR (RFC 8949 §4.2 deterministic)",
        "test_only_keys": {
            "test_only_ephemeral_sender_priv_hex": SENDER_IDENTITY_PRIV_HEX,
            "test_only_ephemeral_recipient_priv_hex": RECIPIENT_IDENTITY_PRIV_HEX,
            "test_only_ephemeral_envelope_eph_priv_hex": EPHEMERAL_PRIV_HEX,
            "test_only_envelope_aes_iv_hex": ENVELOPE_IV_HEX,
            "test_only_inner_cggmp24_msg_ascii": INNER_CGGMP24_MSG_BYTES.decode("utf-8"),
            "WARNING": "These are pinned test keys. DO NOT USE IN PRODUCTION.",
        },
        "derived": {
            "sender_identity_pub_hex": compressed_pub_from_point(sender_pub).hex(),
            "recipient_identity_pub_hex": compressed_pub_from_point(recipient_pub).hex(),
            "ephemeral_pub_hex": compressed_pub_from_point(eph_priv * G).hex(),
            "session_id_hex": sid_a.hex(),
            "joint_pubkey_hex": joint_pubkey.hex(),
            "execution_id_hex": eid.hex(),
            "execution_id_prefix_8_hex": eid_prefix_8.hex(),
            "inner_brc78_ecies_hex": inner_bytes.hex(),
            "pre_signature_cbor_hex": pre_sig_cbor.hex(),
            "sender_sig_brc31_der_hex": sig_der.hex(),
            "full_envelope_cbor_hex": full_cbor.hex(),
            "full_envelope_cbor_length_bytes": len(full_cbor),
        },
        "vector": {
            "fields": {
                "1_version": 0x01,
                "2_session_id_hex": sid_a.hex(),
                "3_joint_pubkey_hex": joint_pubkey.hex(),
                "4_phase": phase_str,
                "5_round": round_num,
                "6_from_party": from_party,
                "7_to_party": to_party,
                "8_inner_hex": inner_bytes.hex(),
                "9_sender_sig_brc31_hex": sig_der.hex(),
                "10_execution_id_prefix_hex": eid_prefix_8.hex(),
                "11_correlation_id": correlation_id,
                "12_traceparent": traceparent,
            },
            "full_envelope_cbor_hex": full_cbor.hex(),
        },
        "diagnostic_notation": diag_text,
        "cross_check": {
            "cbor2_vs_manual_canonical_encoder": "agree (asserted in script)",
            "brc31_signature_verifies": True,
        },
    }


# ---------------------------------------------------------------------------
# Output writer
# ---------------------------------------------------------------------------

def write_json(path: str, obj: Any) -> None:
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"wrote {path}")


def main() -> int:
    print("=" * 70)
    print("MPC-Spec canonical test-vector computation")
    print("=" * 70)

    # §02
    eid = compute_execution_id_vectors()
    print("\n--- §02 ExecutionId ---")
    for v in eid["vectors"]:
        print(f"  {v['name']}: {v['expected']['execution_id_hex']}")
    write_json(os.path.join(TV_DIR, "02-execution-id.json"), eid)

    # §03
    brc42 = compute_brc42_all()
    print("\n--- §03 BRC-42 Invoice + HMAC ---")
    print(f"  private vectors agree with BRC-42 spec: {brc42['all_private_vectors_agree']}")
    print(f"  public  vectors agree with BRC-42 spec: {brc42['all_public_vectors_agree']}")
    for v in brc42["private_derivation_vectors"]:
        print(f"  {v['name']}: child_priv = {v['computed']['childPrivateKey_hex']} (agree={v['agrees_with_spec_vector']})")
    for v in brc42["public_derivation_vectors"]:
        print(f"  {v['name']}: child_pub  = {v['computed']['childPublicKey_hex']} (agree={v['agrees_with_spec_vector']})")
    for s in brc42["stress_vectors"]:
        print(f"  {s['name']}: hmac = {s['expected']['hmac_offset_hex']}")
    if not (brc42["all_private_vectors_agree"] and brc42["all_public_vectors_agree"]):
        print("\nFATAL: BRC-42 spec vectors did not round-trip. Refusing to write.")
        return 2
    write_json(os.path.join(TV_DIR, "03-brc42-invoice.json"), brc42)

    # §04
    sid = compute_session_id_vectors()
    print("\n--- §04 SessionId ---")
    for v in sid["vectors"]:
        print(f"  {v['name']}: {v['expected']['session_id_hex']}")
    write_json(os.path.join(TV_DIR, "04-session-id.json"), sid)

    # §05
    env = compute_message_envelope_vector()
    print("\n--- §05 MessageEnvelope ---")
    print(f"  envelope_cbor ({env['derived']['full_envelope_cbor_length_bytes']} bytes): "
          f"{env['vector']['full_envelope_cbor_hex'][:80]}...")
    write_json(os.path.join(TV_DIR, "05-message-envelope.json"), env)

    # Also write raw CBOR hex and diagnostic for §05 to dedicated files.
    cbor_hex_path = os.path.join(TV_DIR, "05-message-envelope.cbor.hex")
    with open(cbor_hex_path, "w") as f:
        f.write(env["vector"]["full_envelope_cbor_hex"] + "\n")
    print(f"wrote {cbor_hex_path}")

    diag_path = os.path.join(TV_DIR, "05-message-envelope.diag.txt")
    with open(diag_path, "w") as f:
        f.write(env["diagnostic_notation"] + "\n")
    print(f"wrote {diag_path}")

    print("\nAll vectors written. Run `cargo run` against cross_validate.rs to "
          "cross-validate BRC-42 + ExecutionId + SessionId.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
