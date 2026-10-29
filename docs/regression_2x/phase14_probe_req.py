# -*- coding: utf-8 -*-
"""P14-2 需求/素材索引勘查（只读）：确认可重建 (requirement, image) 对。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

vr = json.loads((L / "visual_relevance.json").read_text(encoding="utf-8"))

print("=" * 78)
print("requirements_snapshot")
print("=" * 78)
rs = vr.get("requirements_snapshot")
print("type:", type(rs).__name__)
print("artifact_hash:", rs.get("artifact_hash"))
reqs = rs.get("requirements") or []
print("requirements:", len(reqs))
print("req[0]:", json.dumps(reqs[0], ensure_ascii=False, indent=1)[:1400])

print()
print("=" * 78)
print("asset_index_snapshot")
print("=" * 78)
ais = vr.get("asset_index_snapshot")
print("artifact_hash:", ais.get("artifact_hash"))
cands = ais.get("candidates") or []
print("candidates:", len(cands))
for c in cands:
    print("  ", json.dumps({k: c.get(k) for k in
                            ("asset_id", "sha256", "path", "bytes", "width", "height",
                             "decode_status", "media_type")}, ensure_ascii=False)[:280])

print()
print("=" * 78)
print("sources / policy")
print("=" * 78)
print("sources:", json.dumps(vr.get("sources"), ensure_ascii=False)[:700])
print("policy:", json.dumps(vr.get("policy"), ensure_ascii=False)[:500])
print("aggregate:", json.dumps(vr.get("aggregate"), ensure_ascii=False)[:400])
