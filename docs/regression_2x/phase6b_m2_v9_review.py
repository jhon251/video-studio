# -*- coding: utf-8 -*-
"""6-B/M2 —— 用**真实 v9** 完成人工审片闭环（只读 + append-only + 零执行）。

人工决策的**来源**（不发明、不推断）：
  · `docs/regression_2x/PHASE6A_AUDIT.md` §2/§3：人工 6 项发现逐条核实（VERIFIED / PARTIAL）
    与"人工判 v9 = FAIL（不得作为发布候选）"；
  · `docs/KNOWN_ISSUES.md` #67（人工 v9 FAIL 登记）。
本脚本把**已记录的人工结论**转成台账决策（ACCEPT / REJECT / DEFER），并覆盖
6-B/M1 重新发现的 7 项导演质量问题（H1…H7）。

严格边界：不重渲染、不改 v9 产物、不换素材/剪辑/字幕/旁白、不写 DB、不接入 TASK_BLOCKED；
台账 **append-only + 哈希链**（重复运行会追加新版本，历史保留可查）。

用法: python docs/regression_2x/phase6b_m2_v9_review.py
产出: logs/phase6b_m2_review_ledger_v9.jsonl（append-only 台账）
      logs/phase6b_m2_review_v9.json（闭环报告）
"""
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
LEDGER = LOGS / "phase6b_m2_review_ledger_v9.jsonl"

from video_studio.core import human_review as HR  # noqa: E402
from video_studio.ops.review import build_review_report  # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
AUDIT_MD = "docs/regression_2x/PHASE6A_AUDIT.md"
KNOWN = "docs/KNOWN_ISSUES.md#67"

#: 人工决策来源简写（全部指向**已记录**的人审结论）
P_HUMAN_FAIL = "human:6-A 审计 §3 注 + KNOWN_ISSUES #67（人工判 v9 = FAIL，不得作为发布候选）"
P_H2 = "human:6-A 审计 §2.2 + §3 表行2（VERIFIED）"
P_H3 = "human:6-A 审计 §2.3 + §3 表行2（VERIFIED；正文 60 s 口径 / DQ 阈值 25 s）"
P_H4 = "human:6-A 审计 §2.4（VERIFIED）"
P_H5 = "human:6-A 审计 §2.5 + §3（Judge MISMATCH 2 镜 / UNKNOWN 18）；" \
       "6-B/M1 DQ-8 逐镜复现（MISMATCH 3 镜：S05/S11/S18）"
P_H6 = "human:6-A 审计 §2.6 + §3 表行4（VERIFIED）"
P_H7 = "human:6-A 审计 §2.7 + §3 表行5（VERIFIED）"
P_H1 = "human:6-A 审计 §2.1 + §3 表行3（人工抽帧确认 hook 错位 VERIFIED）；" \
       "DQ-1 侧唯一只读证据全 UNKNOWN ⇒ 机械层不可证"
P_SUB = "human:6-A 审计 §3 表行6（PARTIAL：已改善，仍有残留）"
P_HITL = "human:6-A 审计 §4 表（HITL editing_plan 的 approve 理由与最终成片不一致，已登记）"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


# ---- 1) 只读构建：DQ findings → review items ----
db_before, film_before = sha(DB), sha(FILM) if FILM.is_file() else None
rep = build_review_report(PID, DB, ROOT, CFG, film_task=FILM_TASK, evidence_path=EVIDENCE,
                          ledger_path=str(LEDGER), measure_freeze=True)
items = rep["items"]
by = {}
for it in items:
    by.setdefault((it["metric"], it["kind"]), []).append(it)


def pick(metric, kind, idx=0):
    lst = by.get((metric, kind)) or []
    if not lst:
        raise SystemExit("找不到 finding：{} / {}".format(metric, kind))
    return lst[idx]


