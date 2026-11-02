#!/usr/bin/env python3
"""P0-2 新增电路实例：跨电路族泛化验证汇总。

读取 p02_results/<instance>.json（run.py 输出，含 A/B/C/D 四工具读数），
计算模型预测 T_pred = T_base + R·c(1e-10)，与 pyLIQTR 完整编译 T_obs 对比，
输出 p02_circuit_matrix.json + 分电路族统计。

新增实例族（2026-11-02）：
  Arithmetic（Toffoli 主导，压力端 A：T_base ≫ R·c）
    Adder-8 / Adder-16 / Comparator-8 / Comparator-16 / ANDTree-8
  QFT（特殊 dyadic 角，压力端 B：T_base ≪ R·c）
    QFT-8 / QFT-16
  Phase Gradient（重复 dyadic 角）
    PhaseGradient-8
"""
from __future__ import annotations
import json, os, statistics

HERE = os.path.dirname(os.path.abspath(__file__))
RESULTS = os.path.join(HERE, "p02_results")
C_REF = 103  # c_cal(1e-10)，与 ledger.MEASURED_C 一致

INSTANCES = [
    ("Adder-8", "Arithmetic", "adder"),
    ("Adder-16", "Arithmetic", "adder"),
    ("Comparator-8", "Arithmetic", "comparator"),
    ("Comparator-16", "Arithmetic", "comparator"),
    ("ANDTree-8", "Arithmetic", "andtree"),
    ("QFT-8", "QFT", "qft"),
    ("QFT-16", "QFT", "qft"),
    ("PhaseGradient-8", "PhaseGradient", "phase_gradient"),
]


def load(name: str) -> dict:
    with open(os.path.join(RESULTS, f"{name}.json"), encoding="utf-8") as f:
        d = json.load(f)
    return d["results"][0]


def main() -> int:
    rows = []
    for name, family, kind in INSTANCES:
        r = load(name)
        tools = {t["tool"]: t for t in r["tools"]}
        A, B = tools["A_pyliqtr"], tools["B_cirqft"]
        t_base, R = int(r["T_base"]), int(r["R"])
        t_pred = t_base + R * C_REF
        t_obs = int(A["T"])
        are = abs(t_pred - t_obs) / t_obs * 100 if t_obs else None
        # 压力端判定
        if R == 0:
            regime = "A: T_base>>R*c"
        elif t_base == 0:
            regime = "B: T_base<<R*c"
        elif t_base / (R * C_REF) > 3:
            regime = "A-ish: T_base>>R*c"
        elif t_base / (R * C_REF) < 1 / 3:
            regime = "B-ish: T_base<<R*c"
        else:
            regime = "mixed"
        # 证据性质标注：R=0 时 A/B 是完整电路级读数一致（无旋转分解自由度）；
        # 含旋转时 pyLIQTR 的旋转计费来自其内置成本模型（与 c_ref 同源），
        # ARE=0 为模型自洽，特殊角真实合成成本需独立合成器复核（方案 P0-1 缺口）。
        if R == 0:
            caveat = "R=0：A/B 完整电路级读数一致（Toffoli 7T 口径），无旋转分解自由度，非模型循环"
        else:
            caveat = ("pyLIQTR 旋转计费与 c_ref 同源（estimate_resources 内置成本模型，seed 固定）；"
                      "ARE=0 为模型自洽，特殊角真实合成成本需独立合成器复核")
        rows.append({
            "instance": name, "family": family, "kind": kind,
            "n_qubits": int(r["n_qubits"]), "T_base": t_base, "R": R,
            "c_ref": C_REF, "T_predicted": t_pred, "T_observed_pyliqtr": t_obs,
            "ARE_pct": round(are, 4) if are is not None else None,
            "attribution_residual": int(r["attribution_residual"]),
            "attribution_ok": bool(r["attribution_ok"]),
            "regime": regime,
            "caveat": caveat,
            "clifford_A": int(A["Clifford"]), "clifford_B": int(B["Clifford"]),
            "A_note": A["note"], "B_note": B["note"],
        })

    out = {
        "protocol": {
            "source": "run.py --tools A,B,C,D @ epsilon_ref=1e-10",
            "t_observed": "A_pyliqtr estimate_resources 完整电路编译",
            "t_predicted": "T_base + R * c_cal(1e-10)=103（B_cirqft 读 T_base/R）",
            "c_ref": C_REF,
            "date": "2026-11-02",
            "observations": [
                "QFT-8/QFT-16：B（cirq_ft）将全部受控相位 CZPowGate(dyadic) 单列为 R（28/120），T_base=0，"
                "未识别任何特殊角；压力端 B（T_base<<R*c）实例建立",
                "PhaseGradient-8：B 对 Rz(2π/2^k) 识别 3 个特殊角（π→Z、π/2→S、π/4→T 计入 T_base=1），"
                "R=5；A（pyLIQTR）同识别（A.T=516=1+5*103），两工具特殊角识别一致",
                "Arithmetic 5 实例 R=0：A/B 完整电路级 T 完全一致（Toffoli 7T 口径），跨工具无歧义，"
                "压力端 A（T_base>>R*c）实例建立",
            ],
        },
        "instances": rows,
    }
    with open(os.path.join(HERE, "p02_circuit_matrix.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    # ---- 控制台汇总 ----
    hdr = f"{'instance':<16}{'family':<14}{'T_base':>7}{'R':>5}{'T_pred':>8}{'T_obs':>8}{'ARE%':>8}  {'regime':<20}{'ok'}"
    print(hdr)
    print("-" * len(hdr))
    for row in rows:
        print(f"{row['instance']:<16}{row['family']:<14}{row['T_base']:>7}{row['R']:>5}"
              f"{row['T_predicted']:>8}{row['T_observed_pyliqtr']:>8}"
              f"{row['ARE_pct'] if row['ARE_pct'] is not None else 'n/a':>8}  {row['regime']:<20}{row['attribution_ok']}")

    # 分族统计
    print("\n=== 分电路族统计（模型预测 vs pyLIQTR 完整编译）===")
    fams = {}
    for row in rows:
        fams.setdefault(row["family"], []).append(row)
    for fam, rs in fams.items():
        ares = [r["ARE_pct"] for r in rs if r["ARE_pct"] is not None]
        print(f"  {fam:<14} n={len(rs):>2}  MAPE={statistics.mean(ares):.4f}%  maxARE={max(ares):.4f}%"
              f"  residual==0: {sum(1 for r in rs if r['attribution_residual']==0)}/{len(rs)}")

    print("\n=== 压力端覆盖 ===")
    for reg in sorted({r["regime"] for r in rows}):
        n = sum(1 for r in rows if r["regime"] == reg)
        print(f"  {reg}: {n} 实例")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
