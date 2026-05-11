//! Cross-validator for MPC-Spec test vectors.
//!
//! Reads `../../02-execution-id.json`, `../../03-brc42-invoice.json`,
//! `../../04-session-id.json`, and `../../05-message-envelope.json` —
//! recomputes every vector from inputs using independent Rust crates
//! (`sha2`, `hmac`, `k256`, `ciborium`) — and asserts byte-equality with
//! the `expected` value in the JSON. Any mismatch is a fatal error.
//!
//! Run from this directory:
//!     cargo run --release
//!
//! Exit code 0 = all vectors agree, non-zero = at least one disagreement.

use std::fs;
use std::path::{Path, PathBuf};

use hmac::{Hmac, Mac};
use k256::elliptic_curve::sec1::ToEncodedPoint;
use k256::{ProjectivePoint, PublicKey, Scalar, SecretKey};
use sha2::{Digest, Sha256};

type HmacSha256 = Hmac<Sha256>;

const EXECID_DOMAIN: &[u8] = b"calhoun-binary-mpc"; // 18 bytes
const SESSION_DOMAIN: &[u8] = b"calhoun-binary-mpc-session-v1"; // 29 bytes

fn sha256(data: &[u8]) -> [u8; 32] {
    let mut h = Sha256::new();
    h.update(data);
    let out = h.finalize();
    let mut a = [0u8; 32];
    a.copy_from_slice(&out);
    a
}

fn hmac_sha256(key: &[u8], data: &[u8]) -> [u8; 32] {
    let mut m = <HmacSha256 as Mac>::new_from_slice(key).expect("HMAC accepts any key length");
    m.update(data);
    let out = m.finalize().into_bytes();
    let mut a = [0u8; 32];
    a.copy_from_slice(&out);
    a
}

fn hex_decode(s: &str) -> Vec<u8> {
    hex::decode(s).unwrap_or_else(|e| panic!("hex decode failed for {s:?}: {e}"))
}

fn print_check(label: &str, expected_hex: &str, computed: &[u8]) -> bool {
    let computed_hex = hex::encode(computed);
    if computed_hex == expected_hex.to_lowercase() {
        println!("  OK   {label}");
        println!("       expected = {expected_hex}");
        println!("       computed = {computed_hex}");
        true
    } else {
        println!("  FAIL {label}");
        println!("       expected = {expected_hex}");
        println!("       computed = {computed_hex}");
        false
    }
}

// ---------------------------------------------------------------------------
// §02 ExecutionId
// ---------------------------------------------------------------------------

fn execution_id(
    version: u8,
    algo: u8,
    phase: u8,
    session_id: &[u8; 32],
    joint_pubkey: &[u8; 33],
) -> [u8; 32] {
    let mut buf = Vec::with_capacity(86);
    buf.extend_from_slice(EXECID_DOMAIN);
    buf.push(version);
    buf.push(algo);
    buf.push(phase);
    buf.extend_from_slice(session_id);
    buf.extend_from_slice(joint_pubkey);
    assert_eq!(buf.len(), 86, "ExecutionId preimage must be 86 bytes");
    sha256(&buf)
}

fn validate_section_02(json: &serde_json::Value) -> bool {
    println!("\n=== §02 ExecutionId ===");
    let mut all_ok = true;
    let vectors = json["vectors"].as_array().expect("§02 vectors array");
    for v in vectors {
        let name = v["name"].as_str().unwrap();
        let inp = &v["inputs"];
        let version = inp["version"].as_u64().unwrap() as u8;
        let algo = inp["algorithm_tag"].as_u64().unwrap() as u8;
        let phase = inp["phase_tag"].as_u64().unwrap() as u8;
        let sid_vec = hex_decode(inp["session_id_hex"].as_str().unwrap());
        let jpk_vec = hex_decode(inp["joint_pubkey_hex"].as_str().unwrap());
        let mut sid = [0u8; 32];
        sid.copy_from_slice(&sid_vec);
        let mut jpk = [0u8; 33];
        jpk.copy_from_slice(&jpk_vec);
        let eid = execution_id(version, algo, phase, &sid, &jpk);
        let expected = v["expected"]["execution_id_hex"].as_str().unwrap();
        all_ok &= print_check(name, expected, &eid);
    }
    all_ok
}

// ---------------------------------------------------------------------------
// §03 BRC-42
// ---------------------------------------------------------------------------

