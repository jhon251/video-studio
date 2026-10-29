"""Prove cross-project agent_note contamination (theme drift root cause)."""
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row

print("memories 列:", [r[1] for r in con.execute("PRAGMA table_info(memories)")])
print("\n=== agent_role='structure' 的 agent_note（最近 8 条，跨项目）===")
for r in con.execute("select * from memories where agent_role='structure' order by rowid desc limit 8"):
    d = dict(r)
    print("  project={} kind={} content={}".format(d.get("project_id"), d.get("kind"),
                                                   str(d.get("content"))[:150]))

print("\n=== working_context 实际取到的 3 条（project_id=None 时）===")
for r in con.execute("select * from memories where kind='agent_note' and agent_role='structure'"
                     " order by rowid desc limit 3"):
    d = dict(r)
    print("  [{}] {}".format(d.get("project_id"), str(d.get("content"))[:150]))

print("\n=== C 组结构产物里出现的脑机接口痕迹（应来自上述经验）===")
p = ROOT / "projects" / "p_5125df7514f3"
import json
arts = {}
c2 = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
c2.row_factory = sqlite3.Row
for r in c2.execute("select * from artifacts where project_id='p_5125df7514f3' and type='structure_output'"):
    d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
    print("  章节:", [c.get("title") for c in d.get("chapters", [])])
c2.close()
con.close()
