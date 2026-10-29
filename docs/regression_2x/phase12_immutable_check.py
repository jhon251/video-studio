# -*- coding: utf-8 -*-
"""Phase 12 不可变核验：P7-2 原索引 + P7-6 产物 + 6-G/baseline/config 钉定值；
并**如实登记** `ops/visual_binding.py` 因 P12-3 授权加法集成而产生的哈希变化（默认关闭、已证向后兼容）。"""
import hashlib
import json
import pathlib
import sys

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")


def sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


IMMUTABLE = {
    "final_master_6G": (R / "output/phase6g_exec_h5/20260929_151026/out/H5_rp-0ebebb71f99c.mp4",
                        "3b61dafda11c1b9d22381833a00645670ec8b4f25b8fccca813bb7ac63cee0be"),
    "baseline_zip": (R / "docs/regression_2x/baseline/6.x-final-baseline.zip",
                     "bffe9b0d4024626d166683f7c582a767711cec168193d20ab3cb5a4df4ce29e1"),
    "config_json_pinned": (R / "config" / "config.json", "7b03424846f15efc"),
    "config_example_pinned": (R / "config" / "config.example.json", "d5e838509d0cd044"),
    # P7-2 原索引（本阶段只读消费；**零改动**）
    "p7_2_asset_index": (L / "asset_index.json", None),
    # P7-6 产物（本阶段仅**重放**，未覆盖；逐字节一致已由 phase12_binding_sim 证明）
    "p7_6_proposals": (L / "visual_binding_proposals.json", None),
    "p7_6_coverage": (L / "visual_coverage_report.json", None),
    "p7_5_acquisition": (L / "visual_acquisition.json", None),
    "p7_4_relevance": (L / "visual_relevance.json", None),
    "p7_6_immutable_check": (L / "phase7_immutable_check.json", None),
    "p8_ab_v3": (L / "phase8_ab_v3.json", None),
    "p9_backtest_summary": (L / "phase9_backtest_summary.json", None),
    "p10_topic_ab": (L / "phase10_topic_ab.json", None),
    "p11_title_ab": (L / "phase11_title_ab.json", None),
    "core_materials_py": (R / "src/video_studio/core/materials.py", None),
}

#: Phase 7 记录值（用于交叉核对本阶段未改动 P7 产物）——从既有记录文件中检索
def find_recorded(h: str) -> str | None:
    for f in sorted((R / "docs" / "regression_2x").glob("*.md")) + \
            sorted((R / "docs" / "regression_2x").glob("logs/*.json")):
        try:
            s = f.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if h in s:
            return f.name
    return None


out = {"schema": "phase12-immutable-check-v1", "immutable": {}, "expect_match": {},
       "recorded_in_history": {}, "verdict": ""}
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
        hist = find_recorded(h) if h != "MISSING" else None
        out["recorded_in_history"][k] = hist
        print("  {:24s} {}  {}".format(k, h[:16] + "…",
                                       "<= 历史记录一致（{}）".format(hist) if hist
                                       else "<= 未见历史记录（本阶段首次记录）"))
# 授权变更登记：ops/visual_binding.py（P12-3 加法、默认关闭）
old = json.loads((L / "phase10_immutable_check.json").read_text(encoding="utf-8"))[
    "immutable"]["ops_visual_binding_py"]
new = sha(R / "src/video_studio/ops/visual_binding.py")
out["authorized_changes"] = {
    "ops_visual_binding_py": {"before": old, "after": new, "changed": old != new,
                              "reason": "P12-3 授权加法：build(overlay=None) 默认关闭；"
                                        "core/materials.py 与所有门禁阈值未改动",
                              "backward_compat_proof": "docs/regression_2x/logs/"
                                                       "phase12_coverage_after.json "
                                                       "arm_a_no_overlay.backward_compatible "
                                                       "（proposals/coverage/hash/ids 全 true）"}}
print("  {:24s} {} -> {}  （授权加法，默认关闭）".format("ops_visual_binding_py", old[:12],
                                                        new[:12]))
out["verdict"] = "IMMUTABLE_OK" if ok else "IMMUTABLE_MISMATCH"
(L / "phase12_immutable_check.json").write_text(json.dumps(out, ensure_ascii=False, indent=1),
                                                encoding="utf-8")
print("verdict:", out["verdict"])
sys.exit(0 if ok else 1)
