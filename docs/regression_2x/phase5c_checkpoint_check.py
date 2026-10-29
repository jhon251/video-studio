# -*- coding: utf-8 -*-
"""5-C 断点检查（只读）：冻结日志漂移 + DB 关键状态 + 版本链。"""
import hashlib
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BAK = ROOT / "docs" / "regression_2x" / "logs_5b_frozen"
PID = "p_f4b466a4a024"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


drift = []
checked = 0
for p in sorted(LOGS.rglob("*")):
    if not p.is_file():
        continue
    rel = str(p.relative_to(LOGS)).replace("\\", "/")
    if rel.startswith("phase5c_rerun/") or rel.split("/")[0].startswith("phase5c_"):
        continue
    b = BAK / rel
    checked += 1
    if not b.is_file():
        drift.append(("NOT_IN_BACKUP", rel))
    elif sha(p) != sha(b):
        drift.append(("DRIFT", rel))
print("frozen logs checked:", checked, "| drift:", len(drift))
for d in drift[:20]:
    print("   ", d)

con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
print("counts:", {t: con.execute("select count(*) from " + t).fetchone()[0]
                  for t in ("projects", "tasks", "artifacts", "events", "decisions", "changelog")})
print("latest 3 projects:")
for r in con.execute("select project_id, name, created_at from projects order by created_at desc "
                     "limit 3"):
    print("   ", dict(r))
print("render versions of", PID, ":")
for r in con.execute("select task_id, version, status from tasks where project_id=? and "
                     "task_type='render' order by version", (PID,)):
    print("   ", r["task_id"], r["version"], r["status"])
print("v6 film exists:", (ROOT / "projects" / PID / "output" /
                          "t_6d692b93e342_draft.mp4").is_file())
con.close()