fn compressed_pubkey(pk: &PublicKey) -> [u8; 33] {
    let ep = pk.to_encoded_point(true);
    let bytes = ep.as_bytes();
    assert_eq!(bytes.len(), 33);
    let mut a = [0u8; 33];
    a.copy_from_slice(bytes);
    a
}

fn validate_section_03(json: &serde_json::Value) -> bool {
    println!("\n=== §03 BRC-42 invoice + HMAC ===");
    let mut all_ok = true;

    // (a) private derivation vectors
    let priv_vectors = json["private_derivation_vectors"].as_array().unwrap();
    for v in priv_vectors {
        let name = v["name"].as_str().unwrap();
        let inp = &v["inputs"];
        let sender_pub_hex = inp["senderPublicKey"].as_str().unwrap();
        let recip_priv_hex = inp["recipientPrivateKey"].as_str().unwrap();
        let invoice = inp["invoiceNumber"].as_str().unwrap();

        let sender_pub = PublicKey::from_sec1_bytes(&hex_decode(sender_pub_hex))
            .expect("sender pub parses");
        let recip_priv = SecretKey::from_slice(&hex_decode(recip_priv_hex))
            .expect("recip priv parses");

        // shared_secret_point = recip_priv * sender_pub
        let shared_point: ProjectivePoint =
            ProjectivePoint::from(sender_pub.as_affine()) * recip_priv.to_nonzero_scalar().as_ref();
        let shared_pk = PublicKey::try_from(shared_point.to_affine()).expect("shared point ok");
        let shared_compressed = compressed_pubkey(&shared_pk);

        // hmac
        let hmac = hmac_sha256(&shared_compressed, invoice.as_bytes());

        // child_priv = recip_priv + reduce_mod_n(hmac)
        let child_scalar =
            (*recip_priv.to_nonzero_scalar().as_ref()) + scalar_from_be_reduce(&hmac);
        let child_priv_bytes = child_scalar.to_bytes();

        let expected = v["expected"]["childPrivateKey_hex"].as_str().unwrap();
        all_ok &= print_check(name, expected, &child_priv_bytes);
    }

    // (b) public derivation vectors
    let pub_vectors = json["public_derivation_vectors"].as_array().unwrap();
    for v in pub_vectors {
        let name = v["name"].as_str().unwrap();
        let inp = &v["inputs"];
        let sender_priv_hex = inp["senderPrivateKey"].as_str().unwrap();
        let recip_pub_hex = inp["recipientPublicKey"].as_str().unwrap();
        let invoice = inp["invoiceNumber"].as_str().unwrap();

        let sender_priv = SecretKey::from_slice(&hex_decode(sender_priv_hex))
            .expect("sender priv parses");
        let recip_pub = PublicKey::from_sec1_bytes(&hex_decode(recip_pub_hex))
            .expect("recip pub parses");

        // shared = sender_priv * recip_pub
        let shared_point: ProjectivePoint =
            ProjectivePoint::from(recip_pub.as_affine()) * sender_priv.to_nonzero_scalar().as_ref();
        let shared_pk = PublicKey::try_from(shared_point.to_affine()).expect("shared point ok");
        let shared_compressed = compressed_pubkey(&shared_pk);

        let hmac = hmac_sha256(&shared_compressed, invoice.as_bytes());
        let offset = scalar_from_be_reduce(&hmac);

        // child_pub = recip_pub + G * offset
        let offset_point = ProjectivePoint::GENERATOR * offset;
        let child_point: ProjectivePoint =
            ProjectivePoint::from(recip_pub.as_affine()) + offset_point;
        let child_pk = PublicKey::try_from(child_point.to_affine()).expect("child point ok");
        let child_compressed = compressed_pubkey(&child_pk);

        let expected = v["expected"]["childPublicKey_hex"].as_str().unwrap();
        all_ok &= print_check(name, expected, &child_compressed);
    }

    // (c) stress vectors: invoice = "{level}-{lower+trim(proto)}-{key_id}",
    //                     hmac = HMAC-SHA256(shared_secret, invoice.as_bytes()).
    let stress = json["stress_vectors"].as_array().unwrap();
    for v in stress {
        let name = v["name"].as_str().unwrap();
        let inp = &v["inputs"];
        let level = inp["security_level"].as_u64().unwrap() as u8;
        let proto_raw = inp["protocol_id_raw"].as_str().unwrap();
        let key_id_raw = inp["key_id_raw"].as_str().unwrap();
        let shared_hex = inp["shared_secret_hex"].as_str().unwrap();
        let shared = hex_decode(shared_hex);

        let normalized = proto_raw.to_lowercase().trim().to_string();
        let invoice = format!("{}-{}-{}", level, normalized, key_id_raw);
        let hmac = hmac_sha256(&shared, invoice.as_bytes());

        let expected = v["expected"]["hmac_offset_hex"].as_str().unwrap();
        all_ok &= print_check(name, expected, &hmac);
        // sanity: invoice string from JSON must match what we built
        let json_invoice = v["intermediate"]["invoice_string"].as_str().unwrap();
        if json_invoice != invoice {
            println!(
                "  WARN invoice string mismatch (informational):\n       json   = {json_invoice:?}\n       rebuilt= {invoice:?}"
            );
            all_ok = false;
        }
    }

    all_ok
}

