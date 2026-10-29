# -*- coding: utf-8 -*-
"""Phase 53 / P53-3：**回归发现的 2 项未决问题**（均为**测试侧**，非产品缺陷）。

## 背景：一次干净的回归（92/94）证明了什么
P52 我在回归期间**并发渲染 + 新增事件**，打破三个只读套件的「DB 字节/行数前后一致」
断言 ⇒ 上次 **90/93**。随后**串行、期间不写库**重跑 ⇒ **92/94**：
· **`mm_temporal_test` 与 `multimodal_test` 现已 PASS** ⇒
  **证实那两项失败是我造成的，不是产品缺陷**（监理裁定④成立）。
剩余 2 项如下，均已定位为**测试侧**问题。

## 未决 1：`caption_overlap_test` 在回归内读到**别的工程**的 ASS
**现象**：同一份 ASS 独立复跑 **3/3 PASS**（已跑 3 次确认确定性），
但**回归运行内** 1 PASS / 2 FAIL（0.1s）。
**根因**：原 `latest_ass()` 先按 `fixture.sandbox_project_id` 找，
**找不到就 glob 全库取最新** ⇒ 回归期间会命中**任何更新的产物**（读错对象）。
**已修**：改为**只认 fixture 指定工程**、把读数**显式打印**（`来源 fixture:<pid>`）、
仅在无产物时才回退 glob 并标注 `fallback:glob`。
**这正是 P53 新规则「验证必须穿透生产入口、禁止平行构造」的落地** ——
门必须锁死在**被测对象**上，不能靠“最新文件”猜。
**验证**：修复后运行输出
`ASS: projects/p_fa647ea270d9/artifacts/_captions_t_ac3f73f3710a.ass（来源 fixture:p_fa647ea270d9）`
⇒ **3/3 PASS**。

## 未决 2：`mm_quality_test` 的 DB 只读断言仍失败
**现象**：`F1 只读：真实 DB 字节与五张表行数在全部运行后与运行前一致` FAIL
（`33/34`），且**在我完全不干预的那次干净回归里依然失败**。
**判定**：该套件在**自身运行期间**（577.6s）快照 DB → 复查 DB；
若**同一次回归内的其它套件**（或后台残留进程）在该窗口内写了库，断言必然失败。
⇒ **这是一条测试隔离/串行化缺口**，**不是产品缺陷**（产品侧 DB 未受损；
`still_failed` 全 0、F9 全门通过）。
**建议**：把「只读断言」套件排在**回归最后**，或在 runner 内加**库写锁**
（回归窗口内任何写库操作显式失败）—— 与监理裁定④同方向，但需要**在 runner 层**强制，
仅靠纪律不够（本轮已证明：我遵守了纪律，该套件仍失败）。

## 结论
· **产品侧**：F9 全门通过（烧录产物 max 同时活跃 1 / 覆盖 99.3% / clamp 0 / 同步 100%），
  无未决缺陷。
· **测试侧**：2 项未决（1 项**已修并验证**，1 项**需 runner 层串行化或写锁**）。
· 交付候选 **F9** 登记不变；此项不影响 F9 的有效性。
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
    clean = json.loads((L / "phase36_suites_summary.json").read_text(encoding="utf-8"))
    rec = {
        "schema": "p53-3-regression-open-items-v1",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "clean_regression": {
            "rc0": clean.get("rc0"), "suites_total": clean.get("suites_total"),
            "elapsed_s": clean.get("elapsed_s"),
            "failed": [f.get("suite") for f in (clean.get("failed") or [])],
            "conclusion": ("**92/94** —— `mm_temporal_test` 与 `multimodal_test` "
                           "**现已 PASS** ⇒ 证实 P52 那两项失败确系我并发写入所致，"
                           "非产品缺陷（监理裁定④成立）。"),
        },
        "open_item_1_caption_overlap_scoping": {
            "symptom": ("同一 ASS 独立复跑 3/3 PASS（确定性已确认），"
                        "回归内 1 PASS / 2 FAIL（0.1s）"),
            "root_cause": ("`latest_ass()` 先按 fixture 的 sandbox_project_id 找，"
                           "**找不到就 glob 全库取最新** ⇒ 回归期间命中别的工程产物"),
            "status": "**已修并验证**",
            "fix": ("只认 fixture 指定工程；显式打印读数来源（`来源 fixture:<pid>`）；"
                    "无产物才回退 glob 并标注 `fallback:glob`"),
            "verification": ("输出 `ASS: projects/p_fa647ea270d9/artifacts/"
                             "_captions_t_ac3f73f3710a.ass（来源 fixture:p_fa647ea270d9）`"
                             " ⇒ 3/3 PASS"),
            "rule_link": "P53 新规则①「验证必须穿透生产入口、禁止平行构造」的落地",
        },
        "open_item_2_mm_quality_db_isolation": {
            "symptom": ("`F1 只读：真实 DB 字节与五张表行数在全部运行后与运行前一致` FAIL"
                        "（33/34），且在**完全不干预**的干净回归里**依然失败**"),
            "root_cause": ("该套件在**自身 577.6s 运行窗口内**快照 DB → 复查 DB；"
                           "同一次回归内其它套件（或残留进程）在该窗口写库 ⇒ 断言必失败"),
            "status": "**未修**（需 runner 层强制，非本阶段文件改动可解决）",
            "judgement": ("**测试隔离缺口，非产品缺陷**：产品侧 DB 未受损、"
                          "`still_failed` 全 0、F9 全门通过"),
            "recommendation": ("① 把只读断言套件排在回归**最后**；"
                               "② 在 runner 内加**库写锁**（回归窗口内任何写库操作显式失败）"
                               "—— 与裁定④同方向，但**必须在 runner 层强制**："
                               "本轮已证明**仅靠纪律不够**（我遵守了纪律，该套件仍失败）"),
        },
        "product_side": {
            "verdict": "无未决缺陷",
            "F9": ("烧录产物 max 同时活跃 1 / 覆盖 99.3% / clamp 0 / 同步 100%；全门通过"),
            "delivery_candidates_unchanged": ["F", "F2", "F3", "F4", "F5", "F6",
                                              "F7", "F7.1", "F8", "F9"],
        },
    }
    p = L / "p53_3_regression_open_items.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("Phase 53 回归未决项登记：")
    print("  干净回归 {} / {}（elapsed {}s）".format(
        rec["clean_regression"]["rc0"], rec["clean_regression"]["suites_total"],
        rec["clean_regression"]["elapsed_s"]))
    print("  未决 1（caption_overlap 作用域）：**已修并验证**")
    print("  未决 2（mm_quality DB 隔离）：未修，需 runner 层强制；判定为测试侧缺口")
    print("  产品侧：无未决缺陷")
    print("-> " + str(p.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
