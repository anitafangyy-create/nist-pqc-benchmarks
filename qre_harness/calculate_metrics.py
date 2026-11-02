#!/usr/bin/env python3
"""calculate_metrics.py — 留出预测误差、置信区间与分组统计的独立复算

从 heldout_results.csv（或 heldout_predictions.csv）独立复算：
- 每实例误差 / 相对误差
- MAE / RMSE / MRE（留出子集，排除锚定实例）
- 按电路家族分组（TFIM / Hubbard / Chem / QPE）的 MRE
- c̄(1e-10) 的 bootstrap 95% CI（角度重采样，seed 固定）

用法：.venv-qre/bin/python calculate_metrics.py --out metrics.json
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="metrics.json")
    p.add_argument("--csv", default="heldout_predictions.csv")
    p.add_argument("--seed", type=int, default=20261026)
    p.add_argument("--bootstrap", type=int, default=2000)
    args = p.parse_args()

    with open(args.csv, newline="") as f:
        rows = list(csv.DictReader(f))

    non_anchor = [r for r in rows if not r["instance"].startswith("TFIM-J1.0")]
    errs = [abs(float(r["error"])) for r in non_anchor]
    rels = [abs(float(r["relative_error"])) for r in non_anchor
            if r.get("relative_error") and r["relative_error"] != ""]

    mae = statistics.mean(errs)
    rmse = math.sqrt(sum(e * e for e in errs) / len(errs))
    mre = statistics.mean(rels)

    # 分组
    def family(name: str) -> str:
        for k in ("TFIM", "Hubbard", "Chem", "QPE"):
            if name.startswith(k):
                return k
        return "other"

    groups: dict[str, list[float]] = {}
    for r in non_anchor:
        if r.get("relative_error") and r["relative_error"] != "":
            groups.setdefault(family(r["instance"]), []).append(abs(float(r["relative_error"])))
    grouped = {k: {"n": len(v), "mre": round(statistics.mean(v), 4)} for k, v in groups.items()}

    # 角度 bootstrap CI（对 c̄(1e-10)）
    rng = random.Random(args.seed)
    with open("c_microbenchmark_100.json") as f:
        mb = json.load(f)
    vals = [r["t_per_rotation"] for r in mb["rows"]
            if abs(r["epsilon"] - 1e-10) < 1e-12]
    bs = []
    for _ in range(args.bootstrap):
        s = [rng.choice(vals) for _ in range(len(vals))]
        bs.append(statistics.mean(s))
    bs.sort()
    ci = (bs[int(0.025 * args.bootstrap)], bs[int(0.975 * args.bootstrap) - 1])

    payload = {
        "cbar_frozen": 101.06,
        "n_heldout": len(non_anchor),
        "excluded_anchor": "TFIM-J1.0",
        "mae": round(mae, 3),
        "rmse": round(rmse, 3),
        "mean_absolute_relative_error": round(mre, 4),
        "grouped_mre": grouped,
        "cbar_ci95_bootstrap": [round(ci[0], 3), round(ci[1], 3)],
        "bootstrap_B": args.bootstrap,
        "seed": args.seed,
    }
    with open(args.out, "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
