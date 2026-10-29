"""4.x Phase 4-G 证据收集：只读节奏分析（**离线、确定性、只读**）。

产出（docs/regression_2x/logs/）：
  phase4g_rhythm_evidence.json   —— 场景矩阵（正常/过短/过长/边界/BGM 关·开/空旁白/无法判断）、
                                   真实项目只读报告、只读证明（DB 与文件哈希、行数、写入拒绝）、
                                   确定性证明（两次运行逐字节一致）
  phase4g_evidence_summary.txt   —— 人类可读摘要

用法：python docs/regression_2x/phase4g_evidence.py
"""
import hashlib
import json
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.rhythm import analyze_rhythm, rhythm_settings  # noqa: E402
from video_studio.ops.rhythm import rhythm_report  # noqa: E402
from video_studio.ops.report import readonly_connection  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
REAL_DB = ROOT / "projects" / "video_studio.db"
REAL_PID = "p_f4b466a4a024"
LINES = []


def say(s):
    print(s, flush=True)
    LINES.append(str(s))


def sha(p: Path):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def scenes(*durs):
    out, t = [], 0.0
    for i, d in enumerate(durs):
        out.append({"scene_id": "S{:02d}".format(i + 1), "start_s": t, "end_s": t + d,
                    "segment_index": i, "selection_source": "automatic",
                    "selected_asset": {"asset_id": "a{}".format(i),
                                       "name": "img{}.jpg".format(i), "ext": ".jpg"}})
        t += d
    return out


def narr(*durs):
    return {"segments": [{"index": i, "status": "SUCCESS", "duration_s": d}
                         for i, d in enumerate(durs)],
            "total_s": round(sum(durs), 3), "complete": True}


def run_case(name, tl, nr, *, film=None, bgm=None):
    rep = analyze_rhythm({"timeline": tl, "narration": nr,
                          "film_duration_s": (film if film is not None
                                              else (tl[-1]["end_s"] if tl else None)),
                          "bgm": bgm or {}, "sources": {}})
    say("  {:<22s} 建议 {} / 无法判断 {} | {}".format(
        name, rep["summary"]["suggestions"], rep["summary"]["unknowns"],
        json.dumps(rep["summary"]["suggestions_by_rule"], ensure_ascii=False)))
    return {"case": name, "summary": rep["summary"],
            "suggestions": [{"scene_id": s["scene_id"], "rule": s["rule"],
                             "current_duration_s": s["current_duration_s"],
                             "threshold_s": s["threshold_s"], "confidence": s["confidence"],
                             "evidence": s["evidence"], "action": s["action"], "risk": s["risk"],
                             "status": s["status"], "applied": s["applied"]}
                            for s in rep["suggestions"]],
            "unknowns": [{"scene_id": u["scene_id"], "rule": u["rule"], "reason": u["reason"]}
                         for u in rep["unknowns"]],
            "applied_changes": rep["applied_changes"]}


say("=== 4.x Phase 4-G 只读节奏分析：证据 ===")
say("默认阈值：{}（来源 {}）".format(json.dumps(
    {k: v for k, v in rhythm_settings({}).items() if not k.startswith("_")}, ensure_ascii=False),
    rhythm_settings({})["_source"]))

say("\n[1] 场景矩阵（合成输入，纯函数）")
cases = [
    run_case("A 正常节奏", scenes(8, 10, 12, 9, 11, 13), narr(8, 10, 12, 9, 11, 13)),
    run_case("B 过短镜头", scenes(12, 1.5, 18, 14), narr(10, 1.4, 17, 13)),
    run_case("C 过长镜头", scenes(12, 30, 18), narr(11, 28, 17)),
    run_case("D 边界异常", scenes(12, 12), narr(16, 8)),
    run_case("E BGM 关闭", scenes(12, 12), narr(11, 11), bgm={"enabled": False}),
    run_case("F BGM 开启", scenes(12, 12), narr(11, 11),
             bgm={"enabled": True, "applied": True, "bed_db": -20.0, "duck_db": -26.0,
                  "intervals": [{"start_s": 0.0, "end_s": 3.0}, {"start_s": 4.0, "end_s": 6.0},
                                {"start_s": 7.0, "end_s": 9.0}]}),
    run_case("G 空旁白", scenes(12, 12), None),
    run_case("H 无法判断", [{"scene_id": "S01", "start_s": 0.0, "end_s": 25.0, "segment_index": 0,
                             "selected_asset": {"name": "no_ext_material"}}], narr(20), film=25),
]

say("\n[2] 真实项目只读报告（{}）".format(REAL_PID))
con = sqlite3.connect(str(REAL_DB))


def db_counts():
    return {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
            for t in ("tasks", "artifacts", "events", "decisions", "changelog")}


