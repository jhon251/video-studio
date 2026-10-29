# -*- coding: utf-8 -*-
"""Duration Contract v2 —— **真实全新测试项目 E2E**（真实 edge-tts + 真实渲染 + 真实 PI）。

严格约束：
  · **不**使用 mock TTS（真实调用 edge-tts）；
  · **不**触碰生产项目 / v9 / C1–C4 / E1/E2 候选 / baseline / tag；不 promote；
  · 使用**全新的临时工作区与新项目 id**（`p_dcv2_<ts>`），并在开始时/结束时校验历史产物 sha 未变。

链路：真实 TTS → actual duration → audio_time_base → timeline → subtitle → BGM(mix 证据) → render → PI

用法: python docs/regression_2x/phase6e_dc_v2_e2e.py
产出: docs/regression_2x/logs/phase6e_dc_v2_e2e.json
"""
import hashlib
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.editing.agent import EditingAgent              # noqa: E402
from video_studio.agents.voice.agent import VoiceAgent                  # noqa: E402
from video_studio.core import bgm as core_bgm                           # noqa: E402
from video_studio.core import captions as core_captions                 # noqa: E402
from video_studio.core import narration as N                            # noqa: E402
from video_studio.core.narration import NarrationIncompleteError        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
OUT = LOGS / "phase6e_dc_v2_e2e.json"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
TS = time.strftime("%Y%m%d_%H%M%S")
PROJECT_ID = "p_dcv2_{}".format(TS)                 # **全新项目 id**（非生产）
WORK = ROOT / "output" / "phase6e_dc_v2_e2e" / TS
PASS, FAIL, steps = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + json.dumps(detail, ensure_ascii=False,
                                                             default=str)[:300]))
    steps.append({"check": name, "ok": bool(ok), "detail": detail})
    return bool(ok)


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---------------------------------------------------------------- 0) 历史产物基线（必须不变）
V9 = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
M6C = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
E1C = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" / \
    "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4"
E2C = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" / \
    "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4"
BASE_DIR = ROOT / "docs" / "regression_2x" / "baseline"
base_before = {"v9": sha(V9), "c1_c4": {c["index"]: sha(ROOT / c["film"]) for c in
                                        M6C["candidates"]},
               "e1": sha(E1C), "e2": sha(E2C),
               "baselines": sorted(p.name for p in BASE_DIR.glob("*"))}
print("历史基线已记录（v9/C1–C4/E1/E2/baseline）")

# ---------------------------------------------------------------- 1) 夹具（全新临时工程）
if WORK.exists():
    shutil.rmtree(WORK, ignore_errors=True)
(WORK / "media" / "voice").mkdir(parents=True, exist_ok=True)
(WORK / "artifacts").mkdir(parents=True, exist_ok=True)
(WORK / "output").mkdir(parents=True, exist_ok=True)

SCRIPT = {"segments": [
    {"chapter": "A", "narration": "这是真实语音合成链路的第一段旁白，用来验证实际时长是否成为权威。",
     "duration_s": 20},
    {"chapter": "B", "narration": "第二段旁白同样由真实 TTS 合成，脚本声明时长只是规划估计。",
     "duration_s": 20},
    {"chapter": "C", "narration": "第三段旁白完成后，系统应当用实际音频长度推导时间轴与字幕。",
     "duration_s": 20},
]}
sp = WORK / "artifacts" / "script.json"
sp.write_text(json.dumps(SCRIPT, ensure_ascii=False), encoding="utf-8")

