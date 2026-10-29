"""4-C 只读：导出待替换镜头的**真实候选池**（含验证/许可/在屏状态），供人工选择。

用法：python docs/regression_2x/phase4c_dump_candidates.py <pid> [scene_id ...]
"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
PID = sys.argv[1] if len(sys.argv) > 1 else "p_f4b466a4a024"
WANT = sys.argv[2:] or ["S04", "S06"]
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select path, artifact_id, task_id from artifacts where project_id=? and "
                "type='render_output' order by created_at desc limit 1", (PID,)).fetchone()
con.close()
render = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
tl = render.get("material_timeline") or []
print("项目 {} | render artifact {} | render task {}".format(PID, r["artifact_id"], r["task_id"]))
print("已入库（可用）素材池：")
seen = {}
for s in tl:
    a = s.get("selected_asset") or {}
    if a:
        seen.setdefault(a.get("asset_id"), {"name": a.get("name"), "scenes": [],
                                            "license_class": a.get("license_class"),
                                            "provider": a.get("provider"),
                                            "sha256": (a.get("sha256") or "")[:12]})
        seen[a["asset_id"]]["scenes"].append(s.get("scene_id"))
for aid, v in sorted(seen.items()):
    print("  {} | 用于 {} | {} | {}".format(aid, ",".join(v["scenes"]), v["license_class"],
                                            str(v["name"])[:78]))
for sid in WANT:
    sc = next((s for s in tl if s.get("scene_id") == sid), None)
    if sc is None:
        print("\n{} 不存在".format(sid))
        continue
    a = sc.get("selected_asset") or {}
    print("\n=== {} 当前：{} | 素材分={} | 原因={}".format(
        sid, str(a.get("name"))[:70], sc.get("match_score"),
        str(sc.get("selection_reason"))[:150]))
    print("  可替换选项（本镜头候选，已排序）：")
    for c in (sc.get("candidates") or []):
        print("    - {:<22s} 分={:<4} 可用={} | {} | {}".format(
            c.get("asset_id"), c.get("match_score"), c.get("usable", True),
            c.get("name", "")[:62], c.get("license_class")))
    if sc.get("excluded_candidates"):
        print("  已拒候选（许可/校验未过，**不可选**）：")
        for c in sc["excluded_candidates"]:
            print("    - {} | {} | {}".format(c.get("name", "")[:56], c.get("error_code"),
                                              str(c.get("error_detail"))[:60]))
