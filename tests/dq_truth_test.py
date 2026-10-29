# -*- coding: utf-8 -*-
"""6-B/M1 —— **Directorial Quality 冻结真值集回归**（只读；DQ 仍 advisory，不入生产判定链）。

覆盖：
  1. 真值集 `tests/fixtures/directorial_quality_truth_v1.json` 的冻结校验
     （规范化 sha256 自锚点 + 阈值快照 == 代码默认值 + 覆盖项映射齐备）；
  2. DQ-1…DQ-8 逐案行为（PASS/FAIL/UNKNOWN/NOT_ASSESSABLE + 阈值边界）；
  3. **FAIL 证据可回溯契约**：每个 FAIL 的 `findings` 非空且含 scene / asset / 时间区间 / 证据层锚点；
  4. **UNKNOWN ≠ PASS**：DQ-7 总评穷举断言 + 语义项单列；
  5. **机械可测 vs 需要语义/人审** 的分类断言；
  6. **advisory-only 静态 + 运行期证明**：DQ 模块不写 DB/产物、不含 TASK_BLOCKED/render_output、
     不被 agents 引用；对 v9 跑只读诊断后 DB 与项目目录逐字节不变；
  7. **真实 v9 只读审计**：复算状态/实测值，并核验 7 项人审发现的"再发现"结论
     （6 FULL + 1 PARTIAL，hook 保持 UNKNOWN 不伪造）。

用法: python tests/dq_truth_test.py
"""
import ast
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.stdout.reconfigure(encoding="utf-8")

from video_studio.core import direction as D  # noqa: E402
from video_studio.ops import direction as ops_direction  # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "directorial_quality_truth_v1.json"
FREEZE_REC = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m1_truth_freeze.json"
AUDIT = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m1_dq_v9.json"
DB = ROOT / "projects" / "video_studio.db"
CFG = json.loads((ROOT / "config" / "config.json").read_text(encoding="utf-8-sig"))
PID, FILM_TASK = "p_96efdc03e1aa", "t_d0a54bdf1810"
FILM = ROOT / "projects" / PID / "output" / "{}_draft.mp4".format(FILM_TASK)
EVIDENCE = "docs/regression_2x/logs/audit_p96efdc_mm.json"

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

# ============================================================================
# T0 —— 冻结校验
# ============================================================================
print("== T0 冻结校验 ==")
check("T0a schema/阶段正确（directorial-quality-truth-v1 / 6-B/M1）",
      TRUTH.get("schema") == "directorial-quality-truth-v1" and TRUTH.get("stage") == "6-B/M1",
      TRUTH.get("schema"))
check("T0b 规范化 sha256 与文件内冻结锚点一致（改真值必须显式重冻结）",
      TRUTH.get("frozen_sha256") == truth_sha,
      {"live": truth_sha, "frozen": TRUTH.get("frozen_sha256")})
_fp = dict(D.DEFAULT_POLICY)
_frozen = dict(TRUTH["frozen_policy"])
for k in ("outro_keywords", "core_keywords"):
    _fp[k], _frozen[k] = list(_fp[k]), list(_frozen[k])
check("T0c 冻结阈值快照 == 代码 DEFAULT_POLICY（不得为让 v9 变好而调阈值）",
      _fp == _frozen,
      {k: (_frozen.get(k), _fp.get(k)) for k in _fp if _frozen.get(k) != _fp.get(k)})
REQUIRED_COVERAGE = ["Hook", "素材重复/密度", "静态镜头", "场景变化", "视觉语义支撑",
                     "视觉高潮", "Outro"]
check("T0d 授权 7 个覆盖项在 coverage_map 里全部有映射（{}）".format("、".join(REQUIRED_COVERAGE)),
      all(k in (TRUTH.get("coverage_map") or {}) for k in REQUIRED_COVERAGE),
      sorted(TRUTH.get("coverage_map") or {}))
if FREEZE_REC.is_file():
    fr = json.loads(FREEZE_REC.read_text(encoding="utf-8"))
    check("T0e 冻结记录中的 sha 与当前真值集一致",
          fr.get("truth_canonical_sha256") == truth_sha,
          {"live": truth_sha, "recorded": fr.get("truth_canonical_sha256")})
else:
    skip("T0e 冻结记录核对", "缺少 {}（先运行 phase6b_m1_build_truth.py）".format(FREEZE_REC.name))
