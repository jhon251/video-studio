# Stage 33 — STAGE 22.1: Query Execution Completeness + Retrieval Diversity Re-validation

> **性质**:只读诊断 + research harness 修复。生产检索/冻结模块/Gate/CV2/baseline/Run 01 母片零改动。
> harness 修复仅存在于 `output/stage22_visual_quality/retrieval_v2.py`(研究侧);`output/prod01/retrieval/` 原样保留。
> 机器可读:`output/stage22_visual_quality/stage22_1_query_completeness.json`

## 1. Harness Bug 精确定义(以执行证据确认,非代码猜测)

- **名称**:beat 级 query-loop 提前 break;
- **位置**:`output/prod01/retrieval_run.py`(Run 01 的检索 harness,**非冻结模块**);
- **机制**:计划 query 按序执行(t1[:2]+t2[:1]),每条之后若 Wikimedia 候选累计 ≥4 即 break——剩余计划 query 从未搜索;**t3 被结构性排除在循环外**;
- **类型判定:B(beat 级 query-loop break)**——v2 重放在 32 个拍上留下了"跳过 query + 达阈 query"的执行证据;既非单 query 结果上限,也非 Wikimedia 内部行为;
- **设计归属**:冻结的 Stage 12 tier 体系确实有"上一层够用就停止升级"的哲学,harness 把它错误地实现在了平铺 query 循环上,且多样性代价从未被验证。分类:**受冻结哲学影响的实现缺陷,可在研究侧修复**;
- **重要自我修正**:Stage 22 初报"91/101 截断"是**高估**——旧索引把"执行了但 0 结果"的 query 误记为未执行。live replay 修正为 **32/101**。

## 2. 执行完整性(BEFORE → AFTER)

| 指标 | BEFORE | AFTER |
|---|---|---|
| planned queries | 301 | 301 |
| executed | 156(51.8%) | **301(100%)** |
| skipped | 145 | 0 |
| 完整执行拍数 | 10/101 | **101/101** |
| t1 / t2 执行率 | 89.6% / 69.3% | 100% / 100% |
| t3 | 本轮 0 拍计划 t3(harness 结构性遗漏——本轮零实际影响,已标记为潜在隐患) | — |
| break 类型 | B 级 break 确认 **32 拍** | — |

## 3. 候选池多样性变化

- 平均池:**5.2 → 7.4(+42%)**;30/101 拍获得新候选(集中在 32 个截断拍);
- **截断拍的分级分布**:A 级 11、B 级 17、C 级 3、D 级 1——截断不仅打击 C/D,**11 个 A 级强证据拍也损失了池多样性**(跳过的 query 里含有不同视觉家族:haptic glove、GPU、VR play space、neural electrode…)——截断同时喂养了 RC3 的族级单调。

## 4. 12 个 C/D 拍重新诊断(核心发现)

**8/12 个 C/D 拍在生产时本就已完整执行查询——它们的 generic 与截断无关**,只能归因 INTENT/池内容。截断只影响 4 个:

| 拍 | 被跳过的 query | 新池判定 | 结论 |
|---|---|---|---|
| **S16-B01** | `brain implant` | **File:BrainGate.jpg — USABLE/HIGH 0.85** | **真实证据损失实锤**:narration"侵入式 BCI 已在人体上工作"所需的恰是 BrainGate 人体临床试验影像,它就躺在被跳过的 query 下;生产时选了实验鼠(CU/M 0.62) |
| **S19-B01** | `brain prosthesis` | DOE 脑假体 CU/**HIGH** 0.8 | 相关性 MEDIUM→HIGH 升级,改变视觉决策 |
| S27-B01 | hourglass/time | 更多钟表/沙漏(0.95) | 无决策变化——intent 本身要钟表,瓶颈在 RC1 |
| S25B-B01 | game dev | Nintendo DS 等 NOT_USABLE | 无决策变化——池内容依旧 generic |

Pool-empty 组(S30-B02/S33B-B01/S17-B03/S13-B01/S05-B02/S04-B02)skipped=[],完整执行后池依旧空/弱——确认为 intent/覆盖边界问题。

## 5. Entity Query A/B 稳定性

- 原始:B 5 胜 / A 3 胜 / 2 平;
- 完整执行后:**S16-B01 翻转 TIE→A 胜**(BrainGate 0.85 > 实体 query 的牙科诊所照 0.72),其余 9 拍不变 → **B 4 胜 / A 4 胜 / 2 平**;
- **结论稳定:PARTIALLY_SUPPORTED**。实体 query 与完整执行是**互补杠杆**,而完整执行是更便宜、已验证的那个;实体 query 不应全局推广,应作为机构/临床类主张的可选 tier(EXP-22.2)。

## 6. 因果链验证

> Query truncation → 池多样性↓ → 证据候选缺失 → generic 占比↑ → Assignment 只能选 generic

**PARTIALLY_SUPPORTED**:
- CONFIRMED:截断发生(32 拍,B 型,重放证据);截断拍池更小;≥1 实锤证据损失(BrainGate);≥1 相关性级损失(S19-B01);
- NOT PROVEN:截断是审片 generic 印象的**首要**驱动——8/12 C/D 拍完整执行仍 generic;族级单调与 intent cliché 不依赖截断。

## 7. Root Cause Ranking 更新

**排序不变:#1 INTENT > #2 RETRIEVAL > #3 ASSIGNMENT/PRODUCTION-DESIGN。变化:**

1. **RC2 范围修正 + 权重上调**:广度缩水(91→32)但证据质量轴上**实锤了真实证据损失**(BrainGate 案例)——检索侧修复的性价比显著上升;
2. **RC1 强化**:8/12 C/D 拍完整执行仍 generic——intent/池内容是主导路径,"Retrieval harness bug 是真实工程缺陷,但不是 generic visual 的唯一/首要原因";
3. **RC3 不变**;截断跳过的 query 本含异族候选,即截断也间接喂养了族级单调。

## 8. P0/P1/P2 复查

均无需改判:P0 维持(诊断 KPI 部分支持/硬 Gate 不支持);P1 维持;P2 维持(补充:完整执行本身就会部分缓解族级单调,因为被跳过的 query 含异族候选)。

## 9. 对 Production 的建议(仅建议)

1. **R1**:query 完整执行修复值得进入生产——成本一行循环条件、零冻结触碰(检索 harness 非冻结件)、已证真实收益(BrainGate 案例);
2. **R2**:实体 query 不做全局推广,待 EXP-22.2 授权后作为机构/临床主张的可选 tier;
3. **R3**:最高杠杆仍是 RC1 的 intent 类型规范(meta/structure 型 → Honest Neutral 或 visualization)。

## 10. 是否需要下一阶段

需要,但顺序建议:EXP-22.2(完整执行 + 实体 tier)最便宜且已去风险;EXP-22.1(intent 类型)杠杆最高;EXP-22.3/22.4/22.5 随后。均需授权,本阶段未执行任何一项。

## 11. 冻结边界

零冻结模块修改;生产检索、Run 01 母片、baseline、Production Entry/Final Gate 全部原样;全部新数据在 `output/stage22_visual_quality/`。

```
STAGE 22.1 = DIAGNOSTIC COMPLETE · STOP
bug 定性 B 级 beat-loop break(重放实证) · 截断修正 91→32/101(诚实自我修正) · 完整性 51.8%→100% ·
池 5.2→7.4 · BrainGate 实锤证据损失(S16-B01) · 8/12 C/D 拍与截断无关(RC1 强化) ·
Entity A/B 稳定 PARTIALLY_SUPPORTED(4/4/2) · Root Cause 排序不变 · 修复建议 R1-R3 仅建议
STOP——不自行进入 Stage 23,不修改 Production
```
