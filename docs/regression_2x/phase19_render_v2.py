# -*- coding: utf-8 -*-
"""P19-4 v1：**保持 21 段时基**的渲染（旁白音频=事实来源） + P19-1 仲裁层**实测**。

现实约束（如实登记）：**拆镜后时基重排与既有 voice 产物冲突**。
既有 `voice_output` 是 **21 段**（Σ actual TTS = 961.656s，v2 权威 `audio_time_base_s`=978.656s）；
拆成 42 段后，渲染前闸门要求**每个脚本段都有合法音频**（`voice 产物不完整：缺少合法音频的段落 [21..41]`）
⇒ **无法在既有旁白音频上直接渲染 42 段时基**（这也是拆镜执行必须与旁白重配/音频重切同阶段进行的证据）。

本驱动因此按**可执行路线**推进：沿用 v2 时基（978.656s）× **21 段**（旁白零改动），
并**实测 P19-1 仲裁层**——对**全部 21 景**执行 VLM 存在性核验（即渲染后闸门会问的同一个问题），
产出 `RENDER_ARBITRATION` 等价证据与成本台账。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import shutil
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
SRC_PID = "p_96efdc03e1aa"
SRC = R / "projects" / SRC_PID
SANDBOX = R / "output" / "phase19_p19_4_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
AUDIO_TIME_BASE_S = 978.656
DERIVED_SCRIPT = R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json"
VOICE_ART = SRC / "artifacts" / "a_e99273b936c0.json"
VISUAL_ART = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase16_retrieval_payload.json"
MARKED = LOGS / "phase19_discriminative_registry.json"
CROPS = LOGS / "phase17_crop_safety_registry.json"


def log(m):
    print(m, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "render.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def flagged_shas():
    f = set()
    for p, k in ((MARKED, "low_discriminative"), (CROPS, "low_crop_safety")):
        j = json.loads(p.read_text(encoding="utf-8"))
        for r in j["assets"]:
            if r.get(k):
                f.add(r["sha256"])
    return f


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from video_studio.cli import build_engine, load_config

    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = pool["candidates"]
    by_sha = {c["sha256"]: c for c in cands}
    flagged = flagged_shas()
    script = json.loads(DERIVED_SCRIPT.read_text(encoding="utf-8"))
    segs = script["segments"]
    log("脚本: {} 段 | 总时长 {}s（沿用 13-E 派生脚本，文本零改动）".format(
        len(segs), script["total_duration_s"]))
    log("池 {} 张 | 标记 {} 张".format(len(cands), len(flagged)))

    # 素材继承（Phase 16 选材）+ 标记素材重选（≤4 处，同一转录批准口径）
    import sqlite3
    p16 = json.loads((R / "output/phase16_p16_5_sandbox/fixture.json")
                     .read_text(encoding="utf-8"))
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    sel = {}
    for r in con.execute("select payload from events where project_id=? "
                         "and type='MATERIAL_TIMELINE'", (p16["sandbox_project_id"],)):
        for d in json.loads(r["payload"]).get("decisions") or []:
            sel[d["scene_id"]] = (d.get("selected_asset") or {}).get("sha256")
    con.close()
    reselect = []
    used = [v for v in sel.values() if v]
    for sid in sorted(sel):
        if sel[sid] in flagged and len(reselect) < 4:
            best, bn = None, None
            for c in cands:
                if c["sha256"] in flagged:
                    continue
                n = used.count(c["sha256"])
                if best is None or n < bn:
                    best, bn = c, n
            if best:
                reselect.append({"scene_id": sid, "from_sha12": str(sel[sid])[:12],
                                 "to_sha12": best["sha256"][:12],
                                 "approval": {"authorized_by": "human:project-owner",
                                              "approval_document": "Phase 19 授权书"}})
                sel[sid] = best["sha256"]
                used.append(best["sha256"])   # 立刻计入 ⇒ 后续景选到**不同**素材，避免 DQ-2 恶化
    log("标记素材重选: {} 处".format(len(reselect)))
    for x in reselect:
        log("  {} {} -> {}".format(x["scene_id"], x["from_sha12"], x["to_sha12"]))

    # 引擎侧候选池 = 被实际绑定的素材（避免引擎重选漂移）
    bound = sorted({v for v in sel.values() if v})
    sel_payload = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
                   "candidates_total": len(bound), "material_provided": True,
                   "candidates": [by_sha[s] for s in bound if s in by_sha],
                   "_phase19_binding": dict(sel)}
    engine = build_engine(load_config(str(R / "config" / "config.json")))
    pid = engine.create_project("Phase 19 P19-4 交付级渲染（v2 时基 21 段 / 仲裁层 enabled）",
                                name="phase19-p19-4-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    n = 0
    for f in sorted((SRC / "media" / "voice").rglob("*")):
        if f.is_file():
            t = pdir / "media" / "voice" / f.relative_to(SRC / "media" / "voice")
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
    log("voice 媒体: {} 个".format(n))

    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                            max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="13-E 派生脚本（21 段 / 978.656s / 文本零改动）")
        eng.attach_artifact(task["task_id"], aid)
        vj = json.loads(VISUAL_ART.read_text(encoding="utf-8"))
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj,
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        log("  [script] {}".format(aid))
        return {}

    def h_voice(eng, task):
        vj = json.loads(VOICE_ART.read_text(encoding="utf-8"))
        vj["audio"] = "media/voice/narration.mp3"
        vj["audio_time_base_s"] = AUDIO_TIME_BASE_S
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", vj,
                                 summary="旁白（v2 时基 978.656s）")
        eng.attach_artifact(task["task_id"], aid)
        log("  [voice] {}".format(aid))
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates",
                                 sel_payload,
                                 summary="绑定后的池候选 {} 张".format(
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
                raise RuntimeError("__PHASE19_DRY_RUN_STOP__")
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
    fx = {"schema": "phase19-fixture-v2", "sandbox_project_id": pid,
          "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
          "reselect": reselect, "flagged": sorted(flagged),
          "binding": sel_payload["_phase19_binding"],
          "script_sha256": sha(DERIVED_SCRIPT),
          "arbitration_config": str((R / "config/render_arbitration.json")
                                    .relative_to(R)).replace("\\", "/"),
          "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (SANDBOX / "fixture.json").write_text(json.dumps(fx, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
