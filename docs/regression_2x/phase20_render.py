# -*- coding: utf-8 -*-
"""P20-2 交付级渲染（40 段句界拆分时基 + 40 段 voice 派生产物 + 仲裁层 enabled）。"""
from __future__ import annotations

import argparse
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
SANDBOX = R / "output" / "phase20_p20_2_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
SCRIPT40 = R / "output" / "phase20_script_sandbox" / "script_dcv2_p20_40seg.json"
VOICE40 = R / "output" / "phase20_voice_sandbox" / "voice_output_40seg.json"
VOICE_SRC = R / "output" / "phase20_voice_sandbox"
VISUAL_ART = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase16_retrieval_payload.json"
MARKED = LOGS / "phase19_discriminative_registry.json"
CROPS = LOGS / "phase17_crop_safety_registry.json"
P16_FIX = R / "output" / "phase16_p16_5_sandbox" / "fixture.json"
MAX_RESELECT = 4


def log(m):
    print(m, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "render.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from video_studio.cli import build_engine, load_config

    script = json.loads(SCRIPT40.read_text(encoding="utf-8"))
    voice = json.loads(VOICE40.read_text(encoding="utf-8"))
    segs = script["segments"]
    log("40 段脚本: {} 段 | 总时长 {}s | voice base {}s".format(
        len(segs), script["total_duration_s"], voice["audio_time_base_s"]))
    if abs(script["total_duration_s"] - voice["audio_time_base_s"]) > 0.5:
        log("!! 脚本时基与 voice 时基不一致，STOP")
        return

    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = pool["candidates"]
    by_sha = {c["sha256"]: c for c in cands}
    flagged = set()
    for p, k in ((MARKED, "low_discriminative"), (CROPS, "low_crop_safety")):
        for r in json.loads(p.read_text(encoding="utf-8"))["assets"]:
            if r.get(k):
                flagged.add(r["sha256"])
    # 父景选材继承（Phase 16）+ 标记素材重选（≤4 处）
    p16 = json.loads(P16_FIX.read_text(encoding="utf-8"))
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
    reselect = []
    for pid in sorted(psel):
        if psel[pid] in flagged and len(reselect) < MAX_RESELECT:
            best, bn = None, None
            for c in cands:
                if c["sha256"] in flagged:
                    continue
                n = used.count(c["sha256"])
                if best is None or n < bn:
                    best, bn = c, n
            if best:
                reselect.append({"parent_scene_id": pid, "from_sha12": str(psel[pid])[:12],
                                 "to_sha12": best["sha256"][:12],
                                 "approval": {"authorized_by": "human:project-owner",
                                              "approval_document": "Phase 20 授权书"}})
                psel[pid] = best["sha256"]
                used.append(best["sha256"])
    log("标记素材重选: {} 处".format(len(reselect)))
    for x in reselect:
        log("  {} {} -> {}".format(x["parent_scene_id"], x["from_sha12"], x["to_sha12"]))

    bound = sorted({v for v in psel.values() if v})
    sel_payload = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
                   "candidates_total": len(bound), "material_provided": True,
                   "candidates": [by_sha[s] for s in bound if s in by_sha],
                   "_phase20_binding": {s["scene_id"]: psel.get(s["parent_scene_id"])
                                        for s in segs}}

    engine = build_engine(load_config(str(R / "config/config.json")))
    pid = engine.create_project("Phase 20 P20-2 交付级候选（40 段句界拆分 + 旁白切片）",
                                name="phase20-p20-2-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    n = 0
    for f in sorted((SRC / "media" / "voice").rglob("*")):
        if f.is_file():
            t = pdir / "media" / "voice" / f.relative_to(SRC / "media" / "voice")
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
    # 40 段切片也复制进沙箱（voice payload 用相对路径 seg/*.wav）
    for f in sorted((VOICE_SRC / "seg").glob("*.wav")):
        t = pdir / "media" / "voice" / "seg" / f.name
        t.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, t)
        n += 1
    log("voice 媒体（含切片）: {} 个".format(n))

    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                            max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="40 段句界拆分脚本（978.634s / 文本零改动）")
        eng.attach_artifact(task["task_id"], aid)
        vj = json.loads(VISUAL_ART.read_text(encoding="utf-8"))
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj,
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        log("  [script] {}".format(aid))
        return {}

    def h_voice(eng, task):
        vj = dict(voice)
        vj["audio"] = "media/voice/narration.mp3"
        for s in vj["segments"]:
            s["audio"] = "media/voice/{}".format(s["audio"])
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", vj,
                                 summary="40 段切片 voice（v2 时基 978.634s）")
        eng.attach_artifact(task["task_id"], aid)
        log("  [voice] {}（{} 段）".format(aid, len(vj["segments"])))
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", sel_payload,
                                 summary="池候选 {} 张（含降权重选）".format(
                                     len(sel_payload["candidates"])))
        eng.attach_artifact(task["task_id"], aid)
        log("  [retrieval] {} candidates={}".format(aid,
                                                    len(sel_payload["candidates"])))
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn

    if args.dry_run:
        from video_studio.tools.ffmpeg_tool import FFmpegTool
        orig = FFmpegTool.execute

        def guarded(self, inputs, ctx):
            if inputs.get("op") == "raw":
                raise RuntimeError("__PHASE20_DRY_RUN_STOP__")
            return orig(self, inputs, ctx)
        FFmpegTool.execute = guarded
        log("=== DRY-RUN ===")
    t0 = time.time()
    try:
        for cyc in range(1, 8):
            k = engine.run_cycle(pid, limit=args.limit)
            log("cycle {}: 派发 {} | 累计 {:.1f}s".format(cyc, k, time.time() - t0))
            if k == 0:
                break
    except Exception as exc:                                                    # noqa: BLE001
        log("run_cycle 异常: {}: {}".format(type(exc).__name__, exc))
        log(traceback.format_exc()[-1500:])
    log("总耗时: {:.1f}s".format(time.time() - t0))
    t = engine.db.get_task(te)
    log("render: status={} error={}".format((t or {}).get("status"),
                                            str((t or {}).get("error"))[:400]))
    for aid in (t or {}).get("artifacts") or []:
        art = engine.db.get_artifact(aid)
        if art:
            log("   artifact {} type={} {:.0f}B".format(aid, art["type"], art["size"]))
    for f in sorted((pdir / "output").glob("*")):
        log("  out {} {:,}B".format(f.name, f.stat().st_size))
    fx = {"schema": "phase20-fixture-v1", "sandbox_project_id": pid,
          "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
          "script40": str(SCRIPT40.relative_to(R)).replace("\\", "/"),
          "script40_sha256": sha(SCRIPT40),
          "voice40": str(VOICE40.relative_to(R)).replace("\\", "/"),
          "voice40_sha256": sha(VOICE40),
          "reselect": reselect, "flagged": sorted(flagged),
          "binding": sel_payload["_phase20_binding"],
          "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (SANDBOX / "fixture.json").write_text(json.dumps(fx, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
