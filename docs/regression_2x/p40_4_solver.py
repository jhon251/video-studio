# -*- coding: utf-8 -*-
"""Phase 40 / P40-1：**全局约束分配器**（最小冲突局部搜索，替代贪心）。

约束（**硬**，不可行时逐条报告而非静默违反）：
  a) 相邻景禁同素材；
  b) 同素材**间距 ≥3 景**；
  c) 每素材 **≤3 景**；
  d) **代价惩罚**：素材**复用次数**越高代价越高（覆盖监理所指
     「low_discriminative 素材被惩罚缺失、反而用得最多」的现象）。
     ※ 查明：`low_discriminative` 是 **Phase 19 期概念**，当前代码与本案池**均无该标记**
       （全库检索仅命中历史阶段脚本）⇒ 按**通用复用惩罚**实现，并如实登记该差异。

方法：min-conflicts + 随机重启（固定 seed ⇒ 可复现）；目标 = 最小化
  `10×(cap 违例) + 10×(间距违例) + 10×(相邻违例) + 1×Σ(用量²)`。
产出：分配结果 + **逐条约束满足报告**（PASS/FAIL + 违例清单 + 卡死景）。
"""
from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import random
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
SB = R / "output" / "phase36_p36_4_sandbox"
CAND = R / "output" / "p40_probe" / "candidates_per_scene.json"
OUT = R / "docs" / "regression_2x" / "logs" / "p40_allocation.json"
sys.stdout.reconfigure(encoding="utf-8")

CAP = 3
GAP = 3
SEED = 20261002


def sha12(x):
    return str(x)[:12]


def load_options():
    """逐景可选素材集合。

    优先用**复算的候选表**；候选为 0 的景用其实盘已选素材作为**唯一选项**
    （这些景由具名绑定/父景回退决定，不在本分配器可动范围内）。
    所有景都**追加**实盘已选素材，保证「不劣化」。
    """
    cand = json.loads(CAND.read_text(encoding="utf-8"))
    tl = json.loads((SB / "material_timeline.json").read_text(encoding="utf-8"))
    sel = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id"))
           for d in tl["decisions"]}
    scenes, options, fixed = [], {}, {}
    for row in cand:
        sid = row["scene_id"]
        scenes.append(sid)
        opts = [c["asset_id"] for c in (row.get("candidates") or [])
                if c.get("asset_id") and c.get("usable", True) is not False]
        s = sel.get(sid)
        if s and s not in opts:
            opts.append(s)
        options[sid] = opts
        fixed[sid] = (len(opts) <= 1)
    return scenes, options, sel, fixed


def violations(assign, scenes, pool):
    """返回 (cap_viol, gap_viol, adj_viol, 违例明细)。"""
    cnt = collections.Counter(a for a in assign.values() if a)
    capv = {k: v for k, v in cnt.items() if v > CAP}
    gapv, adjv = [], []
    for i, sid in enumerate(scenes):
        a = assign.get(sid)
        if not a:
            continue
        if i > 0 and assign.get(scenes[i - 1]) == a:
            adjv.append((sid, scenes[i - 1], a))
        for j in range(max(0, i - GAP), min(len(scenes), i + GAP + 1)):
            if j != i and assign.get(scenes[j]) == a:
                gapv.append((sid, scenes[j], a))
                break
    return capv, gapv, adjv


def cost(assign, scenes, options):
    capv, gapv, adjv = violations(assign, scenes, options)
    cnt = collections.Counter(a for a in assign.values() if a)
    reuse = sum(v * v for v in cnt.values())            # d) 复用惩罚（平方，鼓励分散）
    return 10 * len(capv) + 10 * len(gapv) + 10 * len(adjv) + reuse, (capv, gapv, adjv)


