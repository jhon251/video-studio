"""只读：查看 timeline 场景的完整字段 + visual_plan 逐镜头文本（确认真实匹配口径）。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
PID = sys.argv[1] if len(sys.argv) > 1 else "p_f4b466a4a024"
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row


def newest(t):
    r = con.execute("select path, artifact_id from artifacts where project_id=? and type=? "
                    "order by created_at desc limit 1", (PID, t)).fetchone()
    return (dict(r), json.loads(Path(r["path"]).read_text(encoding="utf-8"))) if r else (None, None)


_, render = newest("render_output")
_, vp = newest("visual_plan_output")
con.close()
tl = (render or {}).get("material_timeline") or []
print("=== timeline 场景字段（S04）")
for k, v in (tl[3] if len(tl) > 3 else {}).items():
    print("  {:26s} {}".format(k, json.dumps(v, ensure_ascii=False)[:220]))
print("\n=== visual_plan 镜头文本")
for i, sh in enumerate((vp or {}).get("shots") or []):
    print("  shot{} idx={} desc={!r} gen={!r}".format(
        i, sh.get("index"), str(sh.get("description") or "")[:150],
        str(sh.get("gen_prompt") or "")[:150]))