def file_state():
    proj = REAL_DB.parent / REAL_PID
    return {str(p.relative_to(proj)): sha(p) for p in sorted(proj.rglob("*")) if p.is_file()}


before = {"db": sha(REAL_DB), "counts": db_counts(), "files": file_state()}
r1 = rhythm_report(REAL_DB, REAL_PID)
r2 = rhythm_report(REAL_DB, REAL_PID)
cli = subprocess.run([sys.executable, "run.py", "rhythm", REAL_PID, "--json"], cwd=str(ROOT),
                     capture_output=True)
after = {"db": sha(REAL_DB), "counts": db_counts(), "files": file_state()}
con.close()

say("  成片 {}s | 镜头 {} | 切换 {} 次（{}/min）| 旁白 {}s（{} 段）".format(
    r1["summary"]["film_duration_s"], r1["summary"]["scene_count"], r1["summary"]["cuts"],
    r1["summary"]["cuts_per_min"], r1["summary"]["narration_total_s"],
    r1["summary"]["narration_segments"]))
say("  建议 {} 条 / 无法判断 {} 条 | {}".format(
    r1["summary"]["suggestions"], r1["summary"]["unknowns"],
    json.dumps(r1["summary"]["suggestions_by_rule"], ensure_ascii=False)))
for s in r1["suggestions"]:
    say("    · [建议·未执行] {} {} 当前 {}s 阈值 {} 置信 {} | 依据 {}".format(
        s["scene_id"], s["rule"], s["current_duration_s"], s["threshold_s"], s["confidence"],
        json.dumps(s["evidence"], ensure_ascii=False)[:120]))
say("  BGM：{}".format(json.dumps(r1["summary"]["bgm"], ensure_ascii=False)))

say("\n[3] 只读证明")
say("  DB sha256 前后一致：{}（{}…）".format(before["db"] == after["db"], (before["db"] or "")[:16]))
say("  行数前后一致：{} | {}".format(before["counts"] == after["counts"], after["counts"]))
say("  项目文件 {} 个，前后逐字节一致：{}".format(len(before["files"]),
                                                before["files"] == after["files"]))
ro = readonly_connection(REAL_DB)
try:
    ro.execute("insert into events(ts,project_id,type,actor,payload,human_visible) "
               "values(0,'x','X','x','{}',0)")
    rejected = False
except sqlite3.OperationalError:
    rejected = True
finally:
    ro.close()
say("  只读连接拒绝写入（INSERT 抛 OperationalError）：{}".format(rejected))

say("\n[4] 确定性与『未执行』声明")
det = (json.dumps(r1, ensure_ascii=False, sort_keys=True)
       == json.dumps(r2, ensure_ascii=False, sort_keys=True))
say("  两次 API 运行逐字节一致：{} | CLI rc={} 且输出非空：{}".format(
    det, cli.returncode, bool(cli.stdout)))
say("  applied_changes={} | 全部建议 applied=executed=False：{}".format(
    r1["applied_changes"], all(not s["applied"] and not s["executed"]
                               for s in r1["suggestions"])))
say("  策略：{}".format(json.dumps(r1["policy"], ensure_ascii=False)[:220]))

out = {
    "phase": "4-G",
    "settings_default": {k: v for k, v in rhythm_settings({}).items() if not k.startswith("_")},
    "scenario_matrix": cases,
    "real_project": {
        "project_id": REAL_PID,
        "summary": r1["summary"],
        "policy": r1["policy"],
        "applied_changes": r1["applied_changes"],
        "input_fingerprints": r1["input_fingerprints"],
        "suggestions": r1["suggestions"], "unknowns": r1["unknowns"],
        "scenes": r1["scenes"],
    },
    "readonly_proof": {
        "db_sha256_before": before["db"], "db_sha256_after": after["db"],
        "db_unchanged": before["db"] == after["db"],
        "counts_before": before["counts"], "counts_after": after["counts"],
        "counts_unchanged": before["counts"] == after["counts"],
        "project_files_before": len(before["files"]),
        "files_unchanged": before["files"] == after["files"],
        "readonly_connection_rejects_insert": rejected,
        "cli_rc": cli.returncode,
    },
    "determinism": {"two_api_runs_identical": det,
                    "cli_stdout_nonempty": bool(cli.stdout)},
    "note": ("只读建议器：不写库/不写产物/不改时间轴·时长·旁白·素材·BGM/不触发 redo；"
             "所有建议 status=SUGGESTION、applied=false、executed=false；applied_changes=0。"),
}
(LOGS / "phase4g_rhythm_evidence.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
(LOGS / "phase4g_evidence_summary.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase4g_rhythm_evidence.json")
