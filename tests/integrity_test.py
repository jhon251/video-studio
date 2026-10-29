# -*- coding: utf-8 -*-
"""6-A / M1 单元回归：**Production Integrity 只读度量**（PI-1 … PI-6）。

覆盖：
  I1 PI-1 覆盖率（含 v9 实测值 961.656/1532.0 → FAIL 0.6277）
  I2 PI-2 双侧时长契约（短差 FAIL / 过长 FAIL / 相等 PASS）
  I3 PI-3 成片静音 profile（解析单测 + 合成夹具 + v9 实测 570.869 s）
  I4 PI-4 AV 轨道一致性（合成错位夹具 FAIL + v9 实测 PASS）
  I5 PI-5 字幕 orphan（SRT 解析 + 对齐 PASS / 30% orphan FAIL + **v9 真实 73 条**）
  I6 PI-6 段落边界漂移（合成 63 s FAIL + v9 552.16 s FAIL）
  I7 汇总口径：UNKNOWN / NOT_ASSESSABLE 绝不计入 PASS
  I8 只读保证：DB 文件 sha256 不变、项目目录无新增/改动
  I9 CLI 冒烟：`run.py integrity --json` 结构可机读（默认只读、不阻断）

用法: python tests/integrity_test.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8")

from fixtures.build_integrity_fixtures import (make_film, make_track_mismatch,  # noqa: E402
                                               segments, srt_from_cues, timeline)
from video_studio.core import integrity as I  # noqa: E402

PASS, FAIL, SKIP = [], [], []
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
TRUTH = json.loads((ROOT / "tests" / "fixtures" / "production_integrity_truth_v1.json")
                   .read_text(encoding="utf-8"))
POLICY = TRUTH["policy"]
V9 = next(c for c in TRUTH["cases"] if c["id"] == "V9-REAL")
V9M = V9["measured"]
DB = ROOT / "projects" / "video_studio.db"
V9_FILM = ROOT / "projects" / V9["project_id"] / "output" / "{}_draft.mp4".format(V9["film_task"])


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:340]))


def skip(name, why):
    SKIP.append(name)
    print("SKIP  {} | {}".format(name, why))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---------------- I1 PI-1 ----------------
m = I.narration_coverage(V9M["narration_duration_s"], V9M["timeline_duration_s"], POLICY)
check("I1a PI-1 复现 v9：961.656/1532.0 → FAIL、覆盖率 0.6277、短差 570.344 s",
      m["state"] == "FAIL" and m["coverage_ratio"] == 0.6277
      and abs(m["shortfall_s"] - 570.344) < 0.01, m)
check("I1b PI-1 满覆盖 → PASS（20/20 s）",
      I.narration_coverage(20.0, 20.0, POLICY)["state"] == "PASS")
check("I1c PI-1 缺输入 → NOT_ASSESSABLE（不得 PASS）",
      I.narration_coverage(None, 20.0, POLICY)["state"] == "NOT_ASSESSABLE")

# ---------------- I2 PI-2 ----------------
d = I.duration_contract_dual(V9M["timeline_duration_s"], V9M["narration_duration_s"], POLICY)
check("I2a PI-2 复现 v9：短差 570.344 s 超阈 → FAIL（excess_block=False、shortfall_block=True）",
      d["state"] == "FAIL" and d["shortfall_block"] is True and d["excess_block"] is False
      and abs(d["contract"]["shortfall_s"] - 570.344) < 0.01, {k: d[k] for k in
                                                               ("state", "shortfall_block", "excess_block")})
check("I2b PI-2 旁白过长超容差 → FAIL（既有 excess 规则仍在）",
      I.duration_contract_dual(20.0, 30.0, POLICY)["state"] == "FAIL")
check("I2c PI-2 时长相等 → PASS", I.duration_contract_dual(20.0, 20.0, POLICY)["state"] == "PASS")

# ---------------- I3 PI-3 ----------------
parsed = I.parse_silencedetect(
    "[silencedetect @ x] silence_start: 5.0\n[silencedetect @ x] silence_end: 9.5 | "
    "silence_duration: 4.5\n[silencedetect @ x] silence_start: 12.0\n")
check("I3a parse_silencedetect：块/时长/未闭合尾块（end=None，用总长兜底）解析正确",
      len(parsed) == 2 and parsed[0]["dur"] == 4.5 and parsed[1]["start"] == 12.0
      and parsed[1]["end"] is None, parsed)
tmp = Path(tempfile.mkdtemp(prefix="vs_m1_int_"))
clean = make_film(tmp / "clean.mp4", FFMPEG, duration_s=20.0, speech_s=20.0)
short_audio = make_film(tmp / "short.mp4", FFMPEG, duration_s=20.0, speech_s=8.0)
p_clean = I.audio_silence_profile(clean, FFMPEG, 20.0, POLICY)
p_short = I.audio_silence_profile(short_audio, FFMPEG, 20.0, POLICY)
check("I3b PI-3 合成满覆盖成片 → PASS（无 ≥2 s 静音块）",
      p_clean["state"] == "PASS" and p_clean["blocks"] == 0, p_clean)
check("I3c PI-3 合成短旁白（8/20 s，apad 补 12 s）→ FAIL 且尾部静音 ≈12 s",
      p_short["state"] == "FAIL" and p_short["tail_silence_s"] >= 10.0, p_short)
check("I3d PI-3 缺成片 → NOT_ASSESSABLE（不得 PASS）",
      I.audio_silence_profile(None, FFMPEG, 20.0, POLICY)["state"] == "NOT_ASSESSABLE")
if V9_FILM.is_file():
    p_v9 = I.audio_silence_profile(V9_FILM, FFMPEG, V9M["timeline_duration_s"], POLICY)
    check("I3e PI-3 **v9 真实成片**：1 块静音、961.14→1532.01、570.869 s、占比 0.3726 → FAIL",
          p_v9["state"] == "FAIL" and p_v9["blocks"] == 1
          and abs(p_v9["longest_silence_s"] - 570.869) < 0.05
          and abs(p_v9["silence_ratio"] - 0.3726) < 0.001
          and abs(p_v9["speech_end_s"] - 961.144) < 0.05,
          {k: p_v9[k] for k in ("blocks", "longest_silence_s", "silence_ratio", "speech_end_s")})
else:
    skip("I3e PI-3 v9 真实成片", "成片不存在")

# ---------------- I4 PI-4 ----------------
mm = make_track_mismatch(tmp / "mismatch.mp4", FFMPEG, video_s=8.0, audio_s=20.0)
pr_clean = I.probe_tracks(clean, FFPROBE)
pr_mm = I.probe_tracks(mm, FFPROBE)
check("I4a PI-4 合成成片（20 s）→ PASS",
      I.av_track_consistency(pr_clean, 20.0, POLICY)["state"] == "PASS",
      I.av_track_consistency(pr_clean, 20.0, POLICY))
v_mm = I.av_track_consistency(pr_mm, 20.0, POLICY)
check("I4b PI-4 合成轨道错位（视频 8 s / 音频 20 s）→ FAIL（差 12 s）",
      v_mm["state"] == "FAIL" and v_mm["track_delta_s"] >= 11.0, v_mm)
if V9_FILM.is_file():
    pr_v9 = I.probe_tracks(V9_FILM, FFPROBE)
    v9_pi4 = I.av_track_consistency(pr_v9, V9M["timeline_duration_s"], POLICY)
    check("I4c PI-4 **v9 真实成片**：视频 1531.96 / 音频 1532.0 / 帧 38300 → PASS",
          v9_pi4["state"] == "PASS" and abs(pr_v9["video_s"] - 1531.96) < 0.01
          and abs(pr_v9["audio_s"] - 1532.0) < 0.01, pr_v9)
else:
    skip("I4c PI-4 v9 真实成片", "成片不存在")

# ---------------- I5 PI-5 ----------------
aligned = srt_from_cues([(i * 1.0, i * 1.0 + 0.9, "第 {} 条".format(i + 1)) for i in range(20)])
orphan = srt_from_cues([(i * 1.0, i * 1.0 + 0.9, "第 {} 条".format(i + 1)) for i in range(20)]
                       + [(20.1 + i, 20.1 + i + 0.9, "orphan {}".format(i + 1)) for i in range(9)])
cues_aligned = I.parse_srt_cues(aligned)
check("I5a parse_srt_cues：20 条 cue 时间/文本解析正确",
      len(cues_aligned) == 20 and abs(cues_aligned[0]["start"]) < 1e-6
      and cues_aligned[19]["end"] == 19.9, len(cues_aligned))
check("I5b PI-5 字幕与旁白对齐（20 条全在 20 s 内）→ PASS",
      I.subtitle_orphans(cues_aligned, 20.0, 20.0, POLICY)["state"] == "PASS")
o = I.subtitle_orphans(orphan, 20.0, 30.0, POLICY)
check("I5c PI-5 30% orphan（9/29 落在旁白结束之后）→ FAIL",
      o["state"] == "FAIL" and o["orphan_cues"] == 9, o)
if DB.is_file():
    import sqlite3
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    row = con.execute("select path from artifacts where project_id=? and type='subtitle' "
                      "order by created_at desc limit 1", (V9["project_id"],)).fetchone()
    con.close()
    if row:
        sp = Path(row["path"])
        sp = sp if sp.is_absolute() else ROOT / sp
        srt = json.loads(sp.read_text(encoding="utf-8")).get("srt", "")
        v9sub = I.subtitle_orphans(srt, V9M["narration_duration_s"], V9M["timeline_duration_s"],
                                   POLICY)
        check("I5d PI-5 **v9 真实字幕**：216 cue、orphan 73 条（0.338）、首条 967.4 s、覆盖 0.6446 → FAIL",
              v9sub["state"] == "FAIL" and v9sub["cues"] == 216 and v9sub["orphan_cues"] == 73
              and abs(v9sub["orphan_first_s"] - 967.4) < 0.2
              and abs(v9sub["coverage_of_timeline"] - 0.6446) < 0.001,
              {k: v9sub[k] for k in ("cues", "orphan_cues", "orphan_first_s",
                                     "coverage_of_timeline")})
    else:
        skip("I5d PI-5 v9 真实字幕", "无字幕产物")
else:
    skip("I5d PI-5 v9 真实字幕", "无 DB")

# ---------------- I6 PI-6 ----------------
seg10 = segments(10, "段落", 10.0)
dr = I.segment_boundary_drift(seg10, [3.0] * 10, POLICY)
check("I6a PI-6 合成（脚本 10×10 s / TTS 10×3 s）→ FAIL，最大漂移 63 s",
      dr["state"] == "FAIL" and abs(dr["max_abs_drift_s"] - 63.0) < 0.01,
      {k: dr[k] for k in ("state", "max_abs_drift_s", "final_drift_s")})
check("I6b PI-6 脚本与 TTS 完全一致 → PASS",
      I.segment_boundary_drift(seg10, [10.0] * 10, POLICY)["state"] == "PASS")
check("I6c PI-6 缺逐段时长 → UNKNOWN（不得 PASS）",
      I.segment_boundary_drift(seg10, [], POLICY)["state"] == "UNKNOWN")
v9seg = I.segment_boundary_drift([{"duration_s": d} for d in V9M["script_durs"]],
                                 V9M["voice_durs"], POLICY)
check("I6d PI-6 v9 真实 21 段（脚本合计 1530.0 / TTS 合计 961.6）→ 最大漂移 ≈552 s、"
      "末段漂移 ≈−568.3 s → FAIL（真值集用 6-A 审计的 1 位小数表，故容差 ±0.1 s；"
      "3 位小数原始值给出 552.16/−568.344）",
      v9seg["state"] == "FAIL" and abs(v9seg["max_abs_drift_s"] - 552.16) < 0.1
      and abs(v9seg["final_drift_s"] + 568.344) < 0.1,
      {k: v9seg[k] for k in ("state", "max_abs_drift_s", "final_drift_s")})

# ---------------- I7 汇总口径 ----------------
sum_unknown = I.summarize({"PI-1": {"state": "UNKNOWN"}})
sum_na = I.summarize({"PI-1": {"state": "NOT_ASSESSABLE"}})
sum_fail = I.summarize({"PI-1": {"state": "PASS"}, "PI-3": {"state": "FAIL"}})
sum_pass = I.summarize({"PI-1": {"state": "PASS"}, "PI-3": {"state": "PASS"}})
check("I7 汇总：UNKNOWN→UNKNOWN、NOT_ASSESSABLE→NOT_ASSESSABLE、有 FAIL→FAIL、全 PASS→PASS"
      "（UNKNOWN ≠ PASS）",
      sum_unknown["overall"] == "UNKNOWN" and sum_na["overall"] == "NOT_ASSESSABLE"
      and sum_fail["overall"] == "FAIL" and sum_pass["overall"] == "PASS"
      and sum_unknown["unknown_is_not_pass"] is True,
      {k: v["overall"] for k, v in (("unknown", sum_unknown), ("na", sum_na),
                                    ("fail", sum_fail), ("pass", sum_pass))})

# ---------------- I8 只读保证 ----------------
before = {p.relative_to(ROOT).as_posix(): (p.stat().st_size, int(p.stat().st_mtime))
          for p in (ROOT / "projects" / V9["project_id"]).rglob("*") if p.is_file()}
db_sha_before = sha(DB) if DB.is_file() else None
from video_studio.ops.integrity import build_integrity_report  # noqa: E402
rep = build_integrity_report(V9["project_id"], DB, ROOT, CFG,
                             film_task=V9["film_task"]) if DB.is_file() else None
after = {p.relative_to(ROOT).as_posix(): (p.stat().st_size, int(p.stat().st_mtime))
         for p in (ROOT / "projects" / V9["project_id"]).rglob("*") if p.is_file()}
db_sha_after = sha(DB) if DB.is_file() else None
check("I8a 只读：跑完 integrity 报告后**项目目录零新增/零改动**",
      before == after, {"new": sorted(set(after) - set(before)),
                        "changed": sorted(k for k in before if k in after and before[k] != after[k])})
check("I8b 只读：DB 文件 sha256 不变", db_sha_before == db_sha_after,
      {"before": (db_sha_before or "")[:16], "after": (db_sha_after or "")[:16]})
if rep:
    check("I8c 报告自称只读且**未接线**（read_only=true / enforced=false），六项 PI 齐全",
          rep["read_only"] is True and rep["enforced"] is False
          and set(rep["metrics"]) == {"PI-1", "PI-2", "PI-3", "PI-4", "PI-5", "PI-6"}, list(rep))
    check("I8d 端到端复现 v9：PI-1/PI-2/PI-5/PI-6 = FAIL、PI-4 = PASS，overall=FAIL",
          rep["metrics"]["PI-1"]["state"] == "FAIL" and rep["metrics"]["PI-2"]["state"] == "FAIL"
          and rep["metrics"]["PI-4"]["state"] == "PASS"
          and rep["metrics"]["PI-5"]["state"] == "FAIL"
          and rep["metrics"]["PI-6"]["state"] == "FAIL"
          and rep["summary"]["overall"] == "FAIL",
          {k: v["state"] for k, v in rep["metrics"].items()})
else:
    skip("I8c/I8d 端到端", "无 DB")

# ---------------- I9 CLI 冒烟 ----------------
r = subprocess.run([sys.executable, "run.py", "integrity", V9["project_id"], "--json",
                    "--film-task", V9["film_task"]], cwd=str(ROOT), capture_output=True, text=True,
                   encoding="utf-8", errors="replace", timeout=3600)
try:
    cli = json.loads(r.stdout)
    ok_cli = (cli.get("schema") == "production-integrity-v1" and cli.get("read_only") is True
              and cli.get("enforced") is False and "PI-3" in cli.get("metrics", {}))
except Exception as exc:                                        # noqa: BLE001
    cli, ok_cli = {"err": repr(exc), "stdout_head": (r.stdout or "")[:200]}, False
check("I9 `run.py integrity --json`：结构可机读、标注只读/未接线（含 PI-3）", ok_cli, cli)

print("\n结果: {}/{} 通过{}".format(len(PASS), len(PASS) + len(FAIL),
                                   "（另有 {} 项 SKIP）".format(len(SKIP)) if SKIP else ""))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
