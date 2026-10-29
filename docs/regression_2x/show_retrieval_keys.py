"""查看 retrieval 产物的键结构（定位 provider stats 的真实位置）。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
pid = sys.argv[1] if len(sys.argv) > 1 else "p_f4b466a4a024"
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select path from artifacts where project_id=? and type='retrieval_candidates' "
                "order by created_at desc limit 1", (pid,)).fetchone()
con.close()
d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
print("top keys:", sorted(d.keys()))
for k, v in d.items():
    if k == "candidates":
        print("candidates -> [{} items]".format(len(v)))
    elif isinstance(v, dict):
        print("{} -> {}".format(k, json.dumps(v, ensure_ascii=False)[:420]))
    else:
        print("{} -> {}".format(k, json.dumps(v, ensure_ascii=False)[:200]))
