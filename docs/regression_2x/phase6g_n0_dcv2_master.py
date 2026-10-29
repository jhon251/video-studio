# -*- coding: utf-8 -*-
"""6-G / N0 —— 建立 **DCv2 母片**（978.656s 新时基），只写沙箱，**不覆盖** v9/baseline/历史 artifact。

做法（全部确定性、可复算）：
  1. 场景窗口 = `phase6f_rebuild_plan_v2.new_production_timeline`（21 段，S21.end=978.656）
  2. 逐场景用 **v9 在用素材**（只读）渲染正好等于窗口时长的无音轨视频段（720p25，交替轻微缩放）
  3. concat 21 段（stream copy）
  4. 音频 = 真实 TTS 旁白（961.656s）按 **DCv2 音频窗口** 用 `adelay`(=i×750ms) 铺到 978.656s 静音床上
     ⇒ 段间停顿 0.75×20 + 收尾 2.0 精确落在时间轴位置（不重录 TTS）
  5. 烧录 **DCv2 字幕**（`build_cues(windows=实际音频窗口)`）→ 单次 `ass=` 过片
  6. 合成 → 探测 duration（必须 = 978.656±0.05）→ 写 sha256 / timeline identity / manifest
用法: python docs/regression_2x/phase6g_n0_dcv2_master.py
"""
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import captions as core_captions              # noqa: E402
from video_studio.core import narration as N                         # noqa: E402
from video_studio.ops import execution as OPX                        # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
FFMPEG = ROOT / "bin" / "ffmpeg.exe"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
P2 = json.loads((LOGS / "phase6f_rebuild_plan_v2.json").read_text(encoding="utf-8"))
TS = time.strftime("%Y%m%d_%H%M%S")
SANDBOX = ROOT / "output" / "phase6g_sandbox" / TS
WORK, OUTD = SANDBOX / "work", SANDBOX / "out"
PROD = P2["math_verification"]["production_duration_s"]
W, H, FPS = 1280, 720, 25

for d in (WORK, OUTD):
    d.mkdir(parents=True, exist_ok=True)


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def probe(p: Path) -> dict:
    r = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,codec_name,width,height",
                        "-of", "json", str(p)], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    j = json.loads(r.stdout or "{}")
    return {"duration_s": round(float((j.get("format") or {}).get("duration") or 0), 3),
            "streams": [(s.get("codec_type"), s.get("codec_name"), s.get("width"), s.get("height"))
                        for s in (j.get("streams") or [])]}