# ---- 2) 人审决策（覆盖 M1 重新发现的 7 项 + UNKNOWN 路径 + 2 项人工审计记录）----
DECISIONS = [
    # H1 Hook：人工确认错位 ⇒ REJECT；同时 DQ-1 的不可证状态单列 DEFER（UNKNOWN 不走 PASS）
    (pick("DQ-1", "hook_layer_verdict"), "REJECT", "人工抽帧确认 hook 画面与'AI 证明'无关（6-A §2.1）",
     "human:video-auditor(6-A)", P_H1, [{"metric": "DQ-1", "kind": "hook_layer_verdict"}]),
    (pick("DQ-1", "metric_state_unprovable"), "DEFER",
     "DQ-1 唯一只读证据全 UNKNOWN ⇒ 机械层不可证；保持人工复核路径，不得视为 PASS",
     "human:video-auditor(6-A)", P_H1, []),
    # H2 素材重复
    (pick("DQ-2", "unique_assets_below_min"), "REJECT",
     "21 镜仅 4 个唯一素材（下限 6）⇒ 建议补足素材多样性（本阶段不执行）",
     "human:video-auditor(6-A)", P_H2,
     [{"metric": "DQ-2", "kind": "asset_share_exceeds"}]),
    # H3 静态保持（类级决策覆盖 21 条实例 finding）
    (pick("DQ-3", "over_hold_share_exceeds"), "REJECT",
     "21/21 镜保持 > 25 s、均值 72.95 s ⇒ 建议重剪/缩短单镜（本阶段不执行）",
     "human:video-auditor(6-A)", P_H3,
     [{"metric": "DQ-3", "kind": "hold_exceeds_max"},
      {"metric": "DQ-3", "kind": "freeze_profile"}]),
    # H4 密度
    (pick("DQ-4", "scene_changes_below_min"), "REJECT",
     "0.822 镜变/分钟（< 2.0）⇒ 建议提升视觉变化密度（本阶段不执行）",
     "human:video-auditor(6-A)", P_H4,
     [{"metric": "DQ-4", "kind": "longest_static_scene"}]),
    # H5 语义支撑：MISMATCH 成立 ⇒ REJECT；UNKNOWN 部分 ⇒ DEFER（保守）
    (pick("DQ-8", "semantic_mismatch_scenes"), "REJECT",
     "S05/S11/S18 逐镜语义 MISMATCH ⇒ 建议替换/补拍对应画面（本阶段不执行）",
     "human:video-auditor(6-A)", P_H5, []),
    # H6 视觉高潮（核心论点镜素材不足）
    (pick("DQ-5", "distinct_assets_in_core_below_min"), "REJECT",
     "核心论点镜 20 个仅 4 素材、无视觉升级 ⇒ 建议补示意图/数据可视化（本阶段不执行）",
     "human:video-auditor(6-A)", P_H6,
     [{"metric": "DQ-5", "kind": "mean_hold_in_core_exceeds"},
      {"metric": "DQ-5", "kind": "semantic_mismatch_in_core"}]),
    # H7 片尾
    (pick("DQ-6", "no_outro_keyword_in_tail"), "REJECT",
     "末镜无 outro/结束卡 ⇒ 建议补片尾（本阶段不执行）",
     "human:video-auditor(6-A)", P_H7,
     [{"metric": "DQ-6", "kind": "tail_silence_exceeds"}]),
    (pick("DQ-6", "metric_state_unprovable"), "DEFER",
     "DQ-6 语义项 UNKNOWN（无可用只读证据）⇒ 人工复核；不得视为 PASS",
     "human:video-auditor(6-A)", P_H7, []),
]


def append_human_audit_items():
    """把**人工审计记录**（非 DQ 派生）也纳入同一闭环（origin=human_audit）。"""
    extra = []
    for kind, summary, prov in (
            ("human_subtitle_wrapping_residual",
             "字幕断行残留：33.8% 字幕落在静音区；长句两行断开的语义切割仍可优化（人审 PARTIAL）",
             P_SUB),
            ("human_hitl_rationale_mismatch",
             "HITL editing_plan 的 approve 理由（25 镜占位卡方案）与最终 4 素材成片不一致（已登记）",
             P_HITL)):
        extra.append(HR.human_audit_item(PID, kind, summary, prov, film_task=FILM_TASK,
                                         evidence=prov.split("（")[0]))
    return extra


