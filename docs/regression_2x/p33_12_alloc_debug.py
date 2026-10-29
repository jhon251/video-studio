# -*- coding: utf-8 -*-
"""P33 诊断：分配纪律为何不改选（在生产函数内打点）。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.agents.editing import agent as AG                              # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402

pool = [{"asset_id": "asset_a{:02d}".format(k), "name": "素材{}".format(k),
         "path": "/nonexistent/a{:02d}.png".format(k), "relative_path": "a{}.png".format(k),
         "sha256": "{:064d}".format(k), "bytes": 1000, "width": 1920, "height": 1080,
         "license": "CC BY 4.0", "usable": True, "verified": True,
         "provider": "local_ingest"} for k in range(20)]
script = {"segments": [{"scene_id": "S{:02d}".format(i + 1),
                        "narration": "第 {} 段旁白。".format(i + 1),
                        "duration_s": 20.0} for i in range(40)]}


def _stub(scene_id, requirement, candidates, used_asset_ids, policy,
          material_provided=True, provider_requested=False, excluded_candidates=None):
    idx = int("".join(ch for ch in scene_id if ch.isdigit()) or "1") - 1
    a = pool[idx % 6]
    return {"scene_id": scene_id, "candidates": [{**a, "match_score": 99,
                                                  "matched_tokens": ["stub"]}],
            "candidates_total": 1, "insufficiency_class": "NONE",
            "fallback_state": "LOCAL_INGEST", "fallback_action": "正常命中",
            "fallback_reason": "stub", "selected_asset": a,
            "selection_reason": "stub", "needs_hitl": False,
            "allowed_in_final_render": True, "excluded_candidates": [],
            "license_pending": False, "original_requirement": requirement}


_ORIG = MAT.classify_scene
MAT.classify_scene = _stub
AG.classify_scene = _stub
try:
    pol = dict(MAT.policy_from_config(None))
    pol["max_scenes_per_asset"] = 3
    pol["forbid_adjacent_same_asset"] = True
    print("policy passed:", {k: pol[k] for k in ("max_scenes_per_asset",
                                                 "forbid_adjacent_same_asset")})
    tl = AG.EditingAgent._build_material_timeline(
        script, [], pool, policy=pol, material_provided=True, excluded_pool=None,
        provider_requested=False, human_selections={}, segment_durations=None,
        pause_budget_s=0.0, trailing_pad_s=2.0)
    alloc = getattr(tl, "allocation", {}) or {}
    print("alloc:", {k: (len(v) if isinstance(v, list) else v)
                     for k, v in alloc.items() if k != "final_counts"})
    print("final_counts:", alloc["final_counts"])
    print()
    # 检查 scene 是否带 candidates
    for s in tl[:4]:
        cs = s.get("candidates") or []
        print("{} selected={} candidates={} first_cand_keys={}".format(
            s["scene_id"], (s.get("selected_asset") or {}).get("asset_id"),
            len(cs), sorted(cs[0].keys())[:8] if cs else None))
finally:
    MAT.classify_scene = _ORIG
    AG.classify_scene = _ORIG
