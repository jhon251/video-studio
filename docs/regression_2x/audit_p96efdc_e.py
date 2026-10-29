# -*- coding: utf-8 -*-
"""审计 E：候选文件真实缺失（media/ 前缀解析）、跨项目完整性、时间线（只读）。"""
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
PID = "p_96efdc03e1aa"
OTHER = "p_f4b466a4a024"
PDIR = ROOT / "projects" / PID
DB = ROOT / "projects" / "video_studio.db"
SNAP = ROOT / "docs" / "regression_2x" / "snapshots" / "5.x-phase5e-20260917.db"


def ro(path):
    con = sqlite3.connect("file:{}?mode=ro".format(pathlib.Path(path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


con = ro(DB)
q = lambda sql, args=(): [dict(r) for r in con.execute(sql, args)]

print("=== 13d. 候选文件缺失（正确解析：项目 media/ 前缀）===")
cands = q("select artifact_id, task_id, path from artifacts where project_id=? and "
          "type='retrieval_candidates' order by created_at", (PID,))
present, missing = [], []
for c in cands:
    d = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))
    for cd in d.get("candidates") or []:
        rel = cd.get("path") or ""
        p = pathlib.Path(rel)
        full = p if p.is_absolute() else (PDIR / "media" / p)
        (present if full.is_file() else missing).append((c["artifact_id"], cd.get("name"), rel))
print("候选记录: 存在 {} | 缺失 {}".format(len(present), len(missing)))
for m in missing:
    print("   !! {} | {} | {}".format(m[0], str(m[1])[:50], m[2]))

print("\n=== 16. 被删缓存文件是否仍在**历史**检索产物中被引用（审计追溯性）===")
print("缺失文件所属检索产物:", {m[0] for m in missing})

print("\n=== 17. 跨项目完整性：p_f4b466a4a024（5-F 的工作对象）是否被外部改动 ===")
if SNAP.is_file():
    s = ro(SNAP)
    for table in ("tasks", "artifacts", "decisions", "changelog", "events"):
        cols = [x[1] for x in s.execute("pragma table_info({})".format(table))]
        pk = cols[0]
        old = {str(r[pk]): list(r) for r in s.execute(
            "select * from {} where project_id=?".format(table), (OTHER,))}
        cur = {str(r[pk]): list(r) for r in con.execute(
            "select * from {} where project_id=?".format(table), (OTHER,))}
        deleted = sorted(set(old) - set(cur))
        modified = sorted(k for k in set(old) & set(cur) if old[k] != cur[k])
        print("  {:<10} 快照 {} → 当前 {} | 删除 {} | 改写 {} {}".format(
            table, len(old), len(cur), len(deleted), len(modified),
            (deleted[:2], modified[:2]) if (deleted or modified) else ""))
    s.close()

print("\n=== 18. 时间线（项目创建 / 关键运维事件 / 5-E 快照 / 5-F 开始）===")
proj = q("select created_at, updated_at from projects where project_id=?", (PID,))[0]
ev = q("select event_id, ts, type, actor, payload from events where project_id=? order by ts", (PID,))
print("项目创建:", proj["created_at"], "| 事件数:", len(ev))
for e in ev:
    if e["type"].startswith("OPERATOR"):
        print("   #{} ts={} {:<26} {}".format(e["event_id"], round(e["ts"]), e["type"],
                                              str(e["payload"])[:110]))
snap_mtime = pathlib.Path(SNAP).stat().st_mtime if SNAP.is_file() else None
print("5-E 快照 DB mtime:", snap_mtime)
last = q("select event_id, ts, type from events where project_id=? order by ts desc limit 3", (PID,))
print("该项目最近事件:", [(x["event_id"], round(x["ts"]), x["type"]) for x in last])
print("我方 5-F 判据证据 mtime:",
      pathlib.Path(ROOT / "docs" / "regression_2x" / "logs" / "phase5f_judge.json").stat().st_mtime)
con.close()
