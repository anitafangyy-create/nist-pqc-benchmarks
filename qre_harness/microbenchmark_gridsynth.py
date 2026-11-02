#!/usr/bin/env python3
"""microbenchmark_gridsynth.py — 第二独立合成器（GridSynth / pygridsynth 2.0.0）对照微基准。

审稿 Q1 最高优先建议：在冻结角度集上，对同一批通用角度与四档精度，并列记录三列
实际/估计每旋转 T-count：
  (a) pyLIQTR 内置成本模型估计：model(ε) = 3.02·log2(1/ε) + 0.77（论文 Table 10 自述公式）；
  (b) pyLIQTR rz_decomp 实际 Ross–Selinger 分解（与 c_microbenchmark_100.json 同源同角度）；
  (c) GridSynth (pygridsynth) 实际 Clifford+T 分解（独立合成算法，非 pyLIQTR 代码库）。

逐角度 (b) vs (c) 计算 MAE / RMSE / MAPE；分层报告均值、离散度与最大偏差角度。
校准常数不参与回拟合：本脚本只做并列测量与描述统计，不反推任何 c(ε) 常数。

确定性：角度集来自 calibration_angles.csv（seed 20261026）；GridSynth seed 固定 20261026。

说明：pygridsynth 的 mixed-synthesis diamond-norm 工具模块在 import 期引入 cvxpy，
但标准 Z 轴 GridSynth 综合路径不调用该模块；此处用空模块 stub 满足 import 期，
不调用任何 SDP 求解器，不影响 T-count 输出。

用法：
  ../.venv-qre/bin/python microbenchmark_gridsynth.py
"""
from __future__ import annotations

import csv
import json
import math
import statistics
import sys
import time
import types
import warnings

warnings.filterwarnings("ignore")

# ---- import-period stub: cvxpy only backs the unused diamond-norm helper -------------
sys.modules.setdefault("cvxpy", types.ModuleType("cvxpy"))

from pygridsynth import gridsynth_circuit
from pygridsynth.config import GridsynthConfig
from pygridsynth.quantum_gate import TGate

from pyLIQTR.gate_decomp.rotation_gates import rz_decomp

EPSILONS = [1e-4, 1e-6, 1e-8, 1e-10]
SEED = 20261026
# pyLIQTR built-in cost-model formula reported in Table 10 (Gaussian sample)
MODEL_SLOPE = 3.02
MODEL_INTERCEPT = 0.77

ANGLES_CSV = "calibration_angles.csv"
OUT_JSON = "gridssynth_microbenchmark.json"
OUT_CSV = "gridssynth_per_angle.csv"


def model_estimate(eps: float) -> float:
    return MODEL_SLOPE * math.log2(1.0 / eps) + MODEL_INTERCEPT


def gridsynth_t(angle: float, eps: float) -> int:
    cfg = GridsynthConfig(seed=SEED, verbose=0)
    circ = gridsynth_circuit(theta=angle, epsilon=eps, cfg=cfg)
    return sum(1 for g in circ if isinstance(g, TGate))


def rz_t(angle: float, eps: float) -> int:
    g = rz_decomp(rads=angle, precision=eps, use_random_decomp=False)
    return int(g.get_T_count())


def summarize(values: list[int]) -> dict:
    q = statistics.quantiles(values, n=4)
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 3),
        "sd": round(statistics.stdev(values), 3),
        "median": statistics.median(values),
        "q25": round(q[0], 2),
        "q75": round(q[2], 2),
        "p95": sorted(values)[int(math.ceil(0.95 * len(values))) - 1],
        "min": min(values),
        "max": max(values),
    }


