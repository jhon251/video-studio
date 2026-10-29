"""5.x Phase 5-A 证据收集：多模态语义验证（**只读、离线、确定性**）。

产出（docs/regression_2x/logs/）：
  phase5a_multimodal_evidence.json   —— 两版成片的逐镜头证据（CLIP 相似度 + 三态 + 依据 +
                                         模型/版本/输入指纹）+ 与 4-B 结论的**并列对照**（不覆盖）+
                                         确定性证明 + 只读证明 + fail-closed 证明
  phase5a_evidence_summary.txt       —— 人类可读摘要

用法：python docs/regression_2x/phase5a_evidence.py
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.ops.multimodal import multimodal_report  # noqa: E402
from video_studio.ops.metrics import semantic_report  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
DB = ROOT / "projects" / "video_studio.db"
PID = "p_f4b466a4a024"
FROZEN = "a_2ed5f41d6b58"          # 4-B 真值钉定的冻结 3-A 成片（S04/S06 = 鲨鱼照）
CURRENT = "a_e369526c2f47"         # 4-C 修复后的当前成片（v5）
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8"))
LINES = []


def say(s):
    print(s, flush=True)
    LINES.append(str(s))


def sha(p: Path):
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()
    except OSError:
        return None


def state():
    con = sqlite3.connect(str(DB))
    counts = {t: con.execute("select count(*) from {}".format(t)).fetchone()[0]
              for t in ("tasks", "artifacts", "events", "decisions", "changelog")}
    con.close()
    proj = DB.parent / PID
    files = {str(p.relative_to(proj)): sha(p) for p in sorted(proj.rglob("*")) if p.is_file()}
    return {"db": sha(DB), "counts": counts, "files": files}


def norm(rep):
    r = json.loads(json.dumps(rep))
    for s in r.get("scenes") or []:
        for f in s.get("frames") or []:
            f.pop("path", None)
    (r.get("meta") or {}).pop("frames_dir", None)
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


say("=== 5.x Phase 5-A：多模态语义验证证据（真实 CLIP，只读）===")
say("模型目录：{}".format(CFG.get("tools", {}).get("multimodal", {}).get("model_dir")
                          or "models/clip/.../3d74acf9a28c67741b2f4f2ea7635f0aaf6f0268"))
before = state()
runs = {}
for tag, art in (("frozen_v3_" + FROZEN, FROZEN), ("current_v5_" + CURRENT, CURRENT)):
    rep = multimodal_report(DB, PID, artifact_id=art, config=CFG)
    runs[tag] = rep
    say("\n[{}] 成片 {} | 抽帧 {} | 模型 {} | torch {}".format(
        tag, Path(rep.get("film") or "").name,
        (rep.get("meta") or {}).get("frames_extracted"),
        (rep.get("model") or {}).get("snapshot"), (rep.get("versions") or {}).get("torch")))
    say("  权重 sha256 {} | config sha256 {}".format(
        str((rep.get("model") or {}).get("weights_sha256"))[:16],
        str((rep.get("model") or {}).get("config_sha256"))[:16]))
    say("  计数：{}".format(json.dumps(rep.get("counts"), ensure_ascii=False)))
    for s in rep.get("scenes") or []:
        say("   {:4s} {:<9s} 期望域={:<14s} 期望相似度={:<9} 最强其它域={}({:<9}) Δ={:<10} 置信={} 来源={}".format(
            s.get("scene_id"), s.get("verdict"), str(s.get("expected_domain")),
            str(s.get("expected_sim")), str(s.get("best_other_domain")),
            str(s.get("best_other_sim")), str(s.get("delta")), s.get("confidence"),
            s.get("expected_domain_source")))
        say("        画面最像: {}".format(", ".join(
            "{}({})".format(x["domain"], x["sim"]) for x in (s.get("top_k") or []))))

say("\n[4-B 对照（既有证据层，未被覆盖/删除；4-B 用**同一个钉定产物**读取）]")
sem_by_tag = {"frozen_v3_" + FROZEN: semantic_report(DB, PID, artifact_id=FROZEN),
              "current_v5_" + CURRENT: semantic_report(DB, PID, artifact_id=CURRENT)}
for tag, rep in runs.items():
    sem = sem_by_tag[tag]
    sem_by = {s["scene_id"]: s for s in sem.get("scenes") or []}
    say("  {}：4-B {}（artifact={}）".format(
        tag.split("_")[0], json.dumps(sem.get("counts"), ensure_ascii=False),
        FROZEN if tag.startswith("frozen") else CURRENT))
    for s in rep.get("scenes") or []:
        b = sem_by.get(s["scene_id"]) or {}
        say("    {:4s} 4-B={:<9s}({:<22s}) | 多模态={:<9s}({})".format(
            s["scene_id"], b.get("verdict"), str(b.get("rule"))[:22], s["verdict"],
            str(s.get("code") or "-")))

say("\n[确定性与只读]")
dup = multimodal_report(DB, PID, artifact_id=FROZEN, config=CFG)
say("  同一冻结产物两次运行逐字节一致：{}".format(norm(runs["frozen_v3_" + FROZEN]) == norm(dup)))
after = state()
say("  DB 字节未变：{} | 五张表行数未变：{} | 项目 {} 个文件（含成片）未变：{}".format(
    before["db"] == after["db"], before["counts"] == after["counts"], len(after["files"]),
    before["files"] == after["files"]))
say("  只读策略：{}".format(json.dumps(
    (runs["current_v5_" + CURRENT].get("policy") or {}), ensure_ascii=False)[:260]))

say("\n[fail-closed 复核]")
bad = multimodal_report(DB, PID, config={**CFG, "tools": {
    **CFG["tools"], "multimodal": {"model_dir": "models/clip/NO_SUCH"}}})
say("  模型不可用 → error={} | 全部镜头 UNKNOWN={}".format(
    json.dumps(bad.get("error"), ensure_ascii=False),
    all(s["verdict"] == "UNKNOWN" for s in bad.get("scenes") or [])))
say("  计数（不伪造）: {}".format(json.dumps(bad.get("counts"), ensure_ascii=False)))

out = {
    "phase": "5-A",
    "model": {k: (runs["current_v5_" + CURRENT].get("model") or {}).get(k)
              for k in ("snapshot", "architecture", "config_sha256", "weights_sha256", "dir")},
    "versions": runs["current_v5_" + CURRENT].get("versions"),
    "labels": (runs["current_v5_" + CURRENT].get("meta") or {}).get("labels"),
    "runs": {tag: {"film": rep.get("film"), "counts": rep.get("counts"),
                   "sources": rep.get("sources"), "policy": rep.get("policy"),
                   "frames": (rep.get("meta") or {}).get("frames_extracted"),
                   "frame_plan": (rep.get("meta") or {}).get("frame_plan"),
                   "scenes": [{k: v for k, v in s.items() if k != "frames"} |
                              {"frames": [{kk: vv for kk, vv in f.items() if kk != "path"}
                                          for f in s.get("frames") or []]}
                              for s in rep.get("scenes") or []]}
             for tag, rep in runs.items()},
    "four_b_reference": {"truth_artifact": FROZEN,
                         "by_artifact": {tag: {"counts": sem_by_tag[tag].get("counts"),
                                               "scenes": [{k: s.get(k)
                                                           for k in ("scene_id", "verdict", "rule")}
                                                          for s in sem_by_tag[tag].get("scenes") or []]}
                                         for tag in sem_by_tag}},
    "determinism": {"two_runs_identical": norm(runs["frozen_v3_" + FROZEN]) == norm(dup)},
    "readonly": {"db_unchanged": before["db"] == after["db"],
                 "counts_unchanged": before["counts"] == after["counts"],
                 "project_files_unchanged": before["files"] == after["files"],
                 "project_files": len(after["files"])},
    "fail_closed": {"model_missing_error": bad.get("error"), "counts": bad.get("counts")},
    "note": ("多模态结果是**新增证据层**：4-B 结果原样保留、不覆盖不删除；本层只读（不写库/不写产物/"
             "不改选材·时间轴·旁白·BGM/不触发 redo）；模型/版本/输入指纹全部记录，可复算。"),
}
(LOGS / "phase5a_multimodal_evidence.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
(LOGS / "phase5a_evidence_summary.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase5a_multimodal_evidence.json")
