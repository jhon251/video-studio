# -*- coding: utf-8 -*-
"""6-B/M2 —— **Human Review Bridge 冻结真值集回归**（只读 + append-only + 零执行）。

覆盖：
  T0 真值集冻结校验（规范化 sha256 自锚点 + 词汇/语义/必需字段/UNKNOWN 策略）；
  T1 决策构造的合法性：ACCEPT/REJECT/DEFER 均可；非法词、缺字段、**对 UNKNOWN 写 ACCEPT** 必须被拒；
  T2 append-only 台账：哈希链校验 + 三类篡改（改条目/删中间/换序）均被检出；
  T3 汇总不变量：UNKNOWN 只走 DEFER、孤儿决策/无锚点 item 报告、类级决策覆盖实例 finding；
  T4 **真实 v9 闭环**：7 项 M1 发现全覆盖、ACCEPT=0、UNRESOLVED=0、链完整、零执行；
  T5 **零执行证明**：静态（无写库/写产物/阻断形态；无 agent 引用）+ 运行期（DB/成片/项目目录零改动）。

用法: python tests/review_truth_test.py
"""
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
from video_studio.ops import review as ops_review  # noqa: E402

TRUTH_PATH = ROOT / "tests" / "fixtures" / "human_review_truth_v1.json"
FREEZE_REC = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m2_truth_freeze.json"
LEDGER = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m2_review_ledger_v9.jsonl"
REPORT = ROOT / "docs" / "regression_2x" / "logs" / "phase6b_m2_review_v9.json"
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
    (SKIP).append(name)
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
TMP = Path(tempfile.mkdtemp(prefix="vs_m2_review_"))

# ============================================================================
# T0 —— 冻结校验
# ============================================================================
print("== T0 冻结校验 ==")
check("T0a schema/阶段正确（human-review-truth-v1 / 6-B/M2）",
      TRUTH.get("schema") == "human-review-truth-v1" and TRUTH.get("stage") == "6-B/M2",
      TRUTH.get("schema"))
check("T0b 规范化 sha256 与文件内冻结锚点一致", TRUTH.get("frozen_sha256") == truth_sha,
      {"live": truth_sha, "frozen": TRUTH.get("frozen_sha256")})
check("T0c 决策词汇与代码一致（ACCEPT/REJECT/DEFER）",
      list(TRUTH["decision_vocabulary"]) == list(HR.DECISIONS), HR.DECISIONS)
check("T0d 决策语义与代码一致（REJECT = 建议需要修改，非执行）",
      all(TRUTH["decision_semantics"][k] == HR.DECISION_SEMANTICS[k] for k in HR.DECISIONS))
check("T0e 必需字段与代码一致", list(TRUTH["required_decision_fields"])
      == list(HR.REQUIRED_DECISION_FIELDS), HR.REQUIRED_DECISION_FIELDS)
check("T0f UNKNOWN 策略与代码一致（不可证 ⇒ DEFER，禁止 ACCEPT）",
      tuple(TRUTH["unknown_policy"]["unprovable_states"]) == tuple(HR.UNPROVABLE_STATES)
      and TRUTH["unknown_policy"]["accept_forbidden"] is True
      and TRUTH["unknown_policy"]["default_routing"] == "DEFER")
if FREEZE_REC.is_file():
    fr = json.loads(FREEZE_REC.read_text(encoding="utf-8"))
    check("T0g 冻结记录中的 sha 与当前真值集一致",
          fr.get("truth_canonical_sha256") == truth_sha,
          {"live": truth_sha, "recorded": fr.get("truth_canonical_sha256")})
else:
    skip("T0g 冻结记录核对", "缺少 {}（先运行 phase6b_m2_build_truth.py）".format(FREEZE_REC.name))

# ============================================================================
# T1 —— 决策构造合法性
# ============================================================================
print("\n== T1 决策构造 ==")


def _item_from(spec):
    it = HR._item(PID, spec.get("metric"), spec.get("kind"), spec.get("severity", "FAIL"),
                  {"probe": True}, scene_id=spec.get("scene_id"),
                  asset_id=spec.get("asset_id"), window=spec.get("window"),
                  discriminator=json.dumps(spec, sort_keys=True)[:60])
    it["unprovable"] = bool(spec.get("unprovable"))
    it["default_routing"] = "DEFER" if it["unprovable"] else None
    return it


