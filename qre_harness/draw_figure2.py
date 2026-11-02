#!/usr/bin/env python3
"""draw_figure2.py — 重绘 Figure 2（审计堆叠柱），柱顶标签使用严格 n=22 精确率。

数据从 literature_audit/literature_audit.csv 现算（included=TRUE, n=22），不硬编码；
灰层 = n - Y（P/N/U/NA 合并为 No/unclear）。输出 figure2_audit.png 到本脚本同目录。
运行：python draw_figure2.py（仅依赖 matplotlib + 标准库 csv/os）。
"""
import csv, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.abspath(__file__))
rows = [r for r in csv.DictReader(
    open(os.path.join(ROOT, "literature_audit", "literature_audit.csv")))
    if r["included"] == "TRUE"]
n = len(rows)


def y_count(col):
    return sum(1 for r in rows if r[col] == "Y")


series = [
    ("epsilon_code", "States ε"),
    ("rotation_code", "Decomposes rotations"),
    ("comparability_code", "Cross-tool comparable"),
]
labels = [lbl for _, lbl in series]
yes = [y_count(col) for col, _ in series]
other = [n - y for y in yes]
rates = [100.0 * y / n for y in yes]

BLUE, GRAY, RED = "#1f4e8c", "#b8bdc4", "#c0392b"
fig, ax = plt.subplots(figsize=(9.6, 4.65), dpi=200)
x = range(len(labels))
ax.bar(x, yes, color=BLUE, label="Yes", width=0.58)
ax.bar(x, other, bottom=yes, color=GRAY, label="No / unclear", width=0.58)

for xi, yv, ov, rt in zip(x, yes, other, rates):
    ax.text(xi, yv / 2, str(yv), ha="center", va="center", color="white", fontsize=13)
    ax.text(xi, yv + ov / 2, str(ov), ha="center", va="center", color="#333333", fontsize=12)
    ax.text(xi, yv + ov + 0.7, f"{rt:.1f}%", ha="center", va="bottom",
            color=RED, fontsize=14, fontweight="bold")

ax.set_xticks(list(x))
ax.set_xticklabels(labels, fontsize=13)
ax.set_ylim(0, 26)
ax.set_yticks(range(0, 26, 5))
ax.set_ylabel("Papers (n = 22 resource estimates)", fontsize=12)
ax.set_title("Literature audit: reporting conventions in fault-tolerant resource estimates",
             fontsize=15, pad=12)
ax.legend(loc="upper left", frameon=False, fontsize=12)
for spine in ("top", "right"):
    ax.spines[spine].set_visible(False)
fig.tight_layout()
out = os.path.join(ROOT, "figure2_audit.png")
fig.savefig(out, dpi=200, bbox_inches="tight")
print("saved", out)
print("yes=", yes, "other=", other, "rates=", [round(r, 1) for r in rates], "n=", n)
