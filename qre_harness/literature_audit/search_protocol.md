# Literature Audit — Search Protocol

**Audit target:** whether published fault-tolerant resource-estimation papers expose enough
information for a reader to reconstruct a cross-tool comparable T-count (per the four-tuple
protocol of this paper).

**Scope:** sample of papers, not a systematic review of the entire field. Percentages reported
in §5 apply to this sample under the coding rules in `coding_manual.md`.

## Search platforms and dates

| Item | Value |
|---|---|
| Primary platform | arXiv (https://export.arxiv.org API; also arxiv.org search UI) |
| Secondary platforms | Google Scholar (title-level confirmation only), publisher pages (Nature / Quantum Sci. Technol. / PRX Quantum) for venue metadata |
| Search date | 2026-10-20 (UTC+8) |
| Search window | 2018–2026 (statistical sample restricted to 2023–2026 per protocol §exclusion; 2018 Low–Kliuchnikov included as background theory, excluded from statistics) |

## Search strings (as issued)

1. `fault-tolerant quantum resource estimation T-count`
2. `fault-tolerant quantum resource estimation rotation synthesis precision`
3. `quantum chemistry resource estimation T gates`
4. `magic state distillation resource estimation T count`
5. `quantum resource estimation benchmark T-count cross-tool`

Results were combined by relevance to the question "does the paper report resource estimates
whose T-count could be compared across tools", snowballed via citations of
FTCircuitBench / QREChem / pyLIQTR / Qualtran.

## Inclusion criteria

A paper enters the *candidate pool* if it:
- reports quantitative fault-tolerant resource estimates (T-count, Toffoli count,
  physical qubits, runtime, or magic-state cost) for a quantum algorithm; AND
- is written in English and publicly available (arXiv or published venue).

A paper enters the *statistical sample* (n = 22) if it additionally:
- falls in 2023–2026 for the primary comparison claims, OR is QREChem (2023, QST) which the
  paper's §5.5 discusses as the closest competitor; AND
- the estimate concerns algorithm-level logical/physical resources, i.e. it is a
  resource-estimation result rather than a hardware experiment, distillation-circuit-only
  analysis, or pure review.

## Exclusion reasons (8 papers, all recorded in literature_audit.csv `included=False`)

| paper | reason |
|---|---|
| FT molecular systems survey (2025) | review article; no new estimate |
| Magic states rarely most important (2024) | argues against T-count primacy; no comparable T-count |
| Perspective: 25–100 logical qubits (2025) | perspective piece |
| Trading T gates for dirty qubits (2018) | theory of rotation/synthesis tradeoff; outside 2023–2026 window |
| Efficient MSD zero-level distillation (2024) | distillation circuit only |
| Q-Spellbook surface code layouts (2025) | layout design only |
| Unfolded distillation biased-noise (2025) | distillation overhead theory only |
| Surpassing distillation limits with catalysts (2024) | distillation theory only |

## Deduplication

arXiv IDs checked against duplicates; venue versions (e.g. QREChem arXiv 2309.14727 →
published QST version) collapsed to one row each. No duplicate papers remained.

## Screening flow

1. Candidate pool assembled from search strings + citation snowball (≈45 candidates).
2. Title/abstract screen against inclusion criteria (≈45 → 36).
3. Full-text screen: only papers with an actual resource-estimate number kept (36 → 30).
4. Statistical-sample assignment per inclusion criteria (30 → 22 statistical, 8 excluded).

## Coding workflow

- Each paper read in full (arXiv full text or publisher page).
- Codes assigned per `coding_manual.md`; two independent passes (r1, r2) by the same coder,
  second pass blind to the first; disagreements resolved in `resolution`.
- Evidence recorded as `evidence_location` (section/table within the paper) and
  `evidence_quote` (short verbatim quote when available).
- Percentages recomputed by `audit_sensitivity.py`; the CSV is the single source of truth.
