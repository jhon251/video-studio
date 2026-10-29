# -*- coding: utf-8 -*-
"""Phase 44 / P44-3：**FAIL-CLOSED 登记**（不登记交付候选，交监理裁定）。

结论：**语义锚定与既有约束结构性冲突**，F6 未达「全门过」标准 ⇒ 按授权书
「完成或 fail-closed 即 STOP」**不登记 F6 为交付候选**，改为落账本冲突报告。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")
rec = {
    "schema": "p44-3-failclosed-register-v1",
    "stage": "Phase 44（语义锚定 + 字幕句级吸附）—— FAIL-CLOSED，未登记交付候选",
    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "decision": ("**不登记 F6 为交付级候选**：授权书要求「全门过 ⇒ 登记」，"
                 "而本轮锚定生效后 **cap 与家族约束不可同时满足**（详见冲突报告）"
                 "⇒ 按 fail-closed STOP，交监理裁定取舍。"),
    "what_was_achieved": {
        "P44-1_anchor": {
            "mechanism": ("`config/content_exclusions.json` 扩展 `scene_asset_policy`："
                          "7 个标志性素材**只允许**出现在其 `allowed_scenes`；"
                          "过滤在**求解前**剔除越界项 + 求解后**锚定守卫**兜底"),
            "result": "**锚定越界 = 0** ✔（锚定门 A1/A2/A3 PASS；7 种锚定素材均在片且各就其位）",
            "side_effect": ("可用素材被压到 **8 张未锚定 + 7 张受限** ⇒ "
                            "`cap=3` 的可用景位 **24 < 36 景** ⇒ **cap 不可满足**"),
        },
        "P44-2_caption": {
            "mechanism": ("句级吸附（景内每个 cue 边界吸到最近语音恢复点，±0.5s）+ "
                          "恢复点改由**整条旁白 WAV** 独立检出（消除切片边界自测）"),
            "result": "**未能达标**（详见下方口径差异）",
        },
    },
    "conflict_report": {
        "C1_cap_vs_anchor": {
            "statement": "**cap=3 与语义锚定结构性冲突**",
            "arithmetic": ("36 景；未锚定素材 8 张 × cap3 = **24 景位** < 36 景；"
                           "7 张锚定素材只能落在其 allowed_scenes（合计约 16 景位），"
                           "但**其余 20 景**只能靠那 8 张未锚定素材 ⇒ 必然超 cap。"),
            "measured": "F6 实测 cap 违例：`a3aff2f300eb` **7 景**（上限 3）；唯一素材 15 张",
            "not_solver_fault": ("已验证：把锚定过滤放进**求解前**的选项空间后结果不变"
                                 "⇒ 是**不可行**，不是求解器弱"),
        },
        "C2_family_share_vs_anchor": {
            "statement": "家族份额 ≤33% 与锚定冲突（且 33% 本就未达）",
            "measured": "F6 实测 A_纸面符号 **21 景 = 58.3%**（F5 为 41.7%）",
            "arithmetic": "非 A 可用素材仅 8 张（含 A 家族被锚定剔除后）⇒ 非 A 位 24 < 所需 25",
        },
        "C3_caption_metric_unreproducible": {
            "statement": "**字幕同步门口径不可复现**（分母不同源）",
            "supervisor_baseline": "F5 median 0.53s / 62 处 >1s（全片句界 211 个）",
            "my_measurement": ("整条旁白 WAV silencedetect(-35dB,d=0.28) ⇒ **241** 个恢复点；"
                               "最近边界距离 median **0.757s** / >1s **104**（43.2%）"),
            "parameter_sweep": ("已扫 d=0.28/0.30、-32/-35dB、WAV/MP3：恢复点数 220–269，"
                                "**无一组等于 211**；亦无法复现 median 0.53/62"),
            "structural_cause": ("cue 边界 **161 条** vs 恢复点 **241 个** ⇒ 比值 1:1.5；"
                                 "把 161 个边界对齐到 241 个点，**不可能**让每个点都有近邻，"
                                 "故 median 最近距离是**间距统计量**（≈0.76s），"
                                 "**吸附无法降低它**（实测吸附后 0.757→0.797，略升）"),
            "needed_from_supervisor": ("① 211 个句界的**检出参数**；② 门指标的精确定义"
                                       "（分母是恢复点还是 cue 边界；"
                                       "「滞后」是最近边界距离还是下条 cue 起点差）"),
        },
    },
    "options_for_supervisor": [
        {"id": "O1", "what": "放宽锚定：把部分 `allowed_scenes` 扩为「家族级」而非「景级」",
         "effect": "恢复选项空间 ⇒ cap 可满足；代价：锚定精度下降"},
        {"id": "O2", "what": "放宽 cap（如 cap=7）或取消间距约束",
         "effect": "锚定与 cap 可共存；代价：素材复用更密（观感轮番感加重）"},
        {"id": "O3", "what": "扩池：补未锚定素材（B/C/D 家族）≥ 12 张",
         "effect": "锚定 + cap + 份额三者同时可行；代价：需网络获取授权"},
        {"id": "O4", "what": "暂缓锚定，保留 F5 并先解决字幕口径",
         "effect": "F5 已全门过（除家族份额）；锚定表留待扩池后启用"},
    ],
    "current_state": {
        "delivery_candidates_unchanged": ["F", "F2", "F3", "F4", "F5"],
        "F6": "已渲染并落盘（沙箱 `p_0be7e6f92d46`，`t_81f7d7b41021_draft_with_outro_v2.mp4`）"
              "但**未登记为交付候选**（cap 7 / 家族相邻 9 / 份额 58.3% / 字幕门未达）",
        "zero_promotion": True,
    },
    "budget": {"llm_usd": 0.0, "network": 0, "renders": 4},
}
(L / "p44_3_failclosed_register.json").write_text(
    json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("已落账 FAIL-CLOSED 登记（未登记 F6 为交付候选）")
print("  P44-1 锚定：越界 0 ✔（但 cap 结构性不可满足：8 张未锚定素材 × cap3 = 24 < 36）")
print("  P44-2 字幕：口径不可复现（我 241 点/median 0.757 vs 监理 211 点/0.53）")
print("  交付候选保持 F/F2/F3/F4/F5 不变")
print("-> " + str((L / "p44_3_failclosed_register.json").relative_to(R)))
