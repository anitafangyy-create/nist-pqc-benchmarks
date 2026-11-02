#!/usr/bin/env python3
"""统一 harness：输入算法名，跨工具跑资源估计，输出规范账本 JSON。

用法：
    python3 run.py --algorithm all --tools A,B,C,D --out ledger.json
    python3 run.py --algorithm TFIM-J1.0 --eps 1e-10

缺依赖的工具会被跳过并在 JSON 的 skipped 字段说明，不中断整体流程。
依赖安装：
    pip install pyliqtr cirq 2>/dev/null   # A/B
    pip install qsharp                       # C（另需补 QIR 导出）
"""
from __future__ import annotations

import argparse
import json
import sys

from ledger import CanonicalLedger, EPS_REF
from algorithms import ALGORITHMS
import tools as tool_mod


def run_one(algo_name: str, tool_keys: list[str], epsilon: float) -> dict:
    builder = ALGORITHMS[algo_name]
    try:
        ar = builder()  # type: ignore[misc]
    except Exception as exc:  # noqa: BLE001
        # 算法构造依赖缺失（如未装 pyliqtr）：记录为错误结果而非崩溃
        return {
            "algorithm": algo_name,
            "error": f"算法构造失败（依赖缺失？）: {exc}",
            "hint": "pip install pyliqtr cirq",
        }

    ledger = CanonicalLedger(
        algorithm=ar.name,
        n_qubits=ar.n_qubits,
        n_terms=ar.n_terms,
        epsilon_ref=epsilon,
    )
    skipped: list[dict] = []

    b_ledger = None
    for key in tool_keys:
        try:
            if key == "A":
                tl = tool_mod.run_pyliqtr(ar.block_encoding, epsilon=epsilon)
            elif key == "B":
                tl = tool_mod.run_cirqft(ar.block_encoding)
                b_ledger = tl
            elif key == "C":
                # C（Azure QRE）输入是实例的 Q# 抽象电路：(n_qubits, T_base, R)，
                # 其中 T_base/R 取工具 B 的电路级读数（同一抽象电路口径，独立栈复现）。
                # 若 B 未先跑（如 --tools C,D），隐式先取 B 读数。
                if b_ledger is None:
                    b_ledger = tool_mod.run_cirqft(ar.block_encoding)
                tl = tool_mod.run_qsharp(ar.n_qubits, int(b_ledger.T),
                                         int(b_ledger.rotations), epsilon=epsilon)
            elif key == "D":
                tl = tool_mod.run_naive(b_ledger)
            else:
                skipped.append({"tool": key, "reason": "未知工具代号"})
                continue
            ledger.add_tool(tl)
        except tool_mod.ToolUnavailable as exc:
            skipped.append({"tool": key, "reason": str(exc)})
        except Exception as exc:  # noqa: BLE001
            skipped.append({"tool": key, "reason": f"运行异常: {exc}"})

    summary = ledger.reconcile()
    summary["skipped"] = skipped
    return summary


def _to_native(o):
    """递归把 numpy 标量（int64/float64 等）转成 JSON 可序列化原生类型。"""
    if isinstance(o, dict):
        return {k: _to_native(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_to_native(v) for v in o]
    item = getattr(o, "item", None)
    if callable(item):
        try:
            return item()
        except Exception:  # noqa: BLE001
            pass
    if isinstance(o, (str, int, float, bool)) or o is None:
        return o
    return str(o)


def main() -> int:
    p = argparse.ArgumentParser(description="QRE 跨工具统一 harness")
    p.add_argument("--algorithm", default="all",
                    help="算法名（all 或：%s）" % ", ".join(ALGORITHMS))
    p.add_argument("--tools", default="A,B,C,D", help="逗号分隔工具代号 A,B,C,D")
    p.add_argument("--eps", type=float, default=EPS_REF, help="基准合成精度")
    p.add_argument("--out", default="-", help="输出 JSON 路径，- 为 stdout")
    args = p.parse_args()

    names = list(ALGORITHMS) if args.algorithm == "all" else [args.algorithm]
    tool_keys = [k.strip() for k in args.tools.split(",") if k.strip()]

    results = []
    for name in names:
        print(f"[run] {name} ...", file=sys.stderr)
        results.append(run_one(name, tool_keys, args.eps))

    payload = {"epsilon_ref": args.eps, "results": results}
    text = json.dumps(_to_native(payload), indent=2, ensure_ascii=False)

    if args.out == "-":
        print(text)
    else:
        with open(args.out, "w") as f:
            f.write(text)
        print(f"[written] {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
