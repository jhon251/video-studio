# -*- coding: utf-8 -*-
"""P9-2：留存质量**机械层**（纯函数、离线、确定性、**零 LLM**、零 I/O）。

职责边界（写入报告）：**critic 管事实红线，retention 管留存**——二者互不替代。
本模块只评"好不好看"（hook 结构/间隔、情绪节拍、CTA、节奏、结尾），
**不评事实对错**（out-of-scope，见 `OUT_OF_SCOPE`）。

阈值纪律：所有阈值**镜像** `config/script_style_guide.md` v3「留存工程」节，不发明新数
（每个阈值带 `basis` 注明出处）。缺 v3 元数据时输出**结构码** `V3_METADATA_ABSENT`
（单独计数，**不计 FAIL**；相应维度 `NOT_ASSESSABLE` 且不进入评分分母，避免把"没标"当"做得差"）。
"""
from __future__ import annotations

from .visual_requirement import canonical, sha256_text

SCHEMA = "retention-mechanical-v1"
VERSION = 1

PASS, WARN, FAIL, NOT_ASSESSABLE = "PASS", "WARN", "FAIL", "NOT_ASSESSABLE"
EMOTION_BEATS = ("curiosity", "tension", "payoff", "calm", "surprise")

#: 阈值常量（**镜像 style guide v3，不发明新数**）
THRESHOLDS = {
    "hook_window_s": {"value": 40.0, "basis": "style guide v3 §2.1 / §3.13（前 20-40 秒认知冲突）"},
    "hook_interval_max_s": {"value": 90.0,
                            "basis": "style guide v3 §2.1 / §3.5（每 60-90 秒一个信息增量点）"},
    "beat_run_max": {"value": 3, "basis": "style guide v3 §2.2（不得连续 3 个同类节拍）"},
    "cta_max": {"value": 2, "basis": "style guide v3 §2.3（全片 1-2 处互动引导）"},
    "segment_long_s": {"value": 120.0,
                       "basis": "style guide v3 §3.8（不凑时长；超长段落=信息堆叠风险）"},
    "segment_short_s": {"value": 8.0,
                        "basis": "style guide v3 §3.8（过短段落=节奏碎裂风险）"},
    "ending_interaction_max": {"value": 1,
                               "basis": "style guide v3 §2.3（结尾至多 1 句内容型互动）"},
}

#: 机械层**不评**的东西（必须在报告中声明）
OUT_OF_SCOPE = [
    "事实对错 / 证据充分性（归 critic + claim 链，本模块不评）",
    "画面与素材质量（归 Phase 6/7 视觉链）",
    "审美与个人风格偏好（本模块只做结构性与表达性判定）",
]

#: 开场寒暄黑名单（命中即 WARN；不判 FAIL——规范保留"确有叙事价值"的例外）
GREETING_BLACKLIST = ("大家好", "今天我们来聊", "今天聊", "咱们聊聊", "哈喽", "hello everyone",
                      "欢迎来到", "欢迎收看", "废话不多说", "话不多说", "首先自我介绍一下")
#: CTA 裸话术黑名单（含变体）
BARE_CTA = ("感谢观看", "感谢收看", "一键三连", "记得点赞", "点赞关注", "点赞订阅", "关注我",
            "关注一下", "订阅一下", "求个三连", "别忘了三连", "我们下期再见", "下期再见",
            "评论区告诉我", "评论区见", "投币", "收藏转发", "转发给")
#: 结尾收束表述（内容型收束标记）
#: 规约保真修正（P9-2，透明登记）：初版词表只含「答案是/所以/结论…」等子集，导致
#: v3 稿的「最后回到那个判断：…」被误判为 ENDING_NO_CLOSURE（WARN）。按 style guide v3 §3.13 /
#: v2 §十四，结尾是**按功能**定义的（回答"我们现在究竟知道了什么 / 为什么答案会是这样"），
#: 故补齐同类功能表述。**改前/改后结果均在 PHASE9_REPORT.md 中并列登记**（不做静默调参）。
CLOSING_MARKERS = ("所以", "因此", "结论", "回到最初", "回到开头", "回到最开始", "回到那个",
                   "最后回到", "说到底", "归根结底", "总的来说", "总结一下", "答案是", "判断是",
                   "我们现在知道", "这就是", "意味着", "我想说的", "留下的")
