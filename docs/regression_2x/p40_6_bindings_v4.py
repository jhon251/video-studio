# -*- coding: utf-8 -*-
"""Phase 40 / P40-1 前置：**具名绑定表 v4 —— 按构造满足约束**。

放弃用「干跑」判定待绑景（实测踩坑：干跑的 asset_id 命名空间为 `asset_p33_*`，
与本案池 `asset_<sha12>` **不同名** ⇒ 其用量/违例**不能代表实盘**，不可作为判据）。

改为**直接用实盘 F 的真实时间轴**：
  · **固定景** = 实盘 `material_timeline` 中**非具名绑定**得到的景（自动选材/父景回退），
    视为不可动常量；
  · **待绑景** = 实盘由**具名绑定**得到素材的景（这些景无自动候选，必须由绑定决定）；
  · 对**待绑景**做约束感知指派（每素材 ≤3、间距 ≥3、相邻禁同 + 复用平方惩罚），
    并把**固定景的真实用量**计入约束 —— 这才是与实盘一致的约束模型。
"""
from __future__ import annotations

import collections
import json
import pathlib
import random
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
VOICE = R / "output" / "phase36_voice"
SB = R / "output" / "phase36_p36_4_sandbox"
POOL = L / "phase33_retrieval_payload.json"
OUT = VOICE / "bindings_proposal.json"
CAP, GAP, SEED = 3, 3, 20261002
PREF = {
    "四色": ["301ff850be9c", "432cd85be6f1", "5144139591a0", "2442c39e8002"],
    "地图": ["301ff850be9c", "432cd85be6f1", "5144139591a0", "2442c39e8002"],
    "归约": ["1d2fe4b325bd", "a3f0e27204cd", "bd383463dbb9", "3f0b94a3f2ac"],
    "构型": ["1d2fe4b325bd", "a3f0e27204cd", "bd383463dbb9", "3f0b94a3f2ac"],
    "读完": ["a3aff2f300eb", "f0cd2a28016d", "23e71bc8a864", "acaa16094c3b"],
    "审稿": ["f0cd2a28016d", "a3aff2f300eb", "bd383463dbb9", "5144139591a0"],
    "哲学": ["65377b888b77", "acaa16094c3b", "5144139591a0", "2442c39e8002"],
    "反驳": ["acaa16094c3b", "23e71bc8a864", "5144139591a0", "65377b888b77"],
    "单群": ["23e71bc8a864", "acaa16094c3b", "5144139591a0", "65377b888b77"],
    "开普勒": ["a3f0e27204cd", "bd383463dbb9", "1d2fe4b325bd", "3f0b94a3f2ac"],
    "橘子": ["a3f0e27204cd", "bd383463dbb9", "1d2fe4b325bd", "3f0b94a3f2ac"],
    "99": ["bd383463dbb9", "a3f0e27204cd", "5144139591a0", "2442c39e8002"],
    "Flyspeck": ["1e9d2ab4e64e", "33b360a5363c", "3f0b94a3f2ac", "30dd89a16713"],
    "形式化": ["1e9d2ab4e64e", "33b360a5363c", "3f0b94a3f2ac", "30dd89a16713"],
    "Lean": ["1e9d2ab4e64e", "33b360a5363c", "3f0b94a3f2ac", "30dd89a16713"],
    "Scholze": ["33b360a5363c", "1e9d2ab4e64e", "3f0b94a3f2ac", "30dd89a16713"],
    "Liquid": ["33b360a5363c", "1e9d2ab4e64e", "3f0b94a3f2ac", "30dd89a16713"],
    "AlphaGeometry": ["432cd85be6f1", "5144139591a0", "cfae038f6106", "2442c39e8002"],
    "IMO": ["432cd85be6f1", "5144139591a0", "cfae038f6106", "2442c39e8002"],
    "几何": ["432cd85be6f1", "5144139591a0", "cfae038f6106", "2442c39e8002"],
    "机器": ["cfae038f6106", "3f0b94a3f2ac", "30dd89a16713", "2442c39e8002"],
    "封条": ["cfae038f6106", "3f0b94a3f2ac", "2442c39e8002", "30dd89a16713"],
    "自己写": ["cfae038f6106", "3f0b94a3f2ac", "30dd89a16713", "2442c39e8002"],
}


