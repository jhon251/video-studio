# 5-G 规划方案：多模态真值集 v2 扩充与全量评估复验（R3）

> 阶段: 5-G（规划稿，等待人工授权；未动任何代码/测试/基线）
> 上游: 5-F CLOSED（基线 `5.x-phase5f-baseline` sha256 `e4dd33ad…`，当前唯一基准）
> 纪律: 单一核心能力，不混合未授权子阶段；不进入 5.x Final；不自动发布/换材/绕过人工决策

---

## 0. 5-A～5-F 能力、遗留与边界（现状梳理）

### 已完成能力

| 阶段 | 组件 | 能力 | 状态 |
|---|---|---|---|
| 4-B | core/semantics.py | 文本↔素材语义一致性（类别式规则，冻结真值钉定 `a_2ed5f41d6b58`） | ✅ |
| 5-A | core/multimodal.py | 单帧像素证据（CLIP 3 帧：域一致性/相似度/边际/top-k） | ✅ |
| 5-D | core/mm_temporal.py | 多帧时序证据（CLIP 7 帧 + 帧间一致性 + 逐帧投票 + 结构性 UNKNOWN 唯一来源） | ✅ |
| 5-E | core/mm_quality.py | 冻结真值集上的校准/覆盖度/边界距离/证据分级/四段式可解释链/敏感性披露 | ✅ |
| 5-F | core/mm_judge.py | 三层证据最终裁决（J0–J6 + 5 级优先级 + 不选边冲突处理 + 10 理由码；**零阈值、只读零动作**） | ✅ |

### 遗留（#43–#50 + R1–R6）

| 项 | 内容 | 状态 |
|---|---|---|
| #43/#44 | 真值集小（14 例）且同质（全部来自单一项目 `p_f4b466a4a024`） | **LIMITATION（未解）** |
| #47 | top-1 一致性仅解释性 | LIMITATION |
| #49 | Judge 未接入生产判定链（默认关闭、只读） | BY DESIGN |
| #50 | 最终 MATCH 需全层一致 → MATCH 数低于单层 | BY DESIGN |
| R1 | 字幕区域掩码后帧间一致性 | 未来研究（触 5-D 内部） |
| R2 | 候选"成片抽帧口径"预测量 | 未来研究（5-B 侧新证据） |
| R3 | **扩充真值集（多镜头/运动素材/更多项目）** | **值得进入最终产品；5-F 报告自荐"Final 后第一优先项"** |
| R4 | 报告层区分 UNKNOWN 两种语义 | 值得进入最终产品（理由码层已具备等价物） |
| R5 | S06 front/back | 产品决策（需 4-C 人工 + redo） |
| R6 | top-1 一致性仅展示 | 值得进入最终产品（仅展示） |

### 当前能力边界（一句话）

评估/裁决层在**单一项目、14 个同质用例**上可信；**一旦真实制作跨越多项目、多镜头、运动素材，14 例真值集无法证明 Judge/校准层的结论仍然成立**——这就是 5-G 要补的能力边界。

---

## 1. 5-G 核心能力（一个）

> **把冻结真值集从"单一项目 × 14 同质用例"扩充为"多项目 × 多镜头 × 运动素材"的真值集 v2（≥40 例），
> 并在 v2 上全量复验 5-E 校准层与 5-F Judge——不修改任何评分/判定逻辑与阈值。**

（对应 5-F 遗留 R3；直接收敛 #43/#44。）

**为什么选它（对照落选项）**：
- 纯评估、**零行为风险**（不改 4-B/5-A/5-D/Judge 的判定逻辑与阈值，不改生产链任何行为）；
- 是 5-F 报告自荐的"Final 后第一优先项"，且是 #43/#44 的直接收敛路径；
- 为后续一切（#49 Judge 接线、生产报告 R4、乃至 5.x Final）提供**可信度量基础**——没有 v2，任何"实际制作能力提升"的宣称都无法被可信度量；
- 落选：#49 Judge 接线（触生产行为边界，需独立授权）、R4 报告接线（生产报告层代码）、R1/R2（研究项）、SS 系供给扩池（生产供给线，非 5.x 评估子系统）——**均列为 5-G 非目标**。

---

## 2. 目标与非目标

