"""Print the newest project_id for a given project name (avoids PowerShell quoting issues)."""
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
name = sys.argv[1] if len(sys.argv) > 1 else ""
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
if name:
    row = con.execute("select project_id from projects where name=? order by created_at desc limit 1",
                      (name,)).fetchone()
else:
    row = con.execute("select project_id from projects order by created_at desc limit 1").fetchone()
con.close()
print(row[0] if row else "")
