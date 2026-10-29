# -*- coding: utf-8 -*-
"""审计 C：事件流、素材编辑溯源、缺失文件归因、append-only（只读）。"""
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
DB = ROOT / "projects" / "video_studio.db"
PID = "p_96efdc03e1aa"
SNAP = ROOT / "docs" / "regression_2x" / "snapshots" / "5.x-phase5e-20260917.db"


def ro(path):
    con = sqlite3.connect("file:{}?mode=ro".format(pathlib.Path(path).as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


con = ro(DB)
q = lambda sql, args=(): [dict(r) for r in con.execute(sql, args)]

print("=== 11. events 表结构 ===")
print([r[1] for r in con.execute("pragma table_info(events)")])
ev = q("select * from events where project_id=? order by rowid", (PID,))
print("事件数:", len(ev), "| 类型分布:",
      {t: sum(1 for e in ev if e["type"] == t) for t in sorted({e["type"] for e in ev})})
KEY = ("OPERATOR", "INGEST", "CROP", "EDIT", "DELETE", "MATERIAL", "ASSET", "SELECTION", "REDO")
print("\n--- 事件流中与运维/素材相关的（截断显示）---")
for e in ev:
    t, pl = e["type"], str(e["payload"])
    if any(k in t.upper() for k in KEY) or any(k in pl for k in ("crop", "编辑", "裁剪", "删除")):
        print("   #{} {:<22} {:<24} {}".format(e["event_id"], t, str(e["actor"])[:24], pl[:170]))

print("\n=== 12. 素材编辑溯源（GLM 声明『元数据含编辑前后 sha』）===")
idx = ROOT / "projects" / PID / "media" / "external" / ".index.json"
if idx.is_file():
    d = json.loads(idx.read_text(encoding="utf-8"))
    txt = json.dumps(d, ensure_ascii=False)
    print(".index.json keys:", list(d)[:8] if isinstance(d, dict) else type(d))
    print("含 original/edited/pre_crop/crop 字段:", [k for k in ("original_sha", "edited_sha",
                                                                "pre_crop", "crop", "edit")
                                                    if k in txt])
    print(txt[:600])
audits = q("select artifact_id, path, created_at from artifacts where project_id=? and "
           "type='asset_audit' order by created_at", (PID,))
print("\nasset_audit 产物:", [a["artifact_id"] for a in audits])
for a in audits:
    d = json.loads(pathlib.Path(a["path"]).read_text(encoding="utf-8"))
    txt = json.dumps(d, ensure_ascii=False)
    hit = [k for k in ("original_sha", "edited_sha", "pre_crop", "crop", "edit", "裁剪", "编辑")
           if k in txt]
    print("  {} | 字段命中: {} | 前 300 字: {}".format(a["artifact_id"], hit, txt[:300]))

print("\n=== 13. 缺失候选文件归因（是重命名还是删除？） ===")
media = ROOT / "projects" / PID / "media"
stem_ok = []
cands = q("select artifact_id, path from artifacts where project_id=? and "
          "type='retrieval_candidates' order by created_at", (PID,))
missing = {}
for c in cands:
    d = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))
    for cd in d.get("candidates") or []:
        p = cd.get("path")
        if not p:
            continue
        ap = pathlib.Path(p)
        if ap.is_file():
            continue
        alt = list(ap.parent.glob(ap.stem))          # 同名无扩展名
        missing.setdefault(str(ap.relative_to(media)), {"n": 0, "alt": [x.name for x in alt],
                                                        "artifacts": []})
        missing[str(ap.relative_to(media))]["n"] += 1
        missing[str(ap.relative_to(media))]["artifacts"].append(c["artifact_id"])
print("缺失引用（按文件聚合）:", len(missing))
for k, v in sorted(missing.items()):
    print("   {:<70} 引用 {} 次 | 同名无扩展名文件存在={}".format(k[:70], v["n"],
                                                                bool(v["alt"])))
print("\n--- 最终时间轴引用的是哪些路径（应全部存在）---")
r = q("select path from artifacts where project_id=? and type='render_output' "
      "order by created_at desc limit 1", (PID,))[0]
pl = json.loads(pathlib.Path(r["path"]).read_text(encoding="utf-8"))
for s in (pl.get("material_timeline") or [])[:4]:
    a = s.get("selected_asset") or {}
    p = pathlib.Path(a.get("path") or "")
    print("   {} {:<58} exists={}".format(s.get("scene_id"), str(a.get("relative_path"))[:58],
                                          p.is_file()))

print("\n=== 14. append-only（与 5-E 阶段快照对比）===")
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
con.close()

print("\n=== 15. 项目级运维记录文件（非 artifacts/media）===")
for p in sorted((ROOT / "projects" / PID).rglob("*")):
    rel = str(p.relative_to(ROOT / "projects" / PID))
    if p.is_file() and not rel.startswith(("artifacts/", "media/", "output/")):
        print("   ", rel, p.stat().st_size)
