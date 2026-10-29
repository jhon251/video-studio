# -*- coding: utf-8 -*-
"""Phase 14 收尾校验：交付物齐备性 + 边界（只读）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
sys.stdout.reconfigure(encoding="utf-8")

DELIVERABLES = [
    ("P14-1 provider", R / "src/video_studio/tools/vlm_judge.py"),
    ("P14-1/2 评测逻辑", R / "src/video_studio/tools/vlm_eval.py"),
    ("配置示例", R / "config/vlm_judge.example.json"),
    ("冻结真值集", R / "tests/fixtures/vlm_relevance_truth_v1.json"),
    ("门禁报告", R / "docs/regression_2x/logs/phase14_eval_report.json"),
    ("诊断变体报告", R / "docs/regression_2x/logs/phase14_eval_diag_anchor.json"),
    ("标签盘点", R / "docs/regression_2x/logs/phase14_label_inventory.json"),
    ("阶段报告", R / "docs/regression_2x/PHASE14_REPORT.md"),
    ("停放态回归日志", R / "docs/regression_2x/logs/phase14_suites_parked.log"),
    ("回归台账", R / "docs/regression_2x/logs/suites_summary.json"),
]
print("=" * 78)
print("§5 交付物")
print("=" * 78)
missing = []
for name, p in DELIVERABLES:
    if p.is_file():
        h = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        print("  OK   {:18s} {:>9,}B  sha256={}…  {}".format(
            name, p.stat().st_size, h, p.relative_to(R).as_posix()))
    else:
        missing.append(name)
        print("  MISS {:18s} {}".format(name, p))
print("  缺失:", missing or "无")

print()
print("=" * 78)
print("P14-3 应**未产出**（门禁 FAIL）")
print("=" * 78)
for p in (R / "docs/regression_2x/logs/phase14_na_resolution.json",):
    print("  {} exists = {}".format(p.name, p.is_file()))

print()
print("=" * 78)
print("边界核对")
print("=" * 78)
cfg = json.loads((R / "config" / "config.json").read_text(encoding="utf-8"))
print("  config.json 含 vlm_judge 键:", "vlm_judge" in json.dumps(cfg, ensure_ascii=False))
print("  config/vlm_judge.json enabled:", json.loads(
    (R / "config" / "vlm_judge.json").read_text(encoding="utf-8")).get("enabled"))
print("  config/render_motion.json sha256:", hashlib.sha256(
    (R / "config" / "render_motion.json").read_bytes()).hexdigest()[:16], "…")

# 生产链是否引用 vlm_judge（应为 0：未接线）
hits = []
for f in (R / "src" / "video_studio").rglob("*.py"):
    if f.name in ("vlm_judge.py", "vlm_eval.py"):
        continue
    t = f.read_text(encoding="utf-8", errors="replace")
    if "vlm_judge" in t or "vlm_eval" in t:
        hits.append(f.relative_to(R).as_posix())
print("  引用 vlm_judge/vlm_eval 的其它生产文件:", hits or "无（未接线 ✔）")

rep = json.loads((R / "docs/regression_2x/logs/phase14_eval_report.json")
                 .read_text(encoding="utf-8"))
print()
print("=" * 78)
print("门禁结论复核")
print("=" * 78)
print("  truth pairs      :", rep["truth"]["pair_count"],
      "| meets_min_pairs:", rep["truth"]["meets_min_pairs"])
print("  truth sha256     :", rep["truth"]["sha256"][:16], "…")
print("  prompt_version   :", rep["pairs"][0].get("machine_label") and "见产物")
print("  agreement        :", rep["results"]["agreement"])
print("  gate passed      :", rep["gate"]["passed"], "|", rep["gate"]["decision"])
print("  FP(人工IRR→机器REL):", len(rep["results"]["human_irrelevant_to_machine_relevant"]))
print("  cost             : ${:.4f} / ${:.2f}".format(
    rep["cost"]["spent_usd"], rep["cost"]["budget_usd"]))
print("  zero_promotion   :", rep["zero_promotion"])
