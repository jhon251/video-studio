# -*- coding: utf-8 -*-
"""Phase 48 / P48-1：**独立路径转储 + 逐字段 diff**（硬要求：不读代码猜测定案）。

· 独立路径：完全复刻生产路径的构造语义，但**独立重建** options（不经过 agent 的
  `_opts` 构建），用**同一个** `dump_solver_input()` 落盘；
· 然后 `diff()` 两份 JSON，报告**第一个分歧字段**；
· 再在同一输入上跑 `AL.satisfy`，报告是否 pass —— 以验证「输入差异 ⇒ 结果差异」。
"""
from __future__ import annotations

import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.path.insert(0, str(R / "docs" / "regression_2x"))
sys.stdout.reconfigure(encoding="utf-8")
from solver_input_dump import dump_solver_input, diff                         # noqa: E402
from video_studio.agents.editing.agent import EditingAgent as EA               # noqa: E402
from video_studio.core import allocation as AL                                 # noqa: E402
from video_studio.core import materials as MAT                                 # noqa: E402

PROD = R / "output" / "p40_probe" / "solver_input_production.json"
STAND = R / "output" / "p40_probe" / "solver_input_standalone.json"


def main() -> int:
    if not PROD.is_file():
        print("缺生产转储；先跑一次渲染")
        return 1
    prod = json.loads(PROD.read_text(encoding="utf-8"))
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
    gb = json.loads((R / "docs/regression_2x/logs/p47_2_gen_batch.json")
                    .read_text(encoding="utf-8"))
    pref = {}
    for it in (gb.get("items") or []):
        if it.get("ok"):
            pref[str(it["scene_id"])] = "asset_{}".format(str(it["sha256"])[:12])
    ids, opts = [], {}
    # **关键（diff 定位出的分歧根因）**：独立路径原先把检索池的 `asset_id`
    # （`asset_gen_p01_1`）直接喂给求解器，而**生产路径**用的是**时间轴**的
    # `asset_<sha12>`（如 `asset_6bc2321dd55f`）。家族/锚定全按前缀匹配 ⇒
    # **两套 id 命名空间不可互换**，于是"独立路径 pass=True"是**假象**
    # （它测的是另一套 id）。现统一为 `asset_<sha12>`，与生产逐字可比。
    for d in tl:
        sid = d["scene_id"]
        ids.append(sid)
        cs = ["asset_{}".format(str(c.get("sha256"))[:12])
              for c in (d.get("candidates") or []) if c.get("sha256")]
        if not cs:
            cs = ["asset_{}".format(str(c.get("sha256"))[:12]) for c in cands
                  if c.get("sha256")]
        if sid in pref:
            cs = [pref[sid]] + [a for a in cs if a != pref[sid]]
        opts[sid] = cs
    stand = dump_solver_input(
        STAND, source="standalone", ids=ids, options=opts,
        cap=int(prod.get("cap") or 3), gap=int(prod.get("gap") or 3),
        fam_map=fams, max_family_share=prod.get("max_family_share"),
        max_share_by_family=lim, sub_map=subs,
        forbid_adjacent_same_sub=True, initial=None,
        restarts=prod.get("restarts"), iters=prod.get("iters"), seed=None,
        extra={"note": "独立复刻：options 由 timeline 候选域重建"})

    print("=== 输入指纹 ===")
    print("  生产   : {} | 候选域指纹 {}".format(
        prod["input_fingerprint"][:16], prod["options_fingerprint"][:16]))
    print("  独立   : {} | 候选域指纹 {}".format(
        stand["input_fingerprint"][:16], stand["options_fingerprint"][:16]))
    d = diff(prod, stand)
    print()
    print("=== 逐字段 diff ===")
    print("  完全相同: {} | 分歧字段数: {}".format(d["identical"], d["diff_count"]))
    for x in d["all_differences"]:
        print("  · 字段 `{}`".format(x["field"]))
        if "sublabel_count" in x:
            print("     分歧子键 {} 个，例如: {}".format(
                x["sublabel_count"], x.get("sublabels", [])[:6]))
        else:
            print("     生产={} 独立={}".format(
                json.dumps(x["a"], ensure_ascii=False)[:160],
                json.dumps(x["b"], ensure_ascii=False)[:160]))
    print()
    print("=== 同一输入下的求解结果 ===")
    for tag, src in (("生产输入", prod), ("独立输入", stand)):
        o = {k: v for k, v in src["options"].items()}
        r = AL.satisfy(src["ids"], o, cap=src["cap"], gap=src["gap"],
                       fam_map=src["fam_map"],
                       max_family_share=src["max_family_share"],
                       max_share_by_family=src["max_share_by_family"],
                       sub_map=src["sub_map"],
                       forbid_adjacent_same_sub=src["forbid_adjacent_same_sub"],
                       restarts=src.get("restarts") or 40,
                       iters=src.get("iters") or 1500)
        fc = r["report"].get("family_counts") or {}
        tot = sum(fc.values()) or 1
        print("  {:<8} pass={} | G={} ({:.1%}) | cap={} gap={} 家族相邻={} 份额越界={}".format(
            tag, r["pass"], fc.get("G_生成概念插图", 0),
            fc.get("G_生成概念插图", 0) / tot, r["report"].get("cap_violations"),
            r["report"].get("gap_violations"), r["report"].get("adjacent_same_family"),
            r["report"].get("family_share_violations")))
    (R / "docs/regression_2x/logs/p48_1_input_diff.json").write_text(
        json.dumps({"schema": "p48-1-input-diff-report-v1", "diff": d,
                    "production_fp": prod["input_fingerprint"],
                    "standalone_fp": stand["input_fingerprint"],
                    "production_options_counts": prod["options_counts"],
                    "standalone_options_counts": stand["options_counts"]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> docs/regression_2x/logs/p48_1_input_diff.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
