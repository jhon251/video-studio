# -*- coding: utf-8 -*-
"""P16-5 交付级候选重渲染（Phase 16）。

与 13-E 的差异（其余逐字沿用同一生产路径与配方）：
  · 沙箱项目换新（`output/phase16_p16_5_sandbox/`）
  · retrieval 载荷 = **扩池后的 12 张候选**（P16-2 登记 + P16-3 获取）
  · media 内**不复制**源池图像：新载荷用**绝对路径**指向源项目 media（保证字节一致、零覆盖）
  · 运动 enabled=true（沿用 config/render_motion.json）；派生脚本文本零改动

用法：
  python phase16_render.py --dry-run     # 干跑：拦截 ffmpeg，验门禁
  python phase16_render.py               # 真渲染（后台作业）
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
SANDBOX = R / "output" / "phase16_p16_5_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"

AUDIO_TIME_BASE_S = 978.656
DERIVED_SCRIPT = R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json"
VOICE_ART = SRC / "artifacts" / "a_e99273b936c0.json"
VISUAL_ART = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase16_retrieval_payload.json"


def log(msg: str) -> None:
    line = str(msg)
    print(line, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "render.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_voice_media(dst: pathlib.Path) -> int:
    """只复制 voice/（旁白音频）；图像用源项目绝对路径，避免字节分叉与覆盖。"""
    src_v = SRC / "media" / "voice"
    dst_v = dst / "media" / "voice"
    n = 0
    for f in sorted(src_v.rglob("*")):
        if f.is_file():
            t = dst_v / f.relative_to(src_v)
            t.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, t)
            n += 1
    return n


def dep_handler(role: str):
    def handler(eng, task):
        pid = task["project_id"]
        pd = eng.project_dir(pid)
        if role == "script":
            art = json.loads(DERIVED_SCRIPT.read_text(encoding="utf-8"))
            aid = eng.write_artifact(pid, task["task_id"], "script_output", art,
                                     summary="DCv2 派生脚本（沿用，文本零改动）")
            eng.attach_artifact(task["task_id"], aid)
            vj = json.loads(VISUAL_ART.read_text(encoding="utf-8"))
            vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj,
                                     summary="沿用 H5 谱系 visual_plan（只读复制）")
            eng.attach_artifact(task["task_id"], vid)
            log("  [script] {} + visual_plan {}".format(aid, vid))
            return {"script": aid, "visual_plan": vid}
        if role == "voice":
            vj = json.loads(VOICE_ART.read_text(encoding="utf-8"))
            vj["audio"] = "media/voice/narration.mp3"
            vj["audio_time_base_s"] = AUDIO_TIME_BASE_S
            vj["_phase16_derivation"] = {
                "audio_time_base_s_source":
                    "Σ actual_tts_duration_s(961.656) + pause 0.75×20(15.0) + trailing 2.0",
                "derived_from_artifact": "a_e99273b936c0",
                "derived_from_sha256": sha256_file(VOICE_ART),
                "note": "原 voice 产物零改动；同 13-E 口径（v2 时基）",
            }
            aid = eng.write_artifact(pid, task["task_id"], "voice_output", vj,
                                     summary="旁白产物（v2 时基 audio_time_base_s=978.656）")
            eng.attach_artifact(task["task_id"], aid)
            log("  [voice] {} audio_time_base_s={}".format(aid, vj["audio_time_base_s"]))
            return {"voice": aid}
        if role == "retrieval":
            rj = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
            bad = []
            for c in rj.get("candidates") or []:
                p = pathlib.Path(c["path"])
                if not p.is_file():
                    bad.append(c["path"])
            if bad:
                raise RuntimeError("扩池载荷含不存在的候选: {}".format(bad[:4]))
            rj["_phase16"] = {
                "pool_source": POOL_PAYLOAD.name,
                "pool_sha256": sha256_file(POOL_PAYLOAD),
                "candidates_total": len(rj.get("candidates") or []),
                "note": "Phase 16 扩池（P16-2 登记 + P16-3 受治理获取）；路径为绝对路径，字节与源一致",
            }
            aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", rj,
                                     summary="扩池候选 {} 张（Phase 16）".format(
                                         len(rj.get("candidates") or [])))
            eng.attach_artifact(task["task_id"], aid)
            log("  [retrieval] {} candidates={}".format(
                aid, len(rj.get("candidates") or [])))
            return {"retrieval": aid}
        return {}
    return handler


def build():
    from video_studio.cli import build_engine, load_config
    cfg = load_config(str(R / "config" / "config.json"))
    engine = build_engine(cfg)
    pid = engine.create_project(
        "Phase 16 P16-5 交付级候选重渲染（扩池 12 张 / 运动 enabled / 978.7s）",
        name="phase16-p16-5-delivery-candidate")
    log("新建沙箱项目: " + pid)
    n = copy_voice_media(engine.project_dir(pid))
    log("voice 媒体复制: {} 个文件（图像不复制：用源项目绝对路径）".format(n))
    t_script = engine.create_task(pid, "script", "script", max_retries=0)
    t_voice = engine.create_task(pid, "voice", "voice", max_retries=0)
    t_retr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    t_edit = engine.create_task(
        pid, "render", "editing", dependencies=[t_script, t_voice, t_retr],
        inputs={"render_params": {"resolution": "1920x1080", "fps": 25}}, max_retries=0)
    log("任务: script={} voice={} retrieval={} editing={}".format(
        t_script, t_voice, t_retr, t_edit))
    (SANDBOX / "fixture.json").write_text(json.dumps({
        "schema": "phase16-fixture-v1",
        "sandbox_project_id": pid, "source_project_id": SRC_PID,
        "tasks": {"script": t_script, "voice": t_voice,
                  "retrieval": t_retr, "editing": t_edit},
        "pool_payload": str(POOL_PAYLOAD.relative_to(R)).replace("\\", "/"),
        "pool_sha256": sha256_file(POOL_PAYLOAD),
        "derived_script_sha256": sha256_file(DERIVED_SCRIPT),
        "render_params": {"resolution": "1920x1080", "fps": 25},
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return pid, t_edit


def register(engine, pid):
    from video_studio.agents.base import AGENTS
    m = {"script": "script", "voice": "voice", "retrieval": "retrieval"}
    n = 0
    for t in engine.db.list_tasks(pid):
        if t["status"] in ("SUCCEEDED", "SUPERSEDED"):
            continue
        role = m.get(t["task_type"])
        if role and role in AGENTS:
            AGENTS[role].run = dep_handler(role)
            n += 1
    return n


def run(project_id, t_edit, dry, limit):
    from video_studio.cli import build_engine, load_config
    from video_studio.tools.ffmpeg_tool import FFmpegTool
    cfg = load_config(str(R / "config" / "config.json"))
    engine = build_engine(cfg)
    log("依赖任务处理器挂载数: {}".format(register(engine, project_id)))
    orig = None
    if dry:
        orig = FFmpegTool.execute

        def guarded(self, inputs, ctx):
            if inputs.get("op") == "raw":
                raise RuntimeError("__PHASE16_DRY_RUN_STOP__")
            return orig(self, inputs, ctx)
        FFmpegTool.execute = guarded
        log("=== DRY-RUN：拦截 op=raw ===")
    t0 = time.time()
    try:
        for cyc in range(1, 8):
            n = engine.run_cycle(project_id, limit=limit)
            log("cycle {}: 派发 {} | 累计 {:.1f}s".format(cyc, n, time.time() - t0))
            if n == 0:
                break
    except Exception as exc:                                                    # noqa: BLE001
        log("run_cycle 异常: {}: {}".format(type(exc).__name__, exc))
        log(traceback.format_exc()[-2500:])
    finally:
        if dry and orig is not None:
            FFmpegTool.execute = orig
    log("总耗时: {:.1f}s".format(time.time() - t0))
    t = engine.db.get_task(t_edit)
    log("--- editing 任务: status={} error={}".format(
        (t or {}).get("status"), str((t or {}).get("error"))[:500]))
    for aid in (t or {}).get("artifacts") or []:
        a = engine.db.get_artifact(aid)
        if a:
            log("    artifact {} type={} {:.0f}B".format(aid, a["type"], a["size"]))
    pd = engine.project_dir(project_id)
    for f in sorted((pd / "output").glob("*")):
        log("  out {} {:,}B".format(f.name, f.stat().st_size))
    rd = pd / "render"
    if rd.is_dir():
        for f in sorted(rd.glob("*")):
            log("  render/ {} {:,}B".format(f.name, f.stat().st_size))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=10)
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    pid, te = build()
    run(pid, te, a.dry_run, a.limit)


if __name__ == "__main__":
    main()
