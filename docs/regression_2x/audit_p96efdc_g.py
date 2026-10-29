# -*- coding: utf-8 -*-
"""审计 G：ingest 资产索引（编辑前后 sha 的直接证据）+ 成片逐镜头抽帧独立复测（只读）。"""
import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
PID = "p_96efdc03e1aa"
PDIR = ROOT / "projects" / PID
from video_studio.core.materials import frame_corr, gray48  # noqa: E402
import sqlite3  # noqa: E402

con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row


def sha(p):
    try:
        return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
    except OSError:
        return None


print("=== 24. ingest 资产索引（asset_index 产物）中的本地素材登记值 ===")
for aid in ("a_5990c53da05a", "a_2d62554e3463"):
    row = con.execute("select artifact_id, type, task_id, path from artifacts where artifact_id=?",
                      (aid,)).fetchone()
    if not row:
        print("  ", aid, "不存在")
        continue
    d = json.loads(pathlib.Path(row["path"]).read_text(encoding="utf-8"))
    print("  {} ({}) keys={}".format(aid, row["type"], list(d)[:10]))
    items = d.get("assets") or d.get("items") or d.get("index") or []
    print("   条目数:", len(items) if isinstance(items, list) else "n/a")
    for it in (items if isinstance(items, list) else [])[:14]:
        if not isinstance(it, dict):
            continue
        name = str(it.get("name") or it.get("file") or "")
        rel = it.get("relative_path") or it.get("path") or ""
        full = pathlib.Path(rel)
        full = full if full.is_absolute() else (PDIR / "media" / full)
        cur = sha(full) if full.is_file() else None
        rec = it.get("sha256")
        mark = ""
        if rec and cur and rec != cur:
            mark = "  <== 索引 sha 与磁盘**不一致**（文件在登记后被改动）"
        elif rec and cur:
            mark = "  (一致)"
        print("     {:<46} idx_sha={} disk_sha={} size={} dims={}x{}{}".format(
            name[:46], (rec or "")[:12], (cur or "-")[:12], it.get("bytes"),
            it.get("width"), it.get("height"), mark))
con.close()

print("\n=== 25. 成片逐镜头抽帧独立复测（每镜头中点 1 帧，48×48 灰度相关）===")
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select path from artifacts where project_id=? and type='render_output' "
                "order by created_at desc limit 1", (PID,)).fetchone()
con.close()
payload = json.loads(pathlib.Path(r["path"]).read_text(encoding="utf-8"))
film = pathlib.Path(payload["output"])
tl = payload.get("material_timeline") or []
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FF = cfg["tools"]["ffmpeg"]["path"]
tmp = pathlib.Path(tempfile.mkdtemp(prefix="audit_p96_"))
assets = {}
for s in tl:
    a = s.get("selected_asset") or {}
    if a.get("asset_id"):
        assets[a["asset_id"]] = a.get("path")
rows = []
for s in tl:
    sid, a = s.get("scene_id"), (s.get("selected_asset") or {})
    st, en = float(s.get("start_s") or 0), float(s.get("end_s") or 0)
    mid = st + max(0.0, (en - st) / 2.0)
    fp = tmp / (str(sid) + ".png")
    subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(mid), "-i", str(film),
                    "-frames:v", "1", str(fp)], capture_output=True)
    scores = {}
    if fp.is_file():
        g = gray48(fp)
        for aid, ap in assets.items():
            if ap and pathlib.Path(ap).is_file():
                scores[aid] = round(float(frame_corr(g, gray48(ap))), 4)
    want = scores.get(a.get("asset_id"))
    best = max(scores.values()) if scores else None
    ok = bool(want is not None and want >= 0.30 and want >= (best or 0) - 0.15)
    rows.append({"scene_id": sid, "mid_s": mid, "asset": a.get("asset_id"),
                 "name": str(a.get("name"))[:34], "want": want, "best": best,
                 "argmax_ok": (max(scores, key=scores.get) == a.get("asset_id")) if scores else None,
                 "corr_ok": ok})
    print("  {:<4} t={:<7} {:<16} {:<34} want={:<7} best={:<7} ok={} argmax_ok={}".format(
        sid, round(mid, 1), a.get("asset_id"), str(a.get("name"))[:34], want, best, ok,
        rows[-1]["argmax_ok"]))
print("\n  独立抽帧复测：{} / {} 镜头通过（min_corr 0.30, argmax_margin 0.15）".format(
    sum(1 for x in rows if x["corr_ok"]), len(rows)))
out = ROOT / "docs" / "regression_2x" / "logs" / "audit_p96efdc_film_check.json"
out.write_text(json.dumps({"artifact": r["path"], "film": str(film),
                           "film_sha256": sha(film), "rows": rows,
                           "all_ok": all(x["corr_ok"] for x in rows)},
                          ensure_ascii=False, indent=1), encoding="utf-8")
print("  written", out)
