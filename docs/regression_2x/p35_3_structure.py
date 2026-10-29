# -*- coding: utf-8 -*-
"""P35-1 侦察：导出 v3 底账的叙事结构元数据（core_viewpoint / narrative_route / opening）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
P = R / "projects/p_96efdc03e1aa/artifacts/a_49b58fb3dc01.json"
d = json.loads(P.read_text(encoding="utf-8"))
out = {}
for k in ("core_viewpoint", "narrative_route", "recommended_opening",
          "opening_alternatives", "recommended_title", "summary", "note",
          "topic_understanding", "confidence"):
    v = d.get(k)
    out[k] = v
    print("=== {} ===".format(k))
    print(json.dumps(v, ensure_ascii=False, indent=1)[:1400])
    print()
segs = d.get("segments") or []
print("=== segments: {} 段，逐段摘要 ===".format(len(segs)))
for s in segs:
    print("  [{}] {}".format(s.get("segment_id") or s.get("id") or "?",
                            (s.get("text") or s.get("narration") or "")[:110]))
(R / "output/p35_probe").mkdir(parents=True, exist_ok=True)
(R / "output/p35_probe/v3_structure.json").write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print()
print("-> output/p35_probe/v3_structure.json")
