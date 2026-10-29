# Run04 审片工程归因与修复计划（PLAN / AUDIT ONLY）

- 日期: 2026-09-10 · 模式: 只读归因（零代码修改、零 Retrieval/CV2、零生产）
- 证据基座: `run04/exec/RUN04_PROD_20260910_01/`（assignment_policy / shot_provenance / gate_decisions）+ run03 冻结 retrieval_index / cv2_results + claims/claim_inventory.json（113 claims）

## 1. 问题归因表

分类码: A=检索缺陷 B=候选质量缺陷 C=证据域缺陷 D=指派缺陷 E=编排/门缺陷 F=渲染/节奏缺陷 G=可接受的人工编辑议题

| # | 审片发现 | 实证（artifact 反查） | 归因（主→次） |
|---|---|---|---|
| P0 | 0:17–0:21 "Clean Hydrogen Ladder 5.0" 与主题完全无关 | S02-B01 → `r3_S02-B01_1` = `File:2023-10-19 Clean Hydrogen Ladder 5.0.png`；检索 query = **"five level technology ladder"**（对旁白隐喻"五层技术阶梯"的字面检索）；CV2 = **CU/HIGH/0.8**，理由原文"图表内容直接对应口播中的'技术阶梯'"——VLM 只做了**形匹配**（有阶梯、有层级），未验证阶梯的**内容域**（氢能源经济 ≠ 本片自指的五层结构模型）。该拍 claim 本身（claim_inventory: S02-B02#C1 等）是自指结构命题——任何实拍/外来图表在证据域上都不可匹配 | **C 证据域缺陷（主）** → A（隐喻字面检索）→ E（G0–G9 无内容域一致性门） |
| P1 | Run02 自制五层阶梯/结尾框架图消失；学术证据明显增强 | run04 无路由概念（VIZ 未授权 → 无 VIZ 拍），exp225 图表按授权边界不可用；同时真实学术/具名主体素材确实增加 | **G（合理 routing 变化，非能力回退）** + 暴露"结构锚点"能力缺口（开场引入与结尾回顾两个结构拍失去视觉锚） |
| P2a | 0:07–0:21 约 14s 静帧/低信息密度 | S01-B01/B02/B03 全 CU（0.65/0.5/0.6），CV2 理由自认"较难承载抽象概念的视觉表达""与'几层'比喻缺乏直接对应"；且全片 clip 为静帧（static-first，MOTION 死代码） | **F（静帧节奏设计）** → D（弱 CU 元叙事拍被记为 CORRESPONDING 而非诚实中性）→ B（抽象旁白本身难有实拍证据） |
| P2b | 8:16–8:45 尾段静帧约 29s | 481–526s 七拍均为静帧；素材形匹配家族："Ladder ascending to power lines"（回顾拍又见"梯子"形匹配）、"RECAP"木块、手术器械（字面"手术室"） | **F（静帧节奏）** → A/C（回顾词的字面形匹配） |
| P2c | POLICY / FORECAST / RECAP 木块字 = 泛化图库家族 | S31-B01 Scrabble"Policy"、S29-B04"forecast"木块、S33B-B02"RECAP"字母、S20-B03 抽象方块——**图像拼写旁白关键词**，信息密度为零但"形式合法" | **A/C（关键词字面视觉化）→ E（无"文字拼词图"家族门）** |

## 2. 专项回答

**#6 现有 Visual Orchestration Layer 能否拦截"形式合法、质量合格、内容域错误"？**
**不能。** G0–G9 = 存在性/MIME/分辨率/纵横比/内容重复/命名空间/出处链（确定性）+ 拼贴/文字密度/水印（advisory）。语义域一致性不在其内——编排层把语义判断完全委托给冻结 CV2 的合格性（USABLE/CU）。P0 资产走完了全部九道门。

**#7 CV2 为什么放过 Hydrogen Ladder？**
冻结 rubric 只有 `visual_usability`（质量/真实感）与 `semantic_relevance`（口播词 ↔ 画面内容的 VLM 级匹配）——VLM 看到"带层级的阶梯图"对应"五层技术阶梯"即判 HIGH 0.8；rubric **没有 `content_domain` / `domain_match` 字段**，不问"这幅图来自哪个领域、与命题的证据核心是否同域"。另外阈值为 CU 即合格。**Evidence Type / Evidence Core 在研究层已存在**（claim_inventory 113 条含 beat/claim_type/重要性；Stage 22 实体类分类学；`docs/证据语义回归基准.md`、`V2.1_B路线_Evidence聚合层设计.md`）但从未落实为生产硬门。

**#8 关键词白名单 vs 语义域验证**
采用语义链 **Beat Topic → Evidence Core → Candidate Content Domain → Domain Consistency**。拒绝关键词规则：它对 P0 只是侥幸（文件名恰含 Hydrogen）；对"power-line ladder"（无错误域关键词）、"RECAP"木块（词是对的，图是零信息）完全失效，且隐喻/跨语言标题会双向失效。证据核心表可直接由 claim_inventory（beat→claim_text/claim_type）+ narrative 结构生成。

