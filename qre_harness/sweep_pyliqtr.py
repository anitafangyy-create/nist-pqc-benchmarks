#!/usr/bin/env python3
"""
sweep_pyliqtr.py — 真实 pyLIQTR 资源估计版
调用 pyLIQTR 的 ProblemInstances + BlockEncodings，对比 pyLIQTR vs cirq_ft 的 T 计数。

用法：
  python sweep_pyliqtr.py --out sweep_real.csv
"""
import sys, csv, warnings
warnings.filterwarnings('ignore')

import cirq

# ========== pyLIQTR 导入 ==========
try:
    from pyLIQTR.ProblemInstances.spin_models import Transverse_Field_Ising
    from pyLIQTR.BlockEncodings.PauliStringLCU import PauliStringLCU
    from pyLIQTR.gate_decomp.cirq_transforms import clifford_plus_t_direct_transform
    PYLIQTR_OK = True
    print("[ok] pyLIQTR imported")
except ImportError as e:
    PYLIQTR_OK = False
    print(f"[warn] pyLIQTR not available: {e}")
    print("       falling back to openfermion-only mode")

try:
    import cirq_ft
    CIRQ_FT_OK = True
    print("[ok] cirq_ft imported")
except ImportError as e:
    CIRQ_FT_OK = False
    print(f"[warn] cirq_ft not available: {e}")


def count_t_gates(circuit):
    """数电路里 T 门的数量。"""
    t_count = 0
    for moment in circuit:
        for op in moment:
            gate_name = str(op.gate)
            if 'T' in gate_name and 'Clifford' not in gate_name:
                t_count += 1
    return t_count


def count_rotations(circuit):
    """数电路里 Rz 旋转门的数量。"""
    rot_count = 0
    for moment in circuit:
        for op in moment:
            if 'Rz' in str(op.gate) or 'rx' in str(op.gate).lower():
                rot_count += 1
    return rot_count


# ========== 算例列表 ==========
instances = [
    ("TFIM-J1.0", "spin", {"shape": (4,4), "J": 1.0, "g": -1.0}),
    ("TFIM-J0.5", "spin", {"shape": (4,4), "J": 0.5, "g": -1.0}),
    ("TFIM-32",   "spin", {"shape": (4,8), "J": 1.0, "g": -1.0}),
    ("TFIM-64",   "spin", {"shape": (8,8), "J": 1.0, "g": -1.0}),
]

out_path = sys.argv[sys.argv.index('--out')+1] if '--out' in sys.argv else 'sweep_real.csv'

results = []

for name, kind, params in instances:
    print(f"\n--- {name} ---")
    row = {"instance": name, "n_qubits": "", "T_base": "", "R": "", "T_pyliqtr": "", "note": ""}

    if not PYLIQTR_OK:
        row["note"] = "pyLIQTR not installed"
        results.append(row)
        continue

    try:
        # 构建问题实例
        if kind == "spin":
            inst = Transverse_Field_Ising(
                shape=params["shape"],
                J=params["J"],
                g=params["g"]
            )
        else:
            row["note"] = "unknown kind"
            results.append(row)
            continue

        n_q = inst.n_qubits()
        row["n_qubits"] = n_q
        print(f"  qubits: {n_q}")

        # 构建 block encoding
        encoding = PauliStringLCU(inst)
        circuit = encoding.circuit
        print(f"  circuit moments: {len(circuit)}")

        # 数电路里的门类型分布
        gate_counts = {}
        for moment in circuit:
            for op in moment:
                g = str(op.gate)
                gate_counts[g] = gate_counts.get(g, 0) + 1
        print(f"  gate types: {len(gate_counts)}")
        for g, c in sorted(gate_counts.items(), key=lambda x:-x[1])[:5]:
            print(f"    {g}: {c}")

        T_base = count_t_gates(circuit)
        row["T_base"] = T_base
        print(f"  T_base (raw count): {T_base}")

        R = count_rotations(circuit)
        row["R"] = R
        print(f"  R rotations: {R}")

        # pyLIQTR 分解后的 T 计数（尝试不同参数名）
        try:
            decomposed = clifford_plus_t_direct_transform(circuit)
            T_pyliqtr = count_t_gates(decomposed)
            row["T_pyliqtr"] = T_pyliqtr
            print(f"  T_pyliqtr (decomposed): {T_pyliqtr}")
            row["note"] = "measured"
        except Exception as e:
            row["note"] = f"circuit built, decompose: {type(e).__name__}: {str(e)[:60]}"
            print(f"  decompose failed: {e}")

    except Exception as e:
        row["note"] = f"build failed: {e}"
        print(f"  build failed: {e}")

    results.append(row)


# ========== 写 CSV ==========
with open(out_path, 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=["instance","n_qubits","T_base","R","T_pyliqtr","note"])
    w.writeheader()
    for r in results:
        w.writerow(r)

print(f"\n[written] {out_path}")
print("\nDone. Send this CSV back for analysis.")
