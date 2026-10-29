# -*- coding: utf-8 -*-
"""Phase 58 / P58-8：**F15 渲染**（Yunxi 旁白 + F14 视频画面 + BGM）。

· **新沙箱工程**（不触碰 p_3e9292101f10——F10.1/F12/F13/F14 的证据在档）；
· media 树从 F14 工程复制（图池 44 + 视频 23 + BGM 底床），`media/voice/*` 换
  Yunxi 产物（P58-7：36 景文本 sha 守恒 ⇒ pins/字幕句结构不变）；
· 渲染前置门（fail-closed）：切片连续（Σ切片==段音频）/ manifest 9 段 1964 词 /
  逐景文本 sha == v6.5 / pins 36 景；
· 渲染后门：签名门（101–111 cues / 跨度 ≈ 音频 / median ≥3 / 排他 / word_exact）
  + 分配指纹 36/36 + H7 outro。
运行: python docs/regression_2x/p58_8_render_f15.py
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

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
SRC_P = "p_3e9292101f10"
SRC_DIR = R / "projects" / SRC_P
VY = R / "output" / "p58_voice_yunxi"
LOG = R / "output" / "p40_probe" / "render_f15.log"
FFPROBE = str(R / "bin" / "ffprobe.exe")
FF = str(R / "bin" / "ffmpeg.exe")
POOL = R / "docs" / "regression_2x" / "logs" / "p57_merged_payload.json"
VPOOL = R / "docs" / "regression_2x" / "logs" / "p58_video_payload.json"
VISUAL = R / "projects" / "p_96efdc03e1aa" / "artifacts" / "a_a6279580600a.json"


def log(m):
    print(m, flush=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(str(m) + "\n")


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


def dur(p):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(p)],
                       capture_output=True, text=True)
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def parse_ass(p: pathlib.Path):
    rows = []
    for m in re.finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),", p.read_text(encoding="utf-8")):
        def sec(ts):
            h, mm, rest = ts.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(rest)
        rows.append((sec(m.group(1)), sec(m.group(2))))
    return rows


def precondition(sandbox: pathlib.Path) -> list:
    v = []
    sc = json.loads((VY / "script_yunxi_36seg.json").read_text(encoding="utf-8"))
    old_sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                        .read_text(encoding="utf-8"))
    old_sha = {s["scene_id"]: s["narration_sha256"] for s in old_sc["segments"]}
    by_para = {}
    for s in sc["segments"]:
        by_para.setdefault(str(s["scene_id"]).split("_")[0], []).append(s)
    for para, lst in sorted(by_para.items()):
        tot = 0.0
        for s in lst:
            f = VY / "seg" / "{}.wav".format(s["scene_id"])
            d = dur(f) if f.is_file() else None
            if d is None:
                v.append("缺切片:{}".format(s["scene_id"]))
                continue
            tot += d
        pa = VY / "para" / "{}.mp3".format(para)
        pd = dur(pa) if pa.is_file() else None
        if pd is None:
            v.append("缺段音频:{}".format(para))
        elif abs(tot - pd) > 0.35:
            v.append("切片不连续:{} Σ{:.3f} vs {:.3f}".format(para, tot, pd))
    for s in sc["segments"]:
        if s["narration_sha256"] != old_sha.get(s["scene_id"]):
            v.append("文本 sha 变动:{}".format(s["scene_id"]))
    wm = json.loads((VY / "words_manifest.json").read_text(encoding="utf-8"))
    nw = sum(len(p.get("words") or []) for p in (wm.get("paras") or []))
    if len(wm.get("paras") or []) != 9 or nw != 1964:
        v.append("manifest 异常: {} 段 / {} 词".format(len(wm.get("paras") or []), nw))
    pins = json.loads((R / "docs/regression_2x/logs/p56_2_f9_pins.json")
                      .read_text(encoding="utf-8")).get("pins") or {}
    if len(pins) != 36:
        v.append("pins 异常: {} 景".format(len(pins)))
    return v


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    t0 = time.time()
    log("== P58-8 F15 渲染（Yunxi 旁白 + F14 画面 + BGM）==")
    viol = precondition(SRC_DIR)
    if viol:
        log("**前置门 FAIL-CLOSED**：")
        for x in viol:
            log("  " + x)
        return 1
    log("前置门 PASS：切片连续 / manifest 9 段 1964 词 / 文本 sha 守恒 / pins 36 景")

    from video_studio.core.env import load_env
    load_env(R / ".env")
    from video_studio.cli import build_engine, load_config
    engine = build_engine(load_config(str(R / "config" / "config.json")))
    bp = json.loads((R / "output/phase36_voice/bindings_proposal.json")
                    .read_text(encoding="utf-8"))
    binds = {sid: {"sha256": v["sha256"], "name": v.get("name"),
                   "reason": v.get("reason"),
                   "approval_document": v.get("approval_document")}
             for sid, v in bp["bindings"].items()}
    engine.config.setdefault("editing", {}).update({
        "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True,
        "min_scene_gap": 3, "explicit_bindings": binds})
    engine.config.setdefault("tools", {})["bgm"] = {
        "enabled": True,
        "source": "media/bgm/satie_gymnopedie_no1_cc0_bed710s.mp3",
        "provider": "wikimedia_commons", "source_id": "Gymnopedie_No._1.ogg",
        "license": "CC0 1.0 (public domain dedication; composition PD)",
        "attribution": ("Erik Satie, Gymnopédie No. 1 — piano recording, "
                        "CC0 1.0, Wikimedia Commons"),
        "sha256": "7250daa34c1d53a11367e966698e5babd0409b0ab9b8777fae32a95b17d3c5ba"}
    log("注入: cap=3/forbid_adjacent/gap=3/bindings=3 | BGM 床 -20/duck -26 dB")

    # ---- 新沙箱工程 ----
    pid = engine.create_project("Phase 58 F15（Yunxi 旁白 + F14 画面 + BGM）",
                                name="phase58-f15-yunxi")
    pdir = engine.project_dir(pid)
    log("新沙箱: {}".format(pid))
    # 图池候选是**绝对路径**（母库 p_96efdc03e1aa/registered_materials）⇒ 无需复制；
    # 相对路径的只有 p58_videos（视频候选）与 bgm（BGM 底床）。
    shutil.copytree(SRC_DIR / "media" / "p58_videos",
                    pdir / "media" / "p58_videos")
    shutil.copytree(SRC_DIR / "media" / "bgm", pdir / "media" / "bgm")
    (pdir / "media" / "voice" / "seg").mkdir(parents=True)
    shutil.copy2(VY / "narration_yunxi.mp3", pdir / "media" / "voice" / "narration_yunxi.mp3")
    n = 0
    for f in sorted((VY / "seg").glob("*.wav")):
        shutil.copy2(f, pdir / "media" / "voice" / "seg" / f.name)
        n += 1
    shutil.copy2(VY / "words_manifest.json", pdir / "media" / "voice" / "words_manifest.json")
    shutil.copy2(VY / "runs_by_scene.json", pdir / "media" / "voice" / "runs_by_scene.json")
    shutil.copy2(VY / "recoveries.json", pdir / "media" / "voice" / "recoveries.json")
    log("媒体就位: 图池 + 视频 + BGM 复制 | voice = Yunxi（narration + {} 切片 + manifest）".format(n))

    script = json.loads((VY / "script_yunxi_36seg.json").read_text(encoding="utf-8"))
    voice = json.loads((VY / "voice_output_yunxi.json").read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    vpool = json.loads(VPOOL.read_text(encoding="utf-8"))
    cands = [c for c in (list(pool["candidates"]) + list(vpool["candidates"]))
             if c.get("path")]

    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="v6.5 文本 × 36 景（Yunxi 窗口）")
        eng.attach_artifact(task["task_id"], aid)
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output",
                                 json.loads(VISUAL.read_text(encoding="utf-8")),
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        return {}

    def h_voice(eng, task):
        v = dict(voice)
        v["audio"] = "media/voice/narration_yunxi.mp3"
        for s in v["segments"]:
            s["audio"] = "media/voice/" + s["seg_audio"]
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", v,
                                 summary="Yunxi 逐景配音（36 景）")
        eng.attach_artifact(task["task_id"], aid)
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates",
                                 {"schema": "retrieval-candidates-v1",
                                  "material_mode": "mixed",
                                  "candidates_total": len(cands),
                                  "material_provided": True, "candidates": cands},
                                 summary="池 {} 张（v6 + 视频）".format(len(cands)))
        eng.attach_artifact(task["task_id"], aid)
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn

    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080",
                                                      "fps": 25}},
                            max_retries=0)
    log("editing 任务: {}".format(te))
    status = None
    try:
        for cyc in range(1, 9):
            k = engine.run_cycle(pid, limit=10)
            log("cycle {}: 派发 {} | {:.1f}s".format(cyc, k, time.time() - t0))
            tt = engine.db.get_task(te) or {}
            if (tt or {}).get("status") in ("SUCCEEDED", "FAILED", "BLOCKED"):
                status = tt.get("status")
                log("status={} error={}".format(status, str(tt.get("error"))[:300]))
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
    aud = dur(pdir / "media" / "voice" / "narration_yunxi.mp3")
    gate = {"cues": len(rows), "span_s": span, "audio_s": aud,
            "median_dur": round(statistics.median(durs), 3) if durs else None,
            "overlap_pairs": ov,
            "dump_cue_source": dmp.get("cue_source"),
            "dump_first_sources": [c.get("source") for c in (dmp.get("first5") or [])],
            "dump_cue_gate": dmp.get("cue_gate")}
    ok = (101 <= len(rows) <= 111 and aud and abs(span - aud) <= 2.0
          and (gate["median_dur"] or 0) >= 3.0 and ov == 0
          and gate["dump_cue_source"] == "word_exact"
          and set(gate["dump_first_sources"]) == {"word_exact"})
    log("签名门: {}".format(json.dumps(gate, ensure_ascii=False)))
    if not ok:
        log("**签名门 FAIL-CLOSED**")
        return 1

    # ---- 分配指纹（pins 不变）----
    pins = json.loads((R / "docs/regression_2x/logs/p56_2_f9_pins.json")
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
    log("分配指纹: {}/36".format(same))
    if same != 36:
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

    fixture = {"schema": "p58-8-f15-render-fixture-v1",
               "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "sandbox_project_id": pid, "editing_task": te,
               "final": cand.name, "final_sha256": sha(cand),
               "final_bytes": cand.stat().st_size,
               "final_duration_s": dur(cand), "outro": outro,
               "signature_gate": gate, "assignment_same_as_pins": same,
               "voice": "zh-CN-YunxiNeural (edge-tts)",
               "timebase_s": json.loads((VY / "timebase_yunxi.json")
                                        .read_text(encoding="utf-8"))["audio_time_base_s"],
               "bgm": {"track": "Gymnopédie No.1 (CC0)", "bed_db": -20,
                       "duck_db": -26},
               "note": "与 F14.1 唯一差异 = 旁白音色（晓晓→云希）；画面/素材/BGM 零改动"}
    (R / "output" / "phase36_p36_4_sandbox" / "fixture_f15.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> output/phase36_p36_4_sandbox/fixture_f15.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
