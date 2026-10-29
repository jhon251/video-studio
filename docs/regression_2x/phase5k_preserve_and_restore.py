# -*- coding: utf-8 -*-
"""5-K：回归后「冻结证据恢复 + 本轮结果留档」。

步骤（幂等）：
 1. 先 diff：`docs/regression_2x/logs/` 相对冻结快照 `logs_5k_frozen/` 的 drift/added/missing；
 2. 把**本轮**产物另存到 `logs/phase5k_batch_logs/`（batch 结果 JSON、48 套件 summary 与逐套件日志、
    24 个批次子项日志）——另存文件是"新增"，不会被回拷覆盖；
 3. 把冻结快照中存在且内容已变的文件**逐文件回拷**（新增文件保留、不删除）；
 4. 复核 drift/missing，写入 `logs/phase5k_logs_restore.json`。

用法: python docs/regression_2x/phase5k_preserve_and_restore.py
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
KEEP = LOGS / "phase5k_batch_logs"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def live_manifest() -> dict:
    out = {}
    for p in sorted(LOGS.rglob("*")):
        if p.is_file():
            out[p.relative_to(LOGS).as_posix()] = sha(p)
    return out


man = json.loads((BAK / "MANIFEST.json").read_text(encoding="utf-8"))
frozen = man["files"]
pre = live_manifest()
pre_drift = sorted(k for k, v in frozen.items() if pre.get(k) != v)
pre_added = sorted(k for k in pre if k not in frozen)

# 2. 本轮产物另存
KEEP.mkdir(parents=True, exist_ok=True)
patterns = ["phase3a_regression_batch.json", "suites_summary.json", "suite_*.log",
            "phase3a_*.log", "phase5k_*.json", "phase5k_*.log", "phase5k_ro_*.log"]
kept = []
for pat in patterns:
    for p in sorted(LOGS.glob(pat)):
        if p.is_file() and p.parent == LOGS:
            dst = KEEP / p.name
            shutil.copy2(p, dst)
            kept.append(p.name)
kept = sorted(set(kept))

# 3. 回拷冻结证据
restored = []
for rel, h in frozen.items():
    live = LOGS / rel
    if not live.is_file():
        live.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BAK / rel, live)
        restored.append(rel)
    elif sha(live) != h:
        shutil.copy2(BAK / rel, live)
        restored.append(rel)

post = live_manifest()
post_drift = [k for k, v in frozen.items() if post.get(k) != v]
post_missing = [k for k in frozen if k not in post]
out = {"frozen_count": len(frozen), "pre_drift": pre_drift, "pre_drift_count": len(pre_drift),
       "pre_added_count": len(pre_added), "pre_added_sample": pre_added[:40],
       "kept_this_round": kept, "kept_dir": str(KEEP.relative_to(ROOT)),
       "restored_count": len(restored), "restored_sample": restored[:40],
       "post_drift": post_drift, "post_missing": post_missing,
       "verdict": "MATCH" if not post_drift and not post_missing else "DIFF",
       "note": "冻结证据（含 5-A…5-F 全部证据与 §18 之前的历史日志）已原样恢复；"
               "本轮结果留档于 logs/phase5k_batch_logs/"}
(LOGS / "phase5k_logs_restore.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("frozen:", len(frozen), "| pre-drift:", len(pre_drift), "| pre-added:", len(pre_added))
print("kept this round:", len(kept), "->", KEEP.relative_to(ROOT))
print("restored:", len(restored))
print("post drift:", len(post_drift), "| missing:", len(post_missing), "|", out["verdict"])
print("json ->", LOGS / "phase5k_logs_restore.json")
