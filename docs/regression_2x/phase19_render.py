# -*- coding: utf-8 -*-
"""P19-4 交付级最终渲染：拆镜后时间轴（v2, 42 段）× 池内素材 × 仲裁层 enabled。

关键设计：
  · 起点用 13-E/16 沙箱的**选材映射**（parent_scene_id → 同一素材 ⇒ **素材继承**，
    既满足授权书"两侧素材继承"，又**避免引擎重选**导致素材漂移）；
  · 被标记素材（low_crop_safety / low_discriminative）**降权**：对绑定这些素材的景
    生成重选候选（最多 4 处，同一转录批准口径）——本驱动按"每 parent 景取未标记素材中
    DQ-2 复用最少者"确定性替换，未标记者保持不动；
  · 运动 enabled（沿用 config/render_motion.json）；仲裁层 enabled（本阶段新建开关文件）。
"""
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
SRC_PID = "p_96efdc03e1aa"
SRC = R / "projects" / SRC_PID
SANDBOX = R / "output" / "phase19_p19_4_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
AUDIO_TIME_BASE_S = 978.656
VOICE_ART = SRC / "artifacts" / "a_e99273b936c0.json"
VISUAL_ART = SRC / "artifacts" / "a_a6279580600a.json"
SPLIT_SCRIPT = R / "output" / "phase19_script_sandbox" / "script_dcv2_split_v2.json"
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