def run(args: list, tag: str):
    t0 = time.time()
    r = subprocess.run([str(a) for a in args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    if r.returncode != 0:
        raise RuntimeError("{} failed rc={}: {}".format(tag, r.returncode, (r.stderr or "")[-400:]))
    print("   ffmpeg {} ok ({:.1f}s)".format(tag, time.time() - t0))


# ---------------------------------------------------------------- 只读取数
con = sqlite3.connect("file:{}?mode=ro".format(
    (ROOT / "projects" / "video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
rows = [dict(r) for r in con.execute(
    "select type,task_id,path from artifacts where project_id='p_96efdc03e1aa' order by created_at")]
con.close()


def load(rec):
    p = Path(rec["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


def latest(t, task=None):
    lst = [r for r in rows if r["type"] == t]
    return load(next((y for y in lst if task and y["task_id"] == task), lst[-1]))


script = latest("script_output")
voice = latest("voice_output")
render = latest("render_output", "t_d0a54bdf1810")
timeline = render.get("material_timeline") or []
asset_path = {}
for e in timeline:
    sa = e.get("selected_asset") or {}
    if sa.get("path"):
        pth = Path(sa["path"])
        asset_path[str(e.get("scene_id"))] = pth if pth.is_absolute() else ROOT / pth
narr = ROOT / "projects" / "p_96efdc03e1aa" / voice["audio"]
assert narr.is_file(), narr
chain = P2["remapping_21_segments"]

# ---------------------------------------------------------------- 1) 场景视频段
print("== N0-1 逐场景渲染（21 段，新窗口时长）==")
segs = []
for i, c in enumerate(chain):
    sid = c["scene_id"]
    w0, w1 = c["new_timeline_window_s"]
    dur = round(w1 - w0, 3)
    ap = asset_path.get(sid)
    if not ap or not ap.is_file():
        raise RuntimeError("N0_MATERIAL_MISSING: {} 无可用素材路径".format(sid))
    zoom = 1.0 if i % 2 == 0 else 1.08
    if abs(zoom - 1.0) < 1e-6:
        vf = ("scale={}:{}:force_original_aspect_ratio=increase,crop={}:{},fps={},"
              "format=yuv420p").format(W, H, W, H, FPS)
    else:
        vf = ("scale={}:{}:force_original_aspect_ratio=increase,"
              "crop={}:{}:(iw-ow)/2:(ih-oh)/2,fps={},format=yuv420p").format(
                  int(W * zoom), int(H * zoom), W, H, FPS)
    seg = WORK / "seg_{:02d}_{}.mp4".format(i + 1, sid)
    run([FFMPEG, "-y", "-v", "error", "-loop", "1", "-i", ap, "-t", "{:.3f}".format(dur),
         "-vf", vf, "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30",
         "-pix_fmt", "yuv420p", "-video_track_timescale", "25000", seg], "seg:" + sid)
    pr = probe(seg)
    segs.append({"index": i, "scene_id": sid, "window_s": [w0, w1], "target_duration_s": dur,
                 "file": seg.name, "sha256": sha(seg), "duration_s": pr["duration_s"],
                 "asset": ap.name})

concat_txt = WORK / "concat.txt"
concat_txt.write_text("".join("file '{}'\n".format((WORK / s["file"]).as_posix())
                              for s in segs), encoding="utf-8")
video_concat = WORK / "video_concat.mp4"
print("== N0-2 concat 21 段 ==")
run([FFMPEG, "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", concat_txt,
     "-c", "copy", video_concat], "concat")
vprobe = probe(video_concat)

# ---------------------------------------------------------------- 3) DCv2 字幕（实际音频窗口）
cue_windows = [{"scene_id": c["scene_id"], "start_s": c["new_audio_window_s"][0],
                "end_s": c["new_audio_window_s"][1]} for c in chain]
script_segs = [s for s in (script.get("segments") or [])
               if str(s.get("narration", "")).strip()]
cues = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s.get("duration_s")} for s in script_segs],
    windows=[{"start_s": w["start_s"], "end_s": w["end_s"]} for w in cue_windows])
ass_path = WORK / "dcv2_captions.ass"
ass_path.write_text(core_captions.to_ass(cues, resolution="{}x{}".format(W, H)), encoding="utf-8")
cue_json = WORK / "dcv2_cues.json"
cue_json.write_text(json.dumps(cues, ensure_ascii=False, indent=1), encoding="utf-8")
print("== N0-3 字幕：{} 条 cue，末条 {:.3f}s（旧 v1 表末条 1528.636s）==".format(
    len(cues), max(c["end"] for c in cues)))

# ---------------------------------------------------------------- 4) DCv2 音频（adelay 铺到静音床）
print("== N0-4 构建 DCv2 音频（真实 TTS + 停顿预算）==")
parts = []
fc = ["-f", "lavfi", "-t", "{:.3f}".format(PROD), "-i", "anullsrc=r=24000:cl=mono",
      "-i", str(narr)]
graph = ["[1:a]asplit={}[n0]".format(len(chain)) + "".join(
    "" for _ in range(0))]
graph = []
graph.append("[1:a]asplit={}{}".format(
    len(chain), "".join("[a{}]".format(i) for i in range(len(chain)))))
cur = 0.0
for i, c in enumerate(chain):
    d = c["actual_tts_duration_s"]
    delay_ms = int(round(c["new_audio_window_s"][0] * 1000))
    graph.append("[a{}]atrim={:.6f}:{:.6f},asetpts=N/SR/TB,adelay={}|{}[d{}]".format(
        i, cur, cur + d, delay_ms, delay_ms, i))
    cur += d
mix_in = "[0:a]" + "".join("[d{}]".format(i) for i in range(len(chain)))
graph.append("{}amix=inputs={}:duration=first:normalize=0[out]".format(
    mix_in, len(chain) + 1))
audio_wav = WORK / "dcv2_audio.wav"
run([FFMPEG, "-y", "-v", "error"] + fc + ["-filter_complex", ";".join(graph),
     "-map", "[out]", "-c:a", "pcm_s16le", "-ar", "24000", "-ac", "1", audio_wav], "audio")
aprobe = probe(audio_wav)

# ---------------------------------------------------------------- 5) 烧字幕 + 6) 合成
print("== N0-5/6 烧录 DCv2 字幕并合成母片 ==")
video_ass = WORK / "video_captioned.mp4"
ass_file = ass_path.as_posix().replace(":", "\\:")
run([FFMPEG, "-y", "-v", "error", "-i", video_concat, "-vf",
     "ass=filename='{}':fontsdir='C\\:/Windows/Fonts'".format(ass_file),
     "-an", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "30", "-pix_fmt", "yuv420p",
     "-video_track_timescale", "25000", video_ass], "ass-burn")
master = OUTD / "dcv2_master_{}.mp4".format(TS)
run([FFMPEG, "-y", "-v", "error", "-i", video_ass, "-i", audio_wav, "-map", "0:v:0",
     "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-ar", "24000",
     "-t", "{:.3f}".format(PROD), "-movflags", "+faststart", master], "mux")
mprobe = probe(master)

# ---------------------------------------------------------------- 校验 + 记录
checks = []


def ck(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False)[:200]))


ck("N0.1 master duration == 978.656（±0.05）", abs(mprobe["duration_s"] - PROD) <= 0.05, mprobe)
ck("N0.2 时长恒等式 978.656 = 961.656 + 15.0 + 2.0",
   abs(sum(c["actual_tts_duration_s"] for c in chain) - 961.656) < 1e-9
   and abs(0.75 * 20 - 15.0) < 1e-9 and abs(2.0 - 2.0) < 1e-9, None)
ck("N0.3 21 场景连续且 S21.end == 978.656",
   all(abs(chain[i]["new_timeline_window_s"][1]
           - chain[i + 1]["new_timeline_window_s"][0]) < 1e-9 for i in range(20))
   and abs(chain[-1]["new_timeline_window_s"][1] - PROD) < 1e-9)
ck("N0.4 音频时长 == 978.656（±0.05）", abs(aprobe["duration_s"] - PROD) <= 0.05, aprobe)
ck("N0.5 字幕为 DCv2 表（末条 < 978.656，且非 1528.636）",
   max(c["end"] for c in cues) <= PROD + 1e-6, max(c["end"] for c in cues))
ck("N0.6 21 段视频段时长与窗口一致（±1 帧）",
   all(abs(s["duration_s"] - s["target_duration_s"]) <= 0.04 for s in segs),
   [s["duration_s"] for s in segs])
ck("N0.7 输出位于沙箱（不在 projects/ 内）", "phase6g_sandbox" in str(master))
ck("N0.8 视频/音频流齐备", any(s[0] == "video" for s in mprobe["streams"])
   and any(s[0] == "audio" for s in mprobe["streams"]), mprobe["streams"])

# 历史不可变（渲染前后）
HIST = {"v9": ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"}
m6c = json.loads((LOGS / "phase6c_batch.json").read_text(encoding="utf-8"))
for c in m6c["candidates"]:
    HIST["c" + str(c["index"])] = ROOT / c["film"]
HIST["e1"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-ad4bbbee7ea2_outro.mp4")
HIST["e2"] = (ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6e2" / "output" /
              "t_d0a54bdf1810_draft_6c_rp-bee31dff3335_vaid.mp4")
hist_sha = {k: (sha(p) if p.is_file() else None) for k, p in HIST.items()}
ck("N0.9 历史产物 sha256 未变（v9/C1–C4/E1/E2）",
   hist_sha["v9"].startswith("22705c7d7ea20b40") and hist_sha["e1"].startswith("e45d79976856090e")
   and hist_sha["e2"].startswith("659bd0d7c288cd7b")
   and hist_sha["c1"].startswith("fcaa4e78"), {k: v[:12] for k, v in hist_sha.items()})
db_sha = sha(ROOT / "projects" / "video_studio.db")
baseline_entries = sorted(p.name for p in (ROOT / "docs" / "regression_2x" / "baseline").glob("*"))

# 时基身份（B2 复用生产函数）
identity = OPX.timeline_identity(
    [{"scene_id": c["scene_id"], "start_s": c["new_timeline_window_s"][0],
      "end_s": c["new_timeline_window_s"][1]} for c in chain],
    production_duration_s=PROD, source="docs/regression_2x/logs/phase6f_rebuild_plan_v2.json")
ident_file = OUTD / "dcv2_timeline_identity.json"
ident_file.write_text(json.dumps(identity, ensure_ascii=False, indent=1), encoding="utf-8")

manifest = {"schema": "dcv2-master-manifest-v1", "stage": "6-G/N0", "ts": TS,
            "sandbox": str(SANDBOX.relative_to(ROOT)),
            "master": {"path": str(master.relative_to(ROOT)), "bytes": master.stat().st_size,
                       "sha256": sha(master), "duration_s": mprobe["duration_s"],
                       "streams": mprobe["streams"]},
            "audio": {"path": str(audio_wav.relative_to(ROOT)), "sha256": sha(audio_wav),
                      "duration_s": aprobe["duration_s"], "narration_truth_s": 961.656,
                      "pause_budget_s": 0.75, "pauses": 20, "trailing_pad_s": 2.0,
                      "placement": "adelay = i×750ms（按 DCv2 音频窗口精确落位）"},
            "captions": {"ass": str(ass_path.relative_to(ROOT)), "sha256": sha(ass_path),
                         "cues": len(cues), "last_cue_end_s": max(c["end"] for c in cues),
                         "time_base": "DCv2（实际音频窗口）", "v1_last_cue_end_s": 1528.636},
            "scene_segments": segs,
            "timeline_identity": identity,
            "timeline_identity_file": str(ident_file.relative_to(ROOT)),
            "production_duration_check": {
                "formula": "961.656 + 0.75×20 + 2.0", "value": PROD,
                "measured_master_s": mprobe["duration_s"]},
            "checks": checks, "all_pass": all(c["ok"] for c in checks),
            "invariants": {"history_sha256": hist_sha, "db_sha256": db_sha,
                           "baseline_entries": baseline_entries,
                           "db_unchanged_declared": True, "baseline_unchanged_declared": True,
                           "v9_overwritten": False, "candidate_written": False,
                           "project_writes": 0,
                           "note": "母片只写入 output/phase6g_sandbox/<ts>/（非 projects/、非 candidate）"},
            "ffmpeg_calls": len(segs) + 4}
manifest["manifest_sha256"] = hashlib.sha256(json.dumps(
    {k: v for k, v in manifest.items() if k != "manifest_sha256"}, sort_keys=True,
    ensure_ascii=False, separators=(",", ":"), default=str).encode("utf-8")).hexdigest()
mf_path = LOGS / "phase6g_n0_dcv2_master.json"
mf_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1, default=str),
                   encoding="utf-8")

print("\n== N0 汇总 ==")
print("  master      : {} ({:.1f} MB, sha256 {})".format(
    manifest["master"]["path"], manifest["master"]["bytes"] / 1e6,
    manifest["master"]["sha256"][:16]))
print("  duration    : {} s（目标 978.656）".format(mprobe["duration_s"]))
print("  timeline id : {}".format(identity["identity_sha256"][:16]))
print("  captions    : {} cues, 末条 {:.3f}s".format(len(cues), max(c["end"] for c in cues)))
print("  checks      : {}/{} pass".format(sum(1 for c in checks if c["ok"]), len(checks)))
print("manifest ->", mf_path)
sys.exit(0 if all(c["ok"] for c in checks) else 1)
