# -*- coding: utf-8 -*-
"""6-A/M1 + **6-B/M1** —— Directorial Quality 只读度量层（DQ-1 … DQ-8）。

设计契约（严格只读、零强制、零动作）：
  · 只测量/只诊断：**不换素材、不剪辑、不重渲染、不写 DB、不写产物**；
  · **不入生产判定链**：不接入 `TASK_BLOCKED`、不改变 `render_output`、不自动修复；
  · 语义类项目（Hook 相关性、旁白↔画面一致、片尾语义）必须显式区分
    `MATCH / MISMATCH / UNKNOWN / NOT_ASSESSABLE`，且**绝不允许把 UNKNOWN 当 PASS**；
    语义判定**复用既有只读证据**（4-B/5-A/5-D/Judge 的已产报告）；无证据即 `NOT_ASSESSABLE`；
  · 所有门限来自显式 `policy`（`DEFAULT_POLICY` 为 advisory 建议值）；输出恒带 `enforced: False`；
  · 不修改任何 5.x 冻结评估件（Judge / truth set / threshold / multimodal evaluator）。

指标口径（6-A/M1 定义 DQ-1…DQ-7；**6-B/M1 追加 DQ-8**，并统一补 `findings` 证据锚点）：
  DQ-1 Hook 视觉相关性       S01（或指定 hook 镜）在既有只读证据中的层判定
  DQ-2 素材复用/重复         唯一素材数、单素材最大上屏占比
  DQ-3 静态保持时长          逐镜素材保持 + 成片 freezedetect 冻结块
  DQ-4 视觉密度              镜头变化/分钟、唯一素材/分钟、冻结块数/分钟
  DQ-5 高潮视觉覆盖          核心论点镜头内的素材多样性/保持时长（**代理指标**，语义部分单列）
  DQ-6 片尾完整性            结构项（outro 关键词/末镜更换/尾部静音）+ 语义项（单列）
  DQ-7 总评                  四态计数 + 汇总（UNKNOWN ≠ PASS）
  DQ-8 视觉语义支撑（逐镜）  **6-B/M1 新增**：全片逐镜复用 4-B/5-A/5-D/Judge 证据，
                            任一镜头 MISMATCH → FAIL；MATCH 占比 ≥ 阈值 → PASS；其余 → UNKNOWN

证据可回溯契约（6-B/M1）：
  **每一个 FAIL 必须在 `findings` 里给出可定位锚点**（`scene_id` / `asset_id` /
  `start_s`+`end_s` 时间区间 / 证据层名），使人工可以直接核对，而不只是看到一句结论。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

STATE_PASS = "PASS"
STATE_FAIL = "FAIL"
STATE_UNKNOWN = "UNKNOWN"
STATE_NOT_ASSESSABLE = "NOT_ASSESSABLE"
STATES = (STATE_PASS, STATE_FAIL, STATE_UNKNOWN, STATE_NOT_ASSESSABLE)

DEFAULT_POLICY = {
    # ---- 2026-10-20：阈值改按**外部标杆**标定（原值是"内部历史"自洽口径）----
    # 依据：知识区中腰部 UP 主 ≈15 次变化/分钟；王骁 ≈20–40；燕三 ≈60+。
    # 旧值（2.0 次/分钟、单镜 25s）会让"18.4s/镜、26 次切换/464s"的成片全部 PASS ——
    # 那是自洽，不是好看。EP3 实测 changes/min=3.49：旧口径 PASS，新口径 FAIL。
    "max_asset_share": 0.25,          # 单素材最大上屏占比（旧 0.35）
    "min_unique_assets": 6,           # 唯一素材数下限（21 镜口径）
    "max_hold_s": 10.0,               # 单镜静态保持上限（旧 25.0；行业 4–8s，宽到 10）
    "max_over_hold_share": 0.05,      # 超上限镜头占比（旧 0.20）
    "min_scene_changes_per_min": 15.0,  # 视觉变化密度下限（旧 2.0）
    "min_distinct_assets_in_core": 6,  # 核心论点镜头的素材多样性下限
    "max_hold_in_core_s": 12.0,       # 旧 25.0
    "max_tail_silence_s": 3.0,        # 旧 5.0
    # 6-B/M1：DQ-8 的语义"多数判定"阈值（与 DQ-5 语义项同一规则形状：任一 MISMATCH 即 FAIL）
    "min_semantic_match_share": 0.5,
    "outro_keywords": ("感谢观看", "感谢收看", "订阅", "下期", "再见", "我们下期", "收束", "结语"),
    "outro_last_scenes": 2,           # 只在最后 N 镜里认可 outro 关键词
    "core_keywords": ("AlphaGeometry", "Lean", "mathlib", "四色定理", "开普勒", "计算机",
                      "机器", "形式化", "证明", "检查", "验证"),
}

READONLY = {"read_only": True, "enforced": False, "advisory": True}
#: 语义项统一说明：M1 不新算语义，只复用既有只读证据
SEMANTIC_NOTE = ("语义判定复用既有只读证据（4-B/5-A/5-D/Judge）；无证据 → NOT_ASSESSABLE；"
                 "证据存在但不充分 → UNKNOWN；UNKNOWN 不得视为 PASS")


def _v(state: str, **kw) -> dict:
    d = {"state": state, "read_only": True, "enforced": False, "advisory": True}
    d.update(kw)
    return d


def _finding(kind: str, **kw) -> dict:
    """统一**证据锚点**（6-B/M1 契约）：FAIL 必须能回溯到 scene / asset / 时间区间 / 证据层。"""
    d = {"kind": kind}
    d.update({k: v for k, v in kw.items() if v is not None})
    return d


def _win(s: dict) -> list:
    """镜头时间区间 [start_s, end_s]（用于证据定位）。"""
    try:
        return [round(float(s.get("start_s", 0.0)), 3), round(float(s.get("end_s", 0.0)), 3)]
    except (TypeError, ValueError):
        return []


# ------------------------------------------------- DQ-1 Hook 视觉相关性
def hook_relevance(evidence: dict | None, hook_scene: str = "S01", distinct_in_hook=None) -> dict:
    """`evidence`：{scene_id: {layer: state}}（来自既有只读评估报告）。无证据 → NOT_ASSESSABLE。"""
    if not evidence:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-1", hook_scene=hook_scene,
                  semantic=True, reason="未提供既有只读多模态证据", note=SEMANTIC_NOTE)
    layers = {k: str(v).upper() for k, v in (evidence.get(hook_scene) or {}).items()}
    if not layers:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-1", hook_scene=hook_scene, semantic=True,
                  reason="证据中无该镜头的层判定", note=SEMANTIC_NOTE,
                  findings=[_finding("no_layer_verdict_for_hook", scene_id=hook_scene)])
    has_match = any(x == "MATCH" for x in layers.values())
    has_mismatch = any(x == "MISMATCH" for x in layers.values())
    if has_match:
        st = STATE_PASS
    elif has_mismatch:
        st = STATE_FAIL
    else:
        st = STATE_UNKNOWN
    # 6-B/M1：无论 PASS/FAIL/UNKNOWN 都记录**可定位锚点**（哪个镜头的哪些层给了什么判定）
    finds = [_finding("hook_layer_verdict", scene_id=hook_scene, layer=k, verdict=x)
             for k, x in sorted(layers.items()) if x != "MATCH"]
    if has_mismatch:
        finds.insert(0, _finding("hook_semantic_mismatch", scene_id=hook_scene,
                                 layers={k: x for k, x in layers.items() if x == "MISMATCH"}))
    if not finds and has_match:
        finds = [_finding("hook_match", scene_id=hook_scene, layers=layers)]
    return _v(st, metric="DQ-1", hook_scene=hook_scene, semantic=True, layers=layers,
              distinct_assets_used_in_hook=distinct_in_hook, note=SEMANTIC_NOTE,
              findings=finds)


# ------------------------------------------------- DQ-2 素材复用/重复
def asset_reuse(timeline: list[dict], policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not timeline:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-2", reason="无时间轴/镜头")
    secs, scenes, wins = {}, {}, {}
    total = 0.0
    for s in timeline:
        d = max(float(s.get("end_s", 0)) - float(s.get("start_s", 0)), 0.0)
        a = (s.get("selected_asset") or {}).get("asset_id") or "SOLID_COLOR"
        secs[a] = secs.get(a, 0.0) + d
        scenes[a] = scenes.get(a, 0) + 1
        wins.setdefault(a, []).append({"scene_id": s.get("scene_id"), "window": _win(s)})
        total += d
    shares = {k: (v / total if total else 0.0) for k, v in secs.items()}
    max_share = max(shares.values()) if shares else 0.0
    uniq = len(secs)
    fail = max_share > p["max_asset_share"] or uniq < p["min_unique_assets"]
    st = STATE_FAIL if fail else STATE_PASS
    findings = []
    if fail:
        for a, sh in sorted(shares.items(), key=lambda kv: -kv[1]):
            if sh > p["max_asset_share"]:
                findings.append(_finding("asset_share_exceeds", asset_id=a,
                                         share=round(sh, 4), seconds=round(secs[a], 3),
                                         scenes=scenes[a], scene_windows=wins[a]))
        if uniq < p["min_unique_assets"]:
            findings.append(_finding("unique_assets_below_min", unique_assets=uniq,
                                     required=p["min_unique_assets"],
                                     missing=p["min_unique_assets"] - uniq,
                                     asset_ids=sorted(secs)))
    return _v(st, metric="DQ-2", scenes=len(timeline), unique_assets=uniq,
              max_asset_share=round(max_share, 4), total_s=round(total, 3),
              per_asset={k: {"scenes": scenes[k], "seconds": round(secs[k], 3),
                             "share": round(shares[k], 4)} for k in secs},
              findings=findings,
              threshold={"max_asset_share": p["max_asset_share"],
                         "min_unique_assets": p["min_unique_assets"]})


# ------------------------------------------------- DQ-3 静态保持时长
def static_hold(timeline: list[dict], freeze_blocks: list[dict] | None = None,
                policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not timeline:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-3", reason="无时间轴/镜头")
    holds = []
    for s in timeline:
        holds.append({"scene_id": s.get("scene_id"),
                      "hold_s": round(max(float(s.get("end_s", 0)) - float(s.get("start_s", 0)),
                                          0.0), 3),
                      "asset": (s.get("selected_asset") or {}).get("asset_id"),
                      "window": _win(s)})
    over = [h for h in holds if h["hold_s"] > p["max_hold_s"]]
    share_over = len(over) / len(holds)
    freeze = None
    if freeze_blocks:
        fr = [b.get("dur") or 0.0 for b in freeze_blocks]
        freeze = {"blocks": len(fr), "longest_s": round(max(fr), 3) if fr else 0.0,
                  "total_s": round(sum(fr), 3),
                  "longest_block": max(freeze_blocks, key=lambda b: b.get("dur") or 0.0)
                  if freeze_blocks else None}
    fail = share_over > p["max_over_hold_share"]
    st = STATE_FAIL if fail else STATE_PASS
    findings = []
    if fail:
        findings = [_finding("hold_exceeds_max", scene_id=h["scene_id"], asset_id=h["asset"],
                             hold_s=h["hold_s"], window=h["window"])
                    for h in sorted(over, key=lambda x: -x["hold_s"])]
        findings.append(_finding("over_hold_share_exceeds", over=len(over), scenes=len(holds),
                                 share=round(share_over, 4),
                                 required_max_share=p["max_over_hold_share"]))
        if freeze:
            findings.append(_finding("freeze_profile", blocks=freeze["blocks"],
                                     longest_s=freeze["longest_s"],
                                     longest_block=freeze["longest_block"]))
    return _v(st, metric="DQ-3", scenes=len(holds), mean_hold_s=round(
        sum(h["hold_s"] for h in holds) / len(holds), 3),
        max_hold_s=max(h["hold_s"] for h in holds),
        holds_over_threshold=len(over), share_over_threshold=round(share_over, 4),
        holds=holds, freeze_profile=freeze, findings=findings,
        threshold={"max_hold_s": p["max_hold_s"],
                   "max_over_hold_share": p["max_over_hold_share"]})


# ------------------------------------------------- DQ-4 视觉密度
def visual_density(timeline: list[dict], freeze_blocks: list[dict] | None = None,
                   policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not timeline:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-4", reason="无时间轴/镜头")
    total = sum(max(float(s.get("end_s", 0)) - float(s.get("start_s", 0)), 0.0) for s in timeline)
    if total <= 0:
        return _v(STATE_UNKNOWN, metric="DQ-4", reason="时间轴总长为 0")
    uniq = len({(s.get("selected_asset") or {}).get("asset_id") or "SOLID_COLOR"
                for s in timeline})
    changes_per_min = len(timeline) / (total / 60.0)
    uniq_per_min = uniq / (total / 60.0)
    st = STATE_PASS if changes_per_min >= p["min_scene_changes_per_min"] else STATE_FAIL
    longest = max(timeline, key=lambda s: float(s.get("end_s", 0)) - float(s.get("start_s", 0)))
    out = {"metric": "DQ-4", "scene_changes_per_min": round(changes_per_min, 3),
           "unique_assets_per_min": round(uniq_per_min, 3), "scenes": len(timeline),
           "unique_assets": uniq, "total_s": round(total, 3),
           "change_points": [round(float(s.get("start_s", 0)), 3) for s in timeline][:64],
           "longest_scene": {"scene_id": longest.get("scene_id"), "window": _win(longest),
                             "hold_s": round(float(longest.get("end_s", 0))
                                             - float(longest.get("start_s", 0)), 3)},
           "threshold": {"min_scene_changes_per_min": p["min_scene_changes_per_min"]}}
    if freeze_blocks:
        out["freeze_blocks_per_min"] = round(len(freeze_blocks) / (total / 60.0), 3)
    if st == STATE_FAIL:
        out["findings"] = [
            _finding("scene_changes_below_min", scene_changes_per_min=round(changes_per_min, 3),
                     required=p["min_scene_changes_per_min"], scenes=len(timeline),
                     total_s=round(total, 3), mean_scene_s=round(total / len(timeline), 3)),
            _finding("longest_static_scene", scene_id=longest.get("scene_id"),
                     window=_win(longest),
                     hold_s=round(float(longest.get("end_s", 0))
                                  - float(longest.get("start_s", 0)), 3))]
    else:
        out["findings"] = []
    return _v(st, **out)


# ------------------------------------------------- DQ-5 高潮视觉覆盖
def climax_coverage(script_segments: list[dict], timeline: list[dict],
                    evidence: dict | None = None, policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not script_segments or not timeline:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-5", reason="缺脚本或时间轴")
    core = []
    for i, seg in enumerate(script_segments):
        txt = seg.get("narration", "") or ""
        hits = [k for k in p["core_keywords"] if k in txt]
        if hits:
            tl = timeline[i] if i < len(timeline) else {}
            core.append({"scene_index": i + 1, "scene_id": tl.get("scene_id"),
                         "asset": (tl.get("selected_asset") or {}).get("asset_id"),
                         "hits": hits[:4],
                         "window": _win(tl) if tl else None,
                         "hold_s": round(max(float(tl.get("end_s", 0))
                                             - float(tl.get("start_s", 0)), 0.0), 3)
                         if tl else None})
    if not core:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-5", reason="未检测到核心论点镜头（关键词不适用）",
                  proxy=True, note=SEMANTIC_NOTE)
    assets = {c["asset"] for c in core}
    holds = [c["hold_s"] for c in core if c["hold_s"]]
    mean_hold = round(sum(holds) / len(holds), 3) if holds else None
    fail = len(assets) < p["min_distinct_assets_in_core"] \
        or (mean_hold is not None and mean_hold > p["max_hold_in_core_s"])
    # 语义部分：只有拿到既有只读证据才给三态，否则 NOT_ASSESSABLE（绝不并入 PASS）；
    # 规则：任一核心镜头 MISMATCH → MISMATCH（必须暴露）；MATCH 过半 → PASS；其余 → UNKNOWN
    sem = STATE_NOT_ASSESSABLE
    sem_counts = {}
    mismatch_scenes = []
    if evidence:
        states = []
        for c in core:
            lay = {k: str(v).upper() for k, v in (evidence.get(c["scene_id"]) or {}).items()}
            if any(x == "MISMATCH" for x in lay.values()):
                mismatch_scenes.append({"scene_id": c["scene_id"], "window": c.get("window"),
                                        "asset_id": c.get("asset"),
                                        "layers": {k: x for k, x in lay.items()
                                                   if x == "MISMATCH"}})
            states.extend(lay.values())
        if states:
            sem_counts = {s: states.count(s) for s in set(states)}
            if any(x == "MISMATCH" for x in states):
                sem = STATE_FAIL
            elif states.count("MATCH") >= max(1, len(core) // 2):
                sem = STATE_PASS
            else:
                sem = STATE_UNKNOWN
    findings = []
    if fail:
        if len(assets) < p["min_distinct_assets_in_core"]:
            findings.append(_finding("distinct_assets_in_core_below_min",
                                     distinct_assets_in_core=len(assets),
                                     required=p["min_distinct_assets_in_core"],
                                     core_scene_ids=[c["scene_id"] for c in core],
                                     distinct_asset_ids=sorted(x for x in assets if x)))
        if mean_hold is not None and mean_hold > p["max_hold_in_core_s"]:
            findings.append(_finding("mean_hold_in_core_exceeds", mean_hold_in_core_s=mean_hold,
                                     required=p["max_hold_in_core_s"],
                                     longest=[c for c in core
                                              if (c.get("hold_s") or 0)
                                              > p["max_hold_in_core_s"]][:12]))
    if mismatch_scenes:
        findings.append(_finding("semantic_mismatch_in_core", scenes=mismatch_scenes,
                                 semantic_counts=sem_counts))
    return _v(STATE_FAIL if fail else STATE_PASS, metric="DQ-5", proxy=True,
              core_scenes=len(core), distinct_assets_in_core=len(assets),
              mean_hold_in_core_s=mean_hold, semantic_state=sem, semantic_counts=sem_counts,
              note=SEMANTIC_NOTE + "；DQ-5 结构项为**代理指标**（素材多样性/保持时长），语义项单列",
              core_detail=core[:12], findings=findings,
              threshold={"min_distinct_assets_in_core": p["min_distinct_assets_in_core"],
                         "max_hold_in_core_s": p["max_hold_in_core_s"]})


# ------------------------------------------------- DQ-6 片尾完整性
def ending_completeness(script_segments: list[dict], timeline: list[dict],
                        tail_silence_s=None, evidence: dict | None = None,
                        policy: dict | None = None) -> dict:
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not script_segments or not timeline:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-6", reason="缺脚本或时间轴")
    n = len(script_segments)
    tail_idx = set(range(max(n - p["outro_last_scenes"], 0), n))
    outro_hits = [{"scene_index": i + 1, "kw": k}
                  for i, s in enumerate(script_segments) if i in tail_idx
                  for k in p["outro_keywords"] if k in (s.get("narration") or "")]
    last_assets = [((timeline[i].get("selected_asset") or {}).get("asset_id"))
                   for i in range(max(n - 2, 0), min(n, len(timeline)))]
    tail_scene_refs = [{"scene_index": i + 1,
                        "scene_id": (timeline[i] if i < len(timeline) else {}).get("scene_id"),
                        "window": _win(timeline[i]) if i < len(timeline) else None,
                        "asset_id": (timeline[i] if i < len(timeline) else {})
                        .get("selected_asset", {}).get("asset_id") if i < len(timeline) else None,
                        "narration_head": ((script_segments[i].get("narration") or "")[:40])}
                       for i in sorted(tail_idx)]
    structural_fail = (not outro_hits) or (tail_silence_s is not None
                                          and tail_silence_s > p["max_tail_silence_s"])
    sem = STATE_NOT_ASSESSABLE
    if evidence:
        states = []
        for i in range(max(n - p["outro_last_scenes"], 0), n):
            sid = (timeline[i] if i < len(timeline) else {}).get("scene_id")
            states.extend(str(v).upper() for v in (evidence.get(sid) or {}).values())
        if states:
            sem = STATE_PASS if any(x == "MATCH" for x in states) else (
                STATE_FAIL if all(x == "MISMATCH" for x in states) else STATE_UNKNOWN)
    findings = []
    if structural_fail:
        if not outro_hits:
            findings.append(_finding("no_outro_keyword_in_tail", tail_scenes=tail_scene_refs,
                                     keywords=list(p["outro_keywords"]),
                                     last_n_scenes=p["outro_last_scenes"]))
        if tail_silence_s is not None and tail_silence_s > p["max_tail_silence_s"]:
            _last = timeline[-1] if timeline else {}
            findings.append(_finding("tail_silence_exceeds", tail_silence_s=tail_silence_s,
                                     required=p["max_tail_silence_s"],
                                     last_scene={"scene_id": _last.get("scene_id"),
                                                 "window": _win(_last) if _last else None},
                                     timeline_total_s=(_win(_last)[1] if _last else None)))
    return _v(STATE_FAIL if structural_fail else STATE_PASS, metric="DQ-6",
              outro_keyword_hits=outro_hits, tail_scene_assets=last_assets,
              tail_silence_s=tail_silence_s, semantic_state=sem, note=SEMANTIC_NOTE,
              tail_scene_detail=tail_scene_refs, findings=findings,
              threshold={"outro_keywords": list(p["outro_keywords"]),
                         "outro_last_scenes": p["outro_last_scenes"],
                         "max_tail_silence_s": p["max_tail_silence_s"]})


# ------------------------------------------------- DQ-8 视觉语义支撑（逐镜，6-B/M1 新增）
def narration_visual_support(script_segments: list[dict], timeline: list[dict],
                             evidence: dict | None = None, policy: dict | None = None) -> dict:
    """**逐镜**旁白↔画面的语义支撑度：只复用既有只读证据（4-B/5-A/5-D/Judge），不新算语义。

    判定（与 DQ-5 语义项同一规则形状，避免新造阈值）：
      · 无时间轴 / 无脚本 → `NOT_ASSESSABLE`；无证据 → `NOT_ASSESSABLE`（不猜）；
      · 任一镜头存在 `MISMATCH` → `FAIL`（必须暴露，且逐镜给出锚点）；
      · 否则 `MATCH 占比 ≥ min_semantic_match_share` → `PASS`；
      · 其余（证据存在但不足）→ `UNKNOWN`（**绝不并入 PASS**）。
    """
    p = {**DEFAULT_POLICY, **(policy or {})}
    if not timeline or not script_segments:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-8", semantic=True,
                  reason="缺脚本或时间轴", note=SEMANTIC_NOTE)
    if not evidence:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-8", semantic=True,
                  reason="未提供既有只读多模态证据", note=SEMANTIC_NOTE,
                  findings=[_finding("no_evidence")])
    per_scene, states = [], []
    for i, seg in enumerate(script_segments):
        tl = timeline[i] if i < len(timeline) else {}
        sid = tl.get("scene_id")
        lay = {k: str(v).upper() for k, v in (evidence.get(sid) or {}).items()}
        if not lay:
            continue
        states.extend(lay.values())
        per_scene.append({"scene_index": i + 1, "scene_id": sid, "window": _win(tl) if tl else None,
                          "asset_id": (tl.get("selected_asset") or {}).get("asset_id"),
                          "layers": lay,
                          "verdict": ("MISMATCH" if any(x == "MISMATCH" for x in lay.values())
                                      else ("MATCH" if any(x == "MATCH" for x in lay.values())
                                            else "UNKNOWN"))})
    if not states:
        return _v(STATE_NOT_ASSESSABLE, metric="DQ-8", semantic=True,
                  reason="证据中没有任何镜头的层判定", note=SEMANTIC_NOTE,
                  findings=[_finding("no_layer_verdict_in_evidence")])
    counts = {s: states.count(s) for s in set(states)}
    match_share = counts.get("MATCH", 0) / len(states)
    mismatch_scenes = [x for x in per_scene if x["verdict"] == "MISMATCH"]
    unknown_scenes = [{"scene_id": x["scene_id"], "window": x["window"],
                       "layers": {k: v for k, v in x["layers"].items() if v != "MATCH"}}
                      for x in per_scene if x["verdict"] == "UNKNOWN"]
    if mismatch_scenes:
        st = STATE_FAIL
    elif match_share >= p["min_semantic_match_share"]:
        st = STATE_PASS
    else:
        st = STATE_UNKNOWN
    findings = []
    if st == STATE_FAIL:
        findings.append(_finding("semantic_mismatch_scenes", scenes=mismatch_scenes,
                                 layer_counts=counts))
    elif st == STATE_UNKNOWN:
        findings.append(_finding("insufficient_semantic_evidence", layer_counts=counts,
                                 match_share=round(match_share, 4),
                                 unknown_scene_count=len(unknown_scenes),
                                 unknown_scenes=unknown_scenes[:12]))
    else:
        findings.append(_finding("semantic_match_majority", layer_counts=counts,
                                 match_share=round(match_share, 4)))
    return _v(st, metric="DQ-8", semantic=True, scenes=len(timeline),
              scenes_with_evidence=len(per_scene), layer_counts=counts,
              match_share=round(match_share, 4), mismatch_scene_count=len(mismatch_scenes),
              unknown_scene_count=len(unknown_scenes), per_scene=per_scene[:24],
              findings=findings, note=SEMANTIC_NOTE + "；DQ-8 为 6-B/M1 新增的**逐镜**语义支撑指标",
              threshold={"min_semantic_match_share": p["min_semantic_match_share"]})


# ------------------------------------------------- DQ-7 总评
def summarize_direction(metrics: dict) -> dict:
    """DQ-7 总评。

    6-B/M1 收紧（与 PI 侧 M3 同一口径）：混有 `NOT_ASSESSABLE` 时整体不得给 PASS。
    优先级：`FAIL > UNKNOWN > NOT_ASSESSABLE > PASS`；本函数只用于**汇总报告**，不参与任何阻断。
    """
    counts = {s: 0 for s in STATES}
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
    sem = [k for k, v in metrics.items()
           if (v or {}).get("semantic") or (v or {}).get("semantic_state")]
    findings = [{"metric": k, "findings": (v or {}).get("findings")}
                for k, v in sorted(metrics.items())
                if (v or {}).get("state") == STATE_FAIL and (v or {}).get("findings")]
    return {"counts": counts, "failed_metrics": sorted(fails), "overall": overall,
            "semantic_metrics": sorted(sem),
            "semantic_states": {k: ((metrics[k] or {}).get("semantic_state")
                                    or (metrics[k] or {}).get("state")) for k in sem},
            "fail_findings": findings,
            "unknown_is_not_pass": True, **READONLY}


# ------------------------------------------------- 只读测量：freezedetect
_FR_START = re.compile(r"freeze_start:\s*(-?[\d.]+)")
_FR_END = re.compile(r"freeze_end:\s*(-?[\d.]+)")
_FR_DUR = re.compile(r"freeze_duration:\s*([\d.]+)")


def parse_freezedetect(text: str) -> list[dict]:
    starts = [float(x) for x in _FR_START.findall(text or "")]
    ends = [float(x) for x in _FR_END.findall(text or "")]
    durs = [float(x) for x in _FR_DUR.findall(text or "")]
    out = []
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else None
        d = durs[i] if i < len(durs) else (None if e is None else e - s)
        out.append({"start": round(s, 3), "end": (round(e, 3) if e is not None else None),
                    "dur": (round(d, 3) if d is not None else None)})
    return out


def _num(x) -> str:
    """ffmpeg 滤镜数值格式：整数不带小数点（`-60` 而非 `-60.0`）。"""
    return "%g" % float(x)


def close_open_blocks(blocks: list[dict], end_s) -> list[dict]:
    """把**未闭合**的冻结/静音块用 `end_s`（成片总长）补齐（视频在冻结中结束时 ffmpeg 不输出 end）。"""
    if not end_s:
        return blocks
    out = []
    for b in blocks:
        if b.get("end") is None or b.get("dur") is None:
            e = float(end_s)
            out.append({**b, "end": round(e, 3),
                        "dur": round(max(e - float(b.get("start") or 0.0), 0.0), 3),
                        "closed_by_duration": True})
        else:
            out.append(b)
    return out


def measure_freeze(film: str | Path, ffmpeg: str, duration_s=None, timeout: int = 3600,
                   scale_filter: str = "scale=320:-2", noise_db: float = -60.0,
                   min_dur_s: float = 1.0):
    """对**已有成片**跑 `freezedetect`（只读解码，降采样加速）。返回 (blocks, stderr)。

    注意：`scale_filter` 必须是**完整滤镜**（如 `scale=320:-2`）；
    若视频在冻结中结束，ffmpeg 不输出 `freeze_end` → 用 `duration_s` 补齐（见 `close_open_blocks`）。
    """
    vf = "{},freezedetect=n={}dB:d={}".format(scale_filter, _num(noise_db), _num(min_dur_s))
    cmd = [ffmpeg, "-hide_banner", "-nostats", "-i", str(film), "-an", "-vf", vf,
           "-f", "null", "-"]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout)
    err = r.stderr or ""
    blocks = parse_freezedetect((r.stdout or "") + err)
    return close_open_blocks(blocks, duration_s), err
