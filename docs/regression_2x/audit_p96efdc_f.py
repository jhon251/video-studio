# -*- coding: utf-8 -*-
"""审计 F：本地素材 ingest 溯源、retrieval v6 候选统计、4-B 语义、成片独立技术复测（只读）。"""
import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")
ROOT = pathlib.Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
PID = "p_96efdc03e1aa"
PDIR = ROOT / "projects" / PID
import sqlite3  # noqa: E402

con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
q = lambda sql, args=(): [dict(r) for r in con.execute(sql, args)]

print("=== 19. 本地素材 ingest 溯源（asset_audit 任务与其产物）===")
for t in q("select task_id, task_type, status, version, inputs, artifacts, created_at from tasks "
           "where project_id=? and task_type in ('asset_audit','retrieval') order by created_at",
           (PID,)):
    print("  {} {} v{} {} | inputs={} | artifacts={}".format(
        t["task_id"], t["task_type"], t["version"], t["status"],
        str(t["inputs"])[:90], json.loads(t["artifacts"] or "[]")))
print("\n  该项目全部产物类型:", {r["type"]: sum(1 for x in q(
    "select type from artifacts where project_id=?", (PID,)) if x["type"] == r["type"])
    for r in q("select distinct type from artifacts where project_id=?", (PID,))})

print("\n=== 20. 本地领域素材的登记记录（sha / 许可 / 尺寸）===")
for aid in ("asset_30dd89a16713", "asset_23e71bc8a864", "asset_3f0b94a3f2ac"):
    hits = q("select artifact_id, type, path from artifacts where project_id=?", (PID,))
    found = []
    for h in hits:
        p = pathlib.Path(h["path"])
        if p.suffix != ".json" or not p.is_file():
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, json.JSONDecodeError):
            continue
        txt = json.dumps(d, ensure_ascii=False)
        if aid in txt:
            found.append(h["type"] + ":" + h["artifact_id"])
    print("  {} 出现在产物: {}".format(aid, sorted(set(found))[:6]))

print("\n=== 21. retrieval v6（t_a32ee7dc5760 / 产物 a_71f77918bc8a）候选统计 ===")
for c in q("select artifact_id, task_id, path, created_at from artifacts where project_id=? and "
           "type='retrieval_candidates' order by created_at", (PID,)):
    d = json.loads(pathlib.Path(c["path"]).read_text(encoding="utf-8"))
    cands = d.get("candidates") or []
    provs = {}
    for cd in cands:
        k = cd.get("provider") or ("local" if cd.get("source") == "local_ingest" else "?")
        provs[k] = provs.get(k, 0) + 1
    local = [cd for cd in cands if cd.get("source") == "local_ingest" or
             (cd.get("provider") in (None, "local_ingest"))]
    print("  {} ({}) mode={} 候选={} | provider 分布={} | 本地={}".format(
        c["artifact_id"], c["task_id"], d.get("material_mode"), len(cands), provs, len(local)))
    if c["artifact_id"] == "a_71f77918bc8a":
        for cd in cands[:22]:
            print("      - {:<50} score={} prov={} sha={}".format(
                str(cd.get("name"))[:50], cd.get("match_score"), cd.get("provider") or "local",
                (cd.get("sha256") or "")[:10]))

print("\n=== 22. 4-B 语义（run.py semantic-check） ===")
p = subprocess.run([sys.executable, "run.py", "semantic-check", PID, "--json"], cwd=str(ROOT),
                   capture_output=True, text=True, encoding="utf-8", errors="replace")
try:
    j = json.loads((p.stdout or "")[p.stdout.index("{"):p.stdout.rindex("}") + 1])
    print("  counts:", j.get("counts"), "| version:", j.get("version"),
          "| lexicon:", str(j.get("lexicon_sha256"))[:16])
    vs = {}
    for s in j.get("scenes") or []:
        vs.setdefault(s.get("verdict"), []).append(s.get("scene_id"))
    for k, v in vs.items():
        print("   {}: {} 镜 {}".format(k, len(v), v[:6]))
except (ValueError, json.JSONDecodeError):
    print("  解析失败:", (p.stdout or p.stderr)[-200:])
con.close()

print("\n=== 23. 成片独立技术复测（最新 render_output） ===")
con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db").as_posix()),
                      uri=True)
con.row_factory = sqlite3.Row
r = con.execute("select artifact_id, path, task_id from artifacts where project_id=? and "
                "type='render_output' order by created_at desc limit 1", (PID,)).fetchone()
con.close()
payload = json.loads(pathlib.Path(r["path"]).read_text(encoding="utf-8"))
film = pathlib.Path(payload["output"])
cfg = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
FF = cfg["tools"]["ffmpeg"]["path"]
FP = cfg["tools"]["ffmpeg"]["ffprobe"]
print("  产物:", r["artifact_id"], "| 任务:", r["task_id"], "| 成片:", film.name,
      film.stat().st_size, "B | sha256:", hashlib.sha256(film.read_bytes()).hexdigest()[:16])
pr = subprocess.run([FP, "-v", "error", "-print_format", "json", "-show_format", "-show_streams",
                     str(film)], capture_output=True, text=True, encoding="utf-8", errors="replace")
probe = json.loads(pr.stdout or "{}")
print("  format:", {k: probe["format"].get(k) for k in ("format_name", "duration", "size")})
for s in probe.get("streams") or []:
    print("   stream {} {:<6} {:<6} {}x{} rate={} frames={}".format(
        s.get("index"), s.get("codec_type"), s.get("codec_name"), s.get("width"), s.get("height"),
        s.get("sample_rate"), s.get("nb_frames")))
rc = subprocess.run([FF, "-hide_banner", "-nostats", "-i", str(film), "-af",
                     "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True,
                    encoding="utf-8", errors="replace")
tail = "\n".join((rc.stderr or "").strip().splitlines()[-20:])
mi = re.search(r"I:\s*(-?[\d.]+)\s*LUFS", tail)
mp = re.search(r"Peak:\s*(-?[\d.]+)\s*dBFS", tail)
print("  独立 ebur128: I={} LUFS | TP={} dBFS".format(mi.group(1) if mi else None,
                                                      mp.group(1) if mp else None))
print("  渲染记录响度:", {k: (payload.get("audio_loudness") or {}).get(k)
                          for k in ("ok", "measured_lufs", "measured_true_peak_dbtp")})
mv = payload.get("material_verification") or {}
print("  渲染自检:", {k: mv.get(k) for k in ("method", "min_corr", "argmax_margin",
                                            "checked_scenes_total", "failed_scenes")})
print("  时长契约: timeline={}s video={}s ok={}".format(
    (payload.get("duration_contract") or {}).get("timeline_duration_s"),
    payload.get("video_duration_s"), payload.get("video_duration_ok")))
