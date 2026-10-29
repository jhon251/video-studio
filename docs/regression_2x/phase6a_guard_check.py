# -*- coding: utf-8 -*-
"""6-A/M1 守卫校验（只读）：确认 5.x 冻结评估件与 r3 基线**逐字节一致**，并列出工作树相对 r3 的预期漂移。

用法: python docs/regression_2x/phase6a_guard_check.py
产出: docs/regression_2x/logs/phase6a_guard_check.json
"""
import hashlib
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(r"C:\mp4agent\video-studio")
LOGS = ROOT / "docs" / "regression_2x" / "logs"
BASE = ROOT / "docs" / "regression_2x" / "baseline"
R3 = "5.x-post-final-maintenance-baseline-r3"
FINAL = "5.x-final-baseline"
FINAL_SHA = "be1717b9c7fe9ed9124be3876db64b5893915a4d0ffad56bd37eded5e6e2141e"

GUARDS = [
    "src/video_studio/core/mm_judge.py", "src/video_studio/ops/mm_judge.py",
    "src/video_studio/core/mm_temporal.py", "src/video_studio/ops/mm_temporal.py",
    "src/video_studio/core/mm_quality.py", "src/video_studio/ops/mm_quality.py",
    "src/video_studio/core/multimodal.py", "src/video_studio/ops/multimodal.py",
    "src/video_studio/core/mm_worker_clip.py", "src/video_studio/core/semantics.py",
    "src/video_studio/core/selection_review.py", "src/video_studio/ops/selection_review.py",
    "src/video_studio/core/audio.py", "src/video_studio/core/materials.py",
    "src/video_studio/core/narration.py", "src/video_studio/core/captions.py",
    "src/video_studio/agents/editing/agent.py", "src/video_studio/agents/voice/agent.py",
    "src/video_studio/agents/subtitle/agent.py",
    "tests/fixtures/mm_truth_set_v1.json", "tests/fixtures/mm_judge_truth_v1.json",
    "tests/mm_judge_test.py", "tests/mm_quality_test.py", "tests/mm_temporal_test.py",
]


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for c in iter(lambda: fh.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


man = json.loads((BASE / "baseline_manifest_{}.json".format(R3)).read_text(encoding="utf-8"))
files = man["files"]
rows, drifted = [], []
for rel in GUARDS:
    live = ROOT / rel
    in_man = rel in files
    live_sha = sha(live) if live.is_file() else None
    same = (in_man and live_sha == files[rel]["sha256"]) if in_man else None
    rows.append({"file": rel, "in_r3": in_man, "identical_to_r3": same,
                 "sha12": (live_sha or "")[:12]})
    if same is False:
        drifted.append(rel)

# 工作树相对 r3 的漂移（仅基线内文件；新增文件另列）
tree_drift, tree_missing = [], []
for rel, rec in files.items():
    p = ROOT / rel
    if not p.exists():
        tree_missing.append(rel)
    elif sha(p) != rec["sha256"]:
        tree_drift.append(rel)
zip_r3 = BASE / "{}.zip".format(R3)
zip_final = BASE / "{}.zip".format(FINAL)
out = {
    "guards_checked": len(rows), "guards_drifted": drifted, "guard_rows": rows,
    "r3_zip_sha256": sha(zip_r3), "r3_zip_unchanged_vs_manifest":
        sha(zip_r3) == man["zip_sha256"], "r3_file_count": man["file_count"],
    "tree_drift_vs_r3": tree_drift, "tree_missing_vs_r3": tree_missing,
    "final_zip_sha256": sha(zip_final), "final_zip_unchanged": sha(zip_final) == FINAL_SHA,
    "expected_new_files": sorted(
        p.relative_to(ROOT).as_posix() for p in
        [ROOT / "src/video_studio/core/integrity.py", ROOT / "src/video_studio/core/direction.py",
         ROOT / "src/video_studio/ops/integrity.py", ROOT / "src/video_studio/ops/direction.py",
         ROOT / "tests/integrity_test.py", ROOT / "tests/direction_test.py",
         ROOT / "tests/fixtures/production_integrity_truth_v1.json",
         ROOT / "tests/fixtures/build_integrity_fixtures.py"] if p.is_file()),
    "note": "守卫项（5.x 冻结评估件 + 渲染链 + 字幕链）必须与 r3 逐字节一致；"
            "工作树漂移应仅含 src/video_studio/cli.py（新增两个只读子命令）",
}
(LOGS / "phase6a_guard_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                              encoding="utf-8")
print("guards checked:", len(rows), "| drifted:", drifted or "无")
print("r3 zip 未被改写:", out["r3_zip_unchanged_vs_manifest"], "| 文件数", man["file_count"])
print("工作树相对 r3 漂移:", tree_drift, "| 缺失:", tree_missing)
print("旧 5.x-final-baseline sha 未变:", out["final_zip_unchanged"])
print("json ->", LOGS / "phase6a_guard_check.json")
