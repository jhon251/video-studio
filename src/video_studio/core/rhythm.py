"""4.x Phase 4-G：只读节奏分析与人工建议（`rhythm-advisor-v1`）。

**定位**：只**读**已有产物、只**输出**建议与依据。**不**改时间轴/镜头时长/旁白/素材/BGM，
**不**触发 redo、**不**写库、**不**写任何产物、**不**绕过 HITL。

分析项（授权要求 1–7）：
  1. 镜头时长（`R_SCENE_TOO_SHORT` / `R_SCENE_TOO_LONG`）
  2. 旁白段落时长（`R_NARRATION_SEGMENT_*`：段落本身的过短/过长）
  3. 镜头与旁白的时间覆盖（`R_CUT_MID_NARRATION`：切换落在旁白句中）
  4. 镜头切换密度（`R_CUT_DENSITY_HIGH` / `R_CUT_DENSITY_LOW`，单位：cuts/min）
  5. 过短/过长镜头（同 1，阈值可配）
  6. BGM 开启时的节奏提示（`R_BGM_DUCK_FRAGMENTED`：单镜头内 duck 切换过密 → 与分段/镜头边界不齐）
  7. 可疑的静态画面持续时间（`R_STATIC_HOLD`：单张静态素材持续超过 `static_warn_s`）

判定纪律：
  · 每条建议包含 `scene_id` / 当前时长 / 触发规则 / 具体证据 / 建议动作 / 风险与限制 / 置信度；
  · **无法判断时不强行给建议**：进入 `unknowns[]`（`R_UNKNOWN_*`），并在报告里显式计数；
  · 所有建议 `status="SUGGESTION"`、`applied=false`、`executed=false`；报告级 `applied_changes=0`；
  · 纯函数、无时间/随机/网络依赖：**同输入同配置 → 逐字节相同输出**（可用 JSON 直接比对）。
"""
from __future__ import annotations

import hashlib
import json

RHYTHM_SCHEMA = "rhythm-advisor-v1"

DEFAULT_SETTINGS = {
    # ---- 2026-10-20：改按**外部标杆**标定（原值为"内部历史"自洽口径）----
    # 参照：知识区中腰部 ≈15 次切换/分钟；王骁 ≈20–40；燕三 ≈60+。
    # 旧值（max_scene_s=20、static_warn_s=15、min_cuts=2）使"18.4s/镜"的成片几乎不报警；
    # EP3 实测 3.36 次/分钟：旧口径在区间内，新口径直接低于下限。
    "min_scene_s": 1.0,                 # 镜头过短阈值（旧 3.0；允许更碎的切点）
    "max_scene_s": 10.0,                # 镜头过长阈值（旧 20.0）
    "static_warn_s": 4.0,               # 单张静态素材持续超过此时长 → 可疑静态（旧 15.0）
    "min_cuts_per_min": 15.0,           # 切换密度下限（旧 2.0）
    "max_cuts_per_min": 45.0,           # 切换密度上限（旧 12.0；燕三式快剪不误报）
    "narration_boundary_tolerance_s": 0.5,   # 镜头边界与旁白段落边界的对齐容差
    "narration_seg_min_s": 4.0,         # 旁白段落过短阈值（口播语义完整性提示）
    "narration_seg_max_s": 25.0,        # 旁白段落过长阈值（旧 30.0）
    "bgm_duck_transitions_warn": 2,     # 单镜头内 duck 切换次数上限（BGM 开启时）
}

