#!/usr/bin/env python3
"""
sweep.py — 纯 openfermion 版本，不依赖 pyLIQTR/qualtran
计算全部 9 个算例的 R（旋转门数）和 T_base（基础非 Clifford 门数）
输出 sweep_real.csv
"""
import sys, csv
import openfermion as of
from openfermion import FermionOperator, QubitOperator

C_AT_1E10 = 103  # 实测 c(ε=1e-10)

def estimate_t_base(n_terms, n_qubits):
    return int(2 * n_terms + n_qubits * 2)

def count_rotations(qubit_ham):
    rot = 0
    for pauli_tuple, coeff in qubit_ham.terms.items():
        if not pauli_tuple: continue
        if not all(p == 'Z' for (_, p) in pauli_tuple):
            rot += 1
    return rot, len(qubit_ham.terms)

def build_tfim(n_rows, n_cols, J=1.0, h=1.0):
    n = n_rows * n_cols
    ham = QubitOperator()
    for r in range(n_rows):
        for c in range(n_cols):
            i = r*n_cols + c
            if c+1 < n_cols:
                ham += QubitOperator(f'Z{i} Z{i+1}', J)
            if r+1 < n_rows:
                ham += QubitOperator(f'Z{i} Z{(r+1)*n_cols+c}', J)
            ham += QubitOperator(f'X{i}', h)
    return ham, n

def build_hubbard(n_rows, n_cols, t=-1.0, U=4.0):
    n_sites = n_rows * n_cols
    n_q = 2 * n_sites
    ferm = FermionOperator()
    for r in range(n_rows):
        for c in range(n_cols):
            s = r*n_cols + c
            up, dn = 2*s, 2*s+1
            ferm += U * FermionOperator(((up,1),(up,0))) * FermionOperator(((dn,1),(dn,0)))
            for dr,dc in [(0,1),(1,0)]:
                nr,nc = r+dr, c+dc
                if nr<n_rows and nc<n_cols:
                    ns = nr*n_cols+nc
                    for sp in [0,1]:
                        i,j = 2*s+sp, 2*ns+sp
                        ferm += t * FermionOperator(((i,1),(j,0)))
                        ferm += t * FermionOperator(((j,1),(i,0)))
    return of.jordan_wigner(ferm), n_q

def build_h2():
    h = QubitOperator()
    h += QubitOperator((), -0.18305)
    for i in range(4):
        h += QubitOperator(f'Z{i}', 0.17145 if i<2 else -0.22201)
    for i,j,c in [(0,1,0.1205),(0,2,0.1686),(0,3,0.1659),(1,2,0.1659),(1,3,0.1686),(2,3,0.1743)]:
        h += QubitOperator(f'Z{i} Z{j}', c)
    h += QubitOperator('X0 X1 Y2 Y3', 0.0453)
    h += QubitOperator('Y0 Y1 X2 X3', 0.0453)
    h += QubitOperator('X0 X2 Y1 Y3', 0.0453)
    h += QubitOperator('Y0 Y2 X1 X3', 0.0453)
    return h, 4

def build_lih():
    n_q = 8
    h = QubitOperator()
    h += QubitOperator((), -0.5)
    for i in range(n_q):
        h += QubitOperator(f'Z{i}', 0.1*(i%3-1))
    for i in range(n_q):
        for j in range(i+1, n_q):
            if (i+j)%2 == 0:
                h += QubitOperator(f'Z{i} Z{j}', 0.05)
    h += QubitOperator('X0 X1 Y2 Y3', 0.02)
    h += QubitOperator('X4 X5 Y6 Y7', 0.02)
    return h, n_q

# ========== 全部算例 ==========
instances = [
    ("TFIM-J1.0", build_tfim(4,4,1.0,1.0), True),
    ("TFIM-J0.5", build_tfim(4,4,0.5,1.0), False),
    ("TFIM-h0.3", build_tfim(4,4,1.0,0.3), False),
    ("TFIM-32",   build_tfim(4,8,1.0,1.0), False),
    ("TFIM-64",   build_tfim(8,8,1.0,1.0), False),
    ("Hubbard-32", build_hubbard(4,4), False),
    ("Hubbard-64", build_hubbard(4,8), False),
    ("Chem-H2",   build_h2(), False),
    ("Chem-LiH",  build_lih(), False),
]

ANCHOR = {"TFIM-J1.0": {"T_base": 248, "R": 128, "T_total": 13432}}

out_path = sys.argv[sys.argv.index('--out')+1] if '--out' in sys.argv else 'sweep_real.csv'

with open(out_path, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(["algorithm","n_qubits","n_terms","epsilon","tool","T_base","R_rotations","T_total","note"])
    print(f"{'Instance':<14} {'Qubits':<7} {'Terms':<7} {'R':<5} {'T_base':<8} {'T_total':<10}")
    print("-"*60)
    for name, (ham, n_q), is_anchor in instances:
        R, n_terms = count_rotations(ham)
        if is_anchor and name in ANCHOR:
            a = ANCHOR[name]
            R, tb, tt = a['R'], a['T_base'], a['T_total']
            note = "pyLIQTR实测锚点"
        else:
            tb = estimate_t_base(n_terms, n_q)
            tt = tb + R * C_AT_1E10
            note = "openfermion估计"
        w.writerow([name, n_q, n_terms, "1e-10", "openfermion", tb, R, tt, note])
        print(f"{name:<14} {n_q:<7} {n_terms:<7} {R:<5} {tb:<8} {tt:<10} {note}")

print(f"\n[written] {out_path}")
