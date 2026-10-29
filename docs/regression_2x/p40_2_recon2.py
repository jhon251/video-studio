# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 侦察（v2）：从 DB 的 MATERIAL_TIMELINE 事件取**完整决策**（含候选）。"""
from __future__ import annotations

import collections
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
pid = "p_93f362b26cff"
con = sqlite3.connect("file:" + (R / "projects/video_studio.db").as_posix()
                      + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select payload from events where project_id=? and "
                "type='MATERIAL_TIMELINE'", (pid,)).fetchone()
p = json.loads(r["payload"])
dec = p["decisions"]
print("景数 {} | 顶层键 {}".format(len(dec), sorted(p.keys())))
d0 = dec[0]
print("单条决策键: {}".format(sorted(d0.keys())))
print()
widths = collections.Counter(len(d.get("candidates") or []) for d in dec)
print("逐景候选数分布: {}".format(dict(sorted(widths.items()))))
print()
# 池中 low_discriminative / discriminative
pool = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
cand = [c for c in pool["candidates"] if c.get("path")]
keys = set()
for c in cand:
    keys |= set(c.keys())
print("池候选项键: {}".format(sorted(keys)))
for k in ("low_discriminative", "discriminative", "match_score", "rank"):
    vals = {str(c.get(k)) for c in cand if k in c}
    if vals:
        print("  {}: {}".format(k, sorted(vals)[:8]))
print()
SEQ = [(d["scene_id"], ((d.get("selected_asset") or {}).get("asset_id") or "")) for d in dec]
cnt = collections.Counter(a for _, a in SEQ if a)
print("每素材景数（前 6）: {}".format(json.dumps(
    {k[:16]: v for k, v in cnt.most_common(6)}, ensure_ascii=False)))
print()
print("{:<8} {:<16} {:>4}".format("scene", "selected", "cands"))
for d in dec:
    sel = ((d.get("selected_asset") or {}).get("asset_id") or "-")[:14]
    print("{:<8} {:<16} {:>4}".format(d["scene_id"], sel, len(d.get("candidates") or [])))
(R / "output" / "p40_probe").mkdir(parents=True, exist_ok=True)
(R / "output/p40_probe/material_timeline_full.json").write_text(
    json.dumps(p, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("-> output/p40_probe/material_timeline_full.json")