def main() -> int:
    tl = json.loads((SB / "material_timeline.json").read_text(encoding="utf-8"))["decisions"]
    pool = json.loads(POOL.read_text(encoding="utf-8"))
    by_sha = {str(c["sha256"]): c for c in pool["candidates"] if c.get("path")}
    secs = json.loads((VOICE / "scenes.json").read_text(encoding="utf-8"))["scenes"]
    text_of = {s["scene_id"]: s["text"] for s in secs}
    ids = [d["scene_id"] for d in tl]
    real = {d["scene_id"]: ((d.get("selected_asset") or {}).get("asset_id"))
            for d in tl}
    bound_scenes = [d["scene_id"] for d in tl
                    if "具名绑定" in str(d.get("fallback_reason"))]
    fixed = {s: real[s] for s in ids if real.get(s) and s not in bound_scenes}
    print("景 {} | 实盘由具名绑定定素材的景 {} | 固定景（自动/回退）{}".format(
        len(ids), len(bound_scenes), len(fixed)))
    fixed_cnt = collections.Counter(fixed.values())
    print("固定景用量（前 6）: {}".format(json.dumps(
        {k[:14]: v for k, v in fixed_cnt.most_common(6)}, ensure_ascii=False)))

    opts = {}
    for s in bound_scenes:
        t = text_of.get(s, "")
        pref = []
        for k, lst in PREF.items():
            if k in t:
                pref += [h for h in lst if h in by_sha]
        for h in by_sha:
            if h not in pref:
                pref.append(h)
        opts[s] = pref
    pos = {s: i for i, s in enumerate(ids)}

    def cost(a):
        cnt = collections.Counter(fixed.values())
        for h in a.values():
            if h:
                cnt[h] += 1
        capv = sum(1 for v in cnt.values() if v > CAP)
        merged = dict(fixed)
        merged.update(a)
        gapv = adjv = 0
        for i, s in enumerate(ids):
            x = merged.get(s)
            if not x:
                continue
            if i > 0 and merged.get(ids[i - 1]) == x:
                adjv += 1
            for j in range(max(0, i - GAP), min(len(ids), i + GAP + 1)):
                if j != i and merged.get(ids[j]) == x:
                    gapv += 1
                    break
        return 10 * capv + 10 * gapv + 10 * adjv + sum(v * v for v in cnt.values()), cnt

    rng = random.Random(SEED)
    best, best_c = None, None
    for _ in range(30):
        a = {s: rng.choice(opts[s]) for s in bound_scenes}
        cc, _ = cost(a)
        for _ in range(1200):
            if cc == 0:
                break
            s = rng.choice(bound_scenes)
            cur = a[s]
            bc, bch = cc, cur
            for h in opts[s][:8]:
                if h == cur:
                    continue
                a[s] = h
                c2, _ = cost(a)
                if c2 < bc:
                    bc, bch = c2, h
            a[s] = bch
            if rng.random() < 0.15:
                a[s] = rng.choice(opts[s][:8])
            cc, _ = cost(a)
        if best_c is None or cc < best_c:
            best_c, best = cc, dict(a)
            if cc == 0:
                break
    _, cnt = cost(best)
    merged = dict(fixed)
    merged.update(best)
    capv = {k: v for k, v in cnt.items() if v > CAP}
    gapv = adjv = 0
    for i, s in enumerate(ids):
        x = merged.get(s)
        if not x:
            continue
        if i > 0 and merged.get(ids[i - 1]) == x:
            adjv += 1
        for j in range(max(0, i - GAP), min(len(ids), i + GAP + 1)):
            if j != i and merged.get(ids[j]) == x:
                gapv += 1
                break
    detail = {s: {"sha256": h, "name": by_sha[h].get("name"),
                  "reason": "自动选材无候选 ⇒ 具名绑定（P40 约束感知指派）",
                  "approval_document": "Phase 34 授权书 §1(a)（P40 约束感知重指派）"}
              for s, h in best.items()}
    OUT.write_text(json.dumps({
        "schema": "p40-per-scene-bindings-v4",
        "method": ("以**实盘 F 时间轴**为基准：固定景=非绑定景（真实用量计入约束），"
                   "待绑景=绑定景；min-conflicts（seed={}）".format(SEED)),
        "constraints": {"cap": CAP, "min_scene_gap": GAP, "adjacent_forbid_same": True},
        "scene_count": len(ids), "bound": len(best), "bound_scenes": bound_scenes,
        "merged_usage": dict(cnt),
        "constraint_report": {"adjacent_violations": adjv, "gap_violations": gapv,
                              "cap_violations": capv,
                              "max_scenes_per_asset": max(cnt.values()) if cnt else 0,
                              "reuse_cost": sum(v * v for v in cnt.values()),
                              "pass": (not capv and not gapv and not adjv)},
        "bindings": detail,
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("=== 绑定表 v4 约束报告（实盘基准）===")
    print("  相邻违例 {} | 间距违例 {} | cap 违例 {} | max 景/素材 {} | Σ用量² {}".format(
        adjv, gapv, capv or "无", max(cnt.values()) if cnt else 0,
        sum(v * v for v in cnt.values())))
    print("  绑定: {}".format(json.dumps({s: h[:12] for s, h in sorted(best.items())},
                                        ensure_ascii=False)))
    print("-> " + OUT.relative_to(R).as_posix())
    return 0 if (not capv and not gapv and not adjv) else 1


if __name__ == "__main__":
    raise SystemExit(main())