for case in TRUTH["cases"]:
    cid, exp = case["id"], case["expect"]
    item = _item_from(case["item"])
    try:
        rec = HR.make_decision(item, case["decision"], case.get("reason", "理由"),
                               "human:test", case.get("provenance", "truth-set"))
        err = None
    except Exception as exc:                                     # noqa: BLE001
        rec, err = None, str(exc)
    if exp.get("ok"):
        check("{} 合法决策被接受（{}）".format(cid, case["decision"]), rec is not None, err)
        if rec:
            check("{} 决策记录含全部必需字段 + 原始证据 + 零执行".format(cid),
                  all(rec.get(k) for k in HR.REQUIRED_DECISION_FIELDS)
                  and rec.get("executes_changes") is False, sorted(rec))
    else:
        check("{} 非法决策被拒绝（{}）".format(cid, exp.get("error_contains")),
              err is not None and exp["error_contains"] in err, err)
check("T1 决策记录带 decision_semantics（REJECT 明示为建议而非执行）",
      "建议需要修改" in HR.DECISION_SEMANTICS["REJECT"]
      and "不执行" in HR.DECISION_SEMANTICS["REJECT"])

# ============================================================================
# T2 —— append-only 台账 + 链校验 + 篡改检出
# ============================================================================
print("\n== T2 append-only 台账 ==")
led = TMP / "ledger.jsonl"
items = [_item_from({"metric": "DQ-{}".format(i), "kind": "k{}".format(i), "severity": "FAIL"})
         for i in (2, 3, 4)]
for i, it in enumerate(items):
    HR.append_decision(led, HR.make_decision(it, ("DEFER", "REJECT", "ACCEPT")[i],
                                             "理由{}".format(i), "human:test", "truth-set"))
entries = HR.load_ledger(led)
check("T2a 追加 3 条后链完整且 seq 连续",
      len(entries) == 3 and HR.verify_chain(entries)["ok"] is True,
      HR.verify_chain(entries))


def _tamper(name, mutate, expect_broken=True):
    p = TMP / "{}.jsonl".format(name)
    shutil.copy2(led, p)
    lines = p.read_text(encoding="utf-8").splitlines()
    mutate(lines, p)
    e = HR.load_ledger(p)
    v = HR.verify_chain(e)
    check("T2b 篡改检出：{}".format(name), v["ok"] is not expect_broken, v)


def _mod(lines, p):
    d = json.loads(lines[1])
    d["reason"] = "被改写"
    lines[1] = json.dumps(d, ensure_ascii=False)
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _del(lines, p):
    del lines[1]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _swap(lines, p):
    lines[0], lines[2] = lines[2], lines[0]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")


_tamper("modify_entry", _mod)
_tamper("delete_middle_entry", _del)
_tamper("reorder_entries", _swap)
HR.append_decision(led, HR.make_decision(items[0], "REJECT", "改判（追加新版本）", "human:test",
                                         "truth-set"))
e2 = HR.load_ledger(led)
check("T2c append-only：改判只追加历史（长度 3 → 4，历史条目逐字节不变）",
      len(e2) == 4 and [x["entry_sha256"] for x in e2[:3]] == [x["entry_sha256"] for x in entries]
      and HR.verify_chain(e2)["ok"], len(e2))

# ============================================================================
# T3 —— 汇总不变量
# ============================================================================
print("\n== T3 汇总不变量 ==")
u_item = _item_from({"metric": "DQ-1", "kind": "metric_state_unprovable", "severity": "UNKNOWN",
                     "scene_id": "S01", "unprovable": True})
f_item = _item_from({"metric": "DQ-3", "kind": "hold_exceeds_max", "severity": "FAIL",
                     "scene_id": "S07", "window": [385.0, 480.0]})
cls_item = _item_from({"metric": "DQ-3", "kind": "over_hold_share_exceeds", "severity": "FAIL"})
decs = [
    HR.make_decision(u_item, "DEFER", "不可证 ⇒ 人工复核", "human:test", "truth-set"),
    HR.make_decision(cls_item, "REJECT", "类级：保持时长超阈", "human:test", "truth-set",
                     covers=[{"metric": "DQ-3", "kind": "hold_exceeds_max"}]),
]
s = HR.summarize_review([u_item, f_item, cls_item], decs)
check("T3a UNKNOWN 项全部走 DEFER（未出现 ACCEPT/PASS）",
      s["unknown_routed_to_defer"] is True and s["unknown_accepted"] == [], s["rows"][0])