def main() -> int:
    angles = []
    with open(ANGLES_CSV) as f:
        for row in csv.DictReader(f):
            angles.append(float(row["angle_rad"]))
    print(f"loaded {len(angles)} frozen angles", file=sys.stderr)

    rows = []
    t0 = time.time()
    for eps in EPSILONS:
        for i, a in enumerate(angles):
            t_gs = gridsynth_t(a, eps)
            t_rz = rz_t(a, eps)
            rows.append({
                "epsilon": eps,
                "angle": a,
                "t_model": round(model_estimate(eps), 2),
                "t_rz_decomp": t_rz,
                "t_gridsynth": t_gs,
                "delta_gs_minus_rz": t_gs - t_rz,
            })
            if (i + 1) % 25 == 0:
                print(f"  eps={eps:.0e} {i+1}/{len(angles)}", file=sys.stderr)

    # ---- per-precision comparison statistics (c) vs (b) actual decompositions ----
    summary = {}
    for eps in EPSILONS:
        sub = [r for r in rows if r["epsilon"] == eps]
        gs = [r["t_gridsynth"] for r in sub]
        rz = [r["t_rz_decomp"] for r in sub]
        diffs = [r["delta_gs_minus_rz"] for r in sub]
        abs_err = [abs(d) for d in diffs]
        mape = 100.0 * statistics.mean(abs(d) / b for d, b in zip(diffs, rz))
        rmse = math.sqrt(statistics.mean(d * d for d in diffs))
        worst = max(sub, key=lambda r: abs(r["delta_gs_minus_rz"]))
        summary[str(eps)] = {
            "model_estimate_mean": round(model_estimate(eps), 3),
            "rz_decomp": summarize(rz),
            "gridsynth": summarize(gs),
            "gs_minus_rz": {
                "MAE": round(statistics.mean(abs_err), 3),
                "RMSE": round(rmse, 3),
                "MAPE_pct": round(mape, 3),
                "mean_bias_gs_minus_rz": round(statistics.mean(diffs), 3),
                "mean_bias_pct_vs_rz": round(100.0 * (statistics.mean(gs) - statistics.mean(rz))
                                             / statistics.mean(rz), 3),
                "max_abs_diff": max(abs_err),
                "worst_angle": round(worst["angle"], 12),
                "worst_gs": worst["t_gridsynth"],
                "worst_rz": worst["t_rz_decomp"],
            },
            "model_vs_actuals": {
                "model_vs_rz_mean_bias_pct": round(100.0 * (model_estimate(eps) - statistics.mean(rz))
                                                   / statistics.mean(rz), 3),
                "model_vs_gs_mean_bias_pct": round(100.0 * (model_estimate(eps) - statistics.mean(gs))
                                                   / statistics.mean(gs), 3),
            },
        }

    payload = {
        "purpose": "second independent synthesizer (GridSynth) actual T-count vs pyLIQTR "
                   "rz_decomp actual T-count vs built-in model estimate, on the frozen 100-angle set",
        "angle_seed": SEED,
        "gridsynth_seed": SEED,
        "n_angles_per_precision": len(angles),
        "epsilons": EPSILONS,
        "synthesizer_c": "pygridsynth 2.0.0 GridSynth (independent Clifford+T grid synthesis)",
        "synthesizer_b": "pyLIQTR rz_decomp (Ross-Selinger grid, use_random_decomp=False)",
        "model_a_formula": f"model = {MODEL_SLOPE}*log2(1/eps) + {MODEL_INTERCEPT} (built-in cost model)",
        "note": "descriptive comparison only; no calibration constant is refit against these outputs. "
                "rz_decomp and GridSynth counts are paired in the same process on identical angle values; "
                "per-angle rz counts may move by +/-2 T across runs near a grid cell boundary due to floating "
                "tail and gmpy2 precision context, while the distribution mean is stable (<0.3% vs frozen "
                "c_microbenchmark_100.json); inference therefore uses paired MAE/RMSE/MAPE and distribution "
                "means, not exact per-angle reproducibility.",
        "summary": summary,
        "rows": rows,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    # console digest
    print("\n=== per-precision digest (GS vs rz actual decomposition) ===")
    for eps in EPSILONS:
        s = summary[str(eps)]
        print(f"eps={eps:.0e} model={s['model_estimate_mean']:.1f} "
              f"rz_mean={s['rz_decomp']['mean']:.2f} gs_mean={s['gridsynth']['mean']:.2f} "
              f"MAE={s['gs_minus_rz']['MAE']:.3f} RMSE={s['gs_minus_rz']['RMSE']:.3f} "
              f"MAPE={s['gs_minus_rz']['MAPE_pct']:.3f}% bias={s['gs_minus_rz']['mean_bias_pct_vs_rz']:.2f}%")
    print(f"[written] {OUT_JSON} + {OUT_CSV} ({payload['elapsed_s']}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
