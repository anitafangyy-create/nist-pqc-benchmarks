#!/usr/bin/env python3
"""microbenchmark_c.py — 独立 c(ε) 旋转合成微基准（单旋转合成测量）

对多个 generic 角度 Rz(θ) 在四档合成精度 ε ∈ {1e-4, 1e-6, 1e-8, 1e-10}
下调用 pyLIQTR 的 rz_decomp（Ross–Selinger 网格算法）逐个合成，
统计每个旋转的 T 门成本分布（mean / std / min / max / n）。

输出 JSON 与 CSV 两种记录；无任何"主案例反推"参与，
是论文 §3.3 c(ε) 校准点的独立测量证据。

用法：
  .venv-qre/bin/python microbenchmark_c.py --out c_microbenchmark.json
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

EPSILONS = [1e-4, 1e-6, 1e-8, 1e-10]
# generic 角度（避开 π/2、π/4、π/8 等可 Clifford 实现的特殊角）
ANGLES = [
    0.1234567,
    0.31415926,
    0.52359877,
    0.69314718,
    0.87396487,
    1.04719755,
    1.25663706,
    1.57079632 + 0.01,
    1.81379809,
    2.19911486,
]


def t_count_for(angle: float, eps: float) -> int:
    from pyLIQTR.gate_decomp.rotation_gates import rz_decomp
    g = rz_decomp(rads=angle, precision=eps, use_random_decomp=False)
    return int(g.get_T_count())


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="c_microbenchmark.json")
    p.add_argument("--angles", default=",".join(map(str, ANGLES)))
    args = p.parse_args()

    angles = [float(a) for a in args.angles.split(",")]
    rows: list[dict] = []
    t0 = time.time()
    for eps in EPSILONS:
        counts: list[int] = []
        for a in angles:
            t1 = time.time()
            c = t_count_for(a, eps)
            elapsed = time.time() - t1
            counts.append(c)
            print(f"  eps={eps:.0e} angle={a:.7f} -> T={c} ({elapsed:.2f}s)",
                  file=sys.stderr)
            rows.append({"epsilon": eps, "angle": a, "t_per_rotation": c})
        mu = statistics.mean(counts)
        sd = statistics.stdev(counts) if len(counts) > 1 else 0.0
        approx = 3.0 * math.log2(1.0 / eps)
        print(f"[eps={eps:.0e}] n={len(counts)} mean={mu:.2f} sd={sd:.2f} "
              f"min={min(counts)} max={max(counts)} 3log2(1/eps)={approx:.2f}",
              file=sys.stderr)

    payload = {
        "method": "pyLIQTR rz_decomp single-rotation synthesis (Ross–Selinger grid)",
        "angles": angles,
        "epsilons": EPSILONS,
        "note": "independent microbenchmark; not derived from TFIM totals",
        "rows": rows,
        "summary": {
            str(e): {
                "mean": round(statistics.mean(
                    [r["t_per_rotation"] for r in rows if r["epsilon"] == e]), 2),
                "sd": round(statistics.stdev(
                    [r["t_per_rotation"] for r in rows if r["epsilon"] == e]), 2),
                "min": min(r["t_per_rotation"] for r in rows if r["epsilon"] == e),
                "max": max(r["t_per_rotation"] for r in rows if r["epsilon"] == e),
                "n": sum(1 for r in rows if r["epsilon"] == e),
            }
            for e in EPSILONS
        },
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    print(f"[written] {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
