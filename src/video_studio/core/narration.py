"""旁白完整性与时长契约（3.x Phase 2-B.1）。

背景（真实缺陷，已在 `docs/regression_2x/PHASE2_REPORT.md` 记录）：
- `VoiceAgent` 逐段调用 TTS，失败段只塞进 `errors` 数组后继续，任务仍报 SUCCEEDED、confidence=1.0；
- 拼接出的 `narration.mp3` 只覆盖成功段（实测 12 段只成功 1/12、9/12、7/12）；
- `render` 用 `-t {total} -shortest` 收尾 → 成片被音轨长度截短（438s 时间轴只出 238.5s），
  S09–S12 从未出现在成片里，而任务却是"成功"的。

本模块给出**唯一**的契约定义，供 VoiceAgent（产出方）与 EditingAgent（消费方）共同使用：

1. **完整性（硬闸门）**：脚本中每一段非空旁白都必须有**合法音频**（文件非空 + 可探测出正时长）。
   任一段缺失 → `complete=False` → voice 任务失败，render 在**调用 ffmpeg 之前**阻断。
2. **时长契约（Duration Contract v2 = audio_time_base 权威）**：`declared duration_s` 只是**规划估计**；
   **实际 TTS 时长是 narration 事实**，`audio_time_base_s()`（Σ actual + Σ pause_budget + trailing）
   是**生产权威**（timeline / cues / mix / 门禁全部由它推导）。
   · `declared vs actual` 的偏差只产出可审计的 `PLANNING_DRIFT`（**不阻断**合法实际音频）；
   · 旁白只允许按**显式 pause budget** 补齐（`check_narration_padding`）；超出即 fail-closed；
   · 禁止再用 `apad` 把"旁白短缺"伪装成"时长正确"。
3. **容差**：`DEFAULT_DURATION_TOLERANCE_RATIO`（10%，可由
   `editing.narration_duration_tolerance_ratio` 覆盖）**仅用于 PLANNING_DRIFT 诊断**；
   成片产出后再做一次**产出后校验**：`|成片时长 - 时间轴时长| ≤ VIDEO_DURATION_TOLERANCE_S`。
"""

from __future__ import annotations

import json
from pathlib import Path

from .strip import strip_claims

TRAILING_PAD_S = 2.0                     # 收尾时长：与 _build_material_timeline 末镜头延长一致
DEFAULT_DURATION_TOLERANCE_RATIO = 0.10  # 旁白时长 vs 时间轴时长的容差（±10%）
VIDEO_DURATION_TOLERANCE_S = 1.0         # 成片产出后校验的绝对容差（秒）
MIN_SEGMENT_S = 3.0                      # 单段最短时长（与渲染一致）


class NarrationIncompleteError(RuntimeError):
    """旁白不完整（缺段/音频非法）——必须在渲染前阻断。"""


def _segments(script: dict | None) -> list[dict]:
    return list((script or {}).get("segments") or [])


def narration_text(seg: dict) -> str:
    return strip_claims(seg.get("narration") or "").strip()


def narration_segment_indexes(script: dict | None) -> list[int]:
    """需要配音的段落下标（narration 非空）。"""
    return [i for i, s in enumerate(_segments(script)) if narration_text(s)]


def script_time_base_s(script: dict | None) -> float:
    """**规划时基**（planning-only，Duration Contract v2 起不再作为生产权威）。

    v1 曾把它当作"时间轴权威"。v2 明确：
      · `declared duration_s` = **规划估计**；
      · **实际 TTS 时长** = narration 事实；
      · `audio_time_base_s()`（= Σ actual + Σ pause_budget + trailing）= **生产权威**。
    本函数保留给规划期（无 voice 产物时）与诊断使用。
    """
    segs = _segments(script)
    return sum(max(float(s.get("duration_s") or 0), MIN_SEGMENT_S) for s in segs) + TRAILING_PAD_S


def planned_time_base_s(script: dict | None) -> float:
    """`script_time_base_s` 的显式别名（语义：规划估计，非生产权威）。"""
    return script_time_base_s(script)


