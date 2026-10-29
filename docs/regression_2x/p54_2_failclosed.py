# -*- coding: utf-8 -*-
"""Phase 54：**落账（FAIL-CLOSED）** —— P54-1 连续性前置通过、
词级精确构建器已实现但**词→句分配仍有缺陷**（负时长），故**不登记 F10**。

## 已完成且证据充分
**P54-1 前置：切片连续性断言（授权书 §0③）** —— `docs/regression_2x/p54_1_continuity.py`
· **Σ切片时长 == 段音频时长**：9 段**全部 Δ = 0.000** ⇒ **切片连续**；
· **景窗 vs 切片时长**：**不符 0 景**；唯一差值为末景 `P09_5`
  （窗 14.316s / 切片 12.316s，差 **2.000s = 该窗 `trailing_s` 片尾**）
  ⇒ **与监理 §0① 对账一致，非漂移**；
· 词级三量齐备：`words_manifest` **9 段 / 1,964 词**（片内起点齐备）。
⇒ **前置全部满足，未触发 STOP。**

## 阻断（本轮未能修完）
**词级精确构建器** `core/captions.py::build_cues_from_words_exact`（已实现）：
换算链按 §1 落地（词段内起点 − 切片段内起点 + 景窗起点），
排他规则按 §1（`起点 = max(句首词时刻, 上条终点)`、`终点 = min(句末词结束+hold, 下句起点)`、
末条 clamp 景窗）。

**实测缺陷**：
```
cue 数 111 | median 3.049s | **min -87.526** | max 92.064
max 同时活跃 3 | 重叠时刻 4441
  0.100-7.338 (7.2s)  | 1977 年，Appel 和 Haken 宣布…
  7.338-4.487 (-2.9s) | 一百二十多年没人搞定…
  4.487-7.338 (2.9s)  | 归约是纸笔上的硬活…
```
**特征**：出现**负时长**且 `start/end` 交错 ⇒ **词→句分配错位**：
`groups` 里某句取到的首词时刻**晚于**其末词时刻（或取到了**别的景的词**），
于是 `a0 > a1`。**根因在我的「按字符数把词分配到句」这段逻辑**（沿用自 P45-3 的写法，
但那里的时间基是**段内**、此处须先减去**切片段内起点**，两处语义不同 ⇒ 直接复用出错）。

**已排除**：窗对齐（本轮已改为**按 `scene_id` 取窗**，不再按下标猜 —— 修掉 P53 同族隐患）；
连续性（Δ=0.000）；`words_manifest` 齐备（1,964 词、片内起点）。

**未完成的定位**：词→句分配在**跨景/跨句**边界上的归属规则。

## 交付候选
保持 **F / F2 / F3 / F4 / F5 / F6 / F7 / F7.1 / F8 / F9** 不变；**F10 未登记**；零 promotion。

## 下一轮建议（最小改动）
1. **不要按字符数分配词**（那条在段内口径下才成立）。改为**直接按词的绝对时刻落在
   景窗内来筛词**（与 `build_cues_from_words` 的 P51-1 修复同款），
   再用**句在旁白文本中的字符区间**把词归到句；
2. 分配后**断言 `a0 <= a1`**（逐句），任一违反即 fail-closed ——
   把这条不变量写进构建器内部，避免再次产出负时长；
3. 复用 P53 的**转储法**：写盘前转储 `cues` + `groups`（含每句首/末词时刻），
   一次即可定位归属错位。
"""
from __future__ import annotations

import json
import pathlib
import sys
import time

R = pathlib.Path(r"C:\mp4agent\video-studio")
L = R / "docs" / "regression_2x" / "logs"
sys.stdout.reconfigure(encoding="utf-8")


def main() -> int:
    cont = json.loads((L / "p54_1_continuity.json").read_text(encoding="utf-8"))
    rec = {
        "schema": "p54-failclosed-v1",
        "stage": "Phase 54（字幕词级精确重建 + 黑板主线）—— FAIL-CLOSED，未登记 F10",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "p54_1_precondition": {
            "gate": "docs/regression_2x/p54_1_continuity.py",
            "rule": "Σ切片时长 == 段音频时长；任何断 ⇒ STOP",
            "result": "**PASS**",
            "paragraphs": cont["paras"],
            "paragraph_delta_max_s": max(abs(p["delta_s"]) for p in cont["paras"]),
            "window_vs_slice_mismatch": cont["window_vs_slice_mismatch"],
            "words_total": cont["words_total"],
            "supervisor_reconciliation_match": ("末景 P09_5 窗 − 切片 = 2.000s = "
                                                "该窗 `trailing_s` 片尾 ⇒ 与 §0① 一致"),
        },
        "blocking_defect": {
            "builder": "core/captions.py::build_cues_from_words_exact（已实现）",
            "symptom": ("**负时长**与 start/end 交错：cue 数 111、median 3.049s、"
                        "min **-87.526**、max 92.064、**max 同时活跃 3**、"
                        "重叠时刻 4441"),
            "diagnosis": ("**词→句分配错位**：某句取到的首词时刻**晚于**其末词时刻"
                          "（或取到别的景的词）⇒ `a0 > a1`。"
                          "根因是我**沿用 P45-3 的「按字符数分配词」写法**，"
                          "但 P45-3 的时间基是**段内**、此处须先减**切片段内起点**，"
                          "两处语义不同 ⇒ 直接复用即出错。"),
            "ruled_out": [
                "窗对齐（已改为**按 `scene_id` 取窗**，不再按下标猜 —— 修掉 P53 同族隐患）",
                "切片连续性（9 段 Δ=0.000）",
                "`words_manifest` 齐备性（9 段 / 1,964 词 / 片内起点）",
            ],
            "not_located": True,
        },
        "not_started": {
            "P54_2_blackboard_mainline": "未开始（依赖 P54-1 通过后再渲染，避免返工）",
            "P54_3_F10": "未登记",
        },
        "delivery_candidates_unchanged": ["F", "F2", "F3", "F4", "F5", "F6",
                                          "F7", "F7.1", "F8", "F9"],
        "zero_promotion": True,
        "next_round_minimal_fix": [
            "① 弃用「按字符数分配词」；改为**按词的绝对时刻落在景窗内筛词**"
            "（同 P51-1 的修复），再用句在旁白文本中的**字符区间**把词归到句",
            "② 逐句**断言 `a0 <= a1`**，任一违反即 fail-closed"
            "（把不变量写进构建器内部，杜绝再次产出负时长）",
            "③ 复用 P53 **转储法**：写盘前转储 `cues` + `groups`（含每句首/末词时刻）",
        ],
        "budget": {"llm_usd": 0.0, "generation_cny": 0.0, "network": 0, "renders": 0},
    }
    p = L / "p54_failclosed.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Phase 54 落账（FAIL-CLOSED，未登记 F10）")
    print("  P54-1 前置（连续性）：**PASS** —— 9 段 Δ 最大 {:.3f}s；景窗不符 {} 景；"
          "词 {} 个".format(rec["p54_1_precondition"]["paragraph_delta_max_s"],
                            len(cont["window_vs_slice_mismatch"]),
                            cont["words_total"]))
    print("  阻断：词级精确构建器**负时长**（min -87.526）⇒ 词→句分配错位")
    print("  已排除：窗对齐（改按 scene_id 取窗）/ 连续性 / words_manifest 齐备")
    print("  未定位：词→句分配的跨句边界归属规则")
    print("  交付候选保持 F…F9 不变；F10 未登记；零 promotion")
    print("-> " + str(p.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
