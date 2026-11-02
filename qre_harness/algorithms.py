"""算法实例注册表。

每个算法返回一个 (block_encoding, n_qubits, n_terms)，供四个工具适配器读取。
新增算法：写一个 build_*() 并注册到 ALGORITHMS。

已对接（pyLIQTR 真实 API，见 ProblemInstances 文档）：
  - Transverse_Field_Ising(J, h, g, shape=(r,c))   自旋模型，shape 控规模
  - fermionic_models.FermiHubbard(shape=(r,c), J, U)  费米哈伯德，每格点 2 自旋
  - ChemicalHamiltonian(mol_ham)                      分子哈密顿量（openfermion）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any, Optional


@dataclass
class AlgorithmResult:
    name: str
    block_encoding: Any
    n_qubits: int
    n_terms: int


def _safe_n_terms(inst: Any) -> int:
    """不同 ProblemInstance 的项数接口略有差异，做防御性回退。"""
    from pyLIQTR.BlockEncodings import VALID_ENCODINGS
    try:
        return int(inst.n_terms(VALID_ENCODINGS.PauliLCU))
    except Exception:  # noqa: BLE001
        try:
            return int(inst.n_terms())
        except Exception:  # noqa: BLE001
            return 0


def _pauli_lcu(inst: Any):
    from pyLIQTR.BlockEncodings.PauliStringLCU import PauliStringLCU
    return PauliStringLCU(inst)


# ---------------------------------------------------------------------------
# 自旋模型：TFIM（已有）+ 可缩放格点规模
# ---------------------------------------------------------------------------
def _build_spin_lattice(name: str, shape: tuple, **kw) -> AlgorithmResult:
    from pyLIQTR.ProblemInstances.spin_models import Transverse_Field_Ising as TFI
    inst = TFI(shape=shape, **kw)
    enc = _pauli_lcu(inst)
    return AlgorithmResult(
        name=name, block_encoding=enc,
        n_qubits=inst.n_qubits(), n_terms=_safe_n_terms(inst),
    )


def build_tfim_j10() -> AlgorithmResult:
    return _build_spin_lattice("TFIM-J1.0", shape=(4, 4), J=1.0, g=-1.0)


def build_tfim_j05() -> AlgorithmResult:
    return _build_spin_lattice("TFIM-J0.5", shape=(4, 4), J=0.5, g=-1.0)


def build_tfim_h03() -> AlgorithmResult:
    return _build_spin_lattice("TFIM-h0.3", shape=(4, 4), J=1.0, g=-1.0, h=0.3)


def build_tfim_32() -> AlgorithmResult:
    """8×4 格点 = 32 比特，用于规模扫描。"""
    return _build_spin_lattice("TFIM-32", shape=(8, 4), J=1.0, g=-1.0)


def build_tfim_64() -> AlgorithmResult:
    """8×8 格点 = 64 比特，用于规模扫描。"""
    return _build_spin_lattice("TFIM-64", shape=(8, 8), J=1.0, g=-1.0)


# ---------------------------------------------------------------------------
# 费米哈伯德模型（每格点上下两个自旋，qubit 数 = 2 × 格点数）
# ---------------------------------------------------------------------------
def _build_hubbard(name: str, shape: tuple, U: float = 4.0, t: float = -1.0) -> AlgorithmResult:
    from pyLIQTR.ProblemInstances.fermionic_models import FermiHubbard
    inst = FermiHubbard(shape=shape, J=t, U=U)
    enc = _pauli_lcu(inst)
    return AlgorithmResult(
        name=name, block_encoding=enc,
        n_qubits=inst.n_qubits(), n_terms=_safe_n_terms(inst),
    )


def build_hubbard_32() -> AlgorithmResult:
    """4×4 格点 × 2 自旋 = 32 比特。"""
    return _build_hubbard("Hubbard-32", shape=(4, 4))


def build_hubbard_64() -> AlgorithmResult:
    """8×4 格点 × 2 自旋 = 64 比特。"""
    return _build_hubbard("Hubbard-64", shape=(8, 4))


# ---------------------------------------------------------------------------
# 化学哈密顿量（H2 / LiH）：需 openfermion + openfermionpyscf
# ---------------------------------------------------------------------------
def _build_molecule(name: str, geometry: list, basis: str = "sto-3g") -> AlgorithmResult:
    from pyLIQTR.ProblemInstances.ChemicalHamiltonian import ChemicalHamiltonian
    try:
        from openfermion import MolecularData
        from openfermionpyscf import run_pyscf
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"化学算例需 pip install openfermionpyscf pyscf：{exc}"
        )
    mol = MolecularData(geometry, basis, multiplicity=1, charge=0)
    mol = run_pyscf(mol, run_scf=1, run_fci=0)
    inst = ChemicalHamiltonian(mol.get_molecular_hamiltonian(), mol_name=name)
    enc = _pauli_lcu(inst)
    return AlgorithmResult(
        name=name, block_encoding=enc,
        n_qubits=inst.n_qubits(), n_terms=_safe_n_terms(inst),
    )


def build_chem_h2() -> AlgorithmResult:
    geom = [("H", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 0.74))]
    return _build_molecule("Chem-H2", geom)


def build_chem_lih() -> AlgorithmResult:
    geom = [("Li", (0.0, 0.0, 0.0)), ("H", (0.0, 0.0, 1.5))]
    return _build_molecule("Chem-LiH", geom, basis="sto-3g")


# ---------------------------------------------------------------------------
# 族外独立实例：QPE-7（量子相位估计，非 PauliLCU 家族）
# 结构与九实例完全不同的电路族：旋转主导（对角 oracle + inverse QFT 的受控相位
# 网络）、无 Toffoli（T_base=0），打破 LCU 家族 T_base = 2R − 8 的结构规律。
# 工具 A/B 的适配器均接受任意 cirq 电路（estimate_resources / t_complexity），
# 因此该实例直接复用现有工具链。
# ---------------------------------------------------------------------------
QPE_ANGLES = [0.1234567, 0.31415926, 0.52359877,
              0.69314718, 0.87396487, 1.04719755]  # 与微基准角度族同源


def _qpe_circuit(n_data: int, angles: list) -> Any:
    import cirq
    import numpy as np

    q = cirq.LineQubit.range(n_data + 1)
    ctrl, data = q[0], q[1:]
    circ = cirq.Circuit()
    circ.append(cirq.H(ctrl))
    # oracle: 受控对角相位（每数据 qubit 一个受控相位旋转）
    for qubit, th in zip(data, angles):
        circ.append(cirq.CZPowGate(exponent=th / np.pi).on(ctrl, qubit))
    # inverse QFT：受控相位阶梯 + swap 网络（全 Clifford/rotation，无 Toffoli）
    n = n_data
    for i in range(n // 2):
        circ.append(cirq.SWAP(data[i], data[n - 1 - i]))
    for j in range(n):
        for k in range(j):
            circ.append(cirq.CZPowGate(exponent=-2.0 / 2 ** (j - k + 1)).on(data[j], data[k]))
        circ.append(cirq.H(data[j]))
    return circ


def build_qpe_7() -> AlgorithmResult:
    """QPE-7：6 数据 qubit + 1 控制 qubit = 7 qubit；R = 6 oracle + 15 iQFT = 21。"""
    circ = _qpe_circuit(6, QPE_ANGLES)
    return AlgorithmResult(name="QPE-7", block_encoding=circ, n_qubits=7, n_terms=0)


# ---------------------------------------------------------------------------
# P0-2 新增电路族（2026-11-02）：结构独立于 PauliLCU 家族的整电路实例
# 目的：跨电路族泛化验证 + 压力测试
#   - Arithmetic（加法器/比较器/AND树）：Toffoli 主导，R≈0 → 压力端 A（T_base ≫ R·c）
#   - QFT：特殊（dyadic）角度密集，无 Toffoli → 压力端 B（T_base ≪ R·c）
#   - Phase Gradient：重复 dyadic 角度
# 全部为 cirq 电路，走工具 A（pyLIQTR 完整编译）/ B（cirq_ft t_complexity）。
# ---------------------------------------------------------------------------
def _cuccaro_adder(n: int) -> cirq.Circuit:
    """Cuccaro et al. 2004 ripple-carry adder：a + b，和写入 a 位。
    MAJ/UMA 各用 1 Toffoli + 2 CNOT，n-bit 共 2n Toffoli，R = 0。"""
    import cirq
    q = cirq.LineQubit.range(2 * n + 1)  # a[0..n-1], b[n..2n-1], carry=q[2n]
    c = cirq.Circuit()
    carry = q[2 * n]
    # MAJ 阶段（进位传播）
    for i in range(n):
        a, b = q[i], q[n + i]
        c.append(cirq.CNOT(a, b))
        c.append(cirq.CNOT(a, carry))
        c.append(cirq.TOFFOLI(b, carry, a))
    # UMA 阶段（求和 + 还原）
    for i in reversed(range(n)):
        a, b = q[i], q[n + i]
        c.append(cirq.CNOT(carry, a))
        c.append(cirq.CNOT(a, b))
        c.append(cirq.TOFFOLI(b, a, carry))
    return c


def _comparator(n: int) -> cirq.Circuit:
    """n-bit 比较器：flag = (a < b)，逐位 Toffoli 链，R = 0。"""
    import cirq
    q = cirq.LineQubit.range(2 * n + 1)
    c = cirq.Circuit()
    flag = q[2 * n]
    for i in reversed(range(n)):
        c.append(cirq.X(q[i]))
        c.append(cirq.TOFFOLI(q[i], q[n + i], flag))
        c.append(cirq.X(q[i]))
    return c


def _and_tree(n: int) -> cirq.Circuit:
    """n 输入 AND 树（n 为 2 的幂）：log2(n) 层 Toffoli，R = 0。"""
    import cirq
    q = cirq.LineQubit.range(2 * n - 1)  # 叶子在前 n 位，内部节点在后
    c = cirq.Circuit()
    level = list(range(n))
    idx = n
    while len(level) > 1:
        nxt = []
        for j in range(0, len(level), 2):
            c.append(cirq.TOFFOLI(q[level[j]], q[level[j + 1]], q[idx]))
            nxt.append(idx)
            idx += 1
        level = nxt
    return c


def _qft(n: int) -> cirq.Circuit:
    """n-qubit QFT：受控相位阶梯（dyadic 特殊角）+ H，无 Toffoli。"""
    import cirq
    q = cirq.LineQubit.range(n)
    c = cirq.Circuit()
    for j in range(n):
        for k in range(j):
            c.append(cirq.CZPowGate(exponent=2.0 / 2 ** (j - k + 1)).on(q[j], q[k]))
        c.append(cirq.H(q[j]))
    return c


def _phase_gradient(n: int) -> cirq.Circuit:
    """n-qubit phase-gradient state prep：Rz(2π/2^k) per qubit + H（重复 dyadic 角）。"""
    import cirq
    import numpy as np
    q = cirq.LineQubit.range(n)
    c = cirq.Circuit()
    for k in range(n):
        c.append(cirq.rz(2.0 * np.pi / 2 ** (k + 1)).on(q[k]))
        c.append(cirq.H(q[k]))
    return c


def _reg_circuit(name: str, n_qubits: int, circ: cirq.Circuit) -> AlgorithmResult:
    return AlgorithmResult(name=name, block_encoding=circ, n_qubits=n_qubits, n_terms=0)


def build_adder_8() -> AlgorithmResult:
    return _reg_circuit("Adder-8", 17, _cuccaro_adder(8))


def build_adder_16() -> AlgorithmResult:
    return _reg_circuit("Adder-16", 33, _cuccaro_adder(16))


def build_comparator_8() -> AlgorithmResult:
    return _reg_circuit("Comparator-8", 17, _comparator(8))


def build_comparator_16() -> AlgorithmResult:
    return _reg_circuit("Comparator-16", 33, _comparator(16))


def build_andtree_8() -> AlgorithmResult:
    return _reg_circuit("ANDTree-8", 15, _and_tree(8))


def build_qft_8() -> AlgorithmResult:
    return _reg_circuit("QFT-8", 8, _qft(8))


def build_qft_16() -> AlgorithmResult:
    return _reg_circuit("QFT-16", 16, _qft(16))


def build_phase_gradient_8() -> AlgorithmResult:
    return _reg_circuit("PhaseGradient-8", 8, _phase_gradient(8))


ALGORITHMS: dict[str, Callable[[], AlgorithmResult]] = {
    # 已有基线
    "TFIM-J1.0": build_tfim_j10,
    "TFIM-J0.5": build_tfim_j05,
    "TFIM-h0.3": build_tfim_h03,
    # 规模扫描（R 随格点数增长）
    "TFIM-32": build_tfim_32,
    "TFIM-64": build_tfim_64,
    "Hubbard-32": build_hubbard_32,
    "Hubbard-64": build_hubbard_64,
    # 化学（旋转谱与自旋模型不同）
    "Chem-H2": build_chem_h2,
    "Chem-LiH": build_chem_lih,
    # 族外独立实例（非 PauliLCU 家族，打破 T_base=2R-8）
    "QPE-7": build_qpe_7,
    # P0-2 新增：Arithmetic（Toffoli 主导，压力端 A）
    "Adder-8": build_adder_8,
    "Adder-16": build_adder_16,
    "Comparator-8": build_comparator_8,
    "Comparator-16": build_comparator_16,
    "ANDTree-8": build_andtree_8,
    # P0-2 新增：QFT / Phase Gradient（特殊角，压力端 B）
    "QFT-8": build_qft_8,
    "QFT-16": build_qft_16,
    "PhaseGradient-8": build_phase_gradient_8,
}
