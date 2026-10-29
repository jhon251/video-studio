"""3.x Phase 2-A/B 证据汇总器：从数据库/产物/成片抽取报告所需的确切数字。

输出 docs/regression_2x/logs/phase2_evidence.md（UTF-8），供 PHASE2_REPORT.md 引用。

用法：python docs/regression_2x/phase2_evidence.py [project_id]
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
FFPROBE = ROOT / "bin" / "ffprobe.exe"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
PID = sys.argv[1] if len(sys.argv) > 1 else "p_ab2b352e06b8"
OUT = LOGS / "phase2_evidence.md"
L = []

con = sqlite3.connect(str(ROOT / "projects" / "video_studio.db"))
con.row_factory = sqlite3.Row


def probe(p):
    r = subprocess.run([str(FFPROBE), "-v", "error", "-print_format", "json", "-show_format",
                        "-show_streams", str(p)], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return json.loads(r.stdout or "{}")


L.append("# Phase 2-A/B 证据汇总（自动生成）")
L.append("")
L.append("项目: `{}`".format(PID))
L.append("")

L.append("## 1. 项目与任务")
row = con.execute("select * from projects where project_id=?", (PID,)).fetchone()
L.append("goal: {}".format(row["goal"]))
rows = list(con.execute("select task_id, task_type, version, status, retry_count, cost_usd, "
                        "started_at, finished_at, error from tasks where project_id=? "
                        "order by task_type, version", (PID,)))
L.append("任务记录数: {}（含历史版本）".format(len(rows)))
succ = [r for r in rows if r["status"] == "SUCCEEDED"]
blocked = [r for r in rows if r["status"] in ("BLOCKED", "FAILED")]
L.append("SUCCEEDED: {} ｜ BLOCKED/FAILED: {}（均为历史版本，已被 redo 后新版本取代）".format(
    len(succ), len(blocked)))
L.append("")
L.append("| task_id | type | v | status | attempts | cost_usd | 用时s | error |")
L.append("|---|---|---|---|---|---|---|---|")
for r in rows:
    dur = ""
    if r["started_at"] and r["finished_at"]:
        dur = "{:.1f}".format(float(r["finished_at"]) - float(r["started_at"]))
    err = (r["error"] or "")[:60].replace("|", "/").replace("\n", " ")
    L.append("| {} | {} | {} | {} | {} | {:.6f} | {} | {} |".format(
        r["task_id"], r["task_type"], r["version"], r["status"], r["retry_count"],
        float(r["cost_usd"] or 0), dur, err))

L.append("")
L.append("## 2. 成本台账（本项目）")
tot = sum(float(r["cost_usd"] or 0) for r in rows)
L.append("任务行 cost_usd 合计: ${:.6f}".format(tot))
ev = 0.0
n_ev = 0
for r in con.execute("select payload from events where project_id=? and type='LLM_CALL'", (PID,)):
    n_ev += 1
    try:
        ev += float((json.loads(r["payload"]) or {}).get("cost_usd") or 0)
    except Exception:
        pass
L.append("LLM_CALL 事件 {} 条合计: ${:.6f}".format(n_ev, ev))

L.append("")
L.append("## 3. 素材（local_ingest）")
media = ROOT / "projects" / PID / "media"
for f in sorted(media.glob("*.jpg")):
    import hashlib
    h = hashlib.sha256(f.read_bytes()).hexdigest()
    L.append("- `{}` {} bytes sha256={}".format(f.name, f.stat().st_size, h))

L.append("")
L.append("## 4. 音轨（真实 TTS 结果）")
vdir = media / "voice"
narr = vdir / "narration.mp3"
if narr.exists():
    d = probe(narr)
    L.append("narration.mp3: {} bytes duration={}s".format(
        narr.stat().st_size, (d.get("format") or {}).get("duration")))
segs = sorted(vdir.glob("seg_*.mp3"))
ok = [s for s in segs if s.stat().st_size > 0]
L.append("分段: {} 个，非空 {} 个（空文件即 TTS 失败段）".format(len(segs), len(ok)))
for s in segs:
    dur = ""
    if s.stat().st_size:
        dur = (probe(s).get("format") or {}).get("duration")
    L.append("  - {} {} bytes dur={}".format(s.name, s.stat().st_size, dur))

L.append("")
L.append("## 4b. 旁白完整性 + 时长契约（Phase 2-B.1）")
r = con.execute("select path from artifacts where project_id=? and type='voice_output' "
                "order by created_at desc limit 1", (PID,)).fetchone()
if r:
    d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
    L.append("voice_output: status={} complete={} expected={} successful={} failed={} reused={}".format(
        d.get("status"), d.get("complete"), d.get("expected_segments"),
        d.get("successful_segments"), d.get("failed_segments"), d.get("reused_segments")))
    L.append("duration_contract: " + json.dumps(d.get("duration_contract"), ensure_ascii=False))
    L.append("")
    L.append("| seg | status | reused | attempts | bytes | duration_s | error codes |")
    L.append("|---|---|---|---|---|---|---|")
    for s in d.get("segment_details") or []:
        L.append("| {:02d} | {} | {} | {} | {} | {} | {} |".format(
            s["index"], s["status"], s["reused"], s["attempts"], s["bytes"], s["duration_s"],
            ",".join(sorted({e.get("code") for e in (s.get("errors") or [])}))))
r = con.execute("select path from artifacts where project_id=? and type='render_output' "
                "order by created_at desc limit 1", (PID,)).fetchone()
if r:
    d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
    L.append("")
    L.append("render_output: narration_state={} video_duration_s={} ok={} (容差 {}s)".format(
        d.get("narration_state"), d.get("video_duration_s"), d.get("video_duration_ok"),
        d.get("video_duration_tolerance_s")))
    L.append("completeness: " + json.dumps(d.get("narration_completeness"), ensure_ascii=False))
    L.append("duration_contract: " + json.dumps(d.get("duration_contract"), ensure_ascii=False))

L.append("")
L.append("## 5. 成片")
vids = sorted((ROOT / "projects" / PID / "output").glob("*.mp4"))
for v in vids:
    info = probe(v)
    fmt = info.get("format") or {}
    L.append("`{}` {} bytes duration={}s".format(v.name, v.stat().st_size, fmt.get("duration")))
    for s in info.get("streams", []):
        L.append("  - #{} {} {} {}x{} fps={} frames={} dur={} sr={} ch={}".format(
            s.get("index"), s.get("codec_type"), s.get("codec_name"), s.get("width"),
            s.get("height"), s.get("avg_frame_rate"), s.get("nb_frames"), s.get("duration"),
            s.get("sample_rate"), s.get("channels")))
    dec = subprocess.run([str(ROOT / "bin" / "ffmpeg.exe"), "-v", "error", "-i", str(v),
                          "-f", "null", "-"], capture_output=True, text=True, encoding="utf-8",
                         errors="replace")
    L.append("  - ffmpeg 解码 rc={}".format(dec.returncode))

L.append("")
L.append("## 6. 素材时间轴（render_output）")
r = con.execute("select path from artifacts where project_id=? and type='render_output' "
                "order by created_at desc limit 1", (PID,)).fetchone()
if r:
    d = json.loads(Path(r["path"]).read_text(encoding="utf-8"))
    tl = d.get("material_timeline") or []
    L.append("visual_source={} assembly={} scene_count={} scenes_with_asset={}".format(
        d.get("visual_source"), d.get("material_assembly"), d.get("scene_count"),
        d.get("scenes_with_asset")))
    L.append("")
    L.append("| scene | window_s | asset | name | sha256[:16] | fallback |")
    L.append("|---|---|---|---|---|---|")
    for s in tl:
        a = s.get("selected_asset") or {}
        L.append("| {} | {}-{} | {} | {} | {} | {} |".format(
            s["scene_id"], s["start_s"], s["end_s"], a.get("asset_id"), a.get("name"),
            str(a.get("sha256"))[:16], s["fallback_state"]))

con.close()
OUT.write_text("\n".join(L) + "\n", encoding="utf-8")
print("written", OUT, len(L), "lines")
