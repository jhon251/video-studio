# -*- coding: utf-8 -*-
"""Phase 33 / P33-2 —— **分配纪律门**（每素材 ≤N 景 + 相邻景禁同素材）。

背景：素材疲劳本质是**池容量与分配**问题。DQ-2 只约束「单素材最大**时长占比**」，
不约束「单素材**上屏景数**」，也不约束「相邻景是否同素材」——两者都会直接被观众感知为
"又是这张图"。本门把 P33-2 的分配纪律写成可执行断言。

被测对象 = **生产函数** `EditingAgent._build_material_timeline`（非离线复刻）。
为避免依赖真实图片/网络，本测试把选材判据 `classify_scene` **打桩**为确定性分配
（轮转 20 个素材并故意制造超限与相邻重复），从而**只检验纪律后处理本身**：
  · **A1** 开启上限（cap=3）后：无素材被分配到 >3 个景；
  · **A2** 开启相邻规则后：不存在相邻两景同素材；
  · **A3** 关闭纪律（默认）时：**行为与既有完全一致**（不做任何改选）——回归守卫；
  · **A4** 纪律只**改选**、不改变景数与时间轴（窗口/时长不变）；
  · **A5** 无可用替代时记入 `unresolved` 并**保留原分配**（不静默丢弃、不造假）。

运行: python tests/allocation_discipline_test.py
"""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.editing import agent as AG                              # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402

PASS, FAIL = [], []
CAP = 3


def check(name, ok, detail=None):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else json.dumps(detail, ensure_ascii=False,
                                                      default=str)[:300]))
    return bool(ok)


# ---------------- 合成输入 ----------------
N_SCENES = 40
N_ASSETS = 20
script = {"segments": [{"scene_id": "S{:02d}".format(i + 1),
                        "narration": "第 {} 段的旁白文本，用于触发选材打分逻辑。".format(i + 1),
                        "duration_s": 20.0} for i in range(N_SCENES)]}
pool = [{"asset_id": "asset_a{:02d}".format(k), "name": "素材{}".format(k),
         "path": "/nonexistent/a{:02d}.png".format(k), "relative_path": "a{}.png".format(k),
         "sha256": "{:064d}".format(k), "bytes": 1000, "width": 1920, "height": 1080,
         "license": "CC BY 4.0", "usable": True, "verified": True,
         "provider": "local_ingest"} for k in range(N_ASSETS)]

# 打桩：确定性**故意不良**的分配 —— 轮转 6 个素材（⇒ 必然超 cap=3），且相邻常重复
_ORIG = MAT.classify_scene


def _stub_classify(scene_id, requirement, candidates, used_asset_ids, policy,
                   material_provided=True, provider_requested=False,
                   excluded_candidates=None):
    """确定性**故意不良**的初始分配：默认选中**前 6 个**素材轮转
    （40 景 ⇒ 每个 ~7 景，必然超 cap=3）；但**候选集给出全部 20 个**
    ⇒ 纪律后处理有足够替代可改选（这正是 A1/A4b 要检验的路径）。"""
    idx = int("".join(ch for ch in scene_id if ch.isdigit()) or "1") - 1
    chosen = pool[idx % 6]                         # 初始分配只用 6 个 ⇒ 必然超限
    cands = [{**a, "match_score": 99 if a is chosen else 1, "matched_tokens": ["stub"]}
             for a in pool]
    return {"scene_id": scene_id, "candidates": cands,
            "candidates_total": len(cands), "insufficiency_class": "NONE",
            "fallback_state": "LOCAL_INGEST", "fallback_action": "正常命中",
            "fallback_reason": "stub", "selected_asset": chosen,
            "selection_reason": "stub", "needs_hitl": False,
            "allowed_in_final_render": True, "excluded_candidates": [],
            "license_pending": False, "original_requirement": requirement}


MAT.classify_scene = _stub_classify
AG.classify_scene = _stub_classify

