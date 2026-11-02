#!/usr/bin/env python3
"""test_no_calibration_leakage.py — 验证集与校准隔离检查

论文 §3.5/§4.5 的独立验证要求：
- calibration.json 冻结参数：use_anchor_instance = false、post_calibration_updates = false
- 锚定实例 TFIM-J1.0 不进入留出统计（heldout_predictions.csv 的独立统计排除它）
- 表 5 的 MRE/MAE/RMSE 是对"留出 9 实例"而非全部 10 实例计算

用法：.venv-qre/bin/python tests/test_no_calibration_leakage.py
退出码 0 = 通过；非 0 = 失败。
"""
from __future__ import annotations

import csv
import json
import sys

HERE = sys.argv[1] if len(sys.argv) > 1 else "."
FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        FAILS.append(f"{name}: {detail}")
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


# 1) calibration.json 隔离约束
with open(f"{HERE}/calibration.json") as f:
    cal = json.load(f)
check("calibration method is microbenchmark",
      cal.get("method") == "independent_rotation_microbenchmark",
      str(cal.get("method")))
check("use_anchor_instance = false", cal.get("use_anchor_instance") is False,
      str(cal.get("use_anchor_instance")))
check("post_calibration_updates = false",
      cal.get("post_calibration_updates") is False,
      str(cal.get("post_calibration_updates")))
check("calibration dataset recorded", bool(cal.get("calibration_dataset")), "missing")
check("heldout dataset recorded", bool(cal.get("heldout_dataset")), "missing")

# 2) 留出统计排除锚定实例
with open(f"{HERE}/heldout_predictions.csv", newline="") as f:
    rows = list(csv.DictReader(f))
anchor_rows = [r for r in rows if r.get("in_anchor_set") == "yes"]
non_anchor = [r for r in rows if r.get("in_anchor_set") == "no"]
check("exactly one anchor instance", len(anchor_rows) == 1, f"anchor rows = {len(anchor_rows)}")
check("nine held-out instances", len(non_anchor) == 9, f"held-out = {len(non_anchor)}")
check("anchor is TFIM-J1.0", all(r["instance"].startswith("TFIM-J1.0") for r in anchor_rows),
      [r["instance"] for r in anchor_rows])

# 独立统计口径：9 留出实例
maes = [abs(float(r["error"])) for r in non_anchor]
mae = sum(maes) / len(maes)
check("MAE over 9 held-out instances ~1004.7", abs(mae - 1004.7) < 1.0, f"MAE={mae:.1f}")

mres = [abs(float(r["relative_error"])) for r in non_anchor if r.get("relative_error")]
mre = sum(mres) / len(mres)
check("MRE over 9 held-out instances ~1.85%", abs(mre - 0.0185) < 0.0005, f"MRE={mre:.4f}")

# 3) 锚定实例的 T_observed 是原始工具输出而非预测
check("anchor T_observed is Tool A raw count (13432)",
      any(abs(float(r["T_observed"]) - 13432) < 1 for r in anchor_rows),
      "T_observed must equal pyLIQTR raw output, not recomputed")

print()
if FAILS:
    print(f"FAILURES ({len(FAILS)}):")
    for f_ in FAILS:
        print(" -", f_)
    raise SystemExit(1)
print("ALL TESTS PASSED")
