# -*- coding: utf-8 -*-
"""P31：ASSET_INSUFFICIENT 逐景明细（渲染闸门阻断的景、期望/最佳素材与 corr）。只读。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
d = json.loads((R / "docs/regression_2x/logs/phase27_p27_3_verification.json")
               .read_text(encoding="utf-8"))
ps = d["per_scene_verify"]
print("checked={} failed_before={} failed_after={} vlm_cost={}".format(
    ps.get("checked"), ps.get("failed_before_arbitration"),
    ps.get("failed_after_arbitration"), ps.get("vlm_cost_usd")))
print()
print("=== arbitrated（仲裁后仍失败）===")
for a in ps.get("arbitrated") or []:
    v = a.get("vlm") or {}
    print("  {} corr={} presence={} {}", a.get("scene_id"), a.get("orig_corr"),
          v.get("presence"), str(v.get("reason"))[:110])
print()
# 渲染日志里的阻断明细
log = R / "output/phase31_p31_3_sandbox/render.log"
if log.is_file():
    txt = log.read_text(encoding="utf-8", errors="replace")
    i = txt.find("ASSET_INSUFFICIENT")
    print("=== P31 渲染 ASSET_INSUFFICIENT ===")
    print(txt[i:i + 1800] if i >= 0 else "(none)")
print()
print("=== 三指标/时长（新渲染）===")
print("需在验收脚本中实测成片")
