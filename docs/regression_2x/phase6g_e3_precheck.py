# -*- coding: utf-8 -*-
"""只读预检：E3 的冻结设计（6-E 材料计划 C_self_made_spec）能否编译为合法 visual-aid spec。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.core import visual_aid as VA                        # noqa: E402

MP = R / "docs" / "regression_2x" / "phase6e_materials" / "phase6e_material_plan.json"
plan = json.loads(MP.read_text(encoding="utf-8"))
item = plan["items"]["E3"]
spec = VA.compile_from_plan_item(item)
vr = VA.verify_spec(spec)
print("material plan sha256:", hashlib.sha256(MP.read_bytes()).hexdigest())
print("compiled spec sha256:", VA.spec_sha256(spec))
print("panel ids:", [p["id"] for p in spec["panels"]])
print("panel count:", vr.get("panel_count"), "| layout:", spec["layout"])
print("verify errors/warnings:", vr.get("errors"), vr.get("warnings"))
print("rendered_text_lines keys:", list((vr.get("rendered_text_lines") or {}).keys()))
print("sources:", json.dumps(spec.get("sources"), ensure_ascii=False)[:200])
print("must_not:", json.dumps(spec.get("must_not"), ensure_ascii=False)[:200])
