#!/usr/bin/env python3
"""ablation_mixed_precision.py — 实验 C-C：逐旋转成本求和 vs 统一平均成本预测

基于 c_microbenchmark_100.json 的已存实测角度成本（400 行），
构造 R=128 旋转的"合成电路"场景并做三类误差分解：

1. 逐旋转求和 Σcᵢ（蒙特卡洛抽样 128 个实测角度成本，2000 组）——
   模拟"精确计数分解"的分布；
2. 统一平均成本预测 R·c̄（c̄=101.06，即论文 Table 5 所用冻结值）——
   预测值本身是确定数；
3. 混合精度场景：64 个旋转用 ε=1e-8 的成本、64 个旋转用 ε=1e-10 的成本
   逐旋转求和 vs 用 ε=1e-10 的统一 c̄ 预测（检验"精度统一"假设失效时的偏差方向）。

所有输入均为已存实测数据；不含任何电路级工具重跑。
本脚本输出的误差分解用于检验 §3.3 假设表中"角度成本可由均值表示"
与"精度统一"两条假设在多大范围内成立。
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="ablation_mixed_precision.json")
    p.add_argument("--seed", type=int, default=20261026)
    p.add_argument("--n-mc", type=int, default=2000)
    args = p.parse_args()

    with open("c_microbenchmark_100.json") as f:
        mb = json.load(f)
    rows = mb["rows"]

    c8 = [r["t_per_rotation"] for r in rows if abs(r["epsilon"] - 1e-8) < 1e-12]
    c10 = [r["t_per_rotation"] for r in rows if abs(r["epsilon"] - 1e-10) < 1e-12]
    mean10 = statistics.mean(c10)   # ≈101.06, 与 run_heldout 冻结值一致
    mean8 = statistics.mean(c8)

    rng = random.Random(args.seed)
    R = 128

    # 1. 统一精度 (ε=1e-10) 逐旋转求和 vs R·c̄
    sums10 = []
    for _ in range(args.n_mc):
        sample = [rng.choice(c10) for _ in range(R)]
        sums10.append(sum(sample))
    mc_mean10 = statistics.mean(sums10)
    mc_sd10 = statistics.stdev(sums10)
    pred10 = R * mean10
    err_mean10 = mc_mean10 - pred10  # 期望 ≈ 0（同一分布，仅抽样噪声）

    # 2. 混合精度：64 旋转 @1e-8 + 64 旋转 @1e-10，逐旋转求和
    sums_mix = []
    for _ in range(args.n_mc):
        s = sum(rng.choice(c8) for _ in range(R // 2)) + \
            sum(rng.choice(c10) for _ in range(R // 2))
        sums_mix.append(s)
    mc_mean_mix = statistics.mean(sums_mix)
    mc_sd_mix = statistics.stdev(sums_mix)
    err_mix_vs_pred10 = mc_mean_mix - pred10   # 统一 1e-10 预测会高估
    err_mix_vs_pred8 = mc_mean_mix - (R * mean8)

    payload = {
        "method": "Monte-Carlo error decomposition on stored rz_decomp angle costs "
                  "(c_microbenchmark_100.json), R=128 rotations",
        "R": R,
        "n_mc": args.n_mc,
        "seed": args.seed,
        "inputs": {
            "mean_c(1e-10)": round(mean10, 4),
            "mean_c(1e-8)": round(mean8, 4),
            "sd_c(1e-10)": round(statistics.stdev(c10), 4),
        },
        "uniform_1e-10": {
            "sum_mean": round(mc_mean10, 3),
            "sum_sd": round(mc_sd10, 3),
            "pred_Rcbar": round(pred10, 3),
            "bias_sum_vs_pred": round(err_mean10, 3),
        },
        "mixed_precision_64x1e-8_64x1e-10": {
            "sum_mean": round(mc_mean_mix, 3),
            "sum_sd": round(mc_sd_mix, 3),
            "bias_vs_uniform_1e-10_pred": round(err_mix_vs_pred10, 3),
            "bias_vs_uniform_1e-8_pred": round(err_mix_vs_pred8, 3),
            "note": "negative bias vs 1e-10 pred means uniform-fine-precision overestimates "
                    "a coarser-mixed circuit; positive vs 1e-8 pred means uniform-coarse "
                    "underestimates",
        },
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
