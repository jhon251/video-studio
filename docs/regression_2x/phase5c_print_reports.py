# -*- coding: utf-8 -*-
"""5-C：压缩打印 5-A / 5-B / 4-B 报告关键字段（只读）。"""
import json
import pathlib
import sys

sys.stdout.reconfigure(encoding="utf-8")
LOGS = pathlib.Path(r"C:\mp4agent\video-studio\docs\regression_2x\logs")

which = sys.argv[1] if len(sys.argv) > 1 else "mm"
p = {"mm": "phase5c_mm_after.json", "mmb": "phase5c_mmb_after.json",
     "sem": "phase5c_semantic_after.json", "mm_before": "phase5a_mm_v5.json",
     "mmb_before": "phase5b_candidates_before.json"}[which]
d = json.loads((LOGS / p).read_text(encoding="utf-8-sig"))

if which in ("mm", "mm_before"):
    print("schema", d.get("schema"), "status", d.get("status"), "code", d.get("code"),
          "counts", d.get("counts"), "artifact", d.get("artifact_id") or d.get("artifact"))
    for s in d.get("scenes", []):
        fr = s.get("frames") or []
        print(" ", s.get("scene_id"), s.get("verdict"), s.get("code") or "",
              "expected", s.get("expected_domain"), "asset", s.get("asset_id"),
              s.get("asset_name"), "best", s.get("best_label"), "sim", s.get("best_sim"),
              "margin", s.get("margin"), "sims", [(f.get("label"), f.get("sim")) for f in fr][:3])
elif which in ("mmb", "mmb_before"):
    print("status", d.get("status"), "code", d.get("code"), "counts", d.get("counts"))
    print("settings", json.dumps(d.get("settings"), ensure_ascii=False))
    for s in d.get("scenes", []):
        print(" ", s.get("scene_id"), s.get("status"), s.get("code") or "",
              "expected", s.get("expected_domain"), "current", s.get("current_asset_id"),
              "cursor", s.get("cursor_visual_sim"))
        for c in s.get("candidates", []):
            print("     ->", c.get("asset_id"), c.get("name"), "vis", c.get("visual_sim"),
                  "narr", c.get("narration_relevance"), "lic", c.get("license_class"),
                  "gate", c.get("license_gate"), "src", c.get("source_id"))
else:
    print("schema", d.get("schema") or d.get("version"), "counts", d.get("counts"),
          "summary", d.get("summary"))
    for s in d.get("scenes", []):
        print(" ", s.get("scene_id"), s.get("verdict"), s.get("rule_id") or s.get("rule"),
              json.dumps({k: v for k, v in s.items()
                          if k not in ("scene_id", "verdict", "rule_id", "rule")},
                         ensure_ascii=False)[:200])
