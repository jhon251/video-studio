# -*- coding: utf-8 -*-
"""6-E —— **E1 结案登记 + E2 执行前只读审查**（不执行、不渲染、不生成候选）。

人工指令：
  · E1 人工审查**全部通过** ⇒ 标记 `HUMAN_ACCEPT / CLOSED`；保持已完成状态、不重复执行、不得 promote。
  · 仅对 E2（`rp-f3f8548602fa`）做执行前**只读**校验；E3/E4/E5 保持 HOLD。
  · 校验：proposal / approval / material freeze / provenance / hash / locality / conflict +
    自制信息图与「surveyability / 可检视性」叙事的**语义一致性**；
    并确认 E2 **未复用**被明确禁止的 IMO 合影。

产出: logs/phase6e_e2_readiness.json（审查报告）
      登记链追加 2 条：`human-accept-closed-v1`（E1）、`e2-pre-execution-review-v1`
"""
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import execution as EX                       # noqa: E402
from video_studio.core import revision as core_revision             # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
MAT = ROOT / "docs" / "regression_2x" / "phase6e_materials"
DB = ROOT / "projects" / "video_studio.db"
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
V9_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"
R2 = LOGS / "phase6e_round2.json"
REG = LOGS / "phase6e_proposal_register_r2.jsonl"
BM = LOGS / "phase6e_execution_batch_manifest.json"
STATUS = LOGS / "phase6e_approval_status_r2.json"
LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
FREEZE = MAT / "phase6e_material_freeze_manifest.json"
PLAN = MAT / "phase6e_material_plan.json"
PROV = MAT / "phase6e_material_provenance.json"
E1_LEDGER = LOGS / "phase6e_e1_execution_ledger.jsonl"
E1_AP = LOGS / "phase6e_e1_approvals.jsonl"
M3 = LOGS / "phase6b_m3_proposals_v9.json"
M5_AP = LOGS / "phase6b_m4_approvals_v9.jsonl"
M5_EX = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"
M6C = LOGS / "phase6c_batch.json"
OUT = LOGS / "phase6e_e2_readiness.json"
IMO_ASSET = "asset_432cd85be6f1"
IMO_NAME = "Matemati"
REVIEW_AT = "2026-10-07T00:00:00Z"


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def entry_sha(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "entry_sha256"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


checks = []


def ck(name, ok, detail=None):
    checks.append({"check": name, "ok": bool(ok), "detail": detail})
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + json.dumps(detail, ensure_ascii=False)[:220]))
    return bool(ok)


# ================= A) E1 结案（HUMAN_ACCEPT / CLOSED）=================
r2 = json.loads(R2.read_text(encoding="utf-8"))
E1 = next(p for p in r2["proposals"] if p["label"].startswith("E1"))
E1_SHA = EX.proposal_sha256(E1)
e1_led = EX.load_ledger(E1_LEDGER)
e1_succ = [e for e in e1_led if e.get("state") == "SUCCEEDED"]
e1_cand = ROOT / e1_succ[0]["outputs"][0]["path"] if e1_succ else None
print("== A) E1 结案 ==")
ck("A1 E1 存在唯一 SUCCEEDED 执行记录（未重复执行）",
   len(e1_succ) == 1 and len([e for e in e1_led if e.get("state") == "SUCCEEDED"]) == 1,
   {"records": [e.get("state") for e in e1_led]})
ck("A2 E1 候选未 promote（promoted=False 且不在 projects/ 下）",
   e1_succ and e1_succ[0].get("promoted") is False
   and "phase6b_m4_sandbox" in e1_succ[0]["outputs"][0]["path"],
   e1_succ[0]["outputs"][0]["path"] if e1_succ else None)
ck("A3 E1 候选 sha256 仍与记录一致",
   e1_cand and e1_cand.is_file() and sha(e1_cand) == e1_succ[0]["outputs"][0]["sha256"],
   sha(e1_cand) if e1_cand and e1_cand.is_file() else None)
