# -*- coding: utf-8 -*-
"""5-K 关键验证：`-framerate 1` 是否改变**每镜头时长**（决定该项修复能否正式纳入）。

两组证据：
 A. 隔离实验：精确复刻生产的参数**顺序**与形态，测量不同 d 下的输出时长（对比无 `-framerate`）。
 B. 成片实证：在 p_96efdc03e1aa 最终成片上测量**内容边界**（生成边界两侧各取帧，与两个镜头素材做相关），
    判断内容切换是否发生在时间轴声明的时刻。
"""
import json
import pathlib
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.materials import frame_corr, gray48  # noqa: E402

cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FF = cfg["tools"]["ffmpeg"]["path"]
FP = cfg["tools"]["ffmpeg"]["ffprobe"]
tmp = pathlib.Path(tempfile.mkdtemp(prefix="vs_5k_dur_"))
img = tmp / "img.png"
subprocess.run([FF, "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=0x204060:size=640x360",
                "-frames:v", "1", str(img)], capture_output=True)


def probe(p):
    r = subprocess.run([FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                        str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    d = json.loads(r.stdout or "{}")
    v = next((s for s in d.get("streams") or [] if s.get("codec_type") == "video"), {})
    return {"fmt_dur": round(float((d.get("format") or {}).get("duration") or 0), 3),
            "v_dur": round(float(v.get("duration") or 0), 3), "frames": int(v.get("nb_frames") or 0),
            "avg_fps": v.get("avg_frame_rate"), "r_fps": v.get("r_frame_rate")}


print("=== A. 隔离实验（生产参数顺序：-loop 1 [-framerate 1] -t d -i img，filter_complex + fps=30）===")
for d in (2.0, 2.5, 5.0, 20.0):
    row = {}
    for tag, extra in (("old", []), ("new", ["-framerate", "1"])):
        out = tmp / "d{}_{}.mp4".format(d, tag)
        args = ["-loop", "1", *extra, "-t", "{:.3f}".format(d), "-i", str(img),
                "-filter_complex", "[0:v]scale=640:360,setsar=1,fps=30[v]", "-map", "[v]",
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-t", "{:.3f}".format(d), str(out)]
        subprocess.run([FF, "-y", "-v", "error", *args], capture_output=True)
        row[tag] = probe(out) if out.is_file() else None
    print("  d={:<5} old={} new={} | Δ时长={}".format(
        d, row["old"], row["new"],
        round((row["old"]["fmt_dur"] - row["new"]["fmt_dur"]), 3) if row["old"] and row["new"]
        else None))

print("\n=== B. 成片实证：p_96efdc03e1aa 最终成片的内容边界 ===")
import sqlite3  # noqa: E402
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select path from artifacts where project_id='p_96efdc03e1aa' and "
                "type='render_output' order by created_at desc limit 1").fetchone()
con.close()
payload = json.loads(pathlib.Path(r["path"]).read_text(encoding="utf-8"))
film = pathlib.Path(payload["output"])
tl = payload.get("material_timeline") or []
assets = {(s.get("selected_asset") or {}).get("asset_id"): (s.get("selected_asset") or {}).get("path")
          for s in tl}
print("  成片:", film.name)
print("  流信息:", probe(film))
probe_times = []
for idx in (0, 1, 5, 10, 15, 20):
    if idx + 1 >= len(tl):
        continue
    a, b = tl[idx], tl[idx + 1]
    boundary = float(b["start_s"])
    aid_a = (a.get("selected_asset") or {}).get("asset_id")
    aid_b = (b.get("selected_asset") or {}).get("asset_id")
    probe_times.append((boundary, aid_a, aid_b, idx))

print("\n  边界取样（边界前 4s 应=a 素材；边界后 4s 应=b 素材）：")
for boundary, aid_a, aid_b, idx in probe_times:
    res = {}
    for tag, t in (("before", boundary - 4.0), ("after", boundary + 4.0)):
        fp = tmp / "b{}_{}.png".format(idx, tag)
        subprocess.run([FF, "-y", "-v", "error", "-ss", "{:.3f}".format(max(0.0, t)), "-i",
                        str(film), "-frames:v", "1", str(fp)], capture_output=True)
        scores = {}
        if fp.is_file():
            g = gray48(fp)
            for aid, ap in assets.items():
                if ap and pathlib.Path(ap).is_file():
                    scores[aid] = round(float(frame_corr(g, gray48(ap))), 4)
        res[tag] = {"t": round(t, 2), "argmax": (max(scores, key=scores.get) if scores else None),
                    "scores": scores}
    ok = (res["before"]["argmax"] == aid_a and res["after"]["argmax"] == aid_b)
    print("   S{:02d}→S{:02d} 边界 {:>7.1f}s | before({})={} after({})={} | 与声明一致={}".format(
        idx + 1, idx + 2, boundary, res["before"]["t"], res["before"]["argmax"],
        res["after"]["t"], res["after"]["argmax"], ok))
print("\ntmp:", tmp)
