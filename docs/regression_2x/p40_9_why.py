# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 归因：求解器「声明 pass」与实盘「实际 pass」不一致的原因。"""
from __future__ import annotations

import collections
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
pid = "p_41fd3896a307"
con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select payload from events where project_id=? and "
                "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
p = json.loads(r["payload"])
dec = p["decisions"]
al = p.get("material_allocation") or {}
gs = al.get("global_satisfy") or {}
print("global_satisfy 声明: {}".format(json.dumps(
    {k: (v if not isinstance(v, dict) else len(v)) for k, v in gs.items()},
    ensure_ascii=False)))
print()
# 实盘：哪些景有可换候选？
withc = [d["scene_id"] for d in dec if d.get("candidates")]
print("实盘事件里**带 candidates 的景**: {} / {}".format(len(withc), len(dec)))
print("（其余景的 candidates 未随事件持久化）")
print()
# 用 solve 侧的候选复算（生产 classify_scene）
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402
script = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
pool = json.loads((R / "docs/regression_2x/logs/phase33_retrieval_payload.json")
                  .read_text(encoding="utf-8"))
cands = [c for c in pool["candidates"] if c.get("path")]
tl = EA._build_material_timeline(script, [], cands,
                                 policy=MAT.policy_from_config(None),
                                 material_provided=True)
wc = [(d["scene_id"], len(d.get("candidates") or [])) for d in tl]
print("复算带候选的景: {} / {}".format(sum(1 for _, n in wc if n > 0), len(wc)))
print("候选数分布: {}".format(dict(collections.Counter(n for _, n in wc))))
print()
# 复算候选的 asset_id 命名空间
for d in tl:
    cs = d.get("candidates") or []
    if cs:
        print("样例景 {} 候选 asset_id: {}".format(
            d["scene_id"], [ (c.get('asset_id') or '')[:20] for c in cs[:3]]))
        break
seq = [(d["scene_id"], ((d.get("selected_asset") or {}).get("asset_id"))) for d in dec]
adj = [(seq[i - 1][0], seq[i][0], seq[i][1][:18]) for i in range(1, len(seq))
       if seq[i][1] and seq[i - 1][1] == seq[i][1]]
print()
print("F2 残留相邻同素材 {} 处: {}".format(len(adj), adj))
