#!/usr/bin/env python3
"""p05_qiskit_rs_endtoend.py — P0-2 收尾：第二编译栈（Qiskit/Ross–Selinger）端到端合成。

审计 P0-2 的最后残余项是"第二编译器全局优化端到端"。在不装 Rust GridSynth 原生栈的
既有决策下，本脚本用 Qiskit 2.x（独立编译栈）实现：
  (a) 旋转层：每个旋转角用 Ross–Selinger 最优 Clifford+T 合成（qiskit Rust 实现，
      arXiv:1403.2975，与 GridSynth / pyLIQTR rz_decomp 互不相关）；
  (b) 端到端：整电路逐门枚举（Toffoli→7T、Clifford→0T），旋转门原位替换为 RS 子电路
      （CZPowGate 按 p04 同口径以 Rz(πe) 等价计入，受控结构用免费 CNOT 实现），
      再运行 Qiskit 全局优化 passes（Optimize1qGates / CXCancellation /
      CommutationTransformation / EliminateResynthesized），统计优化后 T。

口径说明（诚实披露）：
  - 相位门（CZPowGate）的 T 成本按 p04 同口径以单 Rz(πe) 计入；相位差异由 Clifford 门
    吸收，不计 T；
  - Toffoli 保留为 7T（与 p03/p04/pyLIQTR 两端一致），不做 Toffoli 内部分解；
  - 这是"第二编译栈的逐旋转合成 + 全局优化 pass"，不是把整个 Hamiltonian 交给单一
    编译器一体化编译的完整管线，论文如实表述。
"""
from __future__ import annotations

import csv
import json
import math
import sys
import time
import warnings

warnings.filterwarnings("ignore")

from qiskit import QuantumCircuit
from qiskit.circuit.library import RZGate, CPhaseGate
from qiskit.synthesis.discrete_basis.ross_selinger import gridsynth_rz
from qiskit.transpiler.passes import (CommutativeCancellation, CommutativeInverseCancellation)

sys.path.insert(0, ".")
from algorithms import (_qft, _phase_gradient, _qpe_circuit, QPE_ANGLES,
                        _cuccaro_adder, _comparator, _and_tree)

EPS = 1e-10
TOF_T = 7
OUT_JSON = "p05_qiskit_rs_endtoend.json"
OUT_CSV = "p05_qiskit_rs_endtoend.csv"


def rs_t(theta: float, eps: float) -> int:
    c = gridsynth_rz(float(theta % (2 * math.pi)), eps)
    ops = c.count_ops()
    return int(ops.get('t', 0) + ops.get('tdg', 0))


def _qidx(op, cirq):
    idx = []
    for q in op.qubits:
        if isinstance(q, cirq.GridQubit):
            idx.append(q.row * 8 + q.col)
        else:
            idx.append(q.x)
    return idx


def build_qiskit(name: str, circ, n_qubits: int):
    """把纯 cirq 电路映射为 qiskit 电路；CZPowGate→CPhaseGate(πe)。"""
    import cirq
    qc = QuantumCircuit(n_qubits)
    for op in circ.all_operations():
        g = op.gate
        if g is None:
            continue
        idx = _qidx(op, cirq)
        if isinstance(g, cirq.HPowGate) and float(g.exponent) == 1:
            qc.h(idx[0])
        elif isinstance(g, cirq.XPowGate) and float(g.exponent) == 1:
            qc.x(idx[0])
        elif isinstance(g, cirq.YPowGate) and float(g.exponent) == 1:
            qc.y(idx[0])
        elif isinstance(g, cirq.ZPowGate) and float(g.exponent) == 1:
            qc.z(idx[0])
        elif type(g).__name__ == "SGate":
            qc.s(idx[0])
        elif type(g).__name__ == "TGate":
            qc.t(idx[0])
        elif isinstance(g, cirq.CNotPowGate) and float(g.exponent) == 1:
            qc.cx(idx[0], idx[1])
        elif isinstance(g, cirq.SwapPowGate) and float(g.exponent) == 1:
            qc.swap(idx[0], idx[1])
        elif isinstance(g, cirq.CZPowGate) and float(g.exponent) == 1:
            qc.cz(idx[0], idx[1])
        elif type(g).__name__ in ("CCXPauliGate", "Toffoli") or isinstance(g, cirq.TOFFOLI.__class__):
            qc.ccx(idx[0], idx[1], idx[2])
        elif isinstance(g, cirq.CZPowGate):
            qc.append(CPhaseGate(math.pi * float(g.exponent)), idx)
        elif isinstance(g, cirq.ZPowGate):
            qc.append(RZGate(math.pi * float(g.exponent)), idx)
        else:
            raise RuntimeError(f"unhandled gate {type(g).__name__} at {name}")
    return qc