ck("A4 v9 母版未被 E1 改动", sha(FILM) == V9_SHA)
ck("A5 E1 批准台账仅 E1（无其它提案被批准）",
   all(e.get("proposal_id") == E1["proposal_id"] for e in EX.load_ledger(E1_AP)))

# ================= B) E2 执行前审查 =================
print("\n== B) E2 执行前只读审查 ==")
E2 = next(p for p in r2["proposals"] if p["label"].startswith("E2"))
E2_SHA = EX.proposal_sha256(E2)
bm = json.loads(BM.read_text(encoding="utf-8"))
bm_e2 = next(i for i in bm["items"] if i["label"].startswith("E2"))
freeze = json.loads(FREEZE.read_text(encoding="utf-8"))
fz_e2 = freeze["frozen_items"]["E2"]
plan = json.loads(PLAN.read_text(encoding="utf-8"))
plan_e2 = plan["items"]["E2"]
status = json.loads(STATUS.read_text(encoding="utf-8"))
st = {s["label"][:2]: s for s in status["statuses"]}

# B1 proposal / hash
ck("B1a E2 proposal_id 与批次清单一致",
   E2["proposal_id"] == bm_e2["proposal_id"] == "rp-f3f8548602fa", E2["proposal_id"])
ck("B1b E2 proposal_sha256 == 冻结值（proposal 未被改写）",
   E2_SHA == bm_e2["proposal_sha256"], {"live": E2_SHA, "frozen": bm_e2["proposal_sha256"]})
reg = core_revision.load_register(REG)
ck("B1c E2 在 append-only 登记表中且链完整",
   any(r["proposal_id"] == E2["proposal_id"] for r in reg)
   and core_revision.verify_register_chain(reg)["ok"],
   core_revision.verify_register_chain(reg))
ck("B1d E2 verify_proposal 通过（schema/局部化/执行状态）",
   core_revision.verify_proposal(E2) == [], core_revision.verify_proposal(E2))

# B2 approval
e2_ap_records = [e for e in EX.load_ledger(E1_AP) if e.get("proposal_id") == E2["proposal_id"]]
ck("B2a E2 人工决定 = HOLD（未被自动转为 APPROVE）", st["E2"]["decision"] == "HOLD",
   st["E2"]["decision"])
ck("B2b E2 **没有**批准记录（approvals 台账中无 E2）", e2_ap_records == [], e2_ap_records)
ck("B2c E3/E4/E5 仍为 HOLD 且无批准记录",
   all(st[k]["decision"] == "HOLD" for k in ("E3", "E4", "E5"))
   and not any(e.get("proposal_id") in
               [next(p for p in r2["proposals"] if p["label"].startswith(k))["proposal_id"]
                for k in ("E3", "E4", "E5")] for e in EX.load_ledger(E1_AP)))

# B3 material freeze
ck("B3a E2 已冻结且冻结模式 = 自制信息图（无外部素材需求）",
   fz_e2.get("mode") == "自制信息图"
   and all(m["kind"] == "self_created" for m in bm_e2["exact_material_source"]), fz_e2.get("mode"))
# B3a2：**冻结设计（自制） vs 注册 proposal（replace_asset 需真实素材）** 一致性（关键硬检查）
e2_action = E2["action"]
e2_needs_asset = (E2.get("material_requirement") or {}).get("needs_new_material")
e2_spec = (E2["proposed_change"]["params"] or {}).get("semantic_spec", "")
ck("B3a2 E2 注册 proposal 的 action/params 与『自制信息图』冻结设计一致",
   e2_action != "replace_asset" and not e2_needs_asset and "检索" not in e2_spec,
   {"action": e2_action, "needs_new_material": e2_needs_asset,
    "semantic_spec_head": e2_spec[:90],
    "freeze_mode": fz_e2.get("mode")})
