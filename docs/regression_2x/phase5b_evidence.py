"""5.x Phase 5-B 证据收集：多模态候选生成（**只生成候选；只读；不自动替换**）。

产出（docs/regression_2x/logs/）：
  phase5b_candidates_evidence.json   —— 真实 S04/S06 候选（含视觉证据/许可/风险/旁白关联）+
                                        三条路径（有合格候选 / 无合格候选 / 许可不合格）+
                                        与 4-C 历史人工决定的交叉核对 + 只读与确定性证明 + 模型指纹
  phase5b_evidence_summary.txt       —— 人类可读摘要

用法：python docs/regression_2x/phase5b_evidence.py
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core.mm_candidates import (asset_id_of, build_scene_candidates,  # noqa: E402
                                             mmc_settings, pool_from_retrievals)
from video_studio.ops.mm_candidates import mm_review_report  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
DB = ROOT / "projects" / "video_studio.db"
PID = "p_f4b466a4a024"
FROZEN = "a_2ed5f41d6b58"
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
    (r.get("meta") or {}).pop("frames_dir", None)
    for s in r.get("scenes") or []:
        s["human_command"] = (s.get("human_command") or "").replace(PID, "<pid>")
    return json.dumps(r, ensure_ascii=False, sort_keys=True)


say("=== 5.x Phase 5-B：多模态候选生成证据（只读）===")
# 授权里写的基线文件名带一个笔误前缀 "svg"；如实记录并核对真实文件与 SHA256
declared = "svg5.x-phase5a-baseline.zip"
actual = ROOT / "docs" / "regression_2x" / "baseline" / "5.x-phase5a-baseline.zip"
say("基线：授权书写法 {!r}（该文件不存在）→ 实际文件 {} | sha256 {}".format(
    declared, actual.name, sha(actual)))
baseline = {"declared_name": declared, "actual_file": str(actual.name),
            "sha256": sha(actual), "matches_expected":
            sha(actual) == "1f6bb1062dc7a49570cc298992fd6d99a5579cf387c53c9b0d2aa8c1d8232bac"}

before = state()
rep = mm_review_report(DB, PID, artifact_id=FROZEN, config=CFG)
by = {s["scene_id"]: s for s in rep.get("scenes") or []}
say("\n[1] 真实回归：冻结产物 {} 上 5-A 判 MISMATCH 的镜头 → 候选".format(FROZEN))
say("  5-A 判定 {} | 待复核镜头 {} | 候选状态 {}".format(
    json.dumps(rep.get("mm_counts"), ensure_ascii=False), rep.get("flagged_scenes"),
    json.dumps(rep.get("counts"), ensure_ascii=False)))
for sid in ("S04", "S06"):
    s = by.get(sid) or {}
    say("  {} 状态={} 期望域={} Δ={}".format(
        sid, s.get("status"), s.get("expected_domain"), (s.get("mm_evidence") or {}).get("delta")))
    for c in s.get("candidates") or []:
        v = c.get("visual_evidence") or {}
        say("     · {} | 视觉相似度={} 最像域={}({}) | 许可={}({}) | 来源={}/{} | 关键词分={}".format(
            c.get("name"), v.get("visual_sim_expected"), v.get("visual_best_domain"),
            v.get("visual_best_sim"), c.get("license"), c.get("license_class"),
            (c.get("source") or {}).get("provider"), (c.get("source") or {}).get("source_id"),
            (c.get("semantic_evidence") or {}).get("keyword_match_score")))
        for r in c.get("risks") or []:
            say("         风险：{}".format(r))
    for r in s.get("rejected") or []:
        say("     [排除] {} — {}".format(r.get("name"), "; ".join(r.get("excluded_reasons") or [])))
    say("     人工确认命令（未执行）：{}".format(s.get("human_command")))

say("\n[2] 与 4-C 历史人工决定的交叉核对（只读）")
con = sqlite3.connect(str(DB))
con.row_factory = sqlite3.Row
hist = [dict(r) for r in con.execute(
    "select decision_id, node, made_by, state, rationale, created_at from decisions "
    "where project_id=? and node='selection_override' order by created_at", (PID,)).fetchall()]
con.close()
say("  历史人工决定 {} 条（4-C 闭环）".format(len(hist)))
cross = {}
for s in ("S04", "S06"):
    chosen = None
    for h in hist:
        try:
            snap = json.loads(h.get("rationale") or "{}")
        except ValueError:
            snap = {}
        if s in (h.get("rationale") or ""):
            chosen = h["decision_id"]
    cand_ids = [c["asset_id"] for c in (by.get(s) or {}).get("candidates") or []]
    cross[s] = {"candidate_ids": cand_ids, "historic_decision_present": None}
    for h in hist:
        if s in (h.get("rationale") or ""):
            cross[s]["historic_decision_present"] = h["decision_id"]
    say("  {} 候选={} | 历史决定={}".format(s, cand_ids, cross[s]["historic_decision_present"]))

say("\n[3] 三条路径（要求 8）")
scene_fixture = {"scene_id": "SX", "verdict": "MISMATCH", "code": None,
                 "expected_domain": "xr_device", "expected_domain_source": "lexicon_4b_surface_vote_v1",
                 "narration_sha256": "x", "narration_matched_forms": {"xr_device": ["vr"]},
                 "current_asset": {"asset_id": "asset_shark"}, "top_k": [], "reason": "controlled"}
scoring_fixture = {"ok": True, "model": {"snapshot": "controlled", "weights_sha256": "controlled"},
                   "versions": {}, "scores": {
                       "asset_good": {"by_domain": {"xr_device": 0.28}, "top_domains": [],
                                      "visual_best_domain": "xr_device", "visual_best_sim": 0.28},
                       "asset_fair": {"by_domain": {"xr_device": 0.30}, "top_domains": [],
                                      "visual_best_domain": "xr_device", "visual_best_sim": 0.30}}}


def entry(aid, lic, klass, cleared):
    return {"asset_id": aid, "name": aid + ".jpg", "relative_path": "external/x.jpg",
            "sha256_prefix": aid[-12:], "bytes": 1, "license": lic, "license_class": klass,
            "license_cleared": cleared, "provider": "wikimedia_commons", "source_id": "1",
            "source_url": "https://x", "attribution": "T", "usage_restrictions": None,
            "scope": "external", "used_by_scenes": [], "match_score": 30}


paths = {}
paths["qualified"] = build_scene_candidates(
    scene_fixture, {"pool": [entry("asset_good", "CC BY-SA 4.0", "FREE_ATTRIBUTION", True)]},
    scoring_fixture, mmc_settings({}))
paths["no_qualified"] = build_scene_candidates(
    scene_fixture, {"pool": []}, scoring_fixture, mmc_settings({}))
paths["license_ineligible"] = build_scene_candidates(
    scene_fixture, {"pool": [entry("asset_fair", "fair use", "RESTRICTED", False)]},
    scoring_fixture, mmc_settings({}))
for k, v in paths.items():
    say("  {:<20s} status={:<9s} code={:<28s} 候选={} 排除={}".format(
        k, v.get("status"), str(v.get("code")), len(v.get("candidates") or []),
        len(v.get("rejected") or [])))
say("  （后两条为**受控构造**，走的是与真实路径完全相同的判定代码；样例素材/许可为构造值）")

say("\n[4] 只读、确定性与历史证据保留")
dup = mm_review_report(DB, PID, artifact_id=FROZEN, config=CFG)
after = state()
say("  两次运行报告一致（剔除临时目录/pid 占位后逐字节）：{}".format(norm(rep) == norm(dup)))
say("  DB 字节未变：{} | 五张表行数未变：{} | 项目 {} 个文件未变：{} | 未触发 redo/select-candidate：{}".format(
    before["db"] == after["db"], before["counts"] == after["counts"], len(after["files"]),
    before["files"] == after["files"],
    (rep.get("meta") or {}).get("redo_triggered") == 0
    and (rep.get("meta") or {}).get("select_candidate_called") == 0))
say("  模型：{} | 权重 sha256 {}".format(
    (rep.get("visual_model") or {}).get("snapshot"),
    str((rep.get("visual_model") or {}).get("weights_sha256"))[:16]))

out = {
    "phase": "5-B", "baseline": baseline,
    "model": rep.get("visual_model"), "versions": rep.get("visual_versions"),
    "mm_counts": rep.get("mm_counts"), "counts": rep.get("counts"),
    "policy": rep.get("policy"),
    "real_s04_s06": {sid: {"status": (by.get(sid) or {}).get("status"),
                           "code": (by.get(sid) or {}).get("code"),
                           "expected_domain": (by.get(sid) or {}).get("expected_domain"),
                           "mm_evidence": (by.get(sid) or {}).get("mm_evidence"),
                           "current_asset": (by.get(sid) or {}).get("current_asset"),
                           "candidates": (by.get(sid) or {}).get("candidates"),
                           "rejected": (by.get(sid) or {}).get("rejected"),
                           "human_command": (by.get(sid) or {}).get("human_command")}
                     for sid in ("S04", "S06")},
    "historic_cross_check": {"decisions": hist, "by_scene": cross},
    "paths": {k: {"status": v.get("status"), "code": v.get("code"),
                  "candidates": v.get("candidates"), "rejected": v.get("rejected"),
                  "note": v.get("note")} for k, v in paths.items()},
    "readonly": {"db_unchanged": before["db"] == after["db"],
                 "counts_unchanged": before["counts"] == after["counts"],
                 "project_files_unchanged": before["files"] == after["files"],
                 "project_files": len(after["files"]),
                 "redo_triggered": (rep.get("meta") or {}).get("redo_triggered"),
                 "select_candidate_called": (rep.get("meta") or {}).get("select_candidate_called")},
    "determinism": {"two_runs_identical": norm(rep) == norm(dup)},
    "note": ("只生成候选：不写库/不写产物/不替换素材/不触发 redo；需人工用 4-C 的 select-candidate 明确选定，"
             "再由人工执行 redo；4-B 与 5-A 历史证据原样保留。"),
}
(LOGS / "phase5b_candidates_evidence.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                       encoding="utf-8")
(LOGS / "phase5b_evidence_summary.txt").write_text("\n".join(LINES) + "\n", encoding="utf-8")
print("\nwritten", LOGS / "phase5b_candidates_evidence.json")