check("T3b 类级决策显式覆盖实例 finding（可追溯，不静默忽略）",
      s["covered_by_class_decision"] == 1 and f_item["finding_id"] not in s["unresolved"]
      and any(r["covered_by_decision"] == cls_item["finding_id"] for r in s["rows"]),
      {"covered": s["covered_by_class_decision"], "unresolved": s["unresolved"]})
check("T3c 无锚点 item 与孤儿决策均被显式报告（本例均为空）",
      s["untraceable_items"] == [] and s["decisions_without_item"] == [])
s_orphan = HR.summarize_review([u_item], decs)
check("T3d 孤儿决策被检出（决策找不到对应 finding）",
      len(s_orphan["decisions_without_item"]) == 1
      and s_orphan["decisions_without_item"][0] == cls_item["finding_id"],
      s_orphan["decisions_without_item"])
check("T3e 汇总恒有零执行标记（executed_actions 空、executes_changes=False）",
      s["executed_actions"] == [] and s["executes_changes"] is False and s["read_only"] is True)

# ============================================================================
# T4 —— 真实 v9 闭环
# ============================================================================
print("\n== T4 真实 v9 闭环 ==")
v9 = TRUTH["v9_closure_expect"]
if not (LEDGER.is_file() and REPORT.is_file()):
    skip("T4 v9 闭环", "缺少台账或闭环报告（先运行 phase6b_m2_v9_review.py）")
else:
    entries = HR.load_ledger(LEDGER)
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    summ = rep["summary"]
    check("T4a 台账链完整且条目数达标（{} ≥ {}）".format(len(entries), v9["min_decisions"]),
          HR.verify_chain(entries)["ok"] is True and len(entries) >= v9["min_decisions"],
          HR.verify_chain(entries))
    check("T4b review item 数达标（{} ≥ {}）".format(summ["items"], v9["min_items"]),
          summ["items"] >= v9["min_items"], summ["items"])
    cnt = {k: v for k, v in summ["decision_counts"].items() if v}
    check("T4c 决策计数满足真值（REJECT ≥7 / DEFER ≥4 / ACCEPT = 0）",
          cnt.get("REJECT", 0) >= v9["decision_counts_min"]["REJECT"]
          and cnt.get("DEFER", 0) >= v9["decision_counts_min"]["DEFER"]
          and cnt.get("ACCEPT", 0) == 0, cnt)
    check("T4d 无未决项、无 UNKNOWN 被 ACCEPT、UNKNOWN 全走 DEFER",
          len(summ["unresolved"]) == v9["unresolved"] and summ["unknown_accepted"] == []
          and summ["unknown_routed_to_defer"] is True,
          {"unresolved": summ["unresolved"][:5], "acc": summ["unknown_accepted"]})
    check("T4e 零执行：executed_actions 空、executes_changes=False（REJECT 仅为建议）",
          summ["executed_actions"] == [] and summ["executes_changes"] is False
          and rep["executes_changes"] is False)
    fl = rep.get("film_level_decision") or {}
    check("T4f 成片级决策 = REJECT 且 provenance 指向 KNOWN_ISSUES #67",
          fl.get("decision") == v9["film_level_decision"]
          and v9["film_level_provenance_contains"] in str(fl.get("provenance")),
          fl.get("provenance"))
    rows = {(r["metric"], r["kind"]) for r in summ["rows"]}
    dec_by = {(e.get("metric"), e.get("kind")): e for e in entries}
    missing = []
    for f in v9["m1_findings_must_be_covered"]:
        for kind in f["kinds"]:
            if (f["metric"], kind) not in rows:
                missing.append((f["id"], f["metric"], kind))
    check("T4g M1 重新发现的 7 项问题全部进入 review evidence（每项有 finding 行）",
          missing == [], missing)
    bad_dec = [f["id"] for f in v9["m1_findings_must_be_covered"]
               if f["kinds"][0] in {k for (m, k) in dec_by} and False]
    check("T4g-bis 7 项问题的主 finding 均有对应决策（可一一追溯）",
          all(any(k == kind and m == f["metric"] for (m, k) in dec_by for kind in f["kinds"])
              for f in v9["m1_findings_must_be_covered"]),
          sorted(dec_by, key=str))
    kinds_present = {k for (m, k) in dec_by if k}
    check("T4h 人工审计记录（非 DQ 派生）也纳入闭环（字幕断行残留 / HITL 理由不一致）",
          all(k in kinds_present for k in v9["human_audit_items_expected"]),
          sorted(kinds_present))
    check("T4i 每条决策都带 finding_id/decision/reason/decided_by/provenance 与原始证据",
          all(not HR.verify_decision(e) and e.get("original_evidence") for e in entries),
          [HR.verify_decision(e) for e in entries][:3])
    check("T4j 每条 finding 行都可定位（无锚点 item 为空，模块自检）",
          summ["untraceable_items"] == [], summ["untraceable_items"][:5])
    ro = rep["read_only_evidence"]
    check("T4k 闭环过程只读：DB 与成片 sha 前后一致",
          ro["db_unchanged"] is True and ro["film_unchanged"] is True and ro["project_files_touched"] == [])