ck("B3b E2 冻结规则含：允许 surveyability 术语 / 元数据保持当前版本 / 禁长引语",
   any("surveyability" in x for x in fz_e2.get("frozen_rules", []))
   and any("元数据" in x for x in fz_e2.get("frozen_rules", []))
   and any("长引语" in x for x in fz_e2.get("frozen_rules", [])), fz_e2.get("frozen_rules"))
ck("B3c E2 冻结来源绑定两组 DOI + 本片旁白",
   all(any(d in s for s in fz_e2.get("sources", []))
       for d in ("10.2307/2025976", "10.2307/2025806")), fz_e2.get("sources"))

# B4 provenance（自制 ⇒ 无外部文件；必须显式声明无 asset_id 且禁止素材已登记）
prov = json.loads(PROV.read_text(encoding="utf-8"))
e2_files = [f for f in prov["files"] if f["item"].startswith("e2")]
ck("B4a E2 无外部素材文件（自制）⇒ provenance 无 E2 文件条目", e2_files == [], e2_files)
ck("B4b E2 material_requirement.asset_id 为空（无虚构素材 id）",
   E2["material_requirement"]["asset_id"] is None, E2["material_requirement"])
ck("B4c E2 affected_scope.assets 为空", E2["affected_scope"]["assets"] == [])
ck("B4d E2 计划(A–F)完整",
   all(plan_e2.get(k) is not None for k in ("A_recommended", "C_self_made_spec",
                                            "D_license_risk", "E_human_check", "F_unknown")),
   {k: (plan_e2.get(k) is not None) for k in ("A_recommended", "C_self_made_spec",
                                              "D_license_risk", "E_human_check", "F_unknown")})

# B5 locality / conflict
loc = bm_e2["target"]
ck("B5a E2 局部化：1 镜 / 占比 0.0359 ≤ 上限（6 镜 / 0.30）",
   len(loc["scenes"]) == 1 and loc["window"] == [245.0, 300.0]
   and loc["share_of_film"] <= core_revision.DEFAULT_POLICY["max_share_of_film_per_proposal"],
   loc)
new_matrix = EX.detect_conflicts(r2["proposals"])
e2_pairs = [p for p in new_matrix["pairs"]
            if "E2" in (str(p.get("a", ""))[:2], str(p.get("b", ""))[:2])]
ck("B5b E2 与其他 6-E 提案无内部冲突", e2_pairs == [], e2_pairs)
executed_c = [p for p in json.loads(M3.read_text(encoding="utf-8"))["proposals"]
              if p["label"] in ("H3-batch1-split-longest", "H3-batch2-next-longest",
                                "H5-semantic-mismatch-replace", "H7-outro-card")]
cross = []
for q in executed_c:
    c = EX.pair_conflict(E2, q)
    if c:
        cross.append({"executed": q["label"], "kinds": c["kinds"],
                      "shared_scenes": c.get("shared_scenes"),
                      "requires_human_reapproval": EX.OVERLAP_POLICY["requires_human_reapproval"],
                      "human_confirmed": False})
ck("B5c E2↔已执行 H5 的跨批次重叠已声明（待人工确认，属已知边界）",
   [c for c in cross if c["executed"] == "H5-semantic-mismatch-replace"] != [], cross)
ck("B5d 当前 HOLD 状态下不存在执行阻断（未提交执行批次）",
   bm_e2["conflict_status"]["blocking_now"] is False)

# B6 禁用素材核查（IMO 合影）
imo_in_scope = [a for a in E2["affected_scope"]["assets"] if a == IMO_ASSET]
forb = E2["material_requirement"].get("forbidden_material") or []
params = E2["proposed_change"]["params"]
plan_txt = json.dumps(plan_e2, ensure_ascii=False)
ck("B6a E2 的 forbidden_material 明确列出 IMO 合影资产", 
   any(f.get("asset_id") == IMO_ASSET for f in forb), forb)
ck("B6b E2 的 semantic_spec 明确写明不得使用 IMO/竞赛合影",
   "不得" in params.get("semantic_spec", "") and "IMO" in params.get("semantic_spec", ""))
