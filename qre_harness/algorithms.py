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
}
