"""3-B 真实链路响度取证：读最新 render 产物 → 实测成片 + 打印 audio_loudness 证据块。"""
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core.audio import verify_file  # noqa: E402

FFMPEG = str(ROOT / "bin" / "ffmpeg.exe")
PID = sys.argv[1] if len(sys.argv) > 1 else "p_f4b466a4a024"
con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row
rows = [dict(r) for r in con.execute(
    "select artifact_id, path, created_at, task_id from artifacts where project_id=? "
    "and type='render_output' order by created_at", (PID,))]
con.close()
d = json.loads(Path(rows[-1]["path"]).read_text(encoding="utf-8"))
al = d.get("audio_loudness") or {}
print("project      :", PID, "| render task:", rows[-1]["task_id"], "| artifacts:", len(rows))
print("film         :", Path(d["output"]).name, "| duration:", d.get("video_duration_s"), "s")
print("audio_chain  :", al.get("audio_chain"))
print("mastering    :", al.get("mastering_applied"), "| corrections:", al.get("corrections"))
print("证据块       : ok={} I={} LUFS TP={} dBTP Δ={} LU contract={}".format(
    al.get("ok"), al.get("measured_lufs"), al.get("measured_true_peak_dbtp"), al.get("delta_lu"),
    al.get("contract")))
ev = verify_file(d["output"], exe=FFMPEG)
print("独立复测     : ok={} I={} LUFS TP={} dBTP Δ={} LU".format(
    ev["ok"], ev["measured_lufs"], ev["measured_true_peak_dbtp"], ev["delta_lu"]))
import subprocess
pr = subprocess.run([str(ROOT / "bin" / "ffprobe.exe"), "-v", "error", "-select_streams", "a:0",
                     "-show_entries", "stream=sample_rate,channels,codec_name", "-of", "json",
                     d["output"]], capture_output=True, text=True, encoding="utf-8",
                    errors="replace")
print("音轨属性     :", (json.loads(pr.stdout or "{}").get("streams") or [{}])[0])
