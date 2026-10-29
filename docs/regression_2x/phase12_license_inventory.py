# -*- coding: utf-8 -*-
"""Phase 12 §1/§2 只读盘点：许可/署名记录到底存放在哪里（DB 表 + 产物 + 缓存元数据）。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
DB = R / "projects" / "video_studio.db"
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")

print("== 1) DB 表清单（找 license/material/download/asset 相关）==")
tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
print("  全部表:", tables)
for t in tables:
    cols = [c[1] for c in con.execute("PRAGMA table_info({})".format(t))]
    hit = [c for c in cols if any(k in c.lower() for k in
                                 ("license", "attribut", "provider", "source", "asset", "url", "sha"))]
    if hit:
        try:
            n = con.execute("select count(*) from '{}'".format(t)).fetchone()[0]
        except sqlite3.Error:
            n = "?"
        print("  {}: 相关列={} | 行数={}".format(t, hit, n))

print("\n== 2) 产物类型清单（找 attribution / material / asset 相关）==")
for r in con.execute("select type, count(*) n from artifacts group by type order by n desc"):
    if any(k in r["type"] for k in ("attribut", "asset", "material", "retrieval", "visual")):
        print("  {}: {}".format(r["type"], r["n"]))

print("\n== 3) p_96efdc03e1aa 的 attribution 产物条目字段 ==")
row = con.execute("select artifact_id, path from artifacts where type='attribution' and "
                  "project_id='p_96efdc03e1aa' order by created_at desc limit 1").fetchone()
if row:
    j = json.loads(pathlib.Path(row["path"]).read_text(encoding="utf-8"))
    print("  artifact:", row["artifact_id"], "| keys:", sorted(j.keys()))
    ent = (j.get("entries") or [])
    print("  条目数:", len(ent), "| 条目字段:", sorted(ent[0].keys()) if ent else None)
    for e in ent[:3]:
        print("   ->", json.dumps({k: e.get(k) for k in
                                  ("scene_id", "scope", "provider", "source_id", "source_url",
                                   "license", "license_class", "attribution", "asset_id",
                                   "sha256", "verified")}, ensure_ascii=False)[:260])
con.close()

print("\n== 4) 下载缓存元数据（external/.index.json）字段 ==")
ext = R / "projects" / "p_96efdc03e1aa" / "media" / "external" / ".index.json"
if ext.is_file():
    j = json.loads(ext.read_text(encoding="utf-8"))
    k0 = next(iter(j))
    print("  条目数:", len(j), "| 键示例:", k0, "| 值字段:", sorted(j[k0].keys()))
    print("  是否含 license/attribution:", any(x in json.dumps(j) for x in ("license", "attribut")))

print("\n== 5) material_timeline selected_asset 的许可字段 ==")
con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
ro = con.execute("select path from artifacts where type='render_output' and "
                 "task_id='t_d0a54bdf1810'").fetchone()
j = json.loads(pathlib.Path(ro["path"]).read_text(encoding="utf-8"))
for seg in (j.get("material_timeline") or [])[:6]:
    sa = seg.get("selected_asset") or {}
    print("  {}: asset={} sha={} license={} class={} provider={} url={}".format(
        seg.get("scene_id"), sa.get("asset_id"), str(sa.get("sha256"))[:10],
        sa.get("license"), sa.get("license_class"), sa.get("provider"),
        str(sa.get("source_url"))[:48]))
con.close()