def build_pool_and_selection():
    """池（含标记） + 每 parent 景的素材继承映射（来自 Phase 16 选材）。"""
    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    disc = json.loads(MARKED.read_text(encoding="utf-8"))
    crop = json.loads(CROPS.read_text(encoding="utf-8"))
    flagged = set()
    for r in disc["assets"]:
        if r["low_discriminative"]:
            flagged.add(r["sha256"])
    for r in crop["assets"]:
        if r["low_crop_safety"]:
            flagged.add(r["sha256"])
    cands = pool["candidates"]
    by_sha = {c["sha256"]: c for c in cands}
    # Phase 16 沙箱的选材（parent 景 → asset）
    sel16 = {}
    try:
        fix = json.loads(P16_FIX.read_text(encoding="utf-8"))
        con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                              + "?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        for r in con.execute("select payload from events where project_id=? "
                             "and type='MATERIAL_TIMELINE'", (fix["sandbox_project_id"],)):
            for d in json.loads(r["payload"]).get("decisions") or []:
                sel16[d["scene_id"]] = d.get("selected_asset") or {}
        con.close()
    except Exception as exc:                                                    # noqa: BLE001
        log("  !! 读取 Phase 16 选材失败: {}".format(exc))
    return cands, by_sha, flagged, sel16


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--no-arbitration", action="store_true")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    from video_studio.cli import build_engine, load_config

    cands, by_sha, flagged, sel16 = build_pool_and_selection()
    v2 = json.loads(SPLIT_SCRIPT.read_text(encoding="utf-8"))
    segs = v2["segments"]
    log("拆镜脚本 v2: {} 段 | 总时长 {}s".format(len(segs), v2["total_duration_s"]))
    log("池素材 {} 张 | 被标记（low_crop/low_discrim）{} 张: {}".format(
        len(cands), len(flagged), sorted(x[:12] for x in flagged)))

    # 素材继承 + 标记素材重选（≤4 处）
    parent_asset = {}
    for s in segs:
        pid = s.get("parent_scene_id") or s["scene_id"]
        parent_asset.setdefault(pid, (sel16.get(pid) or {}).get("sha256"))
    reselect = []
    for pid, asha in sorted(parent_asset.items()):
        if asha in flagged and len(reselect) < MAX_RESELECT and len(flagged) < len(cands):
            used = [v for v in parent_asset.values() if v]
            best, bestn = None, None
            for c in cands:
                if c["sha256"] in flagged:
                    continue
                n = used.count(c["sha256"])
                if best is None or n < bestn:
                    best, bestn = c, n
            if best is not None:
                parent_asset[pid] = best["sha256"]
                reselect.append({"parent_scene_id": pid, "from_sha12": str(asha)[:12],
                                 "to_sha12": best["sha256"][:12],
                                 "to_name": best["name"][:44],
                                 "reason": "被标记素材（low_crop_safety/low_discriminative）降权重选",
                                 "approval": {"authorized_by": "human:project-owner",
                                              "approval_document": "Phase 19 授权书"}})
    log("标记素材重选（≤{} 处）: {}".format(MAX_RESELECT, len(reselect)))
    for x in reselect:
        log("  {} {} -> {}".format(x["parent_scene_id"], x["from_sha12"], x["to_sha12"]))

    # 引擎侧：只提供"每个子镜绑定其 parent 素材"的检索载荷，避免引擎重选漂移
    sel_payload = {"schema": "retrieval-candidates-v1", "material_mode": "mixed",
                   "candidates_total": 0, "material_provided": True,
                   "candidates": [], "_phase19_binding": {}}
    for s in segs:
        pid = s.get("parent_scene_id") or s["scene_id"]
        c = by_sha.get(parent_asset.get(pid))
        if c:
            sel_payload["candidates"].append(c)
            sel_payload["_phase19_binding"][s["scene_id"]] = c["sha256"]
    # 去重（每个素材一条）
    seen, uniq = set(), []
    for c in sel_payload["candidates"]:
        if c["sha256"] in seen:
            continue
        seen.add(c["sha256"])
        uniq.append(c)
    sel_payload["candidates"] = uniq
    sel_payload["candidates_total"] = len(uniq)

    engine = build_engine(load_config(str(R / "config" / "config.json")))
    pid = engine.create_project("Phase 19 P19-4 交付级最终渲染（拆镜 v2 / 仲裁层 enabled）",
                                name="phase19-p19-4-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    # voice 媒体
    n = 0
    for f in sorted((SRC / "media" / "voice").rglob("*")):
        if f.is_file():
            t = pdir / "media" / "voice" / f.relative_to(SRC / "media" / "voice")
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
    log("voice 媒体复制: {} 个".format(n))

    # 依赖任务 + 渲染任务
    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                            max_retries=0)

    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        art = dict(v2)
        aid = eng.write_artifact(pid, task["task_id"], "script_output", art,
                                 summary="拆镜 v2（42 段 / 978.656s / 旁白逐字零改动）")
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
                                 summary="池候选 {} 张（含标记降权后的绑定）".format(
                                     len(sel_payload["candidates"])))
        eng.attach_artifact(task["task_id"], aid)
        log("  [retrieval] {} candidates={}".format(aid, len(sel_payload["candidates"])))
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn

    if a.dry_run:
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
            k = engine.run_cycle(pid, limit=a.limit)
            log("cycle {}: 派发 {} | 累计 {:.1f}s".format(cyc, k, time.time() - t0))
            if k == 0:
                break
    except Exception as exc:                                                    # noqa: BLE001
        log("run_cycle 异常: {}: {}".format(type(exc).__name__, exc))
        log(traceback.format_exc()[-1800:])
    log("总耗时: {:.1f}s".format(time.time() - t0))
    t = engine.db.get_task(te)
    log("render 任务 status={} error={}".format((t or {}).get("status"),
                                                str((t or {}).get("error"))[:600]))
    for aid in (t or {}).get("artifacts") or []:
        art = engine.db.get_artifact(aid)
        if art:
            log("   artifact {} type={} {:.0f}B".format(aid, art["type"], art["size"]))
    for f in sorted((pdir / "output").glob("*")):
        log("  out {} {:,}B".format(f.name, f.stat().st_size))
    fx = {"schema": "phase19-fixture-v1", "sandbox_project_id": pid,
          "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
          "split_script": str(SPLIT_SCRIPT.relative_to(R)).replace("\\", "/"),
          "split_script_sha256": sha(SPLIT_SCRIPT),
          "reselect": reselect, "flagged_assets": sorted(flagged),
          "binding": sel_payload["_phase19_binding"],
          "arbitration_enabled": not a.no_arbitration,
          "created_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
    (SANDBOX / "fixture.json").write_text(json.dumps(fx, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
