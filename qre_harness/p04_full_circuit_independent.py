#!/usr/bin/env python3
"""p04_full_circuit_independent.py — P0-2 整电路独立合成核算（审计最关键建议的本地落地）。

审计 P0-2 要求的实验：两个独立合成器对相同完整电路实际分解，比较最终 T-count。
在不安装 Rust GridSynth 原生栈的既有决策下，本脚本以"完整电路级独立流水线"实现：
  独立流水线 = Toffoli→7T 基础计数（电路门枚举）+ 每个旋转门独立合成（GridSynth / rz_decomp）
两者都不依赖 pyLIQTR estimate_resources 的内置 c(eps) 模型，因此整电路 T 计数
T_indep = 7·n_Toffoli + Σ c(θᵢ, ε) 是与工具 A/B 独立的第三视角。

覆盖审计建议的电路集：
  - QFT-8/16      （旋转主导，Clifford H + dyadic 角）
  - QPE-7         （旋转主导，Clifford H/SWAP + oracle 角 + iQFT dyadic 角）
  - PhaseGradient-8（Clifford H + 重复 dyadic 角）
  - Adder/Comparator/ANDTree（Toffoli 主导，R=0）
  - Hybrid（Adder-8 ∥ QFT-8 并行组合 = Clifford + T + generic rotation 混合）
纯 cirq 构造，门类型可完整枚举，无需 pyLIQTR 内部表示。

注意：这是"旋转层独立合成 + Toffoli 标准 7T 分解"的端到端计数，未做跨门优化
（Δ_opt 未纳入，与 Model C 的 compiled 结果仍有差距），论文如实披露。
"""
from __future__ import annotations

import csv
import json
import math
import random
import sys
import time
import types
import warnings

warnings.filterwarnings("ignore")
sys.modules.setdefault("cvxpy", types.ModuleType("cvxpy"))

from pygridsynth import gridsynth_circuit
from pygridsynth.config import GridsynthConfig
from pygridsynth.quantum_gate import TGate
from pyLIQTR.gate_decomp.rotation_gates import rz_decomp

sys.path.insert(0, ".")
from algorithms import (_qft, _phase_gradient, _qpe_circuit, QPE_ANGLES,
                        _cuccaro_adder, _comparator, _and_tree)

EPS = 1e-10
SEED = 20261026
C_REF = 103
TOF_T = 7

# rz_decomp 的 diophantine 求解器使用 Python random.randint（默认系统熵播种），
# 未固定 seed 时同一角度 T 计数在进程间波动；每次 rz 调用前固定 random seed，
# 保证同一角度确定性输出且与调用顺序无关（与 p03_per_angle_synthesis.py 同约定）。
OUT_JSON = "p04_full_circuit_independent.json"
OUT_CSV = "p04_full_circuit_independent.csv"


def gridsynth_t(theta: float, eps: float) -> int:
    cfg = GridsynthConfig(seed=SEED, verbose=0)
    circ = gridsynth_circuit(theta=theta, epsilon=eps, cfg=cfg)
    return sum(1 for g in circ if isinstance(g, TGate))


def rz_t(theta: float, eps: float) -> int:
    random.seed(SEED)  # 固定 diophantine 求解的 random 源，保证可复现（见文件头注释）
    g = rz_decomp(rads=theta, precision=eps, use_random_decomp=False)
    return int(g.get_T_count())


def analyze_circuit(name: str, circ, n_qubits: int) -> dict:
    """遍历电路：Toffoli→7T；CZPowGate/ZPowGate→旋转合成；其余 Clifford→0。"""
    import cirq
    n_tof = 0
    rots = []
    other = {}
    for op in circ.all_operations():
        g = op.gate
        if g is None:
            other.setdefault(str(op), other.get(str(op), 0) + 1)
            continue
        if isinstance(g, cirq.TOFFOLI.__class__) or type(g).__name__ in ("CCXPauliGate", "Toffoli"):
            n_tof += 1
        elif isinstance(g, cirq.CZPowGate):
            rots.append(("CZ", math.pi * float(g.exponent)))
        elif isinstance(g, cirq.ZPowGate):
            rots.append(("Rz", math.pi * float(g.exponent)))
        elif isinstance(g, (cirq.HPowGate, cirq.CNotPowGate, cirq.SwapPowGate,
                            cirq.XPowGate, cirq.YPowGate, cirq.ZPowGate)):
            pass  # Clifford/单比特 Pauli，0 T
        else:
            other.setdefault(type(g).__name__, other.get(type(g).__name__, 0) + 1)

    sum_gs = sum(gridsynth_t(th % (2 * math.pi), EPS) for _, th in rots)
    sum_rz = sum(rz_t(th, EPS) for _, th in rots)
    t_base = n_tof * TOF_T
    return {
        "instance": name,
        "n_qubits": n_qubits,
        "n_toffoli": n_tof,
        "t_base_tof": t_base,
        "n_rotations": len(rots),
        "sum_t_gridsynth_rot": sum_gs,
        "sum_t_rz_rot": sum_rz,
        "t_indep_gridsynth": t_base + sum_gs,
        "t_indep_rz_decomp": t_base + sum_rz,
        "unconsumed_gates": other,
        "angle_costs": [{"gate": gn, "theta_raw": round(th, 12), "theta_norm": round(th % (2 * math.pi), 12),
                         "t_gs": gridsynth_t(th % (2 * math.pi), EPS), "t_rz": rz_t(th, EPS)} for gn, th in rots],
    }


