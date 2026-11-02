"""核心逻辑自测：不安装 pyLIQTR 也能跑。

用 crosscheck_results.json 里 TFIM-J1.0 的已知读数手造两个 ToolLedger，
跑 reconcile()，断言归一化结果复现 248 + 128*103 = 13432，残差为 0。
"""
from ledger import CanonicalLedger, ToolLedger, c_per_rotation, MEASURED_C


def main() -> None:
    # --- 1. c(ε) 校准点检查 ---
    assert c_per_rotation(1e-4, MEASURED_C) == 42, c_per_rotation(1e-4, MEASURED_C)
    assert c_per_rotation(1e-6, MEASURED_C) == 62
    assert c_per_rotation(1e-8, MEASURED_C) == 82
    assert c_per_rotation(1e-10, MEASURED_C) == 103
    print("[ok] c(ε) 校准点复现：42/62/82/103")

    # --- 2. 手造工具 A（pyLIQTR，已分解）与 B（cirq_ft，未分解）读数 ---
    ledger = CanonicalLedger(
        algorithm="TFIM-J1.0", n_qubits=16, n_terms=40, epsilon_ref=1e-10,
    )
    ledger.add_tool(ToolLedger(
        tool="B_cirqft", rotations_decomposed=False,
        T=248, rotations=128, Clifford=1146, logical_qubits=22,
    ))
    ledger.add_tool(ToolLedger(
        tool="A_pyliqtr", rotations_decomposed=True,
        T=13432, rotations=0, Clifford=27515, logical_qubits=22,
        epsilon_used=1e-10,
    ))

    s = ledger.reconcile()
    print("[ok] T_base =", s["T_base"], "(期望 248)")
    print("[ok] R =", s["R"], "(期望 128)")
    print("[ok] c(1e-10) =", s["c_per_rotation_at_ref"], "(期望 103)")
    print("[ok] T_total_at_ref =", s["T_total_at_ref"], "(期望 13432)")
    print("[ok] attribution_residual =", s["attribution_residual"], "(期望 0)")
    print("[ok] attribution_ok =", s["attribution_ok"])

    assert s["T_base"] == 248
    assert s["R"] == 128
    assert s["c_per_rotation_at_ref"] == 103
    assert s["T_total_at_ref"] == 13432
    assert s["attribution_residual"] == 0
    assert s["attribution_ok"] is True

    # --- 3. 一致性：B 按 A 口径分解应等于 A ---
    b_decomposed = 248 + 128 * 103
    assert b_decomposed == s["T_total_at_ref"] == 13432

    print("\n[PASS] 归一化核心复现 crosscheck_results.json，归因恒等式成立。")


if __name__ == "__main__":
    main()
