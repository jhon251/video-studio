# -*- coding: utf-8 -*-
"""6-B/M1 —— DQ 真值集**冻结** + 覆盖矩阵/分类统计（幂等；只写真值集自身与冻结记录）。

  1. 计算 `tests/fixtures/directorial_quality_truth_v1.json` 的**规范化 sha256**（排除 `frozen_sha256` 自身）；
  2. 写回该字段（内容变化 ⇒ 值变化 ⇒ 回归会报"改真值未重冻结"）；
  3. 统计：用例数、四态分布、机械/语义分类、覆盖项映射、FAIL 证据契约；
  4. 写入 `logs/phase6b_m1_truth_freeze.json` 供测试与报告引用。

用法: python docs/regression_2x/phase6b_m1_build_truth.py
"""
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
TRUTH = ROOT / "tests" / "fixtures" / "directorial_quality_truth_v1.json"


def canonical_sha(obj: dict) -> str:
    payload = {k: v for k, v in obj.items() if k != "frozen_sha256"}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


t = json.loads(TRUTH.read_text(encoding="utf-8"))
sha_before = canonical_sha(t)
if t.get("frozen_sha256") != sha_before:
    t["frozen_sha256"] = sha_before
    TRUTH.write_text(json.dumps(t, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
sha_after = canonical_sha(json.loads(TRUTH.read_text(encoding="utf-8")))
assert sha_after == sha_before, "写回冻结值后规范化 sha 变化（自指）"

states = Counter(c["expect"]["state"] for c in t["cases"])
stateful = {k: v for k, v in states.items()}
summ = Counter(c["expect"]["overall"] for c in t["summarize_cases"])
record = {
    "schema": "directorial-quality-truth-freeze-v1",
    "stage": "6-B/M1",
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "truth_path": TRUTH.relative_to(ROOT).as_posix(),
    "truth_canonical_sha256": sha_before,
    "truth_file_sha256": file_sha(TRUTH),
    "case_count": len(t["cases"]),
    "case_state_distribution": stateful,
    "summarize_case_count": len(t["summarize_cases"]),
    "summarize_overall_distribution": dict(summ),
    "coverage_map": t["coverage_map"],
    "mechanical_vs_semantic": t["mechanical_vs_semantic"],
    "frozen_policy": t["frozen_policy"],
    "fail_evidence_contract": t["fail_evidence_contract"],
    "v9_expected_states": t["v9_real_case"]["expect_states"],
    "v9_rediscovery_expect": {r["id"]: r["re_discovery"]
                              for r in t["v9_real_case"]["human_findings_rediscovery"]},
    "documentation_discrepancy_recorded": bool(t.get("documentation_discrepancy")),
    "help": "改真值集后重跑本脚本会刷新 frozen_sha256（= 一次可审计的改真值动作）；"
            "只想校验请运行 tests/dq_truth_test.py",
}
(LOGS / "phase6b_m1_truth_freeze.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("truth canonical sha256:", sha_before)
print("cases:", len(t["cases"]), "| 状态分布:", stateful)
print("summarize 用例:", len(t["summarize_cases"]), "| 分布:", dict(summ))
print("覆盖映射:", json.dumps(t["coverage_map"], ensure_ascii=False)[:200])
print("json ->", LOGS / "phase6b_m1_truth_freeze.json")
