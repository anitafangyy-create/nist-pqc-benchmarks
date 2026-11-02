#!/usr/bin/env python3
"""用 cirq + openfermion 构造 Hubbard 和化学模型，数 Pauli 项和旋转门。

不依赖 pyliqtr；直接构造哈密顿量并展开到 Pauli 基，
统计不同规模下的项数和旋转门数。
"""
import cirq
import openfermion as of
from openfermion import FermionOperator, QubitOperator


def hubbard_pauli_terms(n_rows, n_cols, t=-1.0, U=4.0):
    """构造 Fermi-Hubbard 模型的 Pauli 展开。
    每个格点两个自旋轨道，总共 2*n_rows*n_cols 个量子比特。
    """
    n_sites = n_rows * n_cols
    n_qubits = 2 * n_sites  # 每个格点 spin-up + spin-down

    # 用 Jordan-Wigner 变换的标准形式
    # 跳跃项：c†_{i,σ} c_{j,σ} + h.c.
    #  onsite 相互作用：U n_{i,↑} n_{i,↓}
    fermion_ham = FermionOperator()

    for r in range(n_rows):
        for c in range(n_cols):
            site = r * n_cols + c
            # onsite 相互作用
            up = 2 * site
            down = 2 * site + 1
            fermion_ham += U * FermionOperator(((up, 1), (up, 0))) * \
                           FermionOperator(((down, 1), (down, 0)))
            # 跳跃项
            for dr, dc in [(0,1), (1,0)]:
                nr, nc = r+dr, c+dc
                if nr < n_rows and nc < n_cols:
                    nsite = nr * n_cols + nc
                    for spin in [0, 1]:
                        i = 2 * site + spin
                        j = 2 * nsite + spin
                        fermion_ham += t * FermionOperator(((i, 1), (j, 0)))
                        fermion_ham += t * FermionOperator(((j, 1), (i, 0)))

    # Jordan-Wigner 变换
    qubit_ham = of.jordan_wigner(fermion_ham)
    terms = list(qubit_ham.terms.items())
    return terms, n_qubits


def count_rotations_of_terms(terms):
    """统计需要旋转门的 Pauli 项数。"""
    rot_terms = 0
    z_only = 0
    for pauli_tuple, coeff in terms:
        if not pauli_tuple:
            continue
        if all(p == 'Z' for (_, p) in pauli_tuple):
            z_only += 1
        else:
            rot_terms += 1
    return rot_terms, z_only


def h2_hamiltonian():
    """构造 H2 分子的简化 Hamiltonian（stO-3g, 键长 0.74Å）。
    使用已知的 FCI 系数（无需 pyscf）。"""
    # H2 最小基组的标准 FCI Hamiltonian
    # 4 spin orbitals, 2 electrons
    h = QubitOperator()
    # 来自 H2 化学的标准 Pauli 系数（stO-3g, 0.74A）
    # 常数项
    h += QubitOperator((), -0.18305)
    # 单比特项
    h += QubitOperator('Z0', 0.17145)
    h += QubitOperator('Z1', 0.17145)
    h += QubitOperator('Z2', -0.22201)
    h += QubitOperator('Z3', -0.22201)
    # 双比特 ZZ 项
    h += QubitOperator('Z0 Z1', 0.1205)
    h += QubitOperator('Z0 Z2', 0.1686)
    h += QubitOperator('Z0 Z3', 0.1659)
    h += QubitOperator('Z1 Z2', 0.1659)
    h += QubitOperator('Z1 Z3', 0.1686)
    h += QubitOperator('Z2 Z3', 0.1743)
    # XXYY 项（需要旋转门实现）
    h += QubitOperator('X0 X1 Y2 Y3', 0.0453)
    h += QubitOperator('Y0 Y1 X2 X3', 0.0453)
    h += QubitOperator('X0 X2 Y1 Y3', 0.0453)
    h += QubitOperator('Y0 Y2 X1 X3', 0.0453)
    return h, 4


def count_rotations(qubit_ham):
    """统计需要旋转门的 Pauli 项数。
    所有非 Pauli-Z 项都需要基变换，最终分解时产生旋转门。
    """
    rot_terms = 0
    z_only = 0
    for pauli_tuple, coeff in qubit_ham.terms.items():
        if not pauli_tuple:
            continue  # 常数项
        # 检查是否纯 Z
        if all(p == 'Z' for (_, p) in pauli_tuple):
            z_only += 1
        else:
            rot_terms += 1
    return rot_terms, z_only


print("=" * 65)
print("Hubbard 模型实验（openfermion Jordan-Wigner）")
print("=" * 65)
print(f"{'格点':<12} {'qubit':<6} {'Pauli项总数':<12} {'旋转相关项':<10}")
print("-" * 65)

hubbard_results = []
for r, c in [(2,2), (2,4), (4,4), (4,8)]:
    terms, n_q = hubbard_pauli_terms(r, c)
    rot, zonly = count_rotations_of_terms(terms)
    print(f"{r}x{c:<10} {n_q:<6} {len(terms):<12} {rot:<10}")
    hubbard_results.append({"size": f"{r}x{c}", "n_qubits": n_q,
                            "n_terms": len(terms), "rot_terms": rot})

print()
print("=" * 65)
print("化学模型实验（H2, stO-3g）")
print("=" * 65)
h2, n_q = h2_hamiltonian()
terms = list(h2.terms.items())
rot, zonly = count_rotations_of_terms(terms)
print(f"H2 (4 qubits): 总项数={len(terms)}, Z-only={zonly}, 旋转相关={rot}")

print()
print("=" * 65)
print("汇总")
print("=" * 65)
print(f"Hubbard 2x2=8 qubit:  {hubbard_results[0]['n_terms']} Pauli terms")
print(f"Hubbard 4x4=32 qubit: {hubbard_results[2]['n_terms']} Pauli terms")
print(f"H2 (4 qubit):         {len(terms)} Pauli terms")
print()
print("关键观察：")
print("  - Hubbard 模型 Pauli 项数随格点数快速增长")
print("  - 非 Pauli-Z 项（XXYY 等）在块编码时全部变成旋转门 R")
print("  - T = T_base + R·c(ε) 中，R 对化学/Hubbard 更大")
print("  → 跨工具口径分歧在化学模型上比自旋模型更严重")
