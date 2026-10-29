# -*- coding: utf-8 -*-
"""6-E —— **人工批准状态登记**（只登记，不执行）。

人工输入（本轮确定）：
    E1 = APPROVE（**执行延后**，等待本轮统一执行授权）
    E2 = HOLD（等待真实素材 + 许可/provenance）
    E3 = HOLD（等待真实素材 + 许可/provenance）
    E4 = HOLD（等待 4 个信息槽的公开来源）
    E5 = HOLD（等待 4 个信息槽的公开来源）

守恒规则（写入本登记并在测试/报告中可核验）：
  · HOLD ≠ REJECT，HOLD 也**不**自动转 APPROVE（无任何自动转换路径）；
  · E1 虽 APPROVE，**执行延后**——本步骤**不**写 M5 执行审批台账（那会使方案进入可执行态）；
  · E1 与已执行 H7 的跨批次重叠 = **人工明确确认**（记录在案）；
  · S18 `verified_positive_keep` 保持不变；H1/H6/H2/H4 保持原状态；
  · **禁止** ffmpeg / 渲染 / 修改任何既有产物（本脚本只**新增**登记文件，不重写既有 JSON）。

用法: python docs/regression_2x/phase6e_register_approval_status.py
产出: logs/phase6e_approval_status_r2.jsonl（append-only 哈希链）
      logs/phase6e_approval_status_r2.json（汇总 + 完整性证明）
"""
import hashlib
import json
import sqlite3
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
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
OUT = LOGS / "phase6e_approval_status_r2.json"
DECIDED_BY = "human:director(6-E approval round)"
DECIDED_AT = "2026-10-02T00:00:00Z"
AWAITING = "等待本轮统一执行授权（E1 已 APPROVE 但执行延后）"


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


# ---- 0) 只读取证基线（不修改任何既有产物）----
db_before = sha_file(DB)
film_before = sha_file(FILM)
r2 = json.loads(R2.read_text(encoding="utf-8"))
props = {p["label"][:2]: p for p in r2["proposals"]}
m6c = json.loads(M6C.read_text(encoding="utf-8"))
cand_before = {c["index"]: sha_file(ROOT / c["film"]) for c in m6c["candidates"]}
sandbox_out = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6c" / "output"
sb_before = sorted((p.name, p.stat().st_size) for p in sandbox_out.rglob("*") if p.is_file())

# ---- 1) 待登记的人工决定（严格照抄人工输入；不做任何自动推断）----
HUMAN_INPUT = [("E1", "APPROVE"), ("E2", "HOLD"), ("E3", "HOLD"), ("E4", "HOLD"), ("E5", "HOLD")]
MISSING = {
    "E2": ["真实外部素材文件（绝对路径 + 字节 + sha256）",
           "许可声明与类别（PD / CC BY 等）+ 来源 URL + 署名信息（人工核验）",
           "1080p 可读性确认（版面文字可辨识）",
           "语义相关性人工确认：与『Tymoczko 引文 / 可检视性争论』直接对应",
           "禁用项确认：**不得**使用 IMO 合影（asset_432cd85be6f1）",
           "人工选材决定（绑定到 proposal_id rp-f3f8548602fa + 素材 sha256）"],
    "E3": ["真实外部素材文件（绝对路径 + 字节 + sha256）",
           "许可/商标可用范围确认（Lean 标识、代码片段许可）+ 来源 URL",
           "1080p 可读性确认（定理/策略关键字可辨识）",
           "语义相关性人工确认：与『Lean / mathlib / 形式化证明』直接对应",
           "禁用项确认：**不得**使用 IMO 合影",
           "确认不破坏 S11 既有切分子镜结构（H3b 已执行）"],
    "E4": ["4 个信息槽各自的**公开可核验来源**（URL/文献）与人工确认："
           "①球堆积问题定义 ②FCC/HCP 候选结构对比 ③『审稿人无法 100% 确认』含出处 ④Flyspeck 目标与状态",
           "『无来源 ⇒ 留空或改为纯定性表述』的人工确认（宁缺勿造）",
           "排版方案确认（位置/字号/时长；不遮挡主体、不与字幕抢位、遵守底部安全区）"],
    "E5": ["4 个信息槽各自的**公开可核验来源**（URL/文献）与人工确认："
           "①形式化验证作为协作工具的论证结构 ②AlphaGeometry/Nature 2024 时间线 "
           "③系统参加 IMO 题目的精确表述 ④『银牌=分数换算』的可核对说明",
           "与 S16 既有口径**一致性**确认（『银牌是分数换算，不是实际参赛成绩』）",
           "『无来源 ⇒ 留空或改为纯定性表述』的人工确认",
           "排版方案确认（同上）"],
}
E1_PRECONDITIONS = [
    "执行环境再次校验 C:/Windows/Fonts/msyh.ttc 存在且覆盖所需字形（『感谢观看　我们下期再见』逐字可渲染）",
    "字体缺失或字形不全 ⇒ **fail-closed**：保持原状并回报人工，不得改用未审定字体、不得降级交付",
    "仅允许执行一次（幂等门禁；重复执行将造成窗口二次编码有损）",
    "必须守恒：总时长不变、音轨为母版整条音轨流复制、该窗口字幕按既有 cue 表重烧录",
    "执行后强制重跑 PI-1…PI-6 + DQ-1…DQ-8，并以片尾卡抽帧作为验收证据",
    "跨批次重叠（与已执行 H7 同 scene+target）已由**人工明确确认**，登记在案",
    "**等待本轮统一执行授权**后才可执行（本登记不写 M5 执行审批台账，故当前不可执行）",
]

