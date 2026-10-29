# -*- coding: utf-8 -*-
"""P14-2 人工标签池盘点（只读）：从 DB decisions + review ledger 找逐对人工标签。"""
from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix() + "?mode=ro",
                      uri=True)
con.row_factory = sqlite3.Row

print("=" * 78)
print("DB decisions —— 列结构 + node/state 分布")
print("=" * 78)
cols = [r[1] for r in con.execute("pragma table_info(decisions)")]
print("columns:", cols)
print()
for r in con.execute("select node, state, count(*) n from decisions group by node, state "
                     "order by n desc limit 25"):
    print("  {:34s} {:22s} {:>6}".format(str(r["node"])[:34], str(r["state"])[:22], r["n"]))

print()
print("=" * 78)
print("含 asset_id / scene 的人工决定样本")
print("=" * 78)
sel = [c for c in cols if c in ("decision_id", "project_id", "node", "made_by", "state",
                                "rationale", "asset_id", "scene_id", "artifact_snapshot",
                                "created_at")]
q = "select {} from decisions where made_by like 'human%' limit 400".format(",".join(sel))
rows = [dict(r) for r in con.execute(q)]
print("human rows fetched:", len(rows))
# 找含 asset 信息的
with_asset = []
for d in rows:
    snap = d.get("artifact_snapshot")
    try:
        snapj = json.loads(snap) if isinstance(snap, str) and snap.strip() else snap
    except Exception:                                                       # noqa: BLE001
        snapj = None
    d["_snap"] = snapj
    if d.get("asset_id") or (isinstance(snapj, dict) and
                             (snapj.get("asset_id") or snapj.get("scene_id"))):
        with_asset.append(d)
print("rows carrying asset/scene info:", len(with_asset))
for d in with_asset[:12]:
    print("  node={} state={} by={} asset={} snap={}".format(
        d.get("node"), d.get("state"), d.get("made_by"),
        d.get("asset_id"), json.dumps(d["_snap"], ensure_ascii=False)[:220]))

print()
print("=" * 78)
print("node 名含 reject/deny 的决定")
print("=" * 78)
for r in con.execute("select decision_id, node, state, made_by, rationale, artifact_snapshot "
                     "from decisions where lower(node) like '%reject%' or "
                     "lower(state) like '%reject%' or lower(node) like '%deny%' limit 40"):
    d = dict(r)
    print("  {} | {} | {} | {}".format(d["decision_id"], d["node"], d["state"],
                                       str(d["rationale"])[:110]))
con.close()
