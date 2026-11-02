#!/usr/bin/env python3
"""用 crosscheck_results.json 的真实实测数据生成 sweep.csv。

每个实例在每个 ε 下输出三行：
  - B_cirqft_raw: T_base（恒定，未分解旋转门）
  - normalized:   T_base + R·c(ε)（应=A pyLIQTR）
  - A_pyliqtr:     实测 T（仅 1e-10 有真实值，其余按恒等式）
"""
import json, csv

C = {1e-4: 42, 1e-6: 62, 1e-8: 82, 1e-10: 103}
EPS = [1e-4, 1e-6, 1e-8, 1e-10]

data = json.load(open("../nist-pqc/crosscheck_results.json"))
rows = []
for d in data:
    inst = d["instance"]
    nq = d["n_qubits"]; nt = d["n_terms"]
    tb = d["toolB_cirqft"]["T"]; R = d["toolB_cirqft"]["Rotations"]
    A_meas = d["toolA_pyliqtr"]["T"]
    for e in EPS:
        c = C[e]
        norm = tb + R * c
        rows.append({"algorithm": inst, "n_qubits": nq, "n_terms": nt,
                     "epsilon": e, "tool": "B_cirqft_raw", "T": tb, "rotations": R,
                     "note": "实测裸值"})
        rows.append({"algorithm": inst, "n_qubits": nq, "n_terms": nt,
                     "epsilon": e, "tool": "normalized", "T": norm, "rotations": R,
                     "note": f"T_base+R*c, c={c}"})
        rows.append({"algorithm": inst, "n_qubits": nq, "n_terms": nt,
                     "epsilon": e, "tool": "A_pyliqtr",
                     "T": A_meas if e == 1e-10 else norm,
                     "rotations": R,
                     "note": "实测@1e-10" if e == 1e-10 else "由恒等式"})

with open("sweep.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["algorithm","n_qubits","n_terms","epsilon","tool","T","rotations","note"])
    w.writeheader(); [w.writerow(r) for r in rows]
print(f"[written] sweep.csv ({len(rows)} rows, {len(data)} measured instances)")
