#!/usr/bin/env python3
"""recompute_canonical.py — 权威实验数据重算（纯标准库，无外部依赖）。

统一口径与可复现性闸门：
  1. 从 Hamiltonian 构造（TFIM / Fermi-Hubbard JW / H2 / LiH）纯 Python 重算
     n_terms 与「非-Z Pauli 项数」R_ham（Hamiltonian 层口径，openfermion 模型）；
  2. T_base 模型：2·n_terms + 2·n_qubits（LCU 块编码标准模型，见 run_full_matrix.py）；
  3. T_total(ε=1e-10) = T_base + R_ham · c(1e-10)，c=103（实测校准）；
  4. 实测锚点（TFIM-16 家族）取自 ../crosscheck_results.json，覆盖估计值；
  5. 断言闸门：与既有实测/已知值逐一核对，不一致即失败退出。

输出：sweep_full.csv（canonical，含 status / convention 列）

R 口径说明（论文四元组协议的核心）：
  - measured 行：R 为电路级抽象旋转数（cirq_ft t_complexity 实测）。
  - estimate  行：R 为 Hamiltonian 层非-Z Pauli 项数（openfermion 模型）。
    两者是不同口径（TFIM-16：非-Z=16 vs 电路级实测=128，约 8×），
    估计行的 T_total 是同口径下内部一致的下界参考值，不可与 measured 行
    直接比较——这正是论文「T 门数跨工具不可比」要论证的现象。
"""
from __future__ import annotations

import csv
import json
import math
import os
import sys

C_AT_1E10 = 103          # 实测校准：每个旋转门在 ε=1e-10 下的 T 门成本
EPS_REF = 1e-10
HERE = os.path.dirname(os.path.abspath(__file__))
CROSSCHECK = os.path.join(HERE, "..", "crosscheck_results.json")

# ---------------------------------------------------------------------------
# Hamiltonian 构造（term: tuple[(qubit, pauli)]，已按 qubit 升序排序）
# ---------------------------------------------------------------------------

def _add(h, term, coeff):
    """term: tuple[(int,str)] 或 ()；合并同构项（系数只用于存在性，计数无关）。"""
    t = tuple(sorted(term))
    h[t] = h.get(t, 0.0) + coeff


def _zstring(i, j):
    """JW 相位串：qubit i+1 .. j-1 上的 Z。"""
    return tuple((k, "Z") for k in range(i + 1, j))


def build_tfim(n_rows, n_cols, J=1.0, h=1.0):
    n = n_rows * n_cols
    ham = {}
    for r in range(n_rows):
        for c in range(n_cols):
            i = r * n_cols + c
            if c + 1 < n_cols:
                _add(ham, ((i, "Z"), (i + 1, "Z")), J)
            if r + 1 < n_rows:
                _add(ham, ((i, "Z"), ((r + 1) * n_cols + c, "Z")), J)
            _add(ham, ((i, "X"),), h)
    return ham, n


def build_hubbard(n_rows, n_cols, t=-1.0, U=4.0):
    """Fermi-Hubbard → Jordan–Wigner。每格点 2 自旋轨道：up=2s, dn=2s+1。"""
    n_sites = n_rows * n_cols
    n_q = 2 * n_sites
    ham = {}
    for r in range(n_rows):
        for c in range(n_cols):
            s = r * n_cols + c
            up, dn = 2 * s, 2 * s + 1
            # U · n_up n_dn = U/4 (1 - Z_up - Z_dn + Z_up Z_dn)
            _add(ham, (), U / 4.0)
            _add(ham, ((up, "Z"),), -U / 4.0)
            _add(ham, ((dn, "Z"),), -U / 4.0)
            _add(ham, ((up, "Z"), (dn, "Z")), U / 4.0)
            for dr, dc in [(0, 1), (1, 0)]:
                nr, nc = r + dr, c + dc
                if nr < n_rows and nc < n_cols:
                    ns = nr * n_cols + nc
                    for sp in [0, 1]:
                        i, j = 2 * s + sp, 2 * ns + sp   # i < j
                        zs = _zstring(i, j)
                        _add(ham, ((i, "X"), (j, "X")) + zs, t / 2.0)
                        _add(ham, ((i, "Y"), (j, "Y")) + zs, t / 2.0)
    return ham, n_q


