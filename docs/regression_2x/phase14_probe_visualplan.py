# -*- coding: utf-8 -*-
"""勘查：VisualRequirement 构建时的输入（visual_plan_output.shots）在人审当时是否可用。

若可用 ⇒ P14-1 的需求文本应包含它（否则模型看到的需求比 P7-4 自身可用的更贫瘠）。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

vrq = json.loads((L / "visual_requirements.json").read_text(encoding="utf-8"))
print("visual_requirements.json source_identity:")
print(json.dumps(vrq.get("source_identity"), ensure_ascii=False, indent=1)[:1200])
print()
print("builder_rules:")
print(json.dumps(vrq.get("builder_rules"), ensure_ascii=False, indent=1)[:1500])

# 找 visual_plan_output（shots）
arts = R / "projects" / "p_96efdc03e1aa" / "artifacts"
vp = None
for f in sorted(arts.glob("*.json")):
    try:
        j = json.loads(f.read_text(encoding="utf-8"))
    except Exception:                                                       # noqa: BLE001
        continue
    if isinstance(j, dict) and (j.get("shots") or j.get("schema") == "visual-plan-output-v1"):
        vp = (f, j)
        break
if vp:
    f, j = vp
    print()
    print("visual_plan 产物:", f.name, "| keys:", sorted(j.keys())[:20])
    shots = j.get("shots") or []
    print("shots:", len(shots))
    for s in shots[:3]:
        print("-" * 70)
        print(json.dumps(s, ensure_ascii=False, indent=1)[:1100])
else:
    print("未找到 visual_plan_output")
