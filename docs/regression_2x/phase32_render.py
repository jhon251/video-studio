# -*- coding: utf-8 -*-
"""P32-4 终渲染：v4.1 × 40 景 × 运动 1.25（守卫）× **仲裁**（可接线）× 绑定回退 ×
pause 真实化 × **bank-derived-v2**，随后施加 **H7 片尾卡（in-window overlay，时长不变）**。

与 phase31_render.py 的差异（全部为最小必要差异）：
  1. **加载 `.env`**（`run.py` 同款）⇒ `VLM_API_KEY` 进入环境 ⇒ 仲裁层可真正接线；
  2. 渲染链读 `config/frame_match.json`（`bank_derived="v2"`）⇒ 逐景核验走 v2 口径；
  3. 渲染后施加 H7 片尾卡（drawtext 中文，显式字体；视频重编码 + 音频流复制）。

零 LLM。VLM 仅在仲裁层按需调用（fail-closed；不可用则跳过）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import shutil
import sqlite3
import subprocess
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
SANDBOX = R / "output" / "phase32_p32_4_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
SRC = R / "projects" / "p_96efdc03e1aa"
SCRIPT = R / "output/phase27_script_sandbox/script_p27_v41_40seg.json"
VOICE = R / "output/phase20_voice_sandbox/voice_output_40seg_v21.json"
AUDIO = R / "output/phase30_audio/narration_p30.mp3"
SEGDIR = R / "output/phase20_voice_sandbox/seg"
VISUAL = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "phase16_retrieval_payload.json"
FFMPEG = R / "bin" / "ffmpeg.exe"
FFPROBE = R / "bin" / "ffprobe.exe"
OUTRO_TEXT = "感谢观看　我们下期再见"
OUTRO_FONT = R"msyh.ttc"
OUTRO_FONTSDIR = r"C:\Windows\Fonts"
OUTRO_TAIL_S = 2.2          # 片尾卡覆盖末段时长（窗口内，**不改变总时长**）


def log(m):
    print(m, flush=True)
    SANDBOX.mkdir(parents=True, exist_ok=True)
    with (SANDBOX / "render.log").open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True)
    return round(float(r.stdout.strip().splitlines()[0]), 3) if r.stdout.strip() else None


def apply_outro_card(film: pathlib.Path, out: pathlib.Path) -> dict:
    """H7：在**末段窗口内**叠加片尾卡（drawtext，显式 CJK 字体）+ **母版整条音轨流复制**。

    **总时长不变**（只在原时间轴上重编码末段并拼接）⇒ 不触发时长例外。

    ⚠️ 实现要点（P32-4 踩坑修正）：拼接必须走 **MPEG-TS** 中间格式。
    首版用 MP4 `-c copy` concat，时间戳在接头处断裂 ⇒ 成片**视频轨只有 975.73s**
    （音频/容器 977.88s）⇒ 等于把 2.1s 变成"无新帧"的补齐区（正是本阶段要消灭的缺陷）。
    TS 以 90kHz 时基承载，stream copy 拼接后时间戳连续。
    """
    total = dur(film)
    t0 = max(total - OUTRO_TAIL_S, 0.0)
    tail = max(total - t0, 0.5)
    fp = pathlib.Path(OUTRO_FONTSDIR) / OUTRO_FONT
    if not fp.is_file():
        raise RuntimeError("OUTRO_FONT_MISSING: {}（fail-closed）".format(fp))
    fontopt = "fontfile='{}':".format(str(fp).replace("\\", "/").replace(":", "\\:"))
    vf = ("drawtext=text='{}':{}fontcolor=white:fontsize=64:"
          "box=1:boxcolor=black@0.55:boxborderw=24:x=(w-text_w)/2:y=h-300").format(
        OUTRO_TEXT, fontopt)
    work = SANDBOX / "work"
    work.mkdir(parents=True, exist_ok=True)
    for f in work.glob("*"):
        f.unlink()
    head, tailf = work / "head.ts", work / "tail.ts"
    joined = work / "joined.ts"
    steps = []
    # 前段：流复制到 TS
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-t", "{:.3f}".format(t0),
                    "-i", str(film), "-an", "-c:v", "copy", "-bsf:v", "h264_mp4toannexb",
                    "-f", "mpegts", str(head)], check=True)
    steps.append({"step": "head_stream_copy_ts", "window": [0.0, t0],
                  "sha256": sha(head), "bytes": head.stat().st_size,
                  "duration_s": dur(head)})
    # 末段：重编码（含片尾卡）到 TS
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", "{:.3f}".format(t0),
                    "-t", "{:.3f}".format(tail), "-i", str(film), "-vf", vf, "-an",
                    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-video_track_timescale", "25000",
                    "-f", "mpegts", str(tailf)], check=True)
    steps.append({"step": "tail_reencode_with_outro_card_ts", "window": [t0, total],
                  "seconds": tail, "drawtext": vf, "sha256": sha(tailf),
                  "bytes": tailf.stat().st_size, "duration_s": dur(tailf),
                  "font": {"file": str(fp), "bytes": fp.stat().st_size, "sha256": sha(fp)}})
    # TS 拼接（concat 协议，stream copy）
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-i",
                    "concat:{}|{}".format(head.as_posix(), tailf.as_posix()),
                    "-c", "copy", "-bsf:a", "aac_adtstoasc", "-f", "mpegts",
                    str(joined)], check=True)
    steps.append({"step": "ts_concat_stream_copy", "sha256": sha(joined),
                  "bytes": joined.stat().st_size, "duration_s": dur(joined)})
    # 合流：视频用拼接结果，音频**整条流复制**母版
    subprocess.run([str(FFMPEG), "-y", "-v", "error", "-i", str(joined), "-i", str(film),
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
                    "-movflags", "+faststart", str(out)], check=True)
    steps.append({"step": "mux_stream_copy_audio", "out": out.name,
                  "sha256": sha(out), "bytes": out.stat().st_size,
                  "duration_s": dur(out)})
    return {"steps": steps, "outro_text": OUTRO_TEXT, "window": [t0, total],
            "duration_before_s": total, "duration_after_s": dur(out),
            "duration_unchanged": abs((dur(out) or 0) - (total or 0)) <= 0.08}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    # ---- 关键：加载 .env（与 run.py 一致）⇒ VLM_API_KEY 进入环境 ----
    from video_studio.core.env import load_env
    loaded = load_env(R / ".env")
    log("load_env -> {}".format(sorted(loaded.keys())))
    from video_studio.cli import build_engine, load_config
    from video_studio.tools import vlm_judge as _vj
    _vcfg, _vsrc = _vj.resolve_config(
        json.loads((R / "config/config.json").read_text(encoding="utf-8")), root=R)
    _ok, _why = _vj.available(_vcfg)
    log("VLM available={} why={} src={}".format(_ok, _why, _vsrc))
    from video_studio.core import corr_diagnostics as _CD
    _bcfg, _bsrc = _CD.resolve_config(
        json.loads((R / "config/config.json").read_text(encoding="utf-8")), root=R)
    log("bank chain -> {} | source={}".format(_bcfg.get("bank_derived"), _bsrc))

    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice = json.loads(VOICE.read_text(encoding="utf-8"))
    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    log("底片 {} 段 | 池候选 {} 张".format(len(script["segments"]), len(cands)))

    engine = build_engine(load_config(str(R / "config" / "config.json")))
    pid = engine.create_project("Phase 32 P32-4 交付级候选（v2 + H7 片尾卡）",
                                name="phase32-p32-4-delivery-candidate")
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
    log("渲染总耗时: {:.1f}s".format(time.time() - t0))
    tt = engine.db.get_task(te)
    log("render: status={} error={}".format((tt or {}).get("status"),
                                            str((tt or {}).get("error"))[:300]))
    outs = sorted((pdir / "output").glob("*.mp4"))
    for f in outs:
        log("  out {} {:,}B".format(f.name, f.stat().st_size))

    # ---- 落盘绑定 + 仲裁记录 ----
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (pid,)).fetchone()
    decisions = json.loads(r["payload"])["decisions"] if r else []
    arb = None
    ra = con.execute("select payload from events where project_id=? and "
                     "type='RENDER_ARBITRATION' order by ts desc limit 1", (pid,)).fetchone()
    if ra:
        arb = json.loads(ra["payload"])
    con.close()
    (SANDBOX / "material_timeline.json").write_text(json.dumps(
        {"schema": "p32-material-timeline-v1", "project_id": pid, "decisions": decisions},
        ensure_ascii=False, indent=1), encoding="utf-8")
    log("material_timeline -> {} 条 | 仲裁事件 {}".format(
        len(decisions), "有" if arb else "无"))
    if arb:
        log("  仲裁 called={} arbitrated={} still_failed={} cost={}".format(
            arb.get("called"), len(arb.get("arbitrated") or []),
            len(arb.get("still_failed") or []), arb.get("cost_usd")))

    # ---- H7 片尾卡（在渲染产物上原地施加；只在渲染成功且门已过时才有意义）----
    outro = None
    if outs and (tt or {}).get("status") == "SUCCEEDED":
        src_film = outs[-1]
        cand = pdir / "output" / (src_film.stem + "_with_outro.mp4")
        try:
            outro = apply_outro_card(src_film, cand)
            log("H7 片尾卡 DONE: {} | 时长 {} -> {}".format(
                cand.name, outro["duration_before_s"], outro["duration_after_s"]))
        except Exception as exc:                                                # noqa: BLE001
            log("H7 片尾卡失败: {}: {}".format(type(exc).__name__, exc))
    else:
        log("渲染未成功 ⇒ 不施加 H7 片尾卡（避免无意义产物）")

    (SANDBOX / "fixture.json").write_text(json.dumps({
        "schema": "phase32-fixture-v1", "sandbox_project_id": pid,
        "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
        "script_sha256": sha(SCRIPT), "audio_sha256": sha(AUDIO),
        "n_pool": len(cands), "vlm_available": bool(_ok),
        "bank_chain": _bcfg.get("bank_derived"), "arbitration": arb, "outro": outro,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
