# -*- coding: utf-8 -*-
"""6-A/M2 取证（只读）：统计本轮"判据校正前"留下的历史阻断记录（append-only，不修改）。

目的：如实披露 M2 实现过程中（判据校正前）产生的历史 BLOCKED 记录；这些记录**保留**，
但其中的 PI-4 帧数差 / PI-6 UNKNOWN / PI-5 覆盖比三类判决已不再是阻断判据（见报告 §4）。
用法: python docs/regression_2x/phase6a_m2_interim_blocks.py
产出: logs/phase6a_m2_interim_blocks.json
"""
import json
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
con = sqlite3.connect("file:projects/video_studio.db?mode=ro", uri=True)
rows = con.execute("select task_id, project_id, status, error, created_at from tasks "
                   "where error like '%PRODUCTION_INTEGRITY_FAILED%' "
                   "or error like '%render 前闸门%' order by created_at").fetchall()
con.close()

classes = Counter()
items = []
for tid, pid, status, err, at in rows:
    tags = []
    if "PRODUCTION_INTEGRITY_FAILED" in err:
        tags.append("post_render")
    if "render 前闸门" in err:
        tags.append("pre_render")
    for key, tag in (("PI-1 FAIL", "PI-1:coverage"),
                     ("PI-2 FAIL", "PI-2:dual_contract"),
                     ("PI-3 FAIL", "PI-3:film_silence"),
                     ("PI-6 UNKNOWN", "PI-6:unknown(interim)"),
                     ("PI-6 FAIL", "PI-6:drift"),
                     ("PI-4", "PI-4:seen_in_payload"),
                     ("PI-5", "PI-5:seen_in_payload")):
        if key in err:
            tags.append(tag)
    for t in tags:
        classes[t] += 1
    items.append({"task_id": tid, "project_id": pid, "status": status, "at": at, "tags": tags})

out = {"schema": "m2-interim-blocks-v1", "read_only": True,
       "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
       "total_records": len(items), "tag_counts": dict(classes), "records": items,
       "note": "这些是 M2 实现期间（判据校正前）留下的历史取证记录，**保留不改**"
               "（append-only）；报告 §4 说明其中的 PI-4 帧数差 / PI-6 UNKNOWN / PI-5 覆盖比"
               "三类判决已不再是阻断判据。"}
(LOGS / "phase6a_m2_interim_blocks.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                     encoding="utf-8")
print("历史阻断记录:", len(items), "| 标签计数:", dict(classes))
print("json ->", LOGS / "phase6a_m2_interim_blocks.json")
