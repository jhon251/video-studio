# -*- coding: utf-8 -*-
"""5-L：p_96efdc03e1aa 重渲染**前后事实快照**（只读）——证明除成片外一切未变。

用法: python docs/regression_2x/phase5l_snapshot.py <label> [project_id]
产出: docs/regression_2x/logs/phase5l_snapshot_<label>.json
"""
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
label = sys.argv[1] if len(sys.argv) > 1 else "before"
pid = sys.argv[2] if len(sys.argv) > 2 else "p_96efdc03e1aa"
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def abspath(rel: str) -> Path:
    p = Path(rel)
    return p if p.is_absolute() else ROOT / p


out = {"label": label, "project_id": pid}

# 1. 产物（含文件 sha256）——topic/script/claims 等不得变化
arts = []
for r in con.execute("select artifact_id, type, path, sha256, size, version, superseded_by, "
                     "created_at from artifacts where project_id=? order by created_at", (pid,)):
    a = dict(r)
    p = abspath(a["path"]) if a["path"] else None
    a["file_sha256"] = sha(p) if p and p.is_file() else None
    a["file_bytes"] = p.stat().st_size if p and p.is_file() else None
    arts.append(a)
out["artifacts"] = arts
out["artifacts_by_type"] = dict(Counter(a["type"] for a in arts))

# 2. claims / decisions / tasks
out["claims_by_status"] = {r[0]: r[1] for r in con.execute(
    "select status, count(*) from claims where project_id=? group by status", (pid,))}
out["claim_ids"] = [r[0] for r in con.execute(
    "select claim_id from claims where project_id=? order by claim_id", (pid,))]
out["decisions"] = {
    "count": con.execute("select count(*) from decisions where project_id=?", (pid,)).fetchone()[0],
    "by_node": dict(Counter(str(r[0]) for r in con.execute(
        "select node from decisions where project_id=?", (pid,)))),
    "by_made_by": dict(Counter(str(r[0]) for r in con.execute(
        "select made_by from decisions where project_id=?", (pid,)))),
}
out["tasks"] = [{"task_id": r[0], "task_type": r[1], "version": r[2], "status": r[3],
                 "artifacts": r[4]} for r in con.execute(
    "select task_id, task_type, version, status, artifacts from tasks where project_id=? "
    "order by created_at", (pid,))]
con.close()

# 3. 成片文件（output/ 下的 mp4）
films = {}
for p in sorted((ROOT / "projects" / pid / "output").glob("*.mp4")):
    films[p.name] = {"bytes": p.stat().st_size, "sha256": sha(p),
                     "mtime": int(p.stat().st_mtime)}
out["films"] = films

(LOGS / "phase5l_snapshot_{}.json".format(label)).write_text(
    json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("label:", label, "| artifacts:", len(arts), "| claims:", sum(out["claims_by_status"].values()),
      out["claims_by_status"], "| decisions:", out["decisions"]["count"],
      "| films:", len(films))
for name, f in films.items():
    print("   film {:44s} {:>10d} B  sha {}  mtime {}".format(name, f["bytes"], f["sha256"][:16],
                                                              f["mtime"]))
print("json ->", LOGS / "phase5l_snapshot_{}.json".format(label))
