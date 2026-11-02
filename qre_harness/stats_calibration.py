#!/usr/bin/env python3
"""stats_calibration.py — §5.2 统计增强：log₂ 线性拟合 + 重采样置信区间

基于 c_microbenchmark_100.json 的已存实测（400 行）：

1. 经验 log₂ 关系拟合：OLS 拟合 c̄(ε) ~ a·log₂(1/ε) + b，报告斜率、截距、
   R²、每个精度点的残差与拟合区间（4 个精度点，说明自由度为 2 的局限）。
2. 重采样置信区间：按角度 bootstrap（B=2000，固定种子，分层每精度重采样）
   报告 c̄(ε) 的 95% 百分位 CI，避免把旋转当作完全独立样本的错误解读
   （保留按电路/实例分组重采样的说明）。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics


def ols(xs: list[float], ys: list[float]):
    n = len(xs)
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    intercept = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot else 0.0
    resid = [y - (slope * x + intercept) for x, y in zip(xs, ys)]
    return slope, intercept, r2, resid


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="stats_calibration.json")
    p.add_argument("--seed", type=int, default=20261026)
    p.add_argument("--bootstrap", type=int, default=2000)
    args = p.parse_args()

    with open("c_microbenchmark_100.json") as f:
        mb = json.load(f)
    rows = mb["rows"]
    epsilons = mb["epsilons"]

    # 1) 拟合：x = log2(1/eps), y = 每精度均值
    xs = [math.log2(1.0 / e) for e in epsilons]
    means = []
    for e in epsilons:
        v = [r["t_per_rotation"] for r in rows if abs(r["epsilon"] - e) < 1e-12]
        means.append(statistics.mean(v))
    slope, intercept, r2, resid = ols(xs, means)

    # 2) 分层 bootstrap CI（按角度重采样）
    rng = random.Random(args.seed)
    per_eps = {e: [r["t_per_rotation"] for r in rows if abs(r["epsilon"] - e) < 1e-12]
               for e in epsilons}
    n = len(per_eps[epsilons[0]])
    ci = {}
    for e in epsilons:
        means_bs = []
        for _ in range(args.bootstrap):
            sample = [rng.choice(per_eps[e]) for _ in range(n)]
            means_bs.append(statistics.mean(sample))
        means_bs.sort()
        lo = means_bs[int(0.025 * args.bootstrap)]
        hi = means_bs[int(0.975 * args.bootstrap) - 1]
        ci[str(e)] = {
            "mean": round(statistics.mean(per_eps[e]), 3),
            "ci95_lo": round(lo, 3),
            "ci95_hi": round(hi, 3),
            "halfwidth": round((hi - lo) / 2, 3),
        }

    payload = {
        "method": "OLS fit of mean rotation cost vs log2(1/eps) + stratified bootstrap CI "
                  "(resampling angles within each precision)",
        "fit_points": 4,
        "fit_degrees_of_freedom": 2,
        "slope": round(slope, 4),
        "intercept": round(intercept, 4),
        "r2": round(r2, 4),
        "residuals": {str(e): round(r, 4) for e, r in zip(epsilons, resid)},
        "fit_interval": f"eps in [{min(epsilons)}, {max(epsilons)}], i.e. log2(1/eps) in "
                        f"[{min(xs):.1f}, {max(xs):.1f}]",
        "ci95_per_precision": ci,
        "caveat": "bootstrap resamples angles; if rotations within one circuit are correlated, "
                  "circuit/instance-level resampling is required and would widen these intervals",
        "seed": args.seed,
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