# --------------------------------------------------------------------------- v2 权威层
PAUSE_BUDGET_S = 0.75          # 段间允许的**显式停顿预算**（计入时间轴；非"补静音掩盖"）
TIMELINE_AUDIO_TOLERANCE_S = 0.5   # timeline_total 与 audio_time_base 的允许差
CONCAT_TOLERANCE_S = 0.5           # 拼接音轨实测 vs Σ 段实际时长 的允许差
DEFAULT_POLICY_V2 = {
    "policy": "audio_time_base_v2",
    "pause_budget_s": PAUSE_BUDGET_S,
    "trailing_pad_s": TRAILING_PAD_S,
    "timeline_audio_tolerance_s": TIMELINE_AUDIO_TOLERANCE_S,
    "concat_tolerance_s": CONCAT_TOLERANCE_S,
    # 字幕对齐硬门禁阈值
    "min_cue_speech_coverage": 0.98,      # 字幕展示时间落在实际语音窗口内的比例
    "min_speech_cue_coverage": 0.95,      # 实际语音被字幕覆盖的比例
    "max_cue_beyond_narration_s": 1.0,    # 末条字幕允许越过旁白结束的时间
    # 静音（post-render / promote）
    "max_tail_silence_s": 5.0,
    "max_interior_silence_s": 8.0,
    "max_silence_share": 0.05,
}


def pause_budget_s(config: dict | None = None, policy: dict | None = None) -> float:
    """段间停顿预算（可被 `editing.narration_pause_budget_s` 覆盖）。"""
    pol = {**DEFAULT_POLICY_V2, **(policy or {})}
    raw = ((config or {}).get("editing") or {}).get("narration_pause_budget_s")
    try:
        v = float(raw)
        if v >= 0:
            return v
    except (TypeError, ValueError):
        pass
    return float(pol["pause_budget_s"])


def actual_segment_durations(voice_payload: dict | None) -> list:
    """voice 产物里逐段**实测**时长（缺失/非法 ⇒ None，不猜、不用 declared 顶替）。"""
    segs = list((voice_payload or {}).get("segments") or [])
    out = []
    for s in segs:
        d = s.get("duration_s")
        try:
            d = float(d)
        except (TypeError, ValueError):
            d = None
        ok = (d is not None and d > 0 and str(s.get("status")) in ("SUCCESS", "REUSED")
              and bool(s.get("audio")))
        out.append(d if ok else None)
    return out


def pause_attribution(voice_payload: dict | None) -> dict | None:
    """**P21-1 / time_base_policy=v2.1**：读取逐边界 pause **归因表**。

    表位于 `voice_payload["pause_attribution"]`：
      `{"policy": "v2.1", "boundaries": [{"after_index": i, "pause_s": x,
        "kind": "original|derived", "basis": "..."}], "derived_boundary_pause_s": 0.0}`

    **规则（监理裁定）**：原始段边界保持 `PAUSE_BUDGET_S`（0.75，常量语义不变）；
    经**静音吸附**的派生边界 `pause=0`（实测停顿已被切片吸收，再计即"幻影膨胀"——#75.2 根因）。

    **向后兼容**：无表 / 表非法 ⇒ 返回 `None` ⇒ 调用方走既有常量逻辑
    （21 段原产物路径**逐字节不变**）。`PAUSE_BUDGET_S` 常量**零改动**。
    """
    tbl = (voice_payload or {}).get("pause_attribution")
    if not isinstance(tbl, dict):
        return None
    bnds = tbl.get("boundaries")
    if not isinstance(bnds, list) or not bnds:
        return None
    try:
        rows = {int(b["after_index"]): float(b.get("pause_s") or 0.0) for b in bnds
                if isinstance(b, dict) and b.get("after_index") is not None}
    except (TypeError, ValueError, KeyError):
        return None
    if not rows:
        return None
    default = float(tbl.get("default_pause_s", 0.0))
    return {"policy": str(tbl.get("policy") or "v2.1"), "by_index": rows,
            "default_pause_s": default,
            "constant_pause_s": PAUSE_BUDGET_S, "source": "voice_payload.pause_attribution"}


def _pauses(durs: list, pause: float, attribution: dict | None) -> list:
    """逐边界 pause 列表（长度 = len(durs)；最后一个边界恒 0）。"""
    n = len(durs)
    if not n:
        return []
    if attribution is None:
        return [pause] * max(n - 1, 0) + [0.0]
    by = attribution["by_index"]
    dflt = attribution["default_pause_s"]
    return [by.get(i, dflt) if i < n - 1 else 0.0 for i in range(n)]