# ============================================================================
# T5 —— 零执行证明（静态 + 运行期）
# ============================================================================
print("\n== T5 零执行证明 ==")
banned = TRUTH["non_execution_contract"]["forbidden_static_patterns"]
core_txt = (ROOT / "src/video_studio/core/human_review.py").read_text(encoding="utf-8")
ops_txt = (ROOT / "src/video_studio/ops/review.py").read_text(encoding="utf-8")
for rel, txt in (("core/human_review.py", core_txt), ("ops/review.py", ops_txt)):
    hits = [b for b in banned if b in txt
            and not (b == "TASK_BLOCKED" and "不接入 TASK_BLOCKED" in txt)]
    check("T5a 静态：{} 无写库/写产物/阻断形态".format(rel), hits == [], hits)
check("T5b 静态：core/human_review.py 不触碰 DB 与成片（无 sqlite3/subprocess/ffmpeg）",
      all(x not in core_txt for x in ("sqlite3", "subprocess", "ffmpeg", "ffprobe")))
import ast  # noqa: E402
refs, mentioned = [], []
for p in sorted((ROOT / "src" / "video_studio" / "agents").rglob("*.py")):
    txt = p.read_text(encoding="utf-8")
    if "human_review" in txt or "ops.review" in txt or "ops import review" in txt:
        mentioned.append(p.relative_to(ROOT).as_posix())
    try:
        tree = ast.parse(txt)
    except SyntaxError:
        continue
    for node in ast.walk(tree):
        mods = []
        if isinstance(node, ast.Import):
            mods = [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            mods = [node.module or ""]
        if any(m.endswith("core.human_review") or m.endswith("ops.review")
               or m.split(".")[-1] in ("human_review",) and "human_review" in m
               for m in mods):
            refs.append(p.relative_to(ROOT).as_posix())
check("T5c 静态：没有任何 agent **import** review 桥（不可能接进生产判定链/自动执行）",
      refs == [], refs)
check("T5c-bis 文本提及≠引用：agent 里出现的同名字样均为注释/HITL 语汇，经 AST 复核确认无 import",
      all(x not in refs for x in mentioned), {"mentioned": mentioned[:6], "imported": refs})
if FILM.is_file() and DB.is_file():
    db_b, film_b, man_b = sha(DB), sha(FILM), manifest(FILM.parent)
    led = TMP / "runtime_ledger.jsonl"
    rep_rt = ops_review.build_review_report(PID, DB, ROOT, CFG, film_task=FILM_TASK,
                                            evidence_path=EVIDENCE, ledger_path=str(led),
                                            measure_freeze=False)
    it0 = rep_rt["items"][0]
    HR.append_decision(led, HR.make_decision(it0, "REJECT", "运行期零执行证明", "human:test",
                                             "truth-set"))
    check("T5d 运行期：构建闭环报告 + 追加 REJECT 决策后，DB / 成片 / 项目目录逐字节不变",
          sha(DB) == db_b and sha(FILM) == film_b and manifest(FILM.parent) == man_b,
          {"db": sha(DB) == db_b, "film": sha(FILM) == film_b})
    check("T5e 运行期：报告显式声明零执行且不产生任何执行动作",
          rep_rt["executes_changes"] is False and rep_rt["summary"]["executed_actions"] == []
          and rep_rt["read_only"] is True)
else:
    skip("T5d/T5e 运行期零执行证明", "缺 v9 成片或 DB")

print("\n结果: {}/{} 通过   SKIP={}".format(len(PASS), len(PASS) + len(FAIL), SKIP))
if FAIL:
    print("失败项:", FAIL)
shutil.rmtree(TMP, ignore_errors=True)
sys.exit(0 if not FAIL else 1)
