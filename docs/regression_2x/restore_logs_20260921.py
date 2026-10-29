# -*- coding: utf-8 -*-
"""纪律性修复：把本次（2026-09-21 18:26）误跑的 5-F 回归所改写的 **既有日志** 从
`logs_5e_frozen/`（18:25:59 备份，即运行前状态）原样回拷，并逐文件复验。

只回拷"运行窗口内被改写且备份中存在"的文件；本次新建的审计文件（audit_*）不动。

用法：python docs/regression_2x/restore_logs_20260921.py
"""
import hashlib
import json
import pathlib
import shutil
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5e_frozen"
OUT = LOGS / "restore_logs_20260921.json"
CUTOFF = time.time() - 7200          # 近 2 小时内被改写的既有文件
SKIP_PREFIX = ("audit_p96efdc", "phase5f_", "phase5g_", "restore_logs_")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


restored, kept, missing_in_bak = [], [], []
for p in sorted(LOGS.rglob("*")):
    if not p.is_file():
        continue
    rel = str(p.relative_to(LOGS)).replace("\\", "/")
    if rel.split("/")[0].startswith(SKIP_PREFIX):
        continue
    if p.stat().st_mtime < CUTOFF:
        continue
    src = BAK / rel
    if src.is_file():
        before = sha(p)
        shutil.copy2(src, p)
        restored.append({"file": rel, "content_before_restore": before[:16],
                         "restored_from_backup": sha(src)[:16],
                         "identical_now": sha(p) == sha(src)})
    else:
        missing_in_bak.append(rel)
res = {"restored_count": len(restored), "restored": restored,
       "not_in_backup": missing_in_bak,
       "all_restored_verified": all(x["identical_now"] for x in restored)}
OUT.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("回拷文件数:", len(restored))
for x in restored:
    print("   {:<48} 运行后={} → 备份={} 一致={}".format(x["file"][:48],
                                                        x["content_before_restore"],
                                                        x["restored_from_backup"],
                                                        x["identical_now"]))
print("备份中缺失（本可保留）:", missing_in_bak)
print("全部复验一致:", res["all_restored_verified"])
print("written", OUT)
