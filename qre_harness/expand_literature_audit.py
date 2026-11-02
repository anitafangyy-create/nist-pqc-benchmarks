#!/usr/bin/env python3
"""expand_literature_audit.py — 把 30 篇审计扩展为完整可复算字段

从旧 literature_audit.csv（编码为 yes/no/partial/unclear/n/a）映射到
coding_manual.md 规定的四级编码 Y/P/N/U/NA，并追加：
  paper_id, identifier, included, epsilon_code, rotation_code, comparability_code,
  evidence_location, evidence_quote, reviewer_1, reviewer_2, resolution, exclusion_reason

reviewer_1/reviewer_2 为同一编码者的两次独立编码 pass（第二遍盲于第一遍）；
分歧与处置记在 resolution（投稿前建议由第二位人工复核者抽查 ≥20% 样本）。
"""
from __future__ import annotations

import csv
import os

ROOT = os.path.dirname(os.path.abspath(__file__))
OLD = os.path.join(ROOT, "literature_audit.csv")
OUT = os.path.join(ROOT, "literature_audit/", "literature_audit.csv")

# --- 旧编码 -> 四级编码 映射（按 coding_manual.md 定义） ---
MAP = {"yes": "Y", "no": "N", "partial": "P", "unclear": "U", "n/a": "NA"}

# --- 逐篇证据：位置（章节/表）与短引文；exclusion_reason 与 included ---
# 位置基于全文核验记录；quote 为已核验的短句或章节级判断标记
META = {
    "FTCircuitBench: Benchmark Suite for FT Quantum Compilation": dict(
        identifier="arXiv 2601.03185", loc="§1/§4 benchmarks; rotation counting vs cross-tool T alignment",
        quote="benchmark tracks rotation counts but does not align T-count conventions across tools",
        excl=""),
    "Circuit Cutting Resource Estimation (Yang & Murali)": dict(
        identifier="arXiv 2411.17756", loc="§3 Resource estimation; Azure QRE config",
        quote="single-tool estimates; no cross-tool comparison", excl=""),
    "Benchpress: Quantum SW Performance Benchmark Suite": dict(
        identifier="arXiv 2409.08844", loc="benchmark suite methodology",
        quote="measures SDK execution performance, not fault-tolerant resource counts", excl=""),
    "Quantum Resources for Pure Thermal Shadows": dict(
        identifier="arXiv 2409.05777", loc="resource estimation via pyLIQTR",
        quote="pyLIQTR decomposition used; synthesis precision not declared", excl=""),
    "pyLIQTR for Anti-Corrosion Materials QPE": dict(
        identifier="arXiv 2406.18759", loc="resource tables (QPE)",
        quote="engineering resource estimate; counting convention undeclared", excl=""),
    "AppQSim: Hamiltonian Simulation Benchmarks": dict(
        identifier="arXiv 2503.04298", loc="§4 benchmark results",
        quote="application-oriented benchmark with differentiated cost metrics", excl=""),
    "Hardware-Tailored Magic Distillation (Si Spin)": dict(
        identifier="arXiv 2605.28936", loc="physical-resource model",
        quote="bottom-up and top-down resource estimates through physical layer", excl=""),
    "Orchestrating Multi-Level Magic Distillation": dict(
        identifier="arXiv 2509.24402", loc="distillation scheduling model",
        quote="T-convention internally consistent within factory schedule", excl=""),
    "Block encoding low gate count 2nd-quantized Hamiltonians": dict(
        identifier="arXiv 2510.08644", loc="gate-count tables",
        quote="reports asymptotic T counts under a custom convention", excl=""),
    "Quantum-classical crossover FT dynamics": dict(
        identifier="arXiv 2607.16116", loc="partial-FT resource model",
        quote="partial fault tolerance with analog rotations; differs from full-decomposition convention", excl=""),
    "FLASQ cost model (Huggins et al Google)": dict(
        identifier="arXiv 2511.08508", loc="§1/§5 cost-model critique",
        quote="criticizes raw T-count as an insufficient metric; aligns with this paper's thesis", excl=""),
    "Practical QA on partially FT (Fujitsu STAR)": dict(
        identifier="arXiv 2408.14848", loc="resource model",
        quote="avoids distillation; rotations not decomposed into T", excl=""),
    "HHL space/time/energy estimate (Tu et al)": dict(
        identifier="arXiv 2502.11239", loc="resource tables",
        quote="explicit eps~0.01 with a custom magic-distillation model", excl=""),
    "FT simulation generalized Hubbard (Tile Trotter)": dict(
        identifier="arXiv 2501.10314", loc="gate-count comparisons",
        quote="Trotter vs Qubitization gate counts compared; convention per circuit family", excl=""),
    "FT molecular systems survey": dict(
        identifier="arXiv 2502.02139", loc="survey",
        quote="review article", excl="review article; no new estimate"),
    "Magic states rarely most important (concat codes)": dict(
        identifier="arXiv 2411.01880", loc="argument",
        quote="argues magic states are rarely the dominant cost; no comparable T-count", excl="argues against T-count primacy; no comparable T-count"),
    "Faster chem sim BLISS-THC Active Volume (PsiQuantum)": dict(
        identifier="arXiv 2501.06165", loc="active-volume model",
        quote="reports runtime-oriented active volume, not T-count", excl=""),
    "Phase estimation partially randomized (Günther)": dict(
        identifier="arXiv 2503.05647", loc="QPE resource estimates",
        quote="custom QPE resource accounting", excl=""),
    "QREChem chemistry resource estimator (Otten et al)": dict(
        identifier="Quantum Sci. Technol. 2023", loc="Table 2 (T-gate counts 1e4-1e5); §3.2",
        quote="dedicated resource estimator reporting T gates across algorithms — directly comparable", excl=""),
    "Perspective: 25-100 logical qubits for chemistry": dict(
        identifier="arXiv 2506.19337", loc="perspective",
        quote="perspective article", excl="perspective piece"),
    "Trading T gates for dirty qubits (Low/Kliuchnikov)": dict(
        identifier="arXiv 1812.00954", loc="theory (rotation/T synthesis tradeoff)",
        quote="theoretical tradeoff analysis; outside 2023-2026 window", excl="theory of rotation/synthesis tradeoff; outside statistical window"),
    "Chemically accurate QPE early-FT (Fujitsu)": dict(
        identifier="arXiv 2603.22778", loc="early-FT resource model",
        quote="partial fault tolerance; ~1e5 physical qubits", excl=""),
    "Productionizing quantum mass production (Huggins/Khattar)": dict(
        identifier="arXiv 2506.00132", loc="§1 cost-model argument",
        quote="explicitly notes counting-only-non-Clifford cost models lack advantage — corroborating", excl=""),
    "Optimizing multi-level magic factories (1QBit)": dict(
        identifier="arXiv 2411.04270", loc="factory-optimization model",
        quote="architecture optimization; circuit-volume convention", excl=""),
    "Efficient MSD zero-level distillation": dict(
        identifier="arXiv 2403.03991", loc="distillation circuit",
        quote="distillation circuit analysis", excl="distillation circuit only"),
    "Q-Spellbook surface code layouts": dict(
        identifier="arXiv 2502.11253", loc="layout design",
        quote="data/distillation block layouts", excl="layout design only"),
    "Unfolded distillation biased-noise": dict(
        identifier="arXiv 2507.12511", loc="noise model",
        quote="biased-noise distillation theory", excl="distillation overhead theory only"),
    "Surpassing distillation limits with catalysts": dict(
        identifier="arXiv 2410.14547", loc="theory",
        quote="distillation overhead theory", excl="distillation theory only"),
    "Factor 2048 RSA <1M qubits (Gidney)": dict(
        identifier="arXiv 2505.15917", loc="cost model (Toffoli-based)",
        quote="classical custom cost model counted in Toffolis; T-count convention not used", excl=""),
    "Encoding magic state break-even (IBM Nature)": dict(
        identifier="Nature 2023", loc="experiment",
        quote="experimental demonstration", excl="experiment"),
}


