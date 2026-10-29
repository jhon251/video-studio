"""Inspect task inputs wiring: are upstream artifact refs resolvable?"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1] if len(sys.argv) > 1 else "p_5125df7514f3"
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
print("=== 任务 inputs 与依赖 ===")
for r in con.execute("select task_type,inputs,dependencies,artifacts from tasks where project_id=?"
                     " order by created_at", (pid,)):
    d = dict(r)
    print("  {:16s} inputs={} deps={} arts={}".format(
        d["task_type"], str(d["inputs"])[:110], str(d["dependencies"])[:60],
        str(d["artifacts"])[:60]))
print("\n=== 可解析性检查 ===")
valid = {r["artifact_id"] for r in con.execute("select artifact_id from artifacts where project_id=?",
                                               (pid,))}
for r in con.execute("select task_type,inputs from tasks where project_id=?", (pid,)):
    d = dict(r)
    try:
        inp = json.loads(d["inputs"]) if isinstance(d["inputs"], str) else d["inputs"]
    except (json.JSONDecodeError, TypeError):
        continue
    for k, v in (inp or {}).items():
        for ref in ([v] if isinstance(v, str) else (v or [])):
            if isinstance(ref, str) and ref.startswith(("a_", "p")):
                print("  {:16s} {}={} 可解析={}".format(d["task_type"], k, ref, ref in valid))
con.close()
