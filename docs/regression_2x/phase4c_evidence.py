"""4.x Phase 4-C 验收证据采集（只读）：替换前后关系 / 人工选择 / redo·changelog·approval /
attribution↔timeline 1:1 / 新成片 ffprobe·响度·抽帧 / 语义复核 / 3-A 链路。

产出：docs/regression_2x/logs/phase4c_*.{json,txt}
用法：python docs/regression_2x/phase4c_evidence.py [pid]
"""
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.audio import verify_file as verify_loudness  # noqa: E402
from video_studio.ops.metrics import project_metrics  # noqa: E402
from video_studio.ops.metrics import semantic_report  # noqa: E402
from video_studio.ops.selection_review import review_queue  # noqa: E402

PID = sys.argv[1] if len(sys.argv) > 1 else "p_f4b466a4a024"
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
FFPROBE = ROOT / "bin" / "ffprobe.exe"
REPLACED = ("S04", "S05", "S06")   # 4-C 两次人工替换涉及镜头（S04/S06 首轮，S05 收尾修复）


def ro():
    con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    return con


lines: list[str] = []


def log(s: str) -> None:
    lines.append(s)
    print(s, flush=True)


log("=== 4-C 人审候选替换：验收证据（只读）===")
con = ro()

# ---- 1. 替换前后的素材/版本关系 ----
tasks = [dict(r) for r in con.execute(
    "select task_id, task_type, status, version, created_at from tasks where project_id=? and "
    "task_type='render' order by version", (PID,))]
log("\n[1] 渲染版本链（append-only：旧版本全部保留）")
for t in tasks:
    a = con.execute("select count(*) c from artifacts where task_id=?", (t["task_id"],)).fetchone()
    log("    v{} {} {} status={} artifacts={}".format(
        t["version"], t["task_id"], "(旧)" if t["version"] < max(x["version"] for x in tasks)
        else "(当前)", t["status"], a["c"]))

render = con.execute("select artifact_id, task_id, path from artifacts where project_id=? and "
                     "type='render_output' order by created_at desc limit 1", (PID,)).fetchone()
att = con.execute("select artifact_id, path from artifacts where project_id=? and "
                  "type='attribution' order by created_at desc limit 1", (PID,)).fetchone()
old = con.execute("select artifact_id, path, task_id from artifacts where project_id=? and "
                  "type='render_output' and task_id=? order by created_at desc limit 1",
                  (PID, "t_b7a62ec8e29a")).fetchone()
con.close()
d_new = json.loads(Path(render["path"]).read_text(encoding="utf-8"))
d_old = json.loads(Path(old["path"]).read_text(encoding="utf-8")) if old else {}
log("    旧成片产物 {}（任务 {}）→ 新成片产物 {}（任务 {}）".format(
    old["artifact_id"] if old else "-", old["task_id"] if old else "-",
    render["artifact_id"], render["task_id"]))
relations = []
for sid in REPLACED:
    s_old = next((s for s in (d_old.get("material_timeline") or []) if s["scene_id"] == sid), {})
    s_new = next((s for s in d_new["material_timeline"] if s["scene_id"] == sid), {})
    a_old, a_new = s_old.get("selected_asset") or {}, s_new.get("selected_asset") or {}
    relations.append({"scene_id": sid,
                      "before": {"asset_id": a_old.get("asset_id"), "name": a_old.get("name"),
                                 "sha256_prefix": (a_old.get("sha256") or "")[:12]},
                      "after": {"asset_id": a_new.get("asset_id"), "name": a_new.get("name"),
                                "sha256_prefix": (a_new.get("sha256") or "")[:12],
                                "license": a_new.get("license"),
                                "license_class": a_new.get("license_class")},
                      "selection_source": s_new.get("selection_source"),
                      "human_selection": s_new.get("human_selection"),
                      "fallback_state": s_new.get("fallback_state"),
                      "insufficiency_class": s_new.get("insufficiency_class")})
    log("    {}  {} → {}".format(sid, a_old.get("name"), a_new.get("name")))
    log("        来源={} 人工={}".format(s_new.get("selection_source"),
                                         (s_new.get("human_selection") or {}).get("decided_by")))
