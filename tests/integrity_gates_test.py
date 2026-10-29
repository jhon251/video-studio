# -*- coding: utf-8 -*-
"""6-A / M2 单元回归：**Production Integrity 硬门**（PI-1/PI-2/PI-3/PI-5 = hard gate；
PI-4 / PI-6 = 按 6-A 设计稿接入的正式完整性检查）。

覆盖（对应 6-A/M2 授权书要求的反例集）：
  G1 v9 形态**短旁白**（961.656 s / 1532.0 s）→ 渲染前硬门阻断（PI-1/PI-2/PI-6 FAIL）
  G2 **尾部超长静音**（20 s 成片仅 12 s 有声）→ 渲染后硬门阻断（PI-3 FAIL）
  G3 **片中长静音**（40 s 成片中间 12 s 静音）→ 渲染后硬门阻断（PI-3 FAIL）
  G4 **字幕 orphan**（cue 落在旁白结束之后）→ 渲染后硬门阻断（PI-5 FAIL）
  G5 **音视频轨时长不一致**（video 8 s / audio 20 s）→ 渲染后硬门阻断（PI-4 FAIL）
  G6 **正常完整旁白**（20 s/20 s、无静音、字幕对齐、轨道一致）→ 两道门均不阻断（PASS）
  G7 **UNKNOWN / NOT_ASSESSABLE 绝不等于 PASS**：四道 hard gate（PI-1/PI-2/PI-3/PI-5）与 PI-4
      在"无法证明"时 fail-closed 阻断；PI-6（正式完整性检查）明确违约即阻断、"逐段时长缺失"
      只记为 UNKNOWN（不阻断、也绝不记 PASS；旁白覆盖/时长由 PI-1/PI-2 独立把关）
  G8 门限可复算 + 严格只读（同一输入两次判定逐字节一致；成片 sha256 不变、零新增文件）
  G9 端到端**阶段正确性**（EditingAgent 全链路，真实临时项目目录）：
       · 短旁白 → 在调用 ffmpeg 之前阻断：零 artifact、零新增 mp4；
       · 片中长静音（覆盖率/时长/边界全部达标，仅 PI-3 违约）→ 渲染后阻断：
         不写 render_output / attribution（中间 mp4 仅作为证据留在临时目录，**不登记为交付物**）。

边界声明：本套件只验证 M2 已授权的 PI 硬门行为；不涉及 DQ（仍为只读/建议），
不自动换素材/剪辑/修复/重渲染，不修改 5.x Final 与任何历史基线。
全部产物落在系统临时目录，**不写项目目录、不写 DB**。

用法: python tests/integrity_gates_test.py
"""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))
sys.stdout.reconfigure(encoding="utf-8")

from fixtures.build_integrity_fixtures import (make_film,  # noqa: E402
                                               make_track_mismatch, srt_from_cues,
                                               segments)
from video_studio.agents.editing.agent import EditingAgent  # noqa: E402
from video_studio.core import integrity as I  # noqa: E402
from video_studio.core.narration import NarrationIncompleteError  # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FFMPEG = CFG["tools"]["ffmpeg"]["path"]
FFPROBE = CFG["tools"]["ffmpeg"]["ffprobe"]
TRUTH = json.loads((ROOT / "tests" / "fixtures" / "production_integrity_truth_v1.json")
                   .read_text(encoding="utf-8"))
V9M = next(c for c in TRUTH["cases"] if c["id"] == "V9-REAL")["measured"]
GATE_CODE = I.GATE_CODE

PASS, FAIL = [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + str(detail)[:340]))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def stated(rep):
    return {k: v.get("state") for k, v in (rep.get("metrics") or {}).items()}


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError("ffmpeg 失败 rc={}: {}".format(r.returncode, (r.stderr or "")[-300:]))
    return r


