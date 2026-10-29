# -*- coding: utf-8 -*-
"""直接倾印 requirements_snapshot / asset_index_snapshot 的原始结构（只读）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

vr = json.loads((L / "visual_relevance.json").read_text(encoding="utf-8"))
rs = vr.get("requirements_snapshot") or {}
print("requirements_snapshot keys:", sorted(rs.keys()))
for k, v in rs.items():
    print("  {}: type={} value={}".format(
        k, type(v).__name__,
        json.dumps(v, ensure_ascii=False)[:300] if not isinstance(v, (list, dict))
        else "len={}".format(len(v))))

print()
ais = vr.get("asset_index_snapshot") or {}
print("asset_index_snapshot keys:", sorted(ais.keys()))
for k, v in ais.items():
    print("  {}: type={} {}".format(k, type(v).__name__,
                                    "len={}".format(len(v)) if isinstance(v, (list, dict))
                                    else json.dumps(v, ensure_ascii=False)[:200]))
cl = ais.get("candidates")
if isinstance(cl, list) and cl:
    print()
    print("candidate[0] full:")
    print(json.dumps(cl[0], ensure_ascii=False, indent=1)[:1500])

# requirement 单条：从 scene_results 的 requirement_id 反查 requirements 列表
reqs = rs.get("requirements")
if isinstance(reqs, list) and reqs:
    print()
    print("requirements list len:", len(reqs))
    print("requirement[0]:")
    print(json.dumps(reqs[0], ensure_ascii=False, indent=1)[:1500])
