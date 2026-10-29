# -*- coding: utf-8 -*-
"""导出待重选场景的旁白与镜头描述（供人工撰写检索 query）。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
script = json.loads((R / "output/phase27_script_sandbox/script_p27_v41_40seg.json")
                    .read_text(encoding="utf-8"))
shots = json.loads((R / "projects/p_96efdc03e1aa/artifacts/a_a6279580600a.json")
                   .read_text(encoding="utf-8")).get("shots") or []
segs = script["segments"]
out = {}
for i, s in enumerate(segs):
    sid = str(s.get("scene_id") or "S%02d" % (i + 1))
    if sid in ("S11p1", "S11p2", "S13p1", "S13p2", "S14p1"):
        sh = shots[i] if i < len(shots) else {}
        out[sid] = {"narration": s.get("narration"),
                    "description": sh.get("description"),
                    "gen_prompt": sh.get("gen_prompt")}
p = R / "output/p31_probe/reselect_targets.json"
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("->", p)