ck("B6c E2 未把 IMO 合影写入任何素材/来源字段（无复用）",
   imo_in_scope == [] and not any(f["item"].startswith("e2") for f in prov["files"]))
ck("B6d 冻结核查记录中 E2 的素材条目为 self_created（非图片引用）",
   all(m["kind"] == "self_created" for m in bm_e2["exact_material_source"]),
   [m["kind"] for m in bm_e2["exact_material_source"]])
ck("B6e 计划文本中不出现该 IMO 素材被当作可用素材（只作为禁止项出现）",
   plan_txt.count(IMO_ASSET) <= 1, plan_txt.count(IMO_ASSET))

# B8 执行器可用性（自制叠加层是否有真实执行器）
from video_studio.ops import execution as ops_exec                    # noqa: E402
ex_map = ops_exec.EXECUTORS
exec_info = {"available_actions": sorted(ex_map.keys()),
             "e2_action": e2_action,
             "e2_action_executor": getattr(ex_map.get(e2_action), "__name__", None),
             "add_visual_aid_executor": getattr(ex_map.get("add_visual_aid"), "__name__", None)}
ck("B8a `add_visual_aid` 已有**真实**执行器（不再是 _pending_asset 占位）",
   exec_info["add_visual_aid_executor"] not in (None, "_pending_asset"), exec_info)
ck("B8b E2 注册的 action 已更新为 add_visual_aid（受控更新尚未执行）",
   exec_info["e2_action"] == "add_visual_aid", exec_info)

# B7 语义一致性：E2 设计与 S05/S06/S07 旁白
con = sqlite3.connect("file:{}?mode=ro".format(DB.as_posix()), uri=True)
con.row_factory = sqlite3.Row
con.execute("PRAGMA query_only=ON")
arts = [dict(r) for r in con.execute(
    "select artifact_id, task_id, type, path from artifacts where project_id=? order by created_at",
    (PID,))]
con.close()
by_type = {}
for r in arts:
    by_type.setdefault(r["type"], []).append(r)


def payload(t, task=None):
    lst = by_type.get(t) or []
    x = next((y for y in lst if task and y["task_id"] == task), lst[-1] if lst else None)
    if not x:
        return {}
    p = Path(x["path"])
    return json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))


script = payload("script_output")
render = payload("render_output", FILM_TASK)
timeline = render.get("material_timeline") or []
segs = script.get("segments") or []
narr = {e["scene_id"]: str((segs[i].get("narration") if i < len(segs) else "") or "")
        for i, e in enumerate(timeline)}
narr05 = narr.get("S05", "")
narr06 = narr.get("S06", "")
narr07 = narr.get("S07", "")
joined = narr05 + " " + narr06 + " " + narr07
print("\n-- S05 旁白:", narr05[:240])
print("-- S06 旁白:", narr06[:200])
print("-- S07 旁白:", narr07[:200])

kw = {"Tymoczko": "Tymoczko" in joined, "surveyability/可检视": ("可检视" in joined
                                                                 or "surveyab" in joined.lower()),
      "逐字/原文核对": ("逐字" in joined or "原文" in joined),
      "Detlefsen": "Detlefsen" in joined or "德特勒夫森" in joined,
      "Luker": "Luker" in joined or "卢克" in joined,
      "1980": "1980" in joined, "引文/引语": ("引文" in joined or "引语" in joined),
      "转述": "转述" in joined}
ck("B7a S05 旁白与 E2 的『可检视性争论』主题直接对应（Tymoczko + 可检视/逐字核对）",
   kw["Tymoczko"] and (kw["surveyability/可检视"] or kw["逐字/原文核对"]), kw)
ck("B7b S06/S07 旁白支持 E2 的『两种立场 + 文献元数据』设计（Detlefsen/Luker/1980）",
   (kw["Detlefsen"] or kw["Luker"]) and kw["1980"], kw)
