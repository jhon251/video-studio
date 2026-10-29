# -*- coding: utf-8 -*-
"""6-B/M3 —— **Revision Proposal 冻结真值集回归**（只生成方案；**禁止执行**）。

覆盖：
  T0 真值集冻结校验（schema/字段/动作/策略/必跑清单）；
  T1 合法方案构造（5 类 action；含 new_assets_needed 的 add_asset）；
  T2 **拒绝矩阵**（12 例）：无 finding / 无人工 REJECT / 不可证 finding / 越界 scene·asset /
     超局部化上限 / film_wide / 缺 basis·assumption / 非法 action / 无锚点；
  T3 证据缺口契约：DEFER/UNKNOWN **只**产出待补证据项（no_proposed_change=true）；
  T4 append-only 方案登记：链校验 + 三类篡改检出；
  T5 **真实 v9 闭环**：7 条 REJECT → 8 条方案（H3 两批）全部可回溯（proposal→finding→REJECT seq/sha→evidence）、
     DEFER 项只出现在 evidence_gaps、未覆盖=0；
  T6 **不得改变未被 REJECT 的内容**：每个方案都必须声明 not_touching，且 scope ⊆ 源 finding 锚点；
  T7 **零执行证明**：静态（无写库/写产物/执行路径、无 agent 引用）+ 运行期（DB/成片/项目目录零改动）。

用法: python tests/revision_truth_test.py
"""
import ast
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import human_review as HR  # noqa: E402
from video_studio.core import revision as REV  # noqa: E402
from video_studio.ops import revision as ops_rev  # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "revision_proposal_truth_v1.json"
FREEZE_REC = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m3_truth_freeze.json"
REPORT = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m3_proposals_v9.json"
REGISTER = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m3_proposal_register_v9.jsonl"
DB = ROOT / "projects" / "video_studio.db"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"
LEDGER = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m2_review_ledger_v9.jsonl"

PASS, FAIL, SKIP = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + str(detail)[:360]))


def skip(name, why):
    SKIP.append(name)
    print("SKIP  {} | {}".format(name, why))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


def manifest(d: Path) -> dict:
    return {p.name: (p.stat().st_size, round(p.stat().st_mtime, 3))
            for p in sorted(d.rglob("*")) if p.is_file()}