RULES = {
    "R_SCENE_TOO_SHORT": {
        "area": "镜头时长", "param": "min_scene_s",
        "action": "考虑与相邻镜头合并、或延长该镜头（人工决定；建议器不改时长）",
        "risk": "合并/延长会改变时间轴权威时长，必须人工评估旁白与素材是否仍然对齐"},
    "R_SCENE_TOO_LONG": {
        "area": "镜头时长", "param": "max_scene_s",
        "action": "考虑在该镜头内增加一次切换或缩短它（人工决定；建议器不改时长）",
        "risk": "缩短镜头会挤压旁白口播；若素材只有一张图，切换需要额外素材或纯色卡"},
    "R_STATIC_HOLD": {
        "area": "可疑静态画面", "param": "static_warn_s",
        "action": "考虑补充分镜素材或在镜头内做轻微运动/裁切变化（人工决定；建议器不改画面）",
        "risk": "无第二素材时只能靠纯色卡/字幕变化，可能降低观感；不自动替换素材"},
    "R_CUT_MID_NARRATION": {
        "area": "镜头与旁白覆盖", "param": "narration_boundary_tolerance_s",
        "action": "考虑把该次切换移到旁白句读边界（人工决定；建议器不改时间轴）",
        "risk": "移动切换会同时改变相邻两个镜头的时长；需重跑渲染才能生效（建议器不触发）"},
    "R_NARRATION_SEGMENT_TOO_SHORT": {
        "area": "旁白段落时长", "param": "narration_seg_min_s",
        "action": "考虑与该镜头内其它段落合并朗读（人工决定；建议器不改旁白）",
        "risk": "合并段落会改变旁白音频与时间轴对齐，需人工确认后走 redo"},
    "R_NARRATION_SEGMENT_TOO_LONG": {
        "area": "旁白段落时长", "param": "narration_seg_max_s",
        "action": "考虑拆分为两段并在其间安排一次切换（人工决定；建议器不改旁白）",
        "risk": "拆分需要新的分镜与素材匹配；可能触发素材不足"},
    "R_NARRATION_TRIMMED": {
        "area": "镜头与旁白覆盖", "param": "film_duration_s",
        "action": "考虑延长末尾镜头或精简末段旁白，使口播不被裁掉（人工决定）",
        "risk": "时间轴权威时长契约不允许用旁白长度反向决定片长；改动需整体评估"},
    "R_CUT_DENSITY_HIGH": {
        "area": "切换密度", "param": "max_cuts_per_min",
        "action": "考虑合并部分镜头、降低单位时间切换次数（人工决定）",
        "risk": "合并会放宽节奏但可能让画面变单调；涉及旁白与素材重排"},
    "R_CUT_DENSITY_LOW": {
        "area": "切换密度", "param": "min_cuts_per_min",
        "action": "考虑增加切换点或补充素材（人工决定）",
        "risk": "增加切换需要更多可用素材；素材不足时会退化为纯色卡"},
    "R_BGM_DUCK_FRAGMENTED": {
        "area": "BGM 节奏提示", "param": "bgm_duck_transitions_warn",
        "action": "考虑让旁白分段与镜头边界对齐，减少镜头内 BGM 起伏次数（人工决定）",
        "risk": "改动分段/边界会同时影响旁白与 BGM ducking；建议器不改 BGM 参数"},
}
UNKNOWN_RULES = {
    "R_UNKNOWN_DURATION": "镜头时长缺失/非正数（start_s/end_s 不可用）→ 无法判断节奏",
    "R_UNKNOWN_NARRATION": "该镜头没有可用的旁白段落（缺失/未成功/时长未知）→ 不做覆盖判断",
    "R_UNKNOWN_ASSET_TYPE": "素材类型未知（无法判断是否静态画面）→ 不做静态时长判断",
    "R_UNKNOWN_FILM_DURATION": "成片时长缺失/非正数 → 不做切换密度判断",
    "R_UNKNOWN_NARRATION_TOTAL": "旁白总时长缺失 → 不做旁白超时轴判断",
    "R_UNKNOWN_BGM": "BGM 证据缺失或未生效 → 不做 BGM 节奏提示",
}

IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff")


def rhythm_settings(config: dict | None = None) -> dict:
    """读 `tools.rhythm`；缺省即默认阈值。非法值回退默认（不放松、不猜测）。"""
    raw = ((config or {}).get("tools") or {}).get("rhythm") or {}
    s = dict(DEFAULT_SETTINGS)
    notes = []
    for k, v in raw.items():
        if k not in DEFAULT_SETTINGS:
            continue
        try:
            s[k] = (int(v) if isinstance(DEFAULT_SETTINGS[k], int) and not isinstance(v, bool)
                    else float(v))
        except (TypeError, ValueError):
            notes.append("参数 {}={!r} 非法，保留默认 {}".format(k, v, s[k]))
    s["_notes"] = notes
    s["_source"] = "tools.rhythm" if raw else "default(readonly)"
    return s


def _num(x) -> float | None:
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f


