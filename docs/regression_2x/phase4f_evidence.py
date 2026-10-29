"""4.x Phase 4-F 证据收集：可选 BGM + 旁白 ducking（**离线、确定性**）。

产出（docs/regression_2x/logs/）：
  phase4f_bgm_evidence.json     —— 开关/默认、校验路径、ducking 规则与参数、增益曲线采样、
                                   BGM 来源与 sha256/许可/attribution、成片 ffprobe、最终响度与 TP、
                                   被拒（fail-closed）用例
  phase4f_evidence_summary.txt  —— 人类可读摘要

用法：python docs/regression_2x/phase4f_evidence.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import audio as core_audio  # noqa: E402
from video_studio.core import bgm as core_bgm  # noqa: E402
from video_studio.tools.base import ToolContext  # noqa: E402
from video_studio.agents.retrieval.agent import kw_tokens  # noqa: E402

FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
REAL_JPG = ROOT / "output" / "run03" / "asset_cache" / "files" / "r3_S01-B01_3.img.jpg"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
LINES = []


def say(s):
    print(s, flush=True)
    LINES.append(str(s))


def ff(args, timeout=900):
    return subprocess.run([str(FFMPEG), "-y", "-hide_banner", "-nostats", *args],
                          capture_output=True, text=True, encoding="utf-8", errors="replace",
                          timeout=timeout)


def mean_volume_db(path, ss, dur):
    r = ff(["-ss", str(ss), "-t", str(dur), "-i", str(path), "-af", "volumedetect", "-f", "null", "-"])
    for line in (r.stderr or "").splitlines():
        if "mean_volume:" in line:
            return float(line.split("mean_volume:")[1].split("dB")[0].strip())
    return None


W = Path(tempfile.mkdtemp(prefix="vs_4f_ev_"))
NARR, BGM_OK, BGM_SILENT, BGM_LOUD = W / "narr.wav", W / "bgm.wav", W / "silent.wav", W / "loud.wav"
# 6-A/M2：旁白必须覆盖时间轴（14 s）的 ≥90%，否则成片有长尾静音 —— 属 M2 授权点名的
# 「短旁白 / 成片静音」违约类（渲染前硬门会阻断，导致本步丢失渲染证据）。
# 故旁白改为 6.5s(440Hz) + 6.5s(660Hz) = 13.0s，片尾留 1 s 释放窗。
ff(["-f", "lavfi", "-t", "6.5", "-i", "sine=frequency=440:sample_rate=24000", "-af", "volume=-12dB",
    "-c:a", "pcm_s16le", str(W / "n0.wav")])
ff(["-f", "lavfi", "-t", "6.5", "-i", "sine=frequency=660:sample_rate=24000", "-af", "volume=-12dB",
    "-c:a", "pcm_s16le", str(W / "n1.wav")])
(W / "l.txt").write_text("file '{}'\nfile '{}'\n".format((W / "n0.wav").as_posix(),
                                                         (W / "n1.wav").as_posix()), encoding="utf-8")
ff(["-f", "concat", "-safe", "0", "-i", str(W / "l.txt"), "-c:a", "pcm_s16le", str(NARR)])
ff(["-f", "lavfi", "-t", "20", "-i", "sine=frequency=220:sample_rate=44100", "-af", "volume=-10dB",
    "-c:a", "pcm_s16le", str(BGM_OK)])
ff(["-f", "lavfi", "-t", "10", "-i", "anullsrc=r=44100:cl=mono", "-c:a", "pcm_s16le", str(BGM_SILENT)])
ff(["-f", "lavfi", "-t", "10", "-i", "sine=frequency=220:sample_rate=44100", "-af", "volume=+16dB",
    "-c:a", "pcm_s16le", str(BGM_LOUD)])

VOICE = {"complete": True, "segments": [
    {"index": 0, "status": "SUCCESS", "audio": "media/voice/seg_00.wav", "duration_s": 6.5},
    {"index": 1, "status": "SUCCESS", "audio": "media/voice/seg_01.wav", "duration_s": 6.5}]}
IV = core_bgm.narration_intervals(VOICE)
S = core_bgm.bgm_settings({"tools": {"bgm": {"enabled": True, "provider": "local_bgm",
                                            "source_id": "test_tone_v1", "license": "CC BY-SA 4.0",
                                            "attribution": "Test tone（自生成测试音）"}}})
S_OFF = core_bgm.bgm_settings({})
CFG = {"tools": {"ffmpeg": {"path": str(FFMPEG), "ffprobe": str(FFPROBE)}}}
TOTAL = 14.0

say("=== 4.x Phase 4-F 可选 BGM + ducking：证据（离线）===")
say("开关默认：enabled={} 来源={}；bed_db={} duck_db={} ramp_ms={}".format(
    S_OFF["enabled"], S_OFF["_source"], S_OFF["bed_db"], S_OFF["duck_db"], S_OFF["ramp_ms"]))

# ---- 1) 校验路径 ----
say("\n[1] BGM 校验（来源/字节/音频/响度/许可/归属）")
rows = []
for label, path, kw in (
        ("合规 BGM", BGM_OK, {}),
        ("文件缺失", W / "none.wav", {}),
        ("sha256 不符", BGM_OK, {"sha256": "deadbeef"}),
        ("静音 BGM", BGM_SILENT, {}),
        ("异常响度", BGM_LOUD, {}),
        ("来源不明", BGM_OK, {"provider": None, "source_id": None}),
        ("许可缺失", BGM_OK, {"license": None}),
        ("许可不明", BGM_OK, {"license": "unknown"}),
        ("许可受限", BGM_OK, {"license": "fair use"}),
        ("缺 attribution", BGM_OK, {"attribution": None}),
        ("未配置来源", None, {})):
    settings = {**S, **kw}
    v = core_bgm.verify_bgm(path, settings, ctx=None, config=CFG)
    rows.append({"case": label, "ok": v["ok"], "code": v["code"], "detail": v["detail"],
                 "sha256": v["sha256"], "license": v["license"], "license_class": v["license_class"],
                 "attribution": v["attribution"], "duration_s": v["duration_s"], "lufs": v["lufs"],
                 "true_peak_dbtp": v["true_peak_dbtp"]})
    say("  {:<12s} ok={!s:<5s} code={} lufs={}".format(label, v["ok"], v["code"], v["lufs"]))

# ---- 2) ducking 规则与波形 ----
say("\n[2] ducking 规则（确定性、可复算）")
expr = core_bgm.volume_expression(IV, bed_db=S["bed_db"], duck_db=S["duck_db"],
                                  ramp_s=S["ramp_ms"] / 1000.0)
curve = core_bgm.gain_curve(IV, bed_db=S["bed_db"], duck_db=S["duck_db"],
                            ramp_s=S["ramp_ms"] / 1000.0, total_s=TOTAL, step_s=0.25)
ducked = W / "ducked.wav"
ff(["-i", str(BGM_OK), "-af", "volume='{}':eval=frame".format(expr), "-t", str(TOTAL),
    "-c:a", "pcm_s16le", str(ducked)])
inside = mean_volume_db(ducked, 1.0, 1.5)
outside = mean_volume_db(ducked, 13.4, 0.6)
tail = mean_volume_db(ducked, 13.3, 0.6)
rule = {"bed_db": S["bed_db"], "duck_db": S["duck_db"], "ramp_ms": S["ramp_ms"],
        "narration_priority": True, "intervals": IV,
        "duck_windows": [[round(max(0.0, i["start_s"] - S["ramp_ms"] / 1000.0), 3),
                          round(i["end_s"] + S["ramp_ms"] / 1000.0, 3)] for i in IV],
        "volume_expression": expr,
        "measured": {"inside_narration_db": inside, "outside_narration_db": outside,
                     "tail_after_narration_db": tail,
                     "measured_duck_depth_db": (None if inside is None or outside is None
                                                else round(outside - inside, 2))}}
say("  表达式：{}…".format(expr[:110]))
say("  实测：旁白期间 {} dB / 旁白之外 {} dB → duck 深度 {} dB（规则 {} dB）".format(
    inside, outside, rule["measured"]["measured_duck_depth_db"],
    S["duck_db"] - S["bed_db"]))
say("  恢复：片尾 {} dB（与旁白之外同档）".format(tail))
say("  增益曲线采样（前 12 点，0.25s 步长）：{}".format(
    [(p["t"], p["gain_db"]) for p in curve[:12]]))

# ---- 3) 引擎级渲染（开启 / 关闭）与成片证据 ----
say("\n[3] 引擎级渲染与成片证据")
from video_studio.agents.base import AGENTS  # noqa: E402
from video_studio.core.engine import Engine  # noqa: E402
from video_studio.db.schema import Database  # noqa: E402
from video_studio.llm.router import MockLLM, Router  # noqa: E402

import video_studio.agents.asset.agent  # noqa: E402,F401
import video_studio.agents.editing.agent  # noqa: E402,F401
import video_studio.agents.retrieval.agent  # noqa: E402,F401
import video_studio.agents.script.agent  # noqa: E402,F401
import video_studio.agents.voice.agent  # noqa: E402,F401

WS = Path(tempfile.mkdtemp(prefix="vs_4f_ev_engine_"))
CAT = WS / "catalog"
CAT.mkdir(parents=True, exist_ok=True)
IMG = WS / "vr.jpg"
shutil.copy2(REAL_JPG, IMG)
(CAT / "catalogue.json").write_text(json.dumps({"items": [
    {"source_id": "s1", "name": "VR头显_展示.jpg", "file": str(IMG), "license": "CC BY-SA 4.0",
     "attribution": "T / CC BY-SA"}]}, ensure_ascii=False), encoding="utf-8")
CONFIG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
RULES = json.loads((ROOT / "config" / "rules.json").read_text(encoding="utf-8"))
SCRIPT = {"segments": [{"chapter": "s1", "narration": "虚拟现实头显的正面展示", "duration_s": 6},
                       {"chapter": "s2", "narration": "头显的侧面与镜片细节", "duration_s": 6}],
          "summary": "4-F evidence"}


def run_case(label, bgm_cfg, bgm_file=None):
    cfg = json.loads(json.dumps(CONFIG))
    cfg["tools"]["material"] = {"provider": "local_catalog", "catalog": str(CAT), "timeout_s": 5,
                                "license_required": True}
    cfg["tools"]["retrieval"] = {"scoring": "v2", "query_expansion": True}
    if bgm_cfg:
        cfg["tools"]["bgm"] = bgm_cfg
    db = Database(WS / "state_{}.db".format(label))
    eng = Engine(db, Router(cfg["llm"], MockLLM(cfg["llm"].get("mock", {}).get("responses", {}),
                                                cfg["llm"].get("mock", {}).get("default", {}))),
                 RULES, WS / "projects", cfg, AGENTS)
    pid = eng.create_project("4-F {}".format(label))
    pdir = eng.project_dir(pid)
    (pdir / "media" / "voice").mkdir(parents=True, exist_ok=True)
    shutil.copy2(NARR, pdir / "media" / "voice" / "narration.wav")
    shutil.copy2(W / "n0.wav", pdir / "media" / "voice" / "seg_00.wav")
    shutil.copy2(W / "n1.wav", pdir / "media" / "voice" / "seg_01.wav")
    if bgm_file:
        shutil.copy2(bgm_file, pdir / "media" / "bgm.wav")
    t_s = eng.create_task(pid, "script", "script")
    a = eng.write_artifact(pid, t_s, "script_output", SCRIPT, summary="s")
    eng.attach_artifact(t_s, a)
    eng.db.set_task_status(t_s, "SUCCEEDED")
    t_v = eng.create_task(pid, "voice", "voice", dependencies=[t_s])
    vp = {"complete": True, "audio": "media/voice/narration.wav", "status": "COMPLETE",
          "expected_segments": 2, "successful_segments": 2, "failed_segments": [],
          "narration_duration_s": 13.0, "duration_ok": True,
          "segments": [{"index": 0, "audio": "media/voice/seg_00.wav", "status": "SUCCESS",
                        "duration_s": 6.5}, {"index": 1, "audio": "media/voice/seg_01.wav",
                                             "status": "SUCCESS", "duration_s": 6.5}]}
    a = eng.write_artifact(pid, t_v, "voice_output", vp, summary="v")
    eng.attach_artifact(t_v, a)
    eng.db.set_task_status(t_v, "SUCCEEDED")
    t_r = eng.create_task(pid, "retrieval", "retrieval", dependencies=[t_s])
    eng.run_cycle(pid, limit=4)
    t_render = eng.create_task(pid, "render", "editing", dependencies=[t_s, t_v, t_r])
    for _ in range(4):
        eng.run_cycle(pid, limit=5)
        if eng.db.get_task(t_render)["status"] not in ("PENDING", "DISPATCHED", "RUNNING"):
            break
    t = eng.db.get_task(t_render)
    row = db.conn.execute("select path from artifacts where task_id=? and type='render_output'",
                          (t_render,)).fetchone()
    data = json.loads(Path(row["path"]).read_text(encoding="utf-8")) if row else None
    arow = db.conn.execute("select path from artifacts where project_id=? and type='attribution'"
                           " order by created_at desc limit 1", (pid,)).fetchone()
    attrib = json.loads(Path(arow["path"]).read_text(encoding="utf-8")) if arow else None
    films = sorted((pdir / "output").glob("*.mp4"))
    db.close()
    return {"status": t["status"], "error": t["error"], "data": data, "attrib": attrib,
            "films": [str(f) for f in films], "pdir": str(pdir), "pid": pid}


case_on = run_case("on", {"enabled": True, "source": "media/bgm.wav", "provider": "local_bgm",
                          "source_id": "test_tone_v1", "license": "CC BY-SA 4.0",
                          "attribution": "Test tone（自生成测试音）"}, bgm_file=BGM_OK)
case_off = run_case("off", None)
case_silent = run_case("silent", {"enabled": True, "source": "media/bgm.wav",
                                  "provider": "local_bgm", "source_id": "test_tone_v1",
                                  "license": "CC BY-SA 4.0", "attribution": "T"}, bgm_file=BGM_SILENT)
case_fair = run_case("fairuse", {"enabled": True, "source": "media/bgm.wav",
                                 "provider": "local_bgm", "source_id": "test_tone_v1",
                                 "license": "fair use", "attribution": "T"}, bgm_file=BGM_OK)
bgm_ev = (case_on["data"] or {}).get("bgm") or {}
loud = (case_on["data"] or {}).get("audio_loudness") or {}
probe = {}
if case_on["films"]:
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_streams", "-show_format", "-of", "json",
                        case_on["films"][0]], capture_output=True, text=True, encoding="utf-8")
    meta = json.loads(r.stdout or "{}")
    probe = {"streams": [(s.get("codec_type"), s.get("codec_name"), s.get("sample_rate"),
                          s.get("channels")) for s in meta.get("streams", [])],
             "duration": meta.get("format", {}).get("duration")}
say("  BGM 开启：render={} bgm.applied={} trimmed={} padded={}".format(
    case_on["status"], bgm_ev.get("applied"), (bgm_ev.get("apply_plan") or {}).get("trimmed_to_film"),
    (bgm_ev.get("apply_plan") or {}).get("padded_after_bgm_end")))
say("  BGM 关闭：render={} bgm.applied={}（既有链路不变）".format(
    case_off["status"], (case_off["data"] or {}).get("bgm", {}).get("applied")))
say("  ffprobe：{} duration={}".format(probe.get("streams"), probe.get("duration")))
say("  最终响度：ok={} I={} LUFS TP={} dBTP（契约 -16±1 / ≤-1.5）".format(
    loud.get("ok"), loud.get("measured_lufs"), loud.get("measured_true_peak_dbtp")))
say("  旁白完整性：state={} video_duration_ok={}".format(
    (case_on["data"] or {}).get("narration_state"), (case_on["data"] or {}).get("video_duration_ok")))
say("  fail-closed：静音 BGM → {}（{}）".format(case_silent["status"],
                                                (case_silent["error"] or "")[:80]))
say("  fail-closed：受限许可 → {}（{}）".format(case_fair["status"],
                                               (case_fair["error"] or "")[:80]))

out = {"phase": "4-F", "switch_default": {k: S_OFF[k] for k in
                                          ("enabled", "bed_db", "duck_db", "ramp_ms", "_source")},
       "verify_matrix": rows, "ducking_rule": rule, "gain_curve": curve,
       "engine_cases": {
           "bgm_on": {"status": case_on["status"], "bgm": bgm_ev,
                      "audio_loudness": loud, "probe": probe,
                      "narration_state": (case_on["data"] or {}).get("narration_state"),
                      "video_duration_ok": (case_on["data"] or {}).get("video_duration_ok"),
                      "attribution_bgm": (case_on["attrib"] or {}).get("bgm"),
                      "credits_has_bgm_section": "背景音乐（BGM，可选扩展）"
                      in ((case_on["attrib"] or {}).get("credits_text") or "")},
           "bgm_off": {"status": case_off["status"],
                       "bgm": (case_off["data"] or {}).get("bgm"),
                       "credits_has_bgm_section": "背景音乐（BGM，可选扩展）"
                       in ((case_off["attrib"] or {}).get("credits_text") or "")},
           "bgm_silent": {"status": case_silent["status"], "error": case_silent["error"],
                          "films": case_silent["films"]},
           "bgm_license_restricted": {"status": case_fair["status"], "error": case_fair["error"],
                                      "films": case_fair["films"]}},
       "note": ("BGM 为可选扩展，默认关闭；关闭时不新增任何输入/滤镜，既有输出行为不变。"
                "含 BGM 的混音用**两遍线性 loudnorm**（同一契约常量）达到契约，成片仍由既有 QC 实测把关。")}
(LOGS / "phase4f_bgm_evidence.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
(LOGS / "phase4f_evidence_summary.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase4f_bgm_evidence.json")
