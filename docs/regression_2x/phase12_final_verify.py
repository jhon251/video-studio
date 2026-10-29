# -*- coding: utf-8 -*-
"""Phase 12 收尾核验：报告台账 ↔ 实际文件；登记条目；前后对照事实；回归；不可变；config 零改动。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

ledger = {}
for line in (R / "docs" / "regression_2x" / "PHASE12_REPORT.md").read_text(
        encoding="utf-8").splitlines():
    if line.startswith("| ") and line.count("|") >= 3 and "`" in line:
        parts = [p.strip() for p in line.strip("|").split("|")]
        if len(parts) >= 2:
            first = parts[0]
            name = first.split("`")[1].strip() if "`" in first else first.strip()
            h = parts[1].strip("` ")
            if len(h) == 64 and all(c in "0123456789abcdef" for c in h):
                ledger[name] = h
bad = []
for f, h in ledger.items():
    p = R / f
    if not p.is_file():
        bad.append((f, "文件不存在"))
    elif hashlib.sha256(p.read_bytes()).hexdigest() != h:
        bad.append((f, "哈希不一致"))
print("报告台账条目数:", len(ledger), "| 不一致:", bad or "NONE")

st = (R / "STATUS.md").read_text(encoding="utf-8")
cl = (R / "CHANGELOG.md").read_text(encoding="utf-8")
print("STATUS 含 Phase 12:", "Phase 12（2026-09-30）素材索引许可数据 join" in st)
print("STATUS 保留 Phase 7–11:", all(k in st for k in ("Phase 11（2026-09-30）", "Phase 10（2026-09-30）",
                                                       "Phase 9（2026-09-30）", "Phase 8（2026-09-30）",
                                                       "差异登记（Phase 7）")))
print("CHANGELOG 含 Phase 12:", "## Phase 12 — 素材索引许可数据 join" in cl)

cfg = hashlib.sha256((R / "config" / "config.json").read_bytes()).hexdigest()
print("config.json 零改动:", cfg.startswith("7b03424846f1"))
cov = json.loads((L / "phase12_coverage_after.json").read_text(encoding="utf-8"))
print("臂 A 向后兼容:", json.dumps(cov["arm_a_no_overlay"]["backward_compatible"], ensure_ascii=False))
print("臂 A→B 覆盖:", json.dumps(cov["arm_a_counts"]["coverage_counts"], ensure_ascii=False), "->",
      json.dumps(cov["arm_b_with_overlay"]["counts"]["coverage_counts"], ensure_ascii=False))
print("解锁场景:", cov["scenes_unlocked"], "| S05:", cov["s05_replace_kept_as_proposal"])
print("零执行:", json.dumps(cov["execution"], ensure_ascii=False))
inv = json.loads((L / "phase12_license_sources.json").read_text(encoding="utf-8"))
print("三态:", inv["counts"], "| 索引零改动证据:", inv["overlay"]["artifact_hash"][:16])
suites = json.loads((L / "suites_summary.json").read_text(encoding="utf-8"))
print("回归:", len(suites), "套件 | rc!=0:", [x["suite"] for x in suites if x["rc"] != 0] or "NONE")
im = json.loads((L / "phase12_immutable_check.json").read_text(encoding="utf-8"))
print("不可变:", im["verdict"], "| 授权变更已登记:", im["authorized_changes"]["ops_visual_binding_py"]["changed"])
