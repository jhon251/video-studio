# -*- coding: utf-8 -*-
"""6-B/M5 —— **执行可靠性冻结真值集回归**（真实素材执行分支 + 多方案重叠冲突/一致性/fail-closed）。

覆盖（对应授权"仅关闭 M4 两个 PENDING"）：
  T0 冻结校验（schema/策略/状态机/冲突种类）；
  T1 冲突矩阵 12 例（同镜 / 窗口交叠 / 端点相接不重叠 / 同素材 / 同目标 / 空痕迹 / 重复提交）
     + 6-B/M3 真实 8 方案矩阵（10 对）；
  T2 素材校验 10 例（5 条真实素材 ASSET_OK；缺文件 / sha 不符 / 不可解码 / 许可受限 / 许可未清）；
  T3 批量一致性 8 例（未批准/被拒不拖住已批准、冲突对称阻断、幂等、冲突优先于幂等、篡改/全片重写仍被阻断）；
  T4 真实 v9 证据：2 条 APPROVE→真实执行→强制 PI/DQ 复核 + 成片抽帧比对（replaced=True）、
     冲突批 3 条全部 BLOCKED_CONFLICT、重放被幂等阻断、台账双链、DB/母版/output 零改动；
  T5 并发：加锁后两条互不重叠方案并发执行 ⇒ 都成功且链连续；同一方案并发 ⇒ 一条成功一条被幂等阻断；
  T6 静态零自动化：不存在自动合并/自动排序/自动扩范围/自动批准/批量执行入口。

用法: python tests/execution_reliability_test.py
"""
import ast as _ast
import copy
import hashlib
import json
import shutil
import sys
import tempfile
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import execution as EX            # noqa: E402
from video_studio.ops import execution as ops_exec       # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "execution_reliability_truth_v1.json"
FREEZE_REC = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m5_truth_freeze.json"
V9_REPORT = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m5_v9_execution.json"
V9_APPROVALS = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m5_approvals_v9.jsonl"
V9_EXECS = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m5_execution_ledger_v9.jsonl"
M3_REPORT = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m3_proposals_v9.json"
DB = ROOT / "projects" / "video_studio.db"
FILM = ROOT / "projects" / "p_96efdc03e1aa" / "output" / "t_d0a54bdf1810_draft.mp4"
V9_FILM_SHA = "22705c7d7ea20b40d91120146066b89ab2b5fa5c1a1cab18f5346d4c66497651"

PASS, FAIL, SKIP = [], [], []


def check(name, ok, detail=""):
    (PASS if ok else FAIL).append(name)
    print("{}  {} {}".format("PASS" if ok else "FAIL", name, "" if ok else "| " + str(detail)[:340]))


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
TMP = Path(tempfile.mkdtemp(prefix="vs_m5_rel_"))

BASE = {
    "proposal_id": "rp-m5test00001", "label": "M5-test", "finding_id": "hr-test",
    "action": "replace_asset", "metric": "DQ-2", "kind": "unique_assets_below_min",
    "affected_scope": {"scenes": ["S20"], "window": [1405.0, 1465.0], "assets": [],
                       "share_of_film": 0.04, "not_touching": ["旁白正文", "字幕", "总时长"]},
    "proposed_change": {"what": "替换素材", "how": "沙箱窗口替换", "params": {}},
    "expected_effect": {"metric": "DQ-2", "direction": "唯一素材数上升", "basis": "v9 实测",
                        "assumption": "局部替换不保证全片指标"},
    "decision_ref": {"ledger_seq": 3, "decision": "REJECT", "entry_sha256": "x" * 64},
    "provenance": {"chain": ["a", "b"]},
}


def mkprops(pid="rp-m5test00001", scenes=("S20",), window=(1405.0, 1465.0), assets=(),
            target=None, **over):
    p = copy.deepcopy(BASE)
    p["proposal_id"] = pid
    p["label"] = pid
    p["affected_scope"] = {**p["affected_scope"], "scenes": list(scenes),
                           "window": list(window), "assets": list(assets)}
    if target is not None:
        p["target"] = target
    p.update(over)
    return p