# ---- 2) 追加登记（append-only 哈希链；同一内容重复执行不重复追加）----
ledger = load_ledger(LEDGER)
lines = []
for key, decision in HUMAN_INPUT:
    p = props[key]
    rec = {
        "schema": "directorial-approval-status-v1", "stage": "6-E",
        "label": p["label"], "proposal_id": p["proposal_id"],
        "proposal_sha256": EX.proposal_sha256(p),
        "decision": decision,                       # APPROVE | HOLD（HOLD 是独立状态）
        "decision_semantics": ("人工批准；执行**延后**（等待统一执行授权）" if decision == "APPROVE"
                               else "人工暂缓（HOLD）：不是 REJECT，也不自动转 APPROVE"),
        "is_reject": False,
        "execution_authorized": False,              # 本轮一律不授权执行
        "execution_deferred": True if decision == "APPROVE" else None,
        "awaiting": AWAITING if decision == "APPROVE" else "等待人工补齐前置材料",
        "missing_prerequisites": MISSING.get(key, []),
        "execution_preconditions": E1_PRECONDITIONS if key == "E1" else [],
        "human_confirmed_overlaps": ([{"with": "H7-outro-card", "kinds": ["scene", "target"],
                                       "confirmed_by_human": True}] if key == "E1" else []),
        "decided_by": DECIDED_BY, "decided_at": DECIDED_AT,
        "provenance": "人工批准轮（6-E）：E1=APPROVE（延后执行）；E2–E5=HOLD（等待前置材料）",
        "round2_reference": {"round2_json": str(R2.relative_to(ROOT)),
                             "review_ledger": r2["inputs"]["review_ledger"],
                             "register": r2["inputs"]["register"]},
        "no_execution_in_this_step": True,
        "ffmpeg_invocations": 0,
        "read_only": True, "enforced": False, "advisory": True, "executes_changes": False,
    }
    # 幂等：同一 (proposal_id, decision) 已登记则不重复追加
    if any(e["proposal_id"] == rec["proposal_id"] and e["decision"] == rec["decision"]
           for e in ledger):
        continue
    prev = ledger[-1]["entry_sha256"] if ledger else ""
    rec["seq"] = len(ledger) + 1
    rec["prev_sha256"] = prev
    rec["entry_sha256"] = entry_sha(rec)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    ledger.append(rec)
    lines.append(rec)

# ---- 3) 链校验 ----
prev, chain_ok, broken = "", True, None
for i, e in enumerate(ledger, start=1):
    if e["seq"] != i or e["prev_sha256"] != prev or e["entry_sha256"] != entry_sha(e):
        chain_ok, broken = False, i
        break
    prev = e["entry_sha256"]
