#!/usr/bin/env python3
"""regenerate_summaries.py — 从实测账本派生态总 CSV（纯标准库）。

数据源（单一权威）：
  - ledger.json                 9 实例 × 实测（run.py --algorithm all --tools A,B,C,D）
  - sweep_full.csv              权威口径表（9 行全部 measured）
  - ../crosscheck_results.json  历史锚点（TFIM-16 家族，与 ledger 一致）

输出：
  - experiment_results.csv  实验汇总（pyLIQTR_measured ×9 + 估计参考行）
  - sweep_real.csv          实测锚点汇总（9 行全部 measured）
"""
from __future__ import annotations

import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(HERE, "ledger.json"), encoding="utf-8") as f:
    ledger = json.load(f)
with open(os.path.join(HERE, "sweep_full.csv"), encoding="utf-8") as f:
    canonical = list(csv.DictReader(f))

C_AT_REF = 103  # c(1e-10) 实测校准值
measured = [r for r in ledger["results"] if "error" not in r]
assert len(measured) == 9, f"ledger 应有 9 实测实例，实际 {len(measured)}"

# ---------------------------------------------------------------------------
# experiment_results.csv
# ---------------------------------------------------------------------------
rows = []
for m in measured:
    a = next(t for t in m["tools"] if t["tool"] == "A_pyliqtr")
    b = next(t for t in m["tools"] if t["tool"] == "B_cirqft")
    residual = int(a["T"]) - (int(b["T"]) + int(b["rotations"]) * C_AT_REF)
    rows.append({
        "source": "pyLIQTR_measured", "size": m["algorithm"],
        "n_qubits": int(m["n_qubits"]), "n_terms": int(m["n_terms"]),
        "R": int(b["rotations"]), "T_base": int(b["T"]),
        "c_at_1e-10": C_AT_REF, "T_total_normalized": int(a["T"]),
        "convention": "circuit-level abstract rotations (cirq_ft t_complexity)",
        "note": f"2026-10-25 实测 ledger.json；T_base+R*c=T_total 残差={residual}；"
                f"A Clifford={a['Clifford']}, B Clifford={b['Clifford']}",
    })
    # C（Azure QRE）：独立栈，逻辑级与 B 同口径（旋转单列），物理级 QEC 真数
    c = next((t for t in m["tools"] if t["tool"] == "C_qsharp"), None)
    if c is not None:
        rows.append({
            "source": "azure_qre_measured", "size": m["algorithm"],
            "n_qubits": int(m["n_qubits"]), "n_terms": int(m["n_terms"]),
            "R": int(c["rotations"]), "T_base": int(c["T"]),
            "c_at_1e-10": "n/a", "T_total_normalized": "n/a",
            "convention": "logical: rotation-abstract (Q#); physical: Azure QEC",
            "note": f"2026-10-25 实测；逻辑级 T/R 与 B 一致；"
                    f"physicalQubits={c['note'].split('physicalQubits=')[1].split(',')[0]}",
        })
# 估计参考行（口径对比，不参与实测结论）
trotter = [
    ("4x4=16", 16, 40, 40),
    ("4x6=24", 24, 62, 62),
    ("4x8=32", 32, 84, 84),
    ("8x8=64", 64, 176, 176),
]
jwh = [
    ("2x2=8", 8, 29, 16),
    ("2x4=16", 16, 65, 40),
    ("4x4=32", 32, 145, 96),
    ("4x8=64", 64, 305, 208),
]
for size, nq, nt, R in trotter:
    rows.append({
        "source": "cirq_trotter", "size": size, "n_qubits": nq, "n_terms": nt,
        "R": R, "T_base": "n/a", "c_at_1e-10": "n/a", "T_total_normalized": "n/a",
        "convention": "Trotter circuit, 1 rotation per Pauli term",
        "note": "独立验证 R 缩放方向；口径≠实测电路级 R，不可直接比较",
    })
for size, nq, nt, R in jwh:
    rows.append({
        "source": "openfermion_JW", "size": size, "n_qubits": nq, "n_terms": nt,
        "R": R, "T_base": "n/a", "c_at_1e-10": "n/a", "T_total_normalized": "n/a",
        "convention": "Hamiltonian-level non-Z Pauli terms",
        "note": "估计参考口径（历史 sweep_full estimate 行同款），非实测",
    })

with open(os.path.join(HERE, "experiment_results.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["source", "size", "n_qubits", "n_terms", "R",
                                      "T_base", "c_at_1e-10", "T_total_normalized",
                                      "convention", "note"])
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"[written] experiment_results.csv ({len(rows)} 行：9 实测A + {sum(1 for r in rows if r['source']=='azure_qre_measured')} 实测C + 8 估计参考)")

# ---------------------------------------------------------------------------
# sweep_real.csv（实测锚点汇总：9 行全部 measured）
# ---------------------------------------------------------------------------
real = []
for c in canonical:
    m = next(r for r in measured if r["algorithm"] == c["instance"])
    a = next(t for t in m["tools"] if t["tool"] == "A_pyliqtr")
    b = next(t for t in m["tools"] if t["tool"] == "B_cirqft")
    real.append({
        "instance": c["instance"], "n_qubits": int(m["n_qubits"]),
        "T_base": int(b["T"]), "R": int(b["rotations"]),
        "T_pyliqtr": int(a["T"]),
        "note": "measured 2026-10-25 (ledger.json, pyliqtr1.4.2/qualtran0.4.0)",
    })

with open(os.path.join(HERE, "sweep_real.csv"), "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=["instance", "n_qubits", "T_base", "R", "T_pyliqtr", "note"])
    w.writeheader()
    for r in real:
        w.writerow(r)
print(f"[written] sweep_real.csv ({len(real)} 行，全部 measured)")