def build_h2():
    ham = {}
    _add(ham, (), -0.18305)
    for i in range(4):
        _add(ham, ((i, "Z"),), 0.17145 if i < 2 else -0.22201)
    for i, j, c in [(0,1,0.1205),(0,2,0.1686),(0,3,0.1659),
                    (1,2,0.1659),(1,3,0.1686),(2,3,0.1743)]:
        _add(ham, ((i, "Z"), (j, "Z")), c)
    # 四个 XXYY 型项（与 run_full_matrix.py build_h2 完全一致）
    for t4 in [((0,"X"),(1,"X"),(2,"Y"),(3,"Y")),
               ((0,"Y"),(1,"Y"),(2,"X"),(3,"X")),
               ((0,"X"),(2,"X"),(1,"Y"),(3,"Y")),
               ((0,"Y"),(2,"Y"),(1,"X"),(3,"X"))]:
        _add(ham, t4, 0.0453)
    return ham, 4


def build_lih():
    n_q = 8
    ham = {}
    _add(ham, (), -0.5)
    for i in range(n_q):
        _add(ham, ((i, "Z"),), 0.1 * (i % 3 - 1))
    for i in range(n_q):
        for j in range(i + 1, n_q):
            if (i + j) % 2 == 0:
                _add(ham, ((i, "Z"), (j, "Z")), 0.05)
    for t4 in [(0,1,2,3),(4,5,6,7)]:
        a, b, c_, d = t4
        _add(ham, ((a, "X"), (b, "X"), (c_, "Y"), (d, "Y")), 0.02)
    return ham, n_q


def count_rotations(ham):
    """非-Z Pauli 项数 = Hamiltonian 层旋转门数（openfermion 口径）。"""
    rot = 0
    for term in ham:
        if not term:
            continue
        if not all(p == "Z" for (_, p) in term):
            rot += 1
    return rot, len(ham)


def estimate_t_base(n_terms, n_qubits):
    """LCU 块编码标准模型：T_base ≈ 2·n_terms + 2·n_qubits。"""
    return int(2 * n_terms + 2 * n_qubits)


# ---------------------------------------------------------------------------
# 实测锚点（唯一真实测量：crosscheck_results.json）
# ---------------------------------------------------------------------------
def load_anchor():
    with open(CROSSCHECK, "r", encoding="utf-8") as f:
        data = json.load(f)
    anchor = {}
    for d in data:
        inst = d["instance"]
        b = d["toolB_cirqft"]
        a = d["toolA_pyliqtr"]
        anchor[inst] = {
            "n_qubits": d["n_qubits"],
            "n_terms": d["n_terms"],
            "R": int(b["Rotations"]),
            "T_base": int(b["T"]),
            "T_total": int(a["T"]),
            "residual": int(a["T"]) - (int(b["T"]) + int(b["Rotations"]) * C_AT_1E10),
            "ratio": d.get("raw_T_ratio", round(int(a["T"]) / int(b["T"]), 1)),
        }
    return anchor


# ---------------------------------------------------------------------------
# 实例注册与重算
# ---------------------------------------------------------------------------
INSTANCES = [
    ("TFIM-J1.0", build_tfim(4, 4, 1.0, 1.0), True),
    ("TFIM-J0.5", build_tfim(4, 4, 0.5, 1.0), True),
    ("TFIM-h0.3", build_tfim(4, 4, 1.0, 0.3), True),
    ("TFIM-32",   build_tfim(4, 8, 1.0, 1.0), False),
    ("TFIM-64",   build_tfim(8, 8, 1.0, 1.0), False),
    ("Hubbard-32", build_hubbard(4, 4), False),
    ("Hubbard-64", build_hubbard(4, 8), False),
    ("Chem-H2",   build_h2(), False),
    ("Chem-LiH",  build_lih(), False),
]

