"""只读：诊断 4-C 测试夹具项目为何没有候选（检查检索产物与时间轴决策）。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
row = con.execute("select project_id, name from projects where name like 'phase4c%' "
                  "order by created_at desc limit 3").fetchall()
for r in row:
    pid = r["project_id"]
    print("=== {} ({})".format(pid, r["name"]))
    for t in ("retrieval_candidates", "render_output"):
        a = con.execute("select path from artifacts where project_id=? and type=? "
                        "order by created_at desc limit 1", (pid, t)).fetchone()
        if not a:
            print("   {} 缺失".format(t))
            continue
        d = json.loads(Path(a["path"]).read_text(encoding="utf-8"))
        if t == "retrieval_candidates":
            print("   mode={} total={} verified={} rejected={} err={}".format(
                d.get("material_mode"), d.get("candidates_total"), d.get("external_verified"),
                len(d.get("external_rejected") or []), d.get("external_error")))
            print("   query_source={} | query={!r}".format(d.get("query_source"),
                                                           str(d.get("query"))[:120]))
            print("   external_provider={}".format(
                json.dumps(d.get("external_provider"), ensure_ascii=False)[:260]))
            for c in (d.get("candidates") or [])[:4]:
                print("     cand: {} | {}".format(c.get("asset_id"), str(c.get("name"))[:50]))
        else:
            for s in (d.get("material_timeline") or [])[:2]:
                print("     {} fallback={} class={} cands={} selected={}".format(
                    s.get("scene_id"), s.get("fallback_state"), s.get("insufficiency_class"),
                    len(s.get("candidates") or []),
                    (s.get("selected_asset") or {}).get("name")))
                print("       reason={}".format(str(s.get("fallback_reason"))[:110]))
con.close()