CFG = {"tools": {"tts": {"provider": "edge-tts", "voice_type": "zh-CN-XiaoxiaoNeural"},
                 "ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}},
       "retry": {"default_max_retries": 2, "backoff_base_s": 0.05}}


class FakeDB:
    def __init__(self, tasks, arts):
        self.tasks, self.arts = tasks, arts

    def get_task(self, tid):
        return self.tasks.get(tid)

    def get_artifact(self, aid):
        return self.arts.get(aid)

    def update_task(self, tid, **kw):
        self.tasks.setdefault(tid, {}).update(kw)


class FakeEngine:
    """最小引擎夹具（与既有单测同构）：真实 agent 代码路径 + 真实文件系统。"""

    def __init__(self, workdir: Path, tasks, arts, config):
        self.work, self.config = workdir, config
        self.db = FakeDB(tasks, arts)
        self.written, self.events = [], []

    def project_dir(self, pid):
        return self.work

    def write_artifact(self, project_id, task_id, type_, content, summary="", version=1,
                       license_=None):
        aid = "a_e2e_{}".format(len(self.written) + 1)
        p = self.work / "artifacts" / "{}.json".format(aid)
        p.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
        rec = {"artifact_id": aid, "type": type_, "path": str(p), "summary": summary}
        self.db.arts[aid] = rec
        self.written.append({"id": aid, "type": type_, "content": content, "path": str(p)})
        return aid

    def attach_artifact(self, task_id, artifact_id):
        self.db.tasks.setdefault(task_id, {}).setdefault("artifacts", []).append(artifact_id)

    def emit(self, project_id, type_, actor, task_id=None, payload=None, human_visible=False):
        self.events.append({"type": type_, "task": task_id, "payload": payload})


def make_engine():
    tasks = {"t_script": {"task_id": "t_script", "artifacts": ["a_script"], "dependencies": []},
             "t_voice": {"task_id": "t_voice", "artifacts": [], "dependencies": ["t_script"]},
             "t_render": {"task_id": "t_render", "artifacts": [], "dependencies": ["t_voice"]}}
    arts = {"a_script": {"artifact_id": "a_script", "type": "script_output", "path": str(sp)}}
    return FakeEngine(WORK, tasks, arts, CFG)


def voice_task():
    return {"task_id": "t_voice", "project_id": PROJECT_ID, "task_type": "voice",
            "dependencies": ["t_script"], "inputs": {}}


def render_task():
    return {"task_id": "t_render", "project_id": PROJECT_ID, "task_type": "render",
            "dependencies": ["t_voice"], "inputs": {}}


# ---------------------------------------------------------------- 2) 真实 TTS（VoiceAgent）
print("\n== 真实 TTS（edge-tts，全新项目 {}）==".format(PROJECT_ID))
eng = make_engine()
t0 = time.time()
tts_error = None
try:
    VoiceAgent().run(eng, voice_task())
except Exception as exc:                                                      # noqa: BLE001
    tts_error = "{}: {}".format(type(exc).__name__, str(exc)[:200])
tts_seconds = round(time.time() - t0, 1)
voice = next((w["content"] for w in eng.written if w["type"] == "voice_output"), None)
check("E1 真实 TTS 完成并写出 voice_output（非 mock）",
      voice is not None and voice.get("complete") is True, tts_error or voice and voice.get("summary"))

real = {}
if voice:
    plan = voice["narration_plan"]
    real = {"project_id": PROJECT_ID, "tts_seconds": tts_seconds,
            "declared_total_s": plan["declared_time_base_s"],
            "actual_segment_durations_s": voice["segment_actual_durations_s"],
            "actual_total_s": plan["actual_total_narration_s"],
            "measured_narration_track_s": voice["narration_duration_s"],
            "audio_time_base_s": voice["audio_time_base_s"],
            "pause_budget_s": plan["pause_budget_s"], "trailing_pad_s": plan["trailing_pad_s"],
            "padding_budget_s": voice["padding_budget_s"],
            "planning_drift_s": voice["planning_drift"]["delta_s"],
            "planning_drift_blocking": voice["planning_drift"]["blocking"],
            "contract_policy": voice["duration_contract"]["policy"],
            "audio_padded_to_timeline": voice["duration_contract"]["audio_padded_to_timeline"]}
    check("E2 actual duration 被逐段记录（真实探测值，全为正）",
          all(isinstance(d, float) and d > 0 for d in voice["segment_actual_durations_s"]),
          voice["segment_actual_durations_s"])
    check("E3 audio_time_base = Σactual + pause×2 + trailing（权威）",
          abs(voice["audio_time_base_s"]
              - (plan["actual_total_narration_s"] + plan["pause_budget_s"] * 2
                 + plan["trailing_pad_s"])) < 0.05, real)
    check("E4 契约 policy=audio_time_base_v2 且不再标记 apad 掩盖",
          real["contract_policy"] == "audio_time_base_v2"
          and real["audio_padded_to_timeline"] is False, real)
    check("E5 declared 与 actual 的偏差被判为 PLANNING_DRIFT（不阻断）",
          real["planning_drift_s"] > 0 and real["planning_drift_blocking"] is False,
          {"drift": real["planning_drift_s"], "blocking": real["planning_drift_blocking"]})
    check("E6 实测旁白音轨时长 ≈ Σ 段实际时长（拼接自洽）",
          abs(real["measured_narration_track_s"] - real["actual_total_s"]) < 0.5, real)

# ---------------------------------------------------------------- 3) 字幕（v2 窗口 vs v1 声明）
print("\n== 字幕时间基对比 ==")
cues_v2, cues_v1, sub_align = [], [], None
if voice:
    seg_payload = [{"narration": s["narration"], "duration_s": s["duration_s"]}
                   for s in SCRIPT["segments"]]
    cues_v2 = core_captions.build_cues(seg_payload, windows=voice["audio_segment_windows"])
    cues_v1 = core_captions.build_cues(seg_payload)
    sub_align = N.subtitle_alignment(cues_v2, plan)
    check("E7 v2 字幕全部落在实际音频窗口内",
          all(any(w["start_s"] - 1e-6 <= c["start"] and c["end"] <= w["end_s"] + 1e-6
                  for w in voice["audio_segment_windows"]) for c in cues_v2), cues_v2)
    check("E8 v2 字幕 ↔ 实际音频对齐门禁 PASS（G-SUB）", sub_align["ok"] is True, sub_align)
    check("E9 v1（声明时基）字幕会越过实际旁白结束 ⇒ 对照成立",
          max(c["end"] for c in cues_v1) > voice["audio_time_base_s"] + 1.0,
          {"v1_last_end": max(c["end"] for c in cues_v1),
           "audio_time_base": voice["audio_time_base_s"]})

# ---------------------------------------------------------------- 4) BGM / mix（预算约束证据）
print("\n== BGM / mix 证据（pause budget 约束）==")
mix_ev = None
if voice:
    iv = core_bgm.narration_intervals(voice, limit_s=voice["audio_time_base_s"])
    mix = core_bgm.mix_filters(narration_label="0:a", bgm_label="1:a", master_chain=None,
                               intervals=iv, settings={}, total_s=voice["audio_time_base_s"],
                               narration_audio_duration_s=voice["narration_duration_s"],
                               padding_budget_s=voice["padding_budget_s"])
    mix_ev = mix["evidence"]
    check("E10 旁白补齐量 ≤ 授权 pause budget（不再用 apad 掩盖短缺）",
          mix_ev["narration_pad_within_budget"] is True, mix_ev)

# ---------------------------------------------------------------- 5) 真实渲染（EditingAgent）
print("\n== 真实渲染（EditingAgent + ffmpeg）==")
mp4_before = {p.name for p in (WORK / "output").glob("*.mp4")}
render_error, rend = None, None
if voice:
    vp = next(w["path"] for w in eng.written if w["type"] == "voice_output")
    eng.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": vp}
    eng.db.tasks["t_voice"]["artifacts"] = ["a_voice"]
    t1 = time.time()
    try:
        EditingAgent().run(eng, render_task())
    except Exception as exc:                                                  # noqa: BLE001
        render_error = "{}: {}".format(type(exc).__name__, str(exc)[:300])
    render_seconds = round(time.time() - t1, 1)
    rend = next((w["content"] for w in eng.written if w["type"] == "render_output"), None)
    check("E11 真实渲染 SUCCEEDED 且登记 render_output（未被门禁误拦）",
          rend is not None, render_error or {"written": [w["type"] for w in eng.written]})

render_facts = {}
if rend:
    pi = rend.get("production_integrity") or {}
    pre_blk = pi.get("pre_render") or {}
    post_blk = pi.get("post_render") or {}

    def state_map(m):
        out = {}
        for k, v in (m or {}).items():
            out[k] = v.get("state") if isinstance(v, dict) else v
        return out

    pre = state_map(pre_blk.get("metrics"))
    post = state_map(post_blk.get("metrics"))
    dc = rend.get("duration_contract") or {}
    out_mp4 = sorted((WORK / "output").glob("*.mp4"))
    render_facts = {
        "film": (str(out_mp4[-1].relative_to(ROOT)) if out_mp4 else None),
        "film_sha256": (sha(out_mp4[-1]) if out_mp4 else None),
        "video_duration_s": rend.get("video_duration_s"),
        "audio_time_base_s": voice["audio_time_base_s"] if voice else None,
        "duration_contract_policy": dc.get("policy"),
        "pre_render_blocked": pre_blk.get("blocked"),
        "post_render_blocked": post_blk.get("blocked"),
        "pre_reasons": pre_blk.get("reasons"), "post_reasons": post_blk.get("reasons"),
        "PI": {**pre, **post},
        "G": {k: v for k, v in pre.items() if str(k).startswith("G-")},
        "effective_flags": pi.get("effective_flags"),
        "promote_blocked": ("PROMOTE_BLOCKED" in json.dumps(post_blk.get("reasons") or [],
                                                             ensure_ascii=False)),
    }
    check("E12 成片时长 ≈ audio_time_base（±1s；不再被 apad 拉到声明时长）",
          abs(float(rend.get("video_duration_s") or 0) - float(voice["audio_time_base_s"])) <= 1.0,
          render_facts)
    check("E13 PI-1/PI-2 PASS（覆盖率≈1、无短缺）",
          render_facts["PI"].get("PI-1") == "PASS" and render_facts["PI"].get("PI-2") == "PASS",
          render_facts["PI"])
    check("E14 PI-3 PASS（**无 ~960s 级尾部静音**）", render_facts["PI"].get("PI-3") == "PASS",
          {"PI-3": render_facts["PI"].get("PI-3"),
           "post_reasons": render_facts["post_reasons"]})
    check("E15 PI-4/PI-6 与 G-TL/G-PAD/G-SUB 均 PASS",
          all(render_facts["PI"].get(k) == "PASS" for k in ("PI-4", "PI-6"))
          and all(v == "PASS" for v in render_facts["G"].values()),
          {"G": render_facts["G"], "PI": render_facts["PI"]})
    check("E16 门禁未阻断且 promote 未被静音阻断（新项目合法成片）",
          render_facts["pre_render_blocked"] is False
          and render_facts["post_render_blocked"] is False
          and render_facts["promote_blocked"] is False
          and render_facts["PI"].get("PI-3") == "PASS", render_facts)

# ---------------------------------------------------------------- 6) 渲染级字幕/音频对齐抽帧
print("\n== 渲染级抽帧核验（字幕与实际语音）==")
frame_checks = {}
if rend and voice:
    cap_files = sorted((WORK / "artifacts").glob("_captions_*.ass"))
    ass_cues = []
    if cap_files:
        import re
        for line in cap_files[-1].read_text(encoding="utf-8").splitlines():
            m = re.match(r"Dialogue: [^,]*,([^,]*),([^,]*),", line)
            if m:
                def sec(x):
                    h, mm, s = x.split(":")
                    return int(h) * 3600 + int(mm) * 60 + float(s)
                ass_cues.append({"start": sec(m.group(1)), "end": sec(m.group(2))})
    wins = [(w["start_s"], w["end_s"]) for w in voice["audio_segment_windows"]]
    tail_start = wins[-1][1]
    in_win = all(any(s0 - 0.05 <= c["start"] and c["end"] <= e0 + 0.05 for s0, e0 in wins)
                 for c in ass_cues)
    frame_checks = {"ass_file": (str(cap_files[-1].relative_to(ROOT)) if cap_files else None),
                    "ass_cue_count": len(ass_cues),
                    "all_cues_inside_actual_windows": in_win,
                    "last_cue_end": (max(c["end"] for c in ass_cues) if ass_cues else None),
                    "actual_end_s": tail_start}
    check("E17 渲染实际烧录的 ASS 字幕全部落在实际音频窗口内",
          bool(ass_cues) and in_win, frame_checks)
    film = ROOT / render_facts["film"] if render_facts.get("film") else None
    if film and film.is_file() and ass_cues:
        mid = (wins[0][0] + min(wins[0][1], wins[0][0] + 4.0)) / 2.0
        tail_t = tail_start + 1.0
        f_mid, f_tail = WORK / "frame_speech.png", WORK / "frame_tailpad.png"
        for t, dst in ((mid, f_mid), (tail_t, f_tail)):
            subprocess.run([str(FFMPEG), "-y", "-v", "error", "-ss", "{:.2f}".format(t),
                            "-i", str(film), "-frames:v", "1", str(dst)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        from PIL import Image                                                   # noqa: E402
        import numpy as np                                                      # noqa: E402

        def band_white(p: Path):
            a = np.asarray(Image.open(p).convert("L"), dtype=np.float32) / 255.0
            return int((a[int(a.shape[0] * 0.82):] > 0.80).sum())

        w_mid, w_tail = band_white(f_mid), band_white(f_tail)
        frame_checks.update({"speech_time_s": round(mid, 2), "tail_pad_time_s": round(tail_t, 2),
                             "white_px_at_speech": w_mid, "white_px_in_tail_pad": w_tail,
                             "frame_speech": str(f_mid.relative_to(ROOT)),
                             "frame_tailpad": str(f_tail.relative_to(ROOT))})
        check("E18 语音时刻有字幕（白字像素 > 0）、尾部 pause 区无字幕",
              w_mid > 0 and w_tail == 0, frame_checks)

# ---------------------------------------------------------------- 7) 历史产物未被触碰
print("\n== 历史产物完整性 ==")
base_after = {"v9": sha(V9), "c1_c4": {c["index"]: sha(ROOT / c["film"]) for c in
                                       M6C["candidates"]},
              "e1": sha(E1C), "e2": sha(E2C),
              "baselines": sorted(p.name for p in BASE_DIR.glob("*"))}
check("E19 v9 / C1–C4 / E1 / E2 候选 sha256 全部未变", base_after == base_before,
      {k: (base_before[k] == base_after[k]) for k in ("v9", "e1", "e2")})
check("E20 baseline 目录未新增/修改（无 promote、无新 tag）",
      base_after["baselines"] == base_before["baselines"])
check("E21 使用的是**全新项目 id**（未覆盖生产项目）",
      PROJECT_ID.startswith("p_dcv2_") and PROJECT_ID not in ("p_96efdc03e1aa",))

report = {"schema": "duration-contract-v2-e2e-v1", "stage": "6-E",
          "project_id": PROJECT_ID, "workspace": str(WORK.relative_to(ROOT)),
          "real_tts_provider": "edge-tts (zh-CN-XiaoxiaoNeural)", "mock_tts_used": False,
          "tts_seconds": tts_seconds, "voice": real, "subtitle": {"v2_alignment": sub_align,
                                                                  "v2_last_cue_end": (max(
                                                                      c["end"] for c in cues_v2)
                                                                      if cues_v2 else None),
                                                                  "v1_last_cue_end": (max(
                                                                      c["end"] for c in cues_v1)
                                                                      if cues_v1 else None)},
          "bgm_mix": mix_ev, "render": render_facts, "frames": frame_checks,
          "steps": steps, "pass": len(PASS), "failed": len(FAIL), "failures": FAIL,
          "render_error": render_error, "tts_error": tts_error,
          "history_untouched": base_after == base_before,
          "v9_reference": {"declared_time_base_s": 1532.0, "audio_total_s": 961.656,
                           "note": "对照：v9 旧时基把 570.3s 缺口用 apad 掩盖并造成字幕漂移"}}
report["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")
).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

print("\n结果: {}/{} 通过{}".format(len(PASS), len(PASS) + len(FAIL),
                                    "" if not FAIL else "  失败项: {}".format(FAIL)))
print("report ->", OUT)
sys.exit(1 if FAIL else 0)
