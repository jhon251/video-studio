# -*- coding: utf-8 -*-
"""Phase 40 / P40-1：**约束的局部搜索后处理**（生产分配器核心）。

问题（实测）：原「贪心改选」在遇到冲突时只做**单步**尝试，无解即记 `unresolved`
并**保留违反分配**；且**父景绑定回退**把同一素材强绑给同父段的多个派生景，
与「间距 ≥3」直接冲突 ⇒ 实盘 cap 4>3、间距违例 10。

本模块提供 `satisfy()`：对**逐景候选表**做**最小冲突局部搜索**（固定 seed，可复现），
硬约束 a/b/c 全部编码为代价；无解时**返回最小违例解 + 违例清单**（不静默违反）。
"""
from __future__ import annotations

import collections
import hashlib
import random

CAP_DEFAULT = 3
GAP_DEFAULT = 3
SEED = 20261002


def _family_of(asset_id, fam_map):
    """按**前缀**匹配家族（asset_id 形如 `asset_<sha12>`，family_map 用 sha 前缀）。"""
    if not asset_id or not fam_map:
        return None
    s = str(asset_id)
    for fam, prefixes in fam_map.items():
        for p in prefixes:
            if p and (p in s):
                return fam
    return None


def _violations(assign, ids, cap, gap, fam_map=None, max_family_share=None,
                max_share_by_family=None, sub_map=None,
                forbid_adjacent_same_sub=False):
    cnt = collections.Counter(a for a in assign.values() if a)
    capv = {k: v for k, v in cnt.items() if v > cap}
    gapv, adjv = 0, 0
    fam_adjv = 0
    sub_adjv = 0
    for i, s in enumerate(ids):
        a = assign.get(s)
        if not a:
            continue
        if i > 0 and assign.get(ids[i - 1]) == a:
            adjv += 1
        if fam_map and i > 0:
            fa, fp = _family_of(a, fam_map), _family_of(assign.get(ids[i - 1]), fam_map)
            if fa and fa == fp:
                fam_adjv += 1
            if forbid_adjacent_same_sub and sub_map:
                sa, sp = _family_of(a, sub_map), _family_of(
                    assign.get(ids[i - 1]), sub_map)
                if sa and sa == sp:
                    sub_adjv += 1
        for j in range(max(0, i - gap), min(len(ids), i + gap + 1)):
            if j != i and assign.get(ids[j]) == a:
                gapv += 1
                break
    fam_share_v = {}
    if fam_map and max_family_share:
        total = sum(1 for a in assign.values() if a) or 1
        fc = collections.Counter(_family_of(a, fam_map)
                                 for a in assign.values() if a)
        for fam, n in fc.items():
            if not fam:
                continue
            # ---- P46-2 **双轨门**：优先用该家族自己的上限 ----
            lim = float((max_share_by_family or {}).get(fam, max_family_share))
            if n / total > lim + 1e-9:
                fam_share_v[fam] = {"n": n, "share": round(n / total, 4), "limit": lim}
    return capv, gapv, adjv, fam_adjv, sub_adjv, fam_share_v


def _cost(assign, ids, cap, gap, fam_map=None, max_family_share=None,
          max_share_by_family=None, sub_map=None,
          forbid_adjacent_same_sub=False):
    capv, gapv, adjv, fam_adjv, sub_adjv, fam_share_v = _violations(
        assign, ids, cap, gap, fam_map, max_family_share, max_share_by_family,
        sub_map, forbid_adjacent_same_sub)
    cnt = collections.Counter(a for a in assign.values() if a)
    # 权重：硬约束远高于复用惩罚；间距/相邻/家族相邻权重高（观感门 DQ-3e 直接来源）
    return (20 * len(capv) + 30 * gapv + 30 * adjv + 30 * fam_adjv
            + 30 * sub_adjv
            + 30 * len(fam_share_v) + sum(v * v for v in cnt.values())), \
        (capv, gapv, adjv, fam_adjv, sub_adjv, fam_share_v)


def assignment_fingerprint(assign: dict) -> str:
    """**逐景 sha 指纹**（P56-1 确定性断言用）。

    对 `{scene_id: asset_id}` 按**景序排序**后拼成 `scene=asset` 串并取 sha256。
    同输入两次求解若指纹一致 ⇒ **分配可复现**（这是「单变量对照」成立的前提）。
    """
    _items = ["{}={}".format(k, v or "") for k, v in sorted((assign or {}).items())]
    return hashlib.sha256("\n".join(_items).encode("utf-8")).hexdigest()


