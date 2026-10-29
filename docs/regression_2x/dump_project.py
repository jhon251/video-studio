"""Dump the key artifacts of a real-LLM project (to design objective content checks)."""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1]
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
arts = {}
for r in con.execute("select * from artifacts where project_id=?", (pid,)):
    arts.setdefault(r["type"], []).append(dict(r))
con.close()

print("artifact types:", sorted(arts))
for t in ("topic_output", "structure_output", "script_output", "visual_plan_output",
          "subtitle", "voice_output", "editing_plan_output", "render_output", "qa_report"):
    lst = arts.get(t) or []
    if not lst:
        print("\n--- {} : 缺失 ---".format(t))
        continue
    d = json.loads(Path(lst[-1]["path"]).read_text(encoding="utf-8"))
    print("\n--- {} ({}) ---".format(t, Path(lst[-1]["path"]).name))
    print(json.dumps(d, ensure_ascii=False, indent=1)[:1500])
