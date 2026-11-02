#!/bin/bash
# 5 个新种子 × 100 角度 × 4 精度 的多组随机角度微基准
set -e
PY=/Users/fangyuanyuan/Downloads/机构项目/量子计算机/nist-pqc-benchmarks/.venv-qre/bin/python
for S in 20261027 20261028 20261029 20261101 20261102; do
  echo "=== seed $S ==="
  $PY microbenchmark_c_100.py --n 100 --seed $S \
      --out c_microbenchmark_seed$S.json \
      --angles-csv calibration_angles_seed$S.csv
done
echo "ALL SEEDS DONE"