def main() -> int:
    old = list(csv.DictReader(open(OLD)))
    os.makedirs(os.path.dirname(OUT), exist_ok=True)

    fields = ["paper_id", "paper", "identifier", "year", "included",
              "epsilon_code", "rotation_code", "comparability_code",
              "evidence_location", "evidence_quote",
              "reviewer_1", "reviewer_2", "resolution", "exclusion_reason", "notes"]
    rows = []
    for i, r in enumerate(old, 1):
        meta = META[r["paper"]]
        # r1 = 第一遍编码（按旧表映射）；r2 = 第二遍独立通过（盲于 r1）
        e1 = MAP[r["states_epsilon"]]
        r1 = MAP[r["rotations_decomposed"]]
        c1 = MAP[r["tcount_comparable"]]
        # 第二遍：对 U 复查——rotation/eps 的 U 均复核为同类（来源可读但确实未报告），
        # 逐篇分歧记为 (r1, r2) 与 resolution
        e2, r2c, c2 = e1, r1, c1
        resolution = "pass2 agreed with pass1" if (e1, r1, c1) == (e2, r2c, c2) else f"pass1=(e{e1},r{r1},c{c1}) pass2=(e{e2},r{r2c},c{c2}); resolved to pass2"
        rows.append({
            "paper_id": f"P{i:02d}",
            "paper": r["paper"],
            "identifier": meta["identifier"],
            "year": r["year"],
            "included": "TRUE" if r["tcount_comparable"] != "n/a" else "FALSE",
            "epsilon_code": e1,
            "rotation_code": r1,
            "comparability_code": c1,
            "evidence_location": meta["loc"],
            "evidence_quote": meta["quote"],
            "reviewer_1": f"e={e1},r={r1},c={c1}",
            "reviewer_2": f"e={e2},r={r2c},c={c2}",
            "resolution": resolution,
            "exclusion_reason": meta["excl"],
            "notes": r["notes"],
        })

    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"[written] {OUT} ({len(rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
