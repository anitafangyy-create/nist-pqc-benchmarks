# qre_harness — 跨工具量子资源估计统一 harness

输入一个算法实例，统一调用 4 个资源估计工具，输出**归一化规范账本 JSON**。
服务于论文 *Fault-Tolerant T-Counts Are Not Cross-Tool Comparable*。

## 核心思想

不同工具对 T 门数的口径不同：
- **A pyLIQTR**：旋转门按精度 ε 分解进 T；
- **B cirq_ft/Qualtran**：旋转门单列、不分解；
- **C Azure QRE（qsharp）**：独立栈；逻辑级旋转单列（Q# 抽象电路，与 B 同口径），物理级给出 QEC 真数；
- **D naive**：文献常见"裸 T-count"捷径。

归一化恒等式（已被本项目实测验证）：

```
T_total(ε) = T_base + R · c(ε)
c(ε) ≈ 3 · log₂(1/ε)        # Ross–Selinger
```

对 TFIM：B 的 `248 T + 128 rotations` 按 ε=1e-10 补成
`248 + 128×103 = 13,432`，与 A 完全一致（残差 0）。

## 文件

| 文件 | 作用 | 是否依赖外部包 |
|---|---|---|
| `ledger.py` | 规范账本 + 归一化/归因核心 | 纯 Python（可单测） |
| `algorithms.py` | 算法注册表（TFIM 缩放 / Hubbard / 化学共 9 个） | 构造时需 pyliqtr |
| `tools.py` | 4 个工具适配器（惰性导入，缺包优雅跳过） | 各自按需 |
| `run.py` | CLI：跑矩阵、输出 JSON | — |
| `sweep.py` | ε 全网格 driver：算法×精度，输出长表 CSV（主图数据） | — |
| `make_figure.py` | 读 sweep 数据，生成论文主图 figure_main.html | 纯 Python |
| `literature_audit/literature_audit.csv` | **权威编码表**（30 篇，含 paper_id/included/Y-P-N-U-NA 五码/双审证据；论文 Table 8/9 唯一数据源） | — |
| `literature_audit.csv`（根目录） | 早期迁移用简表（旧 yes/no/partial schema），由 `expand_literature_audit.py` 映射为权威版，不再直接统计 | — |
| `audit_sensitivity.py` | 复算论文 Table 9 五口径（strict/applicable/permissive/upper/decidable），从权威 CSV 读取 | 无 |
| `audit_stats.py` | 输出论文 Table 8 strict 汇总（Y/22）+ 同向证据清单（§2.3 四篇） | 无 |
| `selftest.py` | 复现 248+128×103=13432 | 无 |
| `recompute_canonical.py` | **权威重算脚本**（口径统一阶段）：纯 Python 重算 9 实例 n_terms / R / T_base / T_total，注入实测锚点，带断言闸门 | 无 |
| `apply_measured.py` | **实测替换**：读 `ledger.json`，把 `sweep_full.csv` 全部行替换为 2026-10-25 实测值（含恒等式断言） | 无 |
| `regenerate_summaries.py` | 从 `ledger.json` + `sweep_full.csv` 派生 `experiment_results.csv`（9 实测A + 9 实测C + 8 估计参考）/ `sweep_real.csv`（9 行全实测） | 无 |
| `verify_data.py` | 7 组一致性闸门：CSV × 两份 HTML × ledger JSON（交付前必跑） | 无 |
| `ledger.json` | **实测账本（唯一当前权威数据源）**：9 实例 × A/B/D 实测 + C skipped（2026-10-25） | — |

## 数据口径（重要）

`R` 在仓库中曾有三种口径，**实测（2026-10-25）后 9 实例全部为 circuit-level 口径**：

| 口径 | 定义 | 数值（TFIM-16） | 状态 |
|---|---|---|---|
| **circuit-level**（实测） | cirq_ft/Qualtran t_complexity 的抽象旋转门数 | 128 | `sweep_full.csv` 全部 9 行（`status=measured`） |
| Hamiltonian-level（估计参考） | openfermion 非-Z Pauli 项数 | 16 | 仅 `experiment_results.csv` 的估计参考行（注明非实测） |
| Trotter-circuit（估计参考） | 每 Pauli 项 1 次旋转 | 40 | 仅方向性独立验证（`experiment_results.csv`） |

