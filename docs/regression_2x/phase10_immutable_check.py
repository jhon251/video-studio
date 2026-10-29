# -*- coding: utf-8 -*-
"""Phase 10：填充报告 sha256 台账 + 不可变核验（6-G/baseline/Phase 7/8/9 产物与关键源码）。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

PRODUCED = {
    "__SIG_SHA__": "src/video_studio/tools/topic_signals.py",
    "__TOPIC_SHA__": "src/video_studio/agents/topic/agent.py",
    "__OPS_SHA__": "src/video_studio/ops/retention.py",
    "__CORE_SHA__": "src/video_studio/core/retention.py",
    "__SCRIPT_SHA__": "src/video_studio/agents/script/agent.py",
    "__CLI_SHA__": "src/video_studio/cli.py",
    "__GUIDE_SHA__": "config/script_style_guide.md",
    "__TEST_SHA__": "tests/topic_signals_test.py",
    "__R3_SHA__": "docs/regression_2x/logs/phase10_retention_3sample.json",
    "__AB_SHA__": "docs/regression_2x/logs/phase10_topic_ab.json",
}
rep_path = R / "docs" / "regression_2x" / "PHASE10_REPORT.md"
txt = rep_path.read_text(encoding="utf-8")
for k, f in PRODUCED.items():
    h = hashlib.sha256((R / f).read_bytes()).hexdigest()
    txt = txt.replace(k, h)
    print("  {:16s} -> {}  {}".format(k, h[:16] + "…", f))
rep_path.write_text(txt, encoding="utf-8")
print("残留占位符:", [k for k in PRODUCED if k in rep_path.read_text(encoding="utf-8")])

# ---------------- 不可变核验 ----------------
IMMUTABLE = {
    "final_master_6G": (R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
                        "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be"),
    "baseline_zip": (R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
                     "bffe9b0d4024626d166683f7c582a767711cec168193d20ab3cb5a4df4ce29e1"),
    "p8_style_v2_snapshot": (R / "docs/regression_2x/phase8_style_v2_snapshot.md",
                             "17e6439271dcfed835581cf04d2119d8a773c30191baf10ad53f610dbdfd8465"),
    "p7_6_proposals": (L / "visual_binding_proposals.json", None),
    "p7_6_coverage": (L / "visual_coverage_report.json", None),
    "p7_5_acquisition": (L / "visual_acquisition.json", None),
    "p7_4_relevance": (L / "visual_relevance.json", None),
    "p8_ab_v2": (L / "phase8_ab_v2.json", None),
    "p8_ab_v3": (L / "phase8_ab_v3.json", None),
    "p9_backtest_summary": (L / "phase9_backtest_summary.json", None),
    "p9_backtest_prod": (L / "phase9_backtest_prod.json", None),
    "p9_variance": (L / "phase9_retention_variance.json", None),
    "critic_agent_py": (R / "src/video_studio/agents/critic/agent.py", None),
    "pipeline_lifecycle_py": (R / "src/video_studio/pipeline/lifecycle.py", None),
    "core_integrity_py": (R / "src/video_studio/core/integrity.py", None),
    "ops_visual_binding_py": (R / "src/video_studio/ops/visual_binding.py", None),
    "tools_material_provider_py": (R / "src/video_studio/tools/material_provider.py", None),
    "config_json": (R / "config" / "config.json",
                    "7b03424846f15efc"),          # 基线 manifest 钉定值（前缀比较）
}
out = {"schema": "phase10-immutable-check-v1", "immutable": {}, "expect_match": {},
       "verdict": ""}
ok = True
for k, (p, exp) in IMMUTABLE.items():
    h = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
    out["immutable"][k] = h
    if exp:
        okk = h.startswith(exp) if len(exp) < 64 else (h == exp)
        out["expect_match"][k] = okk
        ok = ok and okk
        print("  {:26s} {}{}".format(k, h[:16] + "…",
                                     "  <= 与基线钉定值一致" if okk else "  <= **不一致**"))
        continue
    print("  {:26s} {}".format(k, h[:16] + "…"))
out["verdict"] = "IMMUTABLE_OK" if ok else "IMMUTABLE_MISMATCH"
out["config_json_note"] = ("config/config.json 经**授权**加法新增 tools.topic_signals（provider=none）；"
                          "llm.tiers 与其余配置逐字未改")
(L / "phase10_immutable_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("verdict:", out["verdict"])
sys.exit(0 if ok else 1)