#: 互动引导（内容型）标记
INTERACTION_MARKERS = ("想知道的", "看完", "你会怎么选", "你觉得", "如果是你", "留言", "评论区")
#: 信息增量点代理标记（**仅当 v3 元数据缺失时**作为 hook 间隔的替代依据，已登记）
INCREMENT_PROXY = ("但", "然而", "其实", "反而", "代价", "限制", "关键", "问题在于", "意外",
                   "没想到", "真正")

#: 评分权重（显式写在代码里；仅对**可评估**维度归一化）
SCORE_WEIGHTS = {
    "hook_structure": 0.25,
    "hook_interval": 0.20,
    "emotion_beats": 0.15,
    "cta": 0.15,
    "rhythm": 0.15,
    "ending": 0.10,
}
DIMENSION_STATUS_SCORE = {PASS: 1.0, WARN: 0.5, FAIL: 0.0}
#: 维度状态**可比秩**（仅用于跨稿件的逐维度比较，如 Phase 8 的 v2↔v3 判据①）：
#: `NOT_ASSESSABLE` 排在 `WARN` 之下只表示"该项未被标注/未被证明"，**不等于更差**；
#: 它不参与 `mechanical_score` 的分母（见 analyze）。
STATUS_RANK = {FAIL: 0, NOT_ASSESSABLE: 1, WARN: 2, PASS: 3}


def _segs(script: dict | None) -> list[dict]:
    return list((script or {}).get("segments") or [])