def audio_time_base_s(voice_payload: dict | None, *, pause_budget_s_: float | None = None,
                      trailing_s: float | None = None) -> float | None:
    """**生产权威时长**：Σ 段实际时长 + Σ 边界 pause + trailing。

    **P21-1**：若 voice 产物带 `pause_attribution`（time_base_policy=v2.1），
    则逐边界 pause 取自归因表（原始边界 0.75、派生边界 0）；否则走既有常量逻辑。
    任一段实际时长缺失 ⇒ 返回 None（fail-closed），**绝不**回退到 declared。
    """
    durs = actual_segment_durations(voice_payload)
    if not durs or any(d is None for d in durs):
        return None
    pause = PAUSE_BUDGET_S if pause_budget_s_ is None else float(pause_budget_s_)
    trail = TRAILING_PAD_S if trailing_s is None else float(trailing_s)
    attrib = pause_attribution(voice_payload)
    pauses = _pauses(durs, pause, attrib)
    return round(sum(durs) + sum(pauses) + trail, 3)


def audio_segment_windows(voice_payload: dict | None, *, pause_budget_s_: float | None = None,
                          trailing_s: float | None = None) -> list:
    """逐段**实际音频窗口**（绝对时间，权威时基）：`[{index,start_s,end_s,actual_s,pause_s}]`。

    **P21-1**：逐边界 pause 取自归因表（见 `pause_attribution`）；无表时走既有常量逻辑。
    """
    durs = actual_segment_durations(voice_payload)
    if not durs or any(d is None for d in durs):
        return []
    pause = PAUSE_BUDGET_S if pause_budget_s_ is None else float(pause_budget_s_)
    attrib = pause_attribution(voice_payload)
    pauses = _pauses(durs, pause, attrib)
    rows, cursor = [], 0.0
    for i, d in enumerate(durs):
        rows.append({"index": i, "start_s": round(cursor, 3), "end_s": round(cursor + d, 3),
                     "actual_s": round(d, 3),
                     "pause_s": round(pauses[i], 3),
                     "pause_kind": (("original" if pauses[i] else "derived")
                                    if attrib else "constant")})
        cursor += d + pauses[i]
    if rows:
        rows[-1]["trailing_pad_s"] = (TRAILING_PAD_S if trailing_s is None else float(trailing_s))
    return rows


def segment_drift(script: dict | None, voice_payload: dict | None) -> dict:
    """逐段 `declared vs actual` 偏差（**诊断**，不阻断生产）。"""
    segs = _segments(script)
    durs = actual_segment_durations(voice_payload)
    rows, dc, ac = [], 0.0, 0.0
    for i, s in enumerate(segs):
        decl = max(float(s.get("duration_s") or 0), MIN_SEGMENT_S)
        act = durs[i] if i < len(durs) else None
        rows.append({"index": i, "scene_id": s.get("scene_id") or "S{:02d}".format(i + 1),
                     "declared_duration_s": round(decl, 3),
                     "actual_tts_duration_s": (round(act, 3) if act is not None else None),
                     "delta_s": (round(decl - act, 3) if act is not None else None)})
        dc += decl
        if act is not None:
            ac += act
    return {"rows": rows, "declared_total_s": round(dc, 3),
            "actual_total_s": (round(ac, 3) if all(r["actual_tts_duration_s"] is not None
                                                   for r in rows) else None),
            "segments": len(rows)}


def cumulative_drift(script: dict | None, voice_payload: dict | None) -> dict:
    """累计漂移（段起始处 `cum_declared - cum_actual`）与最大值（诊断）。"""
    segs = _segments(script)
    durs = actual_segment_durations(voice_payload)
    rows, dc, ac = [], 0.0, 0.0
    mx = 0.0
    for i, s in enumerate(segs):
        act = durs[i] if i < len(durs) else None
        drift = round(dc - ac, 3) if act is not None else None
        rows.append({"index": i, "cum_declared_start_s": round(dc, 3),
                     "cum_actual_start_s": (round(ac, 3) if act is not None else None),
                     "drift_s": drift})
        dc += max(float(s.get("duration_s") or 0), MIN_SEGMENT_S)
        if act is not None:
            ac += act
            mx = max(mx, abs(dc - ac))
    return {"rows": rows, "max_abs_drift_s": round(mx, 3),
            "final_drift_s": (round(dc - ac, 3) if all(r["drift_s"] is not None for r in rows)
                              else None)}


