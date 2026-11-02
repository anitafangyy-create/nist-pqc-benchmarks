#!/usr/bin/env python3
"""audit_sensitivity.py — 文献审计百分比复算（口径标签与论文 Table 8 / Table 9 一一对应）。

从 literature_audit/literature_audit.csv 的 included=TRUE 样本（n=22）复算五个口径：
  strict_full   : Y / 22（全分母，NA 保留在分母；Table 8 / Table 9 Strict 行）
  applicable    : Y / (22 - NA)（排除该轴 NA 后的适用分母；§5.2 适用分母）
  permissive    : (Y + P) / applicable 分母（部分匹配 P 计为可转换；Table 9 Permissive 行）
  upper_bound   : (Y + U) / 22（不确定 U 全部按满足；Table 9 Upper bound 行）
  decidable     : Y / (Y + P + N)（剔除 U、NA 后的可判定子集；Table 9 Decidable subset 行）

编码含义见 literature_audit/coding_manual.md：Y 满足、P 部分匹配、N 不满足、
U 无法判定、NA 不适用（该轴无旋转合成维度）。所有比率为编码情景下的样本比例，
不是统计抽样置信区间。
"""
from __future__ import annotations

import csv
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(ROOT, "literature_audit", "literature_audit.csv")

COLUMNS = [
    ("epsilon_code", "Precision stated (ε)"),
    ("rotation_code", "Rotations decomposed into T"),
    ("comparability_code", "Cross-tool comparable"),
]


def load():
    with open(CSV, newline="") as f:
        return [r for r in csv.DictReader(f) if r["included"] == "TRUE"]


def pct(n, d):
    return f"{n}/{d} = {100.0 * n / d:.1f}%" if d else "n/a"


def rates(col, rows):
    codes = [r[col] for r in rows]
    n = len(codes)
    Y = codes.count("Y")
    P = codes.count("P")
    N = codes.count("N")
    U = codes.count("U")
    NA = codes.count("NA")
    applicable = n - NA
    decidable = Y + P + N
    return {
        "strict_full (Y/22)": pct(Y, n),
        "applicable (Y/(22-NA))": pct(Y, applicable),
        "permissive ((Y+P)/applicable)": pct(Y + P, applicable),
        "upper_bound ((Y+U)/22)": pct(Y + U, n),
        "decidable (Y/(Y+P+N))": pct(Y, decidable),
        "counts": f"Y={Y} P={P} N={N} U={U} NA={NA}",
    }


def main() -> int:
    rows = load()
    print(f"statistical sample n = {len(rows)} (included=TRUE)")
    for col, label in COLUMNS:
        print(f"\n== {label} ({col}) ==")
        out = rates(col, rows)
        print("  " + out["counts"])
        for k in ("strict_full (Y/22)", "applicable (Y/(22-NA))",
                  "permissive ((Y+P)/applicable)", "upper_bound ((Y+U)/22)",
                  "decidable (Y/(Y+P+N))"):
            print(f"  {k:34s}: {out[k]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
