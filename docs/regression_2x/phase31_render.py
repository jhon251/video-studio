# -*- coding: utf-8 -*-
"""P31-2/P31-3 渲染测量：用**当前池自动选材**（生产路径）渲染 40 景候选，
并把渲染实际使用的 material_timeline **落盘**，用于 DQ-2 / A1 / A2 的权威复算。

与 phase30_render.py 的差异（全部为最小必要差异）：
  · 不注入 `_p30_binding`（让生产自动选材自己决定绑定）⇒ 得到**可复算**的 DQ-2；
  · 渲染后从 DB 取 MATERIAL_TIMELINE 决策 + 权威窗口，落盘 `material_timeline.json`。

零 LLM、零 VLM、零网络。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sqlite3
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
SRC = R / "projects" / "p_96efdc03e1aa"
SANDBOX = R / "output" / "phase31_p31_3_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
SCRIPT = R / "output" / "phase27_script_sandbox" / "script_p27_v41_40seg.json"
VOICE = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg_v21.json"
AUDIO = R / "output" / "phase30_audio" / "narration_p30.mp3"
SEGDIR = R / "output" / "phase20_voice_sandbox" / "seg"
VISUAL = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase16_retrieval_payload.json"


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
    log("底片 {} 段 | 声明 {}s".format(len(segs), script["total_duration_s"]))

    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    log("池候选 {} 张（有本地路径）".format(len(cands)))

    engine = build_engine(load_config(str(R / "config" / "config.json")))
    pid = engine.create_project("Phase 31 P31-3 交付级候选（末段窗口修复 + H7 片尾卡前）",
                                name="phase31-p31-3-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    t = pdir / "media" / "voice" / "narration_p30.mp3"
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUDIO, t)
    nseg = 0
    for f in sorted(SEGDIR.glob("*.wav")):
        d = pdir / "media" / "voice" / "seg" / f.name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
        nseg += 1
    log("音频就位: narration_p30.mp3 + {} 切片".format(nseg))

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
        v["audio"] = "media/voice/narration_p30.mp3"
        v["_p30_pause_materialized"] = True
        v["segments"] = [{**s, "audio": "media/voice/" + s["audio"]} for s in v["segments"]]
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", v,
                                 summary="P30-1 真实化音频（977.952s）+ 40 段切片")
        eng.attach_artifact(task["task_id"], aid)
        log("  [voice] {}".format(aid))
        return {}

    def h_retrieval(eng, task):
        # 生产自动选材：池中不带 _p30_binding
        sel = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
               "candidates_total": len(cands), "material_provided": True,
               "candidates": cands}
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", sel,
                                 summary="池候选 {} 张（自动选材）".format(len(cands)))
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
        log(traceback.format_exc()[-1500:])
    log("总耗时: {:.1f}s".format(time.time() - t0))
    tt = engine.db.get_task(te)
    log("render: status={} error={}".format((tt or {}).get("status"),
                                            str((tt or {}).get("error"))[:400]))
    for f in sorted((pdir / "output").glob("*")):
        log("  out {} {:,}B".format(f.name, f.stat().st_size))

    # ---- 落盘渲染实际使用的绑定（供权威 DQ-2 / A1 / A2 复算）----
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (pid,)).fetchone()
    con.close()
    decisions = json.loads(r["payload"])["decisions"] if r else []
    (SANDBOX / "material_timeline.json").write_text(json.dumps(
        {"schema": "p31-material-timeline-v1", "project_id": pid,
         "decisions": decisions}, ensure_ascii=False, indent=1), encoding="utf-8")
    log("material_timeline -> {} 条决策".format(len(decisions)))

    (SANDBOX / "fixture.json").write_text(json.dumps({
        "schema": "phase31-fixture-v1", "sandbox_project_id": pid,
        "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
        "script_sha256": sha(SCRIPT), "audio_sha256": sha(AUDIO),
        "n_pool": len(cands),
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
