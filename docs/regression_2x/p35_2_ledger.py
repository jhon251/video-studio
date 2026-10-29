# -*- coding: utf-8 -*-
"""P35-1 侦察：在 v3/v4.1 谱系的 script_output 中找出含 `fact_risks` 的底账（13 条）。只读。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row

PIDS = ["p_50e10b27b44d", "p_96efdc03e1aa", "p_8b48148d4bf3", "p_37a4ede06517",
        "p_932e24cb9d04"]
best = None
for pid in PIDS:
    for r in con.execute("select artifact_id, type, path from artifacts where project_id=?",
                         (pid,)):
        p = pathlib.Path(r["path"])
        if not p.is_file() or r["type"] != "script_output":
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:                                                   # noqa: BLE001
            continue
        fr = d.get("fact_risks")
        if fr:
            print("{} {} -> fact_risks {} 条 | 段数 {}".format(
                pid, r["artifact_id"], len(fr), len(d.get("segments") or [])))
            if best is None or len(fr) > len(best[1]):
                best = (r["artifact_id"], fr, p, d)
print()
if best:
    aid, fr, p, d = best
    print("=== 采用底账 {} ({}) ===".format(aid, p.name))
    for i, x in enumerate(fr):
        print("{:>2}. {}".format(i + 1, json.dumps(x, ensure_ascii=False)[:240]))
    print()
    print("其它顶层键:", sorted(d.keys()))
    print("hook_map:", json.dumps(d.get("hook_map"), ensure_ascii=False)[:300])
    print("cta_plan:", json.dumps(d.get("cta_plan"), ensure_ascii=False)[:300])
    out = R / "output" / "p35_probe"
    out.mkdir(parents=True, exist_ok=True)
    (out / "fact_risks_ledger.json").write_text(
        json.dumps({"artifact_id": aid, "path": str(p), "fact_risks": fr,
                    "hook_map": d.get("hook_map"), "cta_plan": d.get("cta_plan"),
                    "emotion_beats": [s.get("emotion_beat") for s in
                                      (d.get("segments") or [])]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> output/p35_probe/fact_risks_ledger.json")
else:
    print("未找到含 fact_risks 的 v3 谱系 script_output")