def satisfy(ids, options, initial=None, cap=CAP_DEFAULT, gap=GAP_DEFAULT,
            restarts: int = 20, iters: int = 600, seed: int = SEED,
            topk: int = 12, fam_map=None, max_family_share=None,
            max_share_by_family=None, sub_map=None,
            forbid_adjacent_same_sub=False):
    """对逐景候选做约束满足。

    `ids`     : 景序（决定间距/相邻语义）
    `options` : {scene_id: [asset_id, ...]}（**首选在前**，用于 tie-break）
    `initial` : 初始解（通常为实盘已选，作为起点，避免无谓改动）
    `fam_map` : {家族名: [sha前缀, ...]}（P43-2 感知家族）
    `max_family_share`     : 同家族份额上限（默认轨，P43-2，运行前写死）
    `max_share_by_family`  : **双轨门**（P46-2）：按家族分别设上限
    `sub_map` / `forbid_adjacent_same_sub` : **子族**及「相邻禁同子族」（P46-2）
    """
    rng = random.Random(seed)
    movable = [s for s in ids if len(options.get(s) or []) > 1]
    fixed = {s: (options.get(s) or [None])[0] for s in ids
             if len(options.get(s) or []) <= 1}
    best, best_c, best_v = None, None, None
    base = dict(initial or {})
    _kw = dict(fam_map=fam_map, max_family_share=max_family_share,
               max_share_by_family=max_share_by_family, sub_map=sub_map,
               forbid_adjacent_same_sub=forbid_adjacent_same_sub)
    for r in range(restarts):
        a = dict(base)
        for s in movable:
            a[s] = rng.choice(options[s][:topk]) if r > 0 else (
                base.get(s) or options[s][0])
        cc, vv = _cost(a, ids, cap, gap, **_kw)
        for _ in range(iters):
            if cc == 0:
                break
            capv, gapv, adjv, fam_adjv, sub_adjv, fam_share_v = vv
            conflict = set()
            for k in capv:
                conflict |= {s for s in movable if a.get(s) == k}
            for i, s in enumerate(ids):
                x = a.get(s)
                if not x:
                    continue
                if i > 0 and a.get(ids[i - 1]) == x:
                    conflict.add(s)
                if fam_map and i > 0 and _family_of(x, fam_map) and \
                        _family_of(x, fam_map) == _family_of(a.get(ids[i - 1]), fam_map):
                    conflict.add(s)
                if forbid_adjacent_same_sub and sub_map and i > 0 and \
                        _family_of(x, sub_map) and _family_of(x, sub_map) == \
                        _family_of(a.get(ids[i - 1]), sub_map):
                    conflict.add(s)
                for j in range(max(0, i - gap), min(len(ids), i + gap + 1)):
                    if j != i and a.get(ids[j]) == x:
                        conflict.add(s)
                        break
            if fam_share_v and fam_map:
                for fam in fam_share_v:
                    conflict |= {s for s in movable
                                 if _family_of(a.get(s), fam_map) == fam}
            conflict = [s for s in conflict if s in movable]
            if not conflict:
                break
            s = rng.choice(conflict)
            cur = a.get(s)
            bc, bch = cc, cur
            for h in options[s][:topk]:
                if h == cur:
                    continue
                a[s] = h
                c2, _ = _cost(a, ids, cap, gap, **_kw)
                if c2 < bc:
                    bc, bch = c2, h
            a[s] = bch
            if rng.random() < 0.12:
                a[s] = rng.choice(options[s][:topk])
            cc, vv = _cost(a, ids, cap, gap, **_kw)
        if best_c is None or cc < best_c:
            best, best_c, best_v = dict(a), cc, vv
            if cc == 0:
                break
    for s, x in fixed.items():
        if x:
            best[s] = x
    capv, gapv, adjv, fam_adjv, sub_adjv, fam_share_v = _violations(
        best, ids, cap, gap, fam_map, max_family_share, max_share_by_family,
        sub_map, forbid_adjacent_same_sub)
    cnt = collections.Counter(x for x in best.values() if x)
    fam_cnt = collections.Counter(_family_of(x, fam_map)
                                  for x in best.values() if x)
    return {
        "assignment": best,
        "pass": (not capv and gapv == 0 and adjv == 0 and fam_adjv == 0
                 and sub_adjv == 0 and not fam_share_v),
        "report": {"cap_violations": capv, "gap_violations": gapv,
                   "adjacent_violations": adjv,
                   "adjacent_same_family": fam_adjv,
                   "adjacent_same_sub_family": sub_adjv,
                   "family_share_violations": fam_share_v,
                   "family_counts": dict(fam_cnt),
                   "max_scenes_per_asset": max(cnt.values()) if cnt else 0,
                   "reuse_cost": sum(v * v for v in cnt.values()),
                   "movable_scenes": len(movable), "fixed_scenes": len(fixed)},
        "usage": dict(cnt), "cost": best_c,
    }
