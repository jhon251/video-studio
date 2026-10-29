# -*- coding: utf-8 -*-
"""6-B/M4 —— 在真实 v9 上完成**受控执行闭环**（沙箱内执行；v9 母版零改动）。

本脚本演示并取证：
  1. `H7-outro-card` → 人工 **APPROVE** → 沙箱执行（末段加入片尾卡、总时长不变）→ **强制 PI/DQ 复核**；
  2. `H2-asset-pool-diversity` → 人工 **APPROVE** → 无真实可用新素材 ⇒ `PENDING_HUMAN_ASSET`（不虚构、不占位）；
  3. `H3-batch1-split-longest` → 人工 **REJECT** ⇒ 执行被 `BLOCKED_REJECTED` **阻断**；
  4. `H1-hook-replace` → **未批准** ⇒ 执行被 `BLOCKED_UNAPPROVED` **阻断**；
  5. **tamper guard**：对已批准的 H7 传入被改动的 proposal 副本 ⇒ `BLOCKED_TAMPERED`；
  6. 全程只读 v9：源项目目录、v9 母版成片 sha256、DB 均逐字节不变；执行只在
     `output/phase6b_m4_sandbox/` 内产出。

用法: python docs/regression_2x/phase6b_m4_execute_v9.py
产出: logs/phase6b_m4_approvals_v9.jsonl / logs/phase6b_m4_execution_ledger_v9.jsonl /
      logs/phase6b_m4_v9_execution.json
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
M3_REPORT = LOGS / "phase6b_m3_proposals_v9.json"
APPROVALS = LOGS / "phase6b_m4_approvals_v9.jsonl"
EXEC_LEDGER = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"

from video_studio.core import captions as core_captions  # noqa: E402
from video_studio.core import execution as EX  # noqa: E402
from video_studio.ops import direction as ops_direction  # noqa: E402
from video_studio.ops import execution as ops_exec  # noqa: E402

CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    return {p.name: (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


# ---- 0) 只读取证基线 ----
db_b, film_b, src_dir_b = sha(DB), sha(FILM), manifest(FILM.parent)

# ---- 1) 读 6-B/M3 方案（现算，保证 hash 与执行时一致）----
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location(
    "m3_proposals", str(ROOT / "docs" / "regression_2x" / "phase6b_m3_v9_proposals.py"))
# 说明：直接 import 会重跑 M3 脚本（向登记表追加）；改为读 M3 报告 + 登记表现算 hash
plan_m3 = json.loads(M3_REPORT.read_text(encoding="utf-8"))
proposals = plan_m3["proposals"]
by_label = {p.get("label"): p for p in proposals}
print("M3 方案:", sorted(by_label))

# ---- 2) v9 只读上下文（脚本/旁白产物 + 时间轴 + 字幕 + 证据）----
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
recs = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    (PID,))]
con.close()
by_type = {}
for r in recs:
    by_type.setdefault(r["type"], []).append(r)


def payload(t, task=None):
    lst = by_type.get(t) or []
    rec = next((x for x in lst if task and x["task_id"] == task), lst[-1] if lst else None)
    if not rec:
        return {}
    p = Path(rec["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


script = payload("script_output")
voice = payload("voice_output")
render = payload("render_output", FILM_TASK)
timeline = render.get("material_timeline") or []
timeline_total = float((render.get("duration_contract") or {}).get("timeline_duration_s") or 1532.0)
narr_s = voice.get("narration_duration_s")

# ---- 3) 沙箱准备（输入=复制品；源项目零改动）----
box = ops_exec.prepare_sandbox(ROOT, PID, "h7outro", FILM,
                               artifacts={"script_output": script, "voice_output": voice})
ctx = {"root": ROOT, "box": box["box"], "film": box["film"], "artifacts": box["artifacts"],
       "files": box["files"], "ffmpeg": CFG["tools"]["ffmpeg"]["path"],
       "config": CFG, "timeline": timeline, "timeline_duration_s": timeline_total,
       "evidence": ops_direction.load_evidence(EVIDENCE, ROOT),
       "cues": core_captions.build_cues(
           [{"narration": s.get("narration", ""), "duration_s": s.get("duration_s")}
            for s in (script.get("segments") or [])]),
       "asset_index": {}}

# ---- 4) 人工审批（append-only 台账）----
approvals = []


def approve(label, decision, reason, prov):
    p = by_label[label]
    rec = EX.make_approval(p, decision, "human:director(6-B/M4)", reason, prov,
                           at="2026-09-28T00:00:00Z")
    rec = EX.append_approval(APPROVALS, rec)
    approvals.append(rec)
    return rec


approve("H7-outro-card", "APPROVE",
        "同意在末镜窗口内**原地**加片尾卡（不改总时长、不改旁白正文）",
        "human:6-A 审计 §2.7（缺片尾 VERIFIED）+ KNOWN_ISSUES #67")
approve("H2-asset-pool-diversity", "APPROVE",
        "同意补足素材多样性（4→≥6），但**必须**使用真实可验证素材",
        "human:6-A 审计 §2.2（素材重复 VERIFIED）")
approve("H3-batch1-split-longest", "REJECT",
        "本轮不重剪画面节奏（与既有 5.x 交付节奏策略冲突，留待后续人工统一规划）",
        "human:导演决定（本轮范围外）")

# ---- 5) 受控执行（只执行 APPROVE 且 hash 匹配者）----
executions = []


def run(label, proposal_obj=None, note=""):
    p = proposal_obj if proposal_obj is not None else by_label[label]
    rec = EX.execute_proposal(p, approvals, ops_exec.EXECUTORS, ctx,
                              recheck=ops_exec.pi_recheck)
    rec["note"] = note
    rec = EX.append_execution(EXEC_LEDGER, rec)
    executions.append(rec)
    return rec


r_h7 = run("H7-outro-card", note="受控执行：沙箱内末段加片尾卡，总时长不变")
r_h2 = run("H2-asset-pool-diversity", note="APPROVE 但无真实可用新素材 ⇒ 人工待处理")
r_h3 = run("H3-batch1-split-longest", note="人工 REJECT ⇒ 必须阻断执行")
r_h1 = run("H1-hook-replace", note="未批准 ⇒ 必须阻断执行")
tampered = dict(by_label["H7-outro-card"])
tampered["proposed_change"] = dict(tampered["proposed_change"])
tampered["proposed_change"]["what"] = "（被篡改）把全片重做成 3D 动画"
r_tamper = run("H7-outro-card", proposal_obj=tampered, note="proposal 被改动 ⇒ tamper guard 必须阻断")

# ---- 6) 只读取证：源项目 / v9 母版 / DB 零改动 ----
db_a, film_a, src_dir_a = sha(DB), sha(FILM), manifest(FILM.parent)

summary = EX.summarize_executions(proposals, approvals, executions)
summary["ledger"] = {"approvals": {"path": str(APPROVALS.relative_to(ROOT)),
                                   "entries": len(EX.load_ledger(APPROVALS)),
                                   "chain_ok": EX.verify_chain(EX.load_ledger(APPROVALS))["ok"]},
                     "executions": {"path": str(EXEC_LEDGER.relative_to(ROOT)),
                                    "entries": len(EX.load_ledger(EXEC_LEDGER)),
                                    "chain_ok": EX.verify_chain(EX.load_ledger(EXEC_LEDGER))["ok"]}}

out = {
    "schema": "revision-execution-run-v1",
    "stage": "6-B/M4",
    "read_only_source": True, "auto_approved": False, "auto_executed_all": False,
    "note": "受控执行：仅执行人工 APPROVE 且 proposal hash 匹配的方案；执行在沙箱内完成，"
            "源项目与 v9 母版零改动；执行后强制重跑 PI-1…PI-6（复用冻结定义）并做 DQ 只读复核；"
            "PI FAIL/UNKNOWN 按既有门禁处理（本层不提升、不绕过）。",
    "inputs": {"project_id": PID, "film_task": FILM_TASK, "film": str(FILM),
               "m3_report": str(M3_REPORT.relative_to(ROOT)),
               "sandbox": str(Path(box["box"]).relative_to(ROOT))},
    "sandbox": {"box": str(Path(box["box"]).relative_to(ROOT)),
                "source_film_sha256": box["source_film_sha256"],
                "film_copy_sha256": box["film_sha256"]},
    "approvals": [{"approval_id": a["approval_id"], "proposal_label": a["proposal_label"],
                   "decision": a["decision"], "approved_by": a["approved_by"],
                   "reason": a["reason"], "provenance": a["provenance"],
                   "proposal_sha256": a["proposal_sha256"], "seq": a["seq"],
                   "auto_approved": a.get("auto_approved", False)} for a in approvals],
    "executions": executions,
    "summary": summary,
    "read_only_evidence": {
        "db_sha256_before": db_b, "db_sha256_after": db_a, "db_unchanged": db_b == db_a,
        "v9_master_sha256_before": film_b, "v9_master_sha256_after": film_a,
        "v9_master_unchanged": film_b == film_a,
        "v9_output_dir_unchanged": src_dir_b == src_dir_a,
        "project_files_touched": [],
    },
}
(LOGS / "phase6b_m4_v9_execution.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                   encoding="utf-8")

print("审批:", [(a["proposal_label"], a["decision"]) for a in approvals])
print("执行状态:", {r["proposal_label"]: r["state"] for r in executions})
print("H7 复核: PI", r_h7["recheck"]["pi_metrics"], "| gate", r_h7["pi_gate_outcome"])
print("H7 复核: DQ", r_h7["recheck"]["dq_metrics"], "| DQ-6 结构", r_h7["recheck"]["dq_metrics"]["DQ-6"])
print("未批准却执行:", summary["executed_without_approval"], "| 自动批准:", summary["auto_approved"],
      "| 已提升:", summary["promoted"])
print("台账链:", summary["ledger"])
print("只读: DB 未变", out["read_only_evidence"]["db_unchanged"],
      "| v9 母版未变", out["read_only_evidence"]["v9_master_unchanged"],
      "| v9 output 目录未变", out["read_only_evidence"]["v9_output_dir_unchanged"])
print("json ->", LOGS / "phase6b_m4_v9_execution.json")
