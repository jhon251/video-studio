# -*- coding: utf-8 -*-
"""P30-3 前置：用 **P30-1 pause 真实化音频** 渲染（复用 P27 渲染链，仅替换 voice 音频）。

变更点（最小）：
  · `voice_output.audio` → P30-1 产物 `output/phase30_audio/narration_p30.mp3`；
  · 各段 `duration_s` 保持 P20-1 实测（停顿由**音频自身**承担，不再靠时基外推）；
  · 段窗口按 `audio_segment_windows`（v2.1 表）给出，供视频侧素材持住。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
SRC = R / "projects" / "p_96efdc03e1aa"
SANDBOX = R / "output" / "phase30_p30_3_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"
AUDIO = R / "output" / "phase30_audio" / "narration_p30.mp3"
SEGDIR = R / "output" / "phase20_voice_sandbox" / "seg"
VISUAL = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase16_retrieval_payload.json"
MARKED = LOGS / "phase19_discriminative_registry.json"
CROPS = LOGS / "phase17_crop_safety_registry.json"
P16_FIX = R / "output" / "phase16_p16_5_sandbox" / "fixture.json"
EXCLUDE_HINTS = ("flag", "旗帜", "serbia", "塞尔维亚")
MAX_RESELECT = 4


def log(m):
    print(m, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "render.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    from video_studio.cli import build_engine, load_config

    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    segs = script["segments"]
    log("底片 {} 段 | {}s".format(len(segs), script["total_duration_s"]))
    log("P30-1 音频: {} ({:.3f}s)".format(
        AUDIO.name, json.loads((LOGS / "phase30_p30_1_pause_realize.json")
                               .read_text(encoding="utf-8"))["assertion_frozen_before_run"]
        ["measured_s"]))

    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = pool["candidates"]
    by_sha = {c["sha256"]: c for c in cands}
    flagged = set()
    for p, k in ((MARKED, "low_discriminative"), (CROPS, "low_crop_safety")):
        for r in json.loads(p.read_text(encoding="utf-8"))["assets"]:
            if r.get(k):
                flagged.add(r["sha256"])
    excluded = {c["sha256"] for c in cands
                if any(h in str(c.get("name") or "").lower() for h in EXCLUDE_HINTS)}

    p16 = json.loads(P16_FIX.read_text(encoding="utf-8"))
    import sqlite3
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    psel = {}
    for r in con.execute("select payload from events where project_id=? "
                         "and type='MATERIAL_TIMELINE'", (p16["sandbox_project_id"],)):
        for d in json.loads(r["payload"]).get("decisions") or []:
            psel[d["scene_id"]] = (d.get("selected_asset") or {}).get("sha256")
    con.close()
    used = [v for v in psel.values() if v]
    bad = flagged | excluded
    reselect = []
    for pid in sorted(psel):
        if psel[pid] in bad and len(reselect) < MAX_RESELECT:
            best, bn = None, None
            for c in cands:
                if c["sha256"] in bad:
                    continue
                n = used.count(c["sha256"])
                if best is None or n < bn:
                    best, bn = c, n
            if best:
                reselect.append({"parent_scene_id": pid, "from_sha12": str(psel[pid])[:12],
                                 "to_sha12": best["sha256"][:12],
                                 "approval": {"authorized_by": "human:project-owner",
                                              "approval_document": "Phase 30 授权书"}})
                psel[pid] = best["sha256"]
                used.append(best["sha256"])
    log("重选 {} 处".format(len(reselect)))
    bound = sorted({v for v in psel.values() if v})
    sel_payload = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
                   "candidates_total": len(bound), "material_provided": True,
                   "candidates": [by_sha[s] for s in bound if s in by_sha],
                   "_p30_binding": {s["scene_id"]: psel.get(s["parent_scene_id"])
                                    for s in segs}}

    engine = build_engine(load_config(str(R / "config" / "config.json")))
    pid = engine.create_project("Phase 30 P30-3 交付级候选（pause 真实化）",
                                name="phase30-p30-3-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    t = pdir / "media" / "voice" / "narration_p30.mp3"
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUDIO, t)
    for f in sorted(SEGDIR.glob("*.wav")):
        d = pdir / "media" / "voice" / "seg" / f.name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
    log("音频就位: narration_p30.mp3 + {} 切片".format(len(list(SEGDIR.glob('*.wav')))))

    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                            max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="P27 底片（v4.1 × 40 段）")
        eng.attach_artifact(task["task_id"], aid)
        vj = json.loads(VISUAL.read_text(encoding="utf-8"))
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj,
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        log("  [script] {}".format(aid))
        return {}

    def h_voice(eng, task):
        v = dict(voice)
        v["audio"] = "media/voice/narration_p30.mp3"      # ← P30-1 真实化音频
        v["_p30_pause_materialized"] = True
        v["segments"] = [{**s, "audio": "media/voice/" + s["audio"]} for s in v["segments"]]
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", v,
                                 summary="P30-1 真实化音频（977.952s）+ 40 段切片")
        eng.attach_artifact(task["task_id"], aid)
        log("  [voice] {} audio={}".format(aid, v["audio"]))
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", sel_payload,
                                 summary="池候选 {} 张".format(len(sel_payload["candidates"])))
        eng.attach_artifact(task["task_id"], aid)
        log("  [retrieval] {}".format(aid))
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn
    t0 = time.time()
    try:
        for cyc in range(1, 8):
            k = engine.run_cycle(pid, limit=10)
            log("cycle {}: 派发 {} | {:.1f}s".format(cyc, k, time.time() - t0))
            if k == 0:
                break
    except Exception as exc:                                                    # noqa: BLE001
        log("异常: {}: {}".format(type(exc).__name__, exc))
        log(traceback.format_exc()[-1200:])
    log("总耗时: {:.1f}s".format(time.time() - t0))
    tt = engine.db.get_task(te)
    log("render: status={} error={}".format((tt or {}).get("status"),
                                            str((tt or {}).get("error"))[:400]))
    for f in sorted((pdir / "output").glob("*")):
        log("  out {} {:,}B".format(f.name, f.stat().st_size))
    (SANDBOX / "fixture.json").write_text(json.dumps({
        "schema": "phase30-fixture-v1", "sandbox_project_id": pid,
        "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
        "script_sha256": sha(SCRIPT), "audio_sha256": sha(AUDIO),
        "reselect": reselect, "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