def make_gapped_film(out: Path, *, total_s: float, gap_start_s: float, gap_len_s: float) -> Path:
    """生成"中间有一段数字静音"的成片（用于 PI-3 片中长静音反例）。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    g = gap_start_s + gap_len_s
    _run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-t", "{:.3f}".format(total_s), "-i",
          "testsrc=size=320x180:rate=25", "-f", "lavfi", "-t", "{:.3f}".format(total_s), "-i",
          "sine=frequency=440:sample_rate=24000", "-af",
          "volume=enable='between(t,{:.3f},{:.3f})':volume=0".format(gap_start_s, g),
          "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-pix_fmt", "yuv420p",
          "-preset", "ultrafast", "-c:a", "aac", "-shortest", "-t", "{:.3f}".format(total_s),
          str(out)])
    return out


def make_gapped_mp3(out: Path, *, total_s: float, gap_start_s: float, gap_len_s: float) -> Path:
    """生成"旁白音轨时长达标、但中间有一段静音"的旁白（用于端到端 PI-3 反例）。"""
    out.parent.mkdir(parents=True, exist_ok=True)
    g = gap_start_s + gap_len_s
    _run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-t", "{:.3f}".format(total_s), "-i",
          "sine=frequency=440:sample_rate=24000", "-af",
          "volume=enable='between(t,{:.3f},{:.3f})':volume=0".format(gap_start_s, g),
          "-c:a", "libmp3lame", str(out)])
    return out


TMP = Path(tempfile.mkdtemp(prefix="vs_m2_gates_"))
print("临时目录:", TMP)

# ============================================================================
# G1 —— v9 形态短旁白：渲染前硬门阻断（真实 v9 数值，非合成）
# ============================================================================
V9_SCRIPT = [{"duration_s": d} for d in V9M["script_durs"]]
V9_VOICE = {"complete": True, "narration_duration_s": V9M["narration_duration_s"],
            "segment_details": [{"duration_s": d} for d in V9M["voice_durs"]]}
pre_v9 = I.pre_render_gate(V9_SCRIPT, V9_VOICE, V9M["timeline_duration_s"], I.gate_policy(None),
                           narration_duration_s=V9M["narration_duration_s"])
check("G1a v9 短旁白 → 渲染前硬门阻断", pre_v9["blocked"] is True, pre_v9.get("reasons"))
check("G1b 阻断原因同时含 PI-1（覆盖率 0.6277）与 PI-2（双侧违约）",
      any("PI-1" in r for r in pre_v9["reasons"]) and any("PI-2" in r for r in pre_v9["reasons"]),
      pre_v9["reasons"])
check("G1c PI-6 复核真实漂移 ≈552.2 s → FAIL（真值集为 1 位小数表，容差 ±0.1 s；"
      "3 位小数原始值给出 552.16）",
      pre_v9["metrics"]["PI-6"]["state"] == "FAIL"
      and abs(pre_v9["metrics"]["PI-6"]["max_abs_drift_s"] - 552.16) < 0.1,
      pre_v9["metrics"]["PI-6"])
check("G1d 阻断消息带统一门禁码 {}".format(GATE_CODE),
      pre_v9["message"].startswith(GATE_CODE), pre_v9["message"][:80])

# 反向对照：时长一致（1532.0/1532.0）时同一门**不**阻断（不是"一律阻断"）
V9_VOICE_OK = {"complete": True, "narration_duration_s": V9M["timeline_duration_s"],
               "segment_details": [{"duration_s": d} for d in V9M["script_durs"]]}
pre_v9_ok = I.pre_render_gate(V9_SCRIPT, V9_VOICE_OK, V9M["timeline_duration_s"],
                              I.gate_policy(None),
                              narration_duration_s=V9M["timeline_duration_s"])
check("G1e 反向对照：v9 时长规模下时长一致 → 不阻断（PI-1/PI-2/PI-6 全 PASS）",
      pre_v9_ok["blocked"] is False
      and stated(pre_v9_ok) == {"PI-1": "PASS", "PI-2": "PASS", "PI-6": "PASS"},
      {"blocked": pre_v9_ok["blocked"], "states": stated(pre_v9_ok), "reasons": pre_v9_ok["reasons"]})

# ============================================================================
# G2 —— 尾部超长静音（20 s 成片仅 12 s 有声）
# ============================================================================
f_tail = make_film(TMP / "tail_silence.mp4", FFMPEG, duration_s=20.0, speech_s=12.0)
cues_ok = [{"start": 0.0, "end": 4.0}, {"start": 4.0, "end": 8.0},
           {"start": 8.0, "end": 12.0}]
post_tail = I.post_render_gate(f_tail, 20.0, cues_ok, 12.0, True, FFMPEG, FFPROBE,
                               I.gate_policy(None))
check("G2a 尾部超长静音 → 渲染后硬门阻断（PI-3 FAIL）",
      post_tail["blocked"] is True and post_tail["metrics"]["PI-3"]["state"] == "FAIL",
      {"states": stated(post_tail), "reasons": post_tail["reasons"]})
check("G2b 尾部静音实测 ≈8 s（> 上限 5 s）且静音占比 > 10%",
      post_tail["metrics"]["PI-3"]["tail_silence_s"] > 5.0
      and post_tail["metrics"]["PI-3"]["silence_ratio"] > 0.10,
      post_tail["metrics"]["PI-3"])

# ============================================================================
# G3 —— 片中长静音（40 s 成片中间 12 s 静音；尾部静音 = 0）
# ============================================================================
f_mid = make_gapped_film(TMP / "mid_silence.mp4", total_s=40.0, gap_start_s=14.0, gap_len_s=12.0)
post_mid = I.post_render_gate(f_mid, 40.0, cues_ok, 14.0, True, FFMPEG, FFPROBE,
                              I.gate_policy(None))
pi3_mid = post_mid["metrics"]["PI-3"]
check("G3a 片中长静音 → 渲染后硬门阻断（PI-3 FAIL）",
      post_mid["blocked"] is True and pi3_mid["state"] == "FAIL", post_mid["reasons"])
check("G3b 最长静音实测 ≈12 s（> 上限 8 s），且**非**尾部静音（尾部 = 0）",
      pi3_mid["longest_silence_s"] > 10.0 and pi3_mid["tail_silence_s"] == 0.0
      and pi3_mid["blocks"] >= 1, pi3_mid)

# ============================================================================
# G4 —— 字幕 orphan（cue 落在旁白结束之后）
# ============================================================================
# 干净成片（20 s 全程有声）：保证本用例里**只有** PI-5 违约，判定归因唯一。
f_clean = make_film(TMP / "clean_20s.mp4", FFMPEG, duration_s=20.0, speech_s=20.0)
orphan_cues = [{"start": float(i), "end": float(i) + 1.0} for i in range(7)]
orphan_cues += [{"start": 12.0 + i, "end": 13.0 + i} for i in range(3)]      # 3/10 落在旁白(11s)之后
post_orph = I.post_render_gate(f_clean, 20.0, orphan_cues, 11.0, True, FFMPEG, FFPROBE,
                               I.gate_policy(None))
check("G4a 字幕 orphan 占比 0.30（> 上限 0.02）→ 渲染后硬门阻断（PI-5 FAIL）",
      post_orph["blocked"] is True and post_orph["metrics"]["PI-5"]["state"] == "FAIL",
      {"states": stated(post_orph), "reasons": post_orph["reasons"]})
check("G4b orphan 计数/首条时刻实测（3 条，首条 12.0 s）",
      post_orph["metrics"]["PI-5"]["orphan_cues"] == 3
      and abs(post_orph["metrics"]["PI-5"]["orphan_first_s"] - 12.0) < 0.01,
      post_orph["metrics"]["PI-5"])
check("G4c narration_expected=False 但旁白结束时刻已知时，PI-5 FAIL 同样阻断",
      I.post_render_gate(f_clean, 20.0, orphan_cues, 11.0, False, FFMPEG, FFPROBE,
                         I.gate_policy(None))["blocked"] is True)
_po = I.post_render_gate(f_clean, 20.0, orphan_cues, None, False, FFMPEG, FFPROBE,
                         I.gate_policy(None))
check("G4e 边界如实标注：无旁白计划模式且旁白结束未知 → PI-5 NOT_ASSESSABLE，本条**不阻断**"
      "（仅记录，不谎报 PASS）",
      _po["blocked"] is False and _po["metrics"]["PI-5"]["state"] == "NOT_ASSESSABLE",
      {"blocked": _po["blocked"], "reasons": _po["reasons"]})
# 真实误伤回归（6-A/M2 实测发现）：本产线字幕按阅读速度给时长、长镜头留白，
# 覆盖比 < 0.60 属正常形态；授权点名的 PI-5 判据是 **orphan**，覆盖比只记录、不阻断。
sparse_cues = [{"start": 0.0, "end": 3.4}, {"start": 6.0, "end": 9.4}, {"start": 12.0, "end": 15.4}]
m_sparse = I.subtitle_orphans(sparse_cues, 20.0, 20.0, I.gate_policy(None))
check("G4f 字幕覆盖比 0.51 < 0.60 → 记 coverage_fail=True / orphan_fail=False（判据分离）",
      m_sparse["coverage_fail"] is True and m_sparse["orphan_fail"] is False
      and m_sparse["coverage_is_blocking"] is False, m_sparse)
_post_sparse = I.post_render_gate(f_clean, 20.0, sparse_cues, 20.0, True, FFMPEG, FFPROBE,
                                  I.gate_policy(None))
check("G4g 仅覆盖比不达标（无 orphan）→ 渲染后**不阻断**，原因里明确写“仅记录不阻断”",
      _post_sparse["blocked"] is False
      and any("仅记录不阻断" in r for r in _post_sparse["reasons"]), _post_sparse["reasons"])
srt = srt_from_cues([(c["start"], c["end"], "x") for c in orphan_cues])
m_orph = I.subtitle_orphans(srt, 11.0, 20.0, I.DEFAULT_POLICY)
check("G4d SRT 文本入参等价（解析后判定一致）",
      m_orph["state"] == "FAIL" and m_orph["orphan_cues"] == 3, m_orph)

# ============================================================================
# G5 —— 音视频轨时长不一致（video 8 s / audio 20 s）
# ============================================================================
f_mm = make_track_mismatch(TMP / "track_mismatch.mp4", FFMPEG, video_s=8.0, audio_s=20.0,
                           speech_s=20.0)
post_mm = I.post_render_gate(f_mm, 20.0, cues_ok, 20.0, True, FFMPEG, FFPROBE,
                             I.gate_policy(None))
pi4_mm = post_mm["metrics"]["PI-4"]
check("G5a 音视频轨时长不一致 → 渲染后硬门阻断（PI-4 FAIL）",
      post_mm["blocked"] is True and pi4_mm["state"] == "FAIL", post_mm["reasons"])
check("G5b 轨道差实测 ≈12 s（> 上限）且视频轨相对时间轴也短 12 s",
      pi4_mm["track_delta_s"] > 10.0 and pi4_mm["video_vs_timeline_s"] > 10.0, pi4_mm)
# 真实误伤回归（6-A/M2 实测发现）：10 s/30 fps 成片 ffprobe 报 `nb_frames=299` 而
# `duration×fps=298.0`（±1 帧报数惯例）——帧数差**不作为违约**，否则会阻断合规成片。
probe_edge = {"has_video": True, "has_audio": True, "video_s": 9.933333, "audio_s": 10.0,
              "video_start": 0.0, "audio_start": 0.0, "frames": 299, "fps": 30.0}
pi4_edge = I.av_track_consistency(probe_edge, 10.0, I.gate_policy(None))
check("G5c 10 s/30 fps 成片的 ±1 帧报数差异 → PI-4 PASS（帧数差仅报告，不阻断）",
      pi4_edge["state"] == "PASS" and abs(pi4_edge["frame_count_delta"] - 1.0) < 0.05
      and pi4_edge["frame_count_is_blocking"] is False, pi4_edge)
check("G5d PI-4 容差与既有冻结契约对齐（1.0 s，而非 M1 advisory 的 0.5 s）",
      I.gate_policy(None)["max_av_track_delta_s"] == 1.0
      and I.gate_policy(None)["max_video_timeline_delta_s"] == 1.0)
pi4_tol = I.av_track_consistency({"has_video": True, "has_audio": True, "video_s": 9.3,
                                  "audio_s": 10.0, "video_start": 0.0, "audio_start": 0.0,
                                  "frames": 279, "fps": 30.0}, 10.0, I.gate_policy(None))
check("G5e 轨差 0.7 s（既有冻结容差 1.0 s 内）→ 不判违约（不收紧既有契约）",
      pi4_tol["state"] == "PASS" and abs(pi4_tol["track_delta_s"] - 0.7) < 0.01, pi4_tol)

# ============================================================================
# G6 —— 正常完整旁白：两道门均不阻断（全部 PASS）
# ============================================================================
f_ok = f_clean                       # 复用上面的干净 20 s 成片（全程有声、轨道一致）
cues_full = [{"start": 0.0, "end": 6.0}, {"start": 6.0, "end": 13.0},
             {"start": 13.0, "end": 20.0}]
segs_ok = segments(4, "完整旁白文案用于正常成片回归验证", 5.0)      # 4 段 × 5 s = 20 s
voice_ok = {"complete": True, "narration_duration_s": 20.0,
            "segment_details": [{"duration_s": 5.0} for _ in range(4)]}
pre_ok = I.pre_render_gate(segs_ok, voice_ok, 20.0, I.gate_policy(None), narration_duration_s=20.0)
post_ok = I.post_render_gate(f_ok, 20.0, cues_full, 20.0, True, FFMPEG, FFPROBE,
                             I.gate_policy(None))
check("G6a 正常完整旁白 → 渲染前硬门不阻断（PI-1/PI-2/PI-6 PASS）",
      pre_ok["blocked"] is False and set(stated(pre_ok).values()) == {"PASS"},
      {"states": stated(pre_ok), "reasons": pre_ok["reasons"]})
check("G6b 正常完整成片 → 渲染后硬门不阻断（PI-3/PI-4/PI-5 PASS）",
      post_ok["blocked"] is False and set(stated(post_ok).values()) == {"PASS"},
      {"states": stated(post_ok), "reasons": post_ok["reasons"]})
check("G6c 正常成片 PI-3 无静音块、PI-4 轨道差 0、PI-5 零 orphan",
      post_ok["metrics"]["PI-3"]["blocks"] == 0
      and post_ok["metrics"]["PI-4"]["track_delta_s"] <= 0.5
      and post_ok["metrics"]["PI-5"]["orphan_cues"] == 0, stated(post_ok))
check("G6d 默认策略即启用硬门（无需额外配置；gate/post_render 默认 True）",
      I.gate_policy(None)["gate_enabled"] is True
      and I.gate_policy({})["post_render_enabled"] is True
      and I.gate_policy({})["block_on_unknown"] is True)
check("G6e config.gates.integrity 覆盖是**加法**的（只改显式给出的键）",
      I.gate_policy({"gates": {"integrity": {"max_tail_silence_s": 9.0}}})["max_tail_silence_s"] == 9.0
      and I.gate_policy({"gates": {"integrity": {"max_tail_silence_s": 9.0}}})["max_silence_block_s"]
      == I.DEFAULT_POLICY["max_silence_block_s"])

# ============================================================================
# G7 —— UNKNOWN / NOT_ASSESSABLE 绝不等于 PASS（硬门 fail-closed；PI-6 为正式检查）
# ============================================================================
pre_unknown = I.pre_render_gate(segs_ok, {"complete": True}, 20.0, I.gate_policy(None),
                                narration_duration_s=None)
check("G7a 旁白时长不可测（PI-1 NOT_ASSESSABLE）→ 渲染前 fail-closed 阻断",
      pre_unknown["blocked"] is True
      and pre_unknown["metrics"]["PI-1"]["state"] == "NOT_ASSESSABLE",
      {"states": stated(pre_unknown), "reasons": pre_unknown["reasons"]})
_reasons = " ".join(pre_unknown["reasons"])
check("G7b 逐段 TTS 时长缺失 → PI-6 如实记 UNKNOWN（绝不记 PASS）并写明不据此阻断",
      pre_unknown["metrics"]["PI-6"]["state"] == "UNKNOWN"
      and "PI-6 UNKNOWN" in _reasons and "仅记录" in _reasons, pre_unknown["reasons"])
# PI-6 = 授权书里的**正式完整性检查**（不在四道 hard gate 清单内）：
# 不可评估 → 只记录（状态仍为 UNKNOWN，绝不伪造 PASS）；明确违约 → 阻断。
pre_pi6_unknown = I.pre_render_gate(segs_ok, {"complete": True}, 20.0, I.gate_policy(None),
                                    narration_duration_s=20.0)
check("G7b2 PI-6 单独不可评估（PI-1/PI-2 PASS）→ 不阻断，但状态必须是 UNKNOWN（非 PASS）",
      pre_pi6_unknown["blocked"] is False
      and stated(pre_pi6_unknown) == {"PI-1": "PASS", "PI-2": "PASS", "PI-6": "UNKNOWN"},
      {"blocked": pre_pi6_unknown["blocked"], "states": stated(pre_pi6_unknown)})
seg_bad = [{"duration_s": 10.0} for _ in range(4)]
voice_bad = {"complete": True, "segment_details": [{"duration_s": 0.5} for _ in range(4)]}
pre_pi6_fail = I.pre_render_gate(seg_bad, voice_bad, 20.0, I.gate_policy(None),
                                 narration_duration_s=20.0)
check("G7b3 PI-6 明确违约（最大漂移 38.0 s > 5 s）→ 仍**阻断**（正式检查，不是 advisory）",
      pre_pi6_fail["blocked"] is True and stated(pre_pi6_fail)["PI-6"] == "FAIL",
      {"states": stated(pre_pi6_fail), "reasons": pre_pi6_fail["reasons"]})
check("G7b4 PI-6 可显式收紧为 fail-closed（block_on_unknown_pi6=True；默认 False）",
      I.gate_policy(None)["block_on_unknown_pi6"] is False
      and I.pre_render_gate(segs_ok, {"complete": True}, 20.0,
                            I.gate_policy({"gates": {"integrity":
                                                     {"block_on_unknown_pi6": True}}}),
                            narration_duration_s=20.0)["blocked"] is True)
post_missing = I.post_render_gate(TMP / "not_exist.mp4", 20.0, cues_full, 20.0, True,
                                  FFMPEG, FFPROBE, I.gate_policy(None))
check("G7c 成片不存在（PI-3 NOT_ASSESSABLE）→ 渲染后 fail-closed 阻断",
      post_missing["blocked"] is True
      and post_missing["metrics"]["PI-3"]["state"] == "NOT_ASSESSABLE", post_missing["reasons"])
post_nocue = I.post_render_gate(f_ok, 20.0, [], 20.0, True, FFMPEG, FFPROBE, I.gate_policy(None))
check("G7d 无字幕 cue（PI-5 NOT_ASSESSABLE，且 narration_expected=True）→ 阻断",
      post_nocue["blocked"] is True
      and post_nocue["metrics"]["PI-5"]["state"] == "NOT_ASSESSABLE", post_nocue["reasons"])
summ = I.summarize({"PI-1": {"state": "PASS"}, "PI-3": {"state": "UNKNOWN"},
                    "PI-5": {"state": "NOT_ASSESSABLE"}})
check("G7e summarize：含 UNKNOWN → overall=UNKNOWN（不折成 PASS）",
      summ["overall"] == "UNKNOWN" and summ["unknown_is_not_pass"] is True, summ)
check("G7f 显式关闭硬门时才不阻断（默认开启；关闭须显式配置，属可审计配置面）",
      I.gate_policy({"gates": {"integrity": {"enabled": False}}})["gate_enabled"] is False
      and I.pre_render_gate(segs_ok, {"complete": True}, 20.0,
                            I.gate_policy({"gates": {"integrity": {"enabled": False}}}),
                            narration_duration_s=None)["blocked"] is False)

# ============================================================================
# G8 —— 可复算 + 严格只读（成片 sha256 不变、零新增文件）
# ============================================================================
before_files = {p.name: p.stat().st_size for p in sorted(TMP.glob("*.mp4"))}
film_sha_before = sha(f_ok)
rep1 = I.post_render_gate(f_ok, 20.0, cues_full, 20.0, True, FFMPEG, FFPROBE, I.gate_policy(None))
rep2 = I.post_render_gate(f_ok, 20.0, cues_full, 20.0, True, FFMPEG, FFPROBE, I.gate_policy(None))
check("G8a 同一输入两次判定逐字节一致（可复算）",
      json.dumps(rep1, sort_keys=True, ensure_ascii=False)
      == json.dumps(rep2, sort_keys=True, ensure_ascii=False))
check("G8b 门禁判定不改写成片（sha256 不变）", sha(f_ok) == film_sha_before)
after_files = {p.name: p.stat().st_size for p in sorted(TMP.glob("*.mp4"))}
check("G8c 门禁调用零新增媒体文件", before_files == after_files,
      {"before": sorted(before_files), "after": sorted(after_files)})
check("G8d 所有度量/门禁输出均带只读标记（read_only=True / enforced=False）",
      all(v.get("read_only") is True and v.get("enforced") is False
          for v in rep1["metrics"].values())
      and rep1["read_only"] is True and pre_ok["read_only"] is True)

# ============================================================================
# G9 —— 端到端阶段正确性（EditingAgent 全链路，真实渲染，临时项目目录）
# ============================================================================
CFG_TEST = {"tools": {"tts": {"provider": "edge-tts", "voice_type": "zh-CN-XiaoxiaoNeural"},
                      "ffmpeg": {"path": str(ROOT / "bin" / "ffmpeg.exe"),
                                 "ffprobe": str(ROOT / "bin" / "ffprobe.exe")}},
            "retry": {"default_max_retries": 2, "backoff_base_s": 0.01}}
# 旁白文案加长到"字幕显示时长 ≥ 60% 旁白时长"（真实成片的正常情形；8 字 → 17 字/段）
SCRIPT_M2 = {"segments": [
    {"chapter": "A", "narration": "第一段旁白内容需要完整说明本段的要点", "duration_s": 3},
    {"chapter": "B", "narration": "第二段旁白内容需要完整说明本段的要点", "duration_s": 3},
    {"chapter": "C", "narration": "第三段旁白内容需要完整说明本段的要点", "duration_s": 3},
]}


class _FakeDB:
    def __init__(self, tasks, arts):
        self.tasks = tasks
        self.arts = arts

    def get_task(self, tid):
        return self.tasks.get(tid)

    def get_artifact(self, aid):
        return self.arts.get(aid)

    def update_task(self, tid, **kw):
        self.tasks.setdefault(tid, {}).update(kw)

    def set_task_status(self, tid, status, note=""):
        self.tasks.setdefault(tid, {}).update({"status": status, "note": note})


class _FakeEngine:
    def __init__(self, work: Path):
        self.work = work
        self.db = _FakeDB({"t_script": {"task_id": "t_script", "artifacts": ["a_script"],
                                        "dependencies": []},
                           "t_voice": {"task_id": "t_voice", "artifacts": ["a_voice"],
                                       "dependencies": ["t_script"]},
                           "t_render": {"task_id": "t_render", "artifacts": [],
                                        "dependencies": ["t_voice"]}}, {})
        self.config = CFG_TEST
        self.written, self.events = [], []

    def project_dir(self, pid):
        return self.work

    def write_artifact(self, project_id, task_id, type_, content, summary="", version=1,
                       license_=None):
        aid = "a_test_{}".format(len(self.written) + 1)
        p = self.work / "artifacts" / "{}.json".format(aid)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(content, ensure_ascii=False, indent=1), encoding="utf-8")
        self.db.arts[aid] = {"artifact_id": aid, "type": type_, "path": str(p),
                             "summary": summary}
        self.written.append({"id": aid, "type": type_, "content": content, "path": str(p)})
        return aid

    def attach_artifact(self, task_id, artifact_id):
        self.db.tasks.setdefault(task_id, {}).setdefault("artifacts", []).append(artifact_id)

    def emit(self, project_id, type_, actor, task_id=None, payload=None, human_visible=False):
        self.events.append({"type": type_, "task": task_id, "payload": payload})


def _case(name: str, script_obj, voice_obj):
    work = TMP / name
    (work / "media" / "voice").mkdir(parents=True, exist_ok=True)
    (work / "artifacts").mkdir(parents=True, exist_ok=True)
    (work / "output").mkdir(parents=True, exist_ok=True)
    (work / "artifacts" / "script.json").write_text(json.dumps(script_obj, ensure_ascii=False),
                                                   encoding="utf-8")
    vp = work / "artifacts" / "voice.json"
    vp.write_text(json.dumps(voice_obj, ensure_ascii=False), encoding="utf-8")
    eng = _FakeEngine(work)
    eng.db.arts["a_script"] = {"artifact_id": "a_script", "type": "script_output",
                              "path": str(work / "artifacts" / "script.json")}
    eng.db.arts["a_voice"] = {"artifact_id": "a_voice", "type": "voice_output", "path": str(vp)}
    return eng, work


def _render_task():
    return {"task_id": "t_render", "project_id": "p_test", "task_type": "render",
            "dependencies": ["t_voice"], "inputs": {}}


def _mk_mp3(path: Path, seconds: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    _run([FFMPEG, "-y", "-v", "error", "-f", "lavfi", "-i",
          "sine=frequency=440:duration={:.3f}".format(seconds), "-c:a", "libmp3lame", str(path)])


_SEGS_DETAIL = [{"index": i, "audio": "media/voice/seg_{:02d}.mp3".format(i),
                 "status": "SUCCESS", "reused": False, "attempts": 1, "bytes": 1000,
                 "duration_s": 3.0, "text_sha256": "z"} for i in range(3)]

# ---- G9a 短旁白（9 s 旁白 / 11 s 时间轴）→ 必须在 ffmpeg 之前阻断 ----
eng_a, work_a = _case("agent_short", SCRIPT_M2,
                      {"audio": "media/voice/narration.mp3", "complete": True,
                       "status": "COMPLETE", "expected_segments": 3, "successful_segments": 3,
                       "failed_segments": [], "segments": _SEGS_DETAIL,
                       "segment_details": _SEGS_DETAIL})
_mk_mp3(work_a / "media" / "voice" / "narration.mp3", 9.0)
raised_a = None
try:
    EditingAgent().run(eng_a, _render_task())
except NarrationIncompleteError as exc:
    raised_a = exc
check("G9a 短旁白 → 端到端阻断于**渲染前**（PI-1 覆盖率违约）",
      raised_a is not None and "PI-1" in str(raised_a) and "render 前闸门" in str(raised_a),
      raised_a)
check("G9b 阶段证据：零 artifact 落库（render_output/attribution 均不存在）且未新增 mp4",
      not eng_a.written and not list((work_a / "output").glob("*.mp4")),
      {"written": [w["type"] for w in eng_a.written],
       "mp4": [p.name for p in (work_a / "output").glob("*.mp4")]})

# ---- G9c 片中长静音（覆盖/时长/边界全部达标，仅 PI-3 违约）→ 渲染后阻断 ----
segs_gap = [{"index": i, "audio": "media/voice/seg_{:02d}.mp3".format(i), "status": "SUCCESS",
             "reused": False, "attempts": 1, "bytes": 1000, "duration_s": 3.667,
             "text_sha256": "z"} for i in range(3)]
VOICE_GAP = {"audio": "media/voice/narration.mp3", "complete": True,
             "status": "COMPLETE", "expected_segments": 3, "successful_segments": 3,
             "failed_segments": [], "narration_duration_s": 11.0,
             "segments": segs_gap, "segment_details": segs_gap}
eng_c, work_c = _case("agent_mid_silence", SCRIPT_M2, VOICE_GAP)
make_gapped_mp3(work_c / "media" / "voice" / "narration.mp3", total_s=11.0, gap_start_s=4.25,
                gap_len_s=2.5)
raised_c = None
try:
    EditingAgent().run(eng_c, _render_task())
except Exception as exc:                                            # noqa: BLE001
    raised_c = exc
types_c = [w["type"] for w in eng_c.written]
check("G9c 旁白时长/覆盖率全部达标但成片含片中长静音 → 渲染后硬门阻断（{}）".format(GATE_CODE),
      isinstance(raised_c, I.ProductionIntegrityError)
      and getattr(raised_c, "code", None) == GATE_CODE
      and (raised_c.detail or {}).get("stage") == "post_render", raised_c)
_pm = ((raised_c.detail or {}).get("metrics") or {})
_pre_c = I.pre_render_gate(SCRIPT_M2["segments"], VOICE_GAP, 11.0, I.gate_policy(None),
                           narration_duration_s=11.0)
check("G9d 该阻断只由 PI-3 触发（渲染后 PI-4/PI-5 PASS；同输入的渲染前 PI-1/PI-2/PI-6 全 PASS）",
      _pm.get("PI-3", {}).get("state") == "FAIL"
      and all(_pm.get(k, {}).get("state") == "PASS" for k in ("PI-4", "PI-5"))
      and _pre_c["blocked"] is False and set(stated(_pre_c).values()) == {"PASS"},
      {"post": _pm, "pre": stated(_pre_c)})
check("G9e 阶段证据：不登记任何交付物 artifact（render_output/attribution 均未写）",
      "render_output" not in types_c and "attribution" not in types_c, types_c)
check("G9f 阻断事件 human_visible 已发（含统一门禁码）",
      any(e["type"] == "TASK_BLOCKED" and GATE_CODE in json.dumps(e["payload"] or {},
                                                                 ensure_ascii=False)
          for e in eng_c.events))

print("\n结果: {}/{} 通过".format(len(PASS), len(PASS) + len(FAIL)))
if FAIL:
    print("失败项:", FAIL)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if not FAIL else 1)
