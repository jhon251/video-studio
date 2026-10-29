# -*- coding: utf-8 -*-
"""6-E —— **EXECUTION-LOCKED 状态登记**（只登记，不执行任何 Proposal）。

人工指令（本轮，逐字记录）：
    进入 EXECUTION-LOCKED：
      E1 = APPROVE 但 execution_authorized=false；E2–E5 = HOLD。
    在收到人工"统一执行授权"之前，严格禁止：写 M5 执行审批台账 / 调用 ffmpeg / 渲染候选片 /
    执行任何 proposal / 修改 v9·C1–C4·DB·timeline·字幕·素材 / 自动将 HOLD 转 APPROVE / 自动执行 E1。
    当前只允许：①接收并登记人工补充的 E2/E3 素材与许可证、E4/E5 来源；
                ②接收最终统一执行授权。
    收到材料后只做**只读**完整性校验，不执行；
    收到统一执行授权后**先 STOP**，输出最终执行批次清单（APPROVE/HOLD、proposal_sha256、
    执行前置条件、冲突状态）；只有得到下一条明确"开始执行"指令后才进入执行阶段。
    S18 verified_positive_keep 保持不变。

本脚本**只做**：追加 1 条锁状态记录到既有 append-only 登记链 + 写 1 个**新**汇总 JSON +
只读完整性取证。**不**写 M5 执行审批台账、**不**调用 ffmpeg、**不**修改任何既有产物。

用法: python docs/regression_2x/phase6e_register_lock.py
产出: logs/phase6e_approval_status_r2.jsonl（追加 1 条）
      logs/phase6e_execution_lock.json（新文件）
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import execution as EX            # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
DB = ROOT / "projects" / "video_studio.db"
R2 = LOGS / "phase6e_round2.json"
M6C = LOGS / "phase6c_batch.json"
STATUS_JSON = LOGS / "phase6e_approval_status_r2.json"
LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
M5_APPROVALS = LOGS / "phase6b_m4_approvals_v9.jsonl"       # **禁止**写入
M5_EXEC_LEDGER = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"   # **禁止**写入
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
OUT = LOGS / "phase6e_execution_lock.json"
DECIDED_BY = "human:director(6-E execution lock)"
DECIDED_AT = "2026-10-03T00:00:00Z"

PROHIBITED = [
    "写入 M5 执行审批台账（phase6b_m4_approvals_v9.jsonl）",
    "调用 ffmpeg",
    "渲染任何候选片",
    "执行任何 proposal",
    "修改 v9 / C1–C4 / DB / timeline / 字幕 / 素材",
    "自动将 HOLD 转为 APPROVE",
    "自动执行 E1",
]
ALLOWED = ["接收并登记人工补充的 E2/E3 素材与许可证、E4/E5 来源（只做只读完整性校验）",
           "接收最终统一执行授权（收到后先 STOP，输出最终执行批次清单）"]


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def entry_sha(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def load_ledger(p: Path) -> list:
    if not p.is_file():
        return []
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


# ---- 0) 只读取证基线 ----
db_before = sha_file(DB)
film_before = sha_file(FILM)
m5ap_before, m5ex_before = sha_file(M5_APPROVALS), sha_file(M5_EXEC_LEDGER)
m5ap_n_before, m5ex_n_before = len(load_ledger(M5_APPROVALS)), len(load_ledger(M5_EXEC_LEDGER))
status = json.loads(STATUS_JSON.read_text(encoding="utf-8"))
r2 = json.loads(R2.read_text(encoding="utf-8"))
props = {p["label"][:2]: p for p in r2["proposals"]}
m6c = json.loads(M6C.read_text(encoding="utf-8"))
cand_before = {c["index"]: sha_file(ROOT / c["film"]) for c in m6c["candidates"]}
sandbox_out = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6c" / "output"
sb_before = sorted((p.name, p.stat().st_size) for p in sandbox_out.rglob("*") if p.is_file())
ledger = load_ledger(LEDGER)

# ---- 1) 追加锁状态记录（同一锁重复执行不重复追加）----
LOCK_ID = "6E-EXECUTION-LOCK-v1"
already = any(e.get("lock_id") == LOCK_ID for e in ledger)
appended = []
if not already:
    rec = {
        "schema": "execution-lock-v1", "stage": "6-E", "lock_id": LOCK_ID,
        "state": "EXECUTION-LOCKED",
        "human_instruction": {
            "statuses": [{"label": k, "decision": d} for k, d in
                         [("E1", "APPROVE"), ("E2", "HOLD"), ("E3", "HOLD"),
                          ("E4", "HOLD"), ("E5", "HOLD")]],
            "e1_execution_authorized": False,
            "prohibited_until_unified_authorization": PROHIBITED,
            "allowed_now": ALLOWED,
            "on_materials_received": "只做只读完整性校验，不执行",
            "on_authorization_received": "先 STOP，输出最终执行批次清单（APPROVE/HOLD、"
                                         "proposal_sha256、执行前置条件、冲突状态）",
            "execution_gate": "仅在下一条明确『开始执行』指令后才进入执行阶段",
            "s18_retention": "verified_positive_keep 保持不变",
        },
        "proposal_bindings": [{"label": k, "proposal_id": props[k]["proposal_id"],
                               "proposal_sha256": EX.proposal_sha256(props[k]),
                               "decision": status["statuses"][i]["decision"],
                               "execution_authorized": status["statuses"][i]["execution_authorized"]}
                              for i, k in enumerate(("E1", "E2", "E3", "E4", "E5"))],
        "invariants": {"no_m5_approval_write": True, "ffmpeg_invocations": 0,
                       "no_execution": True, "hold_not_auto_approve": True,
                       "e1_not_auto_executed": True, "s18_retention_unchanged": True,
                       "c1_c4_untouched": True, "v9_untouched": True, "db_untouched": True},
        "decided_by": DECIDED_BY, "decided_at": DECIDED_AT,
        "provenance": "人工指令：6-E 进入 EXECUTION-LOCKED；仅允许接收材料与统一执行授权",
        "reference": {"status_json": str(STATUS_JSON.relative_to(ROOT)),
                      "round2_json": str(R2.relative_to(ROOT))},
        "read_only": True, "enforced": False, "advisory": True, "executes_changes": False,
    }
    prev = ledger[-1]["entry_sha256"] if ledger else ""
    rec["seq"] = len(ledger) + 1
    rec["prev_sha256"] = prev
    rec["entry_sha256"] = entry_sha(rec)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    ledger.append(rec)
    appended.append(rec)

# ---- 2) 链校验 ----
prev, chain_ok, broken = "", True, None
for i, e in enumerate(ledger, start=1):
    if e["seq"] != i or e["prev_sha256"] != prev or e["entry_sha256"] != entry_sha(e):
        chain_ok, broken = False, i
        break
    prev = e["entry_sha256"]
assert chain_ok, "登记链校验失败 at {}".format(broken)

# ---- 3) 只读完整性取证（证明锁生效：无执行、无禁止写入、既有产物未变）----
db_after, film_after = sha_file(DB), sha_file(FILM)
m5ap_after, m5ex_after = sha_file(M5_APPROVALS), sha_file(M5_EXEC_LEDGER)
cand_after = {c["index"]: sha_file(ROOT / c["film"]) for c in m6c["candidates"]}
sb_after = sorted((p.name, p.stat().st_size) for p in sandbox_out.rglob("*") if p.is_file())
retention = r2["retention_records"][0]
conflicts = {"cross_batch_overlaps": r2["cross_batch_overlaps"],
             "internal_conflict_pairs": r2["conflict_matrix_6e"]["conflict_pair_count"],
             "e1_h7_overlap_confirmed_by_human": True,
             "note": "跨批次重叠为 M5 已知边界；因处于 EXECUTION-LOCKED，当前**无任何阻断发生**"
                     "（未提交执行批次）"}
out = {
    "schema": "execution-lock-summary-v1", "stage": "6-E",
    "state": "EXECUTION-LOCKED",
    "note": "**只登记锁状态**：未执行任何 Proposal、未写 M5 执行审批台账、未调用 ffmpeg、未渲染、"
            "未修改 v9/C1–C4/DB/timeline/字幕/素材（既有 JSON 亦未被改写；本文件为新增）。",
    "statuses": [{"label": s["label"], "proposal_id": s["proposal_id"],
                  "decision": s["decision"], "execution_authorized": s["execution_authorized"],
                  "awaiting": s["awaiting"]} for s in status["statuses"]],
    "prohibited_until_unified_authorization": PROHIBITED,
    "allowed_now": ALLOWED,
    "on_materials_received": "只做只读完整性校验（存在/sha256/可解码/许可门禁/来源可核验），"
                             "并登记为『材料已收、待统一授权』；**不执行**",
    "on_authorization_received": "先 STOP，输出最终执行批次清单（E1–E5 的 APPROVE/HOLD、"
                                 "每条 proposal_sha256、执行前置条件、冲突状态）；"
                                 "仅在下一条明确『开始执行』指令后才执行",
    "proposal_sha256": {k: EX.proposal_sha256(props[k]) for k in ("E1", "E2", "E3", "E4", "E5")},
    "conflicts": conflicts,
    "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(ledger),
               "appended_this_run": len(appended), "chain_ok": chain_ok,
               "lock_entry_seq": next((e["seq"] for e in ledger if e.get("lock_id") == LOCK_ID),
                                      None)},
    "integrity": {
        "db_unchanged": db_before == db_after,
        "v9_unchanged": film_before == film_after == V9_SHA,
        "c1_c4_sha_unchanged": all(cand_after[c["index"]] == c["film_sha256"]
                                   for c in m6c["candidates"]),
        "sandbox_output_unchanged": sb_before == sb_after,
        "m5_approvals_ledger_untouched": (m5ap_before == m5ap_after
                                          and m5ap_n_before == len(load_ledger(M5_APPROVALS))),
        "m5_execution_ledger_untouched": (m5ex_before == m5ex_after
                                          and m5ex_n_before == len(load_ledger(M5_EXEC_LEDGER))),
        "m5_approvals_entries": m5ap_n_before,
        "m5_execution_entries": m5ex_n_before,
        "s18_retention_unchanged": (retention["kind"] == "verified_positive_keep"
                                    and retention["no_proposal_generated"] is True),
        "ffmpeg_invocations": 0, "executed_anything": False,
        "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    "next_inputs_expected": ["人工补充的 E2/E3 素材 + 许可证（含 provenance）",
                             "人工补充的 E4/E5 信息槽公开来源",
                             "人工『统一执行授权』"],
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

print("锁状态:", out["state"], "| 台账追加", len(appended), "条 | 台账共", len(ledger),
      "条 | chain_ok", chain_ok, "| lock seq", out["ledger"]["lock_entry_seq"])
for s in out["statuses"]:
    print("  {} {} | 执行授权={}".format(s["label"][:2], s["decision"], s["execution_authorized"]))
print("M5 审批台账未写:", out["integrity"]["m5_approvals_ledger_untouched"],
      "(entries={})".format(out["integrity"]["m5_approvals_entries"]),
      "| M5 执行台账未写:", out["integrity"]["m5_execution_ledger_untouched"],
      "(entries={})".format(out["integrity"]["m5_execution_entries"]))
print("完整性: DB {} | v9 {} | C1–C4 {} | 沙箱产物 {} | ffmpeg {} 次".format(
    out["integrity"]["db_unchanged"], out["integrity"]["v9_unchanged"],
    out["integrity"]["c1_c4_sha_unchanged"], out["integrity"]["sandbox_output_unchanged"],
    out["integrity"]["ffmpeg_invocations"]))
print("json ->", OUT)