extra_items = append_human_audit_items()
for it in extra_items:
    DECISIONS.append((it, "DEFER", it["payload"]["summary"], "human:video-auditor(6-A)",
                      it["source_evidence"], []))

# ---- 3) 追加到 append-only 台账（历史保留；重复运行会追加新版本）----
appended = []
for item, dec, reason, by_, prov, covers in DECISIONS:
    rec = HR.make_decision(item, dec, reason, by_, prov, covers=covers,
                           at="{}T00:00:00Z".format(date.today().isoformat()))
    appended.append(HR.append_decision(LEDGER, rec))

# ---- 4) 复核（读回台账，校验链 + 1:1 追溯）----
rep2 = build_review_report(PID, DB, ROOT, CFG, film_task=FILM_TASK, evidence_path=EVIDENCE,
                           ledger_path=str(LEDGER), extra_items=extra_items,
                           film_level_decision={
                               "decision": "REJECT",
                               "reason": "人工判 v9 = FAIL（不得作为发布候选）",
                               "decided_by": "human:video-auditor(6-A)",
                               "provenance": P_HUMAN_FAIL,
                               "executes_changes": False},
                           measure_freeze=True)
summary = rep2["summary"]
db_after, film_after = sha(DB), sha(FILM) if FILM.is_file() else None

out = {
    "schema": "human-review-v1",
    "kind": "6b_m2_v9_human_review_closure",
    "stage": "6-B/M2",
    "read_only": True, "enforced": False, "advisory": True, "executes_changes": False,
    "note": "把 DQ 只读 findings 转化为可审计的人工决策（ACCEPT/REJECT/DEFER）；"
            "决策来源为**已记录的人审结论**（6-A 审计 / KNOWN_ISSUES #67），不发明、不推断；"
            "本阶段**不执行任何修改**（REJECT 仅表示建议需要修改）。",
    "inputs": {"project_id": PID, "film_task": FILM_TASK, "film": str(FILM),
               "evidence": EVIDENCE, "ledger": str(LEDGER.relative_to(ROOT))},
    "coverage": {"m1_rediscovered_findings": ["H1-hook", "H2-repetition", "H3-static-hold",
                                             "H4-density", "H5-semantic-support",
                                             "H6-climax", "H7-ending"],
                 "all_covered": True},
    "items": rep2["items"],
    "summary": summary,
    "film_level_decision": rep2["summary"]["film_level_decision"],
    "appended_this_run": [{"seq": r["seq"], "finding_id": r["finding_id"],
                           "decision": r["decision"], "kind": r["kind"],
                           "metric": r["metric"], "covers": r["covers"],
                           "provenance": r["provenance"]} for r in appended],
    "read_only_evidence": {
        "db_sha256_before": db_before, "db_sha256_after": db_after,
        "db_unchanged": db_before == db_after,
        "film_sha256_before": film_before, "film_sha256_after": film_after,
        "film_unchanged": film_before == film_after,
        "project_files_touched": [],
    },
}
(LOGS / "phase6b_m2_review_v9.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")

print("DQ:", rep2["inputs"]["dq_metrics"])
print("items={} decided={} covered_by_class={} unresolved={}".format(
    summary["items"], summary["decided"], summary["covered_by_class_decision"],
    len(summary["unresolved"])))
print("决策计数:", {k: v for k, v in summary["decision_counts"].items() if v})
print("UNKNOWN 项是否全部 DEFER:", summary["unknown_routed_to_defer"],
      "| UNKNOWN 被 ACCEPT:", summary["unknown_accepted"])
print("台账:", summary["ledger"])
print("成片级决策:", out["film_level_decision"]["decision"],
      "| 执行动作:", summary["executed_actions"])
print("只读: DB 未变", out["read_only_evidence"]["db_unchanged"],
      "| 成片未变", out["read_only_evidence"]["film_unchanged"])
print("json ->", LOGS / "phase6b_m2_review_v9.json")
