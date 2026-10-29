"""5.x Phase 5-C 前置快照：记录**替换前**的版本链、时间轴、产物哈希、决定/变更行数（只读）。

产出：docs/regression_2x/logs/phase5c_before.json
用法：python docs/regression_2x/phase5c_snapshot_before.py
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
    except OSError:
        return None


con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
tasks = []
for t in con.execute("select task_id, task_type, status, version, lineage, artifacts, created_at "
                     "from tasks where project_id=? and task_type='render' order by created_at",
                     (PID,)).fetchall():
    rec = {"task_id": t["task_id"], "status": t["status"], "version": t["version"],
           "lineage": json.loads(t["lineage"] or "[]"), "created_at": t["created_at"],
           "artifacts": [{"artifact_id": a, "type": (con.execute(
               "select type from artifacts where artifact_id=?", (a,)).fetchone() or ["?"])[0]}
               for a in json.loads(t["artifacts"] or "[]")]}
    tasks.append(rec)
ro_rows = con.execute("select artifact_id, task_id, path, sha256 from artifacts "
                      "where project_id=? and type='render_output' order by created_at",
                      (PID,)).fetchall()
ros = []
for r in ro_rows:
    payload = json.loads(pathlib.Path(r["path"]).read_text(encoding="utf-8"))
    ros.append({"artifact_id": r["artifact_id"], "task_id": r["task_id"],
                "artifact_sha256": sha(r["path"]),
                "film": payload.get("output"), "film_sha256": sha(payload.get("output")),
                "video_duration_s": payload.get("video_duration_s"),
                "timeline": [{"scene_id": s.get("scene_id"), "start_s": s.get("start_s"),
                              "end_s": s.get("end_s"),
                              "asset_id": (s.get("selected_asset") or {}).get("asset_id"),
                              "asset_name": (s.get("selected_asset") or {}).get("name"),
                              "selection_source": s.get("selection_source")}
                             for s in (payload.get("material_timeline") or [])],
                "audio_loudness": {k: (payload.get("audio_loudness") or {}).get(k)
                                   for k in ("ok", "measured_lufs", "measured_true_peak_dbtp")},
                "attribution_artifact": payload.get("attribution_artifact")})
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
(LOGS / "phase5c_before.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                          encoding="utf-8")
print("version chain:", [(t["task_id"], t["version"], t["status"]) for t in tasks])
print("latest:", out["latest_render_task"], "version", out["latest_render_version"])
print("counts:", counts)
print("decisions:", len(decisions), "changelog:", len(changelog))
last = ros[-1] if ros else {}
print("latest film:", pathlib.Path(last.get("film") or "").name, (last.get("film_sha256") or "")[:16])
for s in last.get("timeline") or []:
    print("   ", s["scene_id"], s["start_s"], s["end_s"], s["asset_id"], str(s["asset_name"])[:44],
          s["selection_source"])
print("written", LOGS / "phase5c_before.json")
