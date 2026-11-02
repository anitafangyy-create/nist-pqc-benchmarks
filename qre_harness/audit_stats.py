#!/usr/bin/env python3
"""audit_stats.py — Table 8 strict-汇总（严格 Y 口径），数据来自权威编码表
literature_audit/literature_audit.csv（included=TRUE, n=22）。

严格口径（strict, Y only，全分母 22）：
  precision stated 7/22；rotations decomposed 10/22；cross-tool comparable 1/22。
完整五口径（含 applicable/permissive/upper/decidable）见 audit_sensitivity.py。
"""
import csv
import os
from collections import Counter

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(ROOT, "literature_audit", "literature_audit.csv")

rows = [r for r in csv.DictReader(open(CSV, newline="")) if r["included"] == "TRUE"]
n = len(rows)

print(f"编码论文总数: {sum(1 for _ in csv.DictReader(open(CSV, newline='')))}")
print(f"纳入口径审计的资源估计论文: {n}")
print()

specs = [
    ("epsilon_code", "是否显式声明旋转合成精度 ε"),
    ("rotation_code", "旋转门是否分解为 T"),
    ("comparability_code", "T 计数是否跨工具可比"),
]
for col, title in specs:
    c = Counter(r[col] for r in rows)
    Y = c.get("Y", 0)
    print(f"【{title}】")
    print(f"  Y 满足:          {Y:2d}  strict {Y}/{n} = {100*Y/n:.1f}%")
    print(f"  P 部分匹配:      {c.get('P',0):2d}")
    print(f"  N 不满足:        {c.get('N',0):2d}")
    print(f"  U 无法判定:      {c.get('U',0):2d}")
    print(f"  NA 不适用:      {c.get('NA',0):2d}")
    print()

# 同向证据（§2.3 四篇）：明确质疑裸 T-count 作为通用指标的论文
SUPPORTERS = {"P11", "P23", "P29", "P12"}
crit = [r for r in rows if r["paper_id"] in SUPPORTERS]
print(f"【同向证据】质疑裸 T-count 作为通用指标的论文: {len(crit)} 篇（§2.3）")
for r in sorted(crit, key=lambda x: x["paper_id"]):
    print(f"  - [{r['paper_id']}] {r['paper'][:60]} ({r['identifier']})")
