"""4.x Phase 4-C：人审候选替换的**运维层**（只读复核队列 + 记录人工决定）。

两条命令：
  · `run.py review <project_id>`            只读：列出待复核镜头 + **可选候选池**（含许可/验证状态）+ 当前素材
  · `run.py select-candidate <pid> --scene S04 --asset asset_xxx --by 张三 --reason "..." [--dry-run]`
                                            记录人工选定（写既有 `decisions` + `changelog`；**不改任务/产物**）

边界：
  · 记录前先做**只读校验**（素材必须在该镜头候选池中、可用、许可门禁通过）；不通过则
    **不写任何东西**并返回明确错误码；
  · 本模块**不**修改素材时间轴、**不**触发 redo——替换由人工显式执行 `run.py redo <render_task>` 生效
    （复用既有 append-only / version+1 机制）。
"""
from __future__ import annotations

import json
from pathlib import Path

from ..core.selection_review import (SELECTION_NODE, decision_row, selection_projection,
                                     validate_choice)
from ..db.schema import Database
from .metrics import _scene_inputs, semantic_report
from .report import _art, _one, readonly_connection


def review_queue(db_path: str | Path, project_id: str, only_flagged: bool = True) -> dict:
    """只读复核队列：待复核镜头（默认只列语义核验非 MATCH 的）+ 候选池详情。"""
    con = readonly_connection(db_path)
    try:
        project = _one(con, "select project_id, name, status from projects where project_id=?",
                       (project_id,))
        if project is None:
            return {"found": False, "project_id": project_id}
        render = _art(con, project_id, "render_output")
        tl = ((render or {}).get("payload") or {}).get("material_timeline") or []
        con2 = con
        decisions = {r["scene_id"]: r for r in _pending_decisions(con2, project_id)}
    finally:
        con.close()
    sem = semantic_report(db_path, project_id)
    verdicts = {s["scene_id"]: s for s in sem.get("scenes", [])} if sem.get("found") else {}
    items = []
    for s in tl:
        sid = s.get("scene_id")
        v = verdicts.get(sid, {})
        if only_flagged and v.get("verdict") == "MATCH":
            continue
        cur = s.get("selected_asset") or {}
        options = []
        for c in (s.get("candidates") or []):
            options.append({"asset_id": c.get("asset_id"), "name": c.get("name"),
                            "match_score": c.get("match_score"),
                            "usable": bool(c.get("usable", True)),
                            "unusable_reason": c.get("unusable_reason"),
                            "license": c.get("license"), "license_class": c.get("license_class"),
                            "provider": c.get("provider"), "sha256": (c.get("sha256") or "")[:12],
                            "used_by_scenes": c.get("used_by_scenes") or [],
                            "is_current": c.get("asset_id") == cur.get("asset_id")})
        items.append({
            "scene_id": sid,
            "verdict": v.get("verdict"), "rule": v.get("rule"),
            "semantic_reason": v.get("reason"),
            "current_asset": {"asset_id": cur.get("asset_id"), "name": cur.get("name"),
                              "license_class": cur.get("license_class")},
            "options": options, "options_total": len(options),
            "selectable_total": sum(1 for o in options if o["usable"]),
            "pool_empty": not options,
            "pending_decision": decisions.get(sid),
            "rejected_candidates": [{"name": c.get("name"), "error_code": c.get("error_code"),
                                     "detail": str(c.get("error_detail"))[:80]}
                                    for c in (s.get("excluded_candidates") or [])],
        })
    blocked = [i["scene_id"] for i in items if i["pool_empty"] or i["selectable_total"] == 0]
    return {"found": True, "schema": "review-queue-v1", "project": project,
            "render_task": (render or {}).get("task_id"),
            "render_artifact": (render or {}).get("artifact_id"),
            "semantics": sem.get("counts"), "semantics_version": sem.get("version"),
            "items": items, "item_count": len(items),
            "blocked_scenes": blocked,
            "note": "候选池为空或全部不可用的镜头必须 BLOCKED（不得随便选一个）"}


def _pending_decisions(con, project_id: str) -> list[dict]:
    """已记录的人工选定（只读）。"""
    try:
        rows = con.execute("select decision_id, made_by, state, rationale, artifact_snapshot,"
                           " created_at from decisions where project_id=? and node=? "
                           "order by created_at", (project_id, SELECTION_NODE)).fetchall()
    except Exception:                                     # noqa: BLE001
        return []
    out = []
    for r in rows:
        try:
            snap = r["artifact_snapshot"]
            snap = json.loads(snap) if isinstance(snap, str) else (snap or {})
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(snap, dict) and snap.get("scene_id"):
            out.append({"scene_id": snap["scene_id"], "asset_id": snap.get("asset_id"),
                        "decision_id": r["decision_id"], "decided_by": r["made_by"],
                        "reason": r["rationale"], "decided_at": r["created_at"]})
    return out


