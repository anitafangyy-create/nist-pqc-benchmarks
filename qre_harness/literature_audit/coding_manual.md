# Literature Audit — Coding Manual

Codes are assigned per *public information in the paper itself* (main text + appendices +
supplement). The audit evaluates **reporting transparency**, not research quality and not
tool reliability. "U" must never be silently treated as "N": if the source is inaccessible or
internally contradictory, code U and record why.

## 1. `epsilon_code` — does the paper state the rotation-synthesis precision?

| Code | Definition |
|---|---|
| Y | Reports a synthesis precision ε (e.g. ε = 10⁻⁶), or a configuration that uniquely determines it (synthesizer + accuracy parameter). |
| N | Relevant information absent from main text and appendices, and the estimate is not rotation-free. |
| P | Reports a precision-like quantity that fixes ε only under additional assumptions (e.g. an error budget with unspecified per-rotation split). |
| U | Cannot be determined (source inaccessible, paywall, or internally contradictory). |
| NA | Rotation synthesis is not part of the audited estimate (e.g. no rotations reported; distillation-only; experiment). |

## 2. `rotation_code` — does the paper decompose abstract rotations into T gates?

| Code | Definition |
|---|---|
| Y | Abstract Rz/phase rotations are explicitly decomposed into Clifford+T and the resulting T-count is included in the headline number. |
| P | Rotations are mentioned/counted separately but not folded into the T-count; or decomposition is partial (some rotation families only). |
| N | Rotations are neither decomposed nor separately counted, yet the estimate claims to be a T-count. |
| U | Cannot be determined from the paper. |
| NA | No abstract rotations in the estimate (e.g. Toffoli-based oracle count only; experiment). |

## 3. `comparability_code` — can a reader reconstruct a cross-tool comparable T-count?

This is the four-level code at the core of §5. It answers: *given only what the paper makes
public, can the reader reproduce the estimate under a fixed counting convention (base T + R·c(ε)
with stated ε, or an equivalent fully-specified convention)?*

| Code | Definition |
|---|---|
| Y | The paper supplies enough information (counting convention, rotation count/profile, precision, per-rotation cost or its source) to reconstruct the estimate under an explicit target convention. |
| P | Conversion is possible only under additional assumptions (e.g. adopting a default ε, or a default synthesizer cost) not stated in the paper. |
| N | The information present is insufficient for the defined conversion (missing precision, missing rotation decomposition, or incompatible resource level without a stated mapping). |
| U | Evidence cannot be determined (inaccessible source, contradiction). |
| NA | Not an algorithm-level resource-estimation estimate (excluded from statistics). |

Note: P counts as "partially comparable", NOT as "comparable" in the strict headline rate.
Strict rate = Y / included; permissive rate = (Y + P) / included; U bounds computed in
`audit_sensitivity.py`.

## 4. Fields per paper

`paper_id, identifier, included, epsilon_code, rotation_code, comparability_code,
evidence_location, evidence_quote, reviewer_1, reviewer_2, resolution, exclusion_reason`

- `identifier`: arXiv ID or publisher DOI.
- `included`: TRUE for the 22-paper statistical sample.
- `evidence_location`: section/table where the audited number appears (verbatim section
  headings or table numbers where possible).
- `evidence_quote`: short verbatim quote carrying the coded information, when available;
  `—` if the coded evidence is a section-level judgment rather than a quotable phrase.
- `reviewer_1` / `reviewer_2`: two independent coding passes (same coder, second pass blind
  to first; disagreements recorded in `resolution`).
- `resolution`: how a disagreement between passes was resolved.
- `exclusion_reason`: required iff `included=False`.

## 5. Anti-patterns

- Do NOT code U as N. Do NOT code NA as "does not report".
- Do NOT use the tool a paper *mentions* to infer a precision it never states.
- Do NOT mark P as comparable in the strict rate.
- If a number appears only in an appendix, that counts as reported (Y) — the code is about
  public information, not prominence.