check("T0f 真值集内如实记录 6-A 审计正文与证据的秒数差异（不掩盖）",
      "documentation_discrepancy" in TRUTH
      and TRUTH["documentation_discrepancy"]["audit_evidence_per_asset_seconds"]
      != TRUTH["documentation_discrepancy"]["audit_prose_per_asset_seconds"])

# ============================================================================
# T1 —— 逐案行为断言 + FAIL 证据契约
# ============================================================================
print("\n== T1 逐案行为 ==")
ANCHOR_KEYS = set(TRUTH["fail_evidence_contract"]["required_anchor_keys_any_of"])


def build_timeline(spec):
    assets = spec.get("assets") or []
    holds = spec.get("holds") or [spec.get("hold_s", 10.0)] * len(assets)
    tl, t = [], 0.0
    for i, h in enumerate(holds):
        a = assets[i] if i < len(assets) else None
        tl.append({"scene_id": "S{:02d}".format(i + 1), "start_s": round(t, 3),
                   "end_s": round(t + h, 3),
                   "selected_asset": ({"asset_id": a} if a else None)})
        t += h
    return tl


def call_case(case):
    fn = case["fn"]
    a = dict(case["args"])
    tl = build_timeline(a.pop("timeline_spec")) if "timeline_spec" in a else None
    ev = a.pop("evidence", "__ABSENT__")
    script = a.pop("script", None)
    tail = a.pop("tail_silence_s", None)
    if fn == "hook_relevance":
        return D.hook_relevance(None if ev == "__ABSENT__" else ev)
    if fn in ("asset_reuse", "static_hold", "visual_density"):
        return {"asset_reuse": D.asset_reuse, "static_hold": D.static_hold,
                "visual_density": D.visual_density}[fn](tl, policy=None)
    if fn == "climax_coverage":
        return D.climax_coverage(script or [], tl or [],
                                 None if ev == "__ABSENT__" else ev)
    if fn == "ending_completeness":
        return D.ending_completeness(script or [], tl or [], tail,
                                     None if ev == "__ABSENT__" else ev)
    if fn == "narration_visual_support":
        return D.narration_visual_support(script or [], tl or [],
                                          None if ev == "__ABSENT__" else ev)
    raise ValueError("未知 fn: {}".format(fn))


def anchor_ok(findings):
    for f in findings or []:
        if isinstance(f, dict) and (set(f) & ANCHOR_KEYS):
            return True
    return False


for case in TRUTH["cases"]:
    cid = case["id"]
    res = call_case(case)
    exp = case["expect"]
    check("{} 状态 = {}".format(cid, exp["state"]), res.get("state") == exp["state"],
          {"got": res.get("state"), "detail": {k: res.get(k) for k in
                                               ("unique_assets", "max_asset_share",
                                                "semantic_state", "match_share")}})
    for k, v in exp.items():
        if k == "state":
            continue
        got = res.get(k)
        check("{} {} == {}".format(cid, k, v), got == v, {"got": got, "want": v})
    if exp["state"] == "FAIL":
        findings = res.get("findings") or []
        check("{} FAIL 具备非空 findings（证据可回溯）".format(cid), len(findings) > 0, findings)
        check("{} FAIL 的 findings 含可定位锚点".format(cid), anchor_ok(findings),
              [sorted(f) for f in findings[:3]])

# ============================================================================
# T2 —— DQ-7 总评：UNKNOWN 永不等于 PASS
# ============================================================================
print("\n== T2 DQ-7 总评 ==")
for case in TRUTH["summarize_cases"]:
    metrics = {k: {"state": v} for k, v in case["args"].items()}
    res = D.summarize_direction(metrics)
    for k, v in case["expect"].items():
        if k == "note":
            continue
        check("{} summary.{} == {}".format(case["id"], k, v), res.get(k) == v, res.get(k))
import itertools  # noqa: E402
_bad = []
for r in range(1, 5):
    for combo in itertools.combinations(D.STATES, r):
        if "UNKNOWN" not in combo and "NOT_ASSESSABLE" not in combo:
            continue
        metrics = {"DQ-{}".format(i + 2): {"state": s} for i, s in enumerate(combo)}
        if D.summarize_direction(metrics)["overall"] == "PASS":
            _bad.append(combo)
check("T2 穷举：含 UNKNOWN/NOT_ASSESSABLE 的任意组合 overall 绝不为 PASS", not _bad, _bad)
_sem = D.summarize_direction({"DQ-1": {"state": "UNKNOWN", "semantic": True},
                              "DQ-8": {"state": "UNKNOWN", "semantic": True},
                              "DQ-2": {"state": "PASS"}})