def approve(prop, decision="APPROVE", by="human:test"):
    return EX.make_approval(prop, decision, by, "理由", "真值集", at="2026-09-29T00:00:00Z")


# ============================================================================
# T0 冻结校验
# ============================================================================
print("== T0 冻结校验 ==")
check("T0a schema/阶段正确（execution-reliability-truth-v1 / 6-B/M5）",
      TRUTH.get("schema") == "execution-reliability-truth-v1" and TRUTH.get("stage") == "6-B/M5",
      TRUTH.get("schema"))
check("T0b 规范化 sha256 与文件内冻结锚点一致", TRUTH.get("frozen_sha256") == truth_sha,
      {"live": truth_sha, "frozen": TRUTH.get("frozen_sha256")})
check("T0c 重叠策略与代码 OVERLAP_POLICY 完全一致",
      all(TRUTH["overlap_policy"][k] == EX.OVERLAP_POLICY[k] for k in TRUTH["overlap_policy"])
      and set(TRUTH["overlap_policy"]) == set(EX.OVERLAP_POLICY),
      {k: (TRUTH["overlap_policy"].get(k), EX.OVERLAP_POLICY.get(k))
       for k in set(TRUTH["overlap_policy"]) | set(EX.OVERLAP_POLICY)})
check("T0d 冲突种类 == 代码 CONFLICT_KINDS", list(TRUTH["conflict_kinds"]) == list(EX.CONFLICT_KINDS))
check("T0e M5 新增状态与代码 M5_STATES 一致，且 **M4 冻结状态机未被改动**",
      list(TRUTH["m5_states"]) == list(EX.M5_STATES)
      and all(s in EX.ALL_EXECUTION_STATES for s in EX.M5_STATES)
      and list(json.loads((ROOT / "tests" / "fixtures" / "revision_execution_truth_v1.json")
                          .read_text(encoding="utf-8"))["execution_states"])
      == list(EX.EXECUTION_STATES),
      {"m5": list(EX.M5_STATES), "all": list(EX.ALL_EXECUTION_STATES)})
check("T0f 零自动化偏好写死：不合并/不排序/不扩范围/必须人工重新批准",
      EX.OVERLAP_POLICY["auto_merge"] is False and EX.OVERLAP_POLICY["auto_reorder"] is False
      and EX.OVERLAP_POLICY["auto_scope_expansion"] is False
      and EX.OVERLAP_POLICY["requires_human_reapproval"] is True
      and EX.OVERLAP_POLICY["block_all_participants"] is True)
if FREEZE_REC.is_file():
    fr = json.loads(FREEZE_REC.read_text(encoding="utf-8"))
    check("T0g 冻结记录中的 sha 与当前真值集一致（且用例数一致）",
          fr.get("truth_canonical_sha256") == truth_sha
          and fr.get("conflict_case_count") == len(TRUTH["conflict_cases"])
          and fr.get("asset_case_count") == len(TRUTH["asset_cases"])
          and fr.get("batch_case_count") == len(TRUTH["batch_cases"]))
else:
    skip("T0g 冻结记录核对", "缺少 {}（先运行 phase6b_m5_build_truth.py）".format(FREEZE_REC.name))

# ============================================================================
# T1 冲突矩阵
# ============================================================================
print("\n== T1 冲突/重叠矩阵 ==")
for case in TRUTH["conflict_cases"]:
    a = mkprops("rp-a-" + case["id"], scenes=case["a"].get("scenes") or [],
                window=tuple(case["a"].get("window") or (0.0, 0.0)) if case["a"].get("window")
                else (0.0, 0.0), assets=case["a"].get("assets") or [],
                target=case["a"].get("target"))
    b = mkprops("rp-b-" + case["id"], scenes=case["b"].get("scenes") or [],
                window=tuple(case["b"].get("window") or (0.0, 0.0)) if case["b"].get("window")
                else (0.0, 0.0), assets=case["b"].get("assets") or [],
                target=case["b"].get("target"))
    if not case["a"].get("window"):
        a["affected_scope"].pop("window", None)
    if not case["b"].get("window"):
        b["affected_scope"].pop("window", None)
    c = EX.pair_conflict(a, b)
    got = c["kinds"] if c else None
    check("T1 {}".format(case["id"]), got == case["expect_kinds"],
          {"expect": case["expect_kinds"], "got": got, "why": case["why"]})