def _scene_duration(sc: dict) -> float | None:
    d = _num(sc.get("duration_s"))
    if d is not None and d > 0:
        return round(d, 3)
    a, b = _num(sc.get("start_s")), _num(sc.get("end_s"))
    if a is None or b is None or b <= a:
        return None
    return round(b - a, 3)


def narration_windows(narration: dict | None) -> list[dict]:
    """旁白段落的时间窗（按成功段落顺序累加真实时长）——与 4-F ducking 同一口径。"""
    segs = list((narration or {}).get("segments") or [])
    out, cursor = [], 0.0
    for s in segs:
        st = str(s.get("status") or "")
        if st.upper() in ("FAILED", "PENDING", "SKIPPED"):
            out.append({"index": s.get("index"), "status": st or "UNKNOWN",
                        "start_s": None, "end_s": None, "duration_s": None})
            continue
        d = _num(s.get("duration_s"))
        if d is None or d <= 0:
            out.append({"index": s.get("index"), "status": st or "UNKNOWN",
                        "start_s": None, "end_s": None, "duration_s": None})
            continue
        out.append({"index": s.get("index"), "status": st or "SUCCESS",
                    "start_s": round(cursor, 3), "end_s": round(cursor + d, 3),
                    "duration_s": round(d, 3)})
        cursor += d
    return out


def _effective_ext(asset: dict | None) -> tuple[str, str]:
    """素材扩展名与来源（`ext_field` = 产物里显式给出；`name_suffix` = 从文件名推断）。"""
    if not asset:
        return "", "none"
    ext = str(asset.get("ext") or "").lower()
    if ext:
        return ext, "ext_field"
    name = str(asset.get("name") or "")
    if "." in name:
        return "." + name.rsplit(".", 1)[-1].lower(), "name_suffix"
    return "", "none"


def _is_static(asset: dict | None) -> bool | None:
    """该镜头画面是否静态：图片类素材 → True；视频类 → False；未知 → None（不判断）。"""
    if not asset:
        return None
    ext, _basis = _effective_ext(asset)
    if ext in IMAGE_EXTS:
        return True
    if ext in (".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v"):
        return False
    return None


def _confidence(excess: float, threshold: float) -> str:
    if threshold <= 0:
        return "MEDIUM"
    return "HIGH" if abs(excess) >= 0.25 * abs(threshold) else "MEDIUM"


