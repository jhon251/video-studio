# -*- coding: utf-8 -*-
"""Phase 55：**F10 单变量设计失效登记**（如实修正，不改写已登记数值）。

授权书 §2 要求 **F10 = 单变量验证版**（只修字幕，**画面与 F9 一致**），
使终审「字幕跟嘴」判定**不被视觉变化污染**。

**实测：画面与 F9 一致的只有 4 / 36 景** ⇒ **单变量属性失效**。
原因：渲染 harness 的**素材分配每跑一次都会重算**（局部搜索 + 随机重启，
`initial` 种子在份额越门时被丢弃 ⇒ 结果不固定）⇒ **画面不是受控变量**。

**判定**：F10 的字幕侧证据**依然成立**（烧录 ASS 实测 max 同时活跃 1 / 重叠 0 /
覆盖 99.3% / median 5.720s），但**它不能作为「单变量字幕验证版」使用** ——
终审若直接比较 F9↔F10，**视觉差异会污染**「字幕跟嘴」的判断。

**建议（下一轮最小改动）**：让分配**可复现** —— 把 F9 的
`material_allocation.global_satisfy.assignment` 作为**固定绑定**回灌，
或给求解器固定 `initial` + 固定 `seed` 并**禁用种子丢弃**，
使「只改字幕」在**产物层**也成立。
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
    rec = [json.loads(x) for x in
           (L / "p55_2_delivery_candidate.jsonl").read_text(
               encoding="utf-8").splitlines() if x.strip()][-1]
    sv = rec.get("single_variable_design") or {}
    same, tot = sv.get("scenes_same_asset_vs_F9"), sv.get("scenes_total")
    out = {
        "schema": "p55-single-variable-void-v1",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "requirement": ("授权书 §2：**F10 = 单变量验证版**（只修字幕，画面与 F9 一致）"
                        "⇒ 使终审「字幕跟嘴」判定不被视觉变化污染"),
        "measured": {
            "scenes_same_asset_vs_F9": same, "scenes_total": tot,
            "scenes_differing": (tot - same) if (same is not None and tot) else None,
            "f9_sandbox": sv.get("f9_sandbox"),
            "f10_sandbox": rec.get("sandbox_project_id"),
        },
        "verdict": "**单变量属性失效**",
        "root_cause": ("渲染 harness 的**素材分配每跑一次都会重算**："
                       "`core.allocation.satisfy` 为**局部搜索 + 随机重启**，"
                       "且我在份额越门时会**丢弃 `initial` 种子** ⇒ "
                       "同一输入两次运行的解**不保证相同** ⇒ 画面不是受控变量。"),
        "what_still_holds": {
            "caption_side": ("烧录 ASS 实测 max 同时活跃 **1** / 重叠时刻 **0** / "
                             "覆盖 **99.3%** / median **5.720s** ⇒ 字幕侧证据成立"),
            "internal_assertions": rec.get("p55_1_word_sentence_attribution", {}).get(
                "internal_assertions"),
        },
        "impact_on_final_review": ("**F10 不能作为「单变量字幕验证版」交付终审** —— "
                                   "若直接与 F9 对比，**32 / 36 景的画面差异会污染**"
                                   "「字幕跟嘴」的判断。"),
        "recommended_fix": [
            "① 把 F9 的 `material_allocation.global_satisfy.assignment` 作为"
            "**固定绑定**回灌（最直接、可审计）；或",
            "② 给求解器固定 `initial` + 固定 `seed` 且**禁用种子丢弃**，"
            "并断言两次重渲的 `material_timeline` **逐景 sha 相同**；",
            "③ 把「分配可复现」写成 harness 的**前置断言**，"
            "使任何「只改字幕」的对照在**产物层**也成立。",
        ],
        "delivery_candidates_unchanged": ["F", "F2", "F3", "F4", "F5", "F6",
                                          "F7", "F7.1", "F8", "F9", "F10"],
        "note": ("**F10 已登记且数值不改写**（append-only 纪律）；"
                 "本件为**如实修正**：F10 的**单变量用途**失效，"
                 "但其**字幕侧证据**仍有效。"),
    }
    p = L / "p55_single_variable_void.json"
    p.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print("F10 单变量设计失效登记：")
    print("  画面与 F9 一致 **{} / {} 景** ⇒ **单变量属性失效**".format(same, tot))
    print("  根因：素材分配每跑一次都会重算（局部搜索 + 随机重启 + 种子丢弃）")
    print("  字幕侧证据仍成立：max 1 / 重叠 0 / 覆盖 99.3% / median 5.720s")
    print("  ⇒ **F10 不能作为「单变量字幕验证版」交付终审**")
    print("-> " + str(p.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