**#9 自制图表恢复的独立判断**
1. **不恢复 Run02 exp225 图表**：实验资产（sub-HD、已封存、跨命名空间禁令）。
2. **能力回退认定不成立**：P1 是"VIZ 未授权 + 诚实回退"的合理 routing 结果；但确实暴露**结构锚点能力缺口**（S02-B01 引入拍 + S33B 回顾三拍）。
3. 生产安全的近期选项（无需 VIZ 授权）：把结构自指拍路由为 HN 诚实借用（角标），消除 P0 类域错配上屏——纯 routing/配置层，属下一版生产授权范围。
4. 结构文字卡（typographic structure card，由 narrative 章节数据确定性生成）**属于 VIZ 家族**（生成式信息图形），不能伪装成"非 VIZ"；要么作为窄授权的 VIZ 子类立项，要么不做。不做换皮规避。
5. 是否真的需要首尾图表：需要的是**结构锚点能力**，不是"图表"本身——能力落点可以是 4 或 3。

## 3. 优先级

1. **P0**（域错配，可信度风险）：立即缓解 = 结构自指拍路由 HN（下一版生产配置授权）；系统性修复 = EXP-DC1 → G10 域一致性门（需领域信号授权）。
2. **P2c**（拼词图家族）：并入 EXP-DC1 同一标注集与门规则。
3. **P2a/P2b**（静帧节奏）：F 类，独立"motion/pacing"授权线（当前变更集明确排除，不在本计划动工）。
4. **P1**（结构锚点）：决策项（3 或 4），非缺陷修复。

## 4. 最小修复方案

| 层 | 动作 | 授权需求 |
|---|---|---|
| EXP-DC1（先做，离线） | 构建 Beat→Evidence Core 表（claim_inventory+narrative）；对当前上屏候选做域标注（标题+人工）；原型化 G10 域一致性规则并回放 run04 决策 | 只读+audit 命名空间（同 EXP-VG 模式） |
| G10 实现 | 编排层新增域一致性门：Evidence Core ↔ Candidate Domain 不一致 → BLOCK；部分一致 → DEMOTE。**需要域信号源**：CV2 rubric v2（`content_domain`+`domain_match` 字段，需 CV2 线授权）或独立语义分类调用（同等授权权重）——无免费实现，如实声明 | 新授权 |
| 结构拍路由 | S02-B01 / S33B-B01–B03 / S29-B04 / S31-B01 等结构自指与拼词拍 → HN 诚实借用（角标），下一版生产配置生效 | 下一版生产配置授权 |
| pacing | motion/pacing 授权线（单列） | 新授权 |

## 5. 是否需要新实验 + 硬指标

**EXP-DC1（域一致性门原型，离线，建议立即）**
- 成功：(a) P0 资产被标记域错配；(b) 审片确认的拼词图家族（Policy/Forecast/RECAP）与 power-line ladder 全部被标记（≥6/6）；(c) 确认良好素材误伤 ≤2/51；(d) 标注一致性 ≥80%（两次独立标注）；(e) 纯增量层——不改变 patterns/CORRESPONDING 既有验收。
- 失败：任一已知错配漏标或误伤 >2 → 规则重设计，不得进入 G10。

**EXP-DC2（CV2 rubric v2，需 CV2 线授权，DC1 之后）**
- 成功：在已标注集上 `domain_match` 捕获 ≥90% 错配；与人工标注一致 ≥90%；既有 usability/relevance 字段回归不变。
- 失败：一致 <90% → rubric 迭代，不得替换现行冻结 rubric。

**EXP-SA1（结构锚点 A/B，条件性——依赖评分者）**
- 对比 现状照片 vs HN 角标借用 vs 结构文字卡（若窄授权）：域错配数=0 为硬指标；锚点识别为主观项，仅人工评分，不虚构结论。

## 6. 是否可进入下一版生产

**可以有条件进入**：
- 无需等待新实验即可进入的版本：把结构自指/拼词拍路由为 HN 诚实借用（P0/P2c 的即时缓解，配置层），其余链路维持已 PASS 的编排层。
- **不建议**在 EXP-DC1+G10 落地前宣布 P0 类问题"已解决"——当前层对该类别无拦截能力（本文 §2#6）。
- VIZ 重引入与结构文字卡 = 独立授权决策，不与本轮捆绑。

```
RUN04 REVIEW ATTRIBUTION = COMPLETE
P0 = C→A/E（证据域缺陷为主；域一致性门缺失实证）
P1 = G（合理 routing）+ 结构锚点能力缺口（决策项）
P2 = F 静帧节奏（独立线）+ A/C 拼词图家族（并入 DC1）
新实验 = EXP-DC1（立即建议）· EXP-DC2（需 CV2 授权）· EXP-SA1（条件性）
下一版生产 = 有条件可进入（结构拍 HN 路由缓解；域门系统性修复在 DC1+G10 之后）
本轮零修改 · 零 Retrieval/CV2 · 零生产
STOP——等待授权
```
