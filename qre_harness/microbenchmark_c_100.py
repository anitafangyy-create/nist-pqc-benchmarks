#!/usr/bin/env python3
"""microbenchmark_c_100.py — 扩样独立 c(ε) 旋转合成微基准（100 generic 角度/精度）

对 100 个 generic 角度 Rz(θ) 在四档合成精度 ε ∈ {1e-4, 1e-6, 1e-8, 1e-10}
下调用 pyLIQTR 的 rz_decomp（Ross–Selinger 网格算法）逐个真实合成，
统计每个旋转的 T 门成本分布（mean / std / median / quartiles / p95 / min / max）。

角度集合可复现：固定 RNG 种子，rejection 采样排除特殊角
（Clifford 角 kπ/2、二进角 kπ/2^m (m≤8) 及低精度可精确合成的角度）。

无任何"主案例反推"参与：是论文 c(ε) 校准点的独立测量证据，
且样本量由 10 提升至 100，用于报告置信区间与分位数。

用法：
  .venv-qre/bin/python microbenchmark_c_100.py --out c_microbenchmark_100.json
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
import warnings

warnings.filterwarnings("ignore")

EPSILONS = [1e-4, 1e-6, 1e-8, 1e-10]
N_ANGLES = 100
SEED = 20261026  # 固定种子：角度集合可复现
# 排除半径：接近 Clifford 角 kπ/2 或二进角 kπ/2^m (m ≤ 8) 的角度视为特殊角
_EXCLUDE_TOL = 1e-6


def is_special(rad: float) -> bool:
    """判定角度是否落在可低成本精确合成/Clifford 实现的特殊角附近。

    - Clifford 角：θ ≈ kπ/2（四分之一圈整数倍）
    - 二进角：θ ≈ kπ/2^m, m ≤ 8（低 T 成本网格点）
    - 0 或 π 附近的退化角
    """
    if rad < 1e-4 or abs(rad - math.pi) < 1e-4:
        return True
    for m in range(0, 9):
        step = math.pi / (2 ** m)
        k = round(rad / step)
        if k <= 0:
            continue
        if abs(rad - k * step) < _EXCLUDE_TOL:
            return True
    return False


def generate_angles(n: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    angles: list[float] = []
    while len(angles) < n:
        a = rng.uniform(0.01, math.pi - 0.01)
        if not is_special(a):
            angles.append(a)
    return angles


def t_count_for(angle: float, eps: float) -> int:
    from pyLIQTR.gate_decomp.rotation_gates import rz_decomp
    g = rz_decomp(rads=angle, precision=eps, use_random_decomp=False)
    return int(g.get_T_count())


def summarize(values: list[int]) -> dict:
    q = statistics.quantiles(values, n=4)  # [p25, p50, p75]
    return {
        "n": len(values),
        "mean": round(statistics.mean(values), 2),
        "sd": round(statistics.stdev(values), 2),
        "median": round(statistics.median(values), 2),
        "q25": float(q[0]),
        "q75": float(q[2]),
        "p95": float(sorted(values)[int(math.ceil(0.95 * len(values))) - 1]),
        "min": min(values),
        "max": max(values),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="c_microbenchmark_100.json")
    p.add_argument("--angles-csv", default="calibration_angles.csv")
    p.add_argument("--n", type=int, default=N_ANGLES)
    p.add_argument("--seed", type=int, default=SEED)
    args = p.parse_args()

    angles = generate_angles(args.n, args.seed)
    rows: list[dict] = []
    t0 = time.time()
    for eps in EPSILONS:
        counts: list[int] = []
        for i, a in enumerate(angles):
            t1 = time.time()
            c = t_count_for(a, eps)
            elapsed = time.time() - t1
            counts.append(c)
            rows.append({"epsilon": eps, "angle": a, "t_per_rotation": c})
            if (i + 1) % 25 == 0:
                print(f"  eps={eps:.0e} {i+1}/{len(angles)} angles "
                      f"({elapsed:.2f}s last)", file=sys.stderr)
        s = summarize(counts)
        approx = 3.0 * math.log2(1.0 / eps)
        print(f"[eps={eps:.0e}] {s} 3log2(1/eps)={approx:.2f}", file=sys.stderr)

    summary = {str(e): summarize([r["t_per_rotation"] for r in rows if r["epsilon"] == e])
               for e in EPSILONS}
    payload = {
        "method": "pyLIQTR rz_decomp single-rotation synthesis (Ross–Selinger grid)",
        "n_angles_per_precision": args.n,
        "angle_seed": args.seed,
        "special_angle_exclusion": f"Clifford k*pi/2 and dyadic k*pi/2^m (m<=8), tol {_EXCLUDE_TOL}",
        "epsilons": EPSILONS,
        "note": "independent microbenchmark, expanded sample; not derived from any circuit totals",
        "rows": rows,
        "summary": summary,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)

    with open(args.angles_csv, "w") as f:
        f.write("angle_rad\n")
        for a in angles:
            f.write(f"{a:.12f}\n")
    print(f"[written] {args.out} + {args.angles_csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
