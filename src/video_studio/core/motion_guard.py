# -*- coding: utf-8 -*-
"""P25-1 **每景 corr 守卫**（硬性）：渲染后逐景复核 corr，低于阈值 ⇒ 该景幅度降级重渲。

语义（授权书 P25-1）
  · 运动幅度上修到 1.25 后，个别景的抽帧 corr 可能跌破 0.30（冻结口径 `frame_match_min_corr`）；
  · **守卫**：对每个启用运动的景，复核其渲染后抽帧 corr；
    `corr < CORR_GUARD_MIN(0.30)` ⇒ **该景幅度自动降回 `MAX_ZOOM_END_V1(1.08)` 重渲**，
    并登记 `MOTION_DOWNGRADED`；仲裁层照旧兜底（`core/render_arbitration.py` 不变）。
  · 守卫**只调运动参数**，不改 corr 判定阈值、不改仲裁语义（授权边界）。

确定性：给定 `(scene_corrs, plan)` ⇒ 降级集合唯一确定（同输入同输出）。
"""
from __future__ import annotations

import json
import pathlib

DOWNGRADE_CODE = "MOTION_DOWNGRADED"
SCHEMA = "motion-corr-guard-v1"


def guarded_scenes(plan: dict, scene_corrs: dict, *,
                   min_corr: float | None = None) -> dict:
    """按逐景 corr 复核结果给出**降级集合**。

    参数
      `plan`：`motion.build_plan` 的产物（含 `scenes`，每景有 `scene_id`/`enabled`/`params`）。
      `scene_corrs`：`{scene_id: corr}`（渲染后抽帧复核所得；缺失视为**未知** ⇒ 不降级、但要登记）。
      `min_corr`：阈值，默认 `motion.CORR_GUARD_MIN`（0.30）。

    返回
      `{"downgrade": [scene_id...], "keep": [...], "unknown": [...],
        "records": [{scene_id, corr, action, code}], "all_pass": bool}`
    """
    from video_studio.core import motion as M

    thr = float(min_corr if min_corr is not None else M.CORR_GUARD_MIN)
    downgrade, keep, unknown, records = [], [], [], []
    for s in plan.get("scenes") or []:
        sid = str(s.get("scene_id"))
        if not s.get("enabled"):
            continue
        if sid not in scene_corrs or scene_corrs[sid] is None:
            unknown.append(sid)
            records.append({"scene_id": sid, "corr": None, "action": "KEEP_UNKNOWN",
                            "code": None, "note": "未取得该景 corr ⇒ 不降级（待复核）"})
            continue
        c = float(scene_corrs[sid])
        if c < thr:
            downgrade.append(sid)
            records.append({"scene_id": sid, "corr": round(c, 4), "action": "DOWNGRADE",
                            "code": DOWNGRADE_CODE,
                            "from_zoom_max": M.MAX_ZOOM_END,
                            "to_zoom_max": M.MAX_ZOOM_END_V1})
        else:
            keep.append(sid)
            records.append({"scene_id": sid, "corr": round(c, 4), "action": "KEEP",
                            "code": None})
    return {"schema": SCHEMA, "min_corr": thr, "downgrade": downgrade, "keep": keep,
            "unknown": unknown, "records": records,
            "all_pass": not downgrade and not unknown,
            "note": ("守卫只调运动幅度（1.25 → 1.08）并登记 MOTION_DOWNGRADED；"
                     "不改 corr 判定阈值与仲裁语义。")}


def rebuild_plan_with_guard(scenes: list[dict], *, out_w: int, out_h: int, fps: int,
                            scene_corrs: dict, min_corr: float | None = None,
                            policy: dict | None = None) -> tuple[dict, dict]:
    """按守卫结论**重建**运动计划：降级景用 `zoom_max=MAX_ZOOM_END_V1` 重算。

    返回 `(plan', guard_report)`。**确定性**：同输入同输出。
    """
    from video_studio.core import motion as M

    base = M.build_plan(scenes, out_w=out_w, out_h=out_h, fps=fps, policy=policy)
    guard = guarded_scenes(base, scene_corrs, min_corr=min_corr)
    down = set(guard["downgrade"])
    picked = M.select_scenes(scenes, policy=policy)
    plans = []
    for s in picked:
        sid = str(s.get("scene_id"))
        mtype = "SLOW_PAN" if (M._scene_ordinal(sid) % 2 == 0
                               and s.get("motion_enabled")) else "SLOW_ZOOM_IN"
        zm = M.MAX_ZOOM_END_V1 if sid in down else None
        plans.append(M.plan_scene(s, out_w=out_w, out_h=out_h, fps=fps,
                                  enabled=bool(s.get("motion_enabled")),
                                  motion_type=mtype, zoom_max=zm))
    body = {**base, "scenes": sorted(plans, key=lambda p: str(p["scene_id"]))}
    body["counts"] = {"scenes": len(plans),
                      "enabled": sum(1 for p in plans if p["enabled"]),
                      "static": sum(1 for p in plans if not p["enabled"]),
                      "fallback": sum(1 for p in plans if p["fallback_code"]),
                      "downgraded": len(down)}
    body["artifact_hash"] = M.plan_hash(body)
    body["guard"] = {k: guard[k] for k in ("min_corr", "downgrade", "keep", "unknown",
                                           "all_pass")}
    return body, guard


def write_guard_log(path, plan: dict, guard: dict) -> dict:
    """登记守卫台账（失败降级证据照出）。"""
    p = pathlib.Path(path)
    rec = {"schema": SCHEMA + "-log", "plan_hash": plan.get("artifact_hash"),
           "counts": plan.get("counts"), "guard": guard}
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1, sort_keys=True),
                 encoding="utf-8")
    return rec
