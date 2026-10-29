# -*- coding: utf-8 -*-
"""Phase 9 只读核验：不可变快照（6-G / baseline / Phase 7 / Phase 8 产物 + 源码）零改动 + 产物台账。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

IMMUTABLE = {
    "final_master_6G": (R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
                        "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be"),
    "baseline_zip": (R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
                     "bffe9b0d4024626d166683f7c582a767711cec168193d20ab3cb5a4df4ce29e1"),
    "p7_6_proposals": (L / "visual_binding_proposals.json", None),
    "p7_6_coverage": (L / "visual_coverage_report.json", None),
    "p8_style_v2_snapshot": (R / "docs/regression_2x/phase8_style_v2_snapshot.md",
                             "17e6439271dcfed835581cf04d2119d8a773c30191baf10ad53f610dbdfd8465"),
    "p8_ab_v2": (L / "phase8_ab_v2.json", None),
    "p8_ab_v3": (L / "phase8_ab_v3.json", None),
    "p8_report": (R / "docs/regression_2x/PHASE8_REPORT.md", None),
    "critic_agent_py": (R / "src/video_studio/agents/critic/agent.py", None),
    "pipeline_lifecycle_py": (R / "src/video_studio/pipeline/lifecycle.py", None),
    "core_integrity_py": (R / "src/video_studio/core/integrity.py", None),
    "core_visual_binding_py": (R / "src/video_studio/core/visual_binding.py", None),
    "ops_visual_binding_py": (R / "src/video_studio/ops/visual_binding.py", None),
    "config_json": (R / "config" / "config.json", None),
}

PRODUCED = {
    "core_retention_py": R / "src/video_studio/core/retention.py",
    "ops_retention_py": R / "src/video_studio/ops/retention.py",
    "router_py": R / "src/video_studio/llm" / "router.py",
    "cli_py": R / "src/video_studio/cli.py",
    "test_retention": R / "tests" / "retention_check_test.py",
    "phase9_report": R / "docs/regression_2x/PHASE9_REPORT.md",
    "bt_v2": L / "phase9_backtest_v2.json",
    "bt_v3": L / "phase9_backtest_v3.json",
    "bt_prod": L / "phase9_backtest_prod.json",
    "bt_summary": L / "phase9_backtest_summary.json",
    "variance": L / "phase9_retention_variance.json",
}


def sha(p):
    return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()


rep = {"schema": "phase9-immutable-check-v1", "immutable": {}, "expect_match": {},
       "produced": {}, "verdict": ""}
for k, (p, expect) in IMMUTABLE.items():
    h = sha(p) if p.is_file() else "MISSING"
    rep["immutable"][k] = h
    if expect:
        rep["expect_match"][k] = (h == expect)
for k, p in PRODUCED.items():
    rep["produced"][k] = sha(p) if p.is_file() else "MISSING"
ok = bool(rep["expect_match"]) and all(rep["expect_match"].values())
rep["verdict"] = "IMMUTABLE_OK" if ok else "IMMUTABLE_MISMATCH"
out = L / "phase9_immutable_check.json"
out.write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
for k, v in rep["immutable"].items():
    flag = ""
    if k in rep["expect_match"]:
        flag = "  <= 与历史登记一致" if rep["expect_match"][k] else "  <= **不一致**"
    print("  {:24s} {}{}".format(k, str(v)[:16] + "…", flag))
print("verdict:", rep["verdict"], "| 台账 ->", out.relative_to(R))
sys.exit(0 if ok else 1)
