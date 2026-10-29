# -*- coding: utf-8 -*-
"""P33 微诊断：`_build_material_timeline` 是否真的把 allocation 挂到返回值上。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")
from video_studio.agents.editing import agent as AG                              # noqa: E402
from video_studio.core import materials as MAT                                   # noqa: E402

pool = [{"asset_id": "asset_a{:02d}".format(k), "name": "x{}".format(k),
         "path": "/no/a{}.png".format(k), "relative_path": "a{}.png".format(k),
         "sha256": "{:064d}".format(k), "bytes": 1, "width": 1920, "height": 1080,
         "license": "CC BY 4.0", "usable": True, "verified": True,
         "provider": "local_ingest"} for k in range(8)]
script = {"segments": [{"scene_id": "S{:02d}".format(i + 1),
                        "narration": "文本 {}。".format(i + 1),
                        "duration_s": 20.0} for i in range(6)]}
_ORIG = MAT.classify_scene


def _stub(scene_id, requirement, candidates, used_asset_ids, policy,
          material_provided=True, provider_requested=False, excluded_candidates=None):
    a = pool[0]
    return {"scene_id": scene_id, "candidates": [{**a, "match_score": 9,
                                                  "matched_tokens": ["s"]}],
            "candidates_total": 1, "insufficiency_class": "NONE",
            "fallback_state": "LOCAL_INGEST", "fallback_action": "ok",
            "fallback_reason": "", "selected_asset": a, "selection_reason": "",
            "needs_hitl": False, "allowed_in_final_render": True,
            "excluded_candidates": [], "license_pending": False,
            "original_requirement": requirement}


MAT.classify_scene = _stub
AG.classify_scene = _stub
try:
    for cap, adj in ((None, False), (2, True)):
        pol = dict(MAT.policy_from_config(None))
        pol["max_scenes_per_asset"] = cap
        pol["forbid_adjacent_same_asset"] = adj
        tl = AG.EditingAgent._build_material_timeline(
            script, [], pool, policy=pol, material_provided=True)
        al = getattr(tl, "allocation", "MISSING")
        print("cap={} adj={} -> type={} len={} allocation={}".format(
            cap, adj, type(tl).__name__, len(tl),
            (al if al == "MISSING" else {k: (len(v) if isinstance(v, list) else v)
                                         for k, v in al.items()})))
finally:
    MAT.classify_scene = _ORIG
    AG.classify_scene = _ORIG
