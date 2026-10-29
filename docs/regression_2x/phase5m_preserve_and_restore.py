# -*- coding: utf-8 -*-
"""5-M：电池被中断后的「证据留档 + 冻结日志恢复」（幂等）。

背景：2026-09-21 的 5-M 电池跑到第 24 步（`5f_judge`）后在第 25 步（`unit_suites`）被中断，
电池自带的「跑完 → 另存本轮产物 → 回拷冻结日志」收尾阶段因此未执行。本脚本补做收尾：

 1. diff 当前 `logs/` 相对冻结快照 `logs_5m_frozen/`；
 2. 把**本轮**产物（batch 结果/逐项日志、suite 日志、phase5m_* 证据）另存到 `logs/phase5m_rerun/`；
 3. 把冻结快照里存在且已变的文件**逐文件回拷**（新增文件保留、不删除）；
 4. 复核 drift/missing，写入 `logs/phase5m_logs_restore.json`。

用法: python docs/regression_2x/phase5m_preserve_and_restore.py
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5m_frozen"
KEEP = LOGS / "phase5m_rerun"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def live() -> dict:
    return {p.relative_to(LOGS).as_posix(): sha(p) for p in sorted(LOGS.rglob("*")) if p.is_file()}


_raw = json.loads((BAK / "MANIFEST.json").read_text(encoding="utf-8"))
# 兼容两种清单形态：{"files": {...}}（5-K 脚本）与扁平 {rel: sha}（5-M 电池脚本）
frozen = _raw["files"] if isinstance(_raw, dict) and "files" in _raw else _raw
frozen = {k: v for k, v in frozen.items() if k != "MANIFEST.json"}
pre = live()
pre_drift = sorted(k for k, v in frozen.items() if pre.get(k) != v)
pre_added = sorted(k for k in pre if k not in frozen)

KEEP.mkdir(parents=True, exist_ok=True)
kept = []
for pat in ("phase3a_*.log", "phase3a_regression_batch.json", "suites_summary.json", "suite_*.log",
            "phase5m_*.json", "phase5m_*.log", "phase5m_*.txt", "_captions*.ass"):
    for p in sorted(LOGS.glob(pat)):
        if p.is_file() and p.parent == LOGS:
            shutil.copy2(p, KEEP / p.name)
            kept.append(p.name)
kept = sorted(set(kept))

restored = []
for rel, h in frozen.items():
    lp = LOGS / rel
    if not lp.is_file():
        lp.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(BAK / rel, lp)
        restored.append(rel)
    elif sha(lp) != h:
        shutil.copy2(BAK / rel, lp)
        restored.append(rel)

post = live()
post_drift = [k for k, v in frozen.items() if post.get(k) != v]
post_missing = [k for k in frozen if k not in post]
out = {"frozen_count": len(frozen), "pre_drift_count": len(pre_drift),
       "pre_drift_sample": pre_drift[:30], "pre_added_count": len(pre_added),
       "kept_this_round": kept, "kept_dir": KEEP.relative_to(ROOT).as_posix(),
       "restored_count": len(restored), "restored_sample": restored[:30],
       "post_drift": post_drift, "post_missing": post_missing,
       "verdict": "MATCH" if not post_drift and not post_missing else "DIFF",
       "context": "5-M 电池在第 25 步被中断，本脚本补做电池未执行的收尾（另存 + 回拷）"}
(LOGS / "phase5m_logs_restore.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("frozen:", len(frozen), "| pre-drift:", len(pre_drift), "| pre-added:", len(pre_added))
print("kept this round:", len(kept), "->", KEEP.relative_to(ROOT))
print("restored:", len(restored))
print("post drift:", len(post_drift), "| missing:", len(post_missing), "|", out["verdict"])
print("json ->", LOGS / "phase5m_logs_restore.json")