def planning_drift_report(script: dict | None, voice_payload: dict | None,
                          config: dict | None = None) -> dict:
    """`PLANNING_DRIFT` 诊断：declared 与 actual 的偏差**只审计、不阻断**。

    v2 决策：declared 是规划估计、actual 是事实；除非另有"内容长度政策"，
    不得因为 actual ≠ declared 而阻断合法音频。
    """
    sd, cd = segment_drift(script, voice_payload), cumulative_drift(script, voice_payload)
    return {"code": "PLANNING_DRIFT", "blocking": False,
            "policy": "declared_is_planning_estimate_only",
            "note": "declared duration 仅作规划估计；actual TTS duration 是事实。"
                    "本诊断供审计与规划改进，**不**作为生产阻断条件。",
            "tolerance_ratio": tolerance_ratio(config),
            "declared_total_s": sd["declared_total_s"], "actual_total_s": sd["actual_total_s"],
            "planned_time_base_s": round(script_time_base_s(script), 3),
            "delta_s": (round(sd["declared_total_s"] - sd["actual_total_s"], 3)
                        if sd["actual_total_s"] is not None else None),
            "per_segment": sd["rows"], "cumulative": cd["rows"],
            "max_abs_cumulative_drift_s": cd["max_abs_drift_s"],
            "final_cumulative_drift_s": cd["final_drift_s"]}


def narration_plan(script: dict | None, voice_payload: dict | None, *,
                   config: dict | None = None, policy: dict | None = None) -> dict:
    """**Duration Contract v2 的唯一权威对象**（供 timeline / subtitle / BGM / 门禁共用）。

    权威链：`actual TTS duration` → `audio_time_base` → timeline → cues → mix/render。
    `declared` 只出现在 `planning_drift`（诊断）里。
    """
    pol = {**DEFAULT_POLICY_V2, **(policy or {})}
    pause = pause_budget_s(config, pol)
    trail = float(pol["trailing_pad_s"])
    windows = audio_segment_windows(voice_payload, pause_budget_s_=pause, trailing_s=trail)
    base = audio_time_base_s(voice_payload, pause_budget_s_=pause, trailing_s=trail)
    declared = script_time_base_s(script)
    measured_narr = (voice_payload or {}).get("narration_duration_s")
    concat_ok = None
    if base is not None and measured_narr is not None:
        try:
            concat_ok = abs((sum(float(w["actual_s"]) for w in windows))
                            - float(measured_narr)) <= float(pol["concat_tolerance_s"])
        except (TypeError, ValueError):
            concat_ok = None
    return {"policy": pol["policy"],
            "declared_time_base_s": round(declared, 3),
            "audio_time_base_s": base,
            "pause_budget_s": pause, "trailing_pad_s": trail,
            "actual_total_narration_s": (round(sum(float(w["actual_s"]) for w in windows), 3)
                                         if windows else None),
            "measured_narration_track_s": measured_narr,
            "concat_consistent": concat_ok,
            "segments": windows,
            "segment_count": len(windows),
            "complete": bool(base is not None and len(windows) == len(_segments(script))),
            "planning_drift": planning_drift_report(script, voice_payload, config),
            "padding_policy": {"apad_allowed_s": pause * max(len(windows) - 1, 0) + trail,
                               "forbid_unbudgeted_padding": True}}


def check_narration_padding(padding_s: float | None, plan: dict) -> dict:
    """旁白补齐是否超出**明确授权的 pause budget**（超出 ⇒ fail-closed）。"""
    allowed = float((plan.get("padding_policy") or {}).get("apad_allowed_s") or 0.0)
    p = 0.0 if padding_s is None else float(padding_s)
    ok = p <= allowed + 1e-6
    return {"code": "NARRATION_PADDING_WITHIN_BUDGET" if ok else "NARRATION_PADDING_EXCEEDS_BUDGET",
            "ok": ok, "padding_s": round(p, 3), "allowed_s": round(allowed, 3),
            "excess_s": round(max(p - allowed, 0.0), 3),
            "policy": "apad 只允许覆盖显式 pause budget；不得用补静音掩盖旁白短缺"}


