# -*- coding: utf-8 -*-
"""审计 D：修正候选路径解析（相对项目目录 vs 绝对）、素材文件清点、append-only（只读）。"""
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
PID = "p_96efdc03e1aa"
PDIR = ROOT / "projects" / PID
DB = ROOT / "projects" / "video_studio.db"
SNAP = ROOT / "docs" / "regression_2x" / "snapshots" / "5.x-phase5e-20260917.db"


def ro(path):
    con = sqlite3.connect("file:{}?mode=ro".format(pathlib.Path(path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


def resolve(p):
    if not p:
        return None
    ap = pathlib.Path(p)
    return ap if ap.is_absolute() else (PDIR / ap)


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


con = ro(DB)
q = lambda sql, args=(): [dict(r) for r in con.execute(sql, args)]

print("=== 13b. 候选路径解析（相对项目目录）与文件存在性 ===")
cands = q("select artifact_id, task_id, path from artifacts where project_id=? and "
          "type='retrieval_candidates' order by created_at", (PID,))
print("retrieval_candidates 产物:", [(c["artifact_id"], c["task_id"]) for c in cands])
first = json.loads(pathlib.Path(cands[0]["path"]).read_text(encoding="utf-8"))
print("候选记录字段:", sorted((first.get("candidates") or [{}])[0].keys()))
missing, total, by_art = [], 0, {}
for c in cands:
    d = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))
    for cd in d.get("candidates") or []:
        total += 1
        p = resolve(cd.get("path"))
        ok = bool(p and p.is_file())
        if not ok:
            missing.append((c["artifact_id"], cd.get("name"), cd.get("path")))
            by_art[c["artifact_id"]] = by_art.get(c["artifact_id"], 0) + 1
print("候选记录总数:", total, "| 文件不存在:", len(missing), "| 按产物:",
      {k: v for k, v in sorted(by_art.items())})
for m in missing[:6]:
    print("   !!", m[0], str(m[1])[:52], "|", m[2])

print("\n=== 13c. 磁盘上的素材文件清点（media 下所有非 voice 文件）===")
rows = []
for p in sorted((PDIR / "media").rglob("*")):
    if p.is_file() and "voice" not in p.parts:
        rows.append((str(p.relative_to(PDIR / "media")), p.stat().st_size, (sha(p) or "")[:12]))
for r in rows:
    print("   {:<78} {:>9} {}".format(r[0][:78], r[1], r[2]))

print("\n=== 14b. append-only（与 5-E 阶段快照 DB 对比）===")
if SNAP.is_file():
    s = ro(SNAP)
    for table in ("projects", "tasks", "artifacts", "decisions", "changelog", "events"):
        cols = [x[1] for x in s.execute("pragma table_info({})".format(table))]
        pk = cols[0]
        try:
            old = {str(r[pk]): list(r) for r in s.execute(
                "select * from {} where project_id=?".format(table), (PID,))}
        except sqlite3.OperationalError:
            old = {}
        cur = {str(r[pk]): list(r) for r in con.execute(
            "select * from {} where project_id=?".format(table), (PID,))}
        deleted = sorted(set(old) - set(cur))
        modified = sorted(k for k in set(old) & set(cur) if old[k] != cur[k])
        print("  {:<10} 快照 {} → 当前 {} | 删除 {} | 改写 {} {}".format(
            table, len(old), len(cur), len(deleted), len(modified),
            (deleted[:3], modified[:3]) if (deleted or modified) else ""))
    s.close()
else:
    print("  快照缺失:", SNAP)
con.close()