m3 = json.loads(M3_REPORT.read_text(encoding="utf-8"))
mat = EX.detect_conflicts(m3["proposals"])
exp = TRUTH["m3_register_matrix_expect"]
got_pairs = sorted([c["a"], c["b"], tuple(c["kinds"])] for c in mat["pairs"])
exp_pairs = sorted([x[0], x[1], tuple(x[2])] for x in exp["pairs"])
check("T1 M3 真实 8 方案矩阵：冲突对数与逐对 kinds 完全一致",
      mat["conflict_pair_count"] == exp["conflict_pair_count"] and got_pairs == exp_pairs,
      {"expect": exp_pairs, "got": got_pairs})
check("T1 矩阵对称：row[a][b] == row[b][a] 且自反对角为 None",
      all(mat["matrix"][p][q] == mat["matrix"][q][p] for p in mat["matrix"] for q in mat["matrix"])
      and all(mat["matrix"][p][p] is None for p in mat["matrix"]))
check("T1 冲突对覆盖 ≥3 种重叠种类（scene/window/asset/target 至少各出现一次）",
      len({k for c in mat["pairs"] for k in c["kinds"]}) >= 3,
      sorted({k for c in mat["pairs"] for k in c["kinds"]}))

# ============================================================================
# T2 素材校验（真实 + 构造用例，只读）
# ============================================================================
print("\n== T2 素材真实校验 ==")
if V9_REPORT.is_file():
    v9 = json.loads(V9_REPORT.read_text(encoding="utf-8"))
    ver = {v["asset_id"]: v for v in v9["asset_verification"]}
    for case in TRUTH["asset_cases"]:
        v = ver.get(case["asset_id"])
        check("T2 {}".format(case["asset_id"]),
              bool(v) and v["code"] == case["expect_code"]
              and (v["status"] == case["expect_status"]) and (v["constructed"] == case["constructed"]),
              {"expect": (case["expect_status"], case["expect_code"]), "got": v})
    real = [v for v in v9["asset_verification"] if not v["constructed"]]
    check("T2 真实素材：文件中转出的候选全部 ASSET_OK（存在 + sha256 一致 + 可解码）",
          len(real) == 5 and all(v["status"] == "ok" and v["code"] == "ASSET_OK" for v in real)
          and all(v["actual_sha256"] == v["recorded_sha256"] for v in real),
          {"real": [(v["asset_id"], v["code"]) for v in real]})
    check("T2 真实素材校验均记录了实际 sha256（不是只信索引声明）",
          all(len(v["actual_sha256"] or "") == 64 for v in real))
    check("T2 许可门禁沿用冻结口径：本地 ingest 不适用门禁、外部素材受限/未清才拦截",
          all(v["license_gate_applies"] is False for v in real
              if v["asset_id"] in ("asset_23e71bc8a864", "asset_3f0b94a3f2ac",
                                   "asset_30dd89a16713")))
else:
    skip("T2 素材校验", "缺少 {}".format(V9_REPORT.name))
_static = (ROOT / "src" / "video_studio" / "ops" / "execution.py").read_text(encoding="utf-8")
_st_tree = _ast.parse(_static)


def _call_order(fn_name, callee_snippets):
    fn = next((n for n in _ast.walk(_st_tree)
               if isinstance(n, _ast.FunctionDef) and n.name == fn_name), None)
    lines = {}
    if fn is not None:
        for node in _ast.walk(fn):
            if isinstance(node, _ast.Call):
                seg = _ast.get_source_segment(_static, node.func) or ""
                for s in callee_snippets:
                    if s in seg and s not in lines:
                        lines[s] = node.lineno
    return lines


_order = _call_order("_execute_asset_change", ["verify_asset_candidate", "_encode_still_segment",
                                               "_splice_window"])
