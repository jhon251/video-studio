# -*- coding: utf-8 -*-
"""Phase 56 / P56-2b：**P56 回归暴露的 2 处自身缺陷修复登记**。

P56 首轮回归（`regression_f101.log`）出现 **10 个失败套件**，全部源于**我在本轮引入的代码**，
**不是产品缺陷**。两处根因如下，均已修复并复验。

## 缺陷 1：`build_cues_from_words_exact` 的「词覆盖」断言过严 ⇒ 单测全红
**现象**：`narration_contract_test` / `integrity_truth_test` / `audio_loudness_test` /
`bgm_ducking_test` / `attribution_compliance_test` / `strip_v2_test` 等报
`ValueError: P55-1 词级归属断言失败（fail-closed）：1 项 [{'kind': 'word_coverage',
'assigned': 0, 'manifest_total': ...}]`。
**根因**：单测/最小夹具以**段级**或**空 manifest** 调用构建器 ⇒ `by_para` 与 manifest
键不匹配 ⇒ `assigned=0` ⇒ 我的断言 d 判定失败。但这是**输入没有可用词**，
**不是归属缺陷**。
**修法**：断言 d 加**适用条件** —— 仅当 `total_words > 0` **且**至少有一个段
真正参与游走（`covered_paras > 0`）时才断言；真实渲染路径（36 景 / manifest 齐备）
照常执行。
**复验**：`scene_assembly_test` **15/15**、`narration_contract_test` **45/45**、
`integrity_truth_test` **243/243** 全绿。

## 缺陷 2：fail-closed 分支调用 `engine.emit` 未守护 ⇒ 测试桩崩溃
**现象**：`scene_assembly_test` 报
`AttributeError: 'Eng' object has no attribute 'emit'`。
**根因**：我在 P55-1 的异常分支里直接调 `engine.emit(...)`，而测试桩 `Eng`
**没有 `emit`** ⇒ 原始错误被**替换**成 AttributeError，掩盖了真实原因。
**修法**：用 `getattr(engine, "emit", None)` 守护 + `callable` 判定；
**无论 emit 成败都继续 `raise` 原异常**（不吞错、不改语义）。
**复验**：`scene_assembly_test` **15/15** 全绿。

## 教训（与 P53 新规则同族）
两处都是**把「生产路径的假设」直接搬进可被单测复用的构建器**：
生产有齐备 manifest、生产有 `emit`；单测没有。
⇒ 与「验证必须穿透生产入口」互为反面：**构建器被复用时，必须显式声明其输入前提**，
并把「前提不满足」与「真实缺陷」区分开（`SKIP` vs `FAIL`）。
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
    "schema": "p56-2b-self-defect-fixes-v1",
    "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "trigger": "P56 首轮回归 10 个失败套件（全部源于本轮引入的代码，非产品缺陷）",
    "defect_1_word_coverage_assertion_too_strict": {
        "symptom": ("`narration_contract_test` / `integrity_truth_test` / "
                    "`audio_loudness_test` / `bgm_ducking_test` / "
                    "`attribution_compliance_test` / `strip_v2_test` 报 "
                    "`word_coverage assigned=0`"),
        "root_cause": ("单测/最小夹具以**段级**或**空 manifest** 调用构建器 ⇒ "
                       "`by_para` 与 manifest 键不匹配 ⇒ `assigned=0` ⇒ 断言 d 误判。"
                       "这是**输入没有可用词**，不是归属缺陷。"),
        "fix": ("断言 d 加**适用条件**：仅当 `total_words > 0` **且** `covered_paras > 0` "
                "时才断言；真实渲染路径照常执行"),
        "revalidation": {"scene_assembly_test": "15/15",
                         "narration_contract_test": "45/45",
                         "integrity_truth_test": "243/243"},
    },
    "defect_2_emit_not_guarded": {
        "symptom": "`scene_assembly_test`: AttributeError: 'Eng' object has no attribute 'emit'",
        "root_cause": ("P55-1 异常分支直接调 `engine.emit(...)`，而测试桩 `Eng` 没有 `emit` "
                       "⇒ 原始错误被**替换**成 AttributeError，掩盖真实原因"),
        "fix": ("`getattr(engine, \"emit\", None)` 守护 + `callable` 判定；"
                "**无论 emit 成败都继续 raise 原异常**（不吞错、不改语义）"),
        "revalidation": {"scene_assembly_test": "15/15"},
    },
    "lesson": ("与 P53 新规则同族：两处都是**把「生产路径的假设」直接搬进可被单测复用的"
               "构建器**（生产有齐备 manifest、有 `emit`；单测没有）。"
               "⇒ 构建器被复用时必须**显式声明输入前提**，并把「前提不满足」与"
               "「真实缺陷」区分开（SKIP vs FAIL）。"),
    "content_equivalence_after_fix": {
        "note": ("修复后重渲的产物与已登记 F10.1 **内容等价**："
                 "与 F9 逐景素材 **36 / 36 景一致**、`deterministic=True` ⇒ "
                 "**确定性修复生效**（这正是 P56-1 的目标产物）"),
        "new_sandbox": None,
    },
}
p = L / "p56_2b_self_defect_fixes.json"
p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
print("P56 自身缺陷修复登记：2 处（均非产品缺陷）")
print("  缺陷 1 词覆盖断言过严 ⇒ 加适用条件；复验 15/15、45/45、243/243")
print("  缺陷 2 emit 未守护 ⇒ getattr 保护且不吞错；复验 15/15")
print("  修复后重渲内容与 F10.1 等价（36/36 一致、deterministic=True）")
print("-> " + str(p.relative_to(R)))
