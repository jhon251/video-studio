"""查看某项目最新 retrieval 产物的关键字段（mode/下载字节/query 阶梯/许可证类别）。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1] if len(sys.argv) > 1 else "p_f4b466a4a024"
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute(
    "select artifact_id, path, created_at from artifacts where project_id=? and "
    "type='retrieval_candidates' order by created_at", (pid,))]
con.close()
print("retrieval artifacts:", len(rows))
d = json.loads(Path(rows[-1]["path"]).read_text(encoding="utf-8"))
prov = (d.get("material_providers") or {})
print("material_mode =", d.get("material_mode"), "| reason =", d.get("material_mode_reason"))
print("provider =", prov)
print("external_requested =", d.get("external_requested"), "| verified =",
      len([c for c in (d.get("candidates") or []) if c.get("provider")]))
print("candidates_total =", d.get("candidates_total"), "| rejected =",
      len(d.get("external_rejected") or []))
for c in (d.get("candidates") or [])[:10]:
    print("  - {} | {} | {} | rel={}".format(
        c.get("name", "")[:56], c.get("license"), c.get("provider") or "local",
        c.get("path") or c.get("relative_path")))