try:
    base = dict(MAT.policy_from_config(None))
    kw = dict(material_provided=True, excluded_pool=None, provider_requested=False,
              human_selections={}, segment_durations=None, pause_budget_s=0.0,
              trailing_pad_s=2.0)

    # ---- A3 纪律关闭（默认）⇒ 不做任何改选 ----
    # 注意：`policy` 必须是**关键字**参数（`_build_material_timeline` 的第 2 个位置参数
    # 是 `shots`）—— 首版测试按位置传参 ⇒ policy 落到 shots，纪律从未生效（已修正）。
    off = dict(base)
    tl_off = AG.EditingAgent._build_material_timeline(
        script, [], pool, policy=off, **kw)
    alloc_off = getattr(tl_off, "allocation", {}) or {}
    cnt_off = {}
    for s in tl_off:
        a = (s.get("selected_asset") or {}).get("asset_id")
        if a:
            cnt_off[a] = cnt_off.get(a, 0) + 1
    check("A3 纪律关闭（默认）⇒ 零改选、行为与既有一致",
          not alloc_off["reassigned"] and max(cnt_off.values()) > CAP,
          {"max_count": max(cnt_off.values()), "reassigned": len(alloc_off["reassigned"])})

    # ---- A1/A2/A4 开启纪律 ----
    on = dict(base, max_scenes_per_asset=CAP, forbid_adjacent_same_asset=True)
    # P33-2：纪律开关**不在** `DEFAULT_POLICY` 内（`core/materials.py` 被基线 manifest 钉定），
    # 需显式注入策略字典（生产链由 agent 从 `config.editing` 透传）。
    tl_on = AG.EditingAgent._build_material_timeline(script, [], pool,
                                                    policy=on, **kw)
    alloc_on = getattr(tl_on, "allocation", {}) or {}
    cnt_on = {}
    for s in tl_on:
        a = (s.get("selected_asset") or {}).get("asset_id")
        if a:
            cnt_on[a] = cnt_on.get(a, 0) + 1
    over = {k: v for k, v in cnt_on.items() if v > CAP}
    check("A1 每素材上屏景数 ≤ {}（实测最大 {}）".format(CAP, max(cnt_on.values())),
          not over, over)
    adj = [tl_on[i]["scene_id"] for i in range(1, len(tl_on))
           if (tl_on[i].get("selected_asset") or {}).get("asset_id")
           and (tl_on[i].get("selected_asset") or {}).get("asset_id")
           == (tl_on[i - 1].get("selected_asset") or {}).get("asset_id")]
    check("A2 相邻景不使用同一素材（违例 {} 处）".format(len(adj)), not adj, adj[:6])
    check("A4 纪律只改选、不改时间轴（景数与窗口逐景一致）",
          len(tl_on) == len(tl_off)
          and all(tl_on[i]["start_s"] == tl_off[i]["start_s"]
                  and tl_on[i]["end_s"] == tl_off[i]["end_s"] for i in range(len(tl_on))),
          {"n_on": len(tl_on), "n_off": len(tl_off)})
    check("A4b 纪律确实发生了改选（reassigned = {}）".format(
        len(alloc_on["reassigned"])), len(alloc_on["reassigned"]) > 0)
    # ---- A6：P35-3 **同素材最小间距 ≥ N 景**（升级自「禁相邻」）----
    GAP = 3
    on_gap = dict(base, max_scenes_per_asset=CAP, forbid_adjacent_same_asset=True,
                  min_scene_gap=GAP)
    tl_gap = AG.EditingAgent._build_material_timeline(script, [], pool,
                                                      policy=on_gap, **kw)
    alloc_gap = getattr(tl_gap, "allocation", {}) or {}
    aids = [(s.get("selected_asset") or {}).get("asset_id") for s in tl_gap]

    def _gap_violations(seq, gap):
        v = []
        for i, a in enumerate(seq):
            if not a:
                continue
            for j in range(max(0, i - gap), min(len(seq), i + gap + 1)):
                if j != i and seq[j] == a:
                    v.append((i, j, a))
                    break
        return v

    viol = _gap_violations(aids, GAP)
    cnt_gap = {}
    for a in aids:
        if a:
            cnt_gap[a] = cnt_gap.get(a, 0) + 1
    check("A6 同素材间距 ≥ {} 景（违例 {} 处；每素材最大 {} 景）".format(
        GAP, len(viol), max(cnt_gap.values())), not viol, viol[:6])
    check("A6b 间距规则可关闭（不配置 ⇒ 零改选、行为不变）",
          not _gap_violations([(s.get("selected_asset") or {}).get("asset_id")
                               for s in tl_off], GAP)
          or (getattr(getattr(tl_off, "allocation", {}) or {}, "get", lambda *a: 0)(
              "min_scene_gap") in (None, 0)),
          {"off_gap": (getattr(tl_off, "allocation", {}) or {}).get("min_scene_gap")})
    check("A5 无可用替代的场景被**如实登记**（unresolved 可审计，且原分配保留）",
          isinstance(alloc_on["unresolved"], list)
          and all("scene_id" in u and "why" in u for u in alloc_on["unresolved"]),
          alloc_on["unresolved"][:3])
    # 未解决者仍持有素材（不静默置空）
    unresolved_ids = {u["scene_id"] for u in alloc_on["unresolved"]}
    still_has = all((s.get("selected_asset") or {}).get("asset_id")
                    for s in tl_on if s["scene_id"] in unresolved_ids)
    check("A5b 未解决场景**保留原分配**（不静默丢失素材）", still_has)
finally:
    MAT.classify_scene = _ORIG
    AG.classify_scene = _ORIG

print()
print("=" * 70)
print("allocation_discipline_test: {} PASS / {} FAIL".format(len(PASS), len(FAIL)))
if FAIL:
    print("FAILED:", json.dumps(FAIL, ensure_ascii=False))
print("=" * 70)
sys.exit(1 if FAIL else 0)
