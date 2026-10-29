"""打印某项目最新 render 的时间轴摘要（逐镜头素材/分数/上屏证据）+ 台账一致性。"""
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
    "select artifact_id, type, path, task_id, created_at from artifacts where project_id=? "
    "and type in ('render_output','attribution') order by created_at", (pid,))]
con.close()
print("artifacts:", [(r["type"], r["artifact_id"], r["created_at"]) for r in rows])
rend = [r for r in rows if r["type"] == "render_output"][-1]
d = json.loads(Path(rend["path"]).read_text(encoding="utf-8"))
tl = d.get("material_timeline") or []
print("\nrender task =", rend["task_id"], "| film =", Path(str(d.get("output"))).name,
      "| duration =", d.get("video_duration_s"))
print("assembly =", (d.get("material_assembly") or {}).get("assembly_class")
      if isinstance(d.get("material_assembly"), dict) else d.get("material_assembly"))
seen = {}
for s in tl:
    a = s.get("selected_asset") or {}
    ev = s.get("film_evidence") or {}
    key = a.get("asset_id")
    seen[key] = seen.get(key, 0) + 1
    print("  {} {:.1f}-{:.1f}s | {} | score={} | appears={} corr={} | provider={}".format(
        s["scene_id"], float(s.get("start_s") or 0), float(s.get("end_s") or 0),
        (a.get("name") or "(占位)")[:52], s.get("match_score") or a.get("retrieval_match_score"),
        s.get("appears_in_film"), ev.get("corr_expected"), a.get("provider")))
print("\ndistinct assets:", len([k for k in seen if k]), seen)
att = [r for r in rows if r["type"] == "attribution"]
if att:
    p = json.loads(Path(att[-1]["path"]).read_text(encoding="utf-8"))
    print("attribution:", att[-1]["artifact_id"], "entries=", p.get("entry_count"),
          "classes=", p.get("license_classes_used"),
          "restricted=", p.get("restricted_or_unknown_in_film"),
          "blocked=", len(p.get("licence_blocked_candidates") or []))
