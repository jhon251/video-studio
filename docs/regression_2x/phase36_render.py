# -*- coding: utf-8 -*-
"""Phase 36 / P36-4 终渲染：v6.5 净稿（36 景，段落级 TTS + 静音吸附切景）+ 全门。

· 脚本：`output/phase36_script_sandbox/script_p36_v65_36seg.json`（36 景）
· 音频：`output/phase36_voice/narration_v65.mp3`（由 36 个景切片拼成）
· **具名绑定（P34-1 机制）**：仍启用，确保 no_picture 门通过
· 分配纪律：cap=3 + forbid_adjacent + **min_scene_gap=3**（P35-3）
· 运动：`render_motion.json` = false（P34-2 裁定）
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
SANDBOX = R / "output" / "phase36_p36_4_sandbox"
LOGS = R / "docs" / "regression_2x" / "logs"
VOICE = R / "output" / "phase36_voice"
SCRIPT = R / "output/phase36_script_sandbox/script_p36_v65_36seg.json"
VOICEJ = VOICE / "voice_output_v65.json"
AUDIO = VOICE / "narration_v65.mp3"
SEGD = VOICE / "seg"
SRC = R / "projects" / "p_96efdc03e1aa"
VISUAL = SRC / "artifacts" / "a_a6279580600a.json"
POOL_PAYLOAD = LOGS / "p45_4_merged_payload.json"   # P45-4：扩池后合并池（29 张）
FFPROBE = R / "bin" / "ffprobe.exe"
FF = str(R / "bin" / "ffmpeg.exe")

BIND_SPEC = {
    "S03p1": ("1d2fe4b325bd", "机器验证数学 vs 知识论（形式化意象）"),
    "S05p1": ("a3aff2f300eb", "「没有人读完」：人手书写证明"),
    "S05p2": ("f0cd2a28016d", "历史文献页（年代/审稿意象）"),
    "S13p1": ("1e9d2ab4e64e", "Lean 交互界面（人→机翻译意象）"),
    "S16p1": ("301ff850be9c", "数学分支总图（知识结构意象）"),
    "S17p1": ("23e71bc8a864", "证明链（逐条检视意象）"),
    "S17p2": ("acaa16094c3b", "图论示例图（结构/重排意象）"),
    "S21p1": ("65377b888b77", "罗素《数学原理》1+1=2（证据/严谨意象）"),
}


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
    v = (r.stdout or "").strip().splitlines()
    return round(float(v[0]), 3) if v and v[0] else None


def assemble_narration() -> pathlib.Path:
    """把 36 个景切片按序拼成整条旁白（WAV 拼接 → 单次 MP3 编码，避免逐段填充累积）。"""
    tb = json.loads((VOICE / "timebase_v65.json").read_text(encoding="utf-8"))
    work = VOICE / "_assemble"
    work.mkdir(parents=True, exist_ok=True)
    parts = [work / "p{:03d}.wav".format(w["index"]) for w in tb["windows"]]
    for w, part in zip(tb["windows"], parts):
        if not part.is_file():
            subprocess.run([FF, "-y", "-v", "error", "-i", str(VOICE / w["audio"]),
                            "-ar", "24000", "-ac", "1", "-c:a", "pcm_s16le",
                            str(part)], check=True)
    lst = work / "concat.txt"
    lst.write_text("".join("file '{}'\n".format(p.as_posix()) for p in parts),
                   encoding="utf-8")
    joined = work / "narration_joined.wav"
    subprocess.run([FF, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i",
                    str(lst), "-c", "copy", str(joined)], check=True)
    subprocess.run([FF, "-y", "-v", "error", "-i", str(joined), "-c:a", "libmp3lame",
                    "-b:a", "48k", "-ar", "24000", "-ac", "1", str(AUDIO)], check=True)
    return joined


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    joined = assemble_narration()
    log("旁白拼装: {} | wav {:.3f}s | mp3 {:.3f}s".format(
        AUDIO.name, dur(joined) or 0, dur(AUDIO) or 0))

    from video_studio.core.env import load_env
    loaded = load_env(R / ".env")
    log("load_env -> {}".format(sorted(loaded.keys())))
    from video_studio.cli import build_engine, load_config
    from video_studio.tools import vlm_judge as _vj
    from video_studio.core import corr_diagnostics as _CD
    from video_studio.core import motion as _MO
    _cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
    _vcfg, _ = _vj.resolve_config(_cfg, root=R)
    _ok, _ = _vj.available(_vcfg)
    _bcfg, _ = _CD.resolve_config(_cfg, root=R)
    _mcfg, _msrc = _MO.resolve_config(_cfg, root=R)
    log("VLM available={} | bank={} | **motion enabled={}**".format(
        _ok, _bcfg.get("bank_derived"), _mcfg.get("enabled")))

    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    voice_obj = json.loads(VOICEJ.read_text(encoding="utf-8"))
    tb = json.loads((VOICE / "timebase_v65.json").read_text(encoding="utf-8"))
    pool = json.loads(POOL_PAYLOAD.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    log("景 {} | 池候选 {} 张 | 新时基 {:.3f}".format(
        len(script["segments"]), len(cands), tb["audio_time_base_s"]))

    # ---- 具名绑定：逐景（P36 重映射；预检见 bindings_proposal.json）----
    bp = json.loads((VOICE / "bindings_proposal.json").read_text(encoding="utf-8"))
    binds = {sid: {"sha256": v["sha256"], "name": v.get("name"),
                   "reason": v.get("reason"),
                   "approval_document": v.get("approval_document")}
             for sid, v in bp["bindings"].items()}
    log("具名绑定 {} 景（预检 每素材≤3 OK / 间距≥3 OK）：{}".format(
        len(binds), sorted(binds)[:4]))

    engine = build_engine(load_config(str(R / "config" / "config.json")))
    engine.config.setdefault("editing", {}).update({
        "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True,
        "min_scene_gap": 3, "explicit_bindings": binds})
    log("内存注入: cap=3 / forbid_adjacent=True / **min_scene_gap=3** / bindings={}".format(
        len(binds)))

    pid = engine.create_project("Phase 36 P36-4 交付级候选（v6.5 单线重构）",
                                name="phase36-p36-4-delivery-candidate")
    log("沙箱项目: " + pid)
    pdir = engine.project_dir(pid)
    t = pdir / "media" / "voice" / AUDIO.name
    t.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(AUDIO, t)
    n = 0
    for f in sorted(SEGD.glob("*.wav")):
        d = pdir / "media" / "voice" / "seg" / f.name
        d.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(f, d)
        n += 1
    log("音频就位: {} + {} 切片".format(AUDIO.name, n))
    # ---- P45-3：**词级 cue**（TTS WordBoundary ⇒ 构造保证滞后 0）优先于静音吸附 ----
    _rn = R / "output" / "phase52_voice" / "runs_by_scene.json"
    if _rn.is_file():
        shutil.copy2(_rn, pdir / "media" / "voice" / "runs_by_scene.json")
        _rj2 = json.loads(_rn.read_text(encoding="utf-8"))
        log("音频锚定 cue（P52-1）: runs_by_scene.json（{} 景 / {} 运行）".format(
            _rj2.get("scene_count"),
            sum(len(v) for v in (_rj2.get("runs_by_scene") or {}).values())))
    _wm = R / "output" / "phase45_voice" / "words_manifest.json"
    if _wm.is_file():
        shutil.copy2(_wm, pdir / "media" / "voice" / "words_manifest.json")
        log("词级 cue（P45-3）: words_manifest.json（{} 段）".format(
            len(json.loads(_wm.read_text(encoding="utf-8")).get("paras") or [])))
    else:
        log("词级 cue: **未找到 words_manifest.json** ⇒ 回落静音吸附")
    # ---- P43-1：把**语音恢复点**放进项目媒体目录（供字幕句界吸附）----
    _rec = VOICE / "recoveries_fullfilm.json"
    if _rec.is_file():
        shutil.copy2(_rec, pdir / "media" / "voice" / "recoveries.json")
        _rj = json.loads(_rec.read_text(encoding="utf-8"))
        log("字幕句界吸附(全片口径): recoveries_fullfilm.json（{} 个恢复点）".format(
            _rj.get("absolute_count")))
    else:
        log("字幕句界吸附: **未找到 recoveries.json** ⇒ 走原均匀铺排")

    ts = engine.create_task(pid, "script", "script", max_retries=0)
    tv = engine.create_task(pid, "voice", "voice", max_retries=0)
    tr = engine.create_task(pid, "retrieval", "retrieval", max_retries=0)
    te = engine.create_task(pid, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080", "fps": 25}},
                            max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "script_output", script,
                                 summary="v6.5 净稿 × 36 景（静音吸附切景）")
        eng.attach_artifact(task["task_id"], aid)
        vid = eng.write_artifact(pid, task["task_id"], "visual_plan_output",
                                 json.loads(VISUAL.read_text(encoding="utf-8")),
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        log("  [script] {}".format(aid))
        return {}

    def h_voice(eng, task):
        # **必须逐景（36 段）**：渲染前闸门按**脚本段数**核对 voice 产物
        # （实测踩坑：只给 9 段段级产物 ⇒ fail-closed「voice 产物不完整」）。
        tb_ = json.loads((VOICE / "timebase_v65.json").read_text(encoding="utf-8"))
        seg_by_id = {x["scene_id"]: x for x in tb_["windows"]}
        v = dict(voice_obj)
        v["audio"] = "media/voice/" + AUDIO.name
        v["segments"] = [{
            "scene_id": s["scene_id"], "index": s["index"],
            "parent_scene_id": s.get("parent_scene_id"),
            "text": s["narration"], "text_sha256": s["narration_sha256"],
            "audio": "media/voice/" + seg_by_id[s["scene_id"]]["audio"].replace(
                "seg/", "seg/"),
            "duration_s": s["duration_s"], "status": "SUCCESS",
            "voice": voice_obj.get("voice"), "provider": "edge-tts",
        } for s in script["segments"]]
        v["segments_total"] = len(v["segments"])
        v["all_segments_ok"] = True
        v["narration_duration_s"] = tb_["sum_measured_speech_s"]
        v["pause_attribution"] = {
            "policy": "v2.1",
            "source": ("段落级合成 + 静音吸附切景 ⇒ 景间不加额外静音（pause=0）"),
            "default_pause_s": 0.0, "derived_boundary_pause_s": 0.0,
            "boundaries": [{"after_index": i, "pause_s": 0.0, "kind": "derived"}
                           for i in range(len(v["segments"]) - 1)]}
        aid = eng.write_artifact(pid, task["task_id"], "voice_output", v,
                                 summary="逐景配音（{} 景）".format(len(v["segments"])))
        eng.attach_artifact(task["task_id"], aid)
        log("  [voice] {} ({} 段)".format(aid, len(v["segments"])))
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(pid, task["task_id"], "retrieval_candidates",
                                 {"schema": "retrieval-candidates-v1",
                                  "material_mode": "mixed",
                                  "candidates_total": len(cands),
                                  "material_provided": True, "candidates": cands},
                                 summary="池 {} 张".format(len(cands)))
        eng.attach_artifact(task["task_id"], aid)
        log("  [retrieval] {}".format(aid))
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn
    t0 = time.time()
    try:
        for cyc in range(1, 9):
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

    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (pid,)).fetchone()
    dec = json.loads(r["payload"])["decisions"] if r else []
    ra = con.execute("select payload from events where project_id=? and "
                     "type='RENDER_ARBITRATION' order by ts desc limit 1", (pid,)).fetchone()
    arb = json.loads(ra["payload"]) if ra else None
    mt = json.loads(r["payload"]) if r else {}
    con.close()
    (SANDBOX / "material_timeline.json").write_text(json.dumps(
        {"schema": "p36-material-timeline-v1", "project_id": pid, "decisions": dec},
        ensure_ascii=False, indent=1), encoding="utf-8")
    cards = [d["scene_id"] for d in dec if not (d.get("selected_asset") or {}).get("asset_id")]
    log("material_timeline -> {} 条 | **残留卡景 {}** | 分配: {}".format(
        len(dec), cards, json.dumps(
            {k: (len(v) if isinstance(v, list) else v)
             for k, v in (mt.get("material_allocation") or {}).items()
             if k in ("cap", "min_scene_gap", "forbid_adjacent", "enabled")},
            ensure_ascii=False)))
    if arb:
        log("  仲裁 arbitrated={} still_failed={} cost={}".format(
            len(arb.get("arbitrated") or []), len(arb.get("still_failed") or []),
            arb.get("cost_usd")))

    outro = None
    if outs and (tt or {}).get("status") == "SUCCEEDED":
        import importlib
        H7 = importlib.import_module("p32_h7")
        base = outs[-1]
        cand = pdir / "output" / (base.stem + "_with_outro_v2.mp4")
        try:
            outro = H7.apply_outro(FF, str(FFPROBE), base, cand, SANDBOX / "work_h7")
            log("H7 DONE: {} | {} -> {} | full_cover={}".format(
                cand.name, outro["duration_before_s"], outro["duration_after_s"],
                outro["video_full_cover"]))
        except Exception as exc:                                                # noqa: BLE001
            log("H7 失败: {}: {}".format(type(exc).__name__, exc))

    (SANDBOX / "fixture.json").write_text(json.dumps({
        "schema": "phase36-fixture-v1", "sandbox_project_id": pid,
        "tasks": {"script": ts, "voice": tv, "retrieval": tr, "editing": te},
        "script_sha256": sha(SCRIPT), "audio_sha256": sha(AUDIO),
        "n_pool": len(cands), "vlm_available": bool(_ok),
        "bank_chain": _bcfg.get("bank_derived"),
        "motion_enabled": bool(_mcfg.get("enabled")),
        "scene_count": len(script["segments"]),
        "timebase_s": tb["audio_time_base_s"],
        "mid_sentence_cuts": tb["mid_sentence_cuts"],
        "explicit_bindings": {k: v["sha256"][:12] for k, v in binds.items()},
        "card_scenes_remaining": cards,
        "arbitration": arb, "outro": outro,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> " + str((SANDBOX / "fixture.json").relative_to(R)))


if __name__ == "__main__":
    main()