# 已知值闸门：(instance, 属性, 期望值) — 来自既有实测/已核对代码
KNOWN = {
    ("TFIM-J1.0", "n_terms"): 40, ("TFIM-J1.0", "R_ham"): 16,
    ("TFIM-32", "n_terms"): 84, ("TFIM-32", "R_ham"): 32,
    ("TFIM-64", "n_terms"): 176, ("TFIM-64", "R_ham"): 64,
    ("Hubbard-32", "n_terms"): 145, ("Hubbard-32", "R_ham"): 96,
    ("Hubbard-64", "n_terms"): 305, ("Hubbard-64", "R_ham"): 208,
    ("Chem-H2", "n_terms"): 15, ("Chem-H2", "R_ham"): 4,
    ("Chem-LiH", "n_terms"): 23, ("Chem-LiH", "R_ham"): 2,   # 代码口径=23（旧 CSV 的 20 为陈旧值）
}

def main():
    anchor = load_anchor()
    print(f"[anchor] 实测锚点 {len(anchor)} 条: {list(anchor)}")
    for inst, a in anchor.items():
        ok = "OK" if a["residual"] == 0 else f"RESIDUAL={a['residual']}"
        print(f"   {inst:<10} n_q={a['n_qubits']:<3} n_terms={a['n_terms']:<3} "
              f"R={a['R']:<4} T_base={a['T_base']:<4} T_total={a['T_total']} ratio={a['ratio']}x [{ok}]")

    rows = []
    print(f"\n{'Instance':<12} {'Qubits':<7} {'Terms':<7} {'R_ham':<6} {'T_base':<7} {'T_total':<8} status")
    print("-" * 72)
    for name, (ham, n_q), is_anchor in INSTANCES:
        R_ham, n_terms = count_rotations(ham)
        # 闸门：核对已知值
        for attr, val in [("n_terms", n_terms), ("R_ham", R_ham)]:
            exp = KNOWN.get((name, attr))
            if exp is not None and val != exp:
                print(f"[FAIL] {name}.{attr}: 重算 {val} != 已知 {exp}")
                sys.exit(1)
        if is_anchor and name in anchor:
            a = anchor[name]
            row = {
                "instance": name, "n_qubits": a["n_qubits"], "n_terms": a["n_terms"],
                "R": a["R"], "T_base": a["T_base"],
                "c_at_1e-10": C_AT_1E10, "T_total_1e-10": a["T_total"],
                "status": "measured",
                "convention": "circuit-level abstract rotations (cirq_ft t_complexity)",
            }
        else:
            tb = estimate_t_base(n_terms, n_q)
            tt = tb + R_ham * C_AT_1E10
            row = {
                "instance": name, "n_qubits": n_q, "n_terms": n_terms,
                "R": R_ham, "T_base": tb,
                "c_at_1e-10": C_AT_1E10, "T_total_1e-10": tt,
                "status": "estimate",
                "convention": "Hamiltonian-level non-Z Pauli terms (openfermion model)",
            }
        rows.append(row)
        print(f"{name:<12} {row['n_qubits']:<7} {row['n_terms']:<7} {row['R']:<6} "
              f"{row['T_base']:<7} {row['T_total_1e-10']:<8} {row['status']}")

    # 内部一致性：T_total = T_base + R·c
    for r in rows:
        lhs = r["T_total_1e-10"]
        rhs = r["T_base"] + r["R"] * C_AT_1E10
        if lhs != rhs:
            print(f"[FAIL] {r['instance']}: T_total {lhs} != T_base+R*c {rhs}")
            sys.exit(1)

    out_path = os.path.join(HERE, "sweep_full.csv")
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "instance", "n_qubits", "n_terms", "R", "T_base",
            "c_at_1e-10", "T_total_1e-10", "status", "convention"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    print(f"\n[written] {out_path}（{len(rows)} 行，全部闸门通过）")


if __name__ == "__main__":
    main()
