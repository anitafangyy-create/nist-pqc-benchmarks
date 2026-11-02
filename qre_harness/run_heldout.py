#!/usr/bin/env python3
"""run_heldout.py — 独立留出电路验证（实验 B）

设计（按第三轮审稿方案）：
  - 校准 = 独立单旋转微基准（microbenchmark_c_100.py，100 generic 角度/精度），
    冻结校准参数 c_bar(eps)（平均值），不参与后续任何调整；
  - 验证 = 全部 10 个完整电路实例，预测 T_pred = T_base + R * c_bar(eps_ref)；
  - TFIM-J1.0 曾参与 c_cal 锚定（103=(13432-248)/128），列入观察但不计入
    "独立验证"统计（排除后单独报告）；其余实例从未参与校准或参数选择；
  - 每个实例报告：T_base / R / c_bar / T_pred / T_observed / error / relative_error；
  - 误差统计：MAE / RMSE / mean absolute relative error（观测为 0 设 NaN 单列）；
  - 校准参数在验证阶段不修改（use_anchor_instance=false, post_calibration_updates=false）。

输出：
  calibration.json        —— 冻结的校准配置
  heldout_results.csv     —— 实例级预测与误差
  heldout_predictions.csv —— 误差统计汇总
"""
from __future__ import annotations

import csv
import json
import math
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, "ledger.json")
MICRO100 = os.path.join(ROOT, "c_microbenchmark_100.json")
EPS_REF = 1e-10
ANCHOR_INSTANCES = {"TFIM-J1.0"}  # 曾参与 c_cal 锚定的实例（排除出独立验证统计）

BAR = {
    "1e-10": 101.06,  # 由 c_microbenchmark_100.json summary 读取，此处仅记录口径
}


def main() -> int:
    ledger = json.load(open(LEDGER))
    micro = json.load(open(MICRO100))
    c_bar = {float(e): s["mean"] for e, s in micro["summary"].items()}

    calib = {
        "method": "independent_rotation_microbenchmark",
        "epsilon_values": [1e-4, 1e-6, 1e-8, 1e-10],
        "n_angles_per_precision": micro["n_angles_per_precision"],
        "angle_seed": micro["angle_seed"],
        "special_angle_exclusion": micro["special_angle_exclusion"],
        "calibration_dataset": "calibration_angles.csv",
        "heldout_dataset": "all 10 ledger instances (TFIM-J1.0 excluded from independent stats)",
        "use_anchor_instance": False,
        "post_calibration_updates": False,
        "c_bar_per_epsilon": {str(e): m for e, m in c_bar.items()},
        "note": "calibration frozen before any heldout prediction; parameters not modified afterwards",
    }
    with open(os.path.join(ROOT, "calibration.json"), "w") as f:
        json.dump(calib, f, indent=2)

    rows = []
    for r in ledger["results"]:
        inst = r["algorithm"]
        tools = {t["tool"]: t for t in r["tools"]}
        b = tools.get("B_cirqft")
        a = tools.get("A_pyliqtr")
        if b is None or a is None:
            continue
        t_base = int(b["T"])
        R = int(b["rotations"])
        t_obs = int(a["T"])
        c = c_bar[EPS_REF]
        t_pred = t_base + R * c
        err = t_obs - t_pred
        rel = err / t_obs if t_obs != 0 else float("nan")
        rows.append({
            "instance": inst,
            "T_base": t_base,
            "R": R,
            "c_bar": c,
            "T_predicted": round(t_pred, 2),
            "T_observed": t_obs,
            "error": round(err, 2),
            "relative_error": round(rel, 6),
            "in_anchor_set": "yes" if inst in ANCHOR_INSTANCES else "no",
            "note": ("anchor instance (c_cal=103 back-computed); observed but excluded from independent stats"
                     if inst in ANCHOR_INSTANCES else "never used for calibration"),
        })

    with open(os.path.join(ROOT, "heldout_results.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    def metrics(rs):
        errs = [abs(r["error"]) for r in rs]
        rels = [abs(r["relative_error"]) for r in rs
                if not math.isnan(r["relative_error"])]
        zero_obs = [r["instance"] for r in rs if r["T_observed"] == 0]
        return {
            "n": len(rs),
            "MAE": round(sum(errs) / len(errs), 3) if errs else None,
            "RMSE": round(math.sqrt(sum(e * e for e in errs) / len(errs)), 3) if errs else None,
            "mean_abs_relative_error": round(sum(rels) / len(rels), 6) if rels else None,
            "instances_with_zero_observed": zero_obs,
        }

    stats = {
        "eps_ref": EPS_REF,
        "all_10_instances": metrics(rows),
        "heldout_9_excluding_anchor_TFIM_J1_0": metrics([r for r in rows if r["in_anchor_set"] == "no"]),
        "anchor_only_TFIM_J1_0": metrics([r for r in rows if r["in_anchor_set"] == "yes"]),
    }
    # heldout_predictions.csv: 纯 CSV（实例级预测与误差，机器可读，无任何统计文本混入）
    with open(os.path.join(ROOT, "heldout_predictions.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    # 统计汇总单独落盘为 JSON，不再写入 CSV
    with open(os.path.join(ROOT, "heldout_stats.json"), "w") as f:
        json.dump(stats, f, indent=2)

    print(json.dumps(stats, indent=2))
    print(f"[written] calibration.json / heldout_results.csv / heldout_predictions.csv / heldout_stats.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