check("T2 静态：素材校验失败一律不进入渲染（同一函数内 verify 调用行号 < 渲染调用行号，"
      "且无替代素材分支）",
      bool(_order) and _order.get("verify_asset_candidate", 10 ** 9)
      < _order.get("_encode_still_segment", 0)
      and "fallback_asset" not in _static and "substitute" not in _static, _order)

# ============================================================================
# T3 批量一致性
# ============================================================================
print("\n== T3 批量门禁/一致性 ==")


def batch_of(case):
    same = bool(case.get("same_scene"))
    props = []
    for name in case["proposals"]:
        scenes = ("S20",) if (name == "P1" or same) else ("S21",)
        pid = "rp-" + name
        props.append(mkprops(pid, scenes=scenes,
                             window=(1405.0, 1465.0) if (name == "P1" or same)
                             else (1465.0, 1532.0)))
    if case.get("film_wide"):                       # 先改再批准 ⇒ 审批绑定"全片重写"版本
        props = [({**p, "affected_scope": {**p["affected_scope"], "film_wide": True}}
                  if p["proposal_id"] in ["rp-" + x for x in case["film_wide"]] else p)
                 for p in props]
    aps = [approve(p) for p in props if p["proposal_id"] in ["rp-" + x for x in case["approve"]]]
    aps += [approve(p, "REJECT") for p in props
            if p["proposal_id"] in ["rp-" + x for x in case.get("reject", [])]]
    if case.get("tamper"):                          # 批准之后再改 ⇒ 必须 BLOCKED_TAMPERED
        props = [({**p, "proposed_change": {"what": "被改", "how": "全片重做", "params": {}}}
                  if p["proposal_id"] in ["rp-" + x for x in case["tamper"]] else p) for p in props]
    led = []
    for name in case.get("ledger_executed", []):
        p = next(x for x in props if x["proposal_id"] == "rp-" + name)
        led.append({"proposal_id": p["proposal_id"], "proposal_sha256": EX.proposal_sha256(p),
                    "state": "SUCCEEDED"})
    return props, aps, led


for case in TRUTH["batch_cases"]:
    props, aps, led = batch_of(case)
    g = EX.gate_batch(props, aps, ledger_entries=led)
    got = {p["proposal_id"]: g["decisions"][p["proposal_id"]]["code"] for p in props}
    want = {"rp-" + k: v for k, v in case["expect"].items()}
    check("T3 {}".format(case["id"]), got == want, {"expect": want, "got": got, "why": case["why"]})

_props, _aps, _led = batch_of({"id": "BT-3", "approve": ["P1", "P2"], "proposals": ["P1", "P2"],
                               "expect": {}})
_g = EX.gate_batch(_props, _aps, ledger_entries=_led)
check("T3 冲突阻断记录带 requires_human_reapproval=True 且列出对手",
      all(v.get("requires_human_reapproval") is True and v.get("conflict_with")
          for k, v in _g["decisions"].items() if v["code"] == "BLOCKED_CONFLICT"))
check("T3 阻断者 executor_invoked=False（不调用执行器）",
      all(v.get("executor_invoked") is False for v in _g["decisions"].values()
          if not v.get("allowed")))

# ============================================================================
# T4 真实 v9 证据
# ============================================================================
print("\n== T4 真实 v9 受控执行证据 ==")
if not V9_REPORT.is_file():
    skip("T4 v9 证据", "缺少 {}".format(V9_REPORT.name))