实测值与旧的 Hamiltonian-level 估计不可直接比较（TFIM-16：128 vs 16，≈8×；TFIM-32：256 vs 32）。
`n_terms` 实测口径为 pyLIQTR PauliLCU 编码项数（不含常数项）：Hubbard-32=144（含常数 145）、Chem-H2=14（15）、**Chem-LiH=630（旧 23 为合成占位假数据，真实 STO-3G 12-qubit）**。
权威数据源：`ledger.json`；替换入口：`python3 apply_measured.py`；派生汇总：`python3 regenerate_summaries.py`；验证：`python3 verify_data.py`。

## 实测环境与运行记录（2026-10-25）

本机（macOS x86_64，Python 3.12.1）venv：`.venv-qre/`（已 gitignore）。锁定版本：
`pyliqtr==1.4.2`、`qualtran==0.4.0`、`cirq-core==1.4.0`、`openfermion==1.7.0`、`qsharp==1.31.0`、`numba==0.61.2`、`llvmlite==0.44.0`、`numpy==1.26.4`、`cvxpy==1.4.3`、`pygridsynth==2.0.0`、`qiskit==2.6.1`、`openfermionpyscf==0.5`、`pyscf==2.14.0`、`gmpy2==2.3.2`、Julia 1.10.4（`/usr/local/Cellar/julia/1.10.4`）。

- **重建 venv 配方**：`llvmlite` 只能 `0.44.0` 配 `numba 0.61.2`（0.50 在 cp312+macOS x86_64 无预编译 wheel，源码编译失败；0.45 与 numba 冲突）。pip 索引：`https://mirrors.huaweicloud.com/repository/pypi/simple/`。
- **numpy/cvxpy 加装新包时禁止浮动**：qiskit 安装曾把 numpy 升到 2.5.4（破坏 pygridsynth/numba，numba 需 numpy≤2.2），随后 cvxpy 升级又破坏 numpy 1.26 的 `coo_backend`；最终必须 `numpy==1.26.4 + cvxpy==1.4.3`。qiskit 2.6.1 的部分 pass 依赖 numpy≥2 的 `np.array(copy=None)`（如 `ConsolidateBlocks`），在固定 numpy 1.26 下不可用——p05 只使用保留 Clifford+T 门集的互逆相消 passes（`CommutativeCancellation`/`CommutativeInverseCancellation`），不用会重合成 u/p 门的 1q 优化 pass。
- **pyliqtr patch（重装会丢）**：`pyLIQTR/ProblemInstances/ChemicalHamiltonian.py` 第 35 行 `juliapkg.require_julia("~1.8,~1.9")` 已改为 `"^1.10.3"`（对齐 juliacall 0.9.37），否则 juliapkg 报 "compat entries have empty intersection"。
- **Julia**：官方源下载极慢，用清华镜像 `julia-1.10.4-mac64.tar.gz`。沙箱运行时需把 `lib/julia/*.dylib` 复制进 sandbox_runtime lib 目录（否则 dlopen libgcc_s.1.1.dylib 失败），且该目录的 `libgmp.10.dylib` 已被 brew gmp 6.3.0 覆盖（否则 gmpy2 报 `___gmpz_prevprime` 符号缺失）。
- **执行命令**：`python3 run.py --algorithm all --tools A,B,C,D --out ledger.json`。9 实例 A/B/C/D 全部成功，恒等式 `T_base + R×103 = T_total` 残差 0。
- **工具 C 接线（2026-10-25 补全）**：Azure QRE 的输入语言是 Q#（编译器内部生成 QIR 再估算）。适配器从实例四元组 (n_qubits, T_base, R) 生成 Q# 抽象电路（T_base 个 T 门 + R 次任意角 Rz），经 `qsharp.eval` + `qsharp.estimate`（`TargetProfile.Unrestricted`）跑 Azure RE。逻辑级 `tCount`/`rotationCount` 与工具 B 完全一致（独立栈复现），物理级 `physicalQubits`/`runtime`（Azure 默认 QEC 配置）为 B/D 不具备的真数（TFIM-16: 772,330；Chem-LiH: 1,203,750）。局限：输入为抽象电路而非 pyLIQTR 完整 PauliLCU 电路；Q# 逻辑级不按 ε 分解旋转。代码：`tools.run_qsharp`（`_qsharp_program` 生成器）。
- 已知边界：`sweep_full.csv` 的 `c_at_1e-10=103` 来自 TFIM-16 实测校准（ε=1e-10），所有实例统一使用该值做归一化；ε 依赖 c(ε) 校准见 `sweep.py`。