**目标（全量）**：
1. `mm_truth_set_v2.json`（schema `mm-truth-set-v2`）：≥40 例（v1 14 例原样并入 + ≥26 新例）
2. 覆盖矩阵（硬性）：≥3 个真实项目 · ≥10 多镜头用例 · ≥10 运动素材用例 · ≥6 UNKNOWN/fail-closed 边界类（含 R4 的两种 UNKNOWN 语义分型用例）
3. 每例**看片/看帧人工标注**，双轮标注一致性 ≥80%，标注分歧逐条归因
4. mm_quality + mm_judge 在 v2 上全量评估：v1 14 例判定**零回归**；新例逐类结果披露（含分类别 UNKNOWN 率与精确率）
5. 敏感性披露（v2 重跑：阈值扰动下 UNKNOWN 稳健性）
6. #43/#44 以证据改写（narrowed/resolved 按实测）；报告/README/STATUS/CHANGELOG 同步

**非目标（明确排除）**：
- ❌ Judge 接入生产判定链（#49 维持默认关闭）
- ❌ 生产报告层改造（R4 生产接线另立项）
- ❌ 修改 4-B/5-A/5-D/Judge 的评分与判定逻辑、阈值、词表
- ❌ R1（字幕掩码）、R2（抽帧口径预测量）
- ❌ 供给扩池落地/SS 系生产化、VIZ、任何正式生产 Run
- ❌ 进入 5.x Final

---

## 3. 允许修改范围

| 路径 | 允许 |
|---|---|
| `tests/fixtures/mm_truth_set_v2.json`（新增） | ✅ 新建 |
| `tests/fixtures/mm_truth_set_v1.json` | ❌ 只读（sha256 复验不变） |
| `src/video_studio/core/mm_quality.py` | ✅ **仅限**：v2 schema 校验器 + 真值集路径/版本参数化（`TRUTH_SET_REL` → 可注入）；评分/分级/可解释链逻辑零改动 |
| `src/video_studio/core/mm_judge.py` | ❌ 零改动（它经 mm_quality 的层证据运行，真值集版本对它透明） |
| `src/video_studio/core/multimodal.py / mm_temporal.py / semantics.py` | ❌ 零改动 |
| `tests/mm_quality_test.py / mm_judge_test.py` | ✅ 追加 v2 fixture/参数化测试（既有断言不删不改） |
| `docs/regression_2x/logs/`（新证据文件） | ✅ |
| 冻结模块 14 件、Run01–04、4.x 链路、生产 DB 生产项目 | ❌ 只读 |

---

## 4. DoD 硬标准（全布尔、可自动核对）

| # | 标准 | 核对方式 |
|---|---|---|
| D1 | `mm_truth_set_v2.json` 存在，schema=`mm-truth-set-v2`，**≥40 例**，覆盖矩阵全满足（≥3 项目/≥10 多镜头/≥10 运动/≥6 UNKNOWN 边界类），冻结时间与冻结策略字段齐备 | fixture 校验器 |
| D2 | `mm_truth_set_v1.json` sha256 与 5-F 基线记录**逐字节一致**（只读证明） | hash 对账 |
| D3 | v1 14 例在 v2 流程下判定与 5-F 冻结结论**零回归**（逐例比对） | 测试断言 |
| D4 | mm_quality/mm_judge 源文件 sha256 相对 5-F 基线：mm_judge **不变**；mm_quality 仅校验器/路径参数 diff（diff 审查通过） | git/hash 对账 |
| D5 | 源码级无阈值参数（沿用 5-F 证明法：mm_judge/mm_quality 不含 min_sim/min_vote_frac 等 token） | 静态扫描 |
| D6 | 单元测试：mm_quality_test + mm_judge_test + 新增 v2 测试 **全 rc=0**；总套件 **46+1 rc=0** | 回归电池 |
| D7 | 全量电池 3-A～5-E **25/25 rc=0** + 冻结日志恢复 True + 独立复验 **DRIFT 0** | 电池 summary |
| D8 | `phase5f_evidence.py`（或 5-G 同构脚本）→ **ALL_GREEN=true** | evidence JSON |
| D9 | v2 评估报告披露：分类别精确率/UNKNOWN 率 + 敏感性披露（v2 重跑）；双轮标注一致性 ≥80% + 分歧归因表 | 报告 §新 |
| D10 | KNOWN_ISSUES #43/#44 依证据改写（narrowed 或 resolved）；#49/#50/#47 原样 | KNOWN_ISSUES diff |