(LOGS / "phase4c_replacement_relations.json").write_text(
    json.dumps({"project": PID, "old_render_task": old["task_id"] if old else None,
                "new_render_task": render["task_id"], "relations": relations},
               ensure_ascii=False, indent=1), encoding="utf-8")

# ---- 2/3. 人工选择 + redo/changelog/approval 证据 ----
con = ro()
dec = [dict(r) for r in con.execute(
    "select decision_id, node, made_by, state, rationale, artifact_snapshot, created_at "
    "from decisions where project_id=? and node='selection_override' order by created_at", (PID,))]
chg = [dict(r) for r in con.execute(
    "select change_id, target_type, target_id, changed_by, reason, before_summary, after_summary, "
    "human_confirmed, created_at from changelog where project_id=? and "
    "target_type='selection_override' order by change_id", (PID,))]
con.close()
log("\n[2] 人工选择证据（decisions 表，node=selection_override）")
for d in dec:
    snap = d["artifact_snapshot"]
    snap = json.loads(snap) if isinstance(snap, str) else snap
    log("    {} by={} state={} | {} → {} | reason={}".format(
        d["decision_id"], d["made_by"], d["state"], snap.get("before_asset_name"),
        snap.get("after_asset_name"), str(d["rationale"])[:70]))
log("\n[3] changelog（human_confirmed=1，append-only）")
for c in chg:
    log("    #{} {} {} by={} human_confirmed={}".format(
        c["change_id"], c["target_type"], c["target_id"], c["changed_by"], c["human_confirmed"]))
(LOGS / "phase4c_human_decision_evidence.json").write_text(
    json.dumps({"decisions": dec, "changelog": chg}, ensure_ascii=False, indent=1, default=str),
    encoding="utf-8")

# ---- 4. attribution ↔ timeline 1:1 ----
attp = json.loads(Path(att["path"]).read_text(encoding="utf-8"))
with_asset = [s for s in d_new["material_timeline"] if s.get("selected_asset")]
ok11 = len(attp["entries"]) == len(with_asset) and all(
    e["scene_id"] == s["scene_id"]
    and e["selected_asset"]["asset_id"] == s["selected_asset"]["asset_id"]
    and e["selected_asset"]["sha256"] == s["selected_asset"]["sha256"]
    for e, s in zip(attp["entries"], with_asset))
att_s04 = next((e for e in attp["entries"] if e["scene_id"] == "S04"), {})
log("\n[4] attribution ⟷ 新时间轴 1:1：{}（台账 {} 条 / 有素材镜头 {} 个）".format(
    "PASS" if ok11 else "FAIL", len(attp["entries"]), len(with_asset)))
log("    S04 台账：provider={} source_id={} license={} sha256={}…".format(
    att_s04.get("provider"), att_s04.get("source_id"), att_s04.get("license"),
    (att_s04.get("selected_asset") or {}).get("sha256", "")[:12]))
log("    credits_file={} | 受限/未知={}".format(attp.get("credits_file"),
                                               attp.get("restricted_or_unknown_in_film")))

# ---- 5. 新成片：ffprobe / 响度 / 抽帧 ----
film = Path(d_new["output"])
pr = subprocess.run([str(FFPROBE), "-v", "error", "-show_entries",
                     "stream=codec_type,codec_name,width,height,sample_rate,channels:format=duration",
                     "-of", "json", str(film)], capture_output=True, text=True, encoding="utf-8",
                    errors="replace")
probe = json.loads(pr.stdout or "{}")
loud = verify_loudness(film, exe=str(ROOT / "bin" / "ffmpeg.exe"))
frames = {s["scene_id"]: (s.get("appears_in_film"), (s.get("film_evidence") or {}).get("corr_expected"))
          for s in d_new["material_timeline"]}
mv = d_new.get("material_verification") or {}
log("\n[5] 新成片 {} | ffprobe streams={} duration={}s".format(
    film.name, [(s.get("codec_type"), s.get("codec_name")) for s in probe.get("streams", [])],
    (probe.get("format") or {}).get("duration")))
log("    响度：ok={} I={} LUFS TP={} dBTP Δ={} LU（契约 {}±{}）".format(
    loud["ok"], loud["measured_lufs"], loud["measured_true_peak_dbtp"], loud["delta_lu"],
    loud["target_lufs"], loud["tolerance_lu"]))
