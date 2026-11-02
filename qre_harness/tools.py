"""四个工具适配器。

每个适配器接受一个"可估计资源的电路/块编码对象"，返回 ToolLedger。
依赖采用惰性导入：缺包时抛出 ToolUnavailable，由 run.py 统一跳过，不崩。

工具栈：
  A_pyliqtr : LLNL/USC  pyLIQTR.estimate_resources  （旋转门按 ε 分解）
  B_cirqft  : Google   cirq_ft.t_complexity          （旋转门单列，不分解）
  C_qsharp  : Microsoft Azure Quantum Resource Estimator（独立栈，本地 qsharp 包）
  D_naive   : 文献常用捷径——只数 Clifford+T、忽略旋转
"""
from __future__ import annotations

from typing import Any, Optional
from ledger import ToolLedger, EPS_REF


class ToolUnavailable(RuntimeError):
    """该工具依赖未安装/不可用，harness 应跳过。"""


# ---------------------------------------------------------------------------
# 工具 A：pyLIQTR（已在 crosscheck.py 验证）
# ---------------------------------------------------------------------------
def run_pyliqtr(block_encoding: Any, epsilon: float = EPS_REF) -> ToolLedger:
    try:
        from pyLIQTR.utils.resource_analysis import estimate_resources
    except Exception as exc:  # noqa: BLE001
        raise ToolUnavailable(f"pyLIQTR 未安装：{exc}")
    res = estimate_resources(block_encoding)
    return ToolLedger(
        tool="A_pyliqtr",
        rotations_decomposed=True,
        T=int(res["T"]),
        rotations=0,
        Clifford=int(res["Clifford"]),
        logical_qubits=int(res["LogicalQubits"]),
        epsilon_used=epsilon,
        note="旋转门已按 ε 分解进 T",
    )


# ---------------------------------------------------------------------------
# 工具 B：cirq_ft / Qualtran（已在 crosscheck.py 验证）
# ---------------------------------------------------------------------------
def run_cirqft(block_encoding: Any) -> ToolLedger:
    try:
        from cirq_ft import t_complexity
    except Exception as exc:  # noqa: BLE001
        # qualtran>=0.3 起 cirq_ft 并入 qualtran，t_complexity 移入 cirq_interop
        try:
            from qualtran.cirq_interop.t_complexity_protocol import t_complexity
        except Exception as exc2:  # noqa: BLE001
            raise ToolUnavailable(f"cirq_ft / qualtran 均未安装：{exc} / {exc2}")
    tc = t_complexity(block_encoding)
    return ToolLedger(
        tool="B_cirqft",
        rotations_decomposed=False,
        T=int(tc.t),
        rotations=int(tc.rotations),
        Clifford=int(tc.clifford),
        logical_qubits=0,
        epsilon_used=None,
        note="旋转门单列，未分解",
    )


# ---------------------------------------------------------------------------
# 工具 C：Azure Quantum Resource Estimator（开源 qsharp 包，本地跑）
# ---------------------------------------------------------------------------
_QRE_ROT_ANGLE = 0.1234567  # 代表性旋转角（RE 只计数不分解，角度不影响逻辑读数）


def _qsharp_program(n_qubits: int, t_base: int, rotations: int) -> str:
    """把实例四元组 (n_qubits, T_base, R) 生成 Q# 抽象电路程序。

    Azure QRE 的输入语言是 Q#（内部编译为 QIR 再走资源估算）。
    Q# 的 0..N 为闭区间，故循环上界取 T_base-1 / R-1；上界为 -1 时 0..-1 为空 range
    （正确处理 T_base=0 或 R=0 的实例，如族外 QPE：无 Toffoli、纯旋转）。
    """
    t_hi = t_base - 1
    r_hi = rotations - 1
    return f"""namespace QREBench {{
    operation Main() : Unit {{
        use q = Qubit[{n_qubits}];
        for i in 0..{t_hi} {{ T(q[i % {n_qubits}]); }}
        for r in 0..{r_hi} {{ Rz({_QRE_ROT_ANGLE}, q[r % {n_qubits}]); }}
    }}
}}"""


def run_qsharp(n_qubits: int, t_base: int, rotations: int,
               epsilon: float = EPS_REF) -> ToolLedger:
    """Azure QRE（qsharp 1.31，本地）跑实例的 Q# 抽象电路，返回逻辑级+物理级读数。

    接线说明（2026-10-25）：
      - Q# 是 Azure QRE 的输入语言（编译器内部生成 QIR 再估算）；本适配器从
        实例四元组 (n_qubits, T_base, R) 生成 Q# 抽象电路（T_base 个 T 门 +
        R 次任意角 Rz 旋转），经 qsharp.eval 载入、qsharp.estimate 估算。
      - logicalCounts：tCount / rotationCount / numQubits（旋转单列口径，
        与工具 B 同源可比——C 是独立栈复现）。
      - physicalCounts：physicalQubits / runtime / rqops（Azure 默认 QEC 配置，
        旋转合成进物理 T 工厂，是 B/D 不具备的物理级真数）。
      - 局限：输入为抽象电路而非 pyLIQTR 完整 PauliLCU 电路；旋转角度为代表性
        常数（RE 逻辑级只计数、不因角度不同而改变计数）。
    """
    try:
        import qsharp  # noqa: F401
    except Exception as exc:  # noqa: BLE001
        raise ToolUnavailable(f"qsharp 未安装（pip install qsharp）：{exc}")

    prog = _qsharp_program(n_qubits, t_base, rotations)
    try:
        qsharp.init(target_profile=qsharp.TargetProfile.Unrestricted)
        qsharp.eval(prog)
        r = qsharp.estimate("QREBench.Main()")
    except Exception as exc:  # noqa: BLE001
        raise ToolUnavailable(f"qsharp estimate 失败: {exc}")

    lc = r["logicalCounts"]
    pc = r["physicalCounts"]
    note = (
        "Azure QRE (qsharp) 独立栈：Q# 抽象电路(T_base×T + R×Rz)，"
        "逻辑级旋转单列；物理级 physicalQubits=%s, runtime=%s (默认 QEC 配置)"
    ) % (pc["physicalQubits"], pc["runtime"])
    return ToolLedger(
        tool="C_qsharp",
        rotations_decomposed=False,
        T=int(lc["tCount"]),
        rotations=int(lc["rotationCount"]),
        Clifford=0,
        logical_qubits=int(lc["numQubits"]),
        epsilon_used=None,
        note=note,
    )


# ---------------------------------------------------------------------------
# 工具 D：文献常用"裸 T-count"基线（不依赖任何包）
# ---------------------------------------------------------------------------
def run_naive(b_cirqft: Optional[ToolLedger] = None) -> ToolLedger:
    """模拟多数论文的捷径：只报 B 的 T（不含旋转门），即"忽略旋转"。

    直接复用 B 的读数，标注 rotations_decomposed=False 且 note 说明这是常见误读。
    """
    if b_cirqft is None:
        return ToolLedger(tool="D_naive", rotations_decomposed=False, T=0,
                          rotations=0, note="无 B 读数时为空基线")
    return ToolLedger(
        tool="D_naive",
        rotations_decomposed=False,
        T=int(b_cirqft.T),
        rotations=int(b_cirqft.rotations),
        Clifford=int(b_cirqft.Clifford),
        logical_qubits=0,
        note="文献捷径：只数 Clifford+T，旋转门不计入",
    )


ADAPTERS = {
    "A": run_pyliqtr,
    "B": run_cirqft,
    "C": run_qsharp,
    "D": run_naive,
}