else:
    v9 = json.loads(V9_REPORT.read_text(encoding="utf-8"))
    exp = TRUTH["v9_expect"]
    check("T4a 阶段/schema 与关闭对象正确",
          v9.get("stage") == "6-B/M5" and v9.get("schema") == "revision-execution-run-v2"
          and set(v9.get("closes_pending") or []) == set(TRUTH["closes_pending"]))
    batches = {b["batch"]: b for b in v9["batches"]}
    for name, key in (("batch1", "batch1"), ("batch1_retry", "batch1_retry"),
                      ("batch2_overlap", "batch2_overlap")):
        labels = {}
        for r in batches[name]["records"]:
            labels[r["proposal_label"]] = r["state"]
        want = exp[key]
        ok = all(labels.get(k) == v for k, v in want.items())
        if name == "batch1":
            ok = ok and labels.get("M5-A1-replace-S20") == "SUCCEEDED" \
                and labels.get("M5-D1-replace-S21") == "SUCCEEDED"
        check("T4b {} 状态与真值一致".format(name), ok,
              {"expect": want, "got": labels})
    check("T4c batch1 无可执行集合内的假阻断（未批准/被拒方案未拖住已批准方案）",
          batches["batch1"]["gate_blocked_conflict"] == exp["batch1_blocked_conflict"]
          and batches["batch1"]["gate_blocked_conflict"] == [],
          batches["batch1"]["gate_blocked_conflict"])
    check("T4d 冲突批 3 条全部 BLOCKED_CONFLICT 且执行器未被调用",
          set(batches["batch2_overlap"]["gate_blocked_conflict"])
          == {r["proposal_id"] for r in batches["batch2_overlap"]["records"]}
          and all(r.get("executor_invoked") is False
                  for r in batches["batch2_overlap"]["records"]),
          batches["batch2_overlap"]["gate_blocked_conflict"])
    # 素材 E2E
    e2e = {e["proposal_label"]: e for e in v9["asset_e2e"]}
    for want in exp["asset_e2e"]:
        e = e2e.get(want["proposal_label"])
        ev = (e or {}).get("asset_evidence") or {}
        check("T4e {} 真实素材 E2E（抽帧比对 replaced=True、相关度达标且优于原素材）".format(
            want["proposal_label"]),
            bool(e) and e["state"] == "SUCCEEDED" and ev.get("asset_id") == want["asset_id"]
            and ev.get("prev_asset_id") == want["prev_asset_id"]
            and ev.get("replaced") is True
            and (ev.get("corr_new_mean") or -9) >= want["min_corr_new"]
            and (ev.get("corr_prev_mean") is None
                 or ev.get("corr_prev_mean") <= want["max_corr_prev"]),
            {"asset": ev.get("asset_id"), "corr_new": ev.get("corr_new_mean"),
             "corr_prev": ev.get("corr_prev_mean"), "replaced": ev.get("replaced")})
    for e in v9["asset_e2e"]:
        ev = e["asset_evidence"]
        check("T4f {} 抽帧比对为只读度量且给出阈值/边距".format(e["proposal_label"]),
              ev.get("min_corr") == 0.30 and ev.get("argmax_margin") == 0.15
              and len(ev.get("samples") or []) == 3
              and all(s.get("vs_new") is not None for s in ev["samples"]))
    check("T4g 执行后**强制重跑 PI-1…PI-6**（与真值一致，PI 仍 BLOCKED）",
          all(e["pi_metrics"] and e["pi_gate_outcome"] == exp["pi"]["pi_gate_outcome"]
              and {k: v["state"] for k, v in e["pi_metrics"].items()} == exp["pi"]["v9_pi_states"]
              for e in v9["asset_e2e"]),
          [(e["proposal_label"], e["pi_gate_outcome"]) for e in v9["asset_e2e"]])
    check("T4h DQ 复核仍 advisory（只读推演时间轴 + 未写回）",
          all(e["timeline_projection"] and e["timeline_projection"]["written_back"] is False
              and e["timeline_projection"]["sandbox_only"] is True for e in v9["asset_e2e"]))
    # DQ-2 推演数值：A1 换用已在片中的素材 ⇒ 唯一素材仍 4；D1 换用未用过的新素材 ⇒ 4→5
    _succ = {r["proposal_label"]: ((r.get("recheck") or {}).get("dq_details") or {}).get("DQ-2")
             for b in v9["batches"] for r in b["records"] if r["state"] == "SUCCEEDED"}
    check("T4h2 DQ-2 推演数值符合真值（部分改善但未达阈值 ⇒ 仍 FAIL，不谎报改善）",
          _succ.get("M5-A1-replace-S20", {}).get("unique_assets")
          == exp["projection"]["M5-A1-replace-S20"]["unique_assets"]
          and _succ.get("M5-D1-replace-S21", {}).get("unique_assets")
          == exp["projection"]["M5-D1-replace-S21"]["unique_assets"]
          and all(v.get("state") == "FAIL" for v in _succ.values()),
          _succ)
    check("T4i 成功者**全部**带真实素材证据（无『假成功』）",
          v9["summary"]["succeeded_without_real_asset_evidence"] == []
          and len(v9["summary"]["executed_succeeded"]) == 2)
    check("T4j 未批准却执行 = 空、自动批准 = false、已提升 = 空",
          v9["summary"]["auto_approved"] is False and v9["summary"]["promoted"] == []
          and all(r["state"] != "SUCCEEDED" or r.get("approval_ref")
                  for b in v9["batches"] for r in b["records"]))
    check("T4k 审批/执行两条台账链完整且 seq 唯一连续",
          v9["summary"]["ledger"]["approvals"]["chain_ok"] is True
          and v9["summary"]["ledger"]["executions"]["chain_ok"] is True
          and v9["summary"]["ledger"]["executions"]["unique_seq"]
          == v9["summary"]["ledger"]["executions"]["entries"]
          == exp["ledger_entries"])
    ro = v9["read_only_evidence"]
    check("T4l DB / v9 母版 / v9 output 目录零改动，且产物只在沙箱内",
          ro["db_unchanged"] and ro["v9_master_unchanged"] and ro["v9_output_dir_unchanged"]
          and ro["project_files_touched"] == [] and ro["sandbox_only_outputs"] is True,
          {k: ro[k] for k in ("db_unchanged", "v9_master_unchanged",
                              "v9_output_dir_unchanged", "sandbox_only_outputs")})
    check("T4m 母版 sha256 与冻结记录一致（未被覆盖）",
          ro["v9_master_sha256_after"] == V9_FILM_SHA == sha(FILM))
    check("T4n 构造用例（缺失/sha 不符/不可解码/许可受限/未清）均已登记且标注 constructed",
          len(v9["asset_index"]["constructed_cases"]) == 5
          and all(v9["asset_index"]["records"][a].get("constructed") is True
                  for a in v9["asset_index"]["constructed_cases"]))
    check("T4o 台账中的执行记录数 == 21（3 批），且不含任何未批准成功记录",
          len(EX.load_ledger(V9_EXECS)) == exp["ledger_entries"]
          and all(e["state"] != "SUCCEEDED" or e.get("approval_ref")
                  for e in EX.load_ledger(V9_EXECS)))
    check("T4p 审批记录均非自动批准且绑定 proposal_id + proposal_sha256",
          all(a.get("auto_approved") is False and a.get("proposal_id") and a.get("proposal_sha256")
              for a in EX.load_ledger(V9_APPROVALS)))

