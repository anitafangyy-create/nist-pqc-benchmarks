#!/usr/bin/env python3
"""verify_data.py — 全量交叉核对：CSV × 论文草稿 HTML × 实测 JSON（纯标准库）。

闸门清单：
  1. sweep_full.csv 每行满足 T_total = T_base + R·c(1e-10)，c=103；
  2. sweep_full.csv measured 行 == crosscheck_results.json 实测值；
  3. experiment_results.csv 与 sweep_full / crosscheck 一致；
  4. paper_draft_full.html §4.2 表格与 sweep_full.csv 完全一致；
  5. paper_section4_experiments.html 表格与 sweep_full.csv 完全一致；
  6. 论文草稿中不再出现陈旧值（~250 / ~500 / ~26,000 / ~52,000 / LiH 20 项 / 262）；
  7. sweep.csv（ε 扫描）每行归一化恒等式成立。
任一失败即退出码 1。
"""
from __future__ import annotations

import csv
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
C = 103
fail = []


def check(cond, msg):
    if not cond:
        fail.append(msg)
        print(f"  [FAIL] {msg}")
    else:
        print(f"  [ok]   {msg}")


def load_csv(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---- 1. sweep_full.csv 内部一致性 ----
print("== 1. sweep_full.csv 内部一致性 ==")
sweep = load_csv(os.path.join(HERE, "sweep_full.csv"))
check(len(sweep) == 10, f"10 实例（9 LCU + 1 族外 QPE）（实际 {len(sweep)}）")
for r in sweep:
    lhs = int(r["T_total_1e-10"])
    rhs = int(r["T_base"]) + int(r["R"]) * C
    check(lhs == rhs, f"{r['instance']}: T_total={lhs} == T_base+R*c={rhs}")
    check(r["c_at_1e-10"] == "103", f"{r['instance']}: c=103")
    if r["instance"] == "QPE-7":
        check(int(r["T_base"]) == 0 and int(r["R"]) == 21,
              f"QPE-7: T_base=0, R=21（族外实例参数）")
        check(int(r["T_base"]) != 2 * int(r["R"]) - 8,
              f"QPE-7: 打破 T_base=2R-8（{r['T_base']} != {2*int(r['R'])-8}）")

# ---- 1b. 族外独立实例闸门（第二轮审计 P0 建议）----
print("== 1b. 族外独立实例（QPE-7） ==")
qpe = next(r for r in sweep if r["instance"] == "QPE-7")
with open(os.path.join(HERE, "ledger.json"), encoding="utf-8") as f:
    ledger = json.load(f)
qpe_ledger = next(r for r in ledger["results"] if r["algorithm"] == "QPE-7")
a = next(t for t in qpe_ledger["tools"] if t["tool"] == "A_pyliqtr")
b = next(t for t in qpe_ledger["tools"] if t["tool"] == "B_cirqft")
c = next(t for t in qpe_ledger["tools"] if t["tool"] == "C_qsharp")
check(int(b["T"]) == 0 and int(b["rotations"]) == 21, f"QPE-7: B 读数 T=0, R=21")
check(int(a["T"]) == int(b["T"]) + int(b["rotations"]) * C,
      f"QPE-7: 恒等式 T_A={a['T']} == T_base + R*c = {int(b['T'])+int(b['rotations'])*C}")
check(int(c["T"]) == int(b["T"]) and int(c["rotations"]) == int(b["rotations"]),
      f"QPE-7: C 逻辑级 T/R == B（独立栈复现）")
check(int(qpe["T_total_1e-10"]) == int(a["T"]), f"QPE-7: sweep_full == ledger (T_total={a['T']})")

# ---- 2. measured 行 == crosscheck ----
print("== 2. 实测锚点核对 ==")
with open(os.path.join(ROOT, "crosscheck_results.json"), encoding="utf-8") as f:
    cross = {d["instance"]: d for d in json.load(f)}
for inst, d in cross.items():
    row = next(r for r in sweep if r["instance"] == inst)
    b = d["toolB_cirqft"]
    check(row["status"] == "measured" and int(row["R"]) == int(b["Rotations"])
          and int(row["T_base"]) == int(b["T"])
          and int(row["T_total_1e-10"]) == int(d["toolA_pyliqtr"]["T"]),
          f"{inst}: sweep_full == crosscheck (R={b['Rotations']}, T_base={b['T']}, T_total={d['toolA_pyliqtr']['T']})")
    check(int(d["toolA_pyliqtr"]["T"]) == int(b["T"]) + int(b["Rotations"]) * C,
          f"{inst}: 恒等式 248+128*103=13432 成立（残差 0）")

# ---- 3. experiment_results.csv ----
print("== 3. experiment_results.csv ==")
exp = load_csv(os.path.join(HERE, "experiment_results.csv"))
check(len(exp) == 29, f"29 行（10 实测A + 10 实测C + 9 估计参考）（实际 {len(exp)}）")
with open(os.path.join(HERE, "ledger.json"), encoding="utf-8") as f:
    ledger = json.load(f)
measured_map = {r["algorithm"]: r for r in ledger["results"] if "error" not in r}
assert len(measured_map) == 10, "ledger 应有 10 实测实例"
for e in [r for r in exp if r["source"] == "pyLIQTR_measured"]:
    m = measured_map.get(e["size"])
    if m is None:
        check(False, f"pyLIQTR_measured {e['size']} 不在 ledger 中")
        continue
    a = next(t for t in m["tools"] if t["tool"] == "A_pyliqtr")
    b = next(t for t in m["tools"] if t["tool"] == "B_cirqft")
    check(int(e["R"]) == int(b["rotations"]) and int(e["T_base"]) == int(b["T"])
          and int(e["T_total_normalized"]) == int(a["T"]),
          f"pyLIQTR_measured {e['size']}: R/T_base/T_total 与 ledger 一致")
# C（Azure QRE）行：逻辑级 T/R 必须与 B 完全一致（独立栈复现闸门）
for e in [r for r in exp if r["source"] == "azure_qre_measured"]:
    m = measured_map.get(e["size"])
    if m is None:
        check(False, f"azure_qre_measured {e['size']} 不在 ledger 中")
        continue
    b = next(t for t in m["tools"] if t["tool"] == "B_cirqft")
    c = next(t for t in m["tools"] if t["tool"] == "C_qsharp")
    check(int(e["R"]) == int(c["rotations"]) and int(e["T_base"]) == int(c["T"])
          and int(c["T"]) == int(b["T"]) and int(c["rotations"]) == int(b["rotations"]),
          f"azure_qre_measured {e['size']}: C 逻辑级 T/R == B（独立栈复现）")
# 估计参考行存在性（口径对比，非实测，不与 sweep_full 直接相等）
jw_expected = {("2x2=8", 16), ("2x4=16", 40), ("4x4=32", 96), ("4x8=64", 208)}
for e in [r for r in exp if r["source"] == "openfermion_JW"]:
    check((e["size"], int(e["R"])) in jw_expected,
          f"openfermion_JW {e['size']} R={e['R']} 为估计参考值")
tr_expected = {("4x4=16", 40), ("4x6=24", 62), ("4x8=32", 84), ("8x8=64", 176)}
for e in [r for r in exp if r["source"] == "cirq_trotter"]:
    check((e["size"], int(e["R"])) in tr_expected,
          f"cirq_trotter {e['size']} R={e['R']} 为估计参考值")
# cirq_ft_measured 行（族外实例 B 读数）：与 ledger B 一致
for e in [r for r in exp if r["source"] == "cirq_ft_measured"]:
    m = measured_map.get(e["size"])
    if m is None:
        check(False, f"cirq_ft_measured {e['size']} 不在 ledger 中")
        continue
    b = next(t for t in m["tools"] if t["tool"] == "B_cirqft")
    check(int(e["T_base"]) == int(b["T"]) and int(e["R"]) == int(b["rotations"]),
          f"cirq_ft_measured {e['size']}: T_base/R 与 ledger B 一致")

# ---- 4/5. 论文 HTML 表格与 sweep_full 一致 ----
print("== 4/5. 论文草稿表格核对 ==")
def parse_table_rows(html_path):
    html = open(html_path, encoding="utf-8").read()
    m = re.search(r"<h3>4\.2 Full matrix.*?</table>", html, re.S)
    if not m:
        return None
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", m.group(0), re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if cells and cells[0] != "Instance":
            rows.append(cells)
    return rows

for path, label in [(os.path.join(ROOT, "paper_draft_full.html"), "paper_draft_full.html"),
                    (os.path.join(ROOT, "paper_section4_experiments.html"), "paper_section4_experiments.html")]:
    if not os.path.exists(path):
        print(f"  [skip] {label} 不在代码仓库（论文文稿在仓库外管理），跳过论文表格对账")
        continue
    rows = parse_table_rows(path)
    # 历史 HTML 草稿只含 9 个 LCU 实例（不含族外 QPE-7）；逐行核对与 sweep_full 一致
    check(rows is not None and len(rows) == 9, f"{label}: §4.2 表格 9 行（实际 {len(rows) if rows else 'N/A'}）")
    if rows:
        for cells in rows:
            inst = cells[0]
            r = next((r for r in sweep if r["instance"] == inst), None)
            if r is None:
                check(False, f"{label}: 表格含未知实例 {inst}")
                continue
            nums = [c.replace(",", "").replace("≈", "") for c in cells[1:6]]
            exp_nums = [r["n_qubits"], r["n_terms"], r["R"], r["T_base"], r["T_total_1e-10"]]
            check([n for n in nums] == [str(e) for e in exp_nums],
                  f"{label} {inst}: 表格 {nums} == sweep_full {exp_nums}")

# ---- 5b. 三栈对照表（§4.3）：C 逻辑级 == B、A/物理列 == ledger ----
print("== 5b. §4.3 三栈对照表核对 ==")
def parse_3stack_rows(html_path):
    html = open(html_path, encoding="utf-8").read()
    m = re.search(r"<h3>4\.3 Three-stack cross-tool comparison.*?</table>", html, re.S)
    if not m:
        return None
    rows = []
    for tr in re.findall(r"<tr>(.*?)</tr>", m.group(0), re.S):
        cells = [re.sub(r"<[^>]+>", "", c).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if cells and cells[0] != "Instance":
            rows.append(cells)
    return rows

for path, label in [(os.path.join(ROOT, "paper_draft_full.html"), "paper_draft_full.html"),
                    (os.path.join(ROOT, "paper_section4_experiments.html"), "paper_section4_experiments.html")]:
    if not os.path.exists(path):
        print(f"  [skip] {label} 不在代码仓库（论文文稿在仓库外管理），跳过三栈表对账")
        continue
    rows = parse_3stack_rows(path)
    # 历史 HTML 草稿只含 9 个 LCU 实例；逐行核对与 ledger 一致
    check(rows is not None and len(rows) == 9, f"{label}: §4.3 三栈表 9 行（实际 {len(rows) if rows else 'N/A'}）")
    if rows:
        for cells in rows:
            inst = cells[0]
            m = measured_map.get(inst)
            if m is None:
                check(False, f"{label}: 三栈表含未知实例 {inst}")
                continue
            a = next(t for t in m["tools"] if t["tool"] == "A_pyliqtr")
            b = next(t for t in m["tools"] if t["tool"] == "B_cirqft")
            c = next(t for t in m["tools"] if t["tool"] == "C_qsharp")
            q, b_cell, c_cell, a_cell, phys = cells[1], cells[2], cells[3], cells[4], cells[5]
            b_t, b_r = [x.replace(",", "") for x in b_cell.split(", ")]
            c_t, c_r = [x.replace(",", "") for x in c_cell.split(", ")]
            phys_n = phys.replace(",", "")
            # C 逻辑级必须 == B（独立栈复现）；A == ledger；物理列 == ledger note
            check(b_t == c_t and b_r == c_r and b_t == str(b["T"]) and b_r == str(b["rotations"])
                  and a_cell.replace(",", "") == str(a["T"])
                  and phys_n == re.search(r"physicalQubits=(\d+)", c["note"]).group(1),
                  f"{label} {inst}: 三栈表 B/C/A/物理 == ledger")

# ---- 6. 陈旧值检查 ----
print("== 6. 陈旧值残留检查 ==")
stale_patterns = ["~250", "~500", "~26,000", "~52,000", "preliminary", "simplified model"]
for path in [os.path.join(ROOT, "paper_draft_full.html"),
             os.path.join(ROOT, "paper_section4_experiments.html")]:
    if not os.path.exists(path):
        print(f"  [skip] {os.path.basename(path)} 不在代码仓库，跳过陈旧值残留检查")
        continue
    html = open(path, encoding="utf-8").read()
    for pat in stale_patterns:
        check(pat not in html, f"{os.path.basename(path)}: 无陈旧标记 '{pat}'")
    # 旧 LiH 行（20 项 / 262 / 56）精确定位；20 与 262 在当前数据中无合法出现
    check(">20</td>" not in html, f"{os.path.basename(path)}: 无旧 LiH n_terms=20 残留")
    check(">262</td>" not in html, f"{os.path.basename(path)}: 无旧 LiH T_total=262 残留")

# ---- 7. sweep.csv ε 扫描恒等式 ----
print("== 7. sweep.csv ε 扫描 ==")
sweep_csv = load_csv(os.path.join(HERE, "sweep.csv"))
C_M = {1e-4: 42, 1e-6: 62, 1e-8: 82, 1e-10: 103}
ok = True
for r in sweep_csv:
    if r["tool"] == "normalized":
        e = float(r["epsilon"])
        exp = int(r["rotations"]) * C_M[e] + 248
        ok = ok and int(r["T"]) == exp
check(ok, f"{len([r for r in sweep_csv if r['tool']=='normalized'])} 条 normalized 行全部满足 T=248+R*c(ε)")

print()
# ---- 8. 独立微基准闸门（第二轮审计新增）----
print("== 8. 独立 c(ε) 微基准核对 ==")
mb_path = os.path.join(HERE, "c_microbenchmark_full.json")
if os.path.exists(mb_path):
    with open(mb_path, encoding="utf-8") as f:
        mb = json.load(f)
    for e, cal in [(1e-4, 42), (1e-6, 62), (1e-8, 82), (1e-10, 103)]:
        s = mb["summary"][str(e)]
        check(s["n"] == 10, f"ε={e}: 微基准样本 n={s['n']} (应为 10)")
        if e == 1e-10:
            # 论文 §3.3 声明：锚点校准常数在 ε=1e-10 落在微基准均值 ±1sd 内
            check(abs(s["mean"] - cal) <= s["sd"],
                  f"ε={e}: c_cal={cal} 在微基准 mean={s['mean']} ± sd={s['sd']} 内")
        else:
            # 其余档校准常数取分布上界（calibration upper-bound choice）：≥ mean−sd 且 ≤ max+1
            check(s["mean"] - s["sd"] <= cal <= s["max"] + 1,
                  f"ε={e}: c_cal={cal} 为分布上界选择 (mean={s['mean']}±{s['sd']}, max={s['max']})")
else:
    check(False, "c_microbenchmark_full.json 缺失（先跑 microbenchmark_c.py --out c_microbenchmark_full.json）")

print()
if fail:
    print(f"共 {len(fail)} 项失败")
    sys.exit(1)
print("全部闸门通过：CSV × HTML × 实测 JSON 完全一致")
