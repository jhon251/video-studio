# -*- coding: utf-8 -*-
"""5-K：全量回归后把 `docs/regression_2x/logs/` 中被改写的文件逐文件回拷（冻结证据恢复）。

规则：只恢复「备份里有、且内容已变」的文件；回归过程中**新增**的文件保留并登记（不删除）。
用法: python docs/regression_2x/phase5k_restore_logs.py
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5k_frozen"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


man = json.loads((BAK / "MANIFEST.json").read_text(encoding="utf-8"))
frozen = man["files"]
restored, kept_added, missing_after = [], [], []
for rel, h in frozen.items():
    live = LOGS / rel
    if not live.is_file():
        (LOGS / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BAK / rel, live)
        restored.append(rel)
        continue
    if sha(live) != h:
        shutil.copy2(BAK / rel, live)
        restored.append(rel)
post = {}
for p in sorted(LOGS.rglob("*")):
    if p.is_file():
        post[p.relative_to(LOGS).as_posix()] = sha(p)
added = sorted(k for k in post if k not in frozen)
drift = [k for k, v in frozen.items() if post.get(k) != v]
missing = [k for k in frozen if k not in post]
out = {"frozen_count": len(frozen), "restored": restored, "restored_count": len(restored),
       "added_since_freeze_count": len(added), "added_since_freeze": added[:60],
       "post_drift": drift, "post_missing": missing,
       "verdict": "MATCH" if not drift and not missing else "DIFF"}
(LOGS / "phase5k_logs_restore.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("frozen:", len(frozen), "| restored:", len(restored), "| added since freeze:", len(added))
print("post-restore drift:", len(drift), "| missing:", len(missing), "|",
      out["verdict"])
print("json ->", LOGS / "phase5k_logs_restore.json")
