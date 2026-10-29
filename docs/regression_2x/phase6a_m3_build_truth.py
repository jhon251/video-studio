# -*- coding: utf-8 -*-
"""6-A/M3 —— 真值集**冻结**与覆盖矩阵生成（幂等、只写冻结记录与真值集自身）。

做了什么：
  1. 计算 v2 真值集的**规范化 sha256**（排除 `frozen_sha256` 字段本身，避免自指）；
  2. 把该值写回真值集 `frozen_sha256` 字段（内容变化 ⇒ 值变化 ⇒ 回归会报"改真值未重冻结"）；
  3. 记录 M1 真值集（v1）的 sha256（证明历史证据未被改写）；
  4. 生成覆盖矩阵（PI × 四态 → 用例 id）与用例分类计数；
  5. 写入 `logs/phase6a_m3_truth_freeze.json`（供 M3 测试与报告引用）。

用法: python docs/regression_2x/phase6a_m3_build_truth.py
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
V2 = ROOT / "tests" / "fixtures" / "production_integrity_truth_v2.json"
V1 = ROOT / "tests" / "fixtures" / "production_integrity_truth_v1.json"


def canonical_sha(obj: dict) -> str:
    payload = {k: v for k, v in obj.items() if k != "frozen_sha256"}
    blob = json.dumps(payload, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()


def file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


truth = json.loads(V2.read_text(encoding="utf-8"))
sha_before = canonical_sha(truth)
if truth.get("frozen_sha256") != sha_before:
    truth["frozen_sha256"] = sha_before
    V2.write_text(json.dumps(truth, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
sha_after = canonical_sha(json.loads(V2.read_text(encoding="utf-8")))
assert sha_after == sha_before, "写入冻结值后规范化 sha 发生变化（自指）"

cases = truth["cases"]
kinds = Counter(c["kind"] for c in cases)
matrix = truth["coverage_matrix_expected"]
cells = sum(len(v) for v in matrix.values())
filled = sum(1 for pi in matrix for st in matrix[pi] if matrix[pi][st])
unreachable = sum(1 for pi in matrix for st in ("PASS", "FAIL", "UNKNOWN", "NOT_ASSESSABLE")
                  if not truth["state_reachability"][pi][st])

record = {
    "schema": "production-integrity-truth-freeze-v1",
    "stage": "6-A/M3",
    "at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "v2_path": V2.relative_to(ROOT).as_posix(),
    "v2_canonical_sha256": sha_before,
    "v2_file_sha256": file_sha(V2),
    "v2_case_count": len(cases),
    "v2_case_kinds": dict(kinds),
    "v1_path": V1.relative_to(ROOT).as_posix(),
    "v1_sha256": file_sha(V1),
    "frozen_policy": truth["frozen_policy"],
    "frozen_gate_flags": truth["frozen_gate_flags"],
    "coverage_matrix": matrix,
    "coverage_cells_total": cells,
    "coverage_cells_filled": filled,
    "coverage_cells_unreachable_by_design": unreachable,
    "coverage_matrix_note": "PI-1/PI-2/PI-5 的 UNKNOWN 格按源码为**不可达**（缺数据一律 NOT_ASSESSABLE）；"
                            "PI-3/PI-4/PI-6 四态齐全；PI-3 的阈值等式在媒体层不可确定性分离（见真值集 boundary_notes）。",
    "help": "重跑本脚本会按当前真值集内容刷新 frozen_sha256；若只想校验，请运行 tests/integrity_truth_test.py",
}
(LOGS / "phase6a_m3_truth_freeze.json").write_text(json.dumps(record, ensure_ascii=False, indent=1),
                                                  encoding="utf-8")
print("v2 canonical sha256:", sha_before)
print("v2 file sha256     :", record["v2_file_sha256"])
print("v1 sha256          :", record["v1_sha256"])
print("cases:", len(cases), "|", dict(kinds))
print("矩阵格数:", cells, "| 已填:", filled, "| 设计上不可达:", unreachable)
print("json ->", LOGS / "phase6a_m3_truth_freeze.json")