def main() -> int:
    t0 = time.time()
    import cirq

    # 电路集
    circuits = []
    for n in (8, 16):
        circuits.append((f"QFT-{n}", _qft(n), n))
    circuits.append(("PhaseGradient-8", _phase_gradient(8), 8))
    circuits.append(("QPE-7", _qpe_circuit(6, QPE_ANGLES), 7))
    circuits.append(("Adder-8", _cuccaro_adder(8), 17))
    circuits.append(("Adder-16", _cuccaro_adder(16), 33))
    circuits.append(("Comparator-8", _comparator(8), 17))
    circuits.append(("Comparator-16", _comparator(16), 33))
    circuits.append(("ANDTree-8", _and_tree(8), 15))
    # Hybrid：Adder-8 ∥ QFT-8 并行组合（25 qubit，Clifford+T+generic rotation 混合）
    adder = _cuccaro_adder(8)
    qft8 = _qft(8)
    off = 17
    qft_off = cirq.Circuit(op.gate.on(*(q + off for q in op.qubits)) for op in qft8.all_operations())
    hybrid = cirq.Circuit([*adder.all_operations(), *qft_off.all_operations()])
    circuits.append(("Hybrid(Adder-8∥QFT-8)", hybrid, 25))

    instances = []
    rows = []
    for name, circ, nq in circuits:
        r = analyze_circuit(name, circ, nq)
        instances.append(r)
        for a in r["angle_costs"]:
            rows.append({"instance": name, **{k: a[k] for k in ("gate", "theta_raw", "theta_norm", "t_gs", "t_rz")}})
        print(f"[{name}] tof={r['n_toffoli']} rot={r['n_rotations']} "
              f"T_indep_GS={r['t_indep_gridsynth']} T_indep_rz={r['t_indep_rz_decomp']} "
              f"unconsumed={r['unconsumed_gates']}", file=sys.stderr)

    # 对照 p02 矩阵（工具 A pyLIQTR 观察值 / B 模型预测）
    try:
        matrix = json.load(open("p02_circuit_matrix.json"))
        obs = {}
        for inst in matrix.get("instances", []):
            obs[inst["instance"]] = {
                "T_observed_pyliqtr": inst.get("T_observed_pyliqtr"),
                "T_predicted_model": inst.get("T_predicted"),
                "T_base_B": inst.get("T_base"),
                "R_B": inst.get("R"),
            }
    except Exception as e:  # noqa: BLE001
        print("p02 matrix unavailable:", e, file=sys.stderr)
        obs = {}
    for r in instances:
        m = obs.get(r["instance"])
        if m:
            r.update(m)
            for key, val in (("t_indep_gridsynth", r["t_indep_gridsynth"]),
                             ("t_indep_rz_decomp", r["t_indep_rz_decomp"])):
                if isinstance(m.get("T_observed_pyliqtr"), (int, float)):
                    r[f"delta_{key}_pct"] = round(100 * (val - m["T_observed_pyliqtr"]) / m["T_observed_pyliqtr"], 1)

    payload = {
        "purpose": "P0-2 full-circuit independent synthesis: T_indep = 7*n_Toffoli + sum of per-angle "
                   "synthesis (GridSynth / pyLIQTR rz_decomp), vs pyLIQTR estimate_resources (A) and "
                   "the T_base + R*c(eps) model (B). Independent third view; no cross-gate optimization.",
        "epsilon": EPS,
        "gridsynth_seed": SEED,
        "toffoli_T": TOF_T,
        "c_ref": C_REF,
        "note": "All circuits are pure cirq constructions whose gate set is fully enumerable. "
                "Clifford gates (H, CNOT, SWAP, X) contribute 0 T. Angles extracted exactly from "
                "circuit (CZPowGate/ZPowGate exponent e -> phase pi*e), normalized to [0,2pi) for "
                "GridSynth. No cross-gate optimization (Delta_opt) is applied.",
        "instances": instances,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"[written] {OUT_JSON} + {OUT_CSV} ({payload['elapsed_s']}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