check("T2 语义项单列且 UNKNOWN 原样保留（不被折算成 PASS）",
      set(_sem["semantic_metrics"]) == {"DQ-1", "DQ-8"}
      and all(v == "UNKNOWN" for v in _sem["semantic_states"].values())
      and _sem["overall"] == "UNKNOWN", _sem)

# ============================================================================
# T3 —— 机械可测 vs 需要语义/人审
# ============================================================================
print("\n== T3 机械 vs 语义分类 ==")
_mech = TRUTH["mechanical_vs_semantic"]["mechanical"]
_semantic = TRUTH["mechanical_vs_semantic"]["semantic"]
check("T3 分类声明：机械项 = {}；语义项 = {}".format(_mech, _semantic),
      set(_mech) == {"DQ-2", "DQ-3", "DQ-4"} and "DQ-8" in _semantic and "DQ-1" in _semantic)
tl6 = build_timeline({"hold_s": 10.0, "assets": ["a1", "a2", "a3", "a4", "a5", "a6"]})
m2, m3, m4 = D.asset_reuse(tl6), D.static_hold(tl6), D.visual_density(tl6)
check("T3 机械项输出不含语义标记（semantic / semantic_state）",
      not any((m.get("semantic") or m.get("semantic_state")) for m in (m2, m3, m4)))
sc = [{"narration": "证明"}, {"narration": "检查"}]
ev = {"S01": {"judge": "UNKNOWN"}, "S02": {"judge": "UNKNOWN"}}
check("T3 语义项（DQ-1/DQ-8）输出带 semantic=True 且无证据时 NOT_ASSESSABLE",
      D.hook_relevance(ev).get("semantic") is True
      and D.narration_visual_support(sc, tl6[:2], ev).get("semantic") is True
      and D.narration_visual_support(sc, tl6[:2], None)["state"] == "NOT_ASSESSABLE")
check("T3 DQ-5/DQ-6 语义状态独立字段（semantic_state），不与结构状态混淆",
      "semantic_state" in D.climax_coverage(sc, tl6[:2], ev)
      and "semantic_state" in D.ending_completeness(sc, tl6[:2], 1.0, ev))

# ============================================================================
# T4 —— advisory-only（静态 + 运行期）
# ============================================================================
print("\n== T4 advisory-only 证明 ==")
ALLOWED = {"src/video_studio/core/direction.py", "src/video_studio/ops/direction.py",
           "src/video_studio/cli.py",
           # 6-B/M2：Human Review Bridge 只**读取** DQ 报告（不执行任何修改、不接生产判定链）
           "src/video_studio/ops/review.py",
           # 6-B/M4：受控执行编排在**人工批准 + 沙箱内执行之后**只读重跑 DQ 复核
           #   （advisory=True / enforced=False）。它同样**不得**接入生产判定链
           #   —— 该性质由下面的 T4a-2/T4a-3 单独证明（生产链不可达 + 无阻断形态）。
           "src/video_studio/ops/execution.py"}
refs = []
for p in sorted((ROOT / "src").rglob("*.py")):
    rel = p.relative_to(ROOT).as_posix()
    txt = p.read_text(encoding="utf-8")
    if "direction" in txt and rel not in ALLOWED:
        if "core import direction" in txt or "core import direction as" in txt \
                or "ops import direction" in txt or "ops.direction" in txt \
                or "core.direction" in txt:
            refs.append(rel)
check("T4a 静态：除 core/ops direction 自身与只读 CLI 外，**没有任何模块引用 DQ**"
      "（⇒ 不可能接入 TASK_BLOCKED / 改变 render_output）", refs == [], refs)
# 6-B/M4：白名单扩张后的**替代性强化证明**（不是放宽）
_agent_refs = []
for p in sorted((ROOT / "src" / "video_studio" / "agents").rglob("*.py")):
    txt = p.read_text(encoding="utf-8")
    if "import execution" in txt or "ops.execution" in txt or "ops import execution" in txt:
        _agent_refs.append(p.relative_to(ROOT).as_posix())
check("T4a-2 静态：**生产判定链（agents/）不可达执行层** —— 任何 agents 模块都不引用"
      " execution/ops.execution（⇒ 执行层不可能把 DQ 带进生产阻断判定）",
      _agent_refs == [], _agent_refs)