TRUTH = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
_canon = json.dumps({k: v for k, v in TRUTH.items() if k != "frozen_sha256"},
                    sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
truth_sha = hashlib.sha256(_canon).hexdigest()
TMP = Path(tempfile.mkdtemp(prefix="vs_m3_rev_"))

# ============================================================================
# T0 —— 冻结校验
# ============================================================================
print("== T0 冻结校验 ==")
check("T0a schema/阶段正确（revision-proposal-truth-v1 / 6-B/M3）",
      TRUTH.get("schema") == "revision-proposal-truth-v1" and TRUTH.get("stage") == "6-B/M3",
      TRUTH.get("schema"))
check("T0b 规范化 sha256 与文件内冻结锚点一致", TRUTH.get("frozen_sha256") == truth_sha,
      {"live": truth_sha, "frozen": TRUTH.get("frozen_sha256")})
check("T0c 冻结策略 == 代码 DEFAULT_POLICY", TRUTH["frozen_policy"] == REV.DEFAULT_POLICY,
      {k: (TRUTH["frozen_policy"].get(k), REV.DEFAULT_POLICY.get(k))
       for k in REV.DEFAULT_POLICY if TRUTH["frozen_policy"].get(k) != REV.DEFAULT_POLICY.get(k)})
check("T0d 必跑清单与代码一致（执行方案前必须重跑 PI/DQ/核验/响度/时长/许可）",
      list(TRUTH["must_rerun"]) == list(REV.MUST_RERUN))
check("T0e 方案必需字段与代码一致",
      list(TRUTH["proposal_required_fields"]) == list(REV.REQUIRED_FIELDS))
check("T0f 动作集合与代码一致", list(TRUTH["change_actions"]) == list(REV.CHANGE_ACTIONS))
if FREEZE_REC.is_file():
    fr = json.loads(FREEZE_REC.read_text(encoding="utf-8"))
    check("T0g 冻结记录中的 sha 与当前真值集一致",
          fr.get("truth_canonical_sha256") == truth_sha,
          {"recorded": fr.get("truth_canonical_sha256")})
else:
    skip("T0g 冻结记录核对", "缺少 {}（先运行 phase6b_m3_build_truth.py）".format(FREEZE_REC.name))

# ============================================================================
# 构造基准 finding / REJECT 决策
# ============================================================================
SCENES = ["S01", "S02", "S03", "S05", "S07", "S11", "S18", "S21"]
ASSETS = ["asset_3f0b94a3f2ac", "asset_30dd89a16713", "asset_432cd85be6f1", "asset_23e71bc8a864"]


def base_finding(**kw):
    it = HR._item(PID, kw.get("metric", "DQ-3"), kw.get("kind", "over_hold_share_exceeds"),
                  kw.get("severity", "FAIL"), kw.get("payload", {"probe": True}),
                  scene_id=kw.get("scene_id", "S07"), asset_id=kw.get("asset_id"),
                  window=kw.get("window", [385.0, 480.0]), discriminator="truth")
    it["unprovable"] = bool(kw.get("unprovable"))
    it["source_evidence"] = EVIDENCE
    return it


TMP_LEDGER = TMP / "truth_ledger.jsonl"


def reject_decision(finding):
    """人工 REJECT 决策（**追加进临时台账**，以获得 seq + entry_sha256 溯源字段）。"""
    rec = HR.make_decision(finding, "REJECT", "人工确认问题成立（建议修改）", "human:test",
                           "truth-set")
    return HR.append_decision(TMP_LEDGER, rec)


def base_kwargs(**over):
    kw = dict(action="split_scene", target={"scene_id": "S07"},
              proposed_change={"what": "切分", "how": "同素材内加切点",
                               "params": {"scene_ids": ["S07"], "target_hold_s": 25.0}},
              affected_scope={"scenes": ["S07"], "window": [385.0, 480.0],
                              "share_of_film": 0.062, "not_touching": ["旁白文本", "字幕"]},
              expected_effect={"metric": "DQ-3", "direction": "hold ≤25 s",
                               "basis": "DQ-3 实测 max_hold_s=95.0", "assumption": "需人工确认切点"},
              constraints={"must_preserve": ["总时长"]},
              risk=[{"risk": "风格割裂", "mitigation": "统一规则"}],
              known_scene_ids=SCENES, known_asset_ids=ASSETS)
    kw.update(over)
    return kw


def build(**over):
    f = over.pop("finding", None) or base_finding()
    d = over.pop("decision", None)
    if d is None and "decision_entry" not in over:
        d = reject_decision(f)
    return REV.make_proposal(f, over.pop("decision_entry", d), **base_kwargs(**over))


# ============================================================================
# T1 —— 合法方案
# ============================================================================
print("\n== T1 合法方案 ==")
for case in TRUTH["accept_cases"]:
    kw = {}
    if case["id"].endswith("ADD-ASSET-WITH-NEW-ASSETS-NEEDED"):
        kw["action"] = "add_asset"
        kw["affected_scope"] = {"assets": ASSETS[:4], "share_of_film": 0.2,
                                "not_touching": ["旁白文本"]}
        kw["proposed_change"] = {"what": "补素材", "how": "人工检索",
                                 "params": {"new_assets_needed": case["new_assets_needed"]}}
        kw["expected_effect"] = {"metric": "DQ-2", "direction": "unique 4→6",
                                 "basis": "DQ-2 实测 unique_assets=4", "assumption": "需先获素材"}
    if case["id"].endswith("ADD-VISUAL-AID"):
        kw["action"] = "add_visual_aid"
    if case["id"].endswith("ADD-OUTRO-CARD"):
        kw["action"] = "add_outro_card"
    if case["id"].endswith("REPLACE-ASSET"):
        kw["action"] = "replace_asset"
        kw["affected_scope"] = {"scenes": ["S05"], "window": [245.0, 300.0],
                                "assets": [ASSETS[0]], "share_of_film": 0.04,
                                "not_touching": ["旁白文本", "字幕"]}
        kw["expected_effect"] = {"metric": "DQ-8", "direction": "MISMATCH→0",
                                 "basis": "DQ-8 mismatch_scene_count=3", "assumption": "需人工复核"}
    try:
        rec = build(**kw)
        err = None
    except Exception as exc:                                     # noqa: BLE001
        rec, err = None, str(exc)
    check("{} 合法方案被接受（action={}）".format(case["id"], kw.get("action", "split_scene")),
          rec is not None, err)
    if rec:
        check("{} 方案含全部必需字段 + 人工边界 + 零执行".format(case["id"]),
              not REV.verify_proposal(rec)
              and rec["status"] == "PROPOSED_AWAITING_HUMAN_APPROVAL"
              and rec["approved"] is False and rec["executed"] is False
              and rec["constraints"]["requires_human_approval"] is True
              and rec["constraints"]["must_rerun"] == list(REV.MUST_RERUN), sorted(rec))
        check("{} provenance 链含 finding → REJECT decision → proposal".format(case["id"]),
              len(rec["provenance"]["chain"]) == 3
              and rec["decision_ref"]["decision"] == "REJECT"
              and rec["decision_ref"]["entry_sha256"], rec["provenance"]["chain"])

# ============================================================================
# T2 —— 拒绝矩阵
# ============================================================================
print("\n== T2 拒绝矩阵 ==")


def expect_refusal(cid, mutate, expect_error):
    f = base_finding()
    d = reject_decision(f)
    kw = base_kwargs()
    if mutate == "drop_finding":
        try:
            REV.make_proposal({}, d, **kw)
        except Exception as exc:                                 # noqa: BLE001
            return check("{} 被拒（{}）".format(cid, expect_error), expect_error in str(exc), exc)
        return check("{} 被拒（{}）".format(cid, expect_error), False, "未被拒")
    if mutate == "decision_defer":
        d = HR.make_decision(f, "DEFER", "暂缓", "human:test", "truth-set")
    if mutate == "make_unprovable":
        f = base_finding(unprovable=True, severity="UNKNOWN")
        d = reject_decision(f)      # 即便人工写了 REJECT，也不得据此生成确定性修改方案
    if mutate == "unknown_scene":
        kw["affected_scope"] = {**kw["affected_scope"], "scenes": ["S99"]}
    if mutate == "unknown_asset":
        kw["affected_scope"] = {"scenes": ["S07"], "assets": ["asset_does_not_exist"],
                                "share_of_film": 0.05, "not_touching": ["旁白"]}
    if mutate == "seven_scenes":
        kw["affected_scope"] = {**kw["affected_scope"], "scenes": SCENES[:7]}
    if mutate == "share_0.5":
        kw["affected_scope"] = {**kw["affected_scope"], "share_of_film": 0.5}
    if mutate == "film_wide":
        kw["affected_scope"] = {**kw["affected_scope"], "film_wide": True}
    if mutate == "no_basis":
        kw["expected_effect"] = {"metric": "DQ-3", "direction": "x", "assumption": "y"}
    if mutate == "no_assumption":
        kw["expected_effect"] = {"metric": "DQ-3", "direction": "x", "basis": "DQ-3 实测 95.0"}
    if mutate == "bad_action":
        kw["action"] = "rewrite_whole_film"
    if mutate == "empty_scope":
        kw["affected_scope"] = {"share_of_film": 0.05}
    try:
        REV.make_proposal(f, d, **kw)
        check("{} 被拒（{}）".format(cid, expect_error), False, "未被拒")
    except Exception as exc:                                     # noqa: BLE001
        check("{} 被拒（{}）".format(cid, expect_error), expect_error in str(exc), exc)


for case in TRUTH["refuse_cases"]:
    expect_refusal(case["id"], case["mutate"], case["expect_error"])

# ============================================================================
# T3 —— 证据缺口契约（DEFER/UNKNOWN 不得变成修改指令）
# ============================================================================
print("\n== T3 证据缺口 ==")
f_u = base_finding(metric="DQ-1", kind="metric_state_unprovable", severity="UNKNOWN",
                   unprovable=True, scene_id="S01", window=[0.0, 40.0])
d_u = reject_decision(f_u)          # 人工即便 REJECT，也不得把不可证项变成修改指令
gap = REV.evidence_gap(f_u, d_u, needed="人工抽帧/语义复核", why="状态 UNKNOWN",
                       provenance="6-B/M3 policy")
check("T3a 不可证 finding 只产出待补证据项且 no_proposed_change=true",
      gap["no_proposed_change"] is True and "proposed_change" not in gap
      and gap["status"] == "AWAITING_EVIDENCE" and gap["executed"] is False)
check("T3b 待补证据项保留 finding 溯源",
      gap["finding_id"] == f_u["finding_id"])
try:
    REV.make_proposal(f_u, d_u, **base_kwargs())
    check("T3c 对不可证 finding 生成确定性方案被拒", False, "未被拒")
except Exception as exc:                                         # noqa: BLE001
    check("T3c 对不可证 finding 生成确定性方案被拒",
          "DEFER_MUST_NOT_BECOME_CHANGE" in str(exc), exc)

# ============================================================================
# T4 —— append-only 方案登记 + 篡改检出
# ============================================================================
print("\n== T4 方案登记 ==")
reg = TMP / "register.jsonl"
for a in ("split_scene", "replace_asset", "add_outro_card"):
    REV.append_proposal(reg, build(action=a))
e0 = REV.load_register(reg)
check("T4a 追加 3 条方案后链完整", len(e0) == 3 and REV.verify_register_chain(e0)["ok"],
      REV.verify_register_chain(e0))


def _tamper(name, mutate):
    p = TMP / "{}.jsonl".format(name)
    shutil.copy2(reg, p)
    lines = p.read_text(encoding="utf-8").splitlines()
    mutate(lines, p)
    v = REV.verify_register_chain(REV.load_register(p))
    check("T4b 篡改检出：{}".format(name), v["ok"] is False, v)


_tamper("mod", lambda ln, p: (lambda d: (d.__setitem__("action", "rewrite"), ln.__setitem__(1,
        json.dumps(d, ensure_ascii=False)), p.write_text("\n".join(ln) + "\n", encoding="utf-8")))(
            json.loads(ln[1])))
_tamper("del", lambda ln, p: (ln.pop(1), p.write_text("\n".join(ln) + "\n", encoding="utf-8")))
_tamper("swap", lambda ln, p: (ln.__setitem__(0, ln[2]), ln.__setitem__(2, ln[0]),
                               p.write_text("\n".join(ln) + "\n", encoding="utf-8")))

# ============================================================================
# T5 —— 真实 v9 闭环（7 REJECT → 8 方案）+ T6 不改变未被 REJECT 的内容
# ============================================================================
print("\n== T5/T6 真实 v9 闭环 ==")
v9 = TRUTH["v9_closure_expect"]
if not (REPORT.is_file() and REGISTER.is_file()):
    skip("T5/T6 v9 闭环", "缺少方案报告或登记表（先运行 phase6b_m3_v9_proposals.py）")
else:
    plan = json.loads(REPORT.read_text(encoding="utf-8"))
    s = plan["summary"]
    reg_entries = REV.load_register(REGISTER)
    check("T5a REJECT finding 全覆盖（rejects={} 已覆盖={} 未覆盖={}）".format(
        s["rejects"], s["rejects_covered"], s["rejects_uncovered"]),
        s["rejects"] == v9["rejects"] and s["rejects_covered"] == v9["rejects"]
        and s["rejects_uncovered"] == v9["rejects_uncovered"], s)
    check("T5b 方案数与登记表条目数达标（方案 {}/登记 {}）".format(s["proposals"],
                                                                  len(reg_entries)),
          s["proposals"] == v9["proposals"] and len(reg_entries) == v9["register_entries"]
          and REV.verify_register_chain(reg_entries)["ok"] == v9["register_chain_ok"],
          REV.verify_register_chain(reg_entries))
    check("T5c 局部化：无上限违规、无 film_wide（全片重构被禁止）",
          s["locality_cap_violations"] == v9["locality_cap_violations"] and s["all_local"] is True,
          s["locality_cap_violations"])
    check("T5d DEFER/UNKNOWN 只出现在 evidence_gaps（数量 {}）且未生成修改方案".format(
        s["evidence_gaps"]), s["evidence_gaps"] == v9["evidence_gaps"]
        and all(g["no_proposed_change"] for g in plan["evidence_gaps"]))
    dec_ids = {e["finding_id"] for e in HR.load_ledger(LEDGER)
               if e.get("decision") == "REJECT"}
    prop_ids = {p["finding_id"] for p in plan["proposals"]}
    check("T5e 每条方案都绑定一条**人工 REJECT** finding（proposal.finding_id ⊆ REJECT 集合）",
          prop_ids <= dec_ids and len(prop_ids) == v9["rejects"], {"prop": len(prop_ids),
                                                                   "reject": len(dec_ids)})
    by_id = {p.get("label") or p["proposal_id"]: p for p in plan["proposals"]}
    problems = []
    for h in v9["h1_h7_traceability"]:
        p = by_id.get(h["label"])
        if not p:
            problems.append((h["id"], "缺少方案"))
            continue
        if (p["metric"], p["kind"], p["action"]) != (h["metric"], h["kind"], h["action"]):
            problems.append((h["id"], "metric/kind/action 不符"))
        if not (p["decision_ref"] or {}).get("entry_sha256") or \
                (p["decision_ref"] or {}).get("decision") != "REJECT":
            problems.append((h["id"], "decision_ref 未绑定 REJECT/sha"))
        if not p.get("original_evidence") or not p["provenance"].get("chain"):
            problems.append((h["id"], "缺原始证据/provenance 链"))
    check("T5f H1…H7 的 8 条方案全部可回溯到对应人审 REJECT（finding→seq/sha→evidence）",
          problems == [], problems)
    not_prop = {f"{p['metric']}:{p['kind']}" for p in plan["proposals"]}
    check("T5g 未对 DEFER/UNKNOWN 或人工审计项生成修改方案",
          all(x not in not_prop for x in v9["must_not_propose_for"]), sorted(not_prop))
    check("T6a 每条方案都声明 not_touching（避免改变未被 REJECT 的内容）",
          all((p["affected_scope"].get("not_touching") or []) for p in plan["proposals"]),
          [p["proposal_id"] for p in plan["proposals"]
           if not (p["affected_scope"].get("not_touching") or [])])
    check("T6b 方案影响范围可定位（scene/asset/window/asset_class 至少其一）",
          all(p["affected_scope"].get("scenes") or p["affected_scope"].get("assets")
              or p["affected_scope"].get("window")
              or p["affected_scope"].get("asset_class") for p in plan["proposals"]))
    check("T6c 每个方案都有 expected_effect.basis 与 assumption（不虚构预期收益）",
          all(p["expected_effect"].get("basis") and p["expected_effect"].get("assumption")
              for p in plan["proposals"]))
    check("T6d 每个方案都带 must_rerun 与 requires_human_approval（执行前必须重跑门禁）",
          all(p["constraints"]["must_rerun"] == list(REV.MUST_RERUN)
              and p["constraints"]["requires_human_approval"] is True
              and p["constraints"]["no_auto_execution"] is True for p in plan["proposals"]))
    check("T7a v9 闭环零执行：executed=[] 、executed_actions=[] 、executes_changes=False",
          s["executed"] == v9["executed"] and s["executed_actions"] == v9["executed_actions"]
          and s["executes_changes"] is False and plan["executes_changes"] is False, s["executed"])
    ro = plan["read_only_evidence"]
    check("T7b v9 闭环只读：DB / 成片 / output 清单逐字节不变",
          ro["db_unchanged"] and ro["film_unchanged"] and ro["output_manifest_unchanged"]
          and ro["project_files_touched"] == [], ro)

# ============================================================================
# T7 —— 零执行静态证明
# ============================================================================
print("\n== T7 零执行静态证明 ==")
core_txt = (ROOT / "src/video_studio/core/revision.py").read_text(encoding="utf-8")
ops_txt = (ROOT / "src/video_studio/ops/revision.py").read_text(encoding="utf-8")
for rel, txt in (("core/revision.py", core_txt), ("ops/revision.py", ops_txt)):
    hits = [b for b in ("write_artifact", "set_task_status", "TASK_BLOCKED", "build_engine",
                        "create_task", "run_cycle", "redo(", "INSERT ", "UPDATE ", "DELETE ")
            if b in txt and not (b == "TASK_BLOCKED" and "不接入 TASK_BLOCKED" in txt)]
    check("T7c 静态：{} 无写库/派发/阻断形态".format(rel), hits == [], hits)
check("T7d 静态：core/revision.py 不触碰 DB/成片（无 sqlite3/subprocess/ffmpeg）",
      all(x not in core_txt for x in ("sqlite3", "subprocess", "ffmpeg")))
check("T7e 静态：没有任何 `apply`/execute 执行路径（只生成方案）",
      all(x not in core_txt + ops_txt for x in ("def apply", "apply_proposal", "execute_proposal",
                                                "def execute")))
refs = []
for p in sorted((ROOT / "src" / "video_studio" / "agents").rglob("*.py")):
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        mods = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                ([node.module or ""] if isinstance(node, ast.ImportFrom) else []))
        if any(m.endswith("core.revision") or m.endswith("ops.revision") for m in mods):
            refs.append(p.relative_to(ROOT).as_posix())