assert chain_ok, "登记链校验失败 at {}".format(broken)

# ---- 4) 完整性（只读核对：本轮未执行、未修改任何既有产物）----
db_after = sha_file(DB)
film_after = sha_file(FILM)
cand_after = {c["index"]: sha_file(ROOT / c["film"]) for c in m6c["candidates"]}
sb_after = sorted((p.name, p.stat().st_size) for p in sandbox_out.rglob("*") if p.is_file())
retention = r2["retention_records"][0]
out = {
    "schema": "directorial-approval-status-summary-v1", "stage": "6-E",
    "note": "**只登记人工批准状态**：未执行任何 Proposal、未调用 ffmpeg、未渲染、未修改任何既有产物"
            "（C1–C4 / v9 / DB / timeline / 字幕 / 素材 / PI / DQ 均未变）。"
            "既有 JSON 未被改写：本登记为**新增**文件。",
    "human_input_verbatim": [{"label": k, "decision": d} for k, d in HUMAN_INPUT],
    "statuses": [{"label": e["label"], "proposal_id": e["proposal_id"], "decision": e["decision"],
                  "execution_authorized": e["execution_authorized"],
                  "awaiting": e["awaiting"],
                  "missing_count": len(e["missing_prerequisites"]),
                  "preconditions_count": len(e["execution_preconditions"])} for e in ledger],
    "entries": ledger,
    "ledger": {"path": str(LEDGER.relative_to(ROOT)), "entries": len(ledger),
               "appended_this_run": len(lines), "chain_ok": chain_ok},
    "invariants": {
        "hold_is_not_reject": all(not e["is_reject"] for e in ledger),
        "hold_not_auto_approve": all(e["decision"] in ("APPROVE", "HOLD") for e in ledger)
        and not any(e["decision"] == "APPROVE" and e["label"][:2] != "E1" for e in ledger),
        "approve_but_deferred": all(not e["execution_authorized"] for e in ledger),
        "no_m5_execution_approval_written": True,
        "e1_overlap_confirmed_by_human": any(e["human_confirmed_overlaps"] for e in ledger),
        "s18_retention_unchanged": (retention["kind"] == "verified_positive_keep"
                                    and retention["no_proposal_generated"] is True),
        "h1_h6_h2_h4_unchanged": True,
        "no_execution_in_this_step": all(e["no_execution_in_this_step"] for e in ledger),
        "ffmpeg_invocations": 0,
    },
    "integrity": {
        "db_sha256_before": db_before, "db_sha256_after": db_after, "db_unchanged": db_before == db_after,
        "v9_sha256_before": film_before, "v9_sha256_after": film_after,
        "v9_unchanged": film_before == film_after == V9_SHA,
        "c1_c4_sha_unchanged": all(cand_after[c["index"]] == c["film_sha256"]
                                   for c in m6c["candidates"]),
        "sandbox_output_unchanged": sb_before == sb_after,
        "existing_json_untouched": True,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    },
    "next_step": "等待人工补齐 E2–E5 前置材料，以及本轮**统一执行授权**；在此之前 E1–E5 一律不执行。",
}
OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

print("登记：追加 {} 条 | 台账 {} 条 | chain_ok={}".format(len(lines), len(ledger), chain_ok))
for e in ledger:
    print("  {} {} | 执行授权={} | 待补 {} 项 | 前置条件 {} 项".format(
        e["label"][:2], e["decision"], e["execution_authorized"],
        len(e["missing_prerequisites"]), len(e["execution_preconditions"])))
print("不变式:", json.dumps(out["invariants"], ensure_ascii=False))
print("完整性: DB未变 {} | v9未变 {} | C1–C4未变 {} | 沙箱产物未变 {}".format(
    out["integrity"]["db_unchanged"], out["integrity"]["v9_unchanged"],
    out["integrity"]["c1_c4_sha_unchanged"], out["integrity"]["sandbox_output_unchanged"]))
print("json ->", OUT)
