# -*- coding: utf-8 -*-
"""5-C 后置快照与对比：记录**替换后**的版本链/时间轴/产物哈希/决定，与 before 逐项对比。

产出：
  docs/regression_2x/logs/phase5c_after.json
  docs/regression_2x/logs/phase5c_compare.json

只读（仅写 logs/），不触碰 DB 与项目产物。
用法：python docs/regression_2x/phase5c_snapshot_after.py
"""
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID = "p_f4b466a4a024"


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except (OSError, TypeError):
        return None


con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
tasks = []
for t in con.execute("select task_id, task_type, status, version, lineage, artifacts, created_at "
                     "from tasks where project_id=? and task_type='render' order by created_at",
                     (PID,)).fetchall():
    tasks.append({"task_id": t["task_id"], "status": t["status"], "version": t["version"],
                  "lineage": json.loads(t["lineage"] or "[]"), "created_at": t["created_at"],
                  "artifacts": json.loads(t["artifacts"] or "[]")})
ros = []
for r in con.execute("select artifact_id, task_id, path, sha256, size, created_at from artifacts "
                     "where project_id=? and type='render_output' order by created_at",
                     (PID,)).fetchall():
    payload = json.loads(pathlib.Path(r["path"]).read_text(encoding="utf-8"))
    ros.append({"artifact_id": r["artifact_id"], "task_id": r["task_id"],
                "artifact_path": r["path"], "artifact_sha256": sha(r["path"]),
                "recorded_sha256": r["sha256"], "recorded_size": r["size"],
                "created_at": r["created_at"],
                "film": payload.get("output"), "film_sha256": sha(payload.get("output")),
                "video_duration_s": payload.get("video_duration_s"),
                "timeline_duration_s": payload.get("timeline_duration_s"),
                "timeline": [{"scene_id": s.get("scene_id"), "start_s": s.get("start_s"),
                              "end_s": s.get("end_s"),
                              "asset_id": (s.get("selected_asset") or {}).get("asset_id"),
                              "asset_name": (s.get("selected_asset") or {}).get("name"),
                              "selection_source": s.get("selection_source")}
                             for s in (payload.get("material_timeline") or [])],
                "material_verification": payload.get("material_verification"),
                "audio_loudness": payload.get("audio_loudness"),
                "attribution_artifact": payload.get("attribution_artifact"),
                "attribution": payload.get("attribution")})
counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
          for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
decisions = [dict(r) for r in con.execute(
    "select decision_id, node, made_by, state, rationale, created_at from decisions "
    "where project_id=? order by created_at", (PID,)).fetchall()]
changelog = [dict(r) for r in con.execute(
    "select change_id, target_type, target_id, changed_by, human_confirmed, created_at "
    "from changelog where project_id=? order by change_id", (PID,)).fetchall()]
con.close()

out = {"project_id": PID, "db_sha256": sha(DB), "counts": counts,
       "render_tasks": tasks, "render_outputs": ros,
       "latest_render_task": (tasks[-1]["task_id"] if tasks else None),
       "latest_render_version": (max(t["version"] for t in tasks) if tasks else None),
       "decisions": decisions, "changelog": changelog}