ck("B7c E2 设计的三个面板均绑定来源（P1 旁白 / P2 Crossref / P3 旁白）",
   all(any("旁白" in s or "DOI" in s or "Crossref" in s for s in p.get("fact_sources", []))
       for p in plan_e2["C_self_made_spec"]["panels"]),
   [p.get("fact_sources") for p in plan_e2["C_self_made_spec"]["panels"]])
ck("B7d E2 明确禁止引号引语（与旁白『只能用转述』一致）",
   any("引语" in x for x in plan_e2["C_self_made_spec"]["must_not"])
   and ("转述" in narr05 or "转述" in joined))
ck("B7e E2 只使用中文术语『可检视性』（未擅自引入未核到的英文原词）",
   any("surveyability" in x and "中文" in x for x in plan_e2["C_self_made_spec"]["must_not"]),
   plan_e2["C_self_made_spec"]["must_not"])
ck("B7f 文献元数据与 Crossref 现场复验一致（卷/期/页/年）",
   "76(2), p.57, Feb 1979" in json.dumps(plan_e2, ensure_ascii=False)
   and "77(12), p.803, Dec 1980" in json.dumps(plan_e2, ensure_ascii=False))

# ================= C) 结论 =================
hard_fail = [c for c in checks if not c["ok"]]
tech_ready = all(c["ok"] for c in checks if not c["check"].startswith(("B2a", "B5c")))
human_gaps = [c["check"] for c in checks if not c["ok"] and c["check"].startswith(("B2a", "B5c"))]
verdict = ("E2 READY_FOR_HUMAN_EXECUTION" if not hard_fail else "HOLD")
report = {
    "schema": "phase6e-e2-readiness-v1", "stage": "6-E", "review_at": REVIEW_AT,
    "note": "**只读审查**：未执行、未渲染、未生成候选、未调用 ffmpeg、未修改任何既有产物。",
    "E1_closure": {"state": "HUMAN_ACCEPT / CLOSED", "reviewed_by": "human:director(6-E)",
                   "review_at": REVIEW_AT, "promoted": False, "re_executed": False,
                   "candidate_sha256": (e1_succ[0]["outputs"][0]["sha256"] if e1_succ else None),
                   "proposal_id": E1["proposal_id"], "proposal_sha256": E1_SHA},
    "E2": {"proposal_id": E2["proposal_id"], "proposal_sha256": E2_SHA,
           "decision": st["E2"]["decision"], "execution_eligible": st["E2"]["decision"] == "APPROVE",
           "mode": fz_e2.get("mode"), "target": bm_e2["target"],
           "cross_batch_overlaps": cross,
           "exact_material_source": bm_e2["exact_material_source"],
           "semantic_alignment": kw,
           "narration_excerpts": {"S05": narr05[:400], "S06": narr06[:300], "S07": narr07[:300]},
           "forbidden_material_respected": {"imo_asset_id": IMO_ASSET,
                                            "declared_forbidden": any(f.get("asset_id") == IMO_ASSET
                                                                      for f in forb),
                                            "reused": False}},
    "checks": checks, "hard_failures": hard_fail,
    "technical_ready": tech_ready, "human_side_open_items": human_gaps,
    "verdict": verdict,
    "verdict_explanation": (
        "证据/素材/语义侧检查："
        + ("全部通过" if not hard_fail else "存在硬缺口 " + str([c["check"] for c in hard_fail]))
        + "。核心缺口 = **执行形态不一致**：E2 的冻结设计是『自制信息图』（无外部素材），"
          "但其注册 proposal 仍为 `replace_asset` 且 `needs_new_material=true`（要求检索真实素材）；"
          "而能落地自制叠加层的动作 `add_visual_aid` 当前**没有真实执行器**（映射到 `_pending_asset`）。"
          "⇒ 以现有 execution contract 执行 E2 **无法产出**冻结设计的信息图（会落入 "
          "`PENDING_HUMAN_ASSET` 或无执行器路径）。人工侧另有 ①E2 决定仍为 HOLD（不得自行转 APPROVE）、"
          "②E2↔已执行 H5 的跨批次重叠尚未人工确认。故本轮**不输出** READY 标记。"),
    "not_executed": {"E2": True, "E3": True, "E4": True, "E5": True, "ffmpeg_invocations": 0},
    "integrity": {"v9_sha256": sha(FILM), "v9_unchanged": sha(FILM) == V9_SHA,
                  "c1_c4_unchanged": all(sha(ROOT / c["film"]) == c["film_sha256"]
                                         for c in json.loads(M6C.read_text(encoding="utf-8")
                                                             )["candidates"]),
                  "m5_approvals_entries": len(EX.load_ledger(M5_AP)),
                  "m5_execution_entries": len(EX.load_ledger(M5_EX)),
                  "m5_untouched": (len(EX.load_ledger(M5_AP)) == 3
                                   and len(EX.load_ledger(M5_EX)) == 5)},
}
report["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

# ---- 登记（追加 2 条：E1 结案 + E2 审查）----
rows = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]


