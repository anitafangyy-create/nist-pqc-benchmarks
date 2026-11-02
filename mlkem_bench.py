"""
ML-KEM-1024 vs ECDH-secp256k1 microbenchmark for post-quantum note encryption.

Measures, for each scheme:
  * key generation time
  * encapsulation / ECDH-exchange time (sender side)
  * decapsulation / ECDH-exchange time (recipient side)
  * public key size
  * ciphertext / ephemeral public key size

Then projects the cost onto a Shielded Bitcoin note-spend witness:
  * secp256k1 ECDH: 33 B compressed ephemeral pk, 32 B shared secret
  * ML-KEM-1024:    1568 B ciphertext, 32 B shared secret
"""
from __future__ import annotations

import time
import json
from pathlib import Path
from statistics import mean, stdev

from pqcrypto.kem import ml_kem_1024

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

OUT = Path(__file__).parent
N_RUNS = 20


def bench_mlkem():
    print("=" * 60)
    print("ML-KEM-1024 (FIPS 203)")
    print("=" * 60)

    # keygen
    kg_times = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        pk, sk = ml_kem_1024.keygen()
        kg_times.append(time.perf_counter() - t0)

    # encaps (sender): uses pk
    enc_times = []
    ct_list = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        ct, ss = ml_kem_1024.encaps(pk)
        enc_times.append(time.perf_counter() - t0)
        ct_list.append((ct, ss))

    # decaps (recipient): uses sk, ct
    dec_times = []
    for ct, ss in ct_list:
        t0 = time.perf_counter()
        ss2 = ml_kem_1024.decaps(sk, ct)
        dec_times.append(time.perf_counter() - t0)
        assert ss == ss2, "decaps round-trip failed"

    sizes = {
        "public_key_bytes": ml_kem_1024.PUBLIC_KEY_SIZE,    # 1568
        "secret_key_bytes": ml_kem_1024.SECRET_KEY_SIZE,    # 3168
        "ciphertext_bytes": ml_kem_1024.CIPHERTEXT_SIZE,    # 1568
        "shared_secret_bytes": ml_kem_1024.SHARED_SECRET_SIZE,  # 32
    }
    print(f"  sizes: {sizes}")
    print(f"  keygen:   {mean(kg_times)*1000:.3f} ± {stdev(kg_times)*1000:.3f} ms")
    print(f"  encaps:   {mean(enc_times)*1000:.3f} ± {stdev(enc_times)*1000:.3f} ms")
    print(f"  decaps:   {mean(dec_times)*1000:.3f} ± {stdev(dec_times)*1000:.3f} ms")
    return {
        "scheme": "ML-KEM-1024",
        **sizes,
        "keygen_ms": mean(kg_times) * 1000,
        "keygen_std_ms": stdev(kg_times) * 1000,
        "encaps_ms": mean(enc_times) * 1000,
        "encaps_std_ms": stdev(enc_times) * 1000,
        "decaps_ms": mean(dec_times) * 1000,
        "decaps_std_ms": stdev(dec_times) * 1000,
    }


def bench_ecdh():
    print()
    print("=" * 60)
    print("ECDH secp256k1 (today's Shielded Bitcoin)")
    print("=" * 60)

    # keygen (both parties)
    kg_times = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        sk_a = ec.generate_private_key(ec.SECP256K1())
        sk_b = ec.generate_private_key(ec.SECP256K1())
        kg_times.append(time.perf_counter() - t0)

    sk_a = ec.generate_private_key(ec.SECP256K1())
    sk_b = ec.generate_private_key(ec.SECP256K1())

    # sender exchange (A computes shared using B's public key)
    enc_times = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        shared_a = sk_a.exchange(ec.ECDH(), sk_b.public_key())
        enc_times.append(time.perf_counter() - t0)

    # recipient exchange (B computes shared using A's public key)
    dec_times = []
    for _ in range(N_RUNS):
        t0 = time.perf_counter()
        shared_b = sk_b.exchange(ec.ECDH(), sk_a.public_key())
        dec_times.append(time.perf_counter() - t0)
        assert shared_a == shared_b

    # serialized sizes
    pk_bytes_compressed = sk_b.public_key().public_bytes(
        encoding=serialization.Encoding.X962,
        format=serialization.PublicFormat.CompressedPoint,
    )
    sizes = {
        "public_key_bytes": len(pk_bytes_compressed),  # 33
        "shared_secret_bytes": len(shared_a),           # 32
        "ciphertext_bytes": len(pk_bytes_compressed),   # ephemeral pk = 33
    }
    print(f"  sizes: {sizes}")
    print(f"  keygen (both): {mean(kg_times)*1000:.3f} ± {stdev(kg_times)*1000:.3f} ms")
    print(f"  ecdh exchange (sender):  {mean(enc_times)*1000:.3f} ± {stdev(enc_times)*1000:.3f} ms")
    print(f"  ecdh exchange (recipient): {mean(dec_times)*1000:.3f} ± {stdev(dec_times)*1000:.3f} ms")
    return {
        "scheme": "ECDH-secp256k1",
        **sizes,
        "keygen_ms": mean(kg_times) * 1000,
        "keygen_std_ms": stdev(kg_times) * 1000,
        "encaps_ms": mean(enc_times) * 1000,
        "encaps_std_ms": stdev(enc_times) * 1000,
        "decaps_ms": mean(dec_times) * 1000,
        "decaps_std_ms": stdev(dec_times) * 1000,
    }


def project_witness(ecdh_res, mlkem_res):
    """Project onto a Shielded Bitcoin note-spend witness.

    Note witness components (from unified_merkle_tree.py, depth=3):
      1 (count) + 4 (output_index) + 32 (h_body)
      + len(pk_eph) + 80 (ct_note) + 32 (h_aux)
      + 256 (zk_proof) + 32 (nullifier) + 32*depth (Merkle path)
    """
    depth = 3
    base = 1 + 4 + 32 + 80 + 32 + 256 + 32 + 32 * depth  # = 533 without pk_eph
    ecdh_wit = base + ecdh_res["ciphertext_bytes"]
    mlkem_wit = base + mlkem_res["ciphertext_bytes"]
    print()
    print("=" * 60)
    print("Projected note-spend witness (depth=3, 8-leaf tree)")
    print("=" * 60)
    print(f"  Base witness (excl. ephemeral pk/ct): {base} B")
    print(f"  ECDH secp256k1 note witness: {ecdh_wit} B")
    print(f"  ML-KEM-1024 note witness:    {mlkem_wit} B")
    print(f"  Delta: +{mlkem_wit - ecdh_wit} B ({(mlkem_wit-ecdh_wit)/ecdh_wit*100:.1f}%)")
    return {
        "base_witness_bytes": base,
        "ecdh_note_witness_bytes": ecdh_wit,
        "mlkem_note_witness_bytes": mlkem_wit,
        "delta_bytes": mlkem_wit - ecdh_wit,
        "delta_pct": round((mlkem_wit - ecdh_wit) / ecdh_wit * 100, 1),
    }


if __name__ == "__main__":
    ecdh = bench_ecdh()
    mlkem = bench_mlkem()
    proj = project_witness(ecdh, mlkem)

    result = {"ecdh": ecdh, "mlkem": mlkem, "projection": proj}
    out = OUT / "mlkem_bench_results.json"
    out.write_text(json.dumps(result, indent=2))
    print(f"\n[written] {out}")