## 用法

```bash
pip install pyliqtr cirq      # A/B
pip install qsharp            # C（另需补 QIR 导出，见 tools.run_qsharp 注释）

# 自测（无需任何外部包）
python3 selftest.py

# 跑全部已接算法、4 个工具
python3 run.py --algorithm all --tools A,B,C,D --out ledger.json

# 单个算法、指定基准精度
python3 run.py --algorithm TFIM-J1.0 --eps 1e-10
```

缺依赖的工具不会让程序崩溃，会写进输出里的 `skipped` 字段。

## 输出 schema（节选）

```json
{
  "epsilon_ref": 1e-10,
  "results": [{
    "algorithm": "TFIM-J1.0",
    "T_base": 248, "R": 128,
    "c_per_rotation_at_ref": 103,
    "T_total_at_ref": 13432,
    "attribution_residual": 0,
    "attribution_ok": true,
    "tools": [ ...每个工具原始读数... ],
    "skipped": [ ...未可用工具及原因... ]
  }]
}
```

## 已接算法（9 个，覆盖"R 随规模/算法变化"）

| 算法名 | 模型 | 规模 | 说明 |
|---|---|---|---|
| TFIM-J1.0 / J0.5 / h0.3 | 横场伊辛 | 4×4 = 16 qubit | 原有基线（系数不同但逻辑门数相同） |
| TFIM-32 / TFIM-64 | 横场伊辛 | 8×4 / 8×8 = 32/64 qubit | **R 随格点数增长** |
| Hubbard-32 / Hubbard-64 | Fermi-Hubbard | 4×4 / 8×4 格点×2 自旋 | 费米模型，Pauli 项结构不同 |
| Chem-H2 / Chem-LiH | 分子哈密顿量 | sto-3g | 需 `openfermionpyscf`，旋转谱不同 |

## 用法

```bash
pip install pyliqtr cirq            # A/B + 自旋/Hubbard 算例
pip install openfermionpyscf pyscf  # 仅化学算例需要

# 自测（无需任何外部包）
python3 selftest.py

# 跑全部算例、4 个工具
python3 run.py --algorithm all --tools A,B,C,D --out ledger.json

# 只跑规模扫描
python3 run.py --algorithm TFIM-32 --eps 1e-10

# 列出可用算例
python3 -c "import algorithms; [print(k) for k in algorithms.ALGORITHMS]"
```

缺依赖的工具/算例不会让程序崩溃，会写进输出里的 `error` / `skipped` 字段。

## 输出 schema（节选）

```json
{
  "epsilon_ref": 1e-10,
  "results": [{
    "algorithm": "TFIM-64",
    "T_base": 0, "R": 0,
    "c_per_rotation_at_ref": 103,
    "T_total_at_ref": 0,
    "attribution_residual": null,
    "attribution_ok": false,
    "tools": [ ...每个工具原始读数... ],
    "skipped": [ ...未可用工具及原因... ]
  }]
}
```

## 下一步扩展（论文实验矩阵）

1. ~~`tools.run_qsharp` 补真实 QIR 导出~~ ✅ 已完成（2026-10-25）：Q# 抽象电路 → `qsharp.eval` + `qsharp.estimate`，逻辑级与 B 一致 + 物理级 QEC 真数。可选延伸：改为从 pyLIQTR 完整电路导出（需 cirq-qir 与 Base profile 门集兼容，Rz 需预合成）。
2. 对 ε ∈ {1e-4,1e-6,1e-8,1e-10,1e-12}、全部算例全网格跑，产出主图数据。
3. 可选补 Shor 模幂 / Grover（需另接 Qualtran 的算法模块）。
