# -*- coding: utf-8 -*-
"""Duration Contract v2 —— 单元 / 回归测试（覆盖授权书要求的 9 类场景）。

场景：
  V1 actual < declared        V2 actual > declared       V3 多段累计 drift
  V4 zero/invalid TTS duration V5 字幕越过 actual audio   V6 padding > pause budget
  V7 final tail silence        V8 timeline/audio mismatch V9 旧 apad 掩盖路径
另含：PLANNING_DRIFT 非阻断、G-SEG/G-TL/G-PAD/G-SUB 门禁接线、promote 静音阻断、
     以及**真实 v9 数据回放**（declared 1530 vs actual 961.656）作为旧/新行为对照。

用法: python tests/duration_contract_v2_test.py
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import captions as core_captions             # noqa: E402
from video_studio.core import integrity as core_integrity           # noqa: E402
from video_studio.core import narration as N                        # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
WORK = ROOT / "output" / "phase6e_dc_v2_probe"
PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + json.dumps(detail, ensure_ascii=False,
                                                             default=str)[:260]))


def script_of(durs, texts=None):
    texts = texts or ["旁白第{}段。".format(i + 1) * 12 for i in range(len(durs))]
    return {"segments": [{"scene_id": "S{:02d}".format(i + 1), "duration_s": d,
                          "narration": t} for i, (d, t) in enumerate(zip(durs, texts))]}


def voice_of(actuals, track=None):
    segs = [{"index": i, "status": "SUCCESS", "audio": "a{}.mp3".format(i),
             "duration_s": a, "bytes": 1000, "reused": False, "attempts": 1,
             "text_sha256": "x"} for i, a in enumerate(actuals)]
    return {"segments": segs,
            "narration_duration_s": (round(sum(actuals), 3) if track is None else track),
            "status": "COMPLETE", "complete": True}


print("== V1 actual < declared ==")
sc, vo = script_of([40, 55]), voice_of([30.0, 39.34])
plan = N.narration_plan(sc, vo)
check("V1a audio_time_base = Σactual + pause + trailing（权威）",
      abs(plan["audio_time_base_s"] - (30.0 + 39.34 + 0.75 + 2.0)) < 1e-6, plan["audio_time_base_s"])
check("V1b declared 仅出现在 planning_drift 且**不阻断**",
      plan["planning_drift"]["declared_total_s"] == 95.0
      and plan["planning_drift"]["planned_time_base_s"] == 97.0
      and plan["planning_drift"]["blocking"] is False
      and plan["planning_drift"]["code"] == "PLANNING_DRIFT", plan["planning_drift"])
check("V1c 段级 drift 记录（declared−actual）",
      plan["planning_drift"]["per_segment"][0]["delta_s"] == 10.0)

print("\n== V2 actual > declared（不得因 actual 更长而阻断合法音频）==")
sc2, vo2 = script_of([20, 20]), voice_of([30.0, 30.0])
plan2 = N.narration_plan(sc2, vo2)
check("V2a audio_time_base 随 actual 变长且 complete",
      abs(plan2["audio_time_base_s"] - 62.75) < 1e-6 and plan2["complete"] is True,
      plan2["audio_time_base_s"])
check("V2b planning_drift 为负（actual 更长）仍不阻断",
      plan2["planning_drift"]["delta_s"] == -20.0 and plan2["planning_drift"]["blocking"] is False)

print("\n== V3 多段累计 drift ==")
sc3 = script_of([40, 50, 80, 75, 55])
vo3 = voice_of([30.1, 40.66, 57.72, 50.30, 39.34])
cd = N.cumulative_drift(sc3, vo3)
check("V3a 逐段累计漂移单调增长",
      cd["rows"][0]["drift_s"] == 0.0 and cd["rows"][-1]["drift_s"] > 60.0, cd["rows"])
check("V3b 最大累计漂移 == 末端（全段齐备）",
      abs(cd["max_abs_drift_s"] - abs(cd["final_drift_s"])) < 1e-6, cd)

print("\n== V4 zero / invalid TTS duration ⇒ fail-closed ==")
sc4 = script_of([10, 10, 10])
vo4 = voice_of([10.0, 10.0, 10.0])
vo4["segments"][1]["duration_s"] = 0.0
vo4["segments"][2]["status"] = "FAILED"
durs = N.actual_segment_durations(vo4)
check("V4a 非法段被记为 None（不猜、不用 declared 顶替）",
      durs == [10.0, None, None], durs)
check("V4b audio_time_base 不可计算 ⇒ None", N.audio_time_base_s(vo4) is None)
plan4 = N.narration_plan(sc4, vo4)
g4 = core_integrity.segment_alignment_v2(plan4)
check("V4c G-SEG FAIL（缺实际时长 ⇒ 无法建立可信时基）",
      g4["state"] == core_integrity.STATE_FAIL and plan4["complete"] is False, g4)

print("\n== V5 字幕越过 actual audio（v1 分摊 vs v2 实际窗口）==")
seg_payload = [{"narration": "第一段旁白内容比较长需要切分。", "duration_s": 60.0},
               {"narration": "第二段旁白内容也比较长。", "duration_s": 60.0}]
cues_v1 = core_captions.build_cues(seg_payload)                       # 声明时基（120s）
wins = [{"start_s": 0.0, "end_s": 30.0}, {"start_s": 30.75, "end_s": 60.0}]
cues_v2 = core_captions.build_cues(seg_payload, windows=wins)
check("V5a v2 cue 全部落在实际音频窗口内（不越过）",
      all(any(w["start_s"] - 1e-6 <= c["start"] and c["end"] <= w["end_s"] + 1e-6 for w in wins)
          for c in cues_v2), [c for c in cues_v2])
check("V5b v1（声明时基）会越过实际音频 ⇒ 门禁 FAIL",
      max(c["end"] for c in cues_v1) > wins[-1]["end_s"] + 1.0
      and N.subtitle_alignment(cues_v1, plan2)["ok"] is False,
      N.subtitle_alignment(cues_v1, plan2))
check("V5c v2 字幕 ↔ 实际音频对齐 PASS（同一 plan）",
      N.subtitle_alignment(cues_v2, plan2)["ok"] is True,
      N.subtitle_alignment(cues_v2, plan2))

print("\n== V6 narration padding > pause budget ==")
plan6 = N.narration_plan(sc2, vo2)
_budget6 = plan6["padding_policy"]["apad_allowed_s"]
check("V6a 预算内通过（= 该 plan 的授权预算）",
      N.check_narration_padding(_budget6, plan6)["ok"] is True,
      {"budget": _budget6, "check": N.check_narration_padding(_budget6, plan6)})
big = N.check_narration_padding(568.344, plan6)
check("V6b 超预算（旧 apad 掩盖短缺）⇒ fail-closed", big["ok"] is False
      and big["code"] == "NARRATION_PADDING_EXCEEDS_BUDGET", big)

print("\n== V7 final tail silence ⇒ PI-3 FAIL + promote 阻断 ==")
WORK.mkdir(parents=True, exist_ok=True)
clip = WORK / "silence_tail.mp4"
subprocess.run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
                "color=c=black:s=320x180:d=12:r=25", "-f", "lavfi", "-i",
                "sine=frequency=440:duration=3", "-af", "apad=whole_dur=12", "-shortest",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(clip)],
               capture_output=True, text=True, encoding="utf-8", errors="replace")
post = core_integrity.post_render_gate(str(clip), 12.0, cues_v2, 3.0, True, FFMPEG, FFPROBE,
                                       core_integrity.gate_policy(CFG))
check("V7a PI-3 失败（尾部静音 > 5s）", post["metrics"]["PI-3"]["state"] == "FAIL",
      post["metrics"]["PI-3"])
check("V7b promote 被阻断（不允许用'文件长度正确'掩盖旁白缺口）",
      post.get("promote_blocked") is True
      and any("PROMOTE_BLOCKED" in r for r in post["reasons"]), post["reasons"][:2])

print("\n== V8 timeline/audio mismatch ==")
tl_bad = N.timeline_audio_consistency(1532.0, plan2)
check("V8a 不一致 ⇒ FAIL（G-TL）", tl_bad["ok"] is False
      and tl_bad["code"] == "TIMELINE_AUDIO_MISMATCH", tl_bad)
tl_ok = N.timeline_audio_consistency(plan2["audio_time_base_s"], plan2)
check("V8b 一致 ⇒ PASS", tl_ok["ok"] is True, tl_ok)
gate_bad = core_integrity.pre_render_gate(sc2["segments"], vo2, 1532.0,
                                          core_integrity.gate_policy(CFG),
                                          narration_duration_s=vo2["narration_duration_s"],
                                          narration_plan=plan2, cues=cues_v2,
                                          narration_padding_s=0.0)
check("V8c 预渲染门禁被 G-TL/PI-1/PI-2 阻断", gate_bad["blocked"] is True,
      gate_bad["reasons"][:3])

print("\n== V9 旧 apad 掩盖路径（真实 v9 数据回放：declared 1530 vs actual 961.656）==")
_audit = json.loads((ROOT / "docs" / "regression_2x" / "logs" /
                      "phase6e_duration_contract_audit.json").read_text(encoding="utf-8"))
v9_declared = [r["declared_duration_s"] for r in _audit["audit_table_21_segments"]]
v9_actual = [r["actual_tts_duration_s"] for r in _audit["audit_table_21_segments"]]
sc9, vo9 = script_of(v9_declared), voice_of(v9_actual, track=961.656)
plan9 = N.narration_plan(sc9, vo9)
check("V9a v9 实际数据：declared 1532.0 / actual 961.656（复现审计结论）",
      plan9["declared_time_base_s"] == 1532.0
      and abs(plan9["actual_total_narration_s"] - 961.656) < 0.05,
      {"declared": plan9["declared_time_base_s"], "actual": plan9["actual_total_narration_s"]})
check("V9b v2 权威 = Σactual + 20×0.75 + 2（≈978.7s，不再是 1532s）",
      abs(plan9["audio_time_base_s"] - (961.656 + 15.0 + 2.0)) < 0.05, plan9["audio_time_base_s"])
check("V9c 旧路径若按 declared 铺开 ⇒ 需补 570.3s ⇒ **超出预算，v2 下 fail-closed**",
      N.check_narration_padding(1532.0 - 961.656, plan9)["ok"] is False,
      N.check_narration_padding(1532.0 - 961.656, plan9))
_pd9 = plan9["planning_drift"]
check("V9d planning_drift 如实记录（Σ段差 568.344s；含收尾的时基差 570.344s）且不阻断",
      abs(_pd9["delta_s"] - 568.344) < 0.05
      and abs(_pd9["planned_time_base_s"] - 1532.0) < 0.05
      and abs(plan9["audio_time_base_s"]
              - (plan9["actual_total_narration_s"] + 15.0 + 2.0)) < 0.05
      and _pd9["blocking"] is False
      and abs(_pd9["planning_drift_delta_vs_timeline_s"] - 570.344) < 0.05
      if "planning_drift_delta_vs_timeline_s" in _pd9 else
      abs(_pd9["delta_s"] - 568.344) < 0.05 and _pd9["blocking"] is False,
      _pd9)
cues9_v2 = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s["duration_s"]} for s in sc9["segments"]],
    windows=plan9["segments"])
check("V9e v2 字幕不越过 actual narration（v1 会铺到 1528.6s）",
      max(c["end"] for c in cues9_v2) <= plan9["segments"][-1]["end_s"] + 1e-6
      and N.subtitle_alignment(cues9_v2, plan9)["ok"] is True,
      {"v2_last_cue_end": max(c["end"] for c in cues9_v2),
       "actual_end": plan9["segments"][-1]["end_s"]})

print("\n== 门禁接线（pre-render v2 全绿场景）==")
cues_ok = core_captions.build_cues(
    [{"narration": s["narration"], "duration_s": s["duration_s"]} for s in sc2["segments"]],
    windows=plan2["segments"])
gate_ok = core_integrity.pre_render_gate(
    sc2["segments"], vo2, plan2["audio_time_base_s"], core_integrity.gate_policy(CFG),
    narration_duration_s=vo2["narration_duration_s"], narration_plan=plan2, cues=cues_ok,
    narration_padding_s=plan2["audio_time_base_s"] - vo2["narration_duration_s"])
check("G0 v2 正常场景：门禁不阻断，且 G-SEG/G-TL/G-PAD/G-SUB 全部 PASS",
      gate_ok["blocked"] is False
      and all(gate_ok["metrics"][k]["state"] == core_integrity.STATE_PASS
              for k in ("PI-6", "G-TL", "G-PAD", "G-SUB")),
      {"blocked": gate_ok["blocked"], "reasons": gate_ok["reasons"],
       "states": {k: gate_ok["metrics"][k]["state"] for k in ("PI-1", "PI-2", "PI-6",
                                                              "G-TL", "G-PAD", "G-SUB")}})
check("G1 PLANNING_DRIFT 在门禁里存在且永不为 FAIL",
      gate_ok["metrics"]["PLANNING_DRIFT"]["state"] in (core_integrity.STATE_PASS,
                                                        core_integrity.STATE_UNKNOWN)
      and gate_ok["metrics"]["PLANNING_DRIFT"].get("blocking") is False,
      gate_ok["metrics"]["PLANNING_DRIFT"])

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