def add(rec_id_field, rec_id, rec):
    global rows
    if any(e.get(rec_id_field) == rec_id for e in rows):
        return 0
    rec[rec_id_field] = rec_id
    rec["seq"] = len(rows) + 1
    rec["prev_sha256"] = rows[-1]["entry_sha256"] if rows else ""
    rec["entry_sha256"] = entry_sha(rec)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    rows.append(rec)
    return 1


n1 = add("closure_id", "6E-E1-HUMAN-ACCEPT-v1",
         {"schema": "human-accept-closed-v1", "stage": "6-E", "closed_at": REVIEW_AT,
          "scope": "E1", "proposal_id": E1["proposal_id"], "proposal_sha256": E1_SHA,
          "candidate_sha256": (e1_succ[0]["outputs"][0]["sha256"] if e1_succ else None),
          "state": "HUMAN_ACCEPT / CLOSED", "promoted": False, "re_executed": False,
          "decided_by": "human:director(6-E)", "provenance": "人工审查 E1 执行结果全部通过",
          "read_only": True, "enforced": True, "advisory": False, "executes_changes": False})
n2 = add("review_id", "6E-E2-PRE-EXECUTION-REVIEW-v1",
         {"schema": "e2-pre-execution-review-v1", "stage": "6-E", "review_at": REVIEW_AT,
          "proposal_id": E2["proposal_id"], "proposal_sha256": E2_SHA,
          "decision": st["E2"]["decision"], "technical_ready": tech_ready,
          "verdict": verdict, "hard_failures": [c["check"] for c in hard_fail],
          "human_side_open_items": human_gaps, "executed": False, "ffmpeg_invocations": 0,
          "report": str(OUT.relative_to(ROOT)), "report_sha256": report["report_sha256"],
          "decided_by": "agent:read-only-review", "provenance": "只读执行前校验；未执行任何动作",
          "read_only": True, "enforced": False, "advisory": True, "executes_changes": False})
prev, chain_ok = "", True
for i, e in enumerate(rows, start=1):
    if e["seq"] != i or e["prev_sha256"] != prev or e["entry_sha256"] != entry_sha(e):
        chain_ok = False
        break
    prev = e["entry_sha256"]

print("\n== C) 结论 ==")
print("E1:", report["E1_closure"]["state"], "| promoted:", False, "| re_executed:", False)
print("E2 技术就绪:", tech_ready, "| 硬失败:", [c["check"] for c in hard_fail] or "无")
print("人工侧未闭合:", human_gaps or "无")
print("VERDICT:", verdict)
print("登记链: 追加 {} 条 | 共 {} 条 | chain_ok={}".format(n1 + n2, len(rows), chain_ok))
print("完整性:", json.dumps(report["integrity"], ensure_ascii=False))
print("report ->", OUT)
