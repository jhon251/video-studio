# -*- coding: utf-8 -*-
"""Phase 11：填充报告 sha256 台账 + 不可变核验（config.json 零改动 + 6-G/baseline/Phase 7–10 产物）。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

PRODUCED = {
    "__GUIDE__": "config/metadata_style_guide.md",
    "__CHECK__": "src/video_studio/core/title_check.py",
    "__META__": "src/video_studio/agents/metadata/agent.py",
    "__THUMB__": "src/video_studio/agents/thumbnail/agent.py",
    "__OPS__": "src/video_studio/ops/retention.py",
    "__CLI__": "src/video_studio/cli.py",
    "__TEST__": "tests/title_check_test.py",
    "__AB__": "docs/regression_2x/logs/phase11_title_ab.json",
}
rep_path = R / "docs" / "regression_2x" / "PHASE11_REPORT.md"
txt = rep_path.read_text(encoding="utf-8")
for k, f in PRODUCED.items():
    h = hashlib.sha256((R / f).read_bytes()).hexdigest()
    txt = txt.replace(k, h)
    print("  {:12s} -> {}  {}".format(k, h[:16] + "…", f))
rep_path.write_text(txt, encoding="utf-8")
print("残留占位符:", [k for k in PRODUCED if k in rep_path.read_text(encoding="utf-8")])

IMMUTABLE = {
    "final_master_6G": (R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
                        "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be"),
    "baseline_zip": (R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
                     "bffe9b0d4024626d166683f7c582a767711cec168193d20ab3cb5a4df4ce29e1"),
    "config_json_pinned": (R / "config" / "config.json", "7b03424846f15efc"),
    "config_example_pinned": (R / "config" / "config.example.json", "d5e838509d0cd044"),
    "p7_6_proposals": (L / "visual_binding_proposals.json", None),
    "p7_5_acquisition": (L / "visual_acquisition.json", None),
    "p8_ab_v2": (L / "phase8_ab_v2.json", None),
    "p8_ab_v3": (L / "phase8_ab_v3.json", None),
    "p9_backtest_summary": (L / "phase9_backtest_summary.json", None),
    "p10_topic_ab": (L / "phase10_topic_ab.json", None),
    "p10_retention_3sample": (L / "phase10_retention_3sample.json", None),
    "p10_immutable_check": (L / "phase10_immutable_check.json", None),
    "legacy_metadata_artifact": (R / "projects/p_96efdc03e1aa/artifacts/a_e0ec01d11b5a.json", None),
    "critic_agent_py": (R / "src/video_studio/agents/critic/agent.py", None),
    "publish_tool_py": (R / "src/video_studio/tools/publish_tool.py", None),
    "platform_agent_py": (R / "src/video_studio/agents/platform/agent.py", None),
    "script_agent_py": (R / "src/video_studio/agents/script/agent.py", None),
    "topic_agent_py": (R / "src/video_studio/agents/topic/agent.py", None),
    "core_integrity_py": (R / "src/video_studio/core/integrity.py", None),
    "pipeline_lifecycle_py": (R / "src/video_studio/pipeline/lifecycle.py", None),
}
out = {"schema": "phase11-immutable-check-v1", "immutable": {}, "expect_match": {}, "verdict": ""}
ok = True
for k, (p, exp) in IMMUTABLE.items():
    h = hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "MISSING"
    out["immutable"][k] = h
    if exp:
        okk = h.startswith(exp) if len(exp) < 64 else (h == exp)
        out["expect_match"][k] = okk
        ok = ok and okk
        print("  {:26s} {}{}".format(k, h[:16] + "…",
                                     "  <= 与钉定值一致" if okk else "  <= **不一致**"))
out["verdict"] = "IMMUTABLE_OK" if ok else "IMMUTABLE_MISMATCH"
(L / "phase11_immutable_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("verdict:", out["verdict"])
sys.exit(0 if ok else 1)
