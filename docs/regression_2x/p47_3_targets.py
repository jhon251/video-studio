# -*- coding: utf-8 -*-
"""Phase 47 / P47-2：**冻结风格 + 目标景清单**（无实体锚的抽象景，锚定表反查）。

目标景定义（授权书 §2）：**无实体锚**的抽象论述景 —— 即该景**不在**任何锚定素材的
`allowed_scenes` 里（那些景已被实体锚占用，语义固定）。预期 ~21 景。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
STYLE_ID = "a_黑板粉笔线稿"


def main() -> int:
    cfgp = R / "config" / "gen_style.json"
    cfg = json.loads(cfgp.read_text(encoding="utf-8"))["gen_style"]
    suffix = cfg["candidates"][STYLE_ID]["suffix"]
    sha = hashlib.sha256(suffix.encode("utf-8")).hexdigest()
    cfg["frozen_style_suffix"] = suffix
    cfg["frozen_style_sha256"] = sha
    cfg["frozen_style_id"] = STYLE_ID
    cfg["approved_by"] = "human:project-owner"
    cfg["frozen_at"] = "2026-10-02"
    cfgp.write_text(json.dumps({"gen_style": cfg}, ensure_ascii=False, indent=2)
                    + "\n", encoding="utf-8")

    ce = json.loads((R / "config/content_exclusions.json")
                    .read_text(encoding="utf-8"))["content_exclusions"]
    anchored = ce["scene_asset_policy"]["anchored"]
    occupied = set()
    for spec in anchored.values():
        occupied |= set(spec.get("allowed_scenes") or [])
    # 语境限位（82d1e3ba）也算实体占用
    fm = json.loads((R / "config/family_map.json").read_text(encoding="utf-8"))["family_map"]
    cr = (fm.get("context_restricted") or {}).get("82d1e3bae4f1") or {}
    occupied |= set(cr.get("allowed_scenes") or [])

    sc = json.loads((R / "output/phase36_script_sandbox/script_p36_v65_36seg.json")
                    .read_text(encoding="utf-8"))
    scenes = [s["scene_id"] for s in sc["segments"]]
    targets = [s for s in scenes if s not in occupied]
    print("冻结风格：{} | sha256 {}".format(STYLE_ID, sha[:16]))
    print("实体锚占用景 {} 个".format(len([s for s in scenes if s in occupied])))
    print("**抽象景（生成目标）= {} 个**：".format(len(targets)))
    print("  " + ", ".join(targets))
    art = {"schema": "p47-2-gen-targets-v1", "frozen_style_id": STYLE_ID,
           "frozen_style_sha256": sha, "frozen_style_suffix": suffix,
           "all_scenes": len(scenes), "anchor_occupied": sorted(
               s for s in scenes if s in occupied),
           "targets": targets, "target_count": len(targets),
           "budget_cny_cap": cfg["budget_cny"]["batch"],
           "request_cap": 25}
    (L / "p47_2_gen_targets.json").write_text(
        json.dumps(art, ensure_ascii=False, indent=1), encoding="utf-8")
    print("-> docs/regression_2x/logs/p47_2_gen_targets.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
