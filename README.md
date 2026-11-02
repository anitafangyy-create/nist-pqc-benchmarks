# nist-pqc-benchmarks

Code and data for the fault-tolerant T-count normalization / cross-tool resource
estimate study, together with earlier NIST post-quantum cryptography (PQC)
benchmark tooling.

> **Repository scope:** this repository tracks **source code, small data files and
> documentation only**. The manuscript (DOCX / PDF / HTML), figures and review notes
> are maintained outside the repository under the sibling directory
> `../paper_manuscript/` and are never committed here (see *Manuscript separation*).

## Repository layout

| Path | Contents |
|---|---|
| `qre_harness/` | Main experiment harness: normalization ledger, microbenchmarks, calibration, held-out prediction, dual-synthesizer comparison, literature audit, gate tests. Detailed file map in [`qre_harness/README.md`](qre_harness/README.md). |
| `qre_harness/literature_audit/` | Authoritative coding table `literature_audit.csv`, `coding_manual.md`, `search_protocol.md`. |
| `qre_harness/tests/` | Three pure-stdlib gate tests: normalization identity, data lineage, no calibration leakage. |
| `crosscheck.py`, `mlkem_bench.py`, `sphincs_*.py`, `sphincs_crosscheck.*` | Earlier NIST PQC cross-validation scripts (optional, standalone). |
| `sphincsplus-master/` | Vendored SPHINCS+ reference C source; compiled binaries are ignored. |
| `LICENSE` | License file. |

## Environment

- Python 3.12 (project virtualenv: `.venv-qre/`, ignored by git).
- Pinned key dependencies for the QRE harness:

```
numpy 1.26.4
numba 0.61.2 / llvmlite 0.44.0
pyliqtr 1.4.2
qualtran 0.4.0
cirq-core 1.4.0
openfermion 1.7.0
pygridsynth 2.0.0
qsharp 1.31.0
gmpy2 2.3.2
```

The gate tests and audit statistics below use only the Python standard library and
run without installing the heavy quantum packages.

## Quick start

```bash
# 1) Gate tests (no external packages required)
python qre_harness/tests/test_normalize.py
python qre_harness/tests/test_data_lineage.py
python qre_harness/tests/test_no_calibration_leakage.py

# 2) Data lineage gate: CSV x HTML x measured JSON consistency
python qre_harness/verify_data.py

# 3) Literature-audit statistics: five coding conventions (strict / applicable /
#    permissive / upper bound / decidable subset) recomputed from the authoritative CSV
python qre_harness/audit_sensitivity.py
python qre_harness/audit_stats.py

# 4) Redraw the audit bar chart from the CSV (outputs figure2_audit.png)
python qre_harness/draw_figure2.py
```

## Key data files (under `qre_harness/`)

| File | Role |
|---|---|
| `ledger.json` | Normalized resource-estimate ledger for the instance matrix. |
| `calibration.json`, `c_microbenchmark_100.json`, `stats_calibration.json` | Per-rotation cost calibration, 100-angle microbenchmark, bootstrap statistics. |
| `heldout_stats.json`, `heldout_predictions.csv` | Held-out prediction errors (anchor instance excluded from validation statistics). |
| `gridssynth_microbenchmark.json`, `gridssynth_per_angle.csv` | Dual-synthesizer (rz_decomp vs GridSynth) per-angle comparison. |
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

## License

See [`LICENSE`](LICENSE).
