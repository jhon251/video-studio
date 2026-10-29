# -*- coding: utf-8 -*-
"""P21-3 前置：构建 40 段脚本（消费 pause 归因表 v2.1）+ 渲染（素材绑定展开到派生段）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
L = R / "docs" / "regression_2x" / "logs"
VS = R / "output" / "phase20_voice_sandbox"
SRC = R / "projects" / "p_96efdc03e1aa"
SANDBOX = R / "output" / "phase21_p21_3_sandbox"
sys.stdout.reconfigure(encoding="utf-8")

build = json.loads((L / "phase21_p21_1_2_build.json").read_text(encoding="utf-8"))
voice = json.loads((VS / "voice_output_40seg_v21.json").read_text(encoding="utf-8"))
per = json.loads((L / "phase20_p20_1_voice_slice.json").read_text(encoding="utf-8"))["per_segment"]
src_script = json.loads((R / "output/phase13e_script_sandbox/script_dcv2_derived_v1.json")
                        .read_text(encoding="utf-8"))
by_parent = {s["scene_id"]: s for s in src_script["segments"]}
tbl = {b["after_index"]: b["pause_s"] for b in voice["pause_attribution"]["boundaries"]}
trail = 2.0

# --- 40 段脚本（窗口 = 切片实测 + 该边界 pause；末段 + trailing）---
raw_durs = [float(x["duration_s"] or 0.0) for x in per]
segs, cursor = [], 0.0
for i, x in enumerate(per):
    p = by_parent[x["parent"]]
    d = raw_durs[i]
    pause = tbl.get(i, 0.0) if i < len(per) - 1 else 0.0
    segs.append({
        "scene_id": x["scene_id"], "index": i, "parent_scene_id": x["parent"],
        "narration": x["narration"], "narration_sha256": x["text_sha256"],
        "duration_s": round(d + pause + (trail if i == len(per) - 1 else 0.0), 3),
        "actual_tts_duration_s": round(d, 3), "pause_s": round(pause, 3),
        "pause_kind": ("original" if pause else "derived"),
        "chapter": p.get("chapter"), "tone": p.get("tone"),
        "visual_hint": p.get("visual_hint"),
        "text_edited": False, "text_unchanged": True,
    })
_exact = sum(raw_durs) + sum(tbl.values()) + trail
_delta = round(_exact - sum(s["duration_s"] for s in segs), 3)
segs[-1]["duration_s"] = round(segs[-1]["duration_s"] + _delta, 3)
total = round(sum(s["duration_s"] for s in segs), 3)
script = dict(src_script)
script.update({"segments": segs, "total_duration_s": total,
               "schema": "script-output-v2-p21-sentence-split",
               "_phase21": {"time_base_policy": "v2.1", "segments": len(segs),
                            "pause_attribution": "voice_output_40seg_v21.json",
                            "narrations_edited": False}})
sp = R / "output" / "phase21_script_sandbox"
sp.mkdir(parents=True, exist_ok=True)
f = sp / "script_dcv2_p21_40seg.json"
f.write_text(json.dumps(script, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print("40 段脚本: {} 段 | total_duration_s {} | voice base {} | Δ {}".format(
    len(segs), total, voice["audio_time_base_s"], round(total - voice["audio_time_base_s"], 3)))
oc = sum(len(str(s.get("narration") or "")) for s in src_script["segments"])
nc = sum(len(s["narration"]) for s in segs)
print("文本逐字: {} -> {}（相等 {}）".format(oc, nc, oc == nc))
over = [s for s in segs if s["duration_s"] > 25.0]
print("DQ-3 预期: >25s {}/{} = {:.1%} | max {:.1f}s".format(
    len(over), len(segs), len(over) / len(segs), max(s["duration_s"] for s in segs)))

# --- 渲染 ---
import argparse                                                                 # noqa: E402
ap = argparse.ArgumentParser()
ap.add_argument("--render", action="store_true")
a = ap.parse_args()
if not a.render:
    sys.exit(0)

from video_studio.cli import build_engine, load_config                          # noqa: E402
pool = json.loads((L / "phase16_retrieval_payload.json").read_text(encoding="utf-8"))
cands = pool["candidates"]
by_sha = {c["sha256"]: c for c in cands}
bound = sorted({t["selected_asset"]["sha256"] for t in build["timeline40"]})
sel_payload = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
               "candidates_total": len(bound), "material_provided": True,
               "candidates": [by_sha[s] for s in bound if s in by_sha],
               "_phase21_binding": {t["scene_id"]: t["selected_asset"]["sha256"]
                                    for t in build["timeline40"]}}
engine = build_engine(load_config(str(R / "config/config.json")))
pid = engine.create_project("Phase 21 P21-3 交付级候选（40 段 v2.1 时基 + 绑定展开）",
                            name="phase21-p21-3-delivery-candidate")
print("沙箱项目:", pid)
pdir = engine.project_dir(pid)
n = 0
for f2 in sorted((SRC / "media" / "voice").rglob("*")):
    if f2.is_file():
        t = pdir / "media" / "voice" / f2.relative_to(SRC / "media" / "voice")
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f2, t)
        n += 1
for f2 in sorted((VS / "seg").glob("*.wav")):
    t = pdir / "media" / "voice" / "seg" / f2.name
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(f2, t)
    n += 1
print("voice 媒体:", n)
ts = engine.create_task(pid, "script", "script", max_retries=0)
tv = engine.create_task(pid, "voice", "voice", max_retries=0)
tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                        inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                        max_retries=0)
from video_studio.agents.base import AGENTS                                     # noqa: E402
vj_vis = json.loads((SRC / "artifacts/a_a6279580600a.json").read_text(encoding="utf-8"))


def h_script(eng, task):
    aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                             summary="40 段句界拆分（v2.1 时基 {}s）".format(total))
    eng.attach_artifact(task["task_id"], aid)
    vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj_vis,
                             summary="沿用 H5 visual_plan")
    eng.attach_artifact(task["task_id"], vid)
    print("  [script]", aid)
    return {}


def h_voice(eng, task):
    v = dict(voice)
    v["audio"] = "media/voice/narration.mp3"
    v["segments"] = [{**s, "audio": "media/voice/" + s["audio"]} for s in v["segments"]]
    aid = eng.write_artifact(pid, task["task_id"], "voice_output", v,
                             summary="40 段切片 voice + pause 归因表 v2.1")
    eng.attach_artifact(task["task_id"], aid)
    print("  [voice]", aid, len(v["segments"]), "段")
    return {}


def h_retrieval(eng, task):
    aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", sel_payload,
                             summary="池候选 {} 张".format(len(sel_payload["candidates"])))
    eng.attach_artifact(task["task_id"], aid)
    print("  [retrieval]", aid)
    return {}


for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
    if role in AGENTS:
        AGENTS[role].run = fn
t0 = time.time()
try:
    for cyc in range(1, 8):
        k = engine.run_cycle(pid, limit=10)
        print("cycle {}: 派发 {} | {:.1f}s".format(cyc, k, time.time() - t0), flush=True)
        if k == 0:
            break
except Exception as exc:                                                        # noqa: BLE001
    print("异常:", type(exc).__name__, exc)
print("总耗时: {:.1f}s".format(time.time() - t0))
t = engine.db.get_task(te)
print("render status={} error={}".format((t or {}).get("status"),
                                         str((t or {}).get("error"))[:400]))
for f2 in sorted((pdir / "output").glob("*")):
    print("  out {} {:,}B".format(f2.name, f2.stat().st_size))
SANDBOX.mkdir(parents=True, exist_ok=True)
(SANDBOX / "fixture.json").write_text(json.dumps({
    "schema": "phase21-fixture-v1", "sandbox_project_id": pid,
    "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
    "script40": str(f.relative_to(R)).replace("\\", "/"),
    "script40_sha256": hashlib.sha256(f.read_bytes()).hexdigest(),
    "voice40": str((VS / "voice_output_40seg_v21.json").relative_to(R)).replace("\\", "/"),
    "time_base_policy": "v2.1", "segments": len(segs),
    "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}, ensure_ascii=False, indent=1),
    encoding="utf-8")
print("fixture ->", (SANDBOX / "fixture.json").relative_to(R))
