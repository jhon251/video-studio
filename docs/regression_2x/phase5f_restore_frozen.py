# -*- coding: utf-8 -*-
"""5-F 断点收尾：把被中断的回归所改写的**冻结证据日志**从 `logs_5e_frozen/` 原样恢复（只读校验）。

回归电池（`phase5f_regression.py`）的"跑完即恢复"步骤因收工中断而未执行；本脚本按备份 manifest
逐文件回拷并复验（DRIFT 0 / MISSING 0），保证 5-A…5-E 冻结证据逐字节不变。

用法：python docs/regression_2x/phase5f_restore_frozen.py
"""
import hashlib
import json
import pathlib
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5e_frozen"
OUT = LOGS / "phase5f_restore_frozen.json"


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


if not (BAK / "MANIFEST.json").is_file():
    print("备份 manifest 不存在:", BAK / "MANIFEST.json")
    sys.exit(2)
man = json.loads((BAK / "MANIFEST.json").read_text(encoding="utf-8"))
drift_before, missing_before = [], []
for rel, h in man.items():
    p = LOGS / rel
    if not p.is_file():
        missing_before.append(rel)
    elif sha(p) != h:
        drift_before.append(rel)
restored = 0
for rel in man:
    src, dst = BAK / rel, LOGS / rel
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        restored += 1
drift_after = [rel for rel, h in man.items() if not (LOGS / rel).is_file() or sha(LOGS / rel) != h]
res = {"frozen_count": len(man), "drift_before": drift_before, "missing_before": missing_before,
       "restored_files": restored, "drift_after": drift_after, "frozen_restored": not drift_after}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("冻结文件:", len(man), "| 中断时已被改写:", len(drift_before), drift_before[:5])
print("回拷文件:", restored, "| 回拷后 DRIFT:", len(drift_after), drift_after[:5])
print("冻结证据已完整恢复:", res["frozen_restored"])
print("written", OUT)
