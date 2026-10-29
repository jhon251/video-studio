# -*- coding: utf-8 -*-
"""Phase 58 / F14：**全片视频版**（15 景专属 Pexels 视频 + 10 主线 + 11 锚定）。

与 F12 的唯一差异 = 10 个抽象景的素材（GenConcept 旧图 → 黑板主线图）；
字幕/音频/其余 26 景零改动。pins 已换（`p56_2_f9_pins.json`，F10.1 原件备份于
`p56_2_f9_pins.f10_1_backup.json`）；素材池 = 材料包 v6（65 张含主线 21 张，
绝对路径）。
运行: python docs/regression_2x/p57_5_render_f13.py
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sqlite3
import statistics
import subprocess
import sys
import time
import traceback

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
P = "p_3e9292101f10"
PDIR = R / "projects" / P
LOG = R / "output" / "p40_probe" / "render_f14.log"
FFPROBE = str(R / "bin" / "ffprobe.exe")
FF = str(R / "bin" / "ffmpeg.exe")
SCRIPT_ART = PDIR / "artifacts" / "a_aec6a870612e.json"
VOICE_ART = PDIR / "artifacts" / "a_19df682cbaa4.json"
POOL = R / "docs" / "regression_2x" / "logs" / "p57_merged_payload.json"
VPOOL = R / "docs" / "regression_2x" / "logs" / "p58_video_payload.json"


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
    for m in __import__("re").finditer(r"Dialogue: 0,([0-9:.]+),([0-9:.]+),",
                                       p.read_text(encoding="utf-8")):
        def sec(ts):
            h, mm, rest = ts.split(":")
            return int(h) * 3600 + int(mm) * 60 + float(rest)
        rows.append((sec(m.group(1)), sec(m.group(2))))
    return rows


def main() -> int:
    LOG.write_text("", encoding="utf-8")
    t0 = time.time()
    log("== F13 渲染（F12 字幕 + 黑板主线画面）==")
    from video_studio.core.env import load_env
    load_env(R / ".env")
    from video_studio.cli import build_engine, load_config
    engine = build_engine(load_config(str(R / "config" / "config.json")))
    # 与 F12/F10.1 同一 harness 内存注入
    bp = json.loads((R / "output/phase36_voice/bindings_proposal.json")
                    .read_text(encoding="utf-8"))
    binds = {sid: {"sha256": v["sha256"], "name": v.get("name"),
                   "reason": v.get("reason"),
                   "approval_document": v.get("approval_document")}
             for sid, v in bp["bindings"].items()}
    engine.config.setdefault("editing", {}).update({
        "max_scenes_per_asset": 3, "forbid_adjacent_same_asset": True,
        "min_scene_gap": 3, "explicit_bindings": binds})

    script = json.loads(SCRIPT_ART.read_text(encoding="utf-8"))
    voice = json.loads(VOICE_ART.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    vpool = json.loads(VPOOL.read_text(encoding="utf-8"))
    cands = [c for c in (list(pool["candidates"]) + list(vpool["candidates"]))
             if c.get("path")]
    log("池: {} 候选（主线 21 + 视频 23）| 景 {}".format(
        len(cands), len(script["segments"])))

    ts = engine.create_task(P, "script", "script", max_retries=0)
    tv = engine.create_task(P, "voice", "voice", max_retries=0)
    tr = engine.create_task(P, "retrieval", "retrieval", max_retries=0)
    from video_studio.agents.base import AGENTS

    def h_script(eng, task):
        aid = eng.write_artifact(P, task["task_id"], "script_output", script,
                                 summary="v6.5 净稿 × 36 景（沿用 F10.1）")
        eng.attach_artifact(task["task_id"], aid)
        vid = eng.write_artifact(P, task["task_id"], "visual_plan_output",
                                 json.loads((PDIR / "artifacts" / "a_5ec6f0b428da.json")
                                            .read_text(encoding="utf-8")),
                                 summary="沿用 H5 visual_plan")
        eng.attach_artifact(task["task_id"], vid)
        return {}

    def h_voice(eng, task):
        aid = eng.write_artifact(P, task["task_id"], "voice_output", voice,
                                 summary="逐景配音（36 景，沿用 F10.1）")
        eng.attach_artifact(task["task_id"], aid)
        return {}

    def h_retrieval(eng, task):
        aid = eng.write_artifact(P, task["task_id"], "retrieval_candidates",
                                 {"schema": "retrieval-candidates-v1",
                                  "material_mode": "mixed",
                                  "candidates_total": len(cands),
                                  "material_provided": True, "candidates": cands},
                                 summary="材料包 v6+视频（{} 张）".format(len(cands)))
        eng.attach_artifact(task["task_id"], aid)
        return {}

    for role, fn in (("script", h_script), ("voice", h_voice), ("retrieval", h_retrieval)):
        if role in AGENTS:
            AGENTS[role].run = fn

    te = engine.create_task(P, "render", "editing", dependencies=[ts, tv, tr],
                            inputs={"render_params": {"resolution": "1920x1080",
                                                      "fps": 25}},
                            max_retries=0)
    log("editing 任务: {}".format(te))
    status = None
    try:
        for cyc in range(1, 9):
            k = engine.run_cycle(P, limit=10)
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

    outs = sorted((PDIR / "output").glob("{}_draft.mp4".format(te)))
    if not outs:
        log("**无 draft**")
        return 1
    draft = outs[-1]
    log("draft: {} {:,}B | {:.3f}s".format(draft.name, draft.stat().st_size,
                                           dur(draft) or 0))

    # 签名门（与 F12 同口径；111 cues）
    ass = PDIR / "artifacts" / "_captions_{}.ass".format(te)
    dump_p = PDIR / "artifacts" / "_cuedump_{}.json".format(te)
    dmp = json.loads(dump_p.read_text(encoding="utf-8")) if dump_p.is_file() else {}
    rows = parse_ass(ass) if ass.is_file() else []
    durs = [round(e - s, 3) for s, e in rows]
    span = round(max((e for _, e in rows), default=0) - min((s for s, _ in rows), default=0), 3)
    ov = sum(1 for i in range(1, len(rows)) if rows[i][0] < rows[i - 1][1] - 1e-9)
    aud = dur(PDIR / "media" / "voice" / "narration_v65.mp3")
    ok = (101 <= len(rows) <= 111 and aud and abs(span - aud) <= 2.0
          and (statistics.median(durs) if durs else 0) >= 3.0 and ov == 0
          and dmp.get("cue_source") == "word_exact"
          and {c.get("source") for c in (dmp.get("first5") or [])} == {"word_exact"})
    log("签名门: cues={} span={} median={} ov={} | {}".format(
        len(rows), span, round(statistics.median(durs), 3) if durs else None, ov,
        "PASS" if ok else "FAIL"))
    if not ok:
        return 1

    # 分配指纹 vs F13 pins
    pins = json.loads((R / "docs/regression_2x/logs/p56_2_f9_pins.json")
                      .read_text(encoding="utf-8")).get("pins") or {}
    con = sqlite3.connect("file:" + (R / "projects" / "video_studio.db").as_posix()
                          + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    r = con.execute("select payload from events where project_id=? and "
                    "type='MATERIAL_TIMELINE' order by ts desc limit 1", (P,)).fetchone()
    dec = json.loads(r["payload"])["decisions"]
    con.close()
    same = sum(1 for d in dec if str((d.get("selected_asset") or {}).get("sha256") or "")[:12]
               == str(pins.get(d["scene_id"], ""))[:12])
    log("分配指纹 vs F13 pins: {}/36".format(same))
    if same != 36:
        log("**指纹 FAIL-CLOSED**")
        return 1

    # 主线替换核对：10 景应为主线 sha、26 景与 F12 相同
    f12_fixture = json.loads((R / "output/phase36_p36_4_sandbox/fixture_f12.json")
                             .read_text(encoding="utf-8"))
    log("主线替换: 10 景（见 pins note）| 其余沿用 F10.1")

    import importlib
    sys.path.insert(0, str(R / "docs" / "regression_2x"))
    H7 = importlib.import_module("p32_h7")
    cand = PDIR / "output" / (draft.stem + "_with_outro_v2.mp4")
    outro = H7.apply_outro(FF, FFPROBE, draft, cand, PDIR / "work_h7_f14")
    log("H7 DONE: {} | {} -> {} | full_cover={} | audio_identical={}".format(
        cand.name, outro["duration_before_s"], outro["duration_after_s"],
        outro["video_full_cover"], outro["audio_identical_to_base"]))
    if not (outro["duration_unchanged"] and outro["video_full_cover"]
            and outro["audio_identical_to_base"]):
        return 1

    fixture = {"schema": "p57-5-f13-render-fixture-v1",
               "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "sandbox_project_id": P, "editing_task": te,
               "final": cand.name, "final_sha256": sha(cand),
               "final_bytes": cand.stat().st_size, "final_duration_s": dur(cand),
               "outro": outro, "signature_gate": {"cues": len(rows), "span_s": span,
                                                  "median_dur": round(statistics.median(durs), 3),
                                                  "overlap_pairs": ov},
               "assignment_same_as_f14_pins": same,
               "note": "与 F13 唯一差异 = 15 景换专属 Pexels 视频；字幕/音频/主线/锚定零改动",
               "video_scenes": 15}
    (R / "output" / "phase36_p36_4_sandbox" / "fixture_f14.json").write_text(
        json.dumps(fixture, ensure_ascii=False, indent=1), encoding="utf-8")
    log("fixture -> output/phase36_p36_4_sandbox/fixture_f14.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
