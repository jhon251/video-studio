# -*- coding: utf-8 -*-
"""6-B/M4 —— **受控执行冻结真值集回归**（审批 → hash 绑定 → 局部执行 → PI/DQ 复核 → 零提升）。

覆盖：
  T0 冻结校验（审批字段/决策/状态机/冻结策略）；
  T1 执行门禁 8 例：未批准 / 被拒 / proposal 被改 / 绑错 proposal / 正常 APPROVE /
     film_wide / 超镜头上限 / 占片比超限；
  T2 执行器行为 6 例：执行器抛错（fail-closed、不自动重试/扩范围）/ 未实现 action /
     缺真实素材（PENDING_HUMAN_ASSET）/ 成功但必须带 PI+DQ 复核 / 缺复核即失败 / 复核抛错即失败；
  T3 台账：审批与执行**两条独立** append-only 哈希链 + 三类篡改检出；
  T4 真实 v9 受控执行证据：H7 APPROVE→执行(沙箱)→PI/DQ 复核（PI gate=BLOCKED、DQ-6 FAIL→PASS）、
     H2 PENDING_HUMAN_ASSET、H3a BLOCKED_REJECTED、H1 BLOCKED_UNAPPROVED、tamper BLOCKED_TAMPERED，
     且 `executed_without_approval=[]`、`auto_approved=false`、`promoted=[]`、v9 母版/目录/DB 零改动；
  T5 零自动化静态证明：无自动批准/自动执行全部/自动扩大范围/自动换方案代码路径。

用法: python tests/execution_truth_test.py
"""
import ast
import copy
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import execution as EX  # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "revision_execution_truth_v1.json"
FREEZE_REC = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m4_truth_freeze.json"
V9_REPORT = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m4_v9_execution.json"
V9_APPROVALS = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m4_approvals_v9.jsonl"
V9_EXECS = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m4_execution_ledger_v9.jsonl"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"

PASS, FAIL, SKIP = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name,
                             "" if ok else "| " + str(detail)[:340]))


def skip(name, why):
    SKIP.append(name)
    print("SKIP  {} | {}".format(name, why))


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


