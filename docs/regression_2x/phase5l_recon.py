# -*- coding: utf-8 -*-
"""5-L 侦察（只读）：p_96efdc03e1aa 的渲染任务/时间轴/claim 闸门状态 + 现有成片事实。

用法: python docs/regression_2x/phase5l_recon.py [project_id]
产出: docs/regression_2x/logs/phase5l_recon.json
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
pid = sys.argv[1] if len(sys.argv) > 1 else "p_96efdc03e1aa"
DB = ROOT / "projects" / "video_studio.db"
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
out = {"project_id": pid}

print("== projects ==")
for r in con.execute("select * from projects where project_id=?", (pid,)):
    d = dict(r)
    out["project"] = {k: str(v)[:200] for k, v in d.items()}
    print(" ", {k: str(v)[:80] for k, v in d.items()})

print("\n== tasks (render / editing / audio / subtitle 相关) ==")
rows = [dict(r) for r in con.execute(
    "select task_id, task_type, agent_role, status, version, dependencies, artifacts, "
    "retry_count, approval, error, created_at, updated_at from tasks where project_id=? "
    "order by created_at", (pid,))]
out["task_count"] = len(rows)
for r in rows:
    if r["task_type"] in ("render", "editing_plan", "audio_mix", "subtitle", "voice",
                          "visual_source"):
        print("  {:16s} {:12s} v={} {:10s} arts={} approval={} err={}".format(
            r["task_id"], r["task_type"], r["version"], r["status"],
            str(r["artifacts"])[:60], str(r["approval"])[:18], str(r["error"])[:40]))

print("\n== artifacts ==")
arts = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path, sha256, size, version, superseded_by, created_at "
    "from artifacts where project_id=? order by created_at", (pid,))]
out["artifacts"] = [{k: (str(v)[:300]) for k, v in a.items()} for a in arts]
from collections import Counter
print("  by type:", dict(Counter(a["type"] for a in arts)))
for a in arts:
    if a["type"] in ("render_output", "timeline", "narration", "subtitles", "subtitle_file",
                     "attribution"):
        print("  {:20s} {:18s} v={} {:>10s} sup={} {}".format(
            a["artifact_id"], a["type"], a["version"], str(a["size"]), a["superseded_by"],
            str(a["path"])[-60:]))

print("\n== claims ==")
ccount = {r[0]: r[1] for r in con.execute(
    "select status, count(*) from claims where project_id=? group by status", (pid,))}
out["claims_by_status"] = ccount
print(" ", ccount)
bad = [dict(r) for r in con.execute(
    "select claim_id, status, text from claims where project_id=? and status not in "
    "('VERIFIED','REJECTED')", (pid,))]
out["claims_not_passed"] = [{k: str(v)[:140] for k, v in b.items()} for b in bad]
print("  not passed:", len(bad))
for b in bad[:8]:
    print("   ", b["claim_id"], b["status"], str(b["text"])[:70])

print("\n== decisions (human) ==")
d = [dict(r) for r in con.execute(
    "select decision_id, node, made_by, state, created_at from decisions where project_id=? "
    "order by created_at", (pid,))]
out["decision_count"] = len(d)
from collections import Counter as _C
print("  total:", len(d), "| by node:", dict(_C(str(x["node"]) for x in d)),
      "| by made_by:", dict(_C(str(x["made_by"]) for x in d)))

# 时间轴总时长（取最新 timeline 产物）
tl = [a for a in arts if a["type"] == "timeline"]
if tl:
    last = tl[-1]
    p = Path(last["path"]) if last["path"] else None
    if p and not p.is_absolute():
        p = ROOT / p
    if p and p.is_file():
        data = json.loads(p.read_text(encoding="utf-8"))
        scenes = data if isinstance(data, list) else (data.get("scenes") or [])
        total = 0.0
        for s in scenes:
            total += float(s.get("end_s", 0)) - float(s.get("start_s", 0))
        out["timeline"] = {"artifact": last["artifact_id"], "path": str(p),
                           "scenes": len(scenes), "sum_duration_s": round(total, 3)}
        print("\n== timeline ==")
        print(" ", out["timeline"])
con.close()
(LOGS / "phase5l_recon.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
print("\njson ->", LOGS / "phase5l_recon.json")