def solve(scenes, options, sel, fixed, restarts=40, iters=6000):
    rng = random.Random(SEED)
    movable = [s for s in scenes if not fixed[s] and len(options[s]) > 1]
    best, best_c, best_v = None, None, None
    for r in range(restarts):
        assign = {}
        for s in scenes:
            assign[s] = (rng.choice(options[s]) if options[s] else sel.get(s))
        c, v = cost(assign, scenes, options)
        for _ in range(iters):
            if c == 0:
                break
            # 选一个冲突景
            capv, gapv, adjv = v
            conflict = set()
            for k in capv:
                conflict |= {s for s in scenes if assign[s] == k}
            conflict |= {a for a, _, _ in gapv} | {a for a, _, _ in adjv}
            conflict = [s for s in conflict if not fixed[s] and len(options[s]) > 1]
            if not conflict:
                break
            s = rng.choice(conflict)
            cur = assign[s]
            best_choice, best_local = cur, c
            for cand in options[s]:
                if cand == cur:
                    continue
                assign[s] = cand
                c2, v2 = cost(assign, scenes, options)
                if c2 < best_local:
                    best_local, best_choice = c2, cand
            assign[s] = best_choice
            # 以一定概率接受随机解（跳出局部极小）
            if rng.random() < 0.12 and options[s]:
                assign[s] = rng.choice(options[s])
            c, v = cost(assign, scenes, options)
        if best_c is None or c < best_c:
            best, best_c, best_v = dict(assign), c, v
            if c == 0:
                break
    return best, best_c, best_v


def main() -> int:
    scenes, options, sel, fixed = load_options()
    n_movable = sum(1 for s in scenes if not fixed[s] and len(options[s]) > 1)
    print("景 {} | 可动景（候选>1）{} | 固定景（绑定/唯一）{}".format(
        len(scenes), n_movable, len(scenes) - n_movable))
    assign, c, v = solve(scenes, options, sel, fixed)
    capv, gapv, adjv = v
    cnt = collections.Counter(a for a in assign.values() if a)
    print()
    print("=== 约束满足报告（全局解，代价={}）===".format(c))
    print("  a) 相邻景禁同素材     : {} 违例 ⇒ {}".format(
        len(adjv), "PASS" if not adjv else "FAIL"))
    print("  b) 同素材间距 ≥{}     : {} 违例 ⇒ {}".format(
        GAP, len(gapv), "PASS" if not gapv else "FAIL"))
    print("  c) 每素材 ≤{} 景      : max={} ⇒ {}".format(
        CAP, max(cnt.values()) if cnt else 0, "PASS" if not capv else "FAIL"))
    print("  d) 复用惩罚           : Σ用量² = {}（越低越分散）".format(
        sum(x * x for x in cnt.values())))
    print()
    print("  每素材用量: {}".format(json.dumps(
        {k[:14]: n for k, n in cnt.most_common()}, ensure_ascii=False)))
    stuck = []
    if capv:
        for k, n in capv.items():
            stuck += [s for s in scenes if assign[s] == k]
    print()
    print("  卡死景清单(如有): {}".format(sorted(set(stuck))[:12] or "无"))
    detail = []
    for s in scenes:
        detail.append({"scene_id": s, "asset_id": assign.get(s),
                       "fixed": bool(fixed[s]), "options": len(options[s]),
                       "changed": assign.get(s) != sel.get(s)})
    rep = {
        "schema": "p40-allocation-v1",
        "method": "min-conflicts 局部搜索（seed={}）+ 复用平方惩罚".format(SEED),
        "constraints": {"adjacent_forbid_same": True, "min_scene_gap": GAP,
                        "max_scenes_per_asset": CAP},
        "low_discriminative_note": (
            "监理所指 `low_discriminative` 标记经**全库检索**仅命中 Phase 19 期历史脚本；"
            "当前代码与本案池（phase33_retrieval_payload）**均无该字段** ⇒ "
            "按**通用复用平方惩罚**实现（覆盖同一现象），并如实登记该差异。"),
        "report": {"adjacent_violations": adjv, "gap_violations": gapv,
                   "cap_violations": {k: n for k, n in capv.items()},
                   "max_scenes_per_asset": max(cnt.values()) if cnt else 0,
                   "reuse_cost": sum(x * x for x in cnt.values()),
                   "pass": not (adjv or gapv or capv)},
        "usage": {k: n for k, n in cnt.items()},
        "assignments": detail,
        "changed_count": sum(1 for d in detail if d["changed"]),
        "allocation_hash": hashlib.sha256(json.dumps(
            {s: assign.get(s) for s in scenes}, sort_keys=True).encode()).hexdigest(),
    }
    OUT.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("改选 {} 景 | allocation_hash {}".format(
        rep["changed_count"], rep["allocation_hash"][:16]))
    print("-> " + OUT.relative_to(R).as_posix())
    return 0 if rep["report"]["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
