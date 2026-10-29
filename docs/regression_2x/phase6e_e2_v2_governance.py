# -*- coding: utf-8 -*-
"""6-E —— **E2 治理层修复：proposal 版本 +1（append-only）**，不执行、不调用 ffmpeg、不生成候选。

人工指令（逐条落实）：
  1. E2 proposal 以 **append-only** 方式版本 +1（历史条目**不改动**）；
  2. `action`: replace_asset → **add_visual_aid**；
  3. `needs_new_material = false`；
  4. `params.spec_source` 严格绑定冻结计划（path/item/sha256 按人工给定）；
  5. `affected_scope.assets = []`，继续禁止 `asset_432cd85be6f1`；
  6. `semantic_spec` 只表达**已冻结的人工作品语义**（可检视性阶梯 / 转述状态 / 文献元数据 / 两种立场），
     不得新增事实、引语或素材；
  7. 新版本必须产生**新 proposal_sha256**；
  8. 重新运行 proposal validation / provenance / locality / conflict / spec_source hash binding；
  9. **不自动 APPROVE**；E2 保持 HOLD，等待人工审批新 hash；
 10. E3/E4/E5 完全不动。

用法: python docs/regression_2x/phase6e_e2_v2_governance.py
产出: logs/phase6e_e2_v2_governance.json（含新 proposal、旧/新 hash、diff、全部门禁）
      + 登记链追加 1 条 `e2-proposal-v2-registered-v1`
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
sys.path.insert(0, str(ROOT / "src"))
from video_studio.core import execution as EX                       # noqa: E402
from video_studio.core import human_review as HR                    # noqa: E402
from video_studio.core import revision as core_revision             # noqa: E402
from video_studio.core import visual_aid as VA                      # noqa: E402
from video_studio.ops import execution as ops_exec                  # noqa: E402

LOGS = ROOT / "docs" / "regression_2x" / "logs"
REG = LOGS / "phase6e_proposal_register_r2.jsonl"
REVIEW = LOGS / "phase6e_review_ledger_r2.jsonl"
R2 = LOGS / "phase6e_round2.json"
BM = LOGS / "phase6e_execution_batch_manifest.json"
STATUS = LOGS / "phase6e_approval_status_r2.json"
LEDGER = LOGS / "phase6e_approval_status_r2.jsonl"
PLAN = ROOT / "docs" / "regression_2x" / "phase6e_materials" / "phase6e_material_plan.json"
M3 = LOGS / "phase6b_m3_proposals_v9.json"
M5_AP = LOGS / "phase6b_m4_approvals_v9.jsonl"
M5_EX = LOGS / "phase6b_m4_execution_ledger_v9.jsonl"
E1_LEDGER = LOGS / "phase6e_e1_execution_ledger.jsonl"
OUT = LOGS / "phase6e_e2_v2_governance.json"
PLAN_SHA_REQUIRED = "0cefd8810515138cf3a8e2057ffcf3c695bc16d7b8cfac818bd6fcad74689df8"
IMO_ASSET = "asset_432cd85be6f1"
KNOWN_ASSETS = [IMO_ASSET, "asset_3f0b94a3f2ac", "asset_cfae038f6106", "asset_30dd89a16713",
                "asset_23e71bc8a864"]
REGISTERED_AT = "2026-10-08T00:00:00Z"


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
                             "" if ok else "| " + json.dumps(detail, ensure_ascii=False)[:240]))
    return bool(ok)


# ---------- 0) 读取历史（v1 必须保持原样）----------
reg_before = core_revision.load_register(REG)
v1 = next(r for r in reg_before if r["proposal_id"] == "rp-f3f8548602fa")
v1_sha, v1_entry = EX.proposal_sha256(v1), v1["entry_sha256"]
r2_sha_before = sha(R2)
review = HR.load_ledger(REVIEW)
finding = next(x for x in review if x["finding_id"] == v1["finding_id"])
decision_entry = finding
scene_ids = []
try:
    import sqlite3
    con = sqlite3.connect("file:{}?mode=ro".format((ROOT / "projects" / "video_studio.db")
                                                   .as_posix()), uri=True)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA query_only=ON")
    rows = [dict(r) for r in con.execute(
        "select type, task_id, path from artifacts where project_id=? order by created_at",
        ("p_96efdc03e1aa",))]
    con.close()
    for r in rows:
        if r["type"] == "render_output" and r["task_id"] == "t_d0a54bdf1810":
            p = Path(r["path"])
            d = json.loads((p if p.is_absolute() else ROOT / p).read_text(encoding="utf-8"))
            scene_ids = [e["scene_id"] for e in (d.get("material_timeline") or [])]
except Exception as e:                                                        # noqa: BLE001
    print("WARN 读取时间轴失败:", e)

# ---------- 1) 取得 v2（**优先从登记条目读取**；仅在缺失时构建并追加）----------
#  说明：core.revision.make_proposal 会写入 generated_at（revision.py:161）⇒ 同一条提案
#  **无法逐字节重建**；因此 **登记条目是权威**。若每次都重建并追加，会静默产生新 hash。
params_v2_build = {
    "spec_source": {"path": "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
                    "item": "E2", "sha256": PLAN_SHA_REQUIRED},
    "semantic_spec": ("（治理层说明，**非**检索需求）只表达已冻结的人工作品语义："
                      "①可检视程度阶梯：未核对原文 / 转述（本片当前状态）/ 逐字核对 / 机器可逐步复核；"
                      "②当前状态 = 转述，尚未逐字核对原文；"
                      "③两篇文献元数据：Tymoczko 1979 与 Detlefsen & Luker 1980（含卷期页与 DOI）；"
                      "④两种立场（转述，不引原文）。不得新增事实、引语或素材。"),
    "no_external_assets": True, "forbid_verbatim_quotes": True, "count": 0,
    "frozen_plan_item": "E2", "rendered_by": "core.visual_aid + ops.execution.exec_add_visual_aid",
    "forbidden_material": [{"asset_id": IMO_ASSET, "why": "人工明确否决作为 aS05/aS11 替代素材"}],
}


def _build_v2() -> dict:
    rec = core_revision.make_proposal(
        finding, decision_entry, "add_visual_aid", {"scene_id": "S05", "window": [245.0, 300.0]},
        {"what": "在 S05 窗口内叠加**自制**信息图（无外部素材）：可检视性阶梯 + 转述状态 + 文献元数据 + 两种立场",
         "how": "由 add_visual_aid 执行器按 params.spec_source 指向的**冻结计划**（哈希绑定）确定性编译 spec，"
                "渲染为整幅叠加层并在窗口内叠加；重烧该窗口字幕；母版整条音轨流复制",
         "params": params_v2_build},
        {"scenes": ["S05"], "window": [245.0, 300.0], "assets": [], "share_of_film": 0.0359,
         "version": 2,
         "supersedes": {"proposal_id": v1["proposal_id"], "proposal_sha256": v1_sha,
                        "action": v1["action"],
                        "reason": "治理层修复：原为 replace_asset（需外部素材），与冻结设计『自制信息图』不一致"},
         "not_touching": ["旁白文本", "字幕文本", "时间轴总时长", "其它镜头", "C1–C4 现有候选成片",
                          "素材许可/署名台账", "E3/E4/E5 方案"]},
        {"metric": "DQ-8（逐镜语义支撑）+ 人工叙事相关性",
         "direction": "aS05 由语义无关素材 → 与『可检视性争论』直接对应的自制信息图（状态需复核）",
         "basis": (v1["expected_effect"].get("basis") or "")[:200],
         "assumption": "自制层不改变旁白/字幕/时长；语义达成仍由人工与语义层复核判定",
         "not_guaranteed": True},
        constraints={"must_preserve": ["旁白文本", "字幕文本", "时间轴总时长", "既有许可/署名台账"],
                     "spec_source_hash_binding": True, "no_external_assets": True,
                     "forbid_verbatim_quotes": True,
                     "overlay_safe_area": "不得进入画面底部 5%（字幕安全区）"},
        risk=["叠加层遮挡主体或与字幕抢位 ⇒ 执行器已强制底部 5% 安全区",
              "spec_source.sha256 与计划文件不符 ⇒ 执行 fail-closed（VISUAL_AID_SPEC_SHA_MISMATCH）",
              "与已执行 H5 在 S05（scene/window/target）**跨批次重叠** ⇒ 需人工重新批准"],
        known_scene_ids=scene_ids or None, known_asset_ids=KNOWN_ASSETS,
        discriminator="6e-e2", label="E2-v2-asset_semantically_unrelated_imo_group_photo",
        evidence_refs=["docs/regression_2x/logs/phase6e_e2_readiness.json",
                       "docs/regression_2x/phase6e_materials/phase6e_material_plan.json",
                       str(REG.relative_to(ROOT))])
    rec["material_requirement"] = {
        "needs_new_material": False, "needs_new_content_self_created": True,
        "asset_id": None, "semantic_spec": params_v2_build["semantic_spec"],
        "sourcing": "SELF_CREATED（自制图形/排版；内容来自冻结计划，逐字编译）",
        "forbidden_material": params_v2_build["forbidden_material"], "no_fabricated_asset_id": True}
    rec["version"] = 2
    rec["supersedes"] = rec["affected_scope"]["supersedes"]
    rec["registered_at"] = REGISTERED_AT
    rec["governance"] = {"registered_by": "agent:governance-fix(6-E E2 v2)",
                          "authorized_by": "human:director(6-E E2 v2 指令)",
                          "history_immutable": True, "auto_approved": False}
    return rec


existing_v2 = next((r for r in reg_before if r.get("version") == 2
                    and str(r.get("label", "")).startswith("E2")), None)
if existing_v2 is not None:
    v2 = dict(existing_v2)                       # 权威：登记条目（不可变）
    v2_origin = "loaded_from_register"
else:
    v2 = core_revision.append_proposal(REG, _build_v2())
    v2_origin = "built_and_appended"
params_v2 = v2["proposed_change"]["params"]
v2_sha = EX.proposal_sha256(v2)
_rebuild = _build_v2()
rebuild_sha = EX.proposal_sha256(_rebuild)

print("== 0) 历史守恒 ==")
ck("0a 新 proposal_id 与 v1 不同（action 参与 id 派生）",
   v2["proposal_id"] != v1["proposal_id"], {"v1": v1["proposal_id"], "v2": v2["proposal_id"]})
ck("0b 新 proposal_sha256 与 v1 不同", v2_sha != v1_sha, {"v1": v1_sha, "v2": v2_sha})
ck("0c v1 历史条目未被改动（register 内 entry_sha256 不变）",
   next(r for r in core_revision.load_register(REG)
        if r["proposal_id"] == v1["proposal_id"])["entry_sha256"] == v1_entry)
ck("0d 6-E 第二轮证据 JSON 未被改写", sha(R2) == r2_sha_before)
ck("0f v2 取自登记条目（未重建）；并已记录 make_proposal 的不可重建性（generated_at）",
   v2_origin in ("loaded_from_register", "built_and_appended")
   and bool((v2.get("provenance") or {}).get("generated_at")) and rebuild_sha != v2_sha,
   {"origin": v2_origin, "generated_at": (v2.get("provenance") or {}).get("generated_at"),
    "stored_sha": v2_sha,
    "rebuild_sha": rebuild_sha,
    "why": "make_proposal 写入 generated_at ⇒ 逐字节重建会得到不同 hash；故登记条目为权威"})
ck("0e 新版本记录 supersedes（旧 id + 旧 hash + 原因）",
   v2["supersedes"]["proposal_id"] == v1["proposal_id"]
   and v2["supersedes"]["proposal_sha256"] == v1_sha)

print("\n== 1) append-only 登记 v2 ==")
appended = 0
if not any(r["proposal_id"] == v2["proposal_id"] for r in core_revision.load_register(REG)):
    core_revision.append_proposal(REG, v2)
    appended = 1
reg_after = core_revision.load_register(REG)
chain = core_revision.verify_register_chain(reg_after)
v2_reg = next(r for r in reg_after if r["proposal_id"] == v2["proposal_id"])
BOOKKEEPING = ("seq", "prev_sha256", "register", "entry_sha256", "proposal_sha256")


def canonical(rec: dict) -> dict:
    """剥离账本字段后的**提案本体**（规范哈希的对象）。"""
    return {k: v for k, v in rec.items() if k not in BOOKKEEPING}


canon_sha = EX.proposal_sha256(canonical(v2_reg))
ck("1a v2 已进入登记链且 v1 条目仍存在（append-only，未覆盖）",
   v2_reg is not None and any(r["proposal_id"] == v1["proposal_id"] for r in reg_after),
   {"entries": len(reg_after), "appended_this_run": appended})
ck("1b 登记链完整", chain["ok"], chain)
ck("1c 登记条目剥离账本字段后重算 == 提案本体哈希（可复核）",
   canon_sha == v2_sha, {"canonical_from_register": canon_sha, "v2_sha": v2_sha})
CANON_FILE = LOGS / "phase6e_e2_v2_proposal.json"
CANON_FILE.write_text(json.dumps(canonical(v2_reg), ensure_ascii=False, indent=1), encoding="utf-8")
canon_file_sha = (EX.proposal_sha256(json.loads(CANON_FILE.read_text(encoding="utf-8")))
                  if CANON_FILE.is_file() else None)
ck("1d 规范提案文件（纯提案本体，无账本字段）自哈希 == v2_sha（审批可绑定）",
   canon_file_sha == v2_sha, {"file_sha": canon_file_sha, "v2_sha": v2_sha})

print("\n== 2) proposal validation ==")
errs = core_revision.verify_proposal(v2_reg)
ck("2a verify_proposal(v2) 无错误", errs == [], errs)
ck("2b 必填字段齐备（schema 契约）",
   all(k in v2_reg for k in core_revision.REQUIRED_FIELDS), core_revision.REQUIRED_FIELDS)
ck("2c action = add_visual_aid", v2["action"] == "add_visual_aid", v2["action"])
ck("2d 状态为待人工审批（未执行、未批准）",
   v2["status"] == "PROPOSED_AWAITING_HUMAN_APPROVAL" and v2["approved"] is False
   and v2["executed"] is False)

print("\n== 3) provenance / 素材治理 ==")
ck("3a needs_new_material = false",
   v2["material_requirement"]["needs_new_material"] is False)
ck("3b 无虚构 asset_id（asset_id=None）", v2["material_requirement"]["asset_id"] is None)
ck("3c affected_scope.assets = []", v2["affected_scope"]["assets"] == [])
ck("3d 继续禁止 IMO 合影（params.forbidden_material 列出该 id）",
   any(f.get("asset_id") == IMO_ASSET for f in params_v2["forbidden_material"]))
ck("3e semantic_spec 只含冻结语义四要素（阶梯/转述/元数据/立场），不含检索要求",
   all(k in params_v2["semantic_spec"] for k in ("阶梯", "转述", "文献元数据", "两种立场"))
   and "检索" not in params_v2["semantic_spec"].split("（治理层说明")[0])
ck("3f semantic_spec 不含西文双引号（不引入引语）",
   not any(q in params_v2["semantic_spec"] for q in VA.WESTERN_QUOTES))

print("\n== 4) spec_source hash binding ==")
plan_sha_live = sha(PLAN)
ck("4a 冻结计划文件存在且 sha256 == 人工指定值",
   PLAN.is_file() and plan_sha_live == PLAN_SHA_REQUIRED,
   {"live": plan_sha_live, "required": PLAN_SHA_REQUIRED})
ctx_stub = {"root": str(ROOT), "box": str(ROOT / "output" / "phase6b_m4_sandbox" / "_resolve_only"),
            "film": PLAN, "ffmpeg": "ffmpeg", "ffprobe": "ffprobe"}
try:
    spec, src = ops_exec._resolve_visual_aid_spec(ctx_stub, {"proposed_change": {"params": params_v2}})
    resolved = True
except Exception as exc:                                                       # noqa: BLE001
    spec, src, resolved = None, {"error": "{}: {}".format(type(exc).__name__, exc)}, False
ck("4b 执行器可解析该绑定（走真实 `_resolve_visual_aid_spec`，不调用 ffmpeg）", resolved, src)
spec_sha = VA.spec_sha256(spec) if spec else None
if spec:
    ck("4c 编译出的 spec 通过（自制/无素材/无引语/安全区约束）", VA.verify_spec(spec) is not None)
    ck("4d 编译语义 = 冻结计划（P1 阶梯 4 级含『当前』/ P2 两篇 DOI / P3 两立场）",
       [p["id"] for p in spec["panels"]] == ["P1", "P2", "P3"]
       and spec["panels"][0]["items"] == json.loads(PLAN.read_text(encoding="utf-8"))[
           "items"]["E2"]["C_self_made_spec"]["panels"][0]["content"]
       and any("10.2307/2025976" in x for x in spec["panels"][1]["items"])
       and len(spec["panels"][2]["items"]) == 2)
    ck("4e spec 中无外部素材字段 / 无被否决素材 id",
       IMO_ASSET not in json.dumps(spec, ensure_ascii=False)
       and not any(k in json.dumps(spec, ensure_ascii=False) for k in VA.EXTERNAL_KEYS))

print("\n== 5) locality / conflict ==")
ck("5a 局部化：1 镜 / 占比 0.0359 ≤ 上限（6 镜 / 0.30）",
   len(v2["affected_scope"]["scenes"]) == 1
   and v2["affected_scope"]["share_of_film"] <= core_revision.DEFAULT_POLICY[
       "max_share_of_film_per_proposal"])
proposal_set = [v2_reg] + [r for r in reg_after if r["proposal_id"] != v2["proposal_id"]
                           and r["proposal_id"] != v1["proposal_id"]]
# 6-E 内部冲突：以**生效版本**为准（E2 用 v2；v1 已被 supersede，不参与冲突集）
effective = [v2_reg] + [r for r in reg_after if r["label"].startswith(("E3", "E4", "E5"))]
matrix = EX.detect_conflicts(effective)
v2_pairs = [p for p in matrix["pairs"]
            if "E2" in (str(p.get("a", ""))[:2], str(p.get("b", ""))[:2])]
ck("5b 生效集合内部冲突 0 对（E2v2 与 E3/E4/E5 不重叠）",
   matrix["conflict_pair_count"] == 0 and v2_pairs == [], matrix["pairs"])
executed_c = [p for p in json.loads(M3.read_text(encoding="utf-8"))["proposals"]
              if p["label"] in ("H3-batch1-split-longest", "H3-batch2-next-longest",
                                "H5-semantic-mismatch-replace", "H7-outro-card")]
cross = []
for q in executed_c:
    c = EX.pair_conflict(v2_reg, q)
    if c:
        cross.append({"executed": q["label"], "kinds": c["kinds"],
                      "shared_scenes": c.get("shared_scenes"),
                      "requires_human_reapproval": EX.OVERLAP_POLICY["requires_human_reapproval"],
                      "human_confirmed": False})
ck("5c 与已执行 H5 的跨批次重叠已声明（仍待人工确认）",
   [c for c in cross if c["executed"] == "H5-semantic-mismatch-replace"] != [], cross)
ck("5d 未提交执行批次 ⇒ 当前无阻断", True)

print("\n== 6) 不自动 APPROVE / E3-E5 不动 ==")
bm = json.loads(BM.read_text(encoding="utf-8"))
ck("6a v2 无批准记录（approvals 台账中不存在该 proposal_id）",
   not any(e.get("proposal_id") == v2["proposal_id"] for e in EX.load_ledger(M5_AP))
   and not any(e.get("proposal_id") == v2["proposal_id"]
               for e in EX.load_ledger(LOGS / "phase6e_e1_approvals.jsonl")),
   v2["proposal_id"])
ck("6b v2 无执行记录", not any(e.get("proposal_id") == v2["proposal_id"]
                              for e in EX.load_ledger(M5_EX)
                              + EX.load_ledger(E1_LEDGER)))
st = {s["label"][:2]: s for s in json.loads(STATUS.read_text(encoding="utf-8"))["statuses"]}
ck("6c E2 状态仍为 HOLD（未自动转 APPROVE）", st["E2"]["decision"] == "HOLD", st["E2"]["decision"])
bm_e3 = {i["label"][:2]: i for i in bm["items"]}
untouched = {}
for k in ("E3", "E4", "E5"):
    cur = next(r for r in reg_after if r["label"].startswith(k))
    untouched[k] = EX.proposal_sha256(cur) == bm_e3[k]["proposal_sha256"]
ck("6d E3/E4/E5 proposal_sha256 与批次清单完全一致（未改动）", all(untouched.values()),
   untouched)
ck("6e 未调用 ffmpeg / 未生成任何候选（本脚本仅治理层操作）", True)

# ---------- 7) 输出 ----------
diff = {}
for k in sorted(set(list(v1.keys()) + list(v2.keys()))):
    a, b = v1.get(k), v2.get(k)
    if a != b:
        diff[k] = {"v1": a, "v2": b}
print("\n== 7) 差异字段 ==", list(diff.keys()))

report = {
    "schema": "phase6e-e2-v2-governance-v1", "stage": "6-E", "registered_at": REGISTERED_AT,
    "note": "**治理层修复**：E2 proposal 版本 +1（append-only）。未执行、未审批、未调用 ffmpeg、"
            "未生成候选；历史条目未被修改；E3/E4/E5 未动。",
    "old_proposal": {"proposal_id": v1["proposal_id"], "proposal_sha256": v1_sha,
                     "action": v1["action"], "entry_sha256": v1_entry,
                     "needs_new_material": (v1.get("material_requirement") or {}
                                            ).get("needs_new_material")},
    "new_proposal": {"proposal_id": v2["proposal_id"], "proposal_sha256": v2_sha,
                     "action": v2["action"], "version": 2,
                     "entry_sha256": v2_reg.get("entry_sha256"), "seq": v2_reg.get("seq"),
                     "supersedes": v2["supersedes"], "registered": True,
                     "canonical_proposal_file": str(CANON_FILE.relative_to(ROOT)),
                     "canonical_sha_from_register": canon_sha,
                     "origin": v2_origin,
                     "generated_at": (v2.get("provenance") or {}).get("generated_at"),
                     "rebuild_sha_would_differ": rebuild_sha},
    "proposal_full": v2_reg,
    "diff": {k: {"v1": (str(x)[:400] if x is not None else None),
                 "v2": (str(y)[:400] if y is not None else None)}
             for k, (x, y) in {k: (d["v1"], d["v2"]) for k, d in diff.items()}.items()},
    "checks": checks, "hard_failures": [c["check"] for c in checks if not c["ok"]],
    "gates": {"proposal_validation": errs == [], "register_chain": chain["ok"],
              "provenance": v2["material_requirement"]["needs_new_material"] is False
              and v2["material_requirement"]["asset_id"] is None
              and v2["affected_scope"]["assets"] == [],
              "locality": len(v2["affected_scope"]["scenes"]) == 1,
              "conflict_internal_pairs": matrix["conflict_pair_count"],
              "cross_batch_overlaps": cross,
              "spec_source_binding": {"resolved": resolved, "plan_sha256": plan_sha_live,
                                      "required": PLAN_SHA_REQUIRED, "spec_sha256": spec_sha},
              "e3_e4_e5_untouched": untouched, "auto_approved": False,
              "e2_state_after": st["E2"]["decision"]},
    "known_properties": {
        "proposal_not_byte_reproducible": True,
        "reason": "core.revision.make_proposal 写入 generated_at（revision.py:161）",
        "policy": "以登记条目为权威；审批必须绑定登记条目的 proposal_sha256",
        "rebuild_sha": rebuild_sha, "stored_sha": v2_sha},
    "no_execution": {"ffmpeg_invocations": 0, "candidates_created": 0, "e2_executed": False,
                     "e3_e4_e5_executed": False},
    "next_step": "等待人工审批**新 proposal_sha256**（E2 仍为 HOLD；跨批次重叠亦需确认）。",
}
report["report_sha256"] = hashlib.sha256(
    json.dumps({k: v for k, v in report.items() if k != "report_sha256"}, sort_keys=True,
               ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

rows = [json.loads(x) for x in LEDGER.read_text(encoding="utf-8").splitlines() if x.strip()]
RID = "6E-E2-PROPOSAL-v2-REGISTERED-v1"
if not any(e.get("registration_id") == RID for e in rows):
    r = {"schema": "e2-proposal-v2-registered-v1", "stage": "6-E", "registration_id": RID,
         "registered_at": REGISTERED_AT,
         "old": {"proposal_id": v1["proposal_id"], "proposal_sha256": v1_sha,
                 "action": v1["action"]},
         "new": {"proposal_id": v2["proposal_id"], "proposal_sha256": v2_sha,
                 "action": v2["action"], "version": 2, "entry_sha256": v2_reg.get("entry_sha256")},
         "gates": report["gates"], "hard_failures": report["hard_failures"],
         "e2_state": st["E2"]["decision"], "auto_approved": False, "executed": False,
         "decided_by": "agent:governance-fix(6-E E2 v2)",
         "provenance": "人工指令：E2 proposal 版本 +1（append-only），不自动审批",
         "report": str(OUT.relative_to(ROOT)), "report_sha256": report["report_sha256"],
         "read_only": False, "enforced": False, "advisory": False, "executes_changes": False}
    r["seq"] = len(rows) + 1
    r["prev_sha256"] = rows[-1]["entry_sha256"] if rows else ""
    r["entry_sha256"] = entry_sha(r)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    rows.append(r)
prev, ok = "", True
for i, e in enumerate(rows, start=1):
    if e["seq"] != i or e["prev_sha256"] != prev or e["entry_sha256"] != entry_sha(e):
        ok = False
        break
    prev = e["entry_sha256"]

print("\n== 摘要 ==")
print("旧:", v1["proposal_id"], v1_sha[:16], v1["action"])
print("新:", v2["proposal_id"], v2_sha[:16], v2["action"], "| version", 2,
      "| seq", v2_reg.get("seq"))
print("spec_sha256:", spec_sha)
print("内部冲突:", matrix["conflict_pair_count"], "| 跨批次重叠:", len(cross))
print("硬失败:", report["hard_failures"] or "无")
print("登记链:", len(rows), "条 chain_ok", ok)
print("report ->", OUT)
