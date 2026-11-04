# nist-pqc-benchmarks

Code and data for the manuscript

> **When Are Fault-Tolerant T-Counts Comparable Across Tools? A Normalization Protocol and Literature Audit**

(submitted to *Quantum Science and Technology*).

This repository accompanies the paper and contains everything needed to reproduce
its quantitative claims: the normalization ledger, the microbenchmarks and
calibration data, the literature-audit coding table, the independent full-circuit
synthesis runs, and the second compiler stack (Qiskit Ross–Selinger) end-to-end
verification. The manuscript itself (DOCX / PDF / figures / review notes) is kept
**outside** this repository — see [Manuscript separation](#manuscript-separation).

## What the paper does, in one paragraph

Different fault-tolerant resource-estimation workflows count T gates under
different conventions: some decompose rotations into T gates at a given precision,
others report abstract rotation counts, and yet others mix logical and physical
levels. The paper introduces a **normalization protocol**,

```
T_total(ε) = T_base + R · c(ε),
```

which makes T-counts comparable across tools, and evaluates it with a
cross-tool instance matrix, a 30-paper literature audit of how rotation costs
are counted, and independent full-circuit verification.

Selected results (see the manuscript for the complete account):

| Result | Value |
|---|---|
| Apparent cross-tool T-count discrepancy before normalization | up to **54.2×** |
| Discrepancy after normalization, three independent synthesizers (pyLIQTR `rz_decomp` vs Qiskit Ross–Selinger vs GridSynth) | **≤ 2.4%** |
| Model-consistency MAPE at ε = 10⁻¹⁰ | **1.85%** |
| Audited literature sample | 30 papers (22 included), coded under five reporting conventions |
| Instances in the normalization study | 18 instances across 5 families (plus 10 full circuits in the independent audit) |

> These are the numbers as reported in the manuscript; the "apparent" discrepancy
> is the naive cross-tool spread **before** normalization and is *not* a claim of
> cross-compiler verification.

## Repository layout

| Path | Contents |
|---|---|
| [`qre_harness/`](qre_harness/README.md) | Main experiment harness: normalization ledger, ε-sweep, rotation-cost calibration, held-out prediction, dual-synthesizer comparison, literature audit, gate tests. |
| `qre_harness/p04_full_circuit_independent.py` / `.json` / `.csv` | Independent full-circuit synthesis (T_indep = 7·n_Toffoli + Σᵢ cᵢ(θᵢ,εᵢ)) across 10 circuits: QFT-8/16, QPE-7, PhaseGradient-8, Adder-8/16, Comparator-8/16, ANDTree-8, Hybrid Adder-8 ∥ QFT-8 (25 qubits). Fully reproducible (fixed random seed). |
| `qre_harness/p05_qiskit_rs_endtoend.py` / `.json` / `.csv` | Second compiler stack: Qiskit 2.6.1 with the Ross–Selinger solver (independent Rust implementation, arXiv:1403.2975) run end-to-end on the same 10 circuits. |
| `qre_harness/literature_audit/` | Authoritative coding table `literature_audit.csv`, `coding_manual.md`, `search_protocol.md`. |
| `qre_harness/tests/` | Three pure-stdlib gate tests: normalization identity, data lineage, no calibration leakage. |
| `crosscheck.py`, `mlkem_bench.py`, `sphincs_*.py`, `sphincsplus-master/` | **Legacy** NIST PQC cross-validation tooling from an earlier project; independent and standalone. |
| `LICENSE` | License file. |

## Environment

- Python 3.12.
- Pinned key dependencies (see `qre_harness/README.md` for the full recipe and known pitfalls):

```
numpy 1.26.4
cvxpy 1.4.3
qiskit 2.6.1
pyliqtr 1.4.2
qualtran 0.4.0
cirq-core 1.4.0
openfermion 1.7.0
pygridsynth 2.0.0
qsharp 1.31.0
numba 0.61.2 / llvmlite 0.44.0
gmpy2 2.3.2
```

> Pin `numpy==1.26.4` and `cvxpy==1.4.3` **before** installing anything else;
> floating upgrades break the pygridsynth/numba and cvxpy `coo_backend` chains.

The gate tests and audit statistics below use only the Python standard library and
run without installing the heavy quantum packages.

## Quick start

```bash
# 1) Gate tests (no external packages required)
python qre_harness/tests/test_normalize.py
python qre_harness/tests/test_data_lineage.py
python qre_harness/tests/test_no_calibration_leakage.py

# 2) Data lineage gate: CSV × HTML × measured JSON consistency
python qre_harness/verify_data.py

# 3) Literature-audit statistics: five coding conventions (strict / applicable /
#    permissive / upper bound / decidable subset) recomputed from the authoritative CSV
python qre_harness/audit_sensitivity.py
python qre_harness/audit_stats.py

# 4) Redraw the audit bar chart from the CSV (outputs figure2_audit.png)
python qre_harness/draw_figure2.py
```

## Reproducing the full verification

With the pinned environment installed:

```bash
# Independent full-circuit synthesis (pyLIQTR-based; reproducible, fixed seed)
python qre_harness/p04_full_circuit_independent.py

# Second compiler stack end-to-end (Qiskit 2.6.1 Ross–Selinger)
python qre_harness/p05_qiskit_rs_endtoend.py
```

Both scripts write `.json` and `.csv` outputs that feed the manuscript's
cross-compiler consistency claims (three synthesizers converge; Toffoli-dominated
families match exactly, rotation-dominated families agree to ≤ 2.4%).

## Key data files (under `qre_harness/`)

| File | Role |
|---|---|
| `ledger.json` | Normalized resource-estimate ledger for the instance matrix (authoritative data source). |
| `calibration.json`, `c_microbenchmark_*.json`, `stats_calibration.json` | Per-rotation cost calibration, multi-seed 100-angle microbenchmark, bootstrap statistics. |
| `heldout_stats.json`, `heldout_predictions.csv` | Held-out prediction errors (anchor instance excluded from validation statistics). |
| `gridssynth_microbenchmark.json`, `gridssynth_per_angle.csv` | Dual-synthesizer (pyLIQTR `rz_decomp` vs GridSynth) per-angle comparison. |
| `p04_full_circuit_independent.json/.csv` | Independent full-circuit synthesis results (10 circuits). |
| `p05_qiskit_rs_endtoend.json/.csv` | Qiskit Ross–Selinger second-stack results (same 10 circuits). |
| `literature_audit/literature_audit.csv` | 30-record audit coding table (22 included resource-estimate papers). |

## Manuscript separation

The following are **excluded from version control** by `.gitignore` and physically
kept in `../paper_manuscript/`:

- manuscript files: `*.docx`, `*.doc`, `*.pdf`, `*.html`, `*.svg`, `*.url`;
- run logs: `*_out*.txt`, `*_err*.txt`;
- packaged snapshots: `*.zip`;
- local environment and caches: `.venv-qre/`, `.preview/`, `__pycache__/`.

Before pushing, verify nothing manuscript-related is staged:

```bash
git ls-files | grep -iE '\.(docx|pdf|html|svg|url)$'   # expected: no output
```

## Citing

If you use this repository or the protocol in your work, please cite the manuscript:

```bibtex
@article{fang2026tcounts,
  title   = {When Are Fault-Tolerant T-Counts Comparable Across Tools?
             A Normalization Protocol and Literature Audit},
  author  = {Fang, Yuanyuan and Zhang, Zhenyu and Zheng, Ernest},
  journal = {Quantum Science and Technology},
  year    = {2026},
  note    = {submitted}
}
```

## License

See [`LICENSE`](LICENSE).