check("T7f 静态：没有任何 agent import revision 模块（不可能接进生产链/自动执行）", refs == [], refs)
if FILM.is_file() and DB.is_file():
    db_b, film_b, man_b = sha(DB), sha(FILM), manifest(FILM.parent)
    specs = [{"id": "smoke", "match": {"metric": "DQ-3", "kind": "over_hold_share_exceeds"},
              "action": "split_scene", "target": {"scene_id": "S07"},
              "proposed_change": {"what": "切分", "how": "加切点", "params": {"scene_ids": ["S07"]}},
              "affected_scope": {"scenes": ["S07"], "window": [385.0, 480.0],
                                 "share_of_film": 0.06, "not_touching": ["旁白文本"]},
              "expected_effect": {"metric": "DQ-3", "direction": "hold ≤25 s",
                                  "basis": "DQ-3 实测 max_hold_s=95.0", "assumption": "需人工确认"},
              "risk": [{"risk": "风格割裂", "mitigation": "统一规则"}]}]
    plan_rt = ops_rev.build_revision_plan(PID, DB, ROOT, CFG, film_task=FILM_TASK,
                                          evidence_path=EVIDENCE, ledger_path=str(LEDGER),
                                          proposal_specs=specs, measure_freeze=False)
    check("T7g 运行期：构建方案计划后 DB / 成片 / 项目目录逐字节不变",
          sha(DB) == db_b and sha(FILM) == film_b and manifest(FILM.parent) == man_b,
          {"db": sha(DB) == db_b, "film": sha(FILM) == film_b})
    check("T7h 运行期：计划显式声明零执行（executed_actions 空、无 executed 方案）",
          plan_rt["summary"]["executed_actions"] == [] and plan_rt["executes_changes"] is False
          and all(p["executed"] is False for p in plan_rt["proposals"]))
else:
    skip("T7g/T7h 运行期零执行证明", "缺 v9 成片或 DB")

print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if not FAIL else 1)
