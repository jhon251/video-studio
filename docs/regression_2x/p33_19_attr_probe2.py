# -*- coding: utf-8 -*-
"""P33 微诊断2：为什么 `scenes.allocation = alloc` 没生效。"""
from __future__ import annotations

import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(R / "src"))
sys.stdout.reconfigure(encoding="utf-8")

# ① 基础能力：list 能否挂属性
x = [1, 2, 3]
x.foo = "bar"
print("① list 挂属性:", getattr(x, "foo", "MISSING"))

# ② 直接调用并检查（同时关掉 try/except 的遮蔽：手工执行等价代码）
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
    tl = AG.EditingAgent._build_material_timeline(
        script, [], pool, policy=dict(MAT.policy_from_config(None)),
        material_provided=True)
    print("② 返回类型:", type(tl).__name__, "| len:", len(tl))
    print("   dir 含 allocation?", "allocation" in dir(tl))
    print("   __dict__:", getattr(tl, "__dict__", "无"))
    # ③ 手工挂上再读（验证同一对象可挂）
    tl.allocation = {"probe": 1}
    print("③ 手工挂后:", getattr(tl, "allocation", "MISSING"))
finally:
    MAT.classify_scene = _ORIG
    AG.classify_scene = _ORIG

# ④ 逐字节确认函数尾部（源码级）
import inspect
src = inspect.getsource(AG.EditingAgent._build_material_timeline)
print()
print("④ 函数尾部 8 行:")
for ln in src.strip().splitlines()[-8:]:
    print("   ", ln)