def _dur(seg: dict) -> float:
    try:
        return float(seg.get("duration_s") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _quote(text: str, limit: int = 60) -> str:
    t = " ".join(str(text or "").split())
    return t[:limit] + ("…" if len(t) > limit else "")


def has_v3_metadata(script: dict | None) -> dict:
    """检测 v3 元数据是否在位（决定哪些维度可评估）。"""
    segs = _segs(script)
    beats = [s.get("emotion_beat") for s in segs]
    devices = [s.get("retention_device") for s in segs]
    cta = (script or {}).get("cta_plan")
    hook_map = (script or {}).get("hook_map")
    return {"emotion_beat": any(b is not None for b in beats),
            "retention_device": any(d not in (None, "", "none") for d in devices),
            "cta_plan": bool(cta), "hook_map": bool(hook_map),
            "any": any(b is not None for b in beats) or bool(cta) or bool(hook_map)}


def dim_hook_structure(script: dict) -> dict:
    segs = _segs(script)
    th = THRESHOLDS["hook_window_s"]
    codes, ev, status = [], [], PASS
    if not segs:
        return {"dimension": "hook_structure", "status": NOT_ASSESSABLE,
                "codes": ["NO_SEGMENTS"], "evidence": [], "measured": {}}
    first = segs[0]
    open_end = _dur(first)
    opening_text = str(first.get("narration") or "")
    greeting_hits = [g for g in GREETING_BLACKLIST if g in opening_text]
    if open_end > th["value"]:
        status = WARN
        codes.append("HOOK_WINDOW_EXCEEDED")
    if greeting_hits:
        status = WARN if status == PASS else status
        codes.append("GREETING_BLACKLIST_HIT")
    ev.append({"segment_index": 0, "quote": _quote(opening_text),
               "why": "首段时长 {:.1f}s / 窗口 ≤{:.0f}s；寒暄命中 {}".format(
                   open_end, th["value"], greeting_hits or "无")})
    v3 = has_v3_metadata(script)
    if not v3["hook_map"]:
        codes.append("V3_METADATA_ABSENT")
    return {"dimension": "hook_structure", "status": status, "codes": codes, "evidence": ev,
            "measured": {"first_segment_s": open_end, "threshold_s": th["value"],
                         "greeting_hits": greeting_hits, "opening_chars": len(opening_text)},
            "basis": th["basis"]}


def dim_hook_interval(script: dict) -> dict:
    """相邻信息增量点（v3 `retention_device`，缺失时用代理标记）间隔 > 90s ⇒ WARN。"""
    segs = _segs(script)
    th = THRESHOLDS["hook_interval_max_s"]
    if not segs:
        return {"dimension": "hook_interval", "status": NOT_ASSESSABLE,
                "codes": ["NO_SEGMENTS"], "evidence": [], "measured": {}}
    v3 = has_v3_metadata(script)
    points, basis = [], ("segments[].retention_device（v3 元数据）" if v3["retention_device"]
                         else "intent_proxy（v3 元数据缺失时的替代依据，**已登记**）")
    t = 0.0
    codes, ev = [], []
    if not v3["retention_device"]:
        codes.append("V3_METADATA_ABSENT")
    for i, s in enumerate(segs):
        end = t + _dur(s)
        if v3["retention_device"]:
            marked = str(s.get("retention_device") or "").strip() not in ("", "none")
        else:
            marked = any(m in str(s.get("narration") or "") for m in INCREMENT_PROXY)
        if marked:
            points.append({"segment_index": i, "at_s": round(end, 2),
                           "quote": _quote(s.get("narration"))})
        t = end
    gaps, prev = [], 0.0
    for p in points:
        gaps.append(round(p["at_s"] - prev, 2))
        prev = p["at_s"]
    total = round(t, 2)
    if points:
        gaps.append(round(total - prev, 2))          # 末尾到片尾的间隔
    max_gap = max(gaps) if gaps else total
    status = PASS if points and max_gap <= th["value"] else (WARN if points else NOT_ASSESSABLE)
    if status == WARN:
        codes.append("HOOK_INTERVAL_EXCEEDED")
    if points:
        worst = max(range(len(gaps)), key=lambda i: gaps[i])
        ev.append({"segment_index": (points[worst]["segment_index"] if worst < len(points)
                                     else len(segs) - 1),
                   "quote": _quote(segs[min(worst, len(segs) - 1)].get("narration")),
                   "why": "最大间隔 {:.1f}s（阈值 {:.0f}s）".format(max_gap, th["value"])})
    return {"dimension": "hook_interval", "status": status, "codes": codes, "evidence": ev,
            "measured": {"increment_points": len(points), "gaps_s": gaps,
                         "max_gap_s": round(max_gap, 2), "total_s": total,
                         "threshold_s": th["value"], "basis_used": basis},
            "basis": th["basis"]}


def dim_emotion_beats(script: dict) -> dict:
    segs = _segs(script)
    th = THRESHOLDS["beat_run_max"]
    beats = [s.get("emotion_beat") for s in segs]
    v3 = has_v3_metadata(script)
    if not segs:
        return {"dimension": "emotion_beats", "status": NOT_ASSESSABLE,
                "codes": ["NO_SEGMENTS"], "evidence": [], "measured": {}}
    if not v3["emotion_beat"]:
        return {"dimension": "emotion_beats", "status": NOT_ASSESSABLE,
                "codes": ["V3_METADATA_ABSENT"], "evidence": [],
                "measured": {"coverage": 0.0, "illegal": [], "runs": []},
                "note": "v2 时代稿件无 emotion_beat ⇒ 结构码呈现，**不计 FAIL**",
                "basis": th["basis"]}
    codes, ev = [], []
    illegal = [{"segment_index": i, "value": b} for i, b in enumerate(beats)
               if b is not None and b not in EMOTION_BEATS]
    runs, run = [], 1
    for i in range(1, len(beats)):
        if beats[i] is not None and beats[i] == beats[i - 1]:
            run += 1
            if run >= th["value"]:
                runs.append({"segment_index": i, "beat": beats[i], "run": run})
                ev.append({"segment_index": i, "quote": _quote(segs[i].get("narration")),
                           "why": "连续 {} 个同类节拍 {}（阈值 <{}）".format(run, beats[i],
                                                                          th["value"])})
        else:
            run = 1
    coverage = round(sum(1 for b in beats if b in EMOTION_BEATS) / len(segs), 3)
    if illegal:
        codes.append("BEAT_ENUM_ILLEGAL")
    if runs:
        codes.append("BEAT_RUN3")
    if coverage < 1.0 and not illegal:
        codes.append("BEAT_COVERAGE_PARTIAL")
    status = FAIL if illegal else (WARN if (runs or coverage < 1.0) else PASS)
    return {"dimension": "emotion_beats", "status": status, "codes": codes, "evidence": ev,
            "measured": {"coverage": coverage, "illegal": illegal, "runs": runs,
                         "sequence": beats}, "basis": th["basis"]}


def dim_cta(script: dict) -> dict:
    segs = _segs(script)
    th = THRESHOLDS["cta_max"]
    v3 = has_v3_metadata(script)
    codes, ev = [], []
    if v3["cta_plan"]:
        items = [{"at_segment": c.get("at_segment"), "type": c.get("type"),
                  "line": str(c.get("line") or "")} for c in (script.get("cta_plan") or [])]
        basis = "cta_plan（v3 元数据）"
    else:
        items = [{"at_segment": i, "type": "text_proxy", "line": str(s.get("narration") or "")}
                 for i, s in enumerate(segs)
                 if any(m in str(s.get("narration") or "") for m in INTERACTION_MARKERS)]
        basis = "narration 互动句代理（v3 元数据缺失时的替代依据，**已登记**）"
        codes.append("V3_METADATA_ABSENT")
    # P10-1：`at_segment` 语义**钉死为 0-based**（0 = 第一段）；越界/非整数 ⇒ 结构违规码（不计 FAIL）
    for it in items:
        if it["type"] == "text_proxy":
            continue
        at = it["at_segment"]
        if isinstance(at, bool) or not isinstance(at, int):
            codes.append("CTA_AT_SEGMENT_INVALID")
            ev.append({"segment_index": None, "quote": _quote(it["line"]),
                       "why": "at_segment={!r} 非整数（须为 0-based 段落下标）".format(at)})
        elif segs and not (0 <= at <= len(segs) - 1):
            codes.append("CTA_AT_SEGMENT_OUT_OF_RANGE")
            ev.append({"segment_index": None, "quote": _quote(it["line"]),
                       "why": "at_segment={} 越界（0-based，有效范围 0..{}）".format(
                           at, len(segs) - 1)})
    bare = [it for it in items if any(b in it["line"] for b in BARE_CTA)]
    for it in bare:
        ev.append({"segment_index": it["at_segment"], "quote": _quote(it["line"]),
                   "why": "命中裸话术黑名单"})
    if not items:
        status = NOT_ASSESSABLE
        codes.append("CTA_ABSENT")
    else:
        status = PASS
        if len(items) > th["value"]:
            status = WARN
            codes.append("CTA_TOO_MANY")
        if any(c in codes for c in ("CTA_AT_SEGMENT_INVALID", "CTA_AT_SEGMENT_OUT_OF_RANGE")):
            status = WARN if status == PASS else status
        if bare:
            status = FAIL
            codes.append("CTA_BARE_CLICHE")
    if items and not bare and len(items) <= th["value"]:
        ev.append({"segment_index": items[0]["at_segment"], "quote": _quote(items[0]["line"]),
                   "why": "共 {} 处互动引导（≤{}），无裸话术".format(len(items), th["value"])})
    return {"dimension": "cta", "status": status, "codes": codes, "evidence": ev,
            "measured": {"count": len(items), "bare_count": len(bare), "items": items,
                         "threshold": th["value"], "basis_used": basis,
                         "at_segment_semantics": "0-based（P10-1 钉死）",
                         "segment_count": len(segs)},
            "basis": th["basis"]}


def dim_rhythm(script: dict) -> dict:
    segs = _segs(script)
    long_th = THRESHOLDS["segment_long_s"]
    short_th = THRESHOLDS["segment_short_s"]
    if not segs:
        return {"dimension": "rhythm", "status": NOT_ASSESSABLE, "codes": ["NO_SEGMENTS"],
                "evidence": [], "measured": {}}
    durs = [_dur(s) for s in segs]
    chars = [len(str(s.get("narration") or "")) for s in segs]
    dens = [round(c / d, 2) if d > 0 else None for c, d in zip(chars, durs)]
    long_idx = [i for i, d in enumerate(durs) if d > long_th["value"]]
    short_idx = [i for i, d in enumerate(durs) if 0 < d < short_th["value"]]
    codes, ev = [], []
    for i in long_idx:
        ev.append({"segment_index": i, "quote": _quote(segs[i].get("narration")),
                   "why": "段落时长 {:.1f}s > {:.0f}s".format(durs[i], long_th["value"])})
        codes.append("SEGMENT_TOO_LONG")
    if short_idx:
        codes.append("SEGMENT_TOO_SHORT")
        ev.append({"segment_index": short_idx[0], "quote": _quote(segs[short_idx[0]].get(
            "narration")), "why": "存在 {} 个 <{:.0f}s 的短段".format(len(short_idx),
                                                                   short_th["value"])})
    status = WARN if (long_idx or short_idx) else PASS
    return {"dimension": "rhythm", "status": status, "codes": codes, "evidence": ev,
            "measured": {"segment_count": len(segs), "durations_s": durs,
                         "total_s": round(sum(durs), 1),
                         "mean_s": round(sum(durs) / len(durs), 1),
                         "min_s": min(durs), "max_s": max(durs),
                         "chars_per_s": dens,
                         "long_segments": long_idx, "short_segments": short_idx},
            "basis": "{}；{}".format(long_th["basis"], short_th["basis"])}


def dim_ending(script: dict) -> dict:
    segs = _segs(script)
    th = THRESHOLDS["ending_interaction_max"]
    if not segs:
        return {"dimension": "ending", "status": NOT_ASSESSABLE, "codes": ["NO_SEGMENTS"],
                "evidence": [], "measured": {}}
    text = str(segs[-1].get("narration") or "")
    closing = [m for m in CLOSING_MARKERS if m in text]
    interaction = [m for m in INTERACTION_MARKERS if m in text]
    codes, ev = [], []
    status = PASS
    if not closing:
        status = WARN
        codes.append("ENDING_NO_CLOSURE")
    if len(interaction) > th["value"]:
        status = WARN
        codes.append("ENDING_TOO_MANY_INTERACTIONS")
    ev.append({"segment_index": len(segs) - 1, "quote": _quote(text),
               "why": "收束标记 {}；互动标记 {}（≤{}）".format(closing or "无", interaction or "无",
                                                             th["value"])})
    return {"dimension": "ending", "status": status, "codes": codes, "evidence": ev,
            "measured": {"closing_markers": closing, "interaction_markers": interaction,
                         "interaction_count": len(interaction), "chars": len(text)},
            "basis": th["basis"]}


DIMENSIONS = ("hook_structure", "hook_interval", "emotion_beats", "cta", "rhythm", "ending")


def analyze(script: dict, *, source: dict | None = None) -> dict:
    """机械层总评（纯函数、确定性）。`source` 记录输入出处（供报告可追溯）。"""
    dims = {name: fn(script) for name, fn in (("hook_structure", dim_hook_structure),
                                              ("hook_interval", dim_hook_interval),
                                              ("emotion_beats", dim_emotion_beats),
                                              ("cta", dim_cta), ("rhythm", dim_rhythm),
                                              ("ending", dim_ending))}
    assessable = {k: v for k, v in dims.items() if v["status"] != NOT_ASSESSABLE}
    wsum = sum(SCORE_WEIGHTS[k] for k in assessable)
    if wsum > 0:
        score = round(sum(SCORE_WEIGHTS[k] * DIMENSION_STATUS_SCORE[v["status"]]
                          for k, v in assessable.items()) / wsum * 100, 1)
        score_basis = "对**可评估**维度按 SCORE_WEIGHTS 归一化（NOT_ASSESSABLE 不计入分母）"
    else:
        score, score_basis = None, "无可评估维度 ⇒ 不给分（禁止编造）"
    structural = {}
    for v in dims.values():
        for c in v["codes"]:
            if c.startswith("V3_METADATA_ABSENT"):
                structural[c] = structural.get(c, 0) + 1
    body = {
        "schema": SCHEMA, "version": VERSION,
        "generation_method": "deterministic-offline（纯函数、零 LLM、零 I/O）",
        # 确定性语义：**哈希绑定输入脚本内容**（script_sha256），来源标签 `source` 仅为可追溯元数据、
        # 不参与哈希 ⇒ 同一脚本无论来源标签如何，机械层输出哈希一致。
        "script_sha256": sha256_text(canonical(script)),
        "source": source or {},
        "v3_metadata_present": has_v3_metadata(script),
        "thresholds": THRESHOLDS, "score_weights": SCORE_WEIGHTS,
        "out_of_scope": OUT_OF_SCOPE,
        "dimensions": dims,
        "status_counts": {s: sum(1 for v in dims.values() if v["status"] == s)
                          for s in (PASS, WARN, FAIL, NOT_ASSESSABLE)},
        "structural_codes": structural,
        "structural_code_note": "V3_METADATA_ABSENT 等结构码**单独计数、不计 FAIL**"
                               "（缺标注 ≠ 做得差）",
        "mechanical_score": score, "mechanical_score_basis": score_basis,
        "segment_count": len(_segs(script)),
        "total_duration_s": round(sum(_dur(s) for s in _segs(script)), 1),
        "not_a_fact_check": "本评分**不评事实对错**（out_of_scope 见上）",
        "applied": False, "executed": False, "requires_human_decision": True,
        "note": "只读评分：不接入任何生产闸门、不阻断任务、不自动改稿",
    }
    body["artifact_hash"] = sha256_text(canonical(_body_wo_hash(body)))
    return body


def _body_wo_hash(body: dict) -> dict:
    """哈希覆盖的字段：排除自身哈希与**来源标签** `source`（非分析结果）。"""
    return {k: v for k, v in body.items() if k not in ("artifact_hash", "source")}


def report_hash(rep: dict) -> str:
    return sha256_text(canonical(_body_wo_hash(rep)))


def validate(rep: dict) -> list[str]:
    errs = []
    if rep.get("schema") != SCHEMA:
        errs.append("schema 非法")
    if rep.get("artifact_hash") != report_hash(rep):
        errs.append("artifact_hash 不一致")
    for d in DIMENSIONS:
        if d not in (rep.get("dimensions") or {}):
            errs.append("缺少维度 {}".format(d))
    for name, v in (rep.get("dimensions") or {}).items():
        if v["status"] not in (PASS, WARN, FAIL, NOT_ASSESSABLE):
            errs.append("{}: status 非法".format(name))
        if v["status"] in (WARN, FAIL) and not v.get("evidence"):
            errs.append("{}: WARN/FAIL 必须带 evidence".format(name))
    sc = rep.get("mechanical_score")
    if sc is not None and not (0 <= sc <= 100):
        errs.append("mechanical_score 越界")
    return errs