TRUTH = json.loads(TRUTH_PATH.read_text(encoding="utf-8"))
_canon = json.dumps({k: v for k, v in TRUTH.items() if k != "frozen_sha256"},
                    sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
truth_sha = hashlib.sha256(_canon).hexdigest()
TMP = Path(tempfile.mkdtemp(prefix="vs_m4_exec_"))

# ============================================================================
# T0 冻结校验
# ============================================================================
print("== T0 冻结校验 ==")
check("T0a schema/阶段正确（revision-execution-truth-v1 / 6-B/M4）",
      TRUTH.get("schema") == "revision-execution-truth-v1" and TRUTH.get("stage") == "6-B/M4",
      TRUTH.get("schema"))
check("T0b 规范化 sha256 与文件内冻结锚点一致", TRUTH.get("frozen_sha256") == truth_sha,
      {"live": truth_sha, "frozen": TRUTH.get("frozen_sha256")})
check("T0c 审批必需字段与代码一致",
      list(TRUTH["approval_required_fields"]) == list(EX.REQUIRED_APPROVAL_FIELDS))
check("T0d 审批取值与状态机与代码一致",
      list(TRUTH["approval_decisions"]) == list(EX.APPROVAL_DECISIONS)
      and list(TRUTH["execution_states"]) == list(EX.EXECUTION_STATES))
check("T0e 冻结策略 == 代码 POLICY（含 require_pi_recheck / no_auto_approval）",
      all(TRUTH["frozen_policy"][k] == EX.POLICY[k] for k in TRUTH["frozen_policy"]),
      {k: (TRUTH["frozen_policy"][k], EX.POLICY.get(k)) for k in TRUTH["frozen_policy"]})
if FREEZE_REC.is_file():
    fr = json.loads(FREEZE_REC.read_text(encoding="utf-8"))
    check("T0f 冻结记录中的 sha 与当前真值集一致",
          fr.get("truth_canonical_sha256") == truth_sha)
else:
    skip("T0f 冻结记录核对", "缺少 {}（先运行 phase6b_m4_build_truth.py）".format(FREEZE_REC.name))

# ============================================================================
# 基准 proposal（局部、可执行）
# ============================================================================
BASE = {
    "proposal_id": "rp-test00000001", "label": "TEST-outro", "finding_id": "hr-test",
    "action": "add_outro_card", "metric": "DQ-6", "kind": "no_outro_keyword_in_tail",
    "affected_scope": {"scenes": ["S21"], "window": [1465.0, 1532.0], "share_of_film": 0.04,
                       "not_touching": ["旁白正文", "字幕", "总时长"]},
    "proposed_change": {"what": "加片尾卡", "how": "原地替换末段", "params": {}},
    "expected_effect": {"metric": "DQ-6", "direction": "outro 命中 0→≥1", "basis": "DQ-6 hits=0",
                        "assumption": "需人工确认"},
    "decision_ref": {"ledger_seq": 1, "decision": "REJECT", "entry_sha256": "x" * 64},
    "provenance": {"chain": ["a", "b", "c"]},
}


def mkprops(**over):
    p = copy.deepcopy(BASE)
    for k, v in over.items():
        p[k] = v
    return p


def approve(prop, decision="APPROVE", by="human:test"):
    return EX.make_approval(prop, decision, by, "理由", "truth-set", at="2026-09-28T00:00:00Z")


# ============================================================================
# T1 执行门禁
# ============================================================================
print("\n== T1 执行门禁 ==")
for case in TRUTH["gate_cases"]:
    prop = mkprops()
    kind = case["approvals"]
    aps = []
    if kind == "none":
        aps = []
    elif kind == "reject":
        aps = [approve(prop, "REJECT")]
    elif kind == "approve":
        aps = [approve(prop)]
    elif kind == "approve_then_modify_proposal":
        aps = [approve(prop)]
        prop = mkprops(proposed_change={"what": "被篡改", "how": "全片重做", "params": {}})
    elif kind == "approve_other_proposal":
        aps = [approve(mkprops(proposal_id="rp-other999999"))]
    if case.get("proposal_mutate") == "film_wide":
        prop["affected_scope"] = {**prop["affected_scope"], "film_wide": True}
        aps = [approve(prop)]
    if case.get("proposal_mutate") == "seven_scenes":
        prop["affected_scope"] = {**prop["affected_scope"],
                                  "scenes": ["S%02d" % i for i in range(1, 8)]}
        aps = [approve(prop)]
    if case.get("proposal_mutate") == "share_0.5":
        prop["affected_scope"] = {**prop["affected_scope"], "share_of_film": 0.5}
        aps = [approve(prop)]
    g = EX.gate_execution(prop, aps)
    check("{} allowed={} code={}".format(case["id"], case["expect"]["allowed"],
                                         case["expect"]["code"]),
          g["allowed"] is case["expect"]["allowed"] and g["code"] == case["expect"]["code"], g)

# ============================================================================
# T2 执行器行为（fail-closed）
# ============================================================================
print("\n== T2 执行器行为 ==")


def raise_exec(ctx, p):
    raise RuntimeError("boom: 执行器故意失败")


def pending_exec(ctx, p):
    return {"pending": "PENDING_HUMAN_ASSET", "why": "无真实可用素材", "steps": []}


def ok_exec(ctx, p):
    out = TMP / "out_{}.txt".format(p["proposal_id"])
    out.write_text("executed", encoding="utf-8")
    return {"steps": [{"step": "write_marker", "out": out.name}],
            "outputs": [{"path": str(out), "sha256": sha(out)}]}


def ok_recheck(ctx, p, res):
    return {"pi_metrics": {"PI-1": {"state": "FAIL"}}, "pi_gate_outcome": "BLOCKED",
            "dq_metrics": {"DQ-6": "PASS"}, "read_only": True}


def raising_recheck(ctx, p, res):
    raise RuntimeError("recheck boom")


for case in TRUTH["execution_cases"]:
    prop = mkprops(action=case["action"])
    aps = [approve(prop)]
    execs = {"split_scene": raise_exec, "add_outro_card": ok_exec,
             "replace_asset": pending_exec}
    recheck = ok_recheck
    if case["executor"] == "raise":
        execs[case["action"]] = raise_exec
    elif case["executor"] == "absent":
        execs = {}
    elif case["executor"] == "pending_asset":
        execs[case["action"]] = pending_exec
    elif case["executor"] == "ok_no_recheck":
        recheck = None
    elif case["executor"] == "ok_recheck_raises":
        recheck = raising_recheck
    rec = EX.execute_proposal(prop, aps, execs, {"root": str(ROOT)}, recheck=recheck)
    exp = case["expect"]
    ok = rec["state"] == exp["state"]
    if "why_contains" in exp:
        ok = ok and exp["why_contains"] in (rec.get("why") or "")
    if exp.get("has_pi_recheck"):
        ok = ok and bool((rec.get("recheck") or {}).get("pi_metrics")) \
            and bool((rec.get("recheck") or {}).get("dq_metrics"))
    if rec["state"] in ("SUCCEEDED", "FAILED"):
        ok = ok and rec["auto_retry"] is False and rec["auto_scope_expansion"] is False \
            and rec["auto_approved"] is False
    check("{} state={}".format(case["id"], exp["state"]), ok,
          {"state": rec["state"], "why": (rec.get("why") or "")[:120]})
check("T2 成功执行后 promoted=False（永不自动提升）",
      EX.execute_proposal(mkprops(), [approve(mkprops())], {"add_outro_card": ok_exec},
                          {"root": str(ROOT)}, recheck=ok_recheck)["promoted"] is False)

# ---------------------------------------------------------------------------
# T2b 授权书第 4/5 条：执行记录必须含 动作/输入-输出/结果/失败原因/溯源；
#      执行器**不得**静默修改 proposal（hash 前后一致、内容逐字节不变）
# ---------------------------------------------------------------------------
_prop = mkprops()
_aps = [approve(_prop)]
_before_txt = json.dumps(_prop, sort_keys=True, ensure_ascii=False)
_before_sha = EX.proposal_sha256(_prop)
_rec = EX.execute_proposal(_prop, _aps, {"add_outro_card": ok_exec},
                           {"root": str(ROOT), "film": "sandbox_copy.mp4"}, recheck=ok_recheck)
_after_txt = json.dumps(_prop, sort_keys=True, ensure_ascii=False)
_need = ("action", "state", "steps", "outputs", "proposal_sha256", "approval_ref", "executed_at")
_missing = [k for k in _need if k not in _rec]
check("T2b 执行记录含 动作/输入输出/结果/溯源 字段（授权书第 4 条）", _missing == [],
      {"missing": _missing, "keys": sorted(_rec.keys())})
check("T2b 执行记录的输入来自**执行器真实返回**（steps 带 step/out 与真实 sha256，不伪造）",
      bool(_rec["steps"]) and all("step" in s for s in _rec["steps"])
      and bool(_rec["outputs"]) and len(_rec["outputs"][0].get("sha256") or "") == 64,
      {"steps": _rec["steps"], "outputs": _rec["outputs"]})
_fail = EX.execute_proposal(mkprops(), [approve(mkprops())], {"add_outro_card": raise_exec},
                            {"root": str(ROOT)}, recheck=ok_recheck)
check("T2b 失败记录含**失败原因**（why 非空，且不回填假输出）",
      _fail["state"] == "FAILED" and "boom" in (_fail.get("why") or "")
      and _fail["outputs"] == [] and _fail["recheck"] is None,
      {"state": _fail["state"], "why": (_fail.get("why") or "")[:80]})
check("T2b 执行前后 proposal **逐字节不变**且 hash 一致（执行器不得静默改方案，第 5 条）",
      _before_txt == _after_txt and _rec["proposal_sha256"] == _before_sha,
      {"sha_before": _before_sha[:12], "sha_in_record": str(_rec["proposal_sha256"])[:12],
       "unchanged": _before_txt == _after_txt})
check("T2b 记录中的 proposal_sha256 == 审批绑定值（审批与执行对象同一）",
      _rec["proposal_sha256"] == _aps[0]["proposal_sha256"] == _before_sha)

# ============================================================================
# T3 台账：两条独立 append-only 链 + 篡改检出
# ============================================================================
print("\n== T3 台账 ==")
ap_p, ex_p = TMP / "ap.jsonl", TMP / "ex.jsonl"
for i in range(3):
    prop = mkprops(proposal_id="rp-%012d" % i)
    EX.append_approval(ap_p, approve(prop))
    EX.append_execution(ex_p, EX.execute_proposal(prop, [], {}, {}, recheck=None))
check("T3a 审批/执行两条链各自完整",
      EX.verify_chain(EX.load_ledger(ap_p))["ok"] and EX.verify_chain(EX.load_ledger(ex_p))["ok"])


def _tamper(name, path, mutate):
    p = TMP / (name + ".jsonl")
    shutil.copy2(path, p)
    lines = p.read_text(encoding="utf-8").splitlines()
    mutate(lines, p)
    v = EX.verify_chain(EX.load_ledger(p))
    check("T3b 篡改检出：{}".format(name), v["ok"] is False, v)


for nm, path in (("ap_mod", ap_p), ("ex_del", ex_p), ("ap_swap", ap_p)):
    if nm.endswith("mod"):
        _tamper(nm, path, lambda ln, p: (lambda d: (d.__setitem__("reason", "改"),
                                                    ln.__setitem__(1, json.dumps(d, ensure_ascii=False)),
                                                    p.write_text("\n".join(ln) + "\n", encoding="utf-8")))(json.loads(ln[1])))
    elif nm.endswith("del"):
        _tamper(nm, path, lambda ln, p: (ln.pop(1), p.write_text("\n".join(ln) + "\n", encoding="utf-8")))
    else:
        _tamper(nm, path, lambda ln, p: (ln.__setitem__(0, ln[2]), ln.__setitem__(2, ln[0]),
                                         p.write_text("\n".join(ln) + "\n", encoding="utf-8")))

# ============================================================================
# T4 真实 v9 受控执行证据
# ============================================================================
print("\n== T4 真实 v9 受控执行 ==")
v9 = TRUTH["v9_execution_expect"]
if not (V9_REPORT.is_file() and V9_APPROVALS.is_file() and V9_EXECS.is_file()):
    skip("T4 v9 受控执行", "缺少 v9 执行证据（先运行 phase6b_m4_execute_v9.py）")
else:
    rep = json.loads(V9_REPORT.read_text(encoding="utf-8"))
    execs = rep["executions"]
    by_label = {}
    for e in execs:
        by_label.setdefault(e["proposal_label"], []).append(e)
    states = {e["proposal_label"]: e["state"] for e in execs}
    check("T4a 审批记录与真值一致（H7/H2 APPROVE、H3a REJECT，且均非自动批准）",
          {(a["proposal_label"], a["decision"]) for a in rep["approvals"]}
          == set(v9["approvals"].items()) and all(a.get("auto_approved") is False
                                                  for a in rep["approvals"]),
          [(a["proposal_label"], a["decision"]) for a in rep["approvals"]])
    ok_states = (by_label["H7-outro-card"][0]["state"] == v9["execution_states"]["H7-outro-card"]
                 and states.get("H2-asset-pool-diversity")
                 == v9["execution_states"]["H2-asset-pool-diversity"]
                 and states.get("H3-batch1-split-longest")
                 == v9["execution_states"]["H3-batch1-split-longest"]
                 and states.get("H1-hook-replace")
                 == v9["execution_states"]["H1-hook-replace"]
                 and any(e["state"] == "BLOCKED_TAMPERED" for e in by_label["H7-outro-card"]))
    check("T4b 五类执行结果符合真值（SUCCEEDED / PENDING_HUMAN_ASSET / BLOCKED_REJECTED / "
          "BLOCKED_UNAPPROVED / BLOCKED_TAMPERED）", ok_states, states)
    check("T4c 未批准却执行 = 空、自动批准 = false、已提升 = 空",
          rep["summary"]["executed_without_approval"] == v9["executed_without_approval"]
          and rep["summary"]["auto_approved"] is False
          and rep["summary"]["promoted"] == v9["promoted"], rep["summary"])
    h7 = by_label["H7-outro-card"][0]
    pi = {k: v["state"] for k, v in (h7["recheck"]["pi_metrics"] or {}).items()}
    check("T4d 执行后**强制重跑 PI-1…PI-6** 且与真值一致（v9 仍 BLOCKED）",
          pi == {k: v for k, v in v9["pi_recheck_after_h7"].items() if k != "pi_gate_outcome"}
          and h7["pi_gate_outcome"] == v9["pi_recheck_after_h7"]["pi_gate_outcome"], pi)
    check("T4e DQ 复核：DQ-6 由 FAIL → PASS（真实可测改善）、其余 DQ 项未变",
          (h7["recheck"]["dq_metrics"] or {}).get("DQ-6") == "PASS"
          and all((h7["recheck"]["dq_metrics"] or {}).get(k) == st
                  for k, st in (("DQ-2", "FAIL"), ("DQ-3", "FAIL"), ("DQ-4", "FAIL"),
                                ("DQ-5", "FAIL"), ("DQ-8", "FAIL"))),
          h7["recheck"]["dq_metrics"])
    check("T4f 执行只在沙箱内发生（有输出成片且路径在沙箱下）",
          any("phase6b_m4_sandbox" in (o.get("path") or "")
              for o in (h7.get("outputs") or [])) and rep["sandbox"]["box"].replace("\\", "/").startswith("output/"),
          rep["sandbox"])
    ro = rep["read_only_evidence"]
    check("T4g v9 母版 / v9 output 目录 / DB 在执行前后逐字节不变",
          ro["v9_master_unchanged"] and ro["v9_output_dir_unchanged"] and ro["db_unchanged"]
          and ro["project_files_touched"] == [], ro)
    check("T4h 母版 sha256 与冻结记录一致（未被覆盖）",
          sha(FILM) == v9["v9_master_sha256"] and rep["sandbox"]["source_film_sha256"]
          == v9["v9_master_sha256"], sha(FILM)[:16])
    check("T4i 审批/执行台账链完整（两条独立链）",
          EX.verify_chain(EX.load_ledger(V9_APPROVALS))["ok"]
          and EX.verify_chain(EX.load_ledger(V9_EXECS))["ok"]
          and rep["summary"]["ledger"]["approvals"]["chain_ok"]
          and rep["summary"]["ledger"]["executions"]["chain_ok"])
    check("T4j 只执行了 1 条（未自动执行全部 8 条 M3 方案）",
          rep["summary"]["state_counts"].get("SUCCEEDED") == v9["executed_succeeded"]
          and len(rep["approvals"]) == 3, rep["summary"]["state_counts"])

# ============================================================================
# T5 零自动化静态证明
# ============================================================================
print("\n== T5 零自动化静态证明 ==")
core_txt = (ROOT / "src/video_studio/core/execution.py").read_text(encoding="utf-8")
ops_txt = (ROOT / "src/video_studio/ops/execution.py").read_text(encoding="utf-8")
_t5_tree = ast.parse(core_txt + "\n" + ops_txt)
_defs = [n.name for n in ast.walk(_t5_tree) if isinstance(n, ast.FunctionDef)]
check("T5a 静态：无自动批准/自动执行全部/自动扩大范围/自动换方案**函数**",
      all(not d.startswith("auto_") for d in _defs)
      and not any(x in _defs for x in ("execute_all", "apply_all", "fallback_plan")),
      [d for d in _defs if d.startswith("auto_")])
check("T5b 静态：审批默认值恒为人工（auto_approved=False 写死）",
      '"auto_approved": False' in core_txt)
_c_tree = ast.parse(core_txt)
_imports = [a.name for n in ast.walk(_c_tree) if isinstance(n, ast.Import) for a in n.names]
_imports += [(n.module or "") for n in ast.walk(_c_tree) if isinstance(n, ast.ImportFrom)]
_calls = [getattr(n.func, "attr", None) or getattr(n.func, "id", None)
          for n in ast.walk(_c_tree) if isinstance(n, ast.Call)]
check("T5c 静态：core/execution.py 不 import/调用 DB·进程（执行器由调用方注入）",
      not any(m.split(".")[0] in ("sqlite3", "subprocess") for m in _imports)
      and not any(c in ("run", "Popen", "connect") for c in _calls),
      {"imports": _imports, "calls": [c for c in _calls if c in ("run", "Popen", "connect")]})
check("T5d 静态：沙箱前缀写死为 output/ 下（不写项目/基线目录）",
      "output/phase6b_m4_sandbox" in ops_txt)
refs = []
import ast  # noqa: E402
for p in sorted((ROOT / "src" / "video_studio" / "agents").rglob("*.py")):
    try:
        tree = ast.parse(p.read_text(encoding="utf-8"))
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        mods = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                ([node.module or ""] if isinstance(node, ast.ImportFrom) else []))
        if any(m.endswith("core.execution") or m.endswith("ops.execution") for m in mods):
            refs.append(p.relative_to(ROOT).as_posix())
check("T5e 静态：没有任何 agent import execution 模块（执行链不在生产判定链内）", refs == [], refs)

print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if not FAIL else 1)
