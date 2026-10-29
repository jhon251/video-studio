# -*- coding: utf-8 -*-
"""P34-1 处置准备：8 个卡景的候选集与旁白，判定"池内有候选可绑" vs "真缺口"。"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

TAG = "phase33_p33_4_sandbox"
SCRIPT = json.loads((R / "output/phase33_script_sandbox/script_p33_v41_40seg.json")
                    .read_text(encoding="utf-8"))
dec = json.loads((R / "output" / TAG / "material_timeline.json")
                 .read_text(encoding="utf-8"))["decisions"]
tb = json.loads((R / "output/phase33_voice/timebase_v41.json").read_text(encoding="utf-8"))
wins = {w["scene_id"]: w for w in tb["windows"]}
nar = {s["scene_id"]: s.get("narration") or "" for s in SCRIPT["segments"]}

out = {"schema": "p34-1-card-scene-candidates-v1", "scenes": []}
print("{:<7} {:<12} {:>6} {:>6} {}".format("scene", "window_s", "cands", "usable", "fallback_state"))
for d in dec:
    a = d.get("selected_asset") or {}
    if a.get("asset_id"):
        continue
    sid = d["scene_id"]
    cands = d.get("candidates") or []
    usable = [c for c in cands if c.get("usable", True)]
    w = wins.get(sid) or {}
    print("{:<7} {:<12.2f} {:>6} {:>6} {}".format(
        sid, w.get("window_s") or 0, len(cands), len(usable), d.get("fallback_state")))
    out["scenes"].append({
        "scene_id": sid, "window_s": w.get("window_s"),
        "start_s": w.get("start_s"), "end_s": w.get("end_s"),
        "narration": (nar.get(sid) or "")[:160],
        "insufficiency_class": d.get("insufficiency_class"),
        "fallback_state": d.get("fallback_state"),
        "candidates_total": len(cands),
        "candidates_usable": len(usable),
        "candidates": [{"name": c.get("name"), "sha256": str(c.get("sha256"))[:12],
                        "match_score": c.get("match_score"), "usable": c.get("usable", True),
                        "unusable_reason": c.get("unusable_reason"),
                        "license": c.get("license")} for c in cands[:8]],
    })

p = L / "p34_1_card_candidates.json"
p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

# 池现状
pool = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
cands = [c for c in pool["candidates"] if c.get("path")]
print()
print("池 {} 张（唯一 sha {}）".format(len(cands), len({c['sha256'] for c in cands})))
for c in sorted(cands, key=lambda x: str(x.get("name"))):
    print("   {:<50} {} {}x{}".format(str(c.get("name"))[:50],
                                      str(c.get("license"))[:14],
                                      c.get("width"), c.get("height")))
print()
print("-> " + p.relative_to(R).as_posix())