---

## 5. 测试与真实验证方案

1. **单元**：v2 校验器正/负用例（schema/覆盖矩阵/指纹钉定/fail-closed：损坏文件、缺字段、错误 fingerprint → 显式错误）
2. **真实验证（核心）**：选定 ≥3 个**真实项目**（含成片与冻结层证据者），跑只读校准 + Judge 全流程（同 5-F `--from-calibration` 路径），产出 v2 逐例判定
3. **标注协议（防 DS1 教训）**：标注员**必须看片/看帧**（抽帧 contact sheet），禁止仅凭标题/元数据标注；双轮独立标注 + 一致性对账
4. **回归**：R1–R8 同构迁移 + 全量电池 25/25 + 套件全 rc=0 + 冻结恢复 DRIFT 0
5. **零回归对账**：v1 14 例判定逐例比对 5-F 冻结结论

## 6. fail-closed / 人工审核边界

- 真值集文件指纹不符 → 评估层显式错误，拒绝运行（不静默降级）
- 标注冲突（人工 vs 全层一致）→ **人工权威**：以人工标注为真值，把该例写进"本体/标注修订记录"，**禁止反向调层迎合**
- 新例证据不足（层不可用/帧数不足）→ 该例标 UNKNOWN 类边界用例，**不作 PASS 统计**
- 真值集冻结需人工签核（authorized_by/at/ref 入 frozen_policy）

## 7. 与 4.x / 5-A～5-F 兼容

- v1 文件与指纹不动（D2）；v2 为**新增文件 + 加载参数化**，v1 流程可随时回退复现
- 4-B/5-A/5-D/Judge 源码与行为零改动 → 5-F DoD 全部继续成立
- 生产链（Claim/HITL/append-only/许可门禁/旁白完整性/时间轴/响度）零触碰
- 基线链：`5.x-phase5f-baseline` 保持只读；5-G 完成后新增 `5.x-phase5g-baseline`，delta 独立披露

## 8. 风险与已知限制

| 风险 | 缓解 |
|---|---|
| 真实多镜头/运动素材的存量不足（历史项目以静帧为主） | 先做项目普查（步骤 1）；不足部分**如实记 LIMITATION**，不虚构用例 |
| 人工标注成本（≥40 例 × 看片双轮） | 分批标注 + 每批落盘（DS2 模式）；抽样复验 |
| v2 暴露评估层在运动/多镜头上的真实弱点 → 精确率下降 | 这正是实验目的；**禁止调阈值救指标**；弱点进 KNOWN_ISSUES 与 5-H 候选 |
| schema v2 与 v1 校验器不兼容 | 校验器按 schema 版本分支；v1 路径回归测试保持 |
| 判定 vs 真值分歧被误读为"评估退化" | 报告显式区分"覆盖扩展"与"判定退化"；分歧逐条归因 |

## 9. baseline / manifest / SHA256 / 回滚

- 起点：`5.x-phase5f-baseline`（`e4dd33ad…`）只读
- 完成后：`make_baseline.py 5.x-phase5g-baseline --no-docs` → manifest 单独生成 → `verify_baseline.py` 期望 MATCH → `baseline_delta.py 5.x-phase5f-baseline` 独立披露 → `make_snapshot.py 5.x-phase5g-<date>`
- 回滚：删除 v2 fixture + 还原 mm_quality 参数化 diff + 还原测试追加 → 即回到 5-F 基线态（无生产影响面）

## 10. 验收方式（建议）

人工授权后按序执行，全部门槛满足方可声明 5-G DONE：
1. 项目普查与用例清单（含覆盖矩阵）先行落盘并获确认
2. 双轮标注 + 一致性对账
3. v2 评估全量运行 + 单元/回归全绿
4. 报告/README/STATUS/CHANGELOG/KNOWN_ISSUES 同步
5. 冻结 5.x-phase5g-baseline + 快照
6. STOP，不进入 5.x Final

---

## 附：执行顺序（授权后）

A. 项目普查（可用成片/层证据盘点）→ B. ECT 风格期望域标注草案 → C. 抽帧 contact-sheet 人工双轮标注 → D. v2 fixture 冻结（签核）→ E. 校验器/加载参数化（唯一代码改动）→ F. 单元 + 回归 + v2 全量评估 → G. 报告/KNOWN_ISSUES/基线/快照 → STOP