def analyze_rhythm(payload: dict, *, settings: dict | None = None) -> dict:
    """只读节奏分析：输入为**已产出的证据**（不读库、不写文件），输出建议 + 依据 + UNKNOWN。"""
    s = {**DEFAULT_SETTINGS, **(settings or {})}
    timeline = list((payload or {}).get("timeline") or [])
    narration = (payload or {}).get("narration")
    bgm = (payload or {}).get("bgm") or {}
    film_dur = _num((payload or {}).get("film_duration_s"))
    nw = narration_windows(narration)
    by_index = {w["index"]: w for w in nw}

    suggestions: list[dict] = []
    unknowns: list[dict] = []
    scenes_out: list[dict] = []

    def add_suggestion(scene_id, rule, current, evidence, scope="scene", threshold=None):
        meta = RULES[rule]
        suggestions.append({
            "suggestion_id": "sg_{:03d}".format(len(suggestions) + 1),
            "scene_id": scene_id, "scope": scope, "rule": rule, "area": meta["area"],
            "current_duration_s": current, "threshold_s": threshold,
            "evidence": evidence, "action": meta["action"], "risk": meta["risk"],
            "confidence": evidence.pop("_confidence", "MEDIUM"),
            "status": "SUGGESTION", "applied": False, "executed": False,
            "requires_human_decision": True,
            "note": "只读建议：不会自动生效，需人工决定后另行走 redo/审批",
        })

    def add_unknown(scene_id, rule, evidence):
        unknowns.append({"scene_id": scene_id, "rule": rule,
                         "reason": UNKNOWN_RULES[rule], "evidence": evidence,
                         "status": "UNKNOWN", "suggestion": None})

    static_flag_seen = False
    for i, sc in enumerate(timeline):
        sid = str(sc.get("scene_id") or "S{:02d}".format(i + 1))
        dur = _scene_duration(sc)
        seg_i = sc.get("segment_index")
        win = by_index.get(seg_i)
        asset = sc.get("selected_asset") or {}
        ext_eff, ext_basis = _effective_ext(asset)
        static = _is_static(asset)
        if static is None:
            add_unknown(sid, "R_UNKNOWN_ASSET_TYPE",
                        {"asset_name": asset.get("name"), "ext": asset.get("ext"),
                         "ext_effective": ext_eff, "ext_basis": ext_basis,
                         "reason": "素材扩展名缺失/非图片非视频"})
        else:
            static_flag_seen = True
        scenes_out.append({
            "scene_id": sid, "index": i,
            "start_s": _num(sc.get("start_s")), "end_s": _num(sc.get("end_s")),
            "duration_s": dur, "fallback_state": sc.get("fallback_state"),
            "selection_source": sc.get("selection_source"),
            "asset": {"name": asset.get("name"), "ext": asset.get("ext"),
                      "ext_effective": ext_eff, "ext_basis": ext_basis,
                      "asset_id": asset.get("asset_id"), "static": static},
            "narration": ({"segment_index": seg_i, "start_s": win["start_s"],
                           "end_s": win["end_s"], "duration_s": win["duration_s"],
                           "status": win["status"]} if win else {"segment_index": seg_i}),
        })
        # ---- 1/5 镜头时长 ----
        if dur is None:
            add_unknown(sid, "R_UNKNOWN_DURATION",
                        {"start_s": sc.get("start_s"), "end_s": sc.get("end_s")})
        else:
            if dur < float(s["min_scene_s"]):
                ev = {"measured_duration_s": dur, "threshold_s": float(s["min_scene_s"]),
                      "delta_s": round(dur - float(s["min_scene_s"]), 3),
                      "_confidence": _confidence(dur - float(s["min_scene_s"]),
                                                 float(s["min_scene_s"]))}
                add_suggestion(sid, "R_SCENE_TOO_SHORT", dur, ev,
                               threshold=float(s["min_scene_s"]))
            if dur > float(s["max_scene_s"]):
                ev = {"measured_duration_s": dur, "threshold_s": float(s["max_scene_s"]),
                      "delta_s": round(dur - float(s["max_scene_s"]), 3),
                      "_confidence": _confidence(dur - float(s["max_scene_s"]),
                                                 float(s["max_scene_s"]))}
                add_suggestion(sid, "R_SCENE_TOO_LONG", dur, ev,
                               threshold=float(s["max_scene_s"]))
            # ---- 7 可疑静态画面 ----
            if static is True and dur > float(s["static_warn_s"]):
                ev = {"asset_name": asset.get("name"),
                      "asset_ext_effective": ext_eff, "ext_basis": ext_basis,
                      "static_duration_s": dur, "threshold_s": float(s["static_warn_s"]),
                      "selection_source": sc.get("selection_source"),
                      "_confidence": _confidence(dur - float(s["static_warn_s"]),
                                                 float(s["static_warn_s"]))}
                add_suggestion(sid, "R_STATIC_HOLD", dur, ev, threshold=float(s["static_warn_s"]))
        # ---- 2 旁白段落时长 ----
        if win is None or win.get("duration_s") is None:
            add_unknown(sid, "R_UNKNOWN_NARRATION",
                        {"segment_index": seg_i,
                         "narration_available": bool(nw),
                         "reason": "段落缺失/未成功/时长未知"})
        else:
            nd = float(win["duration_s"])
            if nd < float(s["narration_seg_min_s"]):
                add_suggestion(sid, "R_NARRATION_SEGMENT_TOO_SHORT", nd,
                               {"segment_index": seg_i, "segment_status": win["status"],
                                "measured_duration_s": nd,
                                "threshold_s": float(s["narration_seg_min_s"]),
                                "_confidence": "MEDIUM"},
                               threshold=float(s["narration_seg_min_s"]))
            if nd > float(s["narration_seg_max_s"]):
                add_suggestion(sid, "R_NARRATION_SEGMENT_TOO_LONG", nd,
                               {"segment_index": seg_i, "segment_status": win["status"],
                                "measured_duration_s": nd,
                                "threshold_s": float(s["narration_seg_max_s"]),
                                "_confidence": _confidence(nd - float(s["narration_seg_max_s"]),
                                                           float(s["narration_seg_max_s"]))},
                               threshold=float(s["narration_seg_max_s"]))
        # ---- 3 镜头与旁白的时间覆盖（切换落在旁白句中）----
        if dur is not None and win is not None and win.get("duration_s") is not None:
            a, b = _num(sc.get("start_s")), _num(sc.get("end_s"))
            tol = float(s["narration_boundary_tolerance_s"])
            if a is not None and win["start_s"] is not None:
                lead = round(win["start_s"] - a, 3)      # 口播在镜头开始之前就开始了
                tail = round(win["end_s"] - b, 3)        # 口播延伸到镜头结束之后
                if lead < -tol:
                    add_suggestion(sid, "R_CUT_MID_NARRATION", dur,
                                   {"crossing": "speech_started_before_cut",
                                    "speech_start_s": win["start_s"], "scene_start_s": a,
                                    "lead_s": lead, "tolerance_s": tol,
                                    "segment_index": seg_i, "_confidence": "HIGH"},
                                   threshold=tol)
                elif tail > tol:
                    add_suggestion(sid, "R_CUT_MID_NARRATION", dur,
                                   {"crossing": "speech_continues_after_cut",
                                    "speech_end_s": win["end_s"], "scene_end_s": b,
                                    "tail_s": tail, "tolerance_s": tol,
                                    "segment_index": seg_i, "_confidence": "HIGH"},
                                   threshold=tol)

    # ---- 4 切换密度（片级；挂到最短镜头，标注 scope=film）----
    if film_dur is None or film_dur <= 0:
        add_unknown(None, "R_UNKNOWN_FILM_DURATION", {"film_duration_s": film_dur})
    elif len(timeline) >= 2:
        cuts = len(timeline) - 1
        cpm = cuts / (film_dur / 60.0)
        shortest = min((x for x in scenes_out if x["duration_s"]), key=lambda x: x["duration_s"],
                       default=None)
        anchor = shortest["scene_id"] if shortest else None
        if cpm > float(s["max_cuts_per_min"]):
            add_suggestion(anchor, "R_CUT_DENSITY_HIGH", round(cpm, 3),
                           {"cuts": cuts, "film_duration_s": film_dur,
                            "cuts_per_min": round(cpm, 3),
                            "threshold_cuts_per_min": float(s["max_cuts_per_min"]),
                            "anchor": "最短镜头（最可能需要合并）",
                            "_confidence": _confidence(cpm - float(s["max_cuts_per_min"]),
                                                       float(s["max_cuts_per_min"]))},
                           scope="film", threshold=float(s["max_cuts_per_min"]))
        elif cpm < float(s["min_cuts_per_min"]):
            add_suggestion(anchor, "R_CUT_DENSITY_LOW", round(cpm, 3),
                           {"cuts": cuts, "film_duration_s": film_dur,
                            "cuts_per_min": round(cpm, 3),
                            "threshold_cuts_per_min": float(s["min_cuts_per_min"]),
                            "anchor": "最短镜头（最可能需要拆分）",
                            "_confidence": _confidence(cpm - float(s["min_cuts_per_min"]),
                                                       float(s["min_cuts_per_min"]))},
                           scope="film", threshold=float(s["min_cuts_per_min"]))
    # ---- 旁白总时长 vs 成片时长（口播被裁）----
    n_total = _num((narration or {}).get("total_s"))
    if narration is None:
        add_unknown(None, "R_UNKNOWN_NARRATION_TOTAL", {"narration": None})
    elif n_total is None:
        add_unknown(None, "R_UNKNOWN_NARRATION_TOTAL",
                    {"narration_total_s": None,
                     "segments": len(list((narration or {}).get("segments") or []))})
    elif film_dur and n_total > film_dur + 0.05:
        anchor = scenes_out[-1]["scene_id"] if scenes_out else None
        add_suggestion(anchor, "R_NARRATION_TRIMMED", round(n_total, 3),
                       {"narration_total_s": round(n_total, 3),
                        "film_duration_s": film_dur,
                        "excess_s": round(n_total - film_dur, 3),
                        "trimmed_by_contract": bool((narration or {}).get("trimmed")),
                        "_confidence": "HIGH"},
                       scope="film", threshold=film_dur)
    # ---- 6 BGM 节奏提示（仅在 BGM 真的生效时）----
    if not bgm or not bgm.get("enabled"):
        notes_bgm = {"enabled": False, "applied": False,
                     "note": "BGM 关闭（默认）：不产生任何 BGM 节奏建议"}
    elif not bgm.get("applied"):
        add_unknown(None, "R_UNKNOWN_BGM",
                    {"enabled": True, "applied": False,
                     "reason": "BGM 已配置但未生效（未混入成片）"})
        notes_bgm = {"enabled": True, "applied": False}
    else:
        intervals = list(bgm.get("intervals") or [])
        warn = int(s["bgm_duck_transitions_warn"])
        for x in scenes_out:
            a, b = x["start_s"], x["end_s"]
            if a is None or b is None:
                continue
            inside = [iv for iv in intervals
                      if _num(iv.get("start_s")) is not None
                      and _num(iv.get("start_s")) >= a and _num(iv.get("start_s")) < b]
            if len(inside) > warn:
                add_suggestion(x["scene_id"], "R_BGM_DUCK_FRAGMENTED", round(b - a, 3),
                               {"duck_transitions_in_scene": len(inside),
                                "threshold": warn,
                                "duck_windows": [[iv.get("start_s"), iv.get("end_s")]
                                                 for iv in inside],
                                "bed_db": bgm.get("bed_db"), "duck_db": bgm.get("duck_db"),
                                "_confidence": "MEDIUM"}, threshold=warn)
        notes_bgm = {"enabled": True, "applied": True,
                     "ducking_intervals": len(intervals),
                     "bed_db": bgm.get("bed_db"), "duck_db": bgm.get("duck_db")}

    order = {x["scene_id"]: x["index"] for x in scenes_out}
    order[None] = -1
    suggestions.sort(key=lambda x: (order.get(x["scene_id"], 999), x["rule"]))
    for n, sg in enumerate(suggestions, start=1):
        sg["suggestion_id"] = "sg_{:03d}".format(n)
    unknowns.sort(key=lambda x: (order.get(x["scene_id"], 999), x["rule"]))

    by_rule: dict[str, int] = {}
    for sg in suggestions:
        by_rule[sg["rule"]] = by_rule.get(sg["rule"], 0) + 1
    measured = [x for x in scenes_out if x["duration_s"] is not None]
    report = {
        "schema": RHYTHM_SCHEMA,
        "settings": {k: v for k, v in s.items() if not k.startswith("_")},
        "settings_source": s.get("_source") or "default(readonly)",
        "settings_notes": s.get("_notes") or [],
        "policy": {
            "mode": "readonly_advisory",
            "auto_apply": False, "auto_redo": False, "writes_to_production": False,
            "changes_timeline": False, "changes_scene_duration": False,
            "changes_narration": False, "changes_assets": False, "changes_bgm": False,
            "bypasses_hitl": False, "requires_human_decision": True,
            "note": ("只读建议：不写库/不写产物/不改时间轴·时长·旁白·素材·BGM/不触发 redo；"
                     "任何改动都必须人工决定后另行走审批与 redo"),
        },
        "applied_changes": 0,
        "input_fingerprints": (payload or {}).get("sources") or {},
        "summary": {
            "film_duration_s": film_dur,
            "scene_count": len(scenes_out),
            "scenes_measured": len(measured),
            "cuts": max(0, len(scenes_out) - 1),
            "cuts_per_min": (round((len(scenes_out) - 1) / (film_dur / 60.0), 3)
                             if film_dur else None),
            "narration_total_s": n_total,
            "narration_segments": len(nw),
            "suggestions": len(suggestions),
            "suggestions_by_rule": by_rule,
            "unknowns": len(unknowns),
            "static_scenes": sum(1 for x in scenes_out if x["asset"].get("static") is True),
            "bgm": notes_bgm,
        },
        "scenes": scenes_out,
        "suggestions": suggestions,
        "unknowns": unknowns,
        "rules": {k: {"area": v["area"], "param": v["param"]} for k, v in RULES.items()},
        "unknown_rules": UNKNOWN_RULES,
        "note": ("建议仅供参考：检索/素材/时间轴/旁白的任何变更都必须人工决定并走既有审批与 redo 流程；"
                 "本报告未被写入任何生产产物，也不代表已执行的变更。"),
    }
    return report


def fingerprint(text: str | bytes) -> str:
    b = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(b).hexdigest()