_ex_txt = (ROOT / "src/video_studio/ops/execution.py").read_text(encoding="utf-8")
_ex_banned = [b for b in ("write_artifact", "set_task_status", "emit(", "INSERT ", "UPDATE ",
                          "DELETE ", "TASK_BLOCKED", "create_task", "run_cycle")
              if b in _ex_txt]
check("T4a-3 静态：ops/execution.py 的 DQ 复核为**只读 advisory**（advisory=True / enforced=False），"
      "无写库/写产物/阻断调用形态，且无任何绕过人工审批的执行入口"
      "（沙箱写入约束由 maintenance_fixes_test M8e 静态证明）",
      _ex_banned == [] and "advisory" in _ex_txt and "\"enforced\": False" in _ex_txt
      and "auto_" not in _ex_txt, _ex_banned)
_banned = ("write_artifact", "set_task_status", "emit(", "INSERT ", "UPDATE ", "DELETE ",
           "unlink(", "rmtree(", "write_bytes")
_core_txt = (ROOT / "src/video_studio/core/direction.py").read_text(encoding="utf-8")
_ops_txt = (ROOT / "src/video_studio/ops/direction.py").read_text(encoding="utf-8")
for rel, txt in (("core/direction.py", _core_txt), ("ops/direction.py", _ops_txt)):
    hits = [b for b in _banned if b in txt]
    check("T4b 静态：{} 无写库/写产物/阻断调用形态（无 write_artifact/set_task_status/emit/SQL 写）"
          .format(rel), hits == [], hits)
    check("T4b 静态：{} 中 `TASK_BLOCKED` 至多出现 1 次且仅作为『不接入』声明".format(rel),
          txt.count("TASK_BLOCKED") <= 1
          and ("不接入 TASK_BLOCKED" in txt or "不接入 `TASK_BLOCKED`" in txt),
          txt.count("TASK_BLOCKED"))
check("T4b 静态：core/direction.py 不触碰 DB/文件写入（无 sqlite3 / open( / write_text）",
      all(x not in _core_txt for x in ("sqlite3", "open(", "write_text", "write_bytes")))
check("T4b 静态：ops/direction.py 唯一写文件处是**显式报告输出** write_report（不计入产物）",
      _ops_txt.count("write_text") == 1 and "def write_report" in _ops_txt,
      _ops_txt.count("write_text"))
check("T4c ops/direction 只以 mode=ro + query_only 读库",
      "mode=ro" in _ops_txt and "query_only" in _ops_txt)

if FILM.is_file() and DB.is_file():
    db_before, film_before = sha(DB), sha(FILM)
    out_before = manifest(FILM.parent)
    rep = ops_direction.build_direction_report(PID, DB, ROOT, CFG, film_task=FILM_TASK,
                                               evidence_path=EVIDENCE, measure_freeze=False)
    check("T4d 运行期：对 v9 跑只读诊断后 DB / 成片 / output 目录逐字节不变",
          sha(DB) == db_before and sha(FILM) == film_before
          and manifest(FILM.parent) == out_before,
          {"db": sha(DB) == db_before, "film": sha(FILM) == film_before})
else:
    rep = None
    skip("T4d 运行期只读证明", "缺 v9 成片或 DB")

# ============================================================================
# T5 —— 真实 v9 只读审计 + 人审发现再发现
# ============================================================================
print("\n== T5 真实 v9 只读审计 ==")
v9 = TRUTH["v9_real_case"]
if rep is None:
    skip("T5 v9 审计", "缺 v9 成片或 DB")