(LOGS / "phase5c_after.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                         encoding="utf-8")

# ---------------- 对比 ----------------
before = json.loads((LOGS / "phase5c_before.json").read_text(encoding="utf-8"))
b_tasks = {t["task_id"]: t for t in before["render_tasks"]}
a_tasks = {t["task_id"]: t for t in out["render_tasks"]}
b_ros = {r["task_id"]: r for r in before["render_outputs"]}
a_ros = {r["task_id"]: r for r in out["render_outputs"]}

old_tasks_unchanged = all(
    b_tasks[k]["status"] == a_tasks.get(k, {}).get("status")
    and b_tasks[k]["version"] == a_tasks.get(k, {}).get("version")
    for k in b_tasks)
old_artifacts_unchanged = all(
    b_ros[k]["artifact_sha256"] == a_ros.get(k, {}).get("artifact_sha256")
    and b_ros[k]["film_sha256"] == a_ros.get(k, {}).get("film_sha256")
    for k in b_ros)
new_tasks = sorted(set(a_tasks) - set(b_tasks))
new_arts = sorted(set(a_ros) - set(b_ros))

latest = ros[-1] if ros else {}
prev = ros[-2] if len(ros) > 1 else {}
b_latest = before["render_outputs"][-1] if before["render_outputs"] else {}
tl_changes = []
for a, b in zip(latest.get("timeline") or [], b_latest.get("timeline") or []):
    if (a.get("asset_id") or a.get("asset_name")) != (b.get("asset_id") or b.get("asset_name")):
        tl_changes.append({"scene_id": a.get("scene_id"),
                           "before_asset_id": b.get("asset_id"), "before_name": b.get("asset_name"),
                           "before_source": b.get("selection_source"),
                           "after_asset_id": a.get("asset_id"), "after_name": a.get("asset_name"),
                           "after_source": a.get("selection_source")})
new_decisions = [d for d in decisions if d["decision_id"] not in
                 {x["decision_id"] for x in before["decisions"]}]
new_changes = [c for c in changelog if c["change_id"] not in
               {x["change_id"] for x in before["changelog"]}]
cmp_out = {
    "version_chain_before": [(t["task_id"], t["version"], t["status"]) for t in before["render_tasks"]],
    "version_chain_after": [(t["task_id"], t["version"], t["status"]) for t in out["render_tasks"]],
    "old_render_tasks_unchanged": old_tasks_unchanged,
    "old_render_output_artifacts_unchanged": old_artifacts_unchanged,
    "old_film_files_still_present": all(pathlib.Path(b_ros[k]["film"]).exists() for k in b_ros),
    "new_tasks": new_tasks, "new_render_output_artifacts": new_arts,
    "timeline_changed_scenes": tl_changes,
    "timeline_all_other_scenes_identical": len(tl_changes) == 1,
    "counts_before": before["counts"], "counts_after": counts,
    "count_delta": {k: counts[k] - before["counts"][k] for k in counts},
    "latest_render_version": out["latest_render_version"],
    "previous_render_version": prev.get("task_id"),
    "v6_loudness": (latest.get("audio_loudness") or {}),
    "v6_material_verification": latest.get("material_verification"),
    "v6_duration_s": latest.get("video_duration_s"),
    "v5_duration_s": b_latest.get("video_duration_s"),
    "v6_attribution_artifact": latest.get("attribution_artifact"),
    "v5_attribution_artifact": b_latest.get("attribution_artifact"),
    "new_decisions": new_decisions, "new_changelog": new_changes,
    "db_sha256_before": before["db_sha256"], "db_sha256_after": out["db_sha256"],
}
(LOGS / "phase5c_compare.json").write_text(json.dumps(cmp_out, ensure_ascii=False, indent=1),
                                           encoding="utf-8")

print("version chain after:", cmp_out["version_chain_after"])
print("old tasks/artifacts unchanged:", old_tasks_unchanged, old_artifacts_unchanged)
print("old films present:", cmp_out["old_film_files_still_present"])
print("new tasks:", new_tasks, "new artifacts:", new_arts)
print("timeline changed scenes:", json.dumps(tl_changes, ensure_ascii=False, indent=1))
print("counts delta:", cmp_out["count_delta"])
print("v6 duration:", cmp_out["v6_duration_s"], "v5 duration:", cmp_out["v5_duration_s"])
print("v6 loudness:", json.dumps(cmp_out["v6_loudness"], ensure_ascii=False))
print("new decisions:", len(new_decisions), "new changelog:", len(new_changes))
print("written", LOGS / "phase5c_after.json", "and", LOGS / "phase5c_compare.json")
