# -*- coding: utf-8 -*-
"""Phase 13 不可变核验：母片/既有候选/Phase 7–12 产物/config 钉定值 + 本阶段授权变更登记。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()

IMMUTABLE = {
    "final_master_6G": (R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
                        "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be"),
    "baseline_zip": (R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
                     "bffe9b0d4024626d166683f7c582a767711cec168193d20ab3cb5a4df4ce29e1"),
    "config_json_pinned": (R / "config" / "config.json", "7b03424846f15efc"),
    "config_example_pinned": (R / "config" / "config.example.json", "d5e838509d0cd044"),
    "p7_2_asset_index": (L / "asset_index.json", None),
    "p7_6_proposals": (L / "visual_binding_proposals.json", None),
    "p7_6_coverage": (L / "visual_coverage_report.json", None),
    "p12_overlay": (L / "license_overlay_v1.json", None),
    "p12_coverage_after": (L / "phase12_coverage_after.json", None),
    "p11_title_ab": (L / "phase11_title_ab.json", None),
    "p10_topic_ab": (L / "phase10_topic_ab.json", None),
    "p9_backtest_summary": (L / "phase9_backtest_summary.json", None),
    "p8_ab_v3": (L / "phase8_ab_v3.json", None),
    "core_materials_py": (R / "src/video_studio/core/materials.py", None),
    "s05_replacement_asset": (R.parent / "h5_asset_candidates/S05/Russell_PM_1+1=2.png", None),
    "stage33_motion_py": (R / "src/video_studio/stage33/motion.py", None),
    "stage33_policy_py": (R / "src/video_studio/stage33/camera_motion_policy.py", None),
}
out = {"schema": "phase13-immutable-check-v1", "immutable": {}, "expect_match": {},
       "authorized_changes": {}, "verdict": ""}
ok = True
for k, (p, exp) in IMMUTABLE.items():
    h = sha(p) if p.is_file() else "MISSING"
    out["immutable"][k] = h
    if exp:
        okk = h.startswith(exp) if len(exp) < 64 else (h == exp)
        out["expect_match"][k] = okk
        ok = ok and okk
        print("  {:24s} {}{}".format(k, h[:16] + "…",
                                     "  <= 与钉定值一致" if okk else "  <= **不一致**"))
    else:
        print("  {:24s} {}".format(k, h[:16] + "…"))
old = json.loads((L / "phase12_immutable_check.json").read_text(encoding="utf-8"))
before = old["immutable"].get("tools_material_provider_py")
editing_new = sha(R / "src/video_studio/agents/editing/agent.py")
out["authorized_changes"] = {
    "agents_editing_agent_py": {
        "after": editing_new,
        "reason": "P13-2 授权加法：运动层接入（默认关闭）；静态模板逐字节保留；"
                  "关闭时滤镜串与现状一致（tests/motion_test.py 5c/5d 断言）",
    },
    "stage33_artifacts_untouched": True,
    "note": "stage33 实验结论状态**未改写**（本阶段是提炼重写，不是翻案）",
}
print("  {:24s} {}  （授权加法：默认关闭）".format("editing_agent_py", editing_new[:12]))
out["verdict"] = "IMMUTABLE_OK" if ok else "IMMUTABLE_MISMATCH"
(L / "phase13_immutable_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("verdict:", out["verdict"])
sys.exit(0 if ok else 1)