# ============================================================================
# T5 并发（同进程锁）
# ============================================================================
print("\n== T5 并发一致性 ==")


def _fake_exec(ctx, p):
    f = TMP / "out_{}.txt".format(p["proposal_id"])
    f.write_text("x", encoding="utf-8")
    return {"steps": [{"step": "write", "out": f.name}],
            "outputs": [{"path": str(f), "sha256": sha(f)}]}


def _fake_recheck(ctx, p, res):
    return {"pi_metrics": {"PI-1": {"state": "PASS"}}, "dq_metrics": {"DQ-2": "FAIL"},
            "pi_gate_outcome": "PASS", "read_only": True}


_led = TMP / "conc.jsonl"
_lock = threading.Lock()
_p1 = mkprops("rp-conc-1", scenes=("S20",), window=(1405.0, 1465.0))
_p2 = mkprops("rp-conc-2", scenes=("S21",), window=(1465.0, 1532.0))
_aps2 = [approve(_p1), approve(_p2)]
_res = {}


def _run(key, prop):
    _res[key] = EX.execute_batch([prop], _aps2, {"replace_asset": _fake_exec}, {}, 
                                 recheck=_fake_recheck, ledger=_led, lock=_lock)


_t1 = threading.Thread(target=_run, args=("a", _p1))
_t2 = threading.Thread(target=_run, args=("b", _p2))
_t1.start(); _t2.start(); _t1.join(); _t2.join()
_entries = EX.load_ledger(_led)
check("T5 两条互不重叠方案并发执行 ⇒ 都成功",
      _res["a"]["states"]["rp-conc-1"] == "SUCCEEDED"
      and _res["b"]["states"]["rp-conc-2"] == "SUCCEEDED",
      {k: v["states"] for k, v in _res.items()})
