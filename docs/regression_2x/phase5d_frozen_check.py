# -*- coding: utf-8 -*-
"""5-D 冻结证据完整性检查（只读）：把 `logs_5c_frozen/`（5-D 回归前的冻结集，含 5-C 全部证据）
与当前 `logs/` 逐文件比对，报告 DRIFT / MISSING（忽略本阶段新增的 phase5d_* 与抽帧目录）。

用法：python docs/regression_2x/phase5d_frozen_check.py
"""
import hashlib
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5c_frozen"
OUT = LOGS / "phase5d_frozen_check.json"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


frozen = {k: v for k, v in json.loads((BAK / "MANIFEST.json").read_text(encoding="utf-8")).items()}
drift, missing, added = [], [], []
for rel, h in sorted(frozen.items()):
    p = LOGS / rel
    if not p.is_file():
        missing.append(rel)
    elif sha(p) != h:
        drift.append(rel)
for p in sorted(LOGS.rglob("*")):
    if not p.is_file():
        continue
    rel = str(p.relative_to(LOGS)).replace("\\", "/")
    if rel.startswith("phase5d_") or rel.startswith("phase5c_rerun/") or rel.startswith("phase5d_rerun/"):
        continue
    if rel not in frozen:
        added.append(rel)
res = {"frozen_count": len(frozen), "drift": drift, "missing": missing, "added_non_stage": added,
       "frozen_intact": not drift and not missing}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("冻结文件:", len(frozen), "| DRIFT:", len(drift), drift[:8], "| MISSING:", len(missing),
      "| 非本阶段新增:", len(added), added[:8])
print("冻结证据完整（逐字节一致）:", res["frozen_intact"])
print("written", OUT)
