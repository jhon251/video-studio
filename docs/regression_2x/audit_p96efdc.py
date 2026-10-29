# -*- coding: utf-8 -*-
"""审计 A：项目 p_96efdc03e1aa 的工程状态、任务链、版本链、产物与关键声明核对（只读）。

用法：python docs/regression_2x/audit_p96efdc.py
"""
import hashlib
import json
import pathlib
import sqlite3
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
DB = ROOT / "projects" / "video_studio.db"
PID = "p_96efdc03e1aa"
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row


def q(sql, args=()):
    return [dict(r) for r in con.execute(sql, args)]


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


print("=== 1. 项目 ===")
proj = q("select * from projects where project_id=?", (PID,))
print(json.dumps(proj, ensure_ascii=False, default=str)[:400] if proj else "PROJECT NOT FOUND")
if not proj:
    sys.exit(0)
pdir = ROOT / "projects" / PID
files = [p for p in pdir.rglob("*") if p.is_file()]
print("project files:", len(files), "| films:", len(list((pdir / 'output').glob('*.mp4'))))

print("\n=== 2. 任务链（retrieval / render / assembly / 其它关键）===")
rows = q("select task_id, task_type, status, version, created_at, error, artifacts, inputs "
         "from tasks where project_id=? order by created_at", (PID,))
print("tasks total:", len(rows))
for r in rows:
    if r["task_type"] in ("retrieval", "render", "assembly", "voice", "script", "visual_plan"):
        err = (str(r["error"])[:60] if r["error"] else "")
        print("  v{:<2} {:<12} {:<18} {} {}".format(r["version"], r["task_type"], r["task_id"],
                                                   r["status"], err))
print("\n按类型统计:", {t: sum(1 for r in rows if r["task_type"] == t)
                       for t in sorted({r["task_type"] for r in rows})})
print("非 SUCCEEDED 任务:",
      [(r["task_id"], r["task_type"], r["status"], str(r["error"])[:50])
       for r in rows if r["status"] not in ("SUCCEEDED",)][:10])

print("\n=== 3. render 版本链与成片 ===")
renders = [r for r in rows if r["task_type"] == "render"]
for r in renders:
    arts = json.loads(r["artifacts"] or "[]")
    ro = q("select artifact_id, type, path, created_at from artifacts where task_id=? and type='render_output'", (r["task_id"],))
    film, dur, loud, mv, sel = None, None, None, None, None
    if ro:
        pl = json.loads(pathlib.Path(ro[0]["path"]).read_text(encoding="utf-8"))
        film = pl.get("output")
        dur = pl.get("video_duration_s")
        loud = {k: (pl.get("audio_loudness") or {}).get(k) for k in ("ok", "measured_lufs",
                                                                    "measured_true_peak_dbtp")}
        mv = {k: (pl.get("material_verification") or {}).get(k) for k in ("checked_scenes_total",
                                                                         "failed_scenes")}
        sel = {s.get("selection_source") for s in (pl.get("material_timeline") or [])}
    print("  v{} {} {} | film={} dur={} loud={} mv={} sel_sources={}".format(
        r["version"], r["task_id"], r["status"],
        (pathlib.Path(film).name if film else None), dur, loud, mv, sel))
    if film and not pathlib.Path(film).is_file():
        print("     !! 成片文件缺失:", film)

print("\n=== 4. 最新 render_output 与 assembly ===")
latest = q("select artifact_id, task_id, path, created_at from artifacts where project_id=? "
           "and type='render_output' order by created_at desc", (PID,))
print("render_output 产物数:", len(latest))
asm = q("select artifact_id, task_id, path, created_at from artifacts where project_id=? "
        "and type='assembly' order by created_at desc limit 3", (PID,))
print("assembly 产物:", [(a["artifact_id"], a["task_id"]) for a in asm])
con.close()

print("\n=== 5. 素材文件与 attribution 台账 sha 一致性（关键完整性检查）===")
payload = json.loads(pathlib.Path(latest[0]["path"]).read_text(encoding="utf-8"))
tl = payload.get("material_timeline") or []
print("镜头数:", len(tl), "| 有素材镜头:", sum(1 for s in tl if s.get("selected_asset")))
bad_sha, missing = [], []
used = {}
for s in tl:
    a = s.get("selected_asset") or {}
    if not a:
        continue
    used.setdefault(a.get("asset_id"), {"name": a.get("name"), "sha": a.get("sha256"),
                                        "path": a.get("path"), "scenes": [], "source": a.get("source")})
    used[a["asset_id"]]["scenes"].append(s.get("scene_id"))
    p = a.get("path")
    if not p or not pathlib.Path(p).is_file():
        missing.append((s.get("scene_id"), a.get("asset_id"), p))
    elif sha(p) != a.get("sha256"):
        bad_sha.append((s.get("scene_id"), a.get("asset_id"), a.get("name"),
                        (a.get("sha256") or "")[:12], (sha(p) or "")[:12]))
print("使用中的素材:", len(used))
for aid, v in used.items():
    print("  {} x{} 镜 {} | {} | sha={}… | source={}".format(
        aid, len(v["scenes"]), v["scenes"][:3], str(v["name"])[:44], (v["sha"] or "")[:12],
        v["source"]))
print("时间轴 sha 与磁盘不符:", len(bad_sha))
for x in bad_sha:
    print("   !!", x)
print("时间轴引用的素材文件缺失:", len(missing))
for x in missing:
    print("   !!", x)

att_id = payload.get("attribution_artifact")
if att_id:
    ap = ROOT / "projects" / PID / "artifacts" / (att_id + ".json")
    att = json.loads(ap.read_text(encoding="utf-8"))
    entries = att.get("entries") or []
    mism = []
    for e in entries:
        a = e.get("selected_asset") or {}
        p = a.get("path")
        if not p or not pathlib.Path(p).is_file():
            mism.append((e.get("scene_id"), "MISSING", a.get("name")))
        elif sha(p) != a.get("sha256"):
            mism.append((e.get("scene_id"), "SHA_DIFF", a.get("name"),
                         (a.get("sha256") or "")[:12], (sha(p) or "")[:12]))
    print("attribution 台账 {}：条目 {} | 与磁盘不一致 {} 条".format(att_id, len(entries), len(mism)))
    for x in mism:
        print("   !!", x)
    print("attribution 许可类别:", sorted({e.get("license_class") for e in entries}))
    print("restricted_or_unknown_in_film:", att.get("restricted_or_unknown_in_film"))
print("\n=== 6. 人工选定（decisions / changelog）===")
dec = q("select decision_id, node, made_by, state, rationale, artifact_snapshot, created_at "
        "from decisions where project_id=? and node='selection_override' order by created_at", (PID,))
print("selection_override 决定数:", len(dec))
for d in dec[:3]:
    print("  ", d["decision_id"], d["made_by"], json.loads(d["artifact_snapshot"]) if isinstance(d["artifact_snapshot"], str) else d["artifact_snapshot"])
chg = q("select change_id, target_type, target_id, changed_by, human_confirmed, created_at "
        "from changelog where project_id=? order by change_id", (PID,))
print("changelog 行数:", len(chg), "| 最近 3 条:", [(c["change_id"], c["target_type"], c["target_id"]) for c in chg[-3:]])