else:
    states = {k: v.get("state") for k, v in rep["metrics"].items()}
    check("T5a v9 七项 DQ 状态与冻结真值一致（{}）".format(v9["expect_states"]),
          all(states.get(k) == s for k, s in v9["expect_states"].items()), states)
    check("T5b v9 DQ-7 总评 = FAIL 且计数与真值一致",
          rep["summary"]["overall"] == v9["expect_summary"]["overall"]
          and {k: v for k, v in rep["summary"]["counts"].items() if v}
          == {k: v for k, v in v9["expect_summary"]["counts"].items() if v},
          rep["summary"]["counts"])
    mm, em = rep["metrics"], v9["expect_measurements"]
    check("T5c v9 DQ-2 实测（4 素材 / 最大占比 0.3329）",
          mm["DQ-2"]["unique_assets"] == em["DQ-2"]["unique_assets"]
          and abs(mm["DQ-2"]["max_asset_share"] - em["DQ-2"]["max_asset_share"]) < 0.001,
          mm["DQ-2"]["per_asset"])
    check("T5d v9 DQ-3 实测（均值 72.952 s / 最大 95 s / 21 镜超阈）",
          abs(mm["DQ-3"]["mean_hold_s"] - em["DQ-3"]["mean_hold_s"]) < 0.01
          and abs(mm["DQ-3"]["max_hold_s"] - em["DQ-3"]["max_hold_s"]) < 0.01
          and mm["DQ-3"]["holds_over_threshold"] == em["DQ-3"]["holds_over_threshold"],
          {k: mm["DQ-3"][k] for k in ("mean_hold_s", "max_hold_s", "holds_over_threshold")})
    check("T5e v9 DQ-4 实测（0.822 镜变/分钟 < 阈值 2.0）",
          abs(mm["DQ-4"]["scene_changes_per_min"] - em["DQ-4"]["scene_changes_per_min"]) < 0.001,
          mm["DQ-4"]["scene_changes_per_min"])
    check("T5f v9 DQ-5 实测（核心 20 镜 / 4 素材 / 语义 FAIL）",
          mm["DQ-5"]["core_scenes"] == em["DQ-5"]["core_scenes"]
          and mm["DQ-5"]["distinct_assets_in_core"] == em["DQ-5"]["distinct_assets_in_core"]
          and mm["DQ-5"]["semantic_state"] == em["DQ-5"]["semantic_state"],
          {k: mm["DQ-5"][k] for k in ("core_scenes", "distinct_assets_in_core", "semantic_state")})
    check("T5g v9 DQ-6 实测（outro 命中 0 / 尾部静音 570.869 s / 语义 UNKNOWN）",
          not mm["DQ-6"]["outro_keyword_hits"]
          and abs(mm["DQ-6"]["tail_silence_s"] - em["DQ-6"]["tail_silence_s"]) < 0.05
          and mm["DQ-6"]["semantic_state"] == em["DQ-6"]["semantic_state"],
          {k: mm["DQ-6"][k] for k in ("tail_silence_s", "semantic_state")})
    check("T5h v9 DQ-8 实测（MISMATCH 3 镜 / match_share 0.0595 / UNKNOWN 16 镜）",
          mm["DQ-8"]["mismatch_scene_count"] == em["DQ-8"]["mismatch_scene_count"]
          and abs(mm["DQ-8"]["match_share"] - em["DQ-8"]["match_share"]) < 0.001
          and mm["DQ-8"]["unknown_scene_count"] == em["DQ-8"]["unknown_scene_count"],
          {k: mm["DQ-8"][k] for k in ("mismatch_scene_count", "match_share",
                                      "unknown_scene_count")})
    mism = []
    for f in mm["DQ-8"].get("findings") or []:
        mism += [x.get("scene_id") for x in (f.get("scenes") or [])]
    check("T5i DQ-8 的 MISMATCH 镜头可定位到 scene（真值：S05/S11/S18）",
          mism == em["DQ-8"]["mismatch_scenes"], mism)
    if AUDIT.is_file():
        aud = json.loads(AUDIT.read_text(encoding="utf-8"))
        rc = aud["rediscovery_counts"]
        check("T5j 审计证据文件的再发现结论 = 6 FULL + 1 PARTIAL + 0 NO",
              rc == {"FULL": 6, "PARTIAL": 1, "NO": 0, "total": 7}, rc)
        byid = {r["id"]: r for r in aud["human_findings_rediscovery"]}
        check("T5k hook 发现如实标为 PARTIAL（DQ-1 = UNKNOWN，人工语义判定不伪造）",
              byid["H1-hook-misalignment"]["re_discovery"] == "PARTIAL"
              and byid["H1-hook-misalignment"]["measured_state"] == "UNKNOWN",
              byid["H1-hook-misalignment"]["measured_state"])
        check("T5l 其余 6 项人审发现全部 FULL 再发现且状态一致",
              all(byid[x]["re_discovery"] == "FULL" and byid[x]["state_match"]
                  for x in ("H2-visual-repetition", "H3-static-hold", "H4-visual-density",
                            "H5-semantic-support", "H6-no-visual-climax", "H7-ending-missing")),
              {k: (byid[k]["re_discovery"], byid[k]["state_match"]) for k in byid})
    else:
        skip("T5j-l 审计证据文件核对", "缺少 {}".format(AUDIT.name))

print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
sys.exit(0 if not FAIL else 1)
