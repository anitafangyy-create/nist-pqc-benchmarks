#!/usr/bin/env python3
"""QRE 交叉验证实验：同一 TFIM 电路 × pyLIQTR / cirq_ft 双工具。

用法: python3 crosscheck.py   # -> crosscheck_results.json
依赖: pip3 install pyliqtr
"""
from __future__ import annotations

import json
import time
import warnings

warnings.filterwarnings("ignore")

from pyLIQTR.BlockEncodings import VALID_ENCODINGS
from pyLIQTR.BlockEncodings.PauliStringLCU import PauliStringLCU
from pyLIQTR.ProblemInstances.spin_models import Transverse_Field_Ising as TFI
from pyLIQTR.utils.resource_analysis import (
    estimate_resources,
    get_T_counts_from_rotations,
)
from cirq_ft import t_complexity

GATE_PRECISION = 1e-10
CONFIGS = [
    ("TFIM-J1.0", dict(J=1.0, g=-1.0)),
    ("TFIM-J0.5", dict(J=0.5, g=-1.0)),
    ("TFIM-h0.3", dict(J=1.0, g=-1.0, h=0.3)),
]


def run_one(label: str, kw: dict) -> dict:
    inst = TFI(**kw)
    enc = PauliStringLCU(inst)
    resA = estimate_resources(enc)
    tcB = t_complexity(enc)
    t_per_rot = get_T_counts_from_rotations(1, gate_precision=GATE_PRECISION, seed=0)
    b_decomposed = tcB.t + tcB.rotations * t_per_rot
    ratio = resA["T"] / max(tcB.t, 1)
    print(f"[{label}] qubit={inst.n_qubits()} terms={inst.n_terms(VALID_ENCODINGS.PauliLCU)}")
    print(f"  A(pyLIQTR): T={resA['T']} Clifford={resA['Clifford']} LogicalQubits={resA['LogicalQubits']}")
    print(f"  B(cirq_ft): T={tcB.t} Rotations={tcB.rotations} Clifford={tcB.clifford}")
    print(f"  B 按 A 口径分解: T≈{b_decomposed}  与 A 差={abs(b_decomposed - resA['T'])}")
    print(f"  口径差异: {ratio:.1f}×")
    return {
        "instance": label,
        "n_qubits": inst.n_qubits(),
        "n_terms": inst.n_terms(VALID_ENCODINGS.PauliLCU),
        "gate_precision": GATE_PRECISION,
        "toolA_pyliqtr": {
            "T": resA["T"], "Clifford": resA["Clifford"], "LogicalQubits": resA["LogicalQubits"],
        },
        "toolB_cirqft": {
            "T": tcB.t, "Rotations": tcB.rotations, "Clifford": tcB.clifford,
        },
        "B_decomposed_T": int(b_decomposed),
        "raw_T_ratio": round(ratio, 1),
        "attribution": {
            "rotations": tcB.rotations,
            "T_per_rotation_at_%g" % GATE_PRECISION: int(t_per_rot),
        },
    }


def main() -> None:
    t0 = time.time()
    results = []
    for label, kw in CONFIGS:
        try:
            results.append(run_one(label, kw))
        except Exception as exc:  # noqa: BLE001
            print(f"[{label}] 失败: {exc}")
    with open("crosscheck_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n[saved] crosscheck_results.json（总耗时 {time.time()-t0:.1f}s）")


if __name__ == "__main__":
    main()
