"""Diagnose why retrieval saw 0 candidates although 3 assets were ingested."""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1] if len(sys.argv) > 1 else "p_"
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

print("=== asset_index 产物（全部）===")
for r in con.execute("select artifact_id,task_id,type,path,summary,created_at from artifacts"
                     " where project_id=? and type='asset_index' order by created_at", (pid,)):
    d = dict(r)
    payload = json.loads(Path(d["path"]).read_text(encoding="utf-8"))
    print("  {} task={} files={} mode={} created={}".format(
        d["artifact_id"], d["task_id"], len(payload.get("files", [])),
        payload.get("material_mode"), d["created_at"]))
    for f in payload.get("files", []):
        print("      - {} {} bytes".format(f.get("path"), f.get("size")))

print("\n=== asset_audit / retrieval 任务 ===")
for r in con.execute("select task_id,task_type,status,artifacts,created_at from tasks"
                     " where project_id=? and task_type in ('asset_audit','retrieval','render')"
                     " order by created_at", (pid,)):
    d = dict(r)
    print("  {} {:12s} {:10s} arts={} created={}".format(
        d["task_id"], d["task_type"], d["status"], d["artifacts"], d["created_at"]))

print("\n=== retrieval 产物内容 ===")
for r in con.execute("select path from artifacts where project_id=? and type='retrieval_candidates'"
                     " order by created_at", (pid,)):
    payload = json.loads(Path(dict(r)["path"]).read_text(encoding="utf-8"))
    print("  mode={} candidates_total={} indexed_files={} index_source={} query_source={}".format(
        payload.get("material_mode"), payload.get("candidates_total"),
        payload.get("indexed_files"), payload.get("index_source"), payload.get("query_source")))
    print("  query={}".format(str(payload.get("query"))[:200]))

print("\n=== 项目 media 目录 ===")
media = ROOT / "projects" / pid / "media"
for p in sorted(media.rglob("*")):
    if p.is_file():
        print("  {} {} bytes".format(p.relative_to(media), p.stat().st_size))
con.close()