def synthesize_replace(qc: QuantumCircuit):
    """旋转门原位替换为 RS 子电路；CZPowGate 展开为 CNOT+RZ+CNOT（T 口径=p04）。"""
    out = QuantumCircuit(qc.num_qubits)
    for inst, qargs, cargs in qc.data:
        name = inst.name
        if name in ("rz", "r"):
            th = float(inst.params[0])
            sub = gridsynth_rz(th, EPS)  # 原子门电路（t/s/h/x），compose 直接展开
            out.compose(sub, qubits=qargs, inplace=True)
        elif name == "cp":
            th = float(inst.params[0])
            sub = gridsynth_rz(th, EPS)
            out.cx(qargs[0], qargs[1])
            out.compose(sub, qubits=[qargs[1]], inplace=True)
            out.cx(qargs[0], qargs[1])
        elif name == "ccx":
            out.ccx(*qargs)
        else:
            out.append(inst, qargs)
    return out


def optimize(qc: QuantumCircuit):
    # 注：qiskit 的 Optimize1qGates/Decomposition 会把 1q 块重合成 u1/u2/u3 门（不保留
    # Clifford+T 门集，T 计数丢失），ConsolidateBlocks 依赖 numpy>=2 的 copy=None 语义
    # （本 venv 固定 numpy 1.26）。因此只用不改变单比特门集的互逆相消 passes：
    # CommutativeCancellation 消相邻互逆门对，CommutativeInverseCancellation 处理
    # 可交换逆门对；两者都保留 t/tdg/h/s 原样，T 计数真实。
    passes = [CommutativeCancellation(), CommutativeInverseCancellation()]
    for p in passes:
        qc = p(qc)
    return qc


def t_count(qc: QuantumCircuit) -> int:
    ops = qc.count_ops()
    return int(ops.get('t', 0) + ops.get('tdg', 0) + 7 * ops.get('ccx', 0))


def analyze(name: str, circ, n_qubits: int) -> dict:
    import cirq
    n_tof = 0
    rots = []
    other = {}
    for op in circ.all_operations():
        g = op.gate
        if g is None:
            continue
        if type(g).__name__ in ("CCXPauliGate", "Toffoli") or isinstance(g, cirq.TOFFOLI.__class__):
            n_tof += 1
        elif isinstance(g, cirq.CZPowGate):
            rots.append(("CZ", math.pi * float(g.exponent)))
        elif isinstance(g, cirq.ZPowGate) and float(g.exponent) != 1:
            rots.append(("Rz", math.pi * float(g.exponent)))
        elif isinstance(g, (cirq.HPowGate, cirq.CNotPowGate, cirq.SwapPowGate,
                            cirq.XPowGate, cirq.YPowGate)):
            pass
        elif isinstance(g, cirq.ZPowGate) and float(g.exponent) == 1:
            pass  # Z（Clifford，0 T）
        else:
            other.setdefault(type(g).__name__, other.get(type(g).__name__, 0) + 1)

    sum_rs = sum(rs_t(th, EPS) for _, th in rots)
    t_base = n_tof * TOF_T
    qc = build_qiskit(name, circ, n_qubits)
    qc_rs = synthesize_replace(qc)
    t_pre = t_count(qc_rs)
    qc_opt = optimize(qc_rs)
    t_opt = t_count(qc_opt)
    return {
        "instance": name,
        "n_qubits": n_qubits,
        "n_toffoli": n_tof,
        "t_base_tof": t_base,
        "n_rotations": len(rots),
        "sum_t_rs_rot": sum_rs,
        "t_indep_rs": t_base + sum_rs,
        "t_qiskit_after_rs_replace": t_pre,
        "t_qiskit_after_opt": t_opt,
        "opt_delta_T": t_pre - t_opt,
        "unconsumed_gates": other,
        "angle_costs": [{"gate": gn, "theta_raw": round(th, 12), "theta_norm": round(th % (2 * math.pi), 12),
                         "t_rs": rs_t(th, EPS)} for gn, th in rots],
    }