def timeline_audio_consistency(timeline_total_s: float | None, plan: dict,
                               policy: dict | None = None) -> dict:
    """timeline_total 必须等于 `audio_time_base`（±容差）——不允许"文件长度正确"掩盖缺口。"""
    pol = {**DEFAULT_POLICY_V2, **(policy or {})}
    base = plan.get("audio_time_base_s")
    if timeline_total_s is None or base is None:
        return {"code": "TIMELINE_AUDIO_UNKNOWN", "ok": False,
                "why": "缺少 timeline 总长或 audio_time_base",
                "timeline_total_s": timeline_total_s, "audio_time_base_s": base}
    delta = round(float(timeline_total_s) - float(base), 3)
    ok = abs(delta) <= float(pol["timeline_audio_tolerance_s"])
    return {"code": "TIMELINE_AUDIO_CONSISTENT" if ok else "TIMELINE_AUDIO_MISMATCH",
            "ok": ok, "timeline_total_s": round(float(timeline_total_s), 3),
            "audio_time_base_s": base, "delta_s": delta,
            "tolerance_s": pol["timeline_audio_tolerance_s"]}


def subtitle_alignment(cues: list, plan: dict, policy: dict | None = None) -> dict:
    """字幕 ↔ **实际音频窗口** 对齐度量（v2 硬门禁的数据源）。"""
    pol = {**DEFAULT_POLICY_V2, **(policy or {})}
    segs = plan.get("segments") or []
    if not cues or not segs:
        return {"code": "SUBTITLE_ALIGNMENT_UNKNOWN", "ok": False,
                "why": "缺少 cues 或权威音频窗口"}
    wins = [(float(s["start_s"]), float(s["end_s"])) for s in segs]
    speech = sum(e - s for s, e in wins)
    in_speech = out_speech = 0.0
    beyond = 0.0
    narration_end = wins[-1][1]
    for c in cues:
        cs, ce = float(c["start"]), float(c["end"])
        if ce <= cs:
            continue
        covered = sum(max(0.0, min(ce, e) - max(cs, s)) for s, e in wins)
        in_speech += covered
        out_speech += max(0.0, (ce - cs) - covered)
        beyond += max(0.0, ce - narration_end)
    total_cue = in_speech + out_speech
    cue_cov = (in_speech / total_cue) if total_cue > 0 else 0.0
    speech_cov = (in_speech / speech) if speech > 0 else 0.0
    # 阻断判据（与冻结 PI-5 政策一致）：
    #   ① 字幕**不得出现在无语音处**（cue 展示时间必须落在实际语音窗口内）；
    #   ② 字幕**不得越过旁白结束**。
    #   `speech_cov`（语音被字幕覆盖的比例）只是**度量报告项**：本产线字幕按时长=阅读速度给定、
    #   长镜头留白是正常形态（PI-5 已明确 coverage 类指标仅记录、不阻断），故不作阻断条件。
    ok = bool(cue_cov >= pol["min_cue_speech_coverage"]
              and beyond <= pol["max_cue_beyond_narration_s"] + 1e-6)
    return {"code": "SUBTITLE_ALIGNED" if ok else "SUBTITLE_MISALIGNED", "ok": ok,
            "cue_display_in_speech_ratio": round(cue_cov, 4),
            "speech_covered_by_cue_ratio": round(speech_cov, 4),
            "speech_coverage_is_advisory": True,
            "cue_seconds_outside_speech": round(out_speech, 3),
            "cue_seconds_beyond_narration_end": round(beyond, 3),
            "narration_end_s": round(narration_end, 3),
            "thresholds": {"min_cue_speech_coverage": pol["min_cue_speech_coverage"],
                           "min_speech_cue_coverage": pol["min_speech_cue_coverage"],
                           "min_speech_cue_coverage_advisory": True,
                           "max_cue_beyond_narration_s": pol["max_cue_beyond_narration_s"]}}



def tolerance_ratio(config: dict | None) -> float:
    raw = ((config or {}).get("editing") or {}).get("narration_duration_tolerance_ratio")
    try:
        val = float(raw)
    except (TypeError, ValueError):
        return DEFAULT_DURATION_TOLERANCE_RATIO
    return val if 0.0 <= val <= 1.0 else DEFAULT_DURATION_TOLERANCE_RATIO


