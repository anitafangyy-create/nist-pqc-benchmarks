#!/usr/bin/env python3
"""audit_data_lineage.py — 论文数据来源登记表（每个数字的可追溯路径）

为论文 Table 1 / Table 2 / Table 3 中的每个结果生成一行：
  result_id, instance, tool, metric, input_file, source_function,
  output_file, measured_or_derived, calibration_used, independent

independent 的定义（按第三轮审稿要求）：
  该结果是否独立于"待验证的归一化结论"生成，而不是是否由另一段代码计算。
  - A/B 的原始读数：独立（各自从同一算法规范独立编译/估算）
  - C 的逻辑级读数：不独立（输入直接取自 B 的 (T_base, R) 元组，仅独立栈复现同一规格）
  - c_cal(1e-10)=103：不独立（TFIM 总计数反推锚定）
  - c_cal(1e-4/6/8)=42/62/82：不独立（pyLIQTR 内置模型值=分布上界选择）
  - 微基准均值：独立（逐角度真实合成，与主案例无关）
  - T_pred（归一化预测）：派生且使用校准常数（calibration_used=yes）

用法：
  .venv-qre/bin/python audit_data_lineage.py   # 读 ledger.json + c_microbenchmark_full.json
"""
from __future__ import annotations

import csv
import json
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
LEDGER = os.path.join(ROOT, "ledger.json")
MICRO = os.path.join(ROOT, "c_microbenchmark_full.json")
OUT = os.path.join(ROOT, "audit_data_lineage.csv")


def main() -> int:
    ledger = json.load(open(LEDGER))
    micro = json.load(open(MICRO))

    rows: list[dict] = []
    rid = 0

    def add(**kw):
        nonlocal rid
        rid += 1
        rows.append({"result_id": f"R{rid:03d}", **kw})

    # c_cal 校准常数（论文 §3.3 / Table 3）
    for eps, c in [(1e-4, 42), (1e-6, 62), (1e-8, 82), (1e-10, 103)]:
        src = ("TFIM-J1.0 totals: (13432-248)/128"
               if eps == 1e-10 else
               "pyLIQTR 1.4.2 rotation-cost model values (3.02*log2(1/eps)+0.77, sd 2.06, seed 0)")
        add(instance="(global)", tool="normalization",
            metric=f"c_cal({eps})", input_file="ledger.json",
            source_function="MEASURED_C / anchor back-computation",
            output_file="ledger.json", measured_or_derived="derived",
            calibration_used="yes",
            independent=f"no ({src})")

    # 微基准统计（论文 Table 3）
    for eps, s in micro["summary"].items():
        add(instance="(microbenchmark)", tool="pyLIQTR rz_decomp",
            metric=f"c_microbench_mean({eps})",
            input_file="microbenchmark_c.py angles (10 generic)",
            source_function="rz_decomp(rads, precision).get_T_count()",
            output_file="c_microbenchmark_full.json",
            measured_or_derived="measured_output",
            calibration_used="no",
            independent=f"yes (n={s['n']}, mean={s['mean']}, sd={s['sd']}, range {s['min']}-{s['max']})")

    # 每个实例的跨工具读数与派生结果
    for r in ledger["results"]:
        inst = r["algorithm"]
        tools = {t["tool"]: t for t in r["tools"]}
        a = tools.get("A_pyliqtr")
        b = tools.get("B_cirqft")
        c = tools.get("C_qsharp")
        d = tools.get("D_naive")

        if b is not None:
            add(instance=inst, tool="B_cirqft", metric="t_base",
                input_file="algorithms.py block_encoding",
                source_function="cirq_ft/qualtran t_complexity",
                output_file="ledger.json", measured_or_derived="measured_output",
                calibration_used="no", independent="yes (independent compiler output)")
            add(instance=inst, tool="B_cirqft", metric="rotations",
                input_file="algorithms.py block_encoding",
                source_function="cirq_ft/qualtran t_complexity",
                output_file="ledger.json", measured_or_derived="measured_output",
                calibration_used="no", independent="yes (independent compiler output)")
        if a is not None:
            add(instance=inst, tool="A_pyliqtr", metric="t_total",
                input_file="algorithms.py block_encoding",
                source_function="pyLIQTR estimate_resources (base + rotation-cost model)",
                output_file="ledger.json", measured_or_derived="measured_output",
                calibration_used="no",
                independent="yes (independent compiler output; rotation part is the tool's built-in cost model)")
        if c is not None:
            add(instance=inst, tool="C_qsharp", metric="t_base_logical",
                input_file="run.py (B ledger T_base/R tuple)",
                source_function="qsharp.estimate logicalCounts (Q# abstract circuit)",
                output_file="ledger.json", measured_or_derived="measured_output",
                calibration_used="no",
                independent="no (input shares B's (T_base, R); independent stack, same specification)")
            add(instance=inst, tool="C_qsharp", metric="rotations_logical",
                input_file="run.py (B ledger T_base/R tuple)",
                source_function="qsharp.estimate logicalCounts (Q# abstract circuit)",
                output_file="ledger.json", measured_or_derived="measured_output",
                calibration_used="no",
                independent="no (input shares B's (T_base, R); independent stack, same specification)")
            add(instance=inst, tool="C_qsharp", metric="phys_qubits",
                input_file="run.py (B ledger T_base/R tuple)",
                source_function="qsharp.estimate physicalCounts (Azure default QEC)",
                output_file="ledger.json", measured_or_derived="measured_output",
                calibration_used="no",
                independent="no (physical estimate of the shared abstract circuit)")
            add(instance=inst, tool="C_qsharp", metric="runtime_s",
                input_file="run.py (B ledger T_base/R tuple)",
                source_function="qsharp.estimate physicalCounts (Azure default QEC)",
                output_file="ledger.json", measured_or_derived="measured_output",
                calibration_used="no",
                independent="no (physical estimate of the shared abstract circuit)")
        if d is not None:
            add(instance=inst, tool="D_naive", metric="t_total",
                input_file="B ledger",
                source_function="run_naive (counts Clifford+T, ignores rotations)",
                output_file="ledger.json", measured_or_derived="derived",
                calibration_used="no", independent="no (derived from B's counts)")

        # 归一化预测（论文 Table 1 T_total）
        add(instance=inst, tool="normalization",
            metric="T_pred = T_base + R*c_cal(1e-10)",
            input_file="ledger.json (B counts + MEASURED_C)",
            source_function="CanonicalLedger.reconcile / T_total_at_ref",
            output_file="ledger.json / sweep_full.csv",
            measured_or_derived="derived",
            calibration_used="yes",
            independent="no (uses calibration constant c_cal=103)")
        add(instance=inst, tool="validation",
            metric="calibration_residual",
            input_file="ledger.json",
            source_function="reconcile attribution_residual",
            output_file="ledger.json",
            measured_or_derived="derived",
            calibration_used="yes",
            independent=f"no (residual of the anchored identity; T_A={a['T'] if a else '?'}, pred={r['T_total_at_ref']})")

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"[written] {OUT} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