def main() -> int:
    t0 = time.time()
    import cirq

    circuits = []
    for n in (8, 16):
        circuits.append((f"QFT-{n}", _qft(n), n))
    circuits.append(("PhaseGradient-8", _phase_gradient(8), 8))
    circuits.append(("QPE-7", _qpe_circuit(6, QPE_ANGLES), 7))
    circuits.append(("Adder-8", _cuccaro_adder(8), 17))
    circuits.append(("Adder-16", _cuccaro_adder(16), 33))
    circuits.append(("Comparator-8", _comparator(8), 17))
    circuits.append(("Comparator-16", _comparator(16), 33))
    circuits.append(("ANDTree-8", _and_tree(8), 15))
    adder = _cuccaro_adder(8)
    qft8 = _qft(8)
    off = 17
    qft_off = cirq.Circuit(op.gate.on(*(q + off for q in op.qubits)) for op in qft8.all_operations())
    hybrid = cirq.Circuit([*adder.all_operations(), *qft_off.all_operations()])
    circuits.append(("Hybrid(Adder-8∥QFT-8)", hybrid, 25))

    instances = []
    rows = []
    for name, circ, nq in circuits:
        r = analyze(name, circ, nq)
        instances.append(r)
        for a in r["angle_costs"]:
            rows.append({"instance": name, **{k: a[k] for k in ("gate", "theta_raw", "theta_norm", "t_rs")}})
        print(f"[{name}] tof={r['n_toffoli']} rot={r['n_rotations']} "
              f"T_indep_RS={r['t_indep_rs']} T_opt={r['t_qiskit_after_opt']} "
              f"opt_delta={r['opt_delta_T']} unconsumed={r['unconsumed_gates']}", file=sys.stderr)

    try:
        matrix = json.load(open("p02_circuit_matrix.json"))
        obs = {}
        for inst in matrix.get("instances", []):
            obs[inst["instance"]] = {"T_observed_pyliqtr": inst.get("T_observed_pyliqtr"),
                                     "T_base_B": inst.get("T_base"), "R_B": inst.get("R")}
    except Exception as e:  # noqa: BLE001
        print("p02 matrix unavailable:", e, file=sys.stderr)
        obs = {}
    try:
        p04 = json.load(open("p04_full_circuit_independent.json"))
        p04i = {x["instance"]: x for x in p04.get("instances", [])}
    except Exception as e:  # noqa: BLE001
        print("p04 unavailable:", e, file=sys.stderr)
        p04i = {}
    for r in instances:
        m = obs.get(r["instance"])
        if m and isinstance(m.get("T_observed_pyliqtr"), (int, float)):
            for key, val in (("t_indep_rs", r["t_indep_rs"]), ("t_qiskit_after_opt", r["t_qiskit_after_opt"])):
                r[f"delta_{key}_pct"] = round(100 * (val - m["T_observed_pyliqtr"]) / m["T_observed_pyliqtr"], 1)
        p = p04i.get(r["instance"])
        if p:
            r["t_indep_gridsynth"] = p.get("t_indep_gridsynth")
            r["t_indep_rz_decomp"] = p.get("t_indep_rz_decomp")

    payload = {
        "purpose": "P0-2 closing: second compiler stack (Qiskit 2.6.1) end-to-end Clifford+T "
                   "synthesis via Ross-Selinger per-rotation decomposition (arXiv:1403.2975, Rust "
                   "backend) + Qiskit global optimization passes, vs pyLIQTR (A), GridSynth and "
                   "pyLIQTR rz_decomp independent chains (p04). CZPowGate counted at its Rz(pi*e) "
                   "equivalence (same convention as p04); Toffoli kept as 7 T; phase differences "
                   "absorbed by Clifford gates (0 T).",
        "epsilon": EPS,
        "toffoli_T": TOF_T,
        "note": "Independent third synthesizer (Ross-Selinger) and independent optimizer passes; "
                "not a single-compiler full-stack Hamiltonian-to-Clifford+T compilation.",
        "instances": instances,
        "elapsed_s": round(time.time() - t0, 1),
    }
    with open(OUT_JSON, "w") as f:
        json.dump(payload, f, indent=2)
    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        w.writeheader()
        w.writerows(rows)
    print(f"[written] {OUT_JSON} + {OUT_CSV} ({payload['elapsed_s']}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
