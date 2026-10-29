"""只读：打印 3-A 项目的逐镜头旁白 + 所选素材名（设计/验收语义验证器用）。"""
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


def newest(type_):
    r = con.execute("select path, artifact_id, task_id from artifacts where project_id=? and "
                    "type=? order by created_at desc limit 1", (PID, type_)).fetchone()
    return (dict(r), json.loads(Path(r["path"]).read_text(encoding="utf-8"))) if r else (None, None)


_, script = newest("script_output")
r_art, render = newest("render_output")
con.close()
segs = (script or {}).get("segments") or []
tl = (render or {}).get("material_timeline") or []
print("render artifact:", r_art["artifact_id"] if r_art else None, "| scenes:", len(tl),
      "| segments:", len(segs))
for i, s in enumerate(tl):
    seg = segs[i] if i < len(segs) else {}
    a = s.get("selected_asset") or {}
    print("\n--- {} [{}] appears={} corr={}".format(
        s.get("scene_id"), s.get("fallback_state"), s.get("appears_in_film"),
        (s.get("film_evidence") or {}).get("corr_expected")))
    print("  narration({}字): {}".format(len(seg.get("narration") or ""), seg.get("narration")))
    print("  shot_desc: {}".format(str(seg.get("description") or "")[:160]))
    print("  query_text(前160): {}".format(str((s.get("requirement") or {}).get("text") or "")[:160]))
    print("  asset: {}".format(a.get("name")))
    print("  license_class={} provider={}".format(a.get("license_class"), a.get("provider")))
