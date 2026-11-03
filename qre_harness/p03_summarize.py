#!/usr/bin/env python3
"""p03_summarize.py — P0-3 逐角度独立合成核算汇总（论文口径对照）。

把 p03_per_angle_synthesis.json 的逐角度双合成器实测与论文既有读数对照：
  - pyLIQTR 全电路实测（p02_circuit_matrix.json 的 T_observed_pyliqtr；QPE-7 族外取 2163）
  - 论文模型预测 T_base + R*c_cal(1e-10)=103（p02 矩阵 T_predicted）
  - 两个独立合成器逐角度总和 Σ_gridsynth / Σ_rz_decomp
输出每实例系统偏差（独立实测 vs pyLIQTR 内置模型读数），并给出角度类别构成。
"""
from __future__ import annotations

import json
import math

IN_SYNTH = "p03_per_angle_synthesis.json"
IN_MATRIX = "p02_circuit_matrix.json"
OUT = "p03_summary.json"

QPE7_PYLIQTR_T = 2163  # 族外 QPE-7：A 工具全电路读数（heldout 矩阵，= R*103）


def pct(diff, base):
    return round(100.0 * diff / base, 1)


def main() -> int:
    syn = json.load(open(IN_SYNTH))
    mat = json.load(open(IN_MATRIX))
    matrix = {inst["instance"]: inst for inst in mat["instances"]}

    per = []
    for inst in syn["instances"]:
        name = inst["instance"]
        if name in matrix:
            pyliqtr_obs = int(matrix[name]["T_observed_pyliqtr"])
            model_pred = int(matrix[name]["T_predicted"])
            regime = matrix[name]["regime"]
        else:  # QPE-7 族外
            pyliqtr_obs = QPE7_PYLIQTR_T
            model_pred = QPE7_PYLIQTR_T
            regime = "out-of-family"
        sg = inst["sum_t_gridsynth"]
        rz = inst["sum_t_rz_decomp"]
        # 系统偏差：pyLIQTR 内置模型读数 vs 独立合成器逐角度实测总和
        per.append({
            "instance": name,
            "n_rotations": inst["n_rotations"],
            "clifford_theory": inst["n_clifford_theory"],
            "n_Z": inst["n_Z"], "n_S": inst["n_S"], "n_T": inst["n_T"],
            "n_generic": inst["n_generic"],
            "pyliqtr_full_circuit_T": pyliqtr_obs,
            "model_T_base_plus_Rc": model_pred,
            "sum_t_gridsynth": sg,
            "sum_t_rz_decomp": rz,
            "pyliqtr_vs_gridsynth_pct": pct(pyliqtr_obs - sg, sg),
            "pyliqtr_vs_rz_pct": pct(pyliqtr_obs - rz, rz),
            "model_vs_gridsynth_pct": pct(model_pred - sg, sg),
            "model_vs_rz_pct": pct(model_pred - rz, rz),
            "regime": regime,
        })

    payload = {
        "purpose": "P0-3 summary: independent per-angle synthesis totals vs pyLIQTR built-in "
                   "model full-circuit counts, on rotation-dominated instances",
        "epsilon": syn["epsilon"],
        "c_ref": syn["c_ref_model"],
        "gridsynth": syn["gridsynth"],
        "rz_decomp": syn["rz_decomp"],
        "headline": {
            "rz_decomp_scope_overestimate": {
                "QFT-8": per[0]["pyliqtr_vs_rz_pct"],
                "QFT-16": per[1]["pyliqtr_vs_rz_pct"],
                "QPE-7": per[3]["pyliqtr_vs_rz_pct"],
            },
            "gridsynth_scope_overestimate": {
                "QFT-8": per[0]["pyliqtr_vs_gridsynth_pct"],
                "QFT-16": per[1]["pyliqtr_vs_gridsynth_pct"],
                "QPE-7": per[3]["pyliqtr_vs_gridsynth_pct"],
            },
            "phase_gradient_near_agreement_rz_pct": per[2]["pyliqtr_vs_rz_pct"],
            "note": "pyLIQTR full-circuit counts include every CZPowGate/Rz at the uniform "
                    "c(eps)=103 rate; independent per-angle synthesis assigns ~0 T to Z/S "
                    "Clifford angles and a synthesizer-dependent cost to pi/4 (rz_decomp=0, "
                    "GridSynth~136). Scope differences are therefore dominated by Clifford "
                    "angles within the rotation set, not by generic-angle synthesis costs.",
        },
        "instances": per,
    }
    with open(OUT, "w") as f:
        json.dump(payload, f, indent=2)
    print("=== P0-3 digest ===")
    for p in per:
        print(f"{p['instance']:<16} n={p['n_rotations']:>3} "
              f"clifford={p['clifford_theory']:>2} (Z{p['n_Z']} S{p['n_S']} T{p['n_T']} gen{p['n_generic']}) "
              f"pyliqtr={p['pyliqtr_full_circuit_T']:>5} GS={p['sum_t_gridsynth']:>5} "
              f"rz={p['sum_t_rz_decomp']:>5} | pyliqtr-vs-GS {p['pyliqtr_vs_gridsynth_pct']:>6}% "
              f"pyliqtr-vs-rz {p['pyliqtr_vs_rz_pct']:>6}%")
    print(f"[written] {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
