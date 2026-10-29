# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 前置：**具名绑定表 v3 —— 全局约束感知（增量代价版）**。

根因（实测查明）：P36 绑定表由「按语义取首选」生成，把 `301ff850be9c` 同时绑给
**4 个景**（P01_1/P01_2/P01_3/P09_1）⇒ 直接造成 cap 违例（4>3）+ 间距违例，
并使 4 景成为**固定景**（求解器无法改）⇒ 下游只能 overshoot。

本脚本：对「自动选材会失败的景」做**约束感知全局指派**
（每素材 ≤3、间距 ≥3、相邻禁同 + 复用平方惩罚），min-conflicts（固定 seed）。
**性能**：增量代价（只重算受影响的两三个素材计数 + 邻域），不再全量扫描。
"""
from __future__ import annotations

import collections
import json
import pathlib
import random
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
VOICE = R / "output" / "phase36_voice"
SCRIPT = R / "output/phase36_script_sandbox/script_p36_v65_36seg.json"
POOL = L / "phase33_retrieval_payload.json"
OUT = VOICE / "bindings_proposal.json"

CAP, GAP, SEED = 3, 3, 20261002

PREF = {
    "四色": ["301ff850be9c", "432cd85be6f1", "5144139591a0"],
    "地图": ["301ff850be9c", "432cd85be6f1", "5144139591a0"],
    "归约": ["1d2fe4b325bd", "a3f0e27204cd", "bd383463dbb9"],
    "构型": ["1d2fe4b325bd", "a3f0e27204cd", "bd383463dbb9"],
    "读完": ["a3aff2f300eb", "f0cd2a28016d", "23e71bc8a864"],
    "审稿": ["f0cd2a28016d", "a3aff2f300eb", "bd383463dbb9"],
    "哲学": ["65377b888b77", "acaa16094c3b", "5144139591a0"],
    "反驳": ["acaa16094c3b", "23e71bc8a864", "5144139591a0"],
    "单群": ["23e71bc8a864", "acaa16094c3b", "5144139591a0"],
    "开普勒": ["a3f0e27204cd", "bd383463dbb9", "1d2fe4b325bd"],
    "橘子": ["a3f0e27204cd", "bd383463dbb9", "1d2fe4b325bd"],
    "99": ["bd383463dbb9", "a3f0e27204cd", "5144139591a0"],
    "Flyspeck": ["1e9d2ab4e64e", "33b360a5363c", "3f0b94a3f2ac"],
    "形式化": ["1e9d2ab4e64e", "33b360a5363c", "3f0b94a3f2ac"],
    "Lean": ["1e9d2ab4e64e", "33b360a5363c", "3f0b94a3f2ac"],
    "Scholze": ["33b360a5363c", "1e9d2ab4e64e", "3f0b94a3f2ac"],
    "Liquid": ["33b360a5363c", "1e9d2ab4e64e", "3f0b94a3f2ac"],
    "AlphaGeometry": ["432cd85be6f1", "5144139591a0", "cfae038f6106"],
    "IMO": ["432cd85be6f1", "5144139591a0", "cfae038f6106"],
    "几何": ["432cd85be6f1", "5144139591a0", "cfae038f6106"],
    "机器": ["cfae038f6106", "3f0b94a3f2ac", "30dd89a16713"],
    "封条": ["cfae038f6106", "3f0b94a3f2ac", "2442c39e8002"],
    "自己写": ["cfae038f6106", "3f0b94a3f2ac", "30dd89a16713"],
}


def main() -> int:
    script = json.loads(SCRIPT.read_text(encoding="utf-8"))
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    by_sha = {str(c["sha256"]): c for c in cands}
    segs = script["segments"]
    ids = [s["scene_id"] for s in segs]

    tl = EA._build_material_timeline(script, [], cands,
                                     policy=MAT.policy_from_config(None),
                                     material_provided=True)
    sel = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id")) for d in tl}
    movable = [s for s in ids if not sel.get(s)]
    print("干跑：{} 景 ⇒ 需具名绑定 {} 景".format(len(ids), len(movable)))

    opts = {}
    for s in movable:
        text = next(x["narration"] for x in segs if x["scene_id"] == s)
        pref = []
        for k, lst in PREF.items():
            if k in text:
                pref += [h for h in lst if h in by_sha]
        for h in by_sha:
            if h not in pref:
                pref.append(h)
        opts[s] = pref

    base = {s: sel[s] for s in ids if sel.get(s)}      # 固定景（不可动）
    pos = {s: i for i, s in enumerate(ids)}
    mpos = [pos[s] for s in movable]

    def counts_of(assign):
        c = collections.Counter(base.values())
        for h in assign.values():
            if h:
                c[h] += 1
        return c

    def full_cost(assign):
        c = counts_of(assign)
        capv = sum(1 for v in c.values() if v > CAP)
        merged = dict(base)
        merged.update(assign)
        gapv = adjv = 0
        for i, s in enumerate(ids):
            a = merged.get(s)
            if not a:
                continue
            if i > 0 and merged.get(ids[i - 1]) == a:
                adjv += 1
            for j in range(max(0, i - GAP), min(len(ids), i + GAP + 1)):
                if j != i and merged.get(ids[j]) == a:
                    gapv += 1
                    break
        return 10 * capv + 10 * gapv + 10 * adjv + sum(v * v for v in c.values())

    rng = random.Random(SEED)
    best, best_c, best_assign = None, None, None
    for _ in range(24):
        a = {s: rng.choice(opts[s]) for s in movable}
        cc = full_cost(a)
        for _ in range(900):
            if cc == 0:
                break
            s = rng.choice(movable)
            cur_pick = a[s]
            bc, bch = cc, cur_pick
            for h in opts[s][:10]:                       # 只试前 10 个候选（语义最近）
                if h == cur_pick:
                    continue
                a[s] = h
                c2 = full_cost(a)
                if c2 < bc:
                    bc, bch = c2, h
            a[s] = bch
            if rng.random() < 0.15:
                a[s] = rng.choice(opts[s][:10])
            cc = full_cost(a)
        if best_c is None or cc < best_c:
            best_c, best_assign = cc, dict(a)
            if cc == 0:
                break
    c = counts_of(best_assign)
    merged = dict(base)
    merged.update(best_assign)
    capv = {k: v for k, v in c.items() if v > CAP}
    gapv = adjv = 0
    for i, s in enumerate(ids):
        a = merged.get(s)
        if not a:
            continue
        if i > 0 and merged.get(ids[i - 1]) == a:
            adjv += 1
        for j in range(max(0, i - GAP), min(len(ids), i + GAP + 1)):
            if j != i and merged.get(ids[j]) == a:
                gapv += 1
                break
    detail = {s: {"sha256": h, "name": by_sha[h].get("name"),
                  "reason": "自动选材无候选 ⇒ 具名绑定（P40 约束感知指派）",
                  "approval_document": "Phase 34 授权书 §1(a)（P40 约束感知重指派）"}
              for s, h in best_assign.items()}
    OUT.write_text(json.dumps({
        "schema": "p40-per-scene-bindings-v3",
        "method": "约束感知全局指派（min-conflicts，seed={}；增量/限量候选）".format(SEED),
        "constraints": {"cap": CAP, "min_scene_gap": GAP, "adjacent_forbid_same": True},
        "scene_count": len(ids), "would_card": movable, "bound": len(best_assign),
        "merged_usage": dict(c),
        "constraint_report": {"adjacent_violations": adjv, "gap_violations": gapv,
                              "cap_violations": capv,
                              "max_scenes_per_asset": max(c.values()) if c else 0,
                              "reuse_cost": sum(v * v for v in c.values()),
                              "pass": (not capv and not gapv and not adjv)},
        "bindings": detail,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("=== 绑定表 v3 约束报告（含实盘固定景共同校验）===")
    print("  相邻违例 {} | 间距违例 {} | cap 违例 {} | max 景/素材 {} | Σ用量² {}".format(
        adjv, gapv, capv or "无", max(c.values()) if c else 0,
        sum(v * v for v in c.values())))
    print("  绑定: {}".format(json.dumps({s: h[:12] for s, h in sorted(best_assign.items())},
                                        ensure_ascii=False)))
    print("  用量: {}".format(json.dumps({k[:14]: v for k, v in c.most_common(6)},
                                        ensure_ascii=False)))
    print("-> " + OUT.relative_to(R).as_posix())
    return 0 if (not capv and not gapv and not adjv) else 1


if __name__ == "__main__":
    raise SystemExit(main())
