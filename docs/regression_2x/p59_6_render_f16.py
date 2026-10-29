# -*- coding: utf-8 -*-
"""Phase 59 / P59-6：**F16 渲染**（第三期完整制作：v2.2 定稿 + Yunxi + 27 素材零复用 + BGM）。

· 工程 = `p_e66a1c75adf5`（第三期独立沙箱）；音频 = 定稿语音链（462.128s 时间基）；
· 素材 = 27 景零复用（20 Pexels + 5 生成 + 2 PD），经项目级 pins 钉定
  （`logs/pins_p_e66a1c75adf5.json`，P59-6 项目级机制）；
· 注入：cap=3 / forbid_adjacent / gap=3（无 EP2 具名绑定）+ BGM（CC0 床）+
  caption_gate.cue_count_range（本片包络 60–66，机制零改动）；
· 门：签名门 → 分配指纹 27/27 → H7 → fixture_f16（供烧录四门复测）。
任何硬门失败 ⇒ 立即停止。运行: python docs/regression_2x/p59_6_render_f16.py
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
PID = "p_e66a1c75adf5"
PDIR = R / "projects" / PID
VY = R / "output" / "p59_ep3" / "voice_full"
MAT = R / "output" / "p59_ep3" / "materials"
LOG = R / "output" / "p40_probe" / "render_f16.log"
FFPROBE = str(R / "bin" / "ffprobe.exe")
FF = str(R / "bin" / "ffmpeg.exe")
POOL = R / "docs" / "regression_2x" / "logs" / "p59_5_material_payload.json"
FROZEN = R / "output" / "p59_ep3" / "narration_script_ep3_v2_2_frozen.txt"


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


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    t0 = time.time()
    log("== P59-6 F16 渲染（第三期完整制作）==")

    from video_studio.core.env import load_env
    load_env(R / ".env")
    from video_studio.cli import build_engine, load_config
    engine = build_engine(load_config(str(R / "config" / "config.json")))
    engine.config.setdefault("editing", {}).update({
        "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True,
        "min_scene_gap": 3})
    engine.config.setdefault("tools", {})["bgm"] = {
        "enabled": True,
        "source": "media/bgm/satie_gymnopedie_no1_cc0_bed710s.mp3",
        "provider": "wikimedia_commons", "source_id": "Gymnopedie_No._1.ogg",
        "license": "CC0 1.0 (public domain dedication; composition PD)",
        "attribution": ("Erik Satie, Gymnopédie No. 1 — piano recording, "
                        "CC0 1.0, Wikimedia Commons"),
        "sha256": "7250daa34c1d53a11367e966698e5babd0409b0ab9b8777fae32a95b17d3c5ba"}
    engine.config.setdefault("caption_gate", {})["cue_count_range"] = (60, 66)
    log("注入: cap=3/forbid_adjacent/gap=3（无具名绑定）| BGM 床-20/duck-26 | "
        "caption_gate cue 60–66")

    # ---- 媒体就位 ----
    for tgt, srcname in (("p59_videos", "pexels_videos"), ("p59_pd", "pd_images"),
                         ("p59_gen", "gen_images"), ("bgm", "bgm")):
        src = (MAT / srcname) if srcname != "bgm" else SRC_MEDIA()
        dst = PDIR / "media" / tgt
        if not dst.exists():
            shutil.copytree(src, dst)
    (PDIR / "media" / "voice" / "seg").mkdir(parents=True, exist_ok=True)
    shutil.copy2(VY / "narration_yunxi.mp3", PDIR / "media" / "voice" / "narration_yunxi.mp3")
    n = 0
    for f in sorted((VY / "seg").glob("*.wav")):
        shutil.copy2(f, PDIR / "media" / "voice" / "seg" / f.name)
        n += 1
    for f in ("words_manifest.json", "runs_by_scene.json", "recoveries.json"):
        if (VY / f).is_file():
            shutil.copy2(VY / f, PDIR / "media" / "voice" / f)
    log("媒体就位: 27 素材三目录 + BGM | voice（{} 切片 + manifest）".format(n))

    script = json.loads((VY / "script_full.json").read_text(encoding="utf-8"))
    voice = json.loads((VY / "voice_full_payload.json").read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    cands = []
    for c in pool["candidates"]:
        c = dict(c)
        p = pathlib.Path(str(c.get("path") or ""))
        if not p.is_absolute():
            c["path"] = str(PDIR / "media" / p)
        cands.append(c)

    tv = engine.create_task(PID, "voice", "voice", max_retries=0)
    tr = engine.create_task(PID, "retrieval", "retrieval", max_retries=0)
    ts = engine.create_task(PID, "script", "script", max_retries=0)
    from video_studio.agents.base import AGENTS

    # **必须覆写真实 script agent**（首轮 F16 尝试：真实 agent 抢跑 LLM 调用失败
    # ⇒ BLOCKED ⇒ render 永候）。定稿脚本已在语音链落死，这里只做产物登记。
    def h_script(eng, task):
        aid = eng.write_artifact(PID, task["task_id"], "script_output", script,
                                 summary="v2.2 定稿 × 27 景（Yunxi 实测窗口）")
        eng.attach_artifact(task["task_id"], aid)
        plan = {"schema": "visual-plan-v1", "shots": [
            {"index": i, "description": s.get("narration", "")[:40],
             "gen_prompt": c.get("query", ""),
             "source": "material_plan"}
            for i, (s, c) in enumerate(zip(script["segments"], cands))]}
        vid = eng.write_artifact(PID, task["task_id"], "visual_plan_output", plan,
                                 summary="EP3 分镜映射（material_plan 派生）")
        eng.attach_artifact(task["task_id"], vid)
        return {}

    if "script" in AGENTS:
        AGENTS["script"].run = h_script

    def h_voice(eng, task):
        v = dict(voice)
        v["audio"] = "media/voice/narration_yunxi.mp3"
        aid = eng.write_artifact(PID, task["task_id"], "voice_output", v,
                                 summary="Yunxi 逐景配音（27 景 · v2.2 定稿）")
        eng.attach_artifact(task["task_id"], aid)
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(PID, task["task_id"], "retrieval_candidates",
                                 {"schema": "retrieval-candidates-v1",
                                  "material_mode": "mixed",
                                  "candidates_total": len(cands),
                                  "material_provided": True, "candidates": cands},
                                 summary="EP3 池 {} 项（20 视频+5 生成+2 PD）".format(len(cands)))
        eng.attach_artifact(task["task_id"], aid)
        return {}

    for role, fn in (("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn

    te = engine.create_task(PID, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080",
                                                      "fps": 25}},
                            max_retries=0)
    log("editing 任务: {}（deps: {}…）".format(te, ts))
    status = None
    try:
        for cyc in range(1, 9):
            k = engine.run_cycle(PID, limit=10)
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

    outs = sorted((PDIR / "output").glob("{}_draft.mp4".format(te)))
    if not outs:
        log("**无 draft**")
        return 1
    draft = outs[-1]
    log("draft: {} {:,}B | {:.3f}s".format(draft.name, draft.stat().st_size,
                                           dur(draft) or 0))

    # ---- 签名门 ----
    ass = PDIR / "artifacts" / "_captions_{}.ass".format(te)
    dump_p = PDIR / "artifacts" / "_cuedump_{}.json".format(te)
    dmp = json.loads(dump_p.read_text(encoding="utf-8")) if dump_p.is_file() else {}
    rows = parse_ass(ass) if ass.is_file() else []
    durs = [round(e - s, 3) for s, e in rows]
    span = round(max((e for _, e in rows), default=0) - min((s for s, _ in rows), default=0), 3)
    ov = sum(1 for i in range(1, len(rows)) if rows[i][0] < rows[i - 1][1] - 1e-9)
    aud = dur(PDIR / "media" / "voice" / "narration_yunxi.mp3")
    gate = {"cues": len(rows), "span_s": span, "audio_s": aud,
            "median_dur": round(statistics.median(durs), 3) if durs else None,
            "overlap_pairs": ov, "dump_cue_source": dmp.get("cue_source"),
            "dump_first_sources": [c.get("source") for c in (dmp.get("first5") or [])],
            "dump_cue_gate": dmp.get("cue_gate")}
    ok = (60 <= len(rows) <= 66 and aud and abs(span - aud) <= 2.0
          and (gate["median_dur"] or 0) >= 3.0 and ov == 0
          and gate["dump_cue_source"] == "word_exact"
          and set(gate["dump_first_sources"]) == {"word_exact"})
    log("签名门: {}".format(json.dumps(gate, ensure_ascii=False)))
    if not ok:
        log("**签名门 FAIL-CLOSED**")
        return 1

    # ---- 分配指纹 ----
    pins = json.loads((R / "docs/regression_2x/logs/pins_p_e66a1c75adf5.json")
                      .read_text(encoding="utf-8")).get("pins") or {}
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (PID,)).fetchone()
    dec = json.loads(r["payload"])["decisions"]
    con.close()
    same = sum(1 for d in dec if str((d.get("selected_asset") or {}).get("sha256") or "")[:12]
               == str(pins.get(d["scene_id"], ""))[:12])
    log("分配指纹: {}/27".format(same))
    if same != 27:
        log("**指纹 FAIL-CLOSED**")
        return 1

    import importlib
    sys.path.insert(0, str(R / "docs" / "regression_2x"))
    H7 = importlib.import_module("p32_h7")
    cand = PDIR / "output" / (draft.stem + "_with_outro_v2.mp4")
    outro = H7.apply_outro(FF, FFPROBE, draft, cand, PDIR / "work_h7")
    log("H7 DONE: {} | {} -> {} | full_cover={} | audio_identical={}".format(
        cand.name, outro["duration_before_s"], outro["duration_after_s"],
        outro["video_full_cover"], outro["audio_identical_to_base"]))
    if not (outro["duration_unchanged"] and outro["video_full_cover"]
            and outro["audio_identical_to_base"]):
        return 1

    fixture = {"schema": "p59-6-f16-render-fixture-v1",
               "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "sandbox_project_id": PID, "editing_task": te,
               "final": cand.name, "final_sha256": sha(cand),
               "final_bytes": cand.stat().st_size, "final_duration_s": dur(cand),
               "outro": outro, "signature_gate": gate,
               "assignment_same_as_pins": same,
               "voice": "zh-CN-YunxiNeural", "timebase_s": base_of(),
               "bgm": {"track": "Gymnopédie No.1 (CC0)", "bed_db": -20, "duck_db": -26},
               "materials": "27 独立素材零复用（20 Pexels + 5 生成 + 2 PD）",
               "note": "第三期成片；停在人工终审闸，不发布"}
    (R / "output" / "phase36_p36_4_sandbox" / "fixture_f16.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> output/phase36_p36_4_sandbox/fixture_f16.json")
    return 0


def SRC_MEDIA():
    return R / "projects" / "p_3e9292101f10" / "media" / "bgm"


def base_of():
    tb = json.loads((VY / "timebase_full.json").read_text(encoding="utf-8"))
    return tb["audio_time_base_s"]


if __name__ == "__main__":
    raise SystemExit(main())
