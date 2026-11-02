#!/usr/bin/env python3
"""run_record.py — 生成运行记录（每次实验的 commit / 环境 / 种子 / 配置哈希）

按 §9"每次运行应记录 Git commit、软件版本、操作系统、随机种子、配置文件哈希
和开始/结束状态"生成 run_record.json。非确定性工具（pyLIQTR rz_decomp 的
use_random_decomp=False 路径为确定性）说明于 note 字段。

用法：.venv-qre/bin/python run_record.py
"""
from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def sha256(p: str) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def git_head() -> str:
    try:
        out = subprocess.check_output(
            ["git", "-C", ROOT, "rev-parse", "HEAD"], stderr=subprocess.DEVNULL,
            text=True).strip()
    except Exception:
        out = "n/a"
    return out


def git_dirty_files() -> list[str]:
    try:
        out = subprocess.check_output(
            ["git", "-C", ROOT, "status", "--porcelain"], stderr=subprocess.DEVNULL,
            text=True)
        return [l[:120] for l in out.splitlines() if l.strip()][:40]
    except Exception:
        return []


def main() -> int:
    configs = {
        "calibration.json": "configs/calibration.json",
        "c_microbenchmark_100.json": "data/c_microbenchmark_100.json",
        "heldout_results.csv": "data/heldout_results.csv",
        "ledger.json": "data/ledger.json",
    }
    payload = {
        "generated_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "os": f"{platform.system()} {platform.machine()}",
        "python": platform.python_version(),
        "git_head_qre_harness": git_head(),
        "git_dirty_in_qre_harness": git_dirty_files(),
        "seeds": {
            "microbenchmark_100_angles": 20261026,
            "bootstrap_resampling": 20261026,
            "monte_carlo_mixed_precision": 20261026,
        },
        "determinism_note": "pyLIQTR rz_decomp is run with use_random_decomp=False "
                            "(deterministic Ross–Selinger grid); all seeds fixed, so a "
                            "clean rerun reproduces the same numbers.",
        "file_sha256": {name: sha256(os.path.join(ROOT, p))
                        for name, p in configs.items()
                        if os.path.exists(os.path.join(ROOT, p))},
    }
    with open(os.path.join(ROOT, "run_record.json"), "w") as f:
        json.dump(payload, f, indent=2)
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
