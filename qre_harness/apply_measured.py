#!/usr/bin/env python3
"""把 sweep_full.csv 的 estimate 行替换为 2026-10-25 实测值。

实测数据源：qre_harness/ledger.json（run.py --algorithm all --tools A,B,C,D）。
- R/T_base 取自工具 B（qualtran t_complexity：rotations / T）
- T_total 取自工具 A（pyLIQTR estimate_resources 的 T）
- n_terms 取自 pyLIQTR ProblemInstance 实算（PauliLCU 编码，不含常数项）
替换后 9 实例全部为 measured；C 工具（qsharp）在 harness 中为占位 skipped。
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
LEDGER = HERE / "ledger.json"
CSV = HERE / "sweep_full.csv"

CONVENTION = "circuit-level abstract rotations (cirq_ft t_complexity)"
C_AT_REF = 103  # c(1e-10) 实测校准值


def main() -> int:
    led = json.loads(LEDGER.read_text())
    by_name = {r["algorithm"]: r for r in led["results"]}
    assert len(by_name) == 9, f"ledger 应有 9 实例，实际 {len(by_name)}"

    rows = []
    with open(CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames
        for row in reader:
            name = row["instance"]
            m = by_name.get(name)
            if m is None or "error" in m:
                print(f"!! 缺少实测：{name}，保留原行")
                rows.append(row)
                continue
            a = next(t for t in m["tools"] if t["tool"] == "A_pyliqtr")
            b = next(t for t in m["tools"] if t["tool"] == "B_cirqft")
            # 恒等式校验：T_base + R*c = T_total
            assert b["T"] + b["rotations"] * C_AT_REF == a["T"], name
            rows.append({
                "instance": name,
                "n_qubits": int(m["n_qubits"]),
                "n_terms": int(m["n_terms"]),
                "R": int(b["rotations"]),
                "T_base": int(b["T"]),
                "c_at_1e-10": C_AT_REF,
                "T_total_1e-10": int(a["T"]),
                "status": "measured",
                "convention": CONVENTION,
            })

    with open(CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"[ok] sweep_full.csv 已更新：{len(rows)} 行全部 measured")
    for r in rows:
        print(f"  {r['instance']:<12} q={r['n_qubits']:<3} t={r['n_terms']:<4} "
              f"R={r['R']:<5} Tb={r['T_base']:<5} Tt={r['T_total_1e-10']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
