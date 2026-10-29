# -*- coding: utf-8 -*-
"""P20-3 promotion 材料包（交人工观看用）。

内容：候选摘要一页 + 与 21 景版（p_50e10b27b44d）对比 + 已知限制清单 + 阻塞说明。
**因 P20-2 fail-closed，本包不推荐 40 段候选作为交付级候选**（如实说明）。
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import sys
from collections import Counter

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")

p20 = json.loads((L / "phase20_p20_2_verification.json").read_text(encoding="utf-8"))
p19 = json.loads((L / "phase19_p19_4_verification.json").read_text(encoding="utf-8"))
p20fix = json.loads((R / "output/phase20_p20_2_sandbox/fixture.json")
                    .read_text(encoding="utf-8"))
p19fix = json.loads((R / "output/phase19_p19_4_sandbox/fixture.json")
                    .read_text(encoding="utf-8"))
slice_rep = json.loads((L / "phase20_p20_1_voice_slice.json").read_text(encoding="utf-8"))

f40 = R / p20["candidate"]
f21 = R / p19["candidate"]


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


pack = {
    "schema": "phase20-promotion-package-v1",
    "stage": "Phase 20 P20-3 promotion 材料包（交人工观看）",
    "generated_for": "human review（promotion 决策由人工做出；本阶段零 promotion）",
    "recommendation": {
        "recommended_candidate": p19["candidate"],
        "reason": ("40 段候选（P20-2）**时长契约不通过**（992.88s，超 978.7±1s 达 +14.2s）"
                   "且**逐景核验近乎空转**（checked 2/40，派生段未绑定素材）⇒ **不作为交付级候选**。"
                   "21 景候选（P19-4）**全门通过 + DQ-2 PASS**，是当前唯一全门通过的候选。"),
        "not_recommended": p20["candidate"],
    },
    "candidates": {
        "A_21seg_p19": {
            "path": p19["candidate"], "bytes": p19["candidate_bytes"],
            "sha256": p19["candidate_sha256"], "segments": 21,
            "duration_s": p19["duration_contract"]["measured_s"],
            "duration_within": p19["duration_contract"]["within"],
            "loudness": p19["loudness"],
            "pi_pre_blocked": p19["pi_pre"]["blocked"],
            "pi_post_blocked": p19["pi_post"]["blocked"],
            "subtitles": p19["subtitle"],
            "per_scene": p19["per_scene_verify"],
            "motion": p19["motion"],
            "dq2": p19.get("dq2_corrected"), "dq3": p19["dq3"],
            "render_output_registered": False,
            "gates": "全门通过 + DQ-2 PASS；DQ-3 FAIL（max 67.374s）",
        },
        "B_40seg_p20": {
            "path": p20["candidate"], "bytes": p20["candidate_bytes"],
            "sha256": p20["candidate_sha256"], "segments": 40,
            "duration_s": p20["duration_contract"]["measured_s"],
            "duration_within": p20["duration_contract"]["within"],
            "voice_base_s": p20["duration_contract"]["voice_base_s"],
            "loudness": p20["loudness"],
            "pi_pre_blocked": p20["pi_pre"]["blocked"],
            "pi_post_blocked": p20["pi_post"]["blocked"],
            "subtitles": p20["subtitle"],
            "per_scene": p20["per_scene_verify"],
            "motion": p20["motion"],
            "dq2": p20.get("dq2_corrected"), "dq3": p20["dq3"],
            "render_output_registered": False,
            "gates": ("响度/PI/字幕/运动 全 PASS；**时长契约 FAIL（992.88s）**；"
                      "**逐景核验 checked 2/40 空转**；DQ-2 PASS；DQ-3 FAIL 但显著改善"),
        },
    },
    "comparison": {
        "segments": "21 → 40（句界拆分，19 条提案）",
        "duration_s": "{} → {}（Δ{:+.2f}s；40 段因冻结 pause 预算膨胀）".format(
            p19["duration_contract"]["measured_s"], p20["duration_contract"]["measured_s"],
            p20["duration_contract"]["measured_s"] - p19["duration_contract"]["measured_s"]),
        "dq3": "max_hold {}s / 超限 {} → max_hold {}s / 超限 {}（占比 {:.1%}）".format(
            p19["dq3"]["max_hold_s"], p19["dq3"].get("holds_over_threshold"),
            p20["dq3"]["max_hold_s"], p20["dq3"].get("holds_over_threshold"),
            p20["dq3"]["share_over_threshold"]),
        "dq2": "唯一素材 {} → {}；最大复用 {} → {} 景".format(
            (p19.get("dq2_corrected") or {}).get("unique_assets"),
            (p20.get("dq2_corrected") or {}).get("unique_assets"),
            (p19.get("dq2_corrected") or {}).get("max_reuse_scenes"),
            (p20.get("dq2_corrected") or {}).get("max_reuse_scenes")),
        "motion": "{} → {}".format(p19["motion"]["counts"], p20["motion"]["counts"]),
        "subtitles": "均 SUBTITLE_ALIGNED（216 cue、语音内 1.0、越界 0s）",
        "loudness": "均 {} LUFS / {} dBTP".format(p20["loudness"]["measured_lufs"],
                                                  p20["loudness"]["measured_true_peak_dbtp"]),
        "verification_coverage": "21/21 逐景核验 → **2/40**（派生段未绑定素材 ⇒ 空转）",
    },
    "known_limitations": [
        "**时长契约冲突（#75.2）**：`PAUSE_BUDGET_S=0.75` 为冻结常量，40 段 ⇒ 时基 992.884s（+14.2s）；"
        "要回 978.7s 需改 PI 时基语义（超授权）⇒ 40 段与 978.7±1s **不可兼得**。",
        "**段 ID 绑定缺口（#75.3）**：派生段（S01p1/S01p2…）无 `expected_asset_id` ⇒ 落入占位分支 ⇒ "
        "逐景核验 checked 仅 2/40；拆镜必须同步展开素材绑定。",
        "**句中切点设计债（#75.1）**：P19-3 第 2/3 轮句中拆分 NOT_EXECUTED。",
        "**DQ-3 地板**：40 段后仍 45.0% 超 25s（max 36.836s），未达 ≤20%。",
        "**标记素材在片**：`low_discriminative`（`23e71bc8a864`、`432cd85be6f1`）与 "
        "`low_crop_safety`（`5144139591a0`、`a3f0e27204cd`）；P19-4/P20-2 已对绑定这些素材的景做 "
        "**4 处降权重选**（S02/S03/S05/S08）。",
        "**VLM 仲裁放行的景（P19-4，4 景）**：S06（0.242）、S11（0.153）、S13（0.006）、S18（0.253）"
        "——均判 `present` 并放行，附 prompt_version `vlm-presence-verify-v1` 与模型名。",
        "**P20-2 仲裁**：仅 1 景进入仲裁且判 `absent`（S20，corr 0.009）⇒ 维持阻断。",
        "**反门语料不全**：仅构造错配；旧 S05 鲨鱼照等真实错配素材本仓不存在。",
        "**KD-73 未解**：VLM 语义相关性判据与人工不同源（与本阶段的存在性核验是不同任务）。",
    ],
    "reselect": {"p19": p19fix.get("reselect"), "p20": p20fix.get("reselect")},
    "p20_1_provenance": {
        "rule_version": slice_rep["rule_version"],
        "segments": slice_rep["segments"],
        "time_base": slice_rep["time_base"],
        "text_verbatim": slice_rep["text_verbatim"],
        "inputs": slice_rep["inputs"],
        "decision": slice_rep["decision"],
    },
    "one_page_summary": (
        "【Phase 20 一页摘要】P20-1 完成（40 段 voice 派生：零重合成、文本逐字 4927→4927、"
        "19/19 切点落在实测停顿、时基 978.634s）。P20-2 渲染 122.6s 后 **fail-closed**："
        "时长 992.88s（40 段 × 冻结 pause 0.75s ⇒ +14.2s，超 978.7±1s）且逐景核验 checked 2/40（派生段未绑定素材）。"
        "响度/PI/字幕/运动 全 PASS，DQ-2 PASS，DQ-3 显著改善至 45.0%（max 36.836s）但未达 ≤20%。"
        "⇒ **不登记交付级候选**；**21 景版 p_50e10b27b44d 仍是唯一全门通过候选**，交人工观看与 promotion 决策。"),
    "zero_promotion": True,
    "files": {
        "candidate_A": {"path": p19["candidate"], "exists": f21.is_file(),
                        "sha256": p19["candidate_sha256"] if f21.is_file() else None},
        "candidate_B": {"path": p20["candidate"], "exists": f40.is_file(),
                        "sha256": p20["candidate_sha256"] if f40.is_file() else None},
    },
}
p = L / "phase20_p20_3_promotion_package.json"
p.write_text(json.dumps(pack, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")

print("=" * 78)
print("P20-3 promotion 材料包")
print("=" * 78)
print(pack["one_page_summary"])
print()
print("推荐候选:", pack["recommendation"]["recommended_candidate"])
print("不推荐  :", pack["recommendation"]["not_recommended"])
print()
for k, v in pack["comparison"].items():
    print("  {:22s} {}".format(k, v))
print()
print("已知限制 {} 条".format(len(pack["known_limitations"])))
print("->", p.relative_to(R).as_posix())
