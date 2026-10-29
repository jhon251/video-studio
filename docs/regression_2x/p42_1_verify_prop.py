# -*- coding: utf-8 -*-
"""Phase 41 / P41-1 验证：**候选传播后**派生景的候选域（含三处残留景对照）。

关心：
  · 派生景域是否由 0 变非空；
  · **三处残留景对**（P03_2/3、P04_2/3、P06_3/4）在传播后是否获得候选；
  · `STRUCTURAL_SINGLETON`（父景本身仅单一候选/无候选）清单。
"""
from __future__ import annotations

import collections
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing.agent import EditingAgent as EA                 # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402

L = R / "docs" / "regression_2x" / "logs"
RESID = ["P03_2", "P03_3", "P04_2", "P04_3", "P06_3", "P06_4"]


def main() -> int:
    script = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                        .read_text(encoding="utf-8"))
    pool = json.loads((L / "phase33_retrieval_payload.json").read_text(encoding="utf-8"))
    cands = [c for c in pool["candidates"] if c.get("path")]
    tl = EA._build_material_timeline(script, [], cands,
                                     policy=MAT.policy_from_config(None),
                                     material_provided=True)
    width = {d["scene_id"]: len(d.get("candidates") or []) for d in tl}
    src = collections.Counter(str(d.get("binding_source") or d.get("selection_source"))
                              for d in tl)
    print("景 {} | 候选域分布: {}".format(
        len(tl), dict(sorted(collections.Counter(width.values()).items()))))
    print("绑定来源分布: {}".format(dict(src)))
    sing = [s for s, n in width.items() if n == 0]
    print()
    print("STRUCTURAL_SINGLETON（域=0，分配器无法改派）: {} 个".format(len(sing)))
    print("  {}".format(sing or "无"))
    print()
    print("=== 三处残留景对对照 ===")
    for sid in RESID:
        d = next((x for x in tl if x["scene_id"] == sid), None)
        if d is None:
            print("  {} 未找到".format(sid))
            continue
        print("  {:<7} 候选域={:<3} 来源={:<20} 已选={}".format(
            sid, width[sid],
            str(d.get("binding_source") or d.get("selection_source"))[:20],
            str(((d.get("selected_asset") or {}).get("asset_id")))[:20]))
    print()
    prop = [d["scene_id"] for d in tl if d.get("candidates_propagated_from")]
    print("经**候选传播**获得候选的景: {} 个".format(len(prop)))
    print("  {}".format(prop or "无"))
    (L / "p41_1_propagation.json").write_text(json.dumps({
        "schema": "p41-1-candidate-propagation-v1",
        "scene_count": len(tl),
        "domain_histogram": {str(k): v for k, v in
                             sorted(collections.Counter(width.values()).items())},
        "binding_source": dict(src),
        "structural_singleton": sing,
        "propagated_scenes": prop,
        "residual_pairs": {s: {"domain": width.get(s),
                               "binding_source": next(
                                   (str(d.get("binding_source")) for d in tl
                                    if d["scene_id"] == s), None)}
                           for s in RESID},
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    print()
    print("-> docs/regression_2x/logs/p41_1_propagation.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
