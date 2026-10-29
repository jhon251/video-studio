# -*- coding: utf-8 -*-
"""Phase 16 收尾校验：交付物齐备性 + 边界（只读）。"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
PID = "p_96efdc03e1aa"
sys.stdout.reconfigure(encoding="utf-8")

DELIV = [
    ("P16-1 评测集（冻结）", R / "tests/fixtures/p16_negative_filter_eval_v1.json"),
    ("P16-1 验证报告", L / "phase16_negative_filter_report.json"),
    ("P16-1 结论", L / "phase16_p16_1_conclusion.json"),
    ("P16-2 登记台账", L / "phase16_local_registry.json"),
    ("P16-3 获取台账(逐请求)", L / "phase16_acquisition_ledger.json"),
    ("P16-3 获取件登记", L / "phase16_acquired_registry.json"),
    ("扩池候选池", L / "phase16_retrieval_payload.json"),
    ("裁切安全度证据", L / "phase16_crop_safety.json"),
    ("P16-5 DQ 复算", L / "phase16_dq_recompute.json"),
    ("停放态回归日志", L / "phase16_suites_parked.log"),
    ("PHASE16 报告", R / "docs/regression_2x/PHASE16_REPORT.md"),
]
print("=" * 78)
print("交付物")
print("=" * 78)
miss = []
for n, p in DELIV:
    if p.is_file():
        print("  OK   {:24s} {:>9,}B  sha256={}…".format(
            n, p.stat().st_size, hashlib.sha256(p.read_bytes()).hexdigest()[:16]))
    else:
        miss.append(n)
        print("  MISS {:24s} {}".format(n, p))
print("  缺失:", miss or "无")

print()
print("=" * 78)
print("素材池与登记")
print("=" * 78)
proj = R / "projects" / PID
for d, label in ((proj / "media", "media/（冻结索引态）"),
                 (proj / "registered_materials", "registered_materials/（P16-2）"),
                 (proj / "acquired_materials", "acquired_materials/（P16-3）")):
    imgs = [f for f in d.rglob("*") if f.is_file()
            and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")] if d.is_dir() else []
    print("  {:38s} {} 张".format(label, len(imgs)))
pool = json.loads((L / "phase16_retrieval_payload.json").read_text(encoding="utf-8"))
print("  候选池唯一图像:", pool["counts"]["total"], "|", json.dumps(
    pool["counts"]["by_origin"], ensure_ascii=False))

print()
print("=" * 78)
print("边界核对")
print("=" * 78)
cfg = json.loads((R / "config/config.json").read_text(encoding="utf-8"))
print("  config.json 含 vlm/execution 段:", any(k in cfg for k in ("vlm_judge", "execution", "ops")))
print("  config/render_motion.json sha256:", hashlib.sha256(
    (R / "config/render_motion.json").read_bytes()).hexdigest()[:16], "… (enabled=true)")
# 冻结真值只读引用（sha 应与 P14 一致）
tv = R / "tests/fixtures/vlm_relevance_truth_v1.json"
print("  vlm_relevance_truth_v1 sha256:", hashlib.sha256(tv.read_bytes()).hexdigest()[:16],
      "… (应 = 6104cfc202113510)")

print()
print("=" * 78)
print("关键结论复核")
print("=" * 78)
c1 = json.loads((L / "phase16_p16_1_conclusion.json").read_text(encoding="utf-8"))
print("  P16-1 门禁通过:", c1["gate_passed"], "| 捕获", c1["negative_capture_rate"],
      "| 误杀", c1["false_kill_rate"])
print("        回退:", c1["fallback"])
dq = json.loads((L / "phase16_dq_recompute.json").read_text(encoding="utf-8"))
print("  P16-5 DQ-2:", dq["phase13e_reference"]["dq2_state"], "->", dq["phase16"]["dq2_state"],
      "| 唯一素材", dq["phase13e_reference"]["unique_assets"], "->", dq["phase16"]["unique_assets"],
      "| 最大复用", dq["phase13e_reference"]["dq2_max_reuse_scenes"], "->",
      dq["phase16"]["dq2_max_reuse_scenes"])
print("  P16-5 DQ-3:", dq["phase13e_reference"]["dq3_state"], "->", dq["phase16"]["dq3_state"],
      "（超限景数", dq["phase16"]["dq3_holds_over_threshold"], "/21，换素材不可修复）")
cs = json.loads((L / "phase16_crop_safety.json").read_text(encoding="utf-8"))
print("  裁切失真素材:", cs["distorted_count"], "/", len(cs["rows"]),
      "->", [r["sha12"] for r in cs["rows"] if r["corr_full_vs_center_crop"] < 0.30])
