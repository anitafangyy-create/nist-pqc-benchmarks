#!/usr/bin/env python3
"""p03_per_angle_synthesis.py — P0-3 逐角度独立合成核算（旋转主导实例）。

审计 P0 核心缺口：QFT/PhaseGradient/QPE-7 的 T 成本此前只能与 pyLIQTR 内置
estimate_resources 成本模型对照（同源自洽，非独立验证）。本脚本把旋转层升级为
两个独立合成器逐角度核算：

  (a) GridSynth  (pygridsynth 2.0.0)：独立 Clifford+T 网格合成算法；
  (b) pyLIQTR rz_decomp：逐门 Ross–Selinger 精确/近似分解路径。

两者都不依赖 pyLIQTR estimate_resources 的内置 c(eps) 成本模型，因此 Σ 逐角度
实际成本是独立实测，可量化内置模型对特殊角（Clifford 角）的系统性高估。

角度来源：直接遍历 cirq 电路构造（algorithms.py 的 _qft / _phase_gradient /
_qpe_circuit），提取每个旋转门的精确 exponent（2/2^d 等为二进制精确 float），
避免任何截断/序列化误差（qpe7_actual_angle_costs.json 中的 7~8 位截断角度会把
Clifford 角误判为通用角，已在冒烟测试证实）。

确定性：GridSynth seed=20261026（与既有 microbenchmark 一致）；rz_decomp
use_random_decomp=False。

输出：p03_per_angle_synthesis.json（逐角度 + 汇总）+ p03_per_angle_synthesis.csv。
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
import types
import warnings

warnings.filterwarnings("ignore")

# ---- import-period stub: cvxpy only backs the unused diamond-norm helper ----
sys.modules.setdefault("cvxpy", types.ModuleType("cvxpy"))

from pygridsynth import gridsynth_circuit
from pygridsynth.config import GridsynthConfig
from pygridsynth.quantum_gate import TGate

from pyLIQTR.gate_decomp.rotation_gates import rz_decomp

import sys as _sys
sys.path.insert(0, ".")
from algorithms import _qft, _phase_gradient, _qpe_circuit, QPE_ANGLES

EPS = 1e-10
SEED = 20261026
C_REF = 103  # 论文锚定 c_cal(1e-10)
OUT_JSON = "p03_per_angle_synthesis.json"
OUT_CSV = "p03_per_angle_synthesis.csv"


def gridsynth_t(theta: float, eps: float) -> int:
    cfg = GridsynthConfig(seed=SEED, verbose=0)
    circ = gridsynth_circuit(theta=theta, epsilon=eps, cfg=cfg)
    return sum(1 for g in circ if isinstance(g, TGate))


def rz_t(theta: float, eps: float) -> int:
    g = rz_decomp(rads=theta, precision=eps, use_random_decomp=False)
    return int(g.get_T_count())


def theta_class(theta: float) -> str:
    """理论 Clifford 分类（基于精确旋转角的等价类）：
    θ ≡ 0 (mod π) -> Z；θ ≡ π/2 (mod π) -> S；θ ≡ π/4 (mod π/2) -> T；
    其余 -> generic。注：π/4 属于 Clifford+T 集的精确可合成角（1 T），
    但 GridSynth 近似合成路径是否识别由合成器决定（见 per-angle 实测）。"""
    half = theta % math.pi
    if abs(half) < 1e-12 or abs(half - math.pi) < 1e-12:
        return "Z"
    if abs(half - math.pi / 2) < 1e-12:
        return "S"
    q = theta % (math.pi / 2)
    if abs(q) < 1e-12 or abs(q - math.pi / 4) < 1e-12:
        return "T"
    return "generic"


def extract_rotations(circ):
    """遍历 cirq 电路，提取全部旋转门 (门名, 相位角 θ)。"""
    import cirq
    rots = []
    for op in circ.all_operations():
        g = op.gate
        if g is None:
            continue
        if isinstance(g, cirq.CZPowGate):
            rots.append(("CZ", math.pi * float(g.exponent)))
        elif isinstance(g, cirq.ZPowGate):
            rots.append(("Rz", math.pi * float(g.exponent)))
    return rots


def build_instances():
    """返回 [(name, circuit, n_rot_expected)]。"""
    import cirq
    import numpy as np
    out = []
    for n in (8, 16):
        c = _qft(n)
        out.append((f"QFT-{n}", c, n * (n - 1) // 2))
    c = _phase_gradient(8)
    out.append(("PhaseGradient-8", c, 8))
    c = _qpe_circuit(6, QPE_ANGLES)
    out.append(("QPE-7", c, 21))
    return out


def main() -> int:
    t0 = time.time()
    instances = []
    rows = []
    for name, circ, n_exp in build_instances():
        rots = extract_rotations(circ)
        # 归一化到 [0, 2π)（旋转等价；GridSynth 对负数/超出范围的输入行为不一致）
        norm = []
        for gname, th in rots:
            th_n = th % (2.0 * math.pi)
            norm.append((gname, th, th_n))
        assert len(norm) == n_exp, f"{name}: expected {n_exp} rotations, got {len(norm)}"
        per_angle = []
        for gname, th_raw, th in norm:
            t_gs = gridsynth_t(th, EPS)
            t_rz = rz_t(th_raw, EPS)
            per_angle.append({
                "gate": gname,
                "theta_raw": round(th_raw, 12),
                "theta_norm": round(th, 12),
                "theta_class": theta_class(th_raw),
                "t_gridsynth": t_gs,
                "t_rz_decomp": t_rz,
            })
            rows.append({
                "instance": name, "gate": gname,
                "theta_raw": round(th_raw, 12), "theta_norm": round(th, 12),
                "theta_class": theta_class(th_raw),
                "t_gridsynth": t_gs, "t_rz_decomp": t_rz,
            })
        sum_gs = sum(r["t_gridsynth"] for r in per_angle)
        sum_rz = sum(r["t_rz_decomp"] for r in per_angle)
        n_z = sum(1 for r in per_angle if r["theta_class"] == "Z")
        n_s = sum(1 for r in per_angle if r["theta_class"] == "S")
        n_t = sum(1 for r in per_angle if r["theta_class"] == "T")
        n_gen = sum(1 for r in per_angle if r["theta_class"] == "generic")
        n_clifford_theory = n_z + n_s + n_t
        instances.append({
            "instance": name,
            "n_rotations": len(per_angle),
            "n_Z": n_z, "n_S": n_s, "n_T": n_t, "n_generic": n_gen,
            "n_clifford_theory": n_clifford_theory,
            "sum_t_gridsynth": sum_gs,
            "sum_t_rz_decomp": sum_rz,
            "model_R_times_103": len(per_angle) * C_REF,
            "c_ref": C_REF,
            "epsilon": EPS,
            "angle_cost_table": per_angle,
        })
        print(f"[{name}] n={len(per_angle)} (Z={n_z},S={n_s},T={n_t},generic={n_gen}) "
              f"sum_GS={sum_gs} sum_rz={sum_rz} R*103={len(per_angle)*C_REF}",
              file=sys.stderr)

    payload = {
        "purpose": "P0-3 per-angle independent synthesis audit for rotation-dominated instances "
                   "(QFT-8/16, PhaseGradient-8, QPE-7): GridSynth + pyLIQTR rz_decomp "
                   "actual per-rotation T counts vs the uniform c(eps)=103 model",
        "epsilon": EPS,
        "gridsynth_seed": SEED,
        "rz_decomp": "pyLIQTR rz_decomp use_random_decomp=False",
        "gridsynth": "pygridsynth 2.0.0 GridSynth",
        "c_ref_model": C_REF,
        "note": "Angles are extracted exactly from the cirq circuit constructions "
                "(CZPowGate exponent e -> phase angle pi*e; normalized to [0,2pi) for "
                "GridSynth, raw sign preserved for rz_decomp). Truncated angle files "
                "are NOT used: smoke tests show 7-8 digit truncation turns Clifford "
                "angles into generic-angle syntheses (~100 T) in GridSynth. The T-class "
                "theta_class is a theoretical Clifford classification; whether each "
                "synthesizer realizes zero cost is measured, not assumed.",
        "instances": instances,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[written] {OUT_JSON} + {OUT_CSV} ({payload['elapsed_s']}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
