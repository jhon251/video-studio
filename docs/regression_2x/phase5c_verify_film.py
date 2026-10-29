# -*- coding: utf-8 -*-
"""5-C 成片技术核验（只读）：ffprobe 容器/编码/时长、独立 ebur128 实测响度、
逐镜头抽帧 48×48 灰度 Pearson 反查（证明像素级确为所选素材）。

用法：python docs/regression_2x/phase5c_verify_film.py [artifact_id]
产出：docs/regression_2x/logs/phase5c_film_verify.json
"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
ART = sys.argv[1] if len(sys.argv) > 1 else "a_fa4716cffb26"  # v6 render_output

from video_studio.core.materials import frame_corr, gray48  # noqa: E402

cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
_tools = (cfg.get("tools") or {}).get("ffmpeg") or {}
ffmpeg = _tools.get("path") or "ffmpeg"
ffprobe = _tools.get("ffprobe") or "ffprobe"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return p.returncode, (p.stdout or "") + (p.stderr or "")


payload = json.loads((ROOT / "projects" / "p_f4b466a4a024" / "artifacts" / (ART + ".json"))
                     .read_text(encoding="utf-8"))
film = pathlib.Path(payload["output"])
out = {"artifact_id": ART, "film": str(film), "exists": film.exists()}
out["film_sha256"] = hashlib.sha256(film.read_bytes()).hexdigest()
out["film_bytes"] = film.stat().st_size

# ---------- ffprobe ----------
rc, txt = run([ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
               str(film)])
out["ffprobe_rc"] = rc
probe = json.loads(txt)
out["format"] = {k: probe["format"].get(k) for k in ("format_name", "duration", "size", "bit_rate")}
streams = []
for s in probe["streams"]:
    streams.append({"index": s.get("index"), "type": s.get("codec_type"),
                    "codec": s.get("codec_name"), "profile": s.get("profile"),
                    "width": s.get("width"), "height": s.get("height"),
                    "pix_fmt": s.get("pix_fmt"), "sample_rate": s.get("sample_rate"),
                    "channels": s.get("channels"), "nb_frames": s.get("nb_frames"),
                    "duration": s.get("duration"), "avg_frame_rate": s.get("avg_frame_rate")})
out["streams"] = streams
v = next((s for s in streams if s["type"] == "video"), {})
a = next((s for s in streams if s["type"] == "audio"), {})
out["video_codec_ok"] = v.get("codec") == "h264"
out["audio_codec_ok"] = a.get("codec") == "aac"
out["duration_s"] = float(probe["format"].get("duration") or 0.0)
out["payload_video_duration_s"] = payload.get("video_duration_s")
out["duration_matches_payload"] = abs(out["duration_s"] - float(payload.get("video_duration_s") or -1)) < 0.5

# ---------- 独立响度实测（ffmpeg ebur128） ----------
rc, txt = run([ffmpeg, "-hide_banner", "-nostats", "-i", str(film),
               "-af", "ebur128=peak=true", "-f", "null", "-"])
out["ebur128_rc"] = rc
tail = txt.strip().splitlines()[-25:]
joined = "\n".join(tail)
m_i = re.search(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+)\s*LUFS", joined) or \
    re.search(r"I:\s*(-?[\d.]+)\s*LUFS", joined)
m_tp = re.search(r"True peak:\s*\n\s*Peak:\s*(-?[\d.]+)\s*dBFS", joined) or \
    re.search(r"Peak:\s*(-?[\d.]+)\s*dBFS", joined)
out["measured_lufs"] = float(m_i.group(1)) if m_i else None
out["measured_true_peak_dbtp"] = float(m_tp.group(1)) if m_tp else None
out["ebur128_tail"] = tail
contract = payload.get("audio_loudness", {}).get("contract") or {}
tgt = float(contract.get("target_lufs", -16.0))
tol = float(contract.get("tolerance_lu", 1.0))
tp_max = float(contract.get("max_true_peak_dbtp", -1.5))
out["loudness_contract"] = contract
out["loudness_independent_ok"] = bool(
    out["measured_lufs"] is not None and abs(out["measured_lufs"] - tgt) <= tol
    and out["measured_true_peak_dbtp"] is not None and out["measured_true_peak_dbtp"] <= tp_max)
out["pipeline_recorded_loudness"] = {
    k: (payload.get("audio_loudness") or {}).get(k)
    for k in ("ok", "measured_lufs", "measured_true_peak_dbtp", "delta_lu")}

# ---------- 逐镜头抽帧反查 ----------
tmp = pathlib.Path(tempfile.mkdtemp(prefix="phase5c_frames_"))
timeline = payload.get("material_timeline") or []
asset_paths = {}
for s in timeline:
    sa = s.get("selected_asset") or {}
    if sa.get("asset_id"):
        asset_paths[sa["asset_id"]] = sa.get("path")
scene_rows = []
for s in timeline:
    sid = s.get("scene_id")
    st, en = float(s.get("start_s") or 0.0), float(s.get("end_s") or 0.0)
    mid = st + max(0.0, (en - st) / 2.0)
    fp = tmp / (str(sid) + ".png")
    rc, _ = run([ffmpeg, "-y", "-v", "error", "-ss", "{:.3f}".format(mid), "-i", str(film),
                 "-frames:v", "1", str(fp)])
    row = {"scene_id": sid, "mid_s": mid, "extract_rc": rc, "frame": str(fp)}
    if fp.exists():
        g = gray48(fp)
        sa = s.get("selected_asset") or {}
        scores = {}
        for aid, ap in asset_paths.items():
            if ap and pathlib.Path(ap).exists():
                scores[aid] = round(frame_corr(g, gray48(ap)), 6)
        row["scores"] = scores
        row["selected_asset_id"] = sa.get("asset_id")
        row["selected_asset_name"] = sa.get("name")
        row["want_corr"] = scores.get(sa.get("asset_id"))
        row["argmax_asset_id"] = max(scores, key=scores.get) if scores else None
        best = max(scores.values()) if scores else 0.0
        row["best_corr"] = best
        row["argmax_matches_selected"] = (row["argmax_asset_id"] == sa.get("asset_id"))
        row["corr_ok"] = bool(row["want_corr"] is not None and row["want_corr"] >= 0.30
                              and row["want_corr"] >= best - 0.15)
    scene_rows.append(row)
out["frames_dir"] = str(tmp)
out["scenes"] = scene_rows
out["all_scenes_corr_ok"] = all(r.get("corr_ok") for r in scene_rows)

# S06 专项：side vs front 对比
s06 = next((r for r in scene_rows if r["scene_id"] == "S06"), None)
if s06:
    sc = s06.get("scores") or {}
    out["s06_side_vs_front"] = {
        "side_asset": "asset_f3cf2b80432d", "side_corr": sc.get("asset_f3cf2b80432d"),
        "front_asset": "asset_edece2b357f1", "front_corr": sc.get("asset_edece2b357f1"),
        "visitor_asset": "asset_4f49f4c7edd0", "visitor_corr": sc.get("asset_4f49f4c7edd0")}
    out["s06_replacement_confirmed_in_pixels"] = bool(
        sc.get("asset_f3cf2b80432d") is not None and sc.get("asset_edece2b357f1") is not None
        and sc["asset_f3cf2b80432d"] > sc["asset_edece2b357f1"])

(LOGS / "phase5c_film_verify.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
print("film:", film.name, out["film_bytes"], "bytes, sha256", out["film_sha256"][:16])
print("format:", out["format"])
print("video:", v.get("codec"), v.get("width"), "x", v.get("height"), v.get("nb_frames"),
      "audio:", a.get("codec"), a.get("sample_rate"), a.get("channels"))
print("duration:", out["duration_s"], "payload", out["payload_video_duration_s"],
      "match", out["duration_matches_payload"])
print("loudness independent: I=", out["measured_lufs"], "LUFS TP=", out["measured_true_peak_dbtp"],
      "dBTP ok=", out["loudness_independent_ok"])
print("pipeline loudness:", out["pipeline_recorded_loudness"])
for r in scene_rows:
    print("  ", r["scene_id"], "mid", round(r["mid_s"], 2), "sel", r.get("selected_asset_id"),
          "want", r.get("want_corr"), "best", r.get("best_corr"), "corr_ok", r.get("corr_ok"),
          "argmax", r.get("argmax_asset_id"))
print("S06 side/front:", out.get("s06_side_vs_front"),
      "confirmed:", out.get("s06_replacement_confirmed_in_pixels"))
print("written", LOGS / "phase5c_film_verify.json")