log("    抽帧：方法={} 检查 {} 镜 / 失败 {} 镜 | S04={} S06={}".format(
    mv.get("method"), len(mv.get("checked_scenes") or []), len(mv.get("failed_scenes") or []),
    frames.get("S04"), frames.get("S06")))
log("    时长契约：video_ok={} timeline={}s video={}s".format(
    d_new.get("video_duration_ok"), (d_new.get("duration_contract") or {}).get("timeline_duration_s"),
    d_new.get("video_duration_s")))
(LOGS / "phase4c_new_film_evidence.json").write_text(json.dumps(
    {"film": str(film), "probe": probe, "loudness": loud,
     "material_verification": {"method": mv.get("method"),
                               "checked": mv.get("checked_scenes"),
                               "failed": mv.get("failed_scenes")},
     "appears_in_film": {k: v for k, v in frames.items()},
     "duration_contract": d_new.get("duration_contract")}, ensure_ascii=False, indent=1),
    encoding="utf-8")

# ---- 6. 语义复核（替换后应转为 MATCH）----
sem = semantic_report(DB, PID)
log("\n[6] 语义复核（4-B 验证器，对**新成片**）：{}".format(sem["counts"]))
for s in sem["scenes"]:
    log("    {:<4s} {:<9s} {:<22s} {}".format(s["scene_id"], s["verdict"], s["rule"] or "-",
                                              str((s.get("asset") or {}).get("name"))[:60]))
(LOGS / "phase4c_semantic_after.json").write_text(json.dumps(sem, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")

# ---- 7. 指标与复核队列 ----
m = project_metrics(DB, PID)
q = review_queue(DB, PID)
log("\n[7] metrics：语义={} 上屏={} 响度ok={} | 复核队列待办 {} 个 / 必须 BLOCKED {} 个".format(
    (m.get("semantics") or {}).get("counts"), m["on_screen"], m["contracts"].get("loudness_ok"),
    q.get("item_count"), q.get("blocked_scenes")))

# ---- 8. 资产复用连带检查（对比上一版逐镜头分配）----
con = ro()
rows = [dict(r) for r in con.execute(
    "select artifact_id, path, task_id from artifacts where project_id=? and type='render_output' "
    "order by created_at", (PID,))]
con.close()
prev = json.loads(Path(rows[-2]["path"]).read_text(encoding="utf-8")) if len(rows) >= 2 else {}
prev_assign = {s["scene_id"]: ((s.get("selected_asset") or {}).get("asset_id"))
               for s in (prev.get("material_timeline") or [])}
new_assign = {s["scene_id"]: ((s.get("selected_asset") or {}).get("asset_id"))
              for s in d_new["material_timeline"]}
reuse = {}
for sid, aid in sorted(new_assign.items()):
    reuse.setdefault(aid, []).append(sid)
log("\n[8] 资产复用连带检查（当前版 {} / 上一版 {}）".format(render["artifact_id"],
                                                             prev.get("output") and rows[-2]["artifact_id"]))
for aid, sids in sorted(reuse.items(), key=lambda kv: -len(kv[1])):
    name = next((str((s.get("selected_asset") or {}).get("name"))[:48]
                 for s in d_new["material_timeline"]
                 if (s.get("selected_asset") or {}).get("asset_id") == aid), "")
    log("    {} 用于 {} 个镜头 {} | {}".format(aid, len(sids), sids, name))
changed = {sid: (prev_assign.get(sid), new_assign.get(sid)) for sid in sorted(new_assign)
           if prev_assign.get(sid) != new_assign.get(sid)}
log("    与上一版相比发生变化的镜头：{}".format(changed or "无"))
log("    未被任何镜头使用（已释放）素材：{}".format(
    sorted(set(prev_assign.values()) - set(new_assign.values())) or "无"))
(LOGS / "phase4c_reuse_check.json").write_text(json.dumps(
    {"current_artifact": render["artifact_id"], "previous_artifact": rows[-2]["artifact_id"],
     "reuse": {k: v for k, v in reuse.items()}, "changed_scenes": changed,
     "freed_assets": sorted(set(prev_assign.values()) - set(new_assign.values()))},
    ensure_ascii=False, indent=1), encoding="utf-8")

(LOGS / "phase4c_evidence_summary.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase4c_evidence_summary.txt")
