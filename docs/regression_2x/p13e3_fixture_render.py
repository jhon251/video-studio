# -*- coding: utf-8 -*-
"""P13E-3 ② 夹具构建 + 渲染（生产路径 editing._render，运动 enabled=true）。

授权：情形② —— v2 时基（沙箱 voice 派生件补 audio_time_base_s）。

用法（同一个脚本，build 与 run 必须在**同一进程**内注册依赖回调，
否则第二轮派发时依赖任务会变成 no-op SUCCEEDED、不产生产物，
下游 editing 任务将永远停在 PENDING —— 已实测）：
  python p13e3_fixture_render.py --dry-run            # 拦截 ffmpeg：跑通全部门禁，不渲染
  python p13e3_fixture_render.py                      # 真渲染（后台作业）
  python p13e3_fixture_render.py --project p_xxx      # 复用已建夹具

零覆盖纪律：全部写入沙箱项目目录 + output/phase13e_p13e3_sandbox/
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
SANDBOX = R / "output" / "phase13e_p13e3_sandbox"

AUDIO_TIME_BASE_S = 978.656
DERIVED_SCRIPT = R / "output" / "phase13e_script_sandbox" / "script_dcv2_derived_v1.json"
VOICE_ART = SRC / "artifacts" / "a_e99273b936c0.json"
VISUAL_ART = SRC / "artifacts" / "a_a6279580600a.json"
RETR_ART = SRC / "artifacts" / "a_71f77918bc8a.json"


def log(msg: str) -> None:
    line = str(msg)
    print(line, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "fixture_build.log").open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_media(dst: pathlib.Path) -> dict:
    src_media = SRC / "media"
    dst_media = dst / "media"
    copied = {}
    for f in sorted(src_media.rglob("*")):
        if not f.is_file():
            continue
        rel = f.relative_to(src_media)
        target = dst_media / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, target)
        copied[rel.as_posix()] = target.stat().st_size
    return copied


# ---------------------------------------------------------------- 依赖任务产物
def dep_handler(role: str):
    """script / voice / retrieval 三个依赖角色的确定性产物处理器。"""

    def handler(eng, task):
        pid = task["project_id"]
        pd = eng.project_dir(pid)
        if role == "script":
            art = json.loads(DERIVED_SCRIPT.read_text(encoding="utf-8"))
            aid = eng.write_artifact(pid, task["task_id"], "script_output", art,
                                     summary="DCv2 派生脚本（978.656s / 21 段 / 文本逐字未改）")
            eng.attach_artifact(task["task_id"], aid)
            vj = json.loads(VISUAL_ART.read_text(encoding="utf-8"))
            vid2 = eng.write_artifact(pid, task["task_id"], "visual_plan_output", vj,
                                      summary="沿用 H5 谱系 visual_plan（只读复制）")
            eng.attach_artifact(task["task_id"], vid2)
            log("  [script] artifact={} ({} 段) + visual_plan={}".format(
                aid, len(art.get("segments") or []), vid2))
            return {"script_artifact": aid, "visual_plan_artifact": vid2}

        if role == "voice":
            vj = json.loads(VOICE_ART.read_text(encoding="utf-8"))
            vj["audio"] = "media/voice/narration.mp3"
            vj["audio_time_base_s"] = AUDIO_TIME_BASE_S
            vj["_dcv2_p13e3_derivation"] = {
                "audio_time_base_s_source":
                    "Σ actual_tts_duration_s(961.656) + pause 0.75×20(15.0) + trailing 2.0",
                "authoritative_narration_track_s": 961.656,
                "derived_from_artifact": "a_e99273b936c0",
                "derived_from_sha256": sha256_file(VOICE_ART),
                "policy": "duration_contract_v2 (audio_time_base authoritative)",
                "note": "原 voice 产物零改动；本件为沙箱派生，仅补 v2 权威字段 + 音频相对路径",
                "authorized_by": "P13E-3 ② 情形②（用户授权启用 v2 时基）",
            }
            aid = eng.write_artifact(pid, task["task_id"], "voice_output", vj,
                                     summary="既有旁白产物（沙箱派生：audio_time_base_s=978.656）")
            eng.attach_artifact(task["task_id"], aid)
            log("  [voice] artifact={} complete={} audio_time_base_s={}".format(
                aid, vj.get("complete"), vj.get("audio_time_base_s")))
            return {"voice_artifact": aid}

        if role == "retrieval":
            rj = json.loads(RETR_ART.read_text(encoding="utf-8"))
            missing = [str(c.get("path") or "") for c in (rj.get("candidates") or [])
                       if not (pd / "media" / str(c.get("path") or "")).is_file()]
            rj["_dcv2_p13e3_derivation"] = {
                "retrieval_source": "a_71f77918bc8a",
                "retrieval_source_sha256": sha256_file(RETR_ART),
                "supply": "沿用既有项目检索产物（素材池）+ H5 binding 继承",
                "rel_paths_unchanged": True,
                "missing_candidate_files": missing,
            }
            aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates", rj,
                                     summary="既有检索产物（{} 候选 / mode={}）".format(
                                         len(rj.get("candidates") or []), rj.get("material_mode")))
            eng.attach_artifact(task["task_id"], aid)
            log("  [retrieval] artifact={} candidates={} mode={} missing={}".format(
                aid, len(rj.get("candidates") or []), rj.get("material_mode"), len(missing)))
            return {"retrieval_artifact": aid}
        return {}
    return handler


def register_dep_handlers(engine, pid: str) -> int:
    """把三个依赖角色的处理器挂到该项目所有未完成的依赖任务上。返回挂载数。"""
    from video_studio.agents.base import AGENTS
    role_by_type = {"script": "script", "voice": "voice", "retrieval": "retrieval"}
    n = 0
    for t in engine.db.list_tasks(pid):
        if t["status"] in ("SUCCEEDED", "SUPERSEDED"):
            continue
        role = role_by_type.get(t["task_type"])
        if role is None:
            continue
        if role not in AGENTS:
            log("  !! 未注册 agent_role: {}（任务 {}）".format(role, t["task_id"]))
            continue
        AGENTS[role].run = dep_handler(role)
        n += 1
    return n


def build(project_id: str | None):
    """建沙箱项目 + 三条依赖任务 + editing 任务（同进程内随后 run）。"""
    from video_studio.cli import build_engine, load_config

    cfg = load_config(str(R / "config" / "config.json"))
    engine = build_engine(cfg)

    if project_id:
        pid = project_id
        log("复用既有沙箱项目: " + pid)
    else:
        pid = engine.create_project(
            "P13E-3 ② 全片运动候选渲染（DCv2 谱系 / 978.7s / 运动 enabled）",
            name="phase13e-p13e3-motion-candidate")
        log("新建沙箱项目: " + pid)
        copied = copy_media(engine.project_dir(pid))
        log("media 复制: {} 个文件".format(len(copied)))
        t_script = engine.create_task(pid, "script", "script", max_retries=0)
        t_voice = engine.create_task(pid, "voice", "voice", max_retries=0)
        t_retr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
        t_edit = engine.create_task(
            pid, "render", "editing", dependencies=[t_script, t_voice, t_retr],
            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
            max_retries=0)
        log("任务: script={} voice={} retrieval={} editing={}".format(
            t_script, t_voice, t_retr, t_edit))
        (SANDBOX / "fixture.json").write_text(json.dumps({
            "schema": "phase13e-p13e3-fixture-v1",
            "sandbox_project_id": pid,
            "source_project_id": SRC_PID,
            "authoritative_film":
                "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
            "tasks": {"script": t_script, "voice": t_voice,
                      "retrieval": t_retr, "editing": t_edit},
            "render_params": {"resolution": "1920x1080", "fps": 25},
            "audio_time_base_s": AUDIO_TIME_BASE_S,
            "derived_script": str(DERIVED_SCRIPT.relative_to(R)).replace("\\", "/"),
            "derived_script_sha256": sha256_file(DERIVED_SCRIPT),
            "motion_switch": "config/render_motion.json",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }, ensure_ascii=False, indent=1), encoding="utf-8")
        return pid, t_edit

    # 复用已有夹具：找回 editing 任务
    fix = json.loads((SANDBOX / "fixture.json").read_text(encoding="utf-8"))
    return pid, fix["tasks"]["editing"]


def run(project_id: str, t_edit: str, dry: bool, limit: int) -> None:
    from video_studio.cli import build_engine, load_config
    from video_studio.tools.ffmpeg_tool import FFmpegTool

    cfg = load_config(str(R / "config" / "config.json"))
    engine = build_engine(cfg)

    n_reg = register_dep_handlers(engine, project_id)
    log("依赖任务处理器挂载数: {}".format(n_reg))

    if dry:
        orig_exec = FFmpegTool.execute

        def guarded(self, inputs, ctx):
            if inputs.get("op") == "raw":
                raise RuntimeError("__P13E3_DRY_RUN_STOP__（夹具干跑：已在 ffmpeg 之前拦停）")
            return orig_exec(self, inputs, ctx)
        FFmpegTool.execute = guarded
        log("=== DRY-RUN：拦截 op=raw，仅跑通门禁 ===")
    else:
        orig_exec = None
        log("=== 真渲染：走 FFmpegTool op=raw（后台作业）===")

    t0 = time.time()
    log("=== run_cycle 开始（project={} limit={}）===".format(project_id, limit))
    try:
        # dispatchable() 是本轮快照 ⇒ 依赖刚转 SUCCEEDED 的任务需下一轮才派发
        for cycle in range(1, 8):
            n = engine.run_cycle(project_id, limit=limit)
            log("cycle {}: 派发 {} 个任务 | 累计 {:.1f}s".format(
                cycle, n, time.time() - t0))
            if n == 0:
                break
    except Exception as exc:                                    # noqa: BLE001
        log("run_cycle 抛异常: {}: {}".format(type(exc).__name__, exc))
        log(traceback.format_exc()[-3000:])
    finally:
        if dry and orig_exec is not None:
            FFmpegTool.execute = orig_exec

    log("总耗时: {:.1f}s".format(time.time() - t0))
    log("--- 任务状态 ---")
    for tid, label in ((t_edit, "editing"),):
        t = engine.db.get_task(tid)
        if t:
            log("  {} {} status={} error={}".format(label, tid, t["status"],
                                                    str(t.get("error"))[:600]))
            for aid in t.get("artifacts") or []:
                a = engine.db.get_artifact(aid)
                if a:
                    log("    artifact {} type={} {:.0f}B".format(aid, a["type"], a["size"]))
    pd = engine.project_dir(project_id)
    log("--- 输出目录 ---")
    for f in sorted((pd / "output").glob("*")):
        log("  {} {:,}B".format(f.name, f.stat().st_size))
    log("--- render/ 目录 ---")
    rd = pd / "render"
    if rd.is_dir():
        for f in sorted(rd.glob("*")):
            log("  {} {:,}B".format(f.name, f.stat().st_size))
        me = rd / "motion_evidence.json"
        if me.is_file():
            mj = json.loads(me.read_text(encoding="utf-8"))
            log("  motion counts: {}".format(json.dumps(mj.get("plan_counts"),
                                                        ensure_ascii=False)))
            log("  motion applied: {}".format([e["scene_id"] for e in (mj.get("applied") or [])]))
            log("  motion fallback: {}".format([e["scene_id"] for e in (mj.get("fallback") or [])]))
    else:
        log("  (render/ 未创建)")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--project", default=None)
    ap.add_argument("--limit", type=int, default=10)
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    pid, t_edit = build(args.project)
    run(pid, t_edit, args.dry_run, args.limit)


if __name__ == "__main__":
    main()
