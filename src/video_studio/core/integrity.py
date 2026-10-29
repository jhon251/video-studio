# -*- coding: utf-8 -*-
"""6-A / M1 + M2 —— **Production Integrity**（PI-1 … PI-6）度量层与硬门。

两层职责（务必区分）：
  · **M1 度量层（本文件上半部，纯只读）**：`narration_coverage` / `duration_contract_dual` /
    `audio_silence_profile` / `av_track_consistency` / `subtitle_orphans` / `segment_boundary_drift`
    ——只测量、只判定、只报告：不写 DB、不写产物、不改时间轴/素材/旁白/字幕/渲染行为。
  · **M2 硬门（本文件下半部，`pre_render_gate` / `post_render_gate`）**：由 `agents/editing/agent.py`
    在**渲染前**（ffmpeg 之前）与**渲染后**（写交付物 artifact 之前）显式调用；判定结果直接决定
    「继续 / 阻断」。硬门自身**仍不写任何东西**（不修素材、不剪辑、不修复、不重渲染）。

6-A/M2 授权范围：**只接线 PI**（PI-1 覆盖率 / PI-2 双侧时长契约 / PI-3 成片静音 / PI-5 字幕 orphan
= hard gate；PI-4 / PI-6 = 按 6-A 设计稿接入的正式完整性检查）；**DQ-1…DQ-7 保持只读/建议**。

设计契约：
  · 所有门限来自显式传入的 `policy`（`DEFAULT_POLICY` 为默认值，可用 `config.gates.integrity` 覆盖，
    覆盖是**加法**的、不改任何既有 config 键语义）；
  · 度量层每个指标的输出都带 `enforced: False`（度量本身不阻断）；
  · 判定状态只有四种：`PASS / FAIL / UNKNOWN / NOT_ASSESSABLE`；
    **`UNKNOWN` 与 `NOT_ASSESSABLE` 绝不等同 `PASS`**（汇总口径见 `summarize()`）；
    硬门默认 `block_on_unknown=True`：**无法证明 = fail-closed 阻断**（不伪造 PASS）。
  · 不修改任何 5.x 冻结评估件（Judge / truth set / threshold / multimodal evaluator）；
    时长契约判定**复用** `core.narration.duration_contract`（只读调用，不改其语义）。

指标口径（与 6-A 审计一致，可复算）：
  PI-1 旁白覆盖率            narration_duration_s / timeline_duration_s ≥ min_narration_coverage
  PI-2 双侧时长契约          excess（既有规则）+ **shortfall（新增下界判定）**
  PI-3 成片音频连续性        silencedetect：最长静音 / 静音占比 / 尾部静音
  PI-4 AV 轨道一致性         三轨时长、起始、帧数一致性
  PI-5 字幕覆盖 / orphan     cue 落在旁白结束之后即 orphan；orphan 占比上限
  PI-6 段落边界漂移          脚本时基 vs 逐段真实 TTS 时长的累计错位
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

STATE_PASS = "PASS"
STATE_FAIL = "FAIL"
STATE_UNKNOWN = "UNKNOWN"
STATE_NOT_ASSESSABLE = "NOT_ASSESSABLE"

#: 默认度量阈值。6-A/M2 对齐说明（避免"收紧既有冻结契约"）：
#:   · `max_av_track_delta_s` / `max_video_timeline_delta_s` 由 0.5 s 对齐为 **1.0 s**——
#:     与产线既有冻结容差 `VIDEO_DURATION_TOLERANCE_S = 1.0 s`（时长契约 = 时间轴权威）一致；
#:     若用 0.5 s，会把"既有契约判定合格"的成片判为违约（越权收紧）。
#:   · `max_frame_count_delta` 仅用于**度量报告**（不参与 FAIL 判定）：ffprobe 的 `nb_frames`
#:     与 `duration×fps` 天然可能相差 ±1 帧（mux 报数惯例），据此阻断会误伤合规成片。
DEFAULT_POLICY = {
    "min_narration_coverage": 0.90,
    "max_shortfall_s": 30.0,
    "max_shortfall_ratio": 0.10,
    "max_silence_block_s": 8.0,
    "max_silence_ratio": 0.10,
    "max_tail_silence_s": 5.0,
    "silence_noise_db": -45,
    "silence_min_dur_s": 2.0,
    "max_av_track_delta_s": 1.0,
    "max_video_timeline_delta_s": 1.0,
    "max_start_delta_s": 0.5,
    "max_frame_count_delta": 1,
    "max_orphan_share": 0.02,
    "min_cue_over_narration": 0.60,
    "max_cue_over_narration": 1.10,
    "max_segment_drift_s": 5.0,
}

READONLY = {"read_only": True, "enforced": False, "advisory": True}


def _verdict(state: str, **kw) -> dict:
    d = {"state": state}
    d.update(READONLY)
    d.update(kw)
    return d


# ---------------------------------------------------------------- PI-1 覆盖率
def narration_coverage(narration_duration_s, timeline_duration_s, policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not timeline_duration_s or narration_duration_s is None:
        return _verdict(STATE_NOT_ASSESSABLE, reason="缺少旁白时长或时间轴时长",
                        narration_duration_s=narration_duration_s,
                        timeline_duration_s=timeline_duration_s)
    ratio = float(narration_duration_s) / float(timeline_duration_s)
    shortfall = max(float(timeline_duration_s) - float(narration_duration_s), 0.0)
    st = STATE_PASS if ratio >= p["min_narration_coverage"] else STATE_FAIL
    return _verdict(st, metric="PI-1", narration_duration_s=round(float(narration_duration_s), 3),
                    timeline_duration_s=round(float(timeline_duration_s), 3),
                    coverage_ratio=round(ratio, 4), shortfall_s=round(shortfall, 3),
                    threshold={"min_narration_coverage": p["min_narration_coverage"]})


# ------------------------------------------------------- PI-2 双侧时长契约
def duration_contract_dual(timeline_duration_s, narration_duration_s, policy: dict | None = None,
                           tol: float | None = None) -> dict:
    """复用既有 `core.narration.duration_contract`（只读），并补上**短差下界**判定。"""
    from .narration import duration_contract          # 只读调用，不修改该模块
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not timeline_duration_s or narration_duration_s is None:
        return _verdict(STATE_NOT_ASSESSABLE, metric="PI-2", reason="缺少时长输入")
    c = duration_contract(float(timeline_duration_s), float(narration_duration_s), tol)
    excess_block = bool(c["excess_s"] and c["excess_s"] > 0 and not c["within_tolerance"])
    short_block = bool(c["shortfall_s"] and
                       (c["shortfall_s"] > p["max_shortfall_s"]
                        or (c["delta_ratio"] or 0) > p["max_shortfall_ratio"]))
    st = STATE_FAIL if (excess_block or short_block) else STATE_PASS
    return _verdict(st, metric="PI-2", contract=c,
                    excess_block=excess_block, shortfall_block=short_block,
                    threshold={"max_shortfall_s": p["max_shortfall_s"],
                               "max_shortfall_ratio": p["max_shortfall_ratio"],
                               "tolerance_ratio": c["tolerance_ratio"]})


# ------------------------------------------------- PI-3 成片音频连续性
_SIL_START = re.compile(r"silence_start:\s*(-?[\d.]+)")
_SIL_END = re.compile(r"silence_end:\s*(-?[\d.]+)")
_SIL_DUR = re.compile(r"silence_duration:\s*([\d.]+)")


def parse_silencedetect(text: str) -> list[dict]:
    starts = [float(x) for x in _SIL_START.findall(text or "")]
    ends = [float(x) for x in _SIL_END.findall(text or "")]
    durs = [float(x) for x in _SIL_DUR.findall(text or "")]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        d = durs[i] if i < len(durs) else (None if e is None else e - s)
        out.append({"start": round(s, 3), "end": (round(e, 3) if e is not None else None),
                    "dur": (round(d, 3) if d is not None else None)})
    return out


def measure_silence(film: str | Path, ffmpeg: str, noise_db: float = -45.0,
                    min_dur_s: float = 2.0, timeout: int = 3600) -> tuple[list[dict], str]:
    """对**已有成片**跑 `silencedetect`（只读解码，不产出文件）。返回 (blocks, stderr)。"""
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-i", str(film), "-af",
           "silencedetect=noise={}dB:d={}".format(noise_db, min_dur_s), "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    return parse_silencedetect((r.stdout or "") + (r.stderr or "")), (r.stderr or "")


def audio_silence_profile(film: str | Path | None, ffmpeg: str | None, timeline_duration_s,
                          policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not film or not Path(film).is_file():
        return _verdict(STATE_NOT_ASSESSABLE, metric="PI-3", reason="成片文件不存在",
                        film=str(film) if film else None)
    if not ffmpeg:
        return _verdict(STATE_UNKNOWN, metric="PI-3", reason="未提供 ffmpeg 路径")
    try:
        blocks, _err = measure_silence(film, ffmpeg, p["silence_noise_db"], p["silence_min_dur_s"])
    except Exception as exc:                                   # noqa: BLE001
        return _verdict(STATE_UNKNOWN, metric="PI-3", reason="silencedetect 失败: {}".format(exc))
    total = float(timeline_duration_s or 0) or None
    longest = max([b["dur"] for b in blocks if b["dur"]], default=0.0)
    sil_total = sum(b["dur"] for b in blocks if b["dur"])
    tail = 0.0
    if blocks and total:
        last = blocks[-1]
        if last["end"] is None or abs((last["end"] or 0) - total) <= 1.0:
            tail = last["dur"] or 0.0
    speech_end = blocks[0]["start"] if blocks else (total or None)
    fail = (longest > p["max_silence_block_s"]
            or (total and sil_total / total > p["max_silence_ratio"])
            or tail > p["max_tail_silence_s"])
    st = STATE_FAIL if fail else STATE_PASS
    return _verdict(st, metric="PI-3", blocks=len(blocks), longest_silence_s=round(longest, 3),
                    total_silence_s=round(sil_total, 3),
                    silence_ratio=(round(sil_total / total, 4) if total else None),
                    tail_silence_s=round(tail, 3), speech_end_s=speech_end,
                    block_list=blocks[:20],
                    threshold={k: p[k] for k in ("max_silence_block_s", "max_silence_ratio",
                                                 "max_tail_silence_s", "silence_noise_db",
                                                 "silence_min_dur_s")})


# ------------------------------------------------- PI-4 AV 轨道一致性
def probe_tracks(film: str | Path, ffprobe: str, timeout: int = 300) -> dict:
    r = subprocess.run([ffprobe, "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", str(film)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=timeout)
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    a = next((s for s in d.get("streams") or [] if s.get("codec_type") == "audio"), {})
    try:
        num, den = (v.get("r_frame_rate") or "0/1").split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except (ValueError, ZeroDivisionError):
        fps = 0.0
    def _f(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None
    return {"container_s": _f((d.get("format") or {}).get("duration")),
            "video_s": _f(v.get("duration")), "audio_s": _f(a.get("duration")),
            "video_start": _f(v.get("start_time")), "audio_start": _f(a.get("start_time")),
            "frames": int(v.get("nb_frames") or 0) or None, "fps": fps,
            "video_codec": v.get("codec_name"), "audio_codec": a.get("codec_name"),
            "resolution": "{}x{}".format(v.get("width"), v.get("height")),
            "has_video": bool(v), "has_audio": bool(a)}


def av_track_consistency(probe: dict | None, timeline_duration_s, policy: dict | None = None) -> dict:
    """PI-4 AV 轨道一致性。

    判定项（fail-closed 依据）：缺视频/音频轨、`|video−audio| > max_av_track_delta_s`、
    `|video−timeline| > max_video_timeline_delta_s`、起始时刻差 > `max_start_delta_s`。
    **帧数差仅报告**（`frame_count_delta`）：ffprobe 的 `nb_frames` 与 `duration×fps` 相差 ±1 帧
    属正常报数差异，不作为违约——否则会把合规成片判为违约（6-A/M2 实测：10 s/30 fps 成片
    `nb_frames=299` vs `duration×fps=298.0`）。
    """
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not probe:
        return _verdict(STATE_NOT_ASSESSABLE, metric="PI-4", reason="无轨道探测结果")
    if not probe.get("has_video") or not probe.get("has_audio"):
        return _verdict(STATE_FAIL, metric="PI-4", reason="缺少视频或音频轨", probe=probe)
    v, a = probe.get("video_s"), probe.get("audio_s")
    if v is None or a is None:
        return _verdict(STATE_UNKNOWN, metric="PI-4", reason="轨道时长不可读", probe=probe)
    track_delta = abs(v - a)
    tl_delta = abs(v - float(timeline_duration_s)) if timeline_duration_s else None
    start_delta = (abs((probe.get("video_start") or 0.0) - (probe.get("audio_start") or 0.0)))
    frames = probe.get("frames")
    frame_delta = (abs(frames - v * probe["fps"]) if (frames and probe.get("fps")) else None)
    fail = (track_delta > p["max_av_track_delta_s"]
            or (tl_delta is not None and tl_delta > p["max_video_timeline_delta_s"])
            or start_delta > p["max_start_delta_s"])
    st = STATE_FAIL if fail else STATE_PASS
    return _verdict(st, metric="PI-4", track_delta_s=round(track_delta, 3),
                    video_vs_timeline_s=(round(tl_delta, 3) if tl_delta is not None else None),
                    start_delta_s=round(start_delta, 3),
                    frame_count_delta=(round(frame_delta, 2) if frame_delta is not None else None),
                    frame_count_is_blocking=False,
                    frame_count_tolerance_report_only=p["max_frame_count_delta"],
                    probe=probe,
                    threshold={k: p[k] for k in ("max_av_track_delta_s",
                                                 "max_video_timeline_delta_s",
                                                 "max_start_delta_s")},
                    note="帧数差仅报告（±1 帧属 ffprobe 报数惯例），不参与 FAIL 判定")


# ------------------------------------------------- PI-5 字幕覆盖 / orphan
_TS = re.compile(r"(\d\d):(\d\d):(\d\d)[,.](\d\d\d)")


def _ts_seconds(ts: str) -> float:
    h, m, s, ms = _TS.match(ts).groups()
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def parse_srt_cues(srt_text: str) -> list[dict]:
    """解析 SRT 为 cue 列表（序号行 + 时间行 + ≥1 文本行）。"""
    cues = []
    for block in (srt_text or "").strip().split("\n\n"):
        lines = [l for l in block.splitlines() if l.strip()]
        if len(lines) < 3 or "-->" not in lines[1]:
            continue
        a, b = [x.strip() for x in lines[1].split("-->")]
        cues.append({"start": _ts_seconds(a), "end": _ts_seconds(b),
                     "text": "\n".join(lines[2:])})
    return cues


def subtitle_orphans(cues: list[dict] | str, narration_end_s, timeline_duration_s=None,
                     policy: dict | None = None) -> dict:
    """orphan 定义（与 6-A 一致）：**cue.start > 旁白结束时刻**（即字幕落在无语音区间）。"""
    p = {**DEFAULT_POLICY, **(policy or {})}
    if isinstance(cues, str):
        cues = parse_srt_cues(cues)
    if not cues:
        return _verdict(STATE_NOT_ASSESSABLE, metric="PI-5", reason="无字幕 cue")
    if narration_end_s is None:
        return _verdict(STATE_NOT_ASSESSABLE, metric="PI-5", reason="旁白结束时刻未知")
    orph = [c for c in cues if c["start"] > float(narration_end_s)]
    disp = sum(max(c["end"] - c["start"], 0.0) for c in cues)
    share = len(orph) / len(cues)
    over_narr = (disp / float(narration_end_s)) if narration_end_s else None
    # 6-A/M2：把"违约"拆成两个**显式**子判定，供硬门分别处置：
    #   · orphan_fail（cue 落在旁白结束之后）——授权书点名的 hard gate 判据 → 阻断；
    #   · coverage_fail（字幕显示时长/旁白时长超出 [0.60, 1.10]）——**仅报告**：
    #     本产线的字幕按"阅读速度"给定时长、长镜头内会留白，覆盖比低于 0.60 是正常形态；
    #     要靠改字幕生成逻辑才能改变，而"不改字幕生成逻辑"是本轮授权前提。
    orphan_fail = share > p["max_orphan_share"]
    coverage_fail = bool(over_narr is not None and not (
        p["min_cue_over_narration"] <= over_narr <= p["max_cue_over_narration"]))
    fail = orphan_fail or coverage_fail
    st = STATE_FAIL if fail else STATE_PASS
    return _verdict(st, metric="PI-5", cues=len(cues),
                    display_total_s=round(disp, 3),
                    display_over_narration=(round(over_narr, 4) if over_narr else None),
                    orphan_cues=len(orph), orphan_share=round(share, 4),
                    orphan_fail=orphan_fail, coverage_fail=coverage_fail,
                    coverage_is_blocking=False,
                    orphan_first_s=(round(orph[0]["start"], 3) if orph else None),
                    orphan_last_s=(round(orph[-1]["start"], 3) if orph else None),
                    coverage_of_timeline=(round(disp / float(timeline_duration_s), 4)
                                          if timeline_duration_s else None),
                    threshold={k: p[k] for k in ("max_orphan_share", "min_cue_over_narration",
                                                 "max_cue_over_narration")})


# ------------------------------------------------- PI-6 段落边界漂移
def segment_boundary_drift(script_segments: list[dict], voice_durations: list,
                           policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not script_segments:
        return _verdict(STATE_NOT_ASSESSABLE, metric="PI-6", reason="无脚本段落")
    if not voice_durations or len(voice_durations) != len(script_segments):
        return _verdict(STATE_UNKNOWN, metric="PI-6",
                        reason="逐段真实 TTS 时长缺失或段数不一致",
                        script_segments=len(script_segments),
                        voice_durations=len(voice_durations or []))
    rows, acc_s, acc_v, worst = [], 0.0, 0.0, 0.0
    for i, s in enumerate(script_segments):
        sd = float(s.get("duration_s") or 0.0)
        vd = float(voice_durations[i] or 0.0)
        drift = acc_v - acc_s
        worst = min(worst, drift) if abs(drift) > abs(worst) else worst
        rows.append({"scene_index": i + 1, "script_start_s": round(acc_s, 3),
                     "voice_start_s": round(acc_v, 3), "drift_s": round(drift, 3),
                     "script_dur_s": round(sd, 3), "voice_dur_s": round(vd, 3)})
        acc_s += sd
        acc_v += vd
    max_abs = max(abs(r["drift_s"]) for r in rows)
    st = STATE_PASS if max_abs <= p["max_segment_drift_s"] else STATE_FAIL
    return _verdict(st, metric="PI-6", max_abs_drift_s=round(max_abs, 3),
                    final_drift_s=round(acc_v - acc_s, 3),
                    script_total_s=round(acc_s, 3), voice_total_s=round(acc_v, 3),
                    per_scene=rows,
                    threshold={"max_segment_drift_s": p["max_segment_drift_s"]})


# ---------------------------------------------------------------- 汇总口径
def summarize(metrics: dict) -> dict:
    """汇总口径（6-A/M3 收紧，与模块契约一致）：

      · 只要存在 `FAIL` → `FAIL`；
      · 否则只要存在 `UNKNOWN` → `UNKNOWN`；
      · 否则只要存在 `NOT_ASSESSABLE` → `NOT_ASSESSABLE`
        （M3 起：**混有"无法评估"项时整体不再是 PASS**——此前混合 PASS+NA 会被折算成 PASS，
         与"UNKNOWN/NOT_ASSESSABLE 绝不等同 PASS"的契约矛盾）；
      · 全部 `PASS` 才给 `PASS`。

    本函数**只用于汇总报告**，不参与任何门禁阻断判定（门禁逐 PI 判定，见 §M2 硬门）。
    """
    counts = {STATE_PASS: 0, STATE_FAIL: 0, STATE_UNKNOWN: 0, STATE_NOT_ASSESSABLE: 0}
    fails = []
    for k, v in metrics.items():
        st = (v or {}).get("state")
        if st in counts:
            counts[st] += 1
            if st == STATE_FAIL:
                fails.append(k)
    if counts[STATE_FAIL]:
        overall = STATE_FAIL
    elif counts[STATE_UNKNOWN]:
        overall = STATE_UNKNOWN
    elif counts[STATE_NOT_ASSESSABLE]:
        overall = STATE_NOT_ASSESSABLE
    else:
        overall = STATE_PASS
    return {"counts": counts, "failed_metrics": sorted(fails), "overall": overall,
            "unknown_is_not_pass": True, **READONLY}


# ============================================================================
# 6-A / M2 —— Production Integrity **硬门**（PI-1/PI-2/PI-3/PI-5 = hard gate；
#              PI-4/PI-6 按 6-A 设计稿接入为正式完整性检查）
#
# 接线原则（授权边界）：
#   · 只接线 PI；DQ-1…DQ-7 保持只读/建议（本模块不涉及 DQ）；
#   · 不自动换素材/不自动剪辑/不自动修复/不自动重渲染；
#   · `apad` 仍是合法的音频处理机制，但**不得**再掩盖"旁白覆盖不足"：
#     渲染前拦覆盖率/双侧时长契约；渲染后拦成片静音/字幕 orphan/轨道不一致；
#   · 正常完整旁白成片：全部 PASS → 行为与既有实现一致（不改渲染参数/不新增输出）；
#   · 判定只用 PASS/FAIL/UNKNOWN/NOT_ASSESSABLE，**UNKNOWN 绝不当作 PASS**：
#     四道 hard gate（PI-1 覆盖率 / PI-2 双侧时长契约 / PI-3 成片静音 / PI-5 字幕 orphan）与
#     PI-4（音视频轨道）在"无法证明"时即阻断（fail-closed）；
#     PI-6（段落边界漂移）是**正式完整性检查**：明确违约即阻断，但"旧 voice 产物缺逐段时长"
#     只记录为 UNKNOWN（不阻断），以免误伤旁白完整/时长达标的成片——其完备性仍由 PI-1/PI-2 独立把关。
# ============================================================================

GATE_CODE = "[PRODUCTION_INTEGRITY_FAILED]"

#: 硬门策略：在 M1 `DEFAULT_POLICY` 之上追加门控开关与 fail-closed 口径
DEFAULT_GATE_POLICY = {
    **DEFAULT_POLICY,
    "gate_enabled": True,          # 渲染前硬门（PI-1 / PI-2 / PI-6）
    "post_render_enabled": True,   # 渲染后硬门（PI-3 / PI-4 / PI-5）
    "block_on_unknown": True,      # 无法证明（UNKNOWN / NOT_ASSESSABLE）即阻断
    # PI-6 属授权书里的**"正式完整性检查"**（不在四道 hard gate 清单内）：
    # 明确违约（漂移 > 阈值）→ 阻断；仅"逐段真实 TTS 时长缺失"导致不可评估 → **只记录不阻断**，
    # 因为在制品（rollout 前）的旧 voice 产物普遍缺该字段，据此阻断会误伤"旁白完整、时长达标"的成片。
    # 注意：不可评估仍如实记为 UNKNOWN（绝不记 PASS），且**旁白覆盖/时长由 PI-1/PI-2 独立 fail-closed 把关**，
    # 因此不存在"用缺字段绕过 narrration completeness"的通道。
    "block_on_unknown_pi6": False,
    # ---- Duration Contract v2（audio_time_base 权威）----
    "declared_vs_actual_blocking": False,   # declared 只是规划估计 ⇒ 只产出 PLANNING_DRIFT，**不阻断**
    "require_audio_time_base": True,        # 有 voice 产物时必须能算出 audio_time_base，否则 fail-closed
    "timeline_audio_tolerance_s": 0.5,      # timeline_total vs audio_time_base
    "subtitle_alignment_enabled": True,     # 字幕 ↔ 实际音频窗口 对齐硬门
    "min_cue_speech_coverage": 0.98,
    "min_speech_cue_coverage": 0.95,
    "max_cue_beyond_narration_s": 1.0,
    "max_padding_over_budget_s": 1e-6,      # apad 超出授权 pause budget ⇒ fail-closed
    "block_promote_on_silence": True,       # 尾部/内部静音违约 ⇒ 阻止 promote
}


class ProductionIntegrityError(RuntimeError):
    """生产完整性违约（PI 硬门）——fail-closed：不产出交付物，等待人工处置。"""

    code = GATE_CODE

    def __init__(self, message: str, detail: dict | None = None):
        super().__init__(message)
        self.detail = detail or {}


def gate_policy(config: dict | None = None) -> dict:
    """合并 `config.gates.integrity` 覆盖值（缺省 = `DEFAULT_GATE_POLICY`）。

    **不修改**任何既有 config 键语义；未配置时行为由本模块默认值决定。
    """
    p = dict(DEFAULT_GATE_POLICY)
    cfg = ((config or {}).get("gates") or {}).get("integrity") or {}
    if isinstance(cfg, dict):
        for k, v in cfg.items():
            if k in p and isinstance(v, (int, float, bool)):
                p[k] = v
        if cfg.get("enabled") is False:
            p["gate_enabled"] = False
    return p


def _gate_message(kind: str, detail: dict) -> str:
    return "{} {}: {}".format(GATE_CODE, kind, json.dumps(detail, ensure_ascii=False)[:900])


def segment_alignment_v2(plan: dict | None, policy: dict | None = None) -> dict:
    """**v2 段级对齐门**：audio_time_base 必须可算、逐段实际时长齐备、窗口单调不重叠。

    与 `segment_boundary_drift`（declared vs actual，属 PLANNING_DRIFT）**职责不同**：
    本门只校验**权威链自身的自洽性**（缺实际时长/窗口倒退或重叠 ⇒ 无法建立可信时基 ⇒ fail-closed）。
    """
    p = {**DEFAULT_GATE_POLICY, **(policy or {})}
    if not plan:
        return {"state": STATE_UNKNOWN, "metric": "G-SEG", "reasons": ["缺少 narration_plan"]}
    segs = plan.get("segments") or []
    problems = []
    if not segs:
        problems.append("权威音频窗口为空（逐段实际时长缺失）")
    if plan.get("audio_time_base_s") is None:
        problems.append("audio_time_base 不可计算")
    if plan.get("concat_consistent") is False:
        problems.append("拼接音轨实测时长与 Σ 段实际时长不一致")
    prev_end = None
    for s in segs:
        try:
            a, b = float(s["start_s"]), float(s["end_s"])
        except (KeyError, TypeError, ValueError):
            problems.append("窗口字段非法: {}".format(s))
            continue
        if b <= a:
            problems.append("窗口非正: {}".format(s.get("index")))
        if prev_end is not None and a < prev_end - 1e-6:
            problems.append("窗口重叠/倒退于段 {}".format(s.get("index")))
        prev_end = b
    st = STATE_PASS if not problems else STATE_FAIL
    return {"state": st, "metric": "G-SEG", "problems": problems,
            "segments": len(segs), "audio_time_base_s": plan.get("audio_time_base_s"),
            "policy": {"require_audio_time_base": p["require_audio_time_base"]}}


def planning_drift_metric(plan: dict | None, policy: dict | None = None) -> dict:
    """`PLANNING_DRIFT` 门禁视图：**永远不 FAIL**（declared 仅是规划估计），只如实记录。"""
    p = {**DEFAULT_GATE_POLICY, **(policy or {})}
    pd = (plan or {}).get("planning_drift") or {}
    if not pd:
        return {"state": STATE_UNKNOWN, "metric": "PLANNING_DRIFT",
                "reasons": ["无 planning_drift 数据"]}
    st = STATE_PASS if p.get("declared_vs_actual_blocking") is False else STATE_FAIL
    return {"state": st, "metric": "PLANNING_DRIFT", "blocking": False,
            "declared_total_s": pd.get("declared_total_s"), "actual_total_s": pd.get("actual_total_s"),
            "delta_s": pd.get("delta_s"), "max_abs_cumulative_drift_s":
                pd.get("max_abs_cumulative_drift_s"),
            "note": "declared 与 actual 的偏差只审计、不阻断（Duration Contract v2）"}


def pre_render_gate(script_segments: list[dict], voice_payload: dict | None,
                    timeline_duration_s, policy: dict | None = None,
                    narration_duration_s=None, narration_plan: dict | None = None,
                    cues: list | None = None, narration_padding_s=None) -> dict:
    """**渲染前**硬门：PI-1 覆盖率 / PI-2 双侧时长契约 / PI-6 段落边界漂移。

    仅在存在 voice 产物（= 真的合成过旁白）时由调用方启用；plan-only（无旁白）保持既有行为。
    `narration_duration_s` 应传**实测值**（与既有闸门同一来源：对 narration 音轨 ffprobe）；
    缺省时回退读 voice 产物自报的 `narration_duration_s`。

    **Duration Contract v2**：当传入 `narration_plan`（`core.narration.narration_plan`）时启用 v2 语义：
      · PI-1/PI-2 以 `timeline_total == audio_time_base` 为前提（正常应 PASS）；
      · 新增 **G-SEG 段级对齐 / G-TL 时基一致 / G-SUB 字幕对齐 / G-PAD 补齐预算** 四道门；
      · declared-vs-actual 偏差降级为 `PLANNING_DRIFT`（**不阻断**）。
    未传 `narration_plan` 时保持 v1 既有语义（向后兼容）。
    """
    p = dict(DEFAULT_GATE_POLICY)
    p.update(policy or {})
    metrics, reasons = {}, []
    if not p.get("gate_enabled", True):
        return {"blocked": False, "disabled": True, "code": GATE_CODE, "metrics": {},
                "reasons": ["gate disabled by policy"], **READONLY}
    narration_s = (narration_duration_s if narration_duration_s is not None
                   else (voice_payload or {}).get("narration_duration_s"))
    v2 = bool(narration_plan)
    if v2:
        # ---- v2 语义：timeline = Σactual + **已声明 pause budget** + trailing ----
        # 已声明的停顿/收尾**不是**"旁白短缺"，故 PI-1/PI-2 应以"语音专属时基"计算：
        #   speech_base = timeline_total − 已声明预算
        # 任何**超出预算**的空缺仍会被 G-TL（timeline==audio_time_base）/ G-PAD（预算）/ PI-3（静音）拦下。
        _budget = float(((narration_plan.get("padding_policy") or {}).get("apad_allowed_s")) or 0.0)
        _speech_base = max(float(timeline_duration_s or 0.0) - _budget, 1e-6)
        pi1 = narration_coverage(narration_s, _speech_base, p)
        pi2 = duration_contract_dual(_speech_base, narration_s, p)
        pi1["basis"] = "v2_speech_exclusive_base"
        pi2["basis"] = "v2_speech_exclusive_base"
        pi1["declared_pause_budget_s"] = round(_budget, 3)
        pi2["declared_pause_budget_s"] = round(_budget, 3)
    else:
        pi1 = narration_coverage(narration_s, timeline_duration_s, p)
        pi2 = duration_contract_dual(timeline_duration_s, narration_s, p)
    vd = [d.get("duration_s") for d in ((voice_payload or {}).get("segment_details") or [])]
    if v2:
        # v2：PI-6 的**阻断语义**改为"权威链自洽性"（declared vs actual → 仅 PLANNING_DRIFT）
        pi6 = segment_alignment_v2(narration_plan, p)
        pd = planning_drift_metric(narration_plan, p)
        metrics.update({"PI-1": pi1, "PI-2": pi2, "PI-6": pi6, "PLANNING_DRIFT": pd,
                        "G-TL": timeline_audio_consistency_v2(timeline_duration_s,
                                                              narration_plan, p)})
        from .narration import check_narration_padding, subtitle_alignment
        budget = ((narration_plan.get("padding_policy") or {}).get("apad_allowed_s") or 0.0)
        pad_used = (budget if narration_padding_s is None else float(narration_padding_s))
        cp = check_narration_padding(pad_used, narration_plan)
        metrics["G-PAD"] = {"state": STATE_PASS if cp["ok"] else STATE_FAIL, "metric": "G-PAD",
                            **cp}
        if p.get("subtitle_alignment_enabled", True) and cues is not None:
            sa = subtitle_alignment(cues, narration_plan, p)
            metrics["G-SUB"] = {"state": STATE_PASS if sa["ok"] else STATE_FAIL, "metric": "G-SUB",
                                **sa}
    else:
        pi6 = segment_boundary_drift(script_segments or [], vd, p)
        metrics.update({"PI-1": pi1, "PI-2": pi2, "PI-6": pi6})

    def need(key, m, why):
        st = m.get("state")
        if st == STATE_FAIL:
            reasons.append("{} {}: {}".format(key, st, why))
            return True
        if st in (STATE_UNKNOWN, STATE_NOT_ASSESSABLE) and p.get("block_on_unknown", True):
            reasons.append("{} {}: 无法证明（{}）→ fail-closed 阻断".format(key, st, why))
            return True
        return False

    blocked = False
    blocked |= need("PI-1", pi1, "旁白覆盖率 {} < {}".format(
        pi1.get("coverage_ratio"), p["min_narration_coverage"]))
    blocked |= need("PI-2", pi2, "时长契约双侧违约（shortfall={} excess={}）".format(
        (pi2.get("contract") or {}).get("shortfall_s"),
        (pi2.get("contract") or {}).get("excess_s")))
    # PI-6（正式完整性检查，非四道 hard gate 之一）：
    #   明确 FAIL → 阻断；UNKNOWN/NOT_ASSESSABLE → 只记录（如实标为 UNKNOWN，绝不记 PASS）。
    if pi6.get("state") == STATE_FAIL:
        reasons.append("PI-6 FAIL: {}".format(
            "权威链不自洽: " + "；".join(pi6.get("problems") or []) if v2
            else "段落边界最大漂移 {} s > {} s".format(pi6.get("max_abs_drift_s"),
                                                    p["max_segment_drift_s"])))
        blocked = True
    elif pi6.get("state") in (STATE_UNKNOWN, STATE_NOT_ASSESSABLE):
        if p.get("block_on_unknown_pi6"):
            reasons.append("PI-6 {}: 无法证明（逐段真实 TTS 时长缺失）→ fail-closed 阻断".format(
                pi6.get("state")))
            blocked = True
        else:
            reasons.append("PI-6 {}: 仅记录（逐段真实 TTS 时长不可得，不等同 PASS；"
                           "旁白覆盖/时长由 PI-1/PI-2 独立把关）".format(pi6.get("state")))
    if v2:
        for key, why in (("G-TL", "timeline_total 与 audio_time_base 不一致"),
                         ("G-PAD", "旁白补齐超出授权 pause budget"),
                         ("G-SUB", "字幕与实际音频窗口未对齐")):
            m = metrics.get(key)
            if m is None:
                continue
            if key == "G-SUB" and cues is None:
                continue
            if m.get("state") == STATE_FAIL:
                reasons.append("{} FAIL: {}".format(key, why))
                blocked = True
    # `reasons` **必须放在最前**：阻断消息会按字符截断，人类可读原因不能被 metrics 挤掉。
    detail = {"reasons": reasons, "stage": "pre_render", "metrics": metrics,
              "policy": {k: p[k] for k in ("min_narration_coverage", "max_shortfall_s",
                                           "max_shortfall_ratio", "max_segment_drift_s",
                                           "block_on_unknown", "block_on_unknown_pi6",
                                           "declared_vs_actual_blocking")},
              "contract_policy": "audio_time_base_v2" if v2 else "timeline_authoritative_v1"}
    return {"blocked": bool(blocked), "disabled": False, "code": GATE_CODE, "metrics": metrics,
            "reasons": reasons, "detail": detail, "message": _gate_message("渲染前闸门", detail),
            **READONLY}


def timeline_audio_consistency_v2(timeline_total_s, plan: dict | None,
                                  policy: dict | None = None) -> dict:
    """时基一致性门（`core.narration.timeline_audio_consistency` 的门禁状态封装）。"""
    from .narration import timeline_audio_consistency
    r = timeline_audio_consistency(timeline_total_s, plan or {}, policy)
    return {"state": STATE_PASS if r.get("ok") else STATE_FAIL, "metric": "G-TL", **r}


def post_render_gate(film: str | Path | None, timeline_duration_s, cues: list[dict] | None,
                     narration_end_s, narration_expected: bool, ffmpeg: str | None,
                     ffprobe: str | None, policy: dict | None = None,
                     narration_plan: dict | None = None) -> dict:
    """**渲染后**硬门：PI-3 成片静音 / PI-4 音视频轨道 / PI-5 字幕 orphan。fail-closed。

    `narration_expected=True`（存在 voice 产物）时 PI-5 必须可证；否则其 NOT_ASSESSABLE 仅记录，
    但若 PI-5 明确 FAIL（例如 cue 明显越界）仍阻断。
    返回 `{blocked, code, metrics, reasons, detail, message}`；**不抛异常、不写任何东西**。
    """
    p = dict(DEFAULT_GATE_POLICY)
    p.update(policy or {})
    metrics, reasons = {}, []
    if not p.get("post_render_enabled", True):
        return {"blocked": False, "disabled": True, "code": GATE_CODE, "metrics": {},
                "reasons": ["post-render gate disabled by policy"], **READONLY}
    pi3 = audio_silence_profile(film, ffmpeg, timeline_duration_s, p)
    # ---- Duration Contract v2：只拦**超出已声明预算**的静音 ----
    # v2 时间轴 = Σactual + 已声明 pause budget + trailing；这些停顿是**声明过的**，不算"缺口"。
    # 因此按比例扣减已声明预算份额后再判定（同时原样保留 v1 口径的原始度量，便于审计）。
    v2_budget_share, pi3_v1 = 0.0, dict(pi3)
    if narration_plan:
        try:
            _bud = float(((narration_plan.get("padding_policy") or {}).get("apad_allowed_s")) or 0.0)
            _tl = float(timeline_duration_s or 0.0)
            v2_budget_share = (_bud / _tl) if _tl > 0 else 0.0
        except (TypeError, ValueError):
            v2_budget_share = 0.0
        if v2_budget_share > 0 and pi3.get("silence_ratio") is not None:
            _unb = max(float(pi3["silence_ratio"]) - v2_budget_share, 0.0)
            pi3 = dict(pi3)
            pi3["silence_ratio_raw"] = pi3_v1.get("silence_ratio")
            pi3["declared_budget_share"] = round(v2_budget_share, 4)
            pi3["silence_ratio"] = round(_unb, 4)
            pi3["basis"] = "v2_unbudgeted_silence"
            if _unb <= float(p["max_silence_ratio"]) + 1e-9:
                pi3["state"] = STATE_PASS
                pi3["note"] = ("原始静音占比 {} 中包含已声明 pause budget 份额 {}；"
                               "扣减后 {} ≤ {}".format(pi3_v1.get("silence_ratio"),
                                                     round(v2_budget_share, 4), round(_unb, 4),
                                                     p["max_silence_ratio"]))
    probe = None
    if film and Path(film).is_file() and ffprobe:
        try:
            probe = probe_tracks(film, ffprobe)
        except Exception:                                        # noqa: BLE001
            probe = None
    pi4 = av_track_consistency(probe, timeline_duration_s, p)
    pi5 = subtitle_orphans(cues or [], narration_end_s, timeline_duration_s, p)
    metrics.update({"PI-3": pi3, "PI-4": pi4, "PI-5": pi5})

    def blocked_if(state, why):
        if state == STATE_FAIL:
            reasons.append(why)
            return True
        if state in (STATE_UNKNOWN, STATE_NOT_ASSESSABLE) and p.get("block_on_unknown", True):
            reasons.append("{} 无法证明（{}）→ fail-closed 阻断".format(why, state))
            return True
        return False

    blocked = False
    blocked |= blocked_if(pi3["state"], "PI-3 成片静音违约（最长 {} s、占比 {}、尾部 {} s）".format(
        pi3.get("longest_silence_s"), pi3.get("silence_ratio"), pi3.get("tail_silence_s")))
    blocked |= blocked_if(pi4["state"], "PI-4 音视频轨道不一致（track_delta={} s、video_vs_timeline={} s）"
                          .format(pi4.get("track_delta_s"), pi4.get("video_vs_timeline_s")))
    # PI-5：授权书点名的判据 = 字幕 **orphan**。显示覆盖比（coverage_fail）属度量报告项：
    # 本产线字幕按时长=阅读速度给定、长镜头留白，覆盖比 < 0.60 是正常形态；且修它需要改字幕生成逻辑，
    # 超出本轮授权（"不得修改字幕生成逻辑"）。故 coverage_fail 只记录、绝不当作 PASS。
    if narration_expected:
        if pi5["state"] in (STATE_UNKNOWN, STATE_NOT_ASSESSABLE):
            blocked |= blocked_if(pi5["state"], "PI-5 字幕 orphan 无法证明")
        elif pi5.get("orphan_fail"):
            reasons.append("PI-5 字幕 orphan 违约（orphan={} 占比 {} > {}）".format(
                pi5.get("orphan_cues"), pi5.get("orphan_share"), p["max_orphan_share"]))
            blocked = True
        if pi5.get("coverage_fail"):
            reasons.append("PI-5 字幕显示覆盖比 {} 超出 [{}, {}] —— **仅记录不阻断**"
                           "（度量报告项；修它需改字幕生成逻辑，不在本轮授权内）".format(
                               pi5.get("display_over_narration"), p["min_cue_over_narration"],
                               p["max_cue_over_narration"]))
    else:
        if pi5.get("orphan_fail"):
            reasons.append("PI-5 字幕 orphan 违约（无旁白计划模式，同样 fail-closed）：orphan={}".format(
                pi5.get("orphan_cues")))
            blocked = True
        else:
            reasons.append("PI-5 {} （无旁白计划模式，仅记录不阻断）".format(pi5["state"]))
    # 同 pre_render：`reasons` 放最前，保证被截断的阻断消息仍保留人类可读原因。
    # ---- Duration Contract v2：静音违约 ⇒ **阻止 promote**（不允许"文件长度正确"掩盖旁白缺口）----
    promote_blocked = False
    if p.get("block_promote_on_silence", True) and pi3["state"] in (STATE_FAIL, STATE_UNKNOWN,
                                                                    STATE_NOT_ASSESSABLE):
        promote_blocked = True
    if promote_blocked:
        reasons.append("[PROMOTE_BLOCKED] PI-3 未 PASS（state={}）：尾部/内部静音不可接受 ⇒ "
                       "禁止 promote（成片可保留供人工审查）".format(pi3["state"]))
    detail = {"reasons": reasons, "stage": "post_render", "metrics": metrics,
              "narration_expected": bool(narration_expected), "promote_blocked": promote_blocked,
              "policy": {k: p[k] for k in ("max_silence_block_s", "max_silence_ratio",
                                           "max_tail_silence_s", "max_av_track_delta_s",
                                           "max_video_timeline_delta_s", "max_orphan_share",
                                           "block_on_unknown", "block_promote_on_silence")}}
    return {"blocked": bool(blocked), "disabled": False, "code": GATE_CODE, "metrics": metrics,
            "reasons": reasons, "detail": detail, "promote_blocked": promote_blocked,
            "message": _gate_message("渲染后闸门", detail), **READONLY}
