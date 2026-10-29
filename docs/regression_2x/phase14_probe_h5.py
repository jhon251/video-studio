# -*- coding: utf-8 -*-
"""勘查 phase6g_exec_h5.json 的 human_decision/human_acceptance（只读）——能否扩充逐对人工标签。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

p = L / "phase6g_exec_h5.json"
j = json.loads(p.read_text(encoding="utf-8"))
print("top keys:", sorted(j.keys())[:40])

for k in ("human_decision", "human_acceptance", "binding", "asset_records",
          "asset_replacement_evidence"):
    if k in j:
        print()
        print("=" * 70)
        print(k, "=>", json.dumps(j[k], ensure_ascii=False)[:1800])

# 递归找所有含 scene_id + asset 的记录
print()
print("=" * 70)
print("递归搜索含 scene_id/asset_id 的记录")
found = []


def walk(o, path=""):
    if isinstance(o, dict):
        if ("scene_id" in o) and any(kk in o for kk in ("asset_id", "replaced", "after_asset_id")):
            found.append((path, o))
        for kk, vv in o.items():
            walk(vv, path + "/" + str(kk))
    elif isinstance(o, list):
        for i, vv in enumerate(o):
            walk(vv, path + "[{}]".format(i))


walk(j)
print("records:", len(found))
for path, o in found[:10]:
    print("-", path)
    print("  ", json.dumps({k: o.get(k) for k in
                            ("scene_id", "asset_id", "replaced", "before_asset_id",
                             "after_asset_id", "corr_new_mean", "corr_prev_mean",
                             "decided_by", "reason")}, ensure_ascii=False)[:400])
