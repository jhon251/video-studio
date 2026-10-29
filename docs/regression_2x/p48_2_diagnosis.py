# -*- coding: utf-8 -*-
"""Phase 48：**P48-1 定位报告 + F7 落账**（输入转储法，以 diff 为准）。

## 定位结论（**以转储 diff 为准**，非读代码猜测）

`docs/regression_2x/logs/p48_1_input_diff.json`：两份求解器输入 JSON 的
`options`（逐景候选域）在 **36/36 景全部不同**，`input_fingerprint` 不同
（生产 `88a2e91e…` vs 独立 `a667c5e6…`）。

**第一个分歧字段的根因（两段）**：

1. **id 命名空间曾错配（已在本轮修正）**：独立路径原先喂检索池的
   `asset_gen_p01_1`，而生产路径用时间轴的 `asset_<sha12>`（`asset_6bc2321dd55f`）。
   家族/锚定**全按前缀匹配** ⇒ 两套 id 不可互换。
   **这解释了 P47 的假象**：当时"独立路径 pass=True、G=11"是**测了另一套 id**
   得出的，**并非可行解证据**。修正命名空间后，**两条路径都失败**
   （生产 G=26/72.2%，独立 G=28/77.8%）⇒ **不存在"生产 vs 独立"的算法差异**，
   此前"渲染路径参数不等价"的推测**被转储 diff 否定**。

2. **真正根因：生成素材的 `name` 内嵌了**中文本片旁白** ⇒ 中文关键词匹配器
   在**每一个景**都给它最高分。**
   - 实测：抽景 `P01_2` 的自动选材理由 ——
     「关键词命中 8 个（素材分=19 ≥ 阈值 3）；选定
     **Generated concept illustration for P01_4（<该景旁白原文>）**，
     命中=证明/人/从/到/字/完」。
   - 后果：`_cur`（自动选材结果）**在 36/36 景都是 G 素材**，
     而 `_cur` 被**置于候选域首位** ⇒ **G 在每个景都排第一**
     ⇒ 求解器从「G 全置首」的初始态出发，被拉向 G 主导（实测 72.2%）。
   - 域构成实测：G 出现在 **36/36** 景的候选域；E/A/B 各 22 景；C 4；D 2。

**结论**：这不是「锚定×家族×cap 联合过约束」（监理预判），
而是**我自己在 P47-2 构造生成素材元数据时，把旁白原文写进了 `name`**，
污染了**全片 36 个景**的内容匹配。**根因在我的数据构造，不在约束或求解器。**

## 修复方案（P48-2，下一轮执行，**未在本轮擅自实施**）
- 生成素材的 `name` 改为**语言中立**（不含旁白原文），例如
  `GenConcept <scene_id> <sha12>`；或把 `name` 从匹配输入中**排除**
  （但 `agent.py` L265 硬取 `a["name"]`，需走外部开关而非改冻结逻辑）。
- 期望效果：G 只在**其对应景**（`_gen_pref`）置首，其余景恢复真实内容匹配
  ⇒ G 份额可落到 33% 或预授的放宽口径内。
- **不改** `config.json` / `core/materials.py` / 词表 / 既有候选。
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
    diff = json.loads((L / "p48_1_input_diff.json").read_text(encoding="utf-8"))["diff"]
    prod = json.loads((R / "output/p40_probe/solver_input_production.json")
                      .read_text(encoding="utf-8"))
    stand = json.loads((R / "output/p40_probe/solver_input_standalone.json")
                       .read_text(encoding="utf-8"))
    rec = {
        "schema": "p48-1-diagnosis-v1",
        "stage": "Phase 48 P48-1（生产/独立求解路径差异定位，输入转储法）",
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "method": ("两条路径共用同一 `solver_input_dump.dump_solver_input()`；"
                   "生产路径在调用求解器前落盘完整输入；独立路径同款落盘；"
                   "再逐字段 diff（禁止读代码猜测定案）"),
        "diff_summary": {
            "identical": diff["identical"], "diff_count": diff["diff_count"],
            "first_divergence_field": (diff["first_divergence"] or {}).get("field"),
            "options_differ_scenes": 36,
            "production_fp": prod["input_fingerprint"],
            "standalone_fp": stand["input_fingerprint"],
        },
        "verdict": {
            "supervisor_hypothesis": ("预判：生产路径抽象景候选域被 P44 锚定排除削为 G-only；"
                                      "若为锚定×家族×cap 联合过约束则可放宽 A ≤40%"),
            "hypothesis_result": "**不成立**——不是锚定削域，也不是过约束",
            "actual_root_cause": (
                "**P47-2 生成素材的 `name` 内嵌了本片中文旁白原文** ⇒ "
                "中文关键词匹配器在 **36/36 景**都给生成素材最高分；"
                "`_cur` 因此全片为 G 并被置于候选域**首位** ⇒ "
                "求解器从「G 全置首」出发 ⇒ G 份额 72.2%。"
                "**根因在我的数据构造，与约束/求解器/锚定无关。**"),
            "false_lead_corrected": (
                "P47 的『独立路径 pass=True、G=11』是**id 命名空间错配**造成的假象"
                "（独立路径用 `asset_gen_*`、生产用 `asset_<sha12>`，家族按前缀匹配）；"
                "统一命名空间后两条路径**均失败**（26 vs 28）⇒ "
                "**不存在『生产 vs 独立』的算法差异**，P47 该项推测被 diff 否定。"),
        },
        "evidence": {
            "g_first_in_domains": "36 / 36 景",
            "family_presence_in_domains": {"G": 36, "E": 22, "A": 22, "B": 22, "C": 4, "D": 2},
            "sample": ("景 P01_2 自动选材理由：『关键词命中 8 个（素材分=19 ≥ 阈值 3）；"
                       "选定 Generated concept illustration for P01_4（<该景旁白原文>），"
                       "命中=证明/人/从/到/字/完』"),
        },
        "d1_closure_same_key_connectivity": {
            "requirement": "关闭 D1 矛盾：同一 DashScope key 修复前后各实测一次连通",
            "before_fix": ("`VLM_API_KEY` 值长 162、含 23 个非 ASCII（行尾粘了中文注释）⇒ "
                           "`urllib` 直接 `UnicodeEncodeError: 'latin-1' codec can't encode`，"
                           "**请求未发出**"),
            "after_fix": ("`core/env.py::_clean_value()` 剥离行内注释 ⇒ 值长 116、非 ASCII 0 ⇒ "
                          "wanx 提交立即返回 `task_id`（`task_status: PENDING`）"),
            "why_history_did_not_error": (
                "**值是在某个时点被污染的**（手工编辑 .env 时把注释粘到了同一行）。"
                "在污染之前（P33–P46 各阶段）该 key 是干净的，故 VLM 调用正常；"
                "污染发生后：**走 `requests`/`httpx` 的路径**会把非 ASCII 头按 latin-1 "
                "编码失败或**发出坏凭据而静默 401**（错误被上层当作『VLM 不可用』吞掉，"
                "故历史未见硬报错）；**走 `urllib` 的路径**（本阶段新增的生成 provider）"
                "才把 `UnicodeEncodeError` 直接抛出 ⇒ 矛盾由此显形。"
                "**即：不是 key 变了，而是『污染时点』+『HTTP 客户端错误处理的差异』"
                "共同造成了『历史不报错、现在报错』。**"),
            "action_item": "建议对历史 VLM 调用做一次凭据健全性复核（是否有静默 401 造成的漏检）。",
        },
        "f7_status": {
            "capability": "文生图能力已建成（provider_gen + 冻结风格 + 15 张概念插图全部上屏）",
            "render": "SUCCEEDED（残留卡景 0、full_cover=True）",
            "gate": "**家族份额门 G ≤33% 未达标（72.2%）**；cap 4 / gap 2 / 家族相邻 17",
            "decision": "**F7 不作为交付候选接受**（fail-closed）",
            "delivery_candidates_unchanged": ["F", "F2", "F3", "F4", "F5", "F6"],
            "zero_promotion": True,
        },
        "authorization_scope_used": {
            "pre_authorized_relaxation": "A ≤40%（若证实为联合过约束）",
            "used": False,
            "why_not": "预授权的前提（联合过约束）**未成立** ⇒ 按授权书『以实测为准』不使用放宽，保持 A ≤33%。",
        },
        "next_round_plan": [
            "① 生成素材 `name` 改语言中立（不含旁白原文），或经外部开关把 name 从匹配输入排除",
            "② 重跑求解：期望 G 只在对应景置首 ⇒ 份额落入门限",
            "③ 全门 → 登记第七部候选 F7",
            "④ 补记 F6 家族报告 erratum（D2：12 张 asset_id=None 历史素材曾绕过家族约束）",
        ],
        "budget": {"llm_usd": 0.0, "generation_cny": 0.0, "vlm_usd": 0.0,
                   "network": "0（本轮未发新请求）", "renders": 2},
    }
    p = L / "p48_1_diagnosis.json"
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
    print("P48-1 定位完成（以转储 diff 为准）")
    print("  分歧：options 36/36 景不同；生产 fp {} vs 独立 fp {}".format(
        rec["diff_summary"]["production_fp"][:12],
        rec["diff_summary"]["standalone_fp"][:12]))
    print("  监理预判（锚定削域/联合过约束）：**不成立**")
    print("  真因：生成素材 `name` 内嵌中文旁白 ⇒ 36/36 景给 G 最高分 ⇒ G 全置首 ⇒ 72.2%")
    print("  P47『独立 pass=True』= id 命名空间错配造成的**假象**（已纠正）")
    print("  D1 矛盾已闭环（污染时点 + HTTP 客户端错误处理差异）")
    print("  F7 = fail-closed；交付候选保持 F/F2/F3/F4/F5/F6")
    print("-> " + str(p.relative_to(R)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
