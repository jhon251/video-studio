# -*- coding: utf-8 -*-
"""6-E —— **执行批次准备（execution batch preparation）**：只读复核 + 最终批次清单。

人工指令（逐字登记）：
  · **解除 proposal 执行授权锁定**，E1–E5 允许进入**执行批次准备**；
  · **暂时禁止实际执行**——"统一执行授权" ≠ "开始执行"；
  · E1–E5 必须严格使用 Material Freeze 中冻结的素材/来源/SHA256/文字规格/窗口；
  · 不得新增素材、不得自行改变视觉方案、不得改变 narration/captions/timeline。

本脚本**只读**复核并产出 1 个**新**文件 + 追加 1 条登记：
  1. proposal hash（重算 ↔ 登记值）
  2. approval / provenance（批准链 + 素材冻结清单自哈希）
  3. conflict（M5 口径：6-E 内部 + 跨批次）
  4. locality（≤6 镜 / 占比 ≤0.30）
  5. provenance（每个素材 URL/许可/SHA256/用途齐备 + 文件真实哈希）
产出: docs/regression_2x/logs/phase6e_execution_batch_manifest.json
      登记链追加 1 条 `execution-authorization-v1`
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import execution as EX            # noqa: E402
from video_studio.core import revision as core_revision  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
MAT = ROOT / "docs" / "regression_2x" / "phase6e_materials"
R2 = LOGS / "phase6e_round2.json"
REG = LOGS / "phase6e_proposal_register_r2.jsonl"
REVIEW = LOGS / "phase6e_review_ledger_r2.jsonl"
STATUS = LOGS / "phase6e_approval_status_r2.json"
LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
FREEZE = MAT / "phase6e_material_freeze_manifest.json"
PROV = MAT / "phase6e_material_provenance.json"
M6C = LOGS / "phase6c_batch.json"
M3 = LOGS / "phase6b_m3_proposals_v9.json"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
M5_AP = LOGS / "phase6b_m4_approvals_v9.jsonl"
M5_EX = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"
OUT = LOGS / "phase6e_execution_batch_manifest.json"
FONT = Path(r"C:\Windows\Fonts\msyh.ttc")
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
UNLOCK_AT = "2026-10-05T00:00:00Z"


def sha_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def n_lines(p: Path) -> int:
    return len([x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()])


def entry_sha(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


# ---------- 0) 只读基线 ----------
db_b, film_b = sha_file(DB), sha_file(FILM)
m5ap_b, m5ex_b, m5ap_n, m5ex_n = sha_file(M5_AP), sha_file(M5_EX), n_lines(M5_AP), n_lines(M5_EX)
sb_out = ROOT / "output" / "phase6b_m4_sandbox" / "p_96efdc03e1aa_6c" / "output"
sb_b = sorted((p.name, p.stat().st_size) for p in sb_out.rglob("*") if p.is_file())
m6c = json.loads(M6C.read_text(encoding="utf-8"))
cand_b = {c["index"]: sha_file(ROOT / c["film"]) for c in m6c["candidates"]}

# ---------- 1) proposal hash ----------
r2 = json.loads(R2.read_text(encoding="utf-8"))
registered = core_revision.load_register(REG)
reg_by_id = {r["proposal_id"]: r for r in registered}
props = {p["label"][:2]: p for p in r2["proposals"]}
hash_rows, hash_ok = [], True
for k in ("E1", "E2", "E3", "E4", "E5"):
    p = props[k]
    live = EX.proposal_sha256(p)
    rec = reg_by_id.get(p["proposal_id"], {})
    frozen_sha = (rec.get("proposal_sha256")
                  or (json.loads(FREEZE.read_text(encoding="utf-8"))["proposal_sha256"].get(k)))
    ok = live == frozen_sha
    hash_ok &= ok
    hash_rows.append({"label": k, "proposal_id": p["proposal_id"], "proposal_sha256": live,
                      "frozen_proposal_sha256": frozen_sha, "match": ok})
reg_chain = core_revision.verify_register_chain(registered)

# ---------- 2) approval / provenance / freeze ----------
from video_studio.core import human_review as HR                          # noqa: E402
review = HR.load_ledger(REVIEW)
review_chain = HR.verify_chain(review)
ledger = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
prev, ledger_ok = "", True
for i, e in enumerate(ledger, start=1):
    if e["seq"] != i or e["prev_sha256"] != prev or e["entry_sha256"] != entry_sha(e):
        ledger_ok = False
        break
    prev = e["entry_sha256"]
status = json.loads(STATUS.read_text(encoding="utf-8"))
approval = {s["label"][:2]: s for s in status["statuses"]}
freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
freeze_core = {k: v for k, v in freeze.items() if k != "manifest_sha256"}
freeze_self_ok = (hashlib.sha256(json.dumps(freeze_core, sort_keys=True, ensure_ascii=False,
                                            separators=(",", ":")).encode("utf-8")).hexdigest()
                  == freeze["manifest_sha256"])
mat_prov = json.loads(PROV.read_text(encoding="utf-8"))
prov_by_path = {f["local_path"]: f for f in mat_prov["files"]}
mat_check, prov_ok = [], True
for f in mat_prov["files"]:
    p = ROOT / f["local_path"]
    live = sha_file(p) if p.is_file() else None
    ok = (p.is_file() and live == f["sha256"] and bool(f.get("source_page_url"))
          and bool(f.get("license")) and bool(f.get("usage")))
    prov_ok &= ok
    mat_check.append({"local_path": f["local_path"], "item": f["item"], "license": f["license"],
                      "usage": f["usage"], "sha256": live, "sha256_match": live == f["sha256"],
                      "bound_url": bool(f.get("source_page_url")), "ok": ok})
font = ({"path": str(FONT), "exists": FONT.is_file(), "bytes": FONT.stat().st_size,
         "sha256": sha_file(FONT)} if FONT.is_file()
        else {"path": str(FONT), "exists": False})

# ---------- 3) conflict（M5 口径）----------
new_matrix = EX.detect_conflicts(r2["proposals"])
executed_c = [p for p in json.loads(M3.read_text(encoding="utf-8"))["proposals"]
              if p["label"] in ("H3-batch1-split-longest", "H3-batch2-next-longest",
                                "H5-semantic-mismatch-replace", "H7-outro-card")]
cross = []
for p in r2["proposals"]:
    for q in executed_c:
        c = EX.pair_conflict(p, q)
        if c:
            cross.append({"new": p["label"].split("-")[0], "executed": q["label"],
                          "kinds": c["kinds"], "shared_scenes": c.get("shared_scenes"),
                          "human_confirmation": ("已确认（人工明确）"
                                                 if p["label"].startswith("E1") else "未确认（待人工）"),
                          "blocking_now": False,
                          "note": "跨批次重叠属 M5 已声明边界（门禁按批次判定）；本轮只做批次准备，"
                                  "不提交执行批次 ⇒ 当前无阻断"})

# ---------- 4) locality ----------
locality = [{"label": k, "scenes": props[k]["affected_scope"]["scenes"],
             "scene_count": len(props[k]["affected_scope"]["scenes"]),
             "window": props[k]["affected_scope"]["window"],
             "share_of_film": props[k]["affected_scope"]["share_of_film"],
             "within_max_scenes": len(props[k]["affected_scope"]["scenes"])
             <= core_revision.DEFAULT_POLICY["max_scenes_per_proposal"],
             "within_max_share": props[k]["affected_scope"]["share_of_film"]
             <= core_revision.DEFAULT_POLICY["max_share_of_film_per_proposal"]} for k in
            ("E1", "E2", "E3", "E4", "E5")]
locality_ok = all(x["within_max_scenes"] and x["within_max_share"] for x in locality)

# ---------- 5) 最终批次清单 ----------
EXEC_ORDER = ["E2", "E4", "E3", "E5", "E1"]          # 按窗口升序（互不重叠 ⇒ 顺序不影响结果）
MATERIALS = {
    "E1": [{"kind": "font", **font, "role": "片尾卡 CJK 字形（fail-closed 前置检查）"}],
    "E2": [{"kind": "self_created", "role": "自制信息图（无外部素材）",
            "sources": ["DOI 10.2307/2025976", "DOI 10.2307/2025806",
                        "本片 S05/S06/S07 旁白"]}],
    "E3": [dict({"kind": "source_code",
                 "role": "逐字引用（第 62–66 行）+ 许可署名"}, **mx) for mx in
           [m for m in mat_check if m["item"] == "e3_lean"]],
    "E4": [dict({"kind": "image", "role": "PD 素材（Public domain，无需署名）"}, **mx) for mx in
           [m for m in mat_check if m["item"] == "e4_kepler"]],
    "E5": [{"kind": "self_created", "role": "自制时间线 + 主张状态卡（无第三方图片）",
            "sources": ["DOI 10.1038/s41586-023-06747-5",
                        "https://deepmind.google/blog/ai-solves-imo-problems-at-silver-medal-level/",
                        "Wikipedia 2024 in artificial intelligence（定性佐证）",
                        "本片 S16 旁白"]}],
}
E3_COMMIT = freeze["frozen_items"]["E3"]["commit_binding"]["commit_sha"]
EXPECTED = {
    "E1": "片尾卡 CJK 文字由豆腐块改为可读中文（显式字体文件）；时长/音轨/字幕守恒",
    "E2": "aS05 由 IMO 合影改为与『引信可检视性争论』直接相关的自制信息图（替换语义无关素材）",
    "E3": "aS11 由 IMO 合影改为『自制版式 + 真实 mathlib4 逐字引用 + 示意图』",
    "E4": "480–690s 长镜叠加自制事实卡（4 信息槽，含 P3 反转双条）+ 复用 PD 素材与 PD 图解",
    "E5": "850–1000s 叠加自制时间线 + 主张状态卡（含 28/42、银牌档次、金牌线 29；禁止奖牌表述）",
}
items = []
for i, k in enumerate(EXEC_ORDER, start=1):
    p, a = props[k], approval[k]
    items.append({
        "execution_order": i,
        "label": p["label"],
        "proposal_id": p["proposal_id"],
        "proposal_sha256": EX.proposal_sha256(p),
        "approval_provenance": {
            "human_decision": a["decision"],
            "execution_authorized": True,                    # 授权已解除（允许批次准备）
            "execution_eligible": a["decision"] == "APPROVE",  # HOLD 不自动转 APPROVE
            "decided_by": "human:director(6-E approval round)",
            "awaiting": a["awaiting"],
            "approval_ledger_ref": {"path": str(LEDGER.relative_to(ROOT)),
                                    "status_seq": next((e["seq"] for e in ledger
                                                        if e.get("label", "").startswith(k)), None)},
            "material_freeze_manifest": str(FREEZE.relative_to(ROOT)),
            "material_freeze_manifest_sha256": freeze["manifest_sha256"],
            "review_ledger_entry": next((x["entry_sha256"] for x in review
                                         if x["scene_id"] == p["affected_scope"]["scenes"][0]), None),
        },
        "target": {"scenes": p["affected_scope"]["scenes"],
                   "window": p["affected_scope"]["window"],
                   "share_of_film": p["affected_scope"]["share_of_film"]},
        "exact_material_source": MATERIALS[k],
        "frozen_text_spec": freeze["frozen_items"][k].get("frozen_rules"),
        "expected_change": EXPECTED[k],
        "conflict_status": {
            "internal_within_batch": [c for c in new_matrix["pairs"]
                                      if k in (c.get("a", "")[:2], c.get("b", "")[:2])] or [],
            "cross_batch": [c for c in cross if c["new"] == k],
            "blocking_now": False,
        },
        "rollback_reference_mother": {
            "ultimate_reference": {"path": str(FILM.relative_to(ROOT)), "sha256": V9_SHA,
                                   "note": "v9 母版；任何回滚以此为最终基准（本阶段未被修改）"},
            "current_most_complete": {"path": m6c["candidates"][3]["film"],
                                      "sha256": m6c["candidates"][3]["film_sha256"],
                                      "note": "6-C C4（含 outro + 两次切分 + H5 换材）"},
            "rollback_procedure": "候选片从不 promote ⇒ 回滚 = 丢弃本步产物；v9 与 C1–C4 始终不被改写",
        },
    })

batch_core = {
    "schema": "phase6e-execution-batch-manifest-v1", "stage": "6-E",
    "state": "EXECUTION-AUTHORIZED / PREPARED / NOT-STARTED",
    "note": "**批次准备清单**：授权已解除，但**未开始执行**——"
            "『统一执行授权』≠『开始执行』。本文件生成过程只读，未调用 ffmpeg、未渲染、"
            "未修改任何既有产物。",
    "written_authorization": {
        "unlock": "解除 proposal 执行授权锁定（E1–E5 允许进入执行批次准备）",
        "explicit_start_command_received": False,
        "execution_started": False,
        "unlock_at": UNLOCK_AT,
        "constraints": ["严格使用 Material Freeze 冻结的素材/来源/SHA256/文字规格/窗口",
                        "不得新增素材", "不得自行改变视觉方案",
                        "不得改变 narration/captions/timeline",
                        "禁止 ffmpeg / 渲染 / 修改 v9·C1–C4·DB·timeline·字幕·素材"],
    },
    "checks": {
        "proposal_hash": {"ok": hash_ok, "rows": hash_rows,
                          "register_chain": reg_chain},
        "approval": {"ok": ledger_ok and review_chain["ok"],
                     "approval_ledger_entries": len(ledger), "approval_ledger_chain_ok": ledger_ok,
                     "review_entries": len(review), "review_chain_ok": review_chain["ok"],
                     "statuses": {k: approval[k]["decision"] for k in approval}},
        "material_freeze": {"ok": freeze_self_ok, "manifest_sha256": freeze["manifest_sha256"],
                            "self_hash_ok": freeze_self_ok, "materials": len(mat_check)},
        "provenance": {"ok": prov_ok, "rows": mat_check},
        "conflict": {"ok": new_matrix["conflict_pair_count"] == 0,
                     "internal_pairs": new_matrix["conflict_pair_count"],
                     "cross_batch": cross},
        "locality": {"ok": locality_ok, "rows": locality},
    },
    "execution_order": EXEC_ORDER,
    "execution_order_rationale": "5 个窗口互不重叠（内部冲突 0）⇒ 顺序不影响结果；"
                                 "按窗口升序排列，便于逐段核对。",
    "executable_subset_if_start_now": [k for k in EXEC_ORDER if approval[k]["decision"] == "APPROVE"],
    "non_executable_subset": [k for k in EXEC_ORDER if approval[k]["decision"] != "APPROVE"],
    "items": items,
    "hard_problems": ([] if (hash_ok and ledger_ok and freeze_self_ok and prov_ok
                             and locality_ok and new_matrix["conflict_pair_count"] == 0)
                      else ["校验未全通过"]),
    "rollback": {
        "no_promotion": True,
        "v9_untouched": True,
        "c1_c4_untouched": True,
        "procedure": "任一步失败 ⇒ 丢弃该步产物并回报；v9 / C1–C4 不被改写（无 promote 路径）",
    },
}
batch_core["manifest_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in batch_core.items() if k != "manifest_sha256"},
               sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
).hexdigest()
OUT.write_text(json.dumps(batch_core, ensure_ascii=False, indent=1), encoding="utf-8")

# ---------- 6) 登记链追加（执行授权解锁；同一解锁幂等）----------
UNLOCK_ID = "6E-EXECUTION-AUTHORIZATION-v1"
appended = 0
if not any(e.get("unlock_id") == UNLOCK_ID for e in ledger):
    rec = {
        "schema": "execution-authorization-v1", "stage": "6-E", "unlock_id": UNLOCK_ID,
        "unlock_at": UNLOCK_AT,
        "state": "EXECUTION-AUTHORIZED / PREPARED / NOT-STARTED",
        "human_instruction": "解除 proposal 执行授权锁定；E1–E5 允许进入执行批次准备；"
                             "**暂时禁止实际执行**（统一执行授权 ≠ 开始执行）",
        "batch_manifest": str(OUT.relative_to(ROOT)),
        "batch_manifest_sha256": batch_core["manifest_sha256"],
        "execution_order": EXEC_ORDER,
        "executable_subset": batch_core["executable_subset_if_start_now"],
        "non_executable_subset": batch_core["non_executable_subset"],
        "proposal_sha256": {r["label"]: r["proposal_sha256"] for r in hash_rows},
        "execution_started": False, "explicit_start_command_received": False,
        "ffmpeg_invocations": 0, "executed_anything": False,
        "decided_by": "human:director(6-E execution authorization)",
        "provenance": "人工解除执行授权锁定；批次清单已生成，等待明确的『开始执行』指令",
        "read_only": True, "enforced": False, "advisory": True, "executes_changes": False,
    }
    rec["seq"] = len(ledger) + 1
    rec["prev_sha256"] = ledger[-1]["entry_sha256"] if ledger else ""
    rec["entry_sha256"] = entry_sha(rec)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    appended = 1
ledger2 = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
# 修正记录（自查发现：首版批次清单中 E4 的 exact_material_source 因路径分隔符过滤失效而为空）
FIX_ID = "6E-EXECUTION-AUTHORIZATION-v1-R1"
fixed = 0
if not any(e.get("unlock_id") == FIX_ID for e in ledger2):
    frec = {
        "schema": "execution-authorization-correction-v1", "stage": "6-E", "unlock_id": FIX_ID,
        "corrects": UNLOCK_ID,
        "defect": "首版 phase6e_execution_batch_manifest.json 中 E4 的 exact_material_source 为空数组"
                  "（过滤条件使用正斜杠前缀，而 Windows 实际路径为反斜杠 ⇒ 未匹配到 4 个 PD 素材）",
        "fix": "改为按 provenance 记录的 item 字段（e4_kepler/e3_lean）分组；批次清单已重新生成",
        "new_batch_manifest_sha256": batch_core["manifest_sha256"],
        "batch_manifest": str(OUT.relative_to(ROOT)),
        "execution_started": False, "ffmpeg_invocations": 0, "executed_anything": False,
        "decided_by": "agent:self-check(6-E batch preparation)",
        "provenance": "只读复核对清单做自检时发现并修正；未涉及任何执行",
        "read_only": True, "enforced": False, "advisory": True, "executes_changes": False,
    }
    frec["seq"] = len(ledger2) + 1
    frec["prev_sha256"] = ledger2[-1]["entry_sha256"] if ledger2 else ""
    frec["entry_sha256"] = entry_sha(frec)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(frec, ensure_ascii=False) + "\n")
    fixed = 1
ledger2 = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
prev, chain2 = "", True
for i, e in enumerate(ledger2, start=1):
    if e["seq"] != i or e["prev_sha256"] != prev or e["entry_sha256"] != entry_sha(e):
        chain2 = False
        break
    prev = e["entry_sha256"]

# ---------- 7) 只读完整性 ----------
db_a, film_a = sha_file(DB), sha_file(FILM)
m5ap_a, m5ex_a = sha_file(M5_AP), sha_file(M5_EX)
cand_a = {c["index"]: sha_file(ROOT / c["film"]) for c in m6c["candidates"]}
sb_a = sorted((p.name, p.stat().st_size) for p in sb_out.rglob("*") if p.is_file())
integrity = {"db_unchanged": db_b == db_a, "v9_unchanged": film_b == film_a == V9_SHA,
             "c1_c4_unchanged": all(cand_a[c["index"]] == c["film_sha256"]
                                    for c in m6c["candidates"]),
             "sandbox_output_unchanged": sb_b == sb_a,
             "m5_approvals_ledger_untouched": m5ap_b == m5ap_a and m5ap_n == n_lines(M5_AP),
             "m5_execution_ledger_untouched": m5ex_b == m5ex_a and m5ex_n == n_lines(M5_EX),
             "m5_approvals_entries": m5ap_n, "m5_execution_entries": m5ex_n,
             "ffmpeg_invocations": 0, "executed_anything": False, "proposals_executed": 0}
batch_core["integrity"] = integrity
OUT.write_text(json.dumps(batch_core, ensure_ascii=False, indent=1), encoding="utf-8")

print("批次清单:", OUT.name, "| manifest_sha256", batch_core["manifest_sha256"][:16])
print("校验: proposal_hash {} | approval {} | freeze {} | provenance {} | conflict {} | locality {}".format(
    hash_ok, ledger_ok and review_chain["ok"], freeze_self_ok, prov_ok,
    new_matrix["conflict_pair_count"] == 0, locality_ok))
print("执行顺序:", " -> ".join(EXEC_ORDER))
print("可执行子集(APPROVE):", batch_core["executable_subset_if_start_now"],
      "| 暂不可执行(HOLD):", batch_core["non_executable_subset"])
print("硬问题:", batch_core["hard_problems"] or "无")
print("登记链: 追加 {} | 修正记录 {} | 共 {} 条 | chain_ok={}".format(
    appended, fixed, len(ledger2), chain2))
print("完整性: DB {} | v9 {} | C1–C4 {} | 沙箱 {} | M5台账未动 {} | ffmpeg {} 次".format(
    integrity["db_unchanged"], integrity["v9_unchanged"], integrity["c1_c4_unchanged"],
    integrity["sandbox_output_unchanged"],
    integrity["m5_approvals_ledger_untouched"] and integrity["m5_execution_ledger_untouched"],
    integrity["ffmpeg_invocations"]))
