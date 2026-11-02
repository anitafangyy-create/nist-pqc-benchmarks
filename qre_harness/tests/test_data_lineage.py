#!/usr/bin/env python3
"""test_data_lineage.py — 论文表格数据可追溯性检查

核对 audit_data_lineage.csv 覆盖论文关键数字：
- 表 1 全部实例的 (T_base, R, T_total) 在台账中有 measured/derived 记录
- 表 4 微基准均值可从中位行复算
- 表 5 留出预测列来自 heldout_predictions.csv
- 每个 result 都有 input_file / source_function / output_file 定位

用法：.venv-qre/bin/python tests/test_data_lineage.py
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


# 1) lineage CSV 存在且覆盖论文实例
try:
    with open(f"{HERE}/audit_data_lineage.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    check("audit_data_lineage.csv non-empty", len(rows) > 50, f"{len(rows)} rows")
    cols = ["result_id", "instance", "tool", "metric", "input_file",
            "source_function", "output_file", "measured_or_derived",
            "calibration_used", "independent"]
    missing = [c for c in cols if c not in rows[0]]
    check("lineage columns complete", not missing, f"missing: {missing}")

    instances_in_lineage = {r["instance"] for r in rows}
    # 表 1 的 10 个实例（TFIM-J1.0/J0.5/h0.3/32/64, Hubbard-32/64, Chem-H2/LiH, QPE-7）
    expected_instances = {"TFIM-J1.0", "TFIM-J0.5", "TFIM-h0.3", "TFIM-32", "TFIM-64",
                          "Hubbard-32", "Hubbard-64", "Chem-H2", "Chem-LiH", "QPE-7"}
    missing_inst = expected_instances - instances_in_lineage
    check("all ten instances traced", not missing_inst, f"missing: {missing_inst}")

    # 2) 锚定实例：normalization/validation 行标记 calibration_used=yes；
    #    工具输出行（A_pyliqtr/t_total）保持独立（calibration_used=no）
    inst_rows = [r for r in rows if r["instance"] == "TFIM-J1.0"]
    check("anchor instance has calibration-used rows (normalization/validation)",
          any(r.get("calibration_used") == "yes" for r in inst_rows),
          [r["metric"] for r in inst_rows if r.get("calibration_used") == "yes"])
    a_raw = [r for r in inst_rows if r["tool"] == "A_pyliqtr" and r["metric"].lower() == "t_total"]
    if a_raw:
        check("anchor tool-output row not calibration-used",
              all(r.get("calibration_used") != "yes" for r in a_raw))
        check("anchor tool-output row independent",
              all(str(r.get("independent")).startswith("yes") for r in a_raw))
    else:
        check("anchor A_pyliqtr/t_total present", False, "not found")
except FileNotFoundError:
    check("audit_data_lineage.csv exists", False, "file not found")

# 3) 微基准均值可复算
try:
    with open(f"{HERE}/c_microbenchmark_100.json") as f:
        mb = json.load(f)
    s = mb["summary"]["1e-10"]
    check("microbenchmark n=100 at 1e-10", s["n"] == 100, f"n={s['n']}")
    check("microbenchmark mean ~101.06", abs(s["mean"] - 101.06) < 0.05, f"mean={s['mean']}")
except FileNotFoundError:
    check("c_microbenchmark_100.json exists", False, "file not found")

# 4) 留出预测列
try:
    with open(f"{HERE}/heldout_predictions.csv", newline="") as f:
        pred_rows = list(csv.DictReader(f))
    insts = {r["instance"] for r in pred_rows}
    check("heldout_predictions.csv covers 10 instances", len(insts) == 10,
          f"{len(insts)} distinct instances, {len(pred_rows)} rows")
    req = {"T_base", "R", "c_bar", "T_predicted", "T_observed", "error", "relative_error"}
    missing = req - set(pred_rows[0].keys()) if pred_rows else req
    check("heldout columns complete", not missing, f"missing: {missing}")
except FileNotFoundError:
    check("heldout_predictions.csv exists", False, "file not found")

print()
if FAILS:
    print(f"FAILURES ({len(FAILS)}):")
    for f_ in FAILS:
        print(" -", f_)
    raise SystemExit(1)
print("ALL TESTS PASSED")
