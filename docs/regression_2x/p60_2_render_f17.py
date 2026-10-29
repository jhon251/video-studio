# -*- coding: utf-8 -*-
"""P60：**F17 渲染**（解释动画接入真实工作流的端到端案例）。

· 临时工程：脚本 = 第二期 P01_1..P01_3（0→48.60s，同旁白同音频）；
  画面 = P60 模块生成的解释动画（按景窗切分的三段视频资产，项目级 pins 钉定）；
· 渲染后门：签名门（60-66 包络按本片句数覆写）→ 分配指纹 3/3 → H7 → placement；
· 音频与 A 组（第二期成片 0-48.60s 截取）同源。
运行: python docs/regression_2x/p60_2_render_f17.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import shutil
import sqlite3
import statistics
import subprocess
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio").resolve()
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
LOG = R / "output" / "p60_ep2" / "render_f17.log"
FF = str(R / "bin" / "ffmpeg.exe")
FFPROBE = str(R / "bin" / "ffprobe.exe")
EP2_FILM = R / "projects/p_2eac65565600/output/t_ee63a79fe9f4_draft_with_outro_v2.mp4"
EP2_PROJ = R / "projects/p_2eac65565600"
EP2_PID = "p_2eac65565600"
ANIM = R / "output/p60_ep2/B_P60_explainer_v2.mp4"
# 真实景窗 = EP2 script artifact a_b2e4a14ac1ba 的 audio_window_s（上一轮 48.6s
# 假窗口 ⇒ NARRATION_INCOMPLETE BLOCKED 的根因，本轮以真实时基修正）
CUT = 61.74
SCENES = [("P01_1", 0.0, 19.204), ("P01_2", 19.204, 39.646),
          ("P01_3", 39.646, 61.74)]
CUE_RANGE = (7, 12)


def log(m):
    print(m, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1", str(p)], capture_output=True, text=True)
    for ln in (r.stdout or "").strip().splitlines():
        if ln.startswith("duration="):
            try:
                return round(float(ln.split("=", 1)[1]), 3)
            except ValueError:
                return None
    return None


def parse_ass(p):
    rows = []
    for m in re.finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),", p.read_text(encoding="utf-8")):
        def sec(ts):
            h, mm, rest = ts.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(rest)
        rows.append((sec(m.group(1)), sec(m.group(2))))
    return rows


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    t0 = time.time()
    log("== P60 F17 渲染（解释动画接入真实工作流）==")

    from video_studio.core.env import load_env
    load_env(R / ".env")
    from video_studio.cli import build_engine, load_config
    engine = build_engine(load_config(str(R / "config" / "config.json")))
    engine.config.setdefault("editing", {}).update({
        "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True,
        "min_scene_gap": 0})                      # 3 景各自独占素材，间距约束天然满足
    engine.config.setdefault("caption_gate", {})["cue_count_range"] = tuple(CUE_RANGE)
    log("注入: cap=3/forbid_adjacent/gap=0（本片 3 景无复用，间距不适用）| "
        "caption_gate cue {}-{}".format(CUE_RANGE[0], CUE_RANGE[1]))

    pid = engine.create_project("Phase 60 F17（解释动画端到端 · 第二期 P01 段）",
                                name="phase60-f17-explain-viz")
    pdir = engine.project_dir(pid)
    log("临时工程: " + pid)

    # ---- 媒体就位 ----
    (pdir / "media" / "voice" / "seg").mkdir(parents=True, exist_ok=True)
    (pdir / "media" / "p60_anim").mkdir(parents=True, exist_ok=True)
    for i, (sid, s, e) in enumerate(SCENES):
        seg_len = round(e - s, 3)
        dst = pdir / "media" / "p60_anim" / "anim_{}.mp4".format(sid)
        subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(s), "-t",
                        "{:.3f}".format(seg_len), "-i", str(ANIM),
                        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-an", str(dst)], check=True)
    voice_src = EP2_PROJ / "media" / "voice" / "seg"
    for sid, s, e in SCENES:
        shutil.copy2(voice_src / "{}.wav".format(sid),
                     pdir / "media" / "voice" / "seg" / "{}.wav".format(sid))
    # 旁白 = 三段拼接（24k mono mp3，与第二期同构）
    parts = []
    for i, (sid, s, e) in enumerate(SCENES):
        w = pdir / "media" / "voice" / "_p{:02d}.wav".format(i)
        subprocess.run([FF, "-y", "-v", "error", "-i",
                        str(EP2_PROJ / "media/voice/seg/{}.wav".format(sid)),
                        "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le", str(w)],
                       check=True)
        parts.append(w)
    lst = pdir / "media" / "voice" / "_concat.txt"
    lst.write_text("".join("file '{}'\n".format(p.as_posix()) for p in parts),
                   encoding="utf-8")
    joined = pdir / "media" / "voice" / "_joined.wav"
    subprocess.run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i",
                    str(lst), "-c", "copy", str(joined)], check=True)
    narr = pdir / "media" / "voice" / "narration_p01.mp3"
    subprocess.run([FF, "-y", "-v", "error", "-i", str(joined), "-c:a", "libmp3lame",
                    "-b:a", "48k", "-ar", "24000", "-ac", "1", str(narr)], check=True)
    # words_manifest：只保留 P01 段内 [0, 61.74) 的词（P01_4 的词越界 ⇒ 字幕溢出音频）
    src_manifest = json.loads((EP2_PROJ / "media/voice/words_manifest.json")
                              .read_text(encoding="utf-8"))
    p01 = [p_ for p_ in src_manifest.get("paras") if p_["para"] == "P01"][0]
    p01 = dict(p01, words=[w_ for w_ in p01.get("words") or []
                           if w_["start_s"] < CUT])
    json.dump({"schema": src_manifest.get("schema"), "voice": "zh-CN-YunxiNeural",
               "paras": [p01]},
              open(pdir / "media/voice/words_manifest.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    log("媒体就位: 动画 3 段 + 语音 3 段 + P01 词级 manifest")

    # ---- 脚本 / 语音 / 检索 产物 ----
    import sqlite3 as _sq
    _con = _sq.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                       + "?mode=ro", uri=True)
    _con.row_factory = _sq.Row
    _row = _con.execute("select path from artifacts where project_id=? and "
                        "type='script_output' order by created_at desc limit 1",
                        (EP2_PID,)).fetchone()
    _con.close()
    ep2_script = json.loads(pathlib.Path(_row["path"]).read_text(encoding="utf-8"))
    segs_by_id = {s["scene_id"]: s for s in ep2_script["segments"]}
    segments = []
    for i, (sid, s, e) in enumerate(SCENES):
        src_seg = segs_by_id[sid]
        segments.append({
            "scene_id": sid, "index": i, "parent_scene_id": "P01",
            "narration": src_seg["narration"],
            "narration_sha256": src_seg.get("narration_sha256"),
            "duration_s": round(e - s, 3),
            "audio_window_s": [s, e],
            "actual_tts_duration_s": round(e - s, 3),
            "pause_budget_s": 0.0, "timing_source": "p60 f17 (reuse EP2 P01 windows)",
            "text_source": src_seg.get("text_source")})
    script = {"schema": "p60-f17-script-v1", "title": "第二期 P01 段（解释动画版）",
              "voice": "zh-CN-YunxiNeural", "segments": segments,
              "scene_count": len(segments), "zero_llm": True,
              "audio_time_base_s": CUT}
    voice = {"audio": "media/voice/narration_p01.mp3", "provider": "edge-tts",
             "voice": "zh-CN-YunxiNeural", "complete": True, "status": "COMPLETE",
             "all_segments_ok": True, "segments_total": len(segments),
             "narration_duration_s": CUT,
             "segments": [{"scene_id": sid, "index": i,
                           "audio": "media/voice/seg/{}.wav".format(sid),
                           "duration_s": round(e - s, 3), "status": "SUCCESS",
                           "text": segs_by_id[sid]["narration"]}
                          for i, (sid, s, e) in enumerate(SCENES)],
             "pause_attribution": {"policy": "v2.1",
                                   "derived_boundary_pause_s": 0.0,
                                   "boundaries": [{"after_index": i, "pause_s": 0.0,
                                                   "kind": "derived"}
                                                  for i in range(len(SCENES) - 1)]}}
    anim_assets = []
    for i, (sid, s, e) in enumerate(SCENES):
        p = pdir / "media" / "p60_anim" / "anim_{}.mp4".format(sid)
        anim_assets.append({
            "asset_id": "asset_anim_" + sid, "name": "解释动画 {}".format(sid),
            "sha256": sha(p), "path": str(p), "media_type": "video",
            "duration_s": round(e - s, 3), "width": 1920, "height": 1080,
            "bytes": p.stat().st_size, "usable": True,
            "license": "Generated (P60 explain_viz, 本频道自有)", "license_cleared": True,
            "license_class": "FREE_ATTRIBUTION", "provider": "generated",
            "source": "external", "source_id": sid, "source_url": None,
            "attribution": "P60 explain_viz 模板动画（自有）",
            "retrieval_match_score": 10, "for_scene": sid})

    # ---- 项目级 pins（P59-6 机制）：3 景 → 3 段解释动画 ----
    pins_map = {sid: a["sha256"] for (sid, s, e), a in zip(SCENES, anim_assets)}
    (R / "docs/regression_2x/logs/pins_{}.json".format(pid)).write_text(
        json.dumps({"schema": "p60-pins-v1", "source_candidate": "P60 explain_viz",
                    "scenes": len(pins_map), "pins": pins_map,
                    "note": "3 景各钉一段解释动画（零复用）"},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    tsv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tsr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    tss = engine.create_task(pid, "script", "script", max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="v2.2 P01 段 × 3 景（Yunxi 实测窗口）")
        eng.attach_artifact(task["task_id"], aid)
        plan = {"schema": "visual-plan-v1", "shots": [
            {"index": i, "description": "解释动画 " + sid, "gen_prompt": "",
             "source": "p60_explain_viz"}
            for i, (sid, s, e) in enumerate(SCENES)]}
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output", plan,
                                 summary="EP3 分镜映射")
        eng.attach_artifact(task["task_id"], vid)
        return {}

    def h_voice(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", voice,
                                 summary="Yunxi 逐景配音（3 景 · 与第二期同源音频）")
        eng.attach_artifact(task["task_id"], aid)
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates",
                                 {"schema": "retrieval-candidates-v1",
                                  "material_mode": "mixed",
                                  "candidates_total": len(anim_assets),
                                  "material_provided": True,
                                  "candidates": anim_assets},
                                 summary="EP3 动画池 {} 项".format(len(anim_assets)))
        eng.attach_artifact(task["task_id"], aid)
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn

    te = engine.create_task(pid, "render", "editing", dependencies=[tss, tsv, tsr],
                            inputs={"render_params": {"resolution": "1920x1080",
                                                      "fps": 25}},
                            max_retries=0)
    log("editing 任务: " + te)
    status = None
    try:
        for cyc in range(1, 9):
            k = engine.run_cycle(pid, limit=10)
            log("cycle {}: 派发 {} | {:.1f}s".format(cyc, k, time.time() - t0))
            tt = engine.db.get_task(te) or {}
            if (tt or {}).get("status") in ("SUCCEEDED", "FAILED", "BLOCKED"):
                status = tt.get("status")
                log("status={} error={}".format(status, str(tt.get("error"))[:400]))
                break
            if k == 0:
                break
    except Exception as exc:                                                    # noqa: BLE001
        log("异常: {}: {}".format(type(exc).__name__, exc))
        log(traceback.format_exc()[-1200:])
        status = "EXCEPTION"
    if status != "SUCCEEDED":
        return 1

    outs = sorted((pdir / "output").glob("{}_draft.mp4".format(te)))
    if not outs:
        log("**无 draft**")
        return 1
    draft = outs[-1]
    log("draft: {} {:,}B | {:.3f}s".format(draft.name, draft.stat().st_size,
                                           dur(draft) or 0))

    # ---- 签名门 ----
    ass = pdir / "artifacts" / "_captions_{}.ass".format(te)
    dump_p = pdir / "artifacts" / "_cuedump_{}.json".format(te)
    dmp = json.loads(dump_p.read_text(encoding="utf-8")) if dump_p.is_file() else {}
    rows = parse_ass(ass) if ass.is_file() else []
    durs = [round(e - s, 3) for s, e in rows]
    span = round(max((e for _, e in rows), default=0) - min((s for s, _ in rows), default=0), 3)
    ov = sum(1 for i in range(1, len(rows)) if rows[i][0] < rows[i - 1][1] - 1e-9)
    aud = dur(pdir / "media" / "voice" / "narration_p01.mp3")
    gate = {"cues": len(rows), "span_s": span, "audio_s": aud,
            "median_dur": round(statistics.median(durs), 3) if durs else None,
            "overlap_pairs": ov, "dump_cue_source": dmp.get("cue_source"),
            "dump_first_sources": [c.get("source") for c in (dmp.get("first5") or [])]}
    ok = (CUE_RANGE[0] <= len(rows) <= CUE_RANGE[1] and aud
          and abs(span - aud) <= 2.0 and (gate["median_dur"] or 0) >= 3.0 and ov == 0
          and gate["dump_cue_source"] == "word_exact"
          and set(gate["dump_first_sources"]) == {"word_exact"})
    log("签名门: {}".format(json.dumps(gate, ensure_ascii=False)))
    if not ok:
        log("**签名门 FAIL-CLOSED**")
        return 1

    # ---- 分配指纹 ----
    pins = json.loads((R / "docs/regression_2x/logs/pins_{}.json".format(pid))
                      .read_text(encoding="utf-8")).get("pins") or {}
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (pid,)).fetchone()
    dec = json.loads(r["payload"])["decisions"]
    con.close()
    same = sum(1 for d in dec if str((d.get("selected_asset") or {}).get("sha256") or "")[:12]
               == str(pins.get(d["scene_id"], ""))[:12])
    log("分配指纹: {}/3".format(same))
    if same != 3:
        log("**指纹 FAIL-CLOSED**")
        return 1

    import importlib
    sys.path.insert(0, str(R / "docs" / "regression_2x"))
    H7 = importlib.import_module("p32_h7")
    cand = pdir / "output" / (draft.stem + "_with_outro_v2.mp4")
    outro = H7.apply_outro(FF, FFPROBE, draft, cand, pdir / "work_h7")
    log("H7 DONE: {} | {} -> {} | full_cover={} | audio_identical={}".format(
        cand.name, outro["duration_before_s"], outro["duration_after_s"],
        outro["video_full_cover"], outro["audio_identical_to_base"]))
    if not (outro["duration_unchanged"] and outro["video_full_cover"]
            and outro["audio_identical_to_base"]):
        return 1

    fixture = {"schema": "p60-f17-render-fixture-v1",
               "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "sandbox_project_id": pid, "editing_task": te,
               "final": cand.name, "final_sha256": sha(cand),
               "final_duration_s": dur(cand), "outro": outro,
               "signature_gate": gate, "assignment_same_as_pins": same,
               "note": "解释动画端到端：3 景 × 解释动画素材，经真实 Agent 管线交付"}
    (R / "output" / "p60_ep2" / "fixture_f17.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> output/p60_ep2/fixture_f17.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
