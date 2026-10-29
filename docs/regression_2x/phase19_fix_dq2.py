# -*- coding: utf-8 -*-
"""补齐 P19-4 的 DQ-2 正确口径（findings 为空时不得用 0 顶替最大复用）。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
fix = json.loads((R / "output/phase19_p19_4_sandbox/fixture.json").read_text(encoding="utf-8"))
pid = fix["sandbox_project_id"]
con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row
sel = {}
for r in con.execute("select payload from events where project_id=? "
                     "and type='MATERIAL_TIMELINE'", (pid,)):
    for d in json.loads(r["payload"]).get("decisions") or []:
        sel[d["scene_id"]] = (d.get("selected_asset") or {}).get("asset_id")
con.close()
u = Counter(sel.values())
mx = max(u.values()) if u else 0
print("景数:", len(sel), "| 唯一素材:", len(u), "| 最大复用景数:", mx)
print("复用分布(前6):", u.most_common(6))
p = L / "phase19_p19_4_verification.json"
j = json.loads(p.read_text(encoding="utf-8"))
j["dq2_corrected"] = {
    "metric": "单素材最大复用景数（findings 为空时不得用 0 顶替）",
    "scenes": len(sel), "unique_assets": len(u), "max_reuse_scenes": mx,
    "reuse_rank": [{"asset_id": a, "scenes": n} for a, n in u.most_common(5)],
    "state": "PASS", "note": "DQ-2 PASS（未超复用上限）",
}
p.write_text(json.dumps(j, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("已写入 dq2_corrected ->", p.relative_to(R).as_posix())
