# -*- coding: utf-8 -*-
"""5-K 只读：判定 `5d_frozen_check` 报的 DRIFT 是否为**预先存在**（对比 5-K 冻结快照 vs 5-B 冻结参照）。

若 logs_5k_frozen 相对 logs_5b_frozen 的 drift 数 ≈ 该检查报出的数字，则说明这些漂移在 5-K 之前就已存在。
产出: docs/regression_2x/logs/phase5k_5b_drift_preexisting.json
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
R2 = Path(r"C:\mp4agent\video-studio\docs\regression_2x")
A = R2 / "logs_5b_frozen"
B = R2 / "logs_5k_frozen"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def man(d: Path) -> dict:
    return {p.relative_to(d).as_posix(): sha(p) for p in sorted(d.rglob("*")) if p.is_file()}


a, b = man(A), man(B)
a.pop("MANIFEST.json", None)
b.pop("MANIFEST.json", None)
drift = sorted(k for k, v in a.items() if b.get(k) != v)
missing = sorted(k for k in a if k not in b)
out = {"ref": str(A.relative_to(R2)), "compare": str(B.relative_to(R2)),
       "ref_files": len(a), "compare_files": len(b),
       "drift_pre_existing": len(drift), "missing_pre_existing": len(missing),
       "drift_sample": drift[:25]}
(R2 / "logs" / "phase5k_5b_drift_preexisting.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("5-B ref files:", len(a), "| 5-K frozen files:", len(b))
print("drift (pre-existing, 5-B vs 5-K frozen):", len(drift), "| missing:", len(missing))
print("json -> docs/regression_2x/logs/phase5k_5b_drift_preexisting.json")
