# -*- coding: utf-8 -*-
"""Phase 8 只读探针：读取 p_96efdc03e1aa 的选题/结构产物，用于构造 A/B 同一简报。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
for t in ("topic_output", "structure_output", "research_output"):
    row = con.execute("select artifact_id,path from artifacts where type=? and "
                      "project_id='p_96efdc03e1aa' order by created_at limit 1", (t,)).fetchone()
    if not row:
        print(t, "缺失")
        continue
    j = json.loads(pathlib.Path(row["path"]).read_text(encoding="utf-8"))
    print("==", t, row["artifact_id"], "keys:", sorted(j.keys())[:16])
    for k in ("topic", "title", "angle", "core_question", "summary", "one_liner", "thesis",
              "chapters", "hypothesis", "keywords"):
        if k in j:
            print("   ", k, "=", json.dumps(j[k], ensure_ascii=False)[:300])
    if t == "topic_output" and j.get("proposals"):
        ps = j["proposals"]
        print("   proposals n =", len(ps), "| item keys:", sorted(ps[0].keys()))
        for p in ps[:2]:
            print("    ->", json.dumps(p, ensure_ascii=False)[:420])
    if t == "structure_output" and j.get("chapters"):
        for c in j["chapters"][:3]:
            print("    ch:", json.dumps({k: c.get(k) for k in ("title", "goal", "duration_s")},
                                        ensure_ascii=False)[:220])
con.close()