def probe_duration_s(ctx, path) -> float | None:
    """用工具层探测音频/视频时长（秒）；失败或非正值返回 None（不猜）。"""
    from ..tools.base import ToolError
    from ..tools.ffmpeg_tool import FFmpegTool

    try:
        res = FFmpegTool().execute({"op": "probe", "inputs": [str(path)]}, ctx)
    except ToolError:
        return None
    data = res.data or {}
    cands = []
    for s in data.get("streams") or []:
        try:
            cands.append(float(s.get("duration")))
        except (TypeError, ValueError):
            pass
    try:
        cands.append(float(data.get("duration")))
    except (TypeError, ValueError):
        pass
    cands = [c for c in cands if c and c > 0]
    return max(cands) if cands else None


def segment_file_ok(ctx, project_dir: Path, rel: str) -> tuple[bool, float | None]:
    """段音频是否**合法**：存在、非空、可探测出 > 0 的时长。返回 (ok, duration_s)。"""
    if not rel:
        return False, None
    p = Path(rel)
    if not p.is_absolute():
        p = Path(project_dir) / rel
    try:
        if not p.is_file() or p.stat().st_size <= 0:
            return False, None
    except OSError:
        return False, None
    dur = probe_duration_s(ctx, p)
    return (dur is not None and dur > 0), dur


def evaluate_narration(script: dict | None, voice_payload: dict | None) -> dict:
    """按脚本预期的段集合，核对 voice 产物里的逐段状态。只做判定，不猜补。"""
    expected = narration_segment_indexes(script)
    segs = {int(s.get("index")): s for s in ((voice_payload or {}).get("segments") or [])
            if s.get("index") is not None}
    ok_idx, bad = [], []
    for i in expected:
        s = segs.get(i)
        if s and str(s.get("status")) in ("SUCCESS", "REUSED") and s.get("audio"):
            ok_idx.append(i)
        else:
            bad.append(i)
    reasons = []
    if (voice_payload or {}).get("status") == "INCOMPLETE":
        reasons.append("voice 产物自述 INCOMPLETE")
    if bad:
        reasons.append("缺少合法音频的段落: {}".format(bad))
    return {
        "expected_segments": len(expected),
        "successful_segments": len(ok_idx),
        "successful_indexes": ok_idx,
        "failed_indexes": bad,
        "complete": bool(expected) and not bad,
        "reasons": reasons,
    }


def duration_contract(timeline_duration_s: float, narration_duration_s: float | None,
                      tol: float | None = None) -> dict:
    """timeline 权威时长 vs 旁白实际时长。返回可审计的判定（不修改任何时长）。

    narration_duration_s is None 表示"本轮未测得"（如旁白未写/未重建）——此时 measured=False，
    不把 0.0 当成"旁白 0 秒"来推断补齐或截断。
    """
    tol = DEFAULT_DURATION_TOLERANCE_RATIO if tol is None else tol
    t = float(timeline_duration_s or 0.0)
    measured = narration_duration_s is not None
    n = float(narration_duration_s or 0.0)
    delta = n - t
    ratio = (abs(delta) / t) if t > 0 else 0.0
    within = bool(measured and t > 0 and n > 0 and ratio <= tol)
    return {
        "policy": "timeline_authoritative",
        "measured": measured,
        "timeline_duration_s": round(t, 3),
        "narration_duration_s": (round(n, 3) if measured else None),
        "delta_s": (round(delta, 3) if measured else None),
        "delta_ratio": (round(ratio, 4) if measured else None),
        "tolerance_ratio": tol,
        "within_tolerance": within,
        "shortfall_s": (round(max(-delta, 0.0), 3) if measured else None),  # 较短→静音补齐
        "excess_s": (round(max(delta, 0.0), 3) if measured else None),      # 较长→超容差则阻断
        "audio_padded_to_timeline": bool(measured and delta < 0),
        "audio_trimmed_to_timeline": bool(measured and delta > 0 and within),
    }


def incomplete_message(kind: str, detail: dict) -> str:
    """统一的阻断文案（带明确错误码，供任务 error / 事件 / 报告引用）。"""
    return "[NARRATION_INCOMPLETE] {}: {}".format(
        kind, json.dumps(detail, ensure_ascii=False))