/// Reduce a 32-byte big-endian scalar modulo the secp256k1 curve order.
fn scalar_from_be_reduce(bytes: &[u8; 32]) -> Scalar {
    use k256::elliptic_curve::ops::Reduce;
    Scalar::reduce(k256::U256::from_be_slice(bytes))
}

// ---------------------------------------------------------------------------
// §04 SessionId
// ---------------------------------------------------------------------------

fn session_id(
    initiator: &[u8; 33],
    sorted_participants: &[[u8; 33]],
    threshold: u16,
    kind: u8,
    nonce: &[u8; 32],
    payload_digest: &[u8; 32],
) -> [u8; 32] {
    let mut buf = Vec::new();
    buf.extend_from_slice(SESSION_DOMAIN);
    buf.extend_from_slice(initiator);
    for p in sorted_participants {
        buf.extend_from_slice(p);
    }
    buf.extend_from_slice(&threshold.to_le_bytes());
    buf.push(kind);
    buf.extend_from_slice(nonce);
    buf.extend_from_slice(payload_digest);
    sha256(&buf)
}

fn validate_section_04(json: &serde_json::Value) -> bool {
    println!("\n=== §04 SessionId ===");
    let mut all_ok = true;
    for v in json["vectors"].as_array().unwrap() {
        let name = v["name"].as_str().unwrap();
        let inp = &v["inputs"];
        let initiator_hex = inp["initiator_identity_hex"].as_str().unwrap();
        let parts_sorted = inp["participants_hex_sorted"].as_array().unwrap();
        let threshold = inp["threshold"].as_u64().unwrap() as u16;
        let kind = inp["ceremony_kind"].as_u64().unwrap() as u8;
        let nonce_hex = inp["nonce_hex"].as_str().unwrap();
        let payload_hex = inp["payload_digest_hex"].as_str().unwrap();

        let mut initiator = [0u8; 33];
        initiator.copy_from_slice(&hex_decode(initiator_hex));
        let participants: Vec<[u8; 33]> = parts_sorted
            .iter()
            .map(|p| {
                let bytes = hex_decode(p.as_str().unwrap());
                let mut a = [0u8; 33];
                a.copy_from_slice(&bytes);
                a
            })
            .collect();
        // assert already sorted
        let mut sorted = participants.clone();
        sorted.sort();
        assert_eq!(
            participants, sorted,
            "JSON participants_hex_sorted must already be sorted"
        );
        let mut nonce = [0u8; 32];
        nonce.copy_from_slice(&hex_decode(nonce_hex));
        let mut payload = [0u8; 32];
        payload.copy_from_slice(&hex_decode(payload_hex));

        let sid = session_id(&initiator, &participants, threshold, kind, &nonce, &payload);
        let expected = v["expected"]["session_id_hex"].as_str().unwrap();
        all_ok &= print_check(name, expected, &sid);
    }
    all_ok
}

// ---------------------------------------------------------------------------
// §05 MessageEnvelope — partial cross-validation
// ---------------------------------------------------------------------------
//
// For the envelope:
//   - We re-encode the same field map with `ciborium` and confirm the bytes
//     match what Python's `cbor2 canonical=True` produced.
//   - We re-verify the BRC-31 ECDSA signature against the recomputed
//     pre-signature CBOR using k256.
//   - We re-derive the ExecutionId prefix from §02 inputs and confirm.
//
// AES-GCM decryption of the inner is not re-validated here (we cross-check
// CBOR + signature; the inner is opaque bytes from the envelope's viewpoint).

