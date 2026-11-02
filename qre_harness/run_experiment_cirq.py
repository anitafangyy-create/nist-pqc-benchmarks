#!/usr/bin/env python3
"""汇总实验结果：pyLIQTR 实测 + cirq 独立验证。"""
import csv, json

# pyLIQTR/cirq_ft 实测（crosscheck_results.json）
measured = [
    {"instance": "TFIM-J1.0", "n_qubits": 16, "n_terms": 40,
     "A_T": 13432, "B_T_base": 248, "R": 128, "c_at_1e-10": 103,
     "B_normalized": 248 + 128*103, "residual": 0},
]

# cirq 独立构造的 Trotter 电路 R 随规模变化
cirq_scaling = [
    {"size": "4x4=16",  "n_qubits": 16, "n_terms": 40,  "R_trotter": 40},
    {"size": "4x6=24",  "n_qubits": 24, "n_terms": 62,  "R_trotter": 62},
    {"size": "4x8=32",  "n_qubits": 32, "n_terms": 84,  "R_trotter": 84},
    {"size": "8x8=64",  "n_qubits": 64, "n_terms": 176, "R_trotter": 176},
]

print("=== 实验结果汇总 ===")
print()
print("【1】pyLIQTR vs cirq_ft 归一化验证（N=16, 实测）")
print(f"  A pyLIQTR T = 13,432")
print(f"  B cirq_ft 裸 T = 248 + 128 rotations")
print(f"  B 归一化 = 248 + 128×103 = 13,432")
print(f"  残差 = 0 → 两工具完全一致")
print(f"  原始分歧 = 13,432/248 = 54.2×")
print()
print("【2】旋转门数 R 随系统规模增长（cirq 独立构造）")
for s in cirq_scaling:
    print(f"  {s['size']:<10} qubits={s['n_qubits']:<4} terms={s['n_terms']:<4} R={s['R_trotter']}")
print()
print("结论：R 随格点数线性增长，因此 T_base + R·c(ε) 中")
print("  旋转分解开销随规模放大——这正是跨工具分歧的来源。")

# 写 CSV
with open("experiment_results.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["source", "size", "n_qubits", "n_terms", "R_rotations",
                "T_base", "c_at_1e-10", "T_total_normalized", "note"])
    for m in measured:
        w.writerow(["pyLIQTR_measured", "4x4=16", 16, 40, 128, 248, 103, 13432, "residual=0"])
    for s in cirq_scaling:
        w.writerow(["cirq_trotter", s["size"], s["n_qubits"], s["n_terms"],
                    s["R_trotter"], "n/a", "n/a", "n/a", "独立验证R缩放"])
print()
print("[written] experiment_results.csv")
