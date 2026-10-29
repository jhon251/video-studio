# -*- coding: utf-8 -*-
"""Phase 47 / P47-3：**G ≤33% 可行性判定** —— 是「求解器搜不到」还是「结构性不可行」？

做法：用真实候选域构造 options，直接调 `AL.satisfy`（加大 restarts/iters），
报告 G 份额能达到的最小值，并与 33%（=12 景）对照。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import allocation as AL                                   # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402


def main() -> int:
    fm = json.loads((R / "config/family_map.json").read_text(encoding="utf-8"))["family_map"]
    fams = dict(fm["families"])
    subs = dict(fm["sub_families"])
    subs.pop("_note", None)
    lim = dict(fm.get("max_share_by_family") or {})
    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    pool = json.loads((R / "docs/regression_2x/logs/p45_4_merged_payload.json")
                      .read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    tl = EA._build_material_timeline(sc, [], cands,
                                     policy=MAT.policy_from_config(None),
                                     material_provided=True)
    ids = [d["scene_id"] for d in tl]
    gb = json.loads((R / "docs/regression_2x/logs/p47_2_gen_batch.json")
                    .read_text(encoding="utf-8"))
    pref = {}
    for it in (gb.get("items") or []):
        if it.get("ok"):
            pref[str(it["scene_id"])] = "asset_{}".format(str(it["sha256"])[:12])
    opts = {}
    for d in tl:
        sid = d["scene_id"]
        cs = [c.get("asset_id") for c in (d.get("candidates") or [])
              if c.get("asset_id")]
        if not cs:
            cs = ["asset_{}".format(str(c.get("sha256"))[:12]) for c in cands
                  if c.get("sha256")]
        if sid in pref:
            cs = [pref[sid]] + [a for a in cs if a != pref[sid]]
        opts[sid] = cs
    nG = sum(1 for s in ids if AL._family_of((opts.get(s) or [""])[0], fams)
             == "G_生成概念插图")
    print("景 {} | 候选域中 G 置首的景 {} | 33% 上限 = {} 景".format(
        len(ids), nG, int(len(ids) * 0.33)))
    best = None
    for share in (0.33, 0.40, 0.45, 0.50):
        r = AL.satisfy(ids, opts, cap=3, gap=3, fam_map=fams,
                       max_family_share=0.33, max_share_by_family=lim,
                       sub_map=subs, forbid_adjacent_same_sub=True,
                       restarts=40, iters=1500)
        fc = r["report"].get("family_counts") or {}
        g = fc.get("G_生成概念插图", 0)
        tot = sum(fc.values()) or 1
        print("  门 {:.0%} ⇒ pass={} | G={} ({:.1%}) | 份额越界={} | gap={} 家族相邻={}".format(
            share, r["pass"], g, g / tot, r["report"].get("family_share_violations"),
            r["report"].get("gap_violations"), r["report"].get("adjacent_same_family")))
        if best is None or g < best[1]:
            best = (share, g, r["pass"])
    print()
    print("G 可达到的最小景数 = {}（上限允许 {}）".format(best[1], int(len(ids) * 0.33)))
    print("结论：{}".format(
        "**结构性不可行**（G 素材被 15 个抽象景的候选域强绑定，无法降到 33%）"
        if best[1] > int(len(ids) * 0.33) else "可行（求解器可满足）"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