fn validate_section_05(json: &serde_json::Value) -> bool {
    println!("\n=== §05 MessageEnvelope ===");
    let mut all_ok = true;

    let derived = &json["derived"];

    // 1) Pre-signature CBOR round-trip via ciborium.
    let fields = &json["vector"]["fields"];
    let version = fields["1_version"].as_u64().unwrap() as u8;
    let session_id = hex_decode(fields["2_session_id_hex"].as_str().unwrap());
    let joint_pub = hex_decode(fields["3_joint_pubkey_hex"].as_str().unwrap());
    let phase = fields["4_phase"].as_str().unwrap().to_string();
    let round = fields["5_round"].as_u64().unwrap();
    let from_party = fields["6_from_party"].as_u64().unwrap();
    let to_party = fields["7_to_party"].as_u64().unwrap();
    let inner = hex_decode(fields["8_inner_hex"].as_str().unwrap());
    let sig_der = hex_decode(fields["9_sender_sig_brc31_hex"].as_str().unwrap());
    let eid_prefix = hex_decode(fields["10_execution_id_prefix_hex"].as_str().unwrap());
    let correlation_id = fields["11_correlation_id"].as_str().unwrap().to_string();
    let traceparent = fields["12_traceparent"].as_str().unwrap().to_string();

    // Build a canonical CBOR map manually. RFC 8949 §4.2.1 — sort entries
    // by bytewise lex order of *encoded* keys. With small u8 keys (1..12),
    // this is just numeric order.
    let pre_sig_bytes = encode_cbor_map(vec![
        (cbor_uint(1), cbor_uint(version as u64)),
        (cbor_uint(2), cbor_bytes(&session_id)),
        (cbor_uint(3), cbor_bytes(&joint_pub)),
        (cbor_uint(4), cbor_text(&phase)),
        (cbor_uint(5), cbor_uint(round)),
        (cbor_uint(6), cbor_uint(from_party)),
        (cbor_uint(7), cbor_uint(to_party)),
        (cbor_uint(8), cbor_bytes(&inner)),
    ]);

    let expected_pre = derived["pre_signature_cbor_hex"].as_str().unwrap();
    all_ok &= print_check("pre-signature CBOR (fields 1..8) matches Python", expected_pre, &pre_sig_bytes);

    // 2) Re-verify the BRC-31 ECDSA signature.
    let sender_pub_hex = derived["sender_identity_pub_hex"].as_str().unwrap();
    let sender_pub = PublicKey::from_sec1_bytes(&hex_decode(sender_pub_hex))
        .expect("sender pub parses");
    use k256::ecdsa::{signature::Verifier, Signature, VerifyingKey};
    let vk = VerifyingKey::from(&sender_pub);
    let sig = Signature::from_der(&sig_der).expect("DER decodes");
    let verifies = vk.verify(&pre_sig_bytes, &sig).is_ok();
    println!(
        "  {} BRC-31 ECDSA signature verifies against pre-signature CBOR",
        if verifies { "OK  " } else { "FAIL" }
    );
    all_ok &= verifies;

    // 3) Full envelope (fields 1..12) CBOR matches.
    let full_bytes = encode_cbor_map(vec![
        (cbor_uint(1), cbor_uint(version as u64)),
        (cbor_uint(2), cbor_bytes(&session_id)),
        (cbor_uint(3), cbor_bytes(&joint_pub)),
        (cbor_uint(4), cbor_text(&phase)),
        (cbor_uint(5), cbor_uint(round)),
        (cbor_uint(6), cbor_uint(from_party)),
        (cbor_uint(7), cbor_uint(to_party)),
        (cbor_uint(8), cbor_bytes(&inner)),
        (cbor_uint(9), cbor_bytes(&sig_der)),
        (cbor_uint(10), cbor_bytes(&eid_prefix)),
        (cbor_uint(11), cbor_text(&correlation_id)),
        (cbor_uint(12), cbor_text(&traceparent)),
    ]);
    let expected_full = derived["full_envelope_cbor_hex"].as_str().unwrap();
    all_ok &= print_check("full envelope CBOR (fields 1..12) matches Python", expected_full, &full_bytes);

    // 4) Re-derive ExecutionId prefix.
    let mut sid = [0u8; 32];
    sid.copy_from_slice(&session_id);
    let mut jpk = [0u8; 33];
    jpk.copy_from_slice(&joint_pub);
    let eid = execution_id(0x01, 0x01, 0x04, &sid, &jpk);
    let prefix_match = eid[..8].to_vec() == eid_prefix;
    println!(
        "  {} ExecutionId prefix (sign-phase, joint=G compressed) matches",
        if prefix_match { "OK  " } else { "FAIL" }
    );
    all_ok &= prefix_match;

    all_ok
}