def record_selection(db_path: str | Path, project_id: str, scene_id: str, asset_id: str,
                     decided_by: str, reason: str, dry_run: bool = False) -> dict:
    """记录"人工明确选定"的候选（写既有 decisions + changelog）。

    先做只读校验（候选池 / 可用性 / 许可门禁）；失败 → 返回 `{"ok": False, "code": ...}` 且**不写任何东西**。
    """
    if not str(decided_by or "").strip():
        return {"ok": False, "code": "HUMAN_SELECTION_NO_REVIEWER",
                "detail": "必须提供 --by（人工决策者标识），拒绝无归属的选材决定"}
    if not str(reason or "").strip():
        return {"ok": False, "code": "HUMAN_SELECTION_NO_REASON",
                "detail": "必须提供 --reason（人工选择理由），拒绝无理由的选材决定"}
    con = readonly_connection(db_path)
    try:
        project = _one(con, "select project_id, name from projects where project_id=?",
                       (project_id,))
        if project is None:
            return {"ok": False, "code": "PROJECT_NOT_FOUND", "detail": project_id}
        render = _art(con, project_id, "render_output")
        tl = ((render or {}).get("payload") or {}).get("material_timeline") or []
        scene = next((s for s in tl if s.get("scene_id") == scene_id), None)
        if scene is None:
            return {"ok": False, "code": "SCENE_NOT_FOUND",
                    "detail": "项目 {} 的最新成片时间轴中没有镜头 {}".format(project_id, scene_id)}
        ok, code, detail = validate_choice(scene.get("candidates") or [], asset_id, scene_id)
        if not ok:
            return {"ok": False, "code": code, "detail": detail}
        chosen = next(c for c in scene["candidates"] if c.get("asset_id") == asset_id)
        before = scene.get("selected_asset") or {}
        render_task, render_art = (render or {}).get("task_id"), (render or {}).get("artifact_id")
    finally:
        con.close()

    row = decision_row(project_id, scene_id, asset_id, decided_by.strip(), reason.strip(),
                       before=before, after=chosen, render_task=render_task,
                       artifact_id=render_art)
    rec = {"ok": True, "code": "OK", "scene_id": scene_id, "asset_id": asset_id,
           "decided_by": row["made_by"], "reason": row["rationale"],
           "before": {"asset_id": before.get("asset_id"), "name": before.get("name")},
           "after": {"asset_id": chosen.get("asset_id"), "name": chosen.get("name"),
                     "license_class": chosen.get("license_class"),
                     "sha256_prefix": (chosen.get("sha256") or "")[:12]},
           "projection_check": sorted(selection_projection(chosen))[:6],
           "render_task": render_task, "render_artifact": render_art,
           "dry_run": bool(dry_run)}
    if dry_run:
        rec["note"] = "dry-run：未写入 decisions/changelog"
        return rec

    db = Database(db_path)
    db.insert_decision(row)
    chg = db.insert_changelog(
        project_id, SELECTION_NODE, "{}:{}".format(scene_id, asset_id), row["made_by"],
        reason="4-C 人工复核替换：{} → {}（{}）".format(
            before.get("name") or before.get("asset_id") or "-", chosen.get("name"), row["rationale"]),
        before_summary="{}|{}".format(before.get("asset_id"), before.get("name")),
        after_summary="{}|{}".format(asset_id, chosen.get("name")), human_confirmed=True)
    rec["decision_id"] = row["decision_id"]
    rec["changelog_id"] = chg
    rec["next_step"] = ("python run.py redo {}  →  python run.py run {} --limit 4"
                        .format(render_task, project_id))
    return rec


def format_review(q: dict) -> str:
    """人可读复核队列。"""
    if not q.get("found"):
        return "项目不存在: {}".format(q.get("project_id"))
    out = ["项目 {} | 语义核验 {}（{}）| 待复核镜头 {} 个".format(
        q["project"]["project_id"], q.get("semantics"), q.get("semantics_version"),
        q.get("item_count"))]
    if q.get("blocked_scenes"):
        out.append("  ⚠ 候选池为空/全不可用 → 必须 BLOCKED：{}".format(q["blocked_scenes"]))
    for it in q.get("items", []):
        out.append("")
        out.append("镜头 {} | 语义判定 {}（{}）".format(it["scene_id"], it["verdict"], it["rule"]))
        out.append("  当前素材：{} （{}）".format(str(it["current_asset"]["name"])[:78],
                                                 it["current_asset"]["asset_id"]))
        out.append("  语义理由：{}".format(str(it.get("semantic_reason"))[:150]))
        out.append("  可选候选（{} 个，其中可用 {} 个）：".format(it["options_total"],
                                                                 it["selectable_total"]))
        for o in it["options"]:
            out.append("    {}{} 分={} | 可用={} | {} | 用于 {} | {}".format(
                "* " if o["is_current"] else "  ", o["asset_id"], o["match_score"], o["usable"],
                o["license_class"], ",".join(o["used_by_scenes"]) or "-", str(o["name"])[:64]))
        if it["rejected_candidates"]:
            out.append("  已拒候选（不可选）：{}".format(
                "; ".join("{}（{}）".format(r["name"][:34], r["error_code"])
                          for r in it["rejected_candidates"][:4])))
        if it.get("pending_decision"):
            d = it["pending_decision"]
            out.append("  已记录人工选定：{} → {}（{}，{}）".format(
                d["scene_id"], d["asset_id"], d["decided_by"], d["decided_at"]))
    out.append("")
    out.append("（只读队列：记录选定请用 `run.py select-candidate`；替换生效请用 `run.py redo <render_task>`）")
    return "\n".join(out)
