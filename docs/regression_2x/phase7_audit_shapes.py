# -*- coding: utf-8 -*-
"""Phase 7 只读审计：导出 6.x 真实 artifact 结构（visual_plan / retrieval_candidates / asset_index /
material_timeline / attribution）——只读 DB，不写任何东西。"""
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")
con = sqlite3.connect("file:{}?mode=ro".format((R / "projects/video_studio.db").as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")


def latest(atype, task_id=None):
    q = ("select artifact_id,task_id,path,created_at from artifacts where type=? "
         + ("and task_id=? " if task_id else "") + "order by created_at desc limit 1")
    args = (atype, task_id) if task_id else (atype,)
    return next((dict(r) for r in con.execute(q, args)), None)


def load(row):
    if not row:
        return None
    p = pathlib.Path(row["path"])
    p = p if p.is_absolute() else R / p
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:                                              # noqa: BLE001
        return {"__error__": str(exc)[:120], "__path__": str(p)}


print("=== v9 render_output（material_timeline 单条结构）===")
ro = latest("render_output", "t_d0a54bdf1810")
d = load(ro)
tl = d.get("material_timeline") or []
print("top keys:", sorted(d.keys())[:18])
print("material_timeline n =", len(tl))
if tl:
    print("segment[0] keys:", sorted(tl[0].keys()))
    print("segment[0]:", json.dumps({k: v for k, v in tl[0].items() if k != "selected_asset"},
                                    ensure_ascii=False)[:400])
    print("segment[0].selected_asset keys:", sorted((tl[0].get("selected_asset") or {}).keys()))
    print("  ->", json.dumps(tl[0].get("selected_asset"), ensure_ascii=False)[:400])
print()
print("=== visual_plan_output ===")
vp = latest("visual_plan_output")
v = load(vp)
if v:
    print("top keys:", sorted(v.keys())[:20])
    for k in ("scenes", "shots", "plan", "visual_plan"):
        if isinstance(v.get(k), list) and v[k]:
            print("  {}[0] keys: {}".format(k, sorted(v[k][0].keys())))
            print("  {}[0]: {}".format(k, json.dumps(v[k][0], ensure_ascii=False)[:420]))
            break
print()
print("=== retrieval_candidates ===")
rc = latest("retrieval_candidates")
c = load(rc)
if c:
    print("top keys:", sorted(c.keys())[:20])
    for k in ("candidates", "items", "results"):
        if isinstance(c.get(k), list) and c[k]:
            print("  {} n={} [0] keys: {}".format(k, len(c[k]), sorted(c[k][0].keys())))
            print("  [0]:", json.dumps(c[k][0], ensure_ascii=False)[:500])
            break
print()
print("=== asset_index ===")
ai = latest("asset_index")
a = load(ai)
if a:
    print("top keys:", sorted(a.keys())[:20])
    for k in ("assets", "items", "index"):
        if isinstance(a.get(k), list) and a[k]:
            print("  {} n={} [0] keys: {}".format(k, len(a[k]), sorted(a[k][0].keys())))
            print("  [0]:", json.dumps(a[k][0], ensure_ascii=False)[:500])
            break
print()
print("=== attribution ===")
at = latest("attribution")
t = load(at)
if t:
    print("top keys:", sorted(t.keys())[:20])
    for k in ("attributions", "items", "records"):
        if isinstance(t.get(k), list) and t[k]:
            print("  {} n={} [0]: {}".format(k, len(t[k]),
                                              json.dumps(t[k][0], ensure_ascii=False)[:400]))
            break
con.close()
