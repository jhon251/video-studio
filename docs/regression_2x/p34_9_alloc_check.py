# -*- coding: utf-8 -*-
"""P34 复核：分配纪律是否在 P34 渲染中生效。只读。"""
from __future__ import annotations

import collections
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
fx = json.loads((R / "output/phase34_p34_4_sandbox/fixture.json")
                .read_text(encoding="utf-8"))
pid = fx["sandbox_project_id"]
print("fixture keys:", sorted(fx.keys()))
print("explicit_bindings:", fx.get("explicit_bindings"))
dec = json.loads((R / "output/phase34_p34_4_sandbox/material_timeline.json")
                 .read_text(encoding="utf-8"))["decisions"]
cnt = collections.Counter()
for d in dec:
    a = (d.get("selected_asset") or {}).get("asset_id")
    if a:
        cnt[a] += 1
print()
print("每素材景数:", json.dumps({k: v for k, v in cnt.most_common()},
                                ensure_ascii=False))
con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select payload from events where project_id=? and "
                "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
al = (json.loads(r["payload"]).get("material_allocation") or {}) if r else {}
print()
print("material_allocation: enabled={} cap={} adj={}".format(
    al.get("enabled"), al.get("cap"), al.get("forbid_adjacent")))
print("  reassigned={} unresolved={}".format(
    len(al.get("reassigned") or []), len(al.get("unresolved") or [])))
print("  final_counts max={}".format(
    max((al.get("final_counts") or {}).values() or [0])))