// ---------------------------------------------------------------------------
// Minimal canonical CBOR encoder (independent of ciborium for the comparison)
// ---------------------------------------------------------------------------

fn cbor_uint(n: u64) -> Vec<u8> {
    encode_uint(0, n)
}

fn cbor_bytes(b: &[u8]) -> Vec<u8> {
    let mut out = encode_uint(2, b.len() as u64);
    out.extend_from_slice(b);
    out
}

fn cbor_text(s: &str) -> Vec<u8> {
    let b = s.as_bytes();
    let mut out = encode_uint(3, b.len() as u64);
    out.extend_from_slice(b);
    out
}

fn encode_uint(major: u8, n: u64) -> Vec<u8> {
    let mut out = Vec::new();
    if n < 24 {
        out.push((major << 5) | (n as u8));
    } else if n < 0x100 {
        out.push((major << 5) | 24);
        out.push(n as u8);
    } else if n < 0x10000 {
        out.push((major << 5) | 25);
        out.extend_from_slice(&(n as u16).to_be_bytes());
    } else if n < 0x100000000 {
        out.push((major << 5) | 26);
        out.extend_from_slice(&(n as u32).to_be_bytes());
    } else {
        out.push((major << 5) | 27);
        out.extend_from_slice(&n.to_be_bytes());
    }
    out
}

fn encode_cbor_map(entries: Vec<(Vec<u8>, Vec<u8>)>) -> Vec<u8> {
    // RFC 8949 §4.2.1: sort entries by bytewise lex order of encoded keys.
    let mut entries = entries;
    entries.sort_by(|a, b| a.0.cmp(&b.0));
    let mut out = encode_uint(5, entries.len() as u64);
    for (k, v) in entries {
        out.extend_from_slice(&k);
        out.extend_from_slice(&v);
    }
    out
}

// ---------------------------------------------------------------------------
// Driver
// ---------------------------------------------------------------------------

fn locate_tv_dir() -> PathBuf {
    // Cargo runs us from the cross_validate_rs directory.
    // Test vectors live at ../../
    let here = Path::new(env!("CARGO_MANIFEST_DIR"));
    here.join("..").join("..").canonicalize().unwrap()
}

fn read_json(path: &Path) -> serde_json::Value {
    let s = fs::read_to_string(path)
        .unwrap_or_else(|e| panic!("read {} failed: {e}", path.display()));
    serde_json::from_str(&s)
        .unwrap_or_else(|e| panic!("parse {} failed: {e}", path.display()))
}

fn main() {
    let tv = locate_tv_dir();
    println!("Cross-validating MPC-Spec test vectors in {}", tv.display());

    let eid_json = read_json(&tv.join("02-execution-id.json"));
    let brc42_json = read_json(&tv.join("03-brc42-invoice.json"));
    let sid_json = read_json(&tv.join("04-session-id.json"));
    let env_json = read_json(&tv.join("05-message-envelope.json"));

    let ok02 = validate_section_02(&eid_json);
    let ok03 = validate_section_03(&brc42_json);
    let ok04 = validate_section_04(&sid_json);
    let ok05 = validate_section_05(&env_json);

    println!("\n=== Summary ===");
    println!("  §02 ExecutionId      : {}", if ok02 { "AGREE" } else { "DISAGREE" });
    println!("  §03 BRC-42 invoice   : {}", if ok03 { "AGREE" } else { "DISAGREE" });
    println!("  §04 SessionId        : {}", if ok04 { "AGREE" } else { "DISAGREE" });
    println!("  §05 MessageEnvelope  : {}", if ok05 { "AGREE" } else { "DISAGREE" });

    if !(ok02 && ok03 && ok04 && ok05) {
        eprintln!("\nFATAL: at least one vector disagreed. Do NOT commit.");
        std::process::exit(2);
    }
    println!("\nAll vectors AGREE byte-for-byte across Python and Rust paths.");
}
