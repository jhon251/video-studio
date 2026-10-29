# -*- coding: utf-8 -*-
"""Phase 13-E / P13E-1：底片谱系核验（哪条时间轴是权威、P7-6 引用哪条、978.7s 谱系 PI 历史状态）。"""
import hashlib
import json
import pathlib
import sqlite3
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
DB = R / "projects" / "video_studio.db"
sys.stdout.reconfigure(encoding="utf-8")


def probe_dur(p):
    import subprocess
    out = subprocess.run([str(R / "bin" / "ffprobe.exe"), "-v", "error", "-show_entries",
                          "format=duration", "-of", "json", str(p)],
                         capture_output=True, text=True).stdout
    return round(float(json.loads(out)["format"]["duration"]), 1) if out else None


print("== 1) 两条谱系底片 ==")
v9 = R / "projects/p_96efdc03e1aa/output/t_d0a54bdf1810_draft.mp4"
h5 = R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4"
for name, p in (("v9 谱系 t_d0a54bdf1810_draft", v9), ("DCv2/H5 谱系 H5_rp-0ebebb71f99c", h5)):
    print("  {}: {:.1f}s | sha256 {}".format(name, probe_dur(p) or 0,
                                             hashlib.sha256(p.read_bytes()).hexdigest()[:16]))

print("\n== 2) 1532s 时间轴的 S05 窗口（render_output material_timeline）==")
render = json.loads((L / "phase6g_exec_h5_prev_render.json").read_text(encoding="utf-8")) \
    if (L / "phase6g_exec_h5_prev_render.json").is_file() else None
con = sqlite3.connect("file:" + DB.as_posix() + "?mode=ro", uri=True)
con.row_factory = sqlite3.Row
row = con.execute("select path from artifacts where type='render_output' and task_id='t_d0a54bdf1810' "
                  "limit 1").fetchone()
tl1532 = json.loads(pathlib.Path(row["path"]).read_text(encoding="utf-8"))
seg = [e for e in (tl1532.get("material_timeline") or []) if str(e.get("scene_id")) == "S05"]
print("  1532s 轴 S05:", {k: seg[0].get(k) for k in ("scene_id", "start_s", "end_s")} if seg else None)
print("  1532s 轴 场景数/总时长:", len(tl1532.get("material_timeline") or []),
      (tl1532.get("duration_contract") or {}).get("timeline_duration_s"))

print("\n== 3) 978.7s DCv2 谱系时间轴（phase6f/6g 重建计划）==")
cands = sorted(list(L.glob("phase6f*rebuild*")) + list(L.glob("phase6*new_production*")))
for p in cands[:6]:
    print("  候选文件:", p.name, p.stat().st_size, "B")
    try:
        j = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        continue
    for key in ("new_production_timeline", "timeline", "scenes"):
        tl = j.get(key)
        if isinstance(tl, list) and tl:
            s05 = [e for e in tl if str(e.get("scene_id")) == "S05"]
            print("    {}: {} 条 | S05={}".format(key, len(tl),
                                                  {k: s05[0].get(k) for k in ("start_s", "end_s")}
                                                  if s05 else None))
            break
print("\n== 4) H5（978.7s）谱系的 PI/DQ 历史状态 ==")
h5j = json.loads((L / "phase6g_exec_h5.json").read_text(encoding="utf-8"))
g = h5j.get("gates") or {}
print("  gates:", json.dumps(g, ensure_ascii=False)[:300])
print("  PI:", json.dumps(h5j.get("PI"), ensure_ascii=False)[:300])
print("  DQ:", json.dumps(h5j.get("DQ"), ensure_ascii=False)[:200])
con.close()
