#!/usr/bin/env python3
"""ablation_special_angles.py — 实验 C-D：特殊角度 vs 通用角的旋转合成成本

对 Clifford 角、二进角、接近特殊角的小扰动角、以及通用角（对照），
在合成精度 ε = 1e-10（论文 c̄ 预测所用精度）下逐个真实调用
pyLIQTR rz_decomp（Ross–Selinger 网格），记录每旋转 T 门成本。

目的：检验"平均成本模型"的适用边界——特殊角（Clifford/二进）成本显著低于
通用角均值 101.06 时，统一 c̄ 预测会在含特殊角的电路上系统高估。

用法：
  .venv-qre/bin/python ablation_special_angles.py --out ablation_special_angles.json
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time
import warnings

warnings.filterwarnings("ignore")

EPS = 1e-10


def t_count_for(angle: float, eps: float) -> int:
    from pyLIQTR.gate_decomp.rotation_gates import rz_decomp
    g = rz_decomp(rads=angle, precision=eps, use_random_decomp=False)
    return int(g.get_T_count())


def build_cases() -> list[dict]:
    cases = []
    # Clifford 角：θ = kπ/2
    for k in (0, 1, 2):
        cases.append({"family": "clifford", "label": f"k={k} (θ={k}π/2)", "angle": k * math.pi / 2})
    # 二进角：θ = π/2^m, m = 2..8
    for m in range(2, 9):
        cases.append({"family": "dyadic", "label": f"π/2^{m}", "angle": math.pi / (2 ** m)})
    # 接近特殊角（扰动 1e-3 rad）
    for base, name in [(math.pi / 4, "π/4"), (math.pi / 8, "π/8")]:
        cases.append({"family": "near-special", "label": f"{name}+1e-3", "angle": base + 1e-3})
    return cases


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="ablation_special_angles.json")
    p.add_argument("--csv", default="ablation_special_angles.csv")
    args = p.parse_args()

    cases = build_cases()
    rows = []
    t0 = time.time()
    for c in cases:
        tc = t_count_for(c["angle"], EPS)
        rows.append({"family": c["family"], "label": c["label"],
                     "angle_rad": round(c["angle"], 12), "epsilon": EPS, "t_per_rotation": tc})
        print(f"  {c['family']:>13} {c['label']:>12} -> {tc} T", file=sys.stderr)

    # 通用角对照（来自 c_microbenchmark_100.json 的已存实测，非本次重跑）
    with open("c_microbenchmark_100.json") as f:
        mb = json.load(f)
    generic = [r["t_per_rotation"] for r in mb["rows"] if r["epsilon"] == EPS]
    payload = {
        "method": "pyLIQTR rz_decomp single-rotation synthesis, special vs generic angles",
        "epsilon": EPS,
        "note": "generic-mean reference taken from c_microbenchmark_100.json (n=100, seed 20261026); "
                "special-angle counts are fresh rz_decomp executions at the same precision",
        "generic_mean": round(statistics.mean(generic), 2),
        "generic_sd": round(statistics.stdev(generic), 2),
        "generic_min": min(generic),
        "rows": rows,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    with open(args.csv, "w") as f:
        f.write("family,label,angle_rad,epsilon,t_per_rotation\n")
        for r in rows:
            f.write(f"{r['family']},{r['label']},{r['angle_rad']},{r['epsilon']},{r['t_per_rotation']}\n")
    print(f"[written] {args.out} + {args.csv}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
