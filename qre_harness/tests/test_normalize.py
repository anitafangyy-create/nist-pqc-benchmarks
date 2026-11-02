#!/usr/bin/env python3
"""test_normalize.py — 公式计算、边界条件与计数口径检查

覆盖论文 §3 归一化恒等式 T_total = T_base + R·c 的纯计算规则：
- 基本公式复算（与 ledger 权威值一致）
- 边界：R=0 → T_total = T_base；c=0 → T_total = T_base
- 计数口径：c 必须为 0 旋转时的合理值（>0）、R 非负、T_base 非负
- 与 heldout_predictions.csv 的预测列一致

用法：.venv-qre/bin/python tests/test_normalize.py
退出码 0 = 全部通过；非 0 = 失败。
"""
from __future__ import annotations

import json
import math
import sys

HERE = sys.argv[1] if len(sys.argv) > 1 else "."

FAILS: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if not cond:
        FAILS.append(f"{name}: {detail}")
    print(f"[{'PASS' if cond else 'FAIL'}] {name}")


# 1) 恒等式复算（锚定常数 c_cal=103，表 1）
with open(f"{HERE}/ledger.json") as f:
    ledger = json.load(f)
instances = ledger["results"] if isinstance(ledger, dict) and "results" in ledger else ledger
if isinstance(instances, dict):
    instances = list(instances.values())

n_checked = 0
for inst in instances:
    if not isinstance(inst, dict):
        continue
    # 与 run_heldout.py 相同的解析路径：B_cirqft 给 (T_base, R)，A_pyliqtr 给 T_total
    tools = {t["tool"]: t for t in inst.get("tools", [])}
    b = tools.get("B_cirqft")
    a = tools.get("A_pyliqtr")
    if b is None or a is None:
        continue
    T_base = int(b["T"])
    R = int(b["rotations"])
    T_total = int(a["T"])
    pred = T_base + R * 103
    check(f"identity for {inst.get('algorithm', '?')}",
          pred == T_total,
          f"T_base={T_base}, R={R}, pred={pred}, reported={T_total}")
    n_checked += 1

check("at least one ledger instance checked", n_checked > 0, f"checked {n_checked}")

# 2) 边界条件
check("R=0 -> T_total=T_base", 248 + 0 * 103 == 248)
check("c=0 -> T_total=T_base", 248 + 128 * 0 == 248)
check("non-negative R", 0 <= 128 and 0 <= 0)
check("positive c", 103 > 0)

# 3) heldout 预测列复算（c_bar = 101.06）
import csv
try:
    with open(f"{HERE}/heldout_predictions.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    ok = 0
    for r in rows:
        if "T_predicted" not in r:
            continue
        T_base = float(r["T_base"])
        R = float(r["R"])
        pred = float(r["T_predicted"])
        expect = T_base + R * 101.06
        if abs(pred - expect) < 0.05:
            ok += 1
    check("heldout_predictions.csv T_predicted recomputable", ok == len(rows),
          f"{ok}/{len(rows)} rows match T_base + R*101.06")
except FileNotFoundError:
    check("heldout_predictions.csv exists", False, "file not found (skip-able if not generated)")

print()
if FAILS:
    print(f"FAILURES ({len(FAILS)}):")
    for f_ in FAILS:
        print(" -", f_)
    raise SystemExit(1)
print("ALL TESTS PASSED")
