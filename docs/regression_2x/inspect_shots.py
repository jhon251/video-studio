"""Inspect visual_plan shots by source type (to make the completeness check source-aware)."""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1] if len(sys.argv) > 1 else "p_314efdfbbeb2"
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute(
    "select * from artifacts where project_id=? and type='visual_plan_output'", (pid,))]
con.close()
d = json.loads(Path(rows[-1]["path"]).read_text(encoding="utf-8"))
print("shots:", len(d.get("shots", [])), "| source 分布:",
      dict(Counter(s.get("source") for s in d["shots"])))
for i, s in enumerate(d["shots"], 1):
    miss = [k for k in ("description", "shot_size", "duration_s", "source") if not s.get(k)]
    gp = s.get("gen_prompt") or ""
    print("shot{:2d} source={:14s} gen_prompt={:4d}字 缺失={} | {}".format(
        i, str(s.get("source")), len(gp), miss or "无", str(s.get("description"))[:34]))