check("T5 并发落账链完整：seq 连续唯一、chain_ok",
      EX.verify_chain(_entries)["ok"] and [e["seq"] for e in _entries] == [1, 2],
      [e["seq"] for e in _entries])
_led2 = TMP / "conc2.jsonl"
_res2 = {}
_psame = mkprops("rp-same-1", scenes=("S20",), window=(1405.0, 1465.0))


def _run_same(key):
    _res2[key] = EX.execute_batch([_psame], [approve(_psame)], {"replace_asset": _fake_exec}, {},
                                  recheck=_fake_recheck, ledger=_led2, lock=_lock)


_ta = threading.Thread(target=_run_same, args=("a",))
_tb = threading.Thread(target=_run_same, args=("b",))
_ta.start(); _tb.start(); _ta.join(); _tb.join()
_states2 = sorted(v["states"]["rp-same-1"] for v in _res2.values())
check("T5 同一方案并发提交 ⇒ 一条 SUCCEEDED、一条 BLOCKED_ALREADY_EXECUTED（不重复执行）",
      _states2 == ["BLOCKED_ALREADY_EXECUTED", "SUCCEEDED"], _states2)

# ============================================================================
# T6 静态零自动化
# ============================================================================
print("\n== T6 静态零自动化 ==")
_core_src = (ROOT / "src" / "video_studio" / "core" / "execution.py").read_text(encoding="utf-8")
_tree = _ast.parse(_core_src)
_names = [n.name for n in _ast.walk(_tree) if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef))]
check("T6a 静态：无自动合并/自动排序/自动扩范围/自动批准函数",
      not [n for n in _names if n.startswith("auto_") or n in
           ("merge_proposals", "reorder_proposals", "expand_scope", "approve_all",
            "auto_approve", "plan_all")], _names)
check("T6b 静态：无『批量自动执行全部』入口（execute_all/apply_all 不存在）",
      "execute_all" not in _core_src and "apply_all" not in _core_src)
check("T6c 静态：core 层仍不 import DB/进程（执行器由调用方注入；冲突判定为纯逻辑）",
      "import sqlite3" not in _core_src and "import subprocess" not in _core_src
      and "os.system" not in _core_src)
# T6d 运行期：冲突阻断**不修改** proposal（逐字节不变），也不产生任何输出
_cp = mkprops("rp-immut-1", scenes=("S20",), window=(1405.0, 1465.0))
_cq = mkprops("rp-immut-2", scenes=("S20",), window=(1405.0, 1465.0))
_cp_txt = json.dumps(_cp, sort_keys=True, ensure_ascii=False)
_res_imm = EX.execute_batch([_cp, _cq], [approve(_cp), approve(_cq)],
                            {"replace_asset": _fake_exec}, {}, recheck=_fake_recheck)
check("T6d 运行期：冲突阻断不修改 proposal、不调用执行器、不产出任何 outputs",
      json.dumps(_cp, sort_keys=True, ensure_ascii=False) == _cp_txt
      and _res_imm["executor_invocations"] == []
      and all(r["outputs"] == [] for r in _res_imm["records"]))
check("T6e 运行期：批量执行对未见过的 action 仍返回 UNSUPPORTED_ACTION（不伪造执行）",
      EX.execute_batch([mkprops("rp-unk", action="reorder_scenes")], [approve(mkprops("rp-unk", action="reorder_scenes"))],
                       {}, {}, recheck=_fake_recheck)["states"]["rp-unk"] == "UNSUPPORTED_ACTION")

shutil.rmtree(TMP, ignore_errors=True)
print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
sys.exit(1 if FAIL else 0)
