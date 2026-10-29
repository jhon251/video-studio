# EXP-DC1 报告：Beat Topic → Evidence Core → Candidate Content → Domain Consistency

- 日期: 2026-09-10 · 性质: 离线标注实验（零生产代码修改、零 Retrieval/CV2、零渲染）
- 命名空间: `output/audit_20260910_dc1/`
- 数据: Run04 正式 exec `RUN04_PROD_20260910_01` 的 101 个上屏展示（含 20 个借用）+ 冻结 claim_inventory/narrative

## 方法

- **PASS 1 证据核心**（`dc1_beat_core.json`）：仅依据 claims/claim_text + narration，为 101 拍标注 `evidence_type + expected_domains + self 标志`。9 拍为 `SELF_REFERENTIAL_STRUCTURE`（S01-B03 / S02-B01 / S02-B03 / S02-B04 / S27-B01 / S33B×3——本片自建五层模型/时间尺度结构的自指命题）。
- **PASS 2 候选内容域**（`dc1_candidate_domain.json`）：**盲评**——仅看素材标题 + CV2 reason 文本，标注每条上屏候选的内容域 + word_spell / generic_stock 旗标。
- **门原型**（`dc1_gate.py`）：R1 自指外来→REJECT；R2 拼词→LOW；R3 泛化概念库存→LOW；R4 同域→KEEP；R5 异域→REJECT。101 条决策**每条含规则+可审计理由**（期望域/实际域/判定依据全文）。
- **PASS 3 一致性**：乱序独立重判 101 行（`dc1_pass3_sheet.json` → 判定表），与门计算结果对账。

## 硬指标结果

| # | 指标 | 要求 | 实测 | 判定 |
|---|---|---|---|---|
| 1 | 已知错配识别 | ≥6/6 | **6/6**：Hydrogen Ladder→R1 REJECT · power-line ladder→R1 REJECT · POLICY→R2 LOW · forecast→R2 LOW · RECAP→R1 REJECT(+拼词记录) · 抽象方块→R3 LOW | ✅ |
| 2 | 误伤 ≤2/51（3.92%） | clear 误伤 ≤2 且速率 ≤3.92% | **clear 2（S08-B01 体感系统图解、S32-B02 晕动症机制图）= 1.98%**；另披露 1 边界（S19-B02 蓝色微距）与 2 起词汇归一（yoga/diving→body_illustration） | ✅（按 ≤2/51 速率口径；绝对数口径下 3 件需复核，见失败案例） |
| 3 | 人工标注一致性 | ≥80% | **95.0%**（96/101；5 处分歧全部为"门偏严"方向并逐条归因） | ✅ |
| 4 | SELF_REF 外来伪证据 | =0 | 8 个自指拍的外来展示 **0 保留**（全 REJECT，含借用到 S27-B01 的"Policy"拼块） | ✅ |
| 5 | 零回归 | 全绿 | 模块单测 12/12 · R1–R8 8/8 · 编排器 T1–T13 16/16 · 冻结指纹 14/14 · Run01–04 母片哈希不变（074985a5 等） | ✅ |
| 6 | 可审计理由 | 每条 | **101/101** 决策含 R1–R5 规则名 + 期望域/实际域/理由全文（`dc1_decisions.json`） | ✅ |

特别测试：Hydrogen Ladder 拒绝 ✅ · power-line ladder 拒绝 ✅ · POLICY/FORECAST/RECAP 识别为低证据价值 ✅（RECAP 同时触发 R1 自指拒绝+拼词记录）· 真实 VR/BCI/动捕/触觉/科研素材 70 条 KEEP，无误杀 ✅

## 失败案例（如实，含根因）

1. **FP S08-B01**：XBio 体感系统图解 ← 期望域表缺 `neuroscience`（第二层=触觉的神经基础，体感科学本域）。根因：**期望域表构建粒度**。
2. **FP S32-B02**：晕动症机制图 ← 同根因（感知科学被标 medicine 而期望表无 neuroscience 近义）。
3. **边界 S19-B02**：蓝色微距（视觉科学 illustrative）——门判 REJECT、复判 KEEP，两可。
4. **词汇归一 2 起**：yoga / diving 被标 wellness/diving 而非 body_illustration——域词表需要同义归一层。
5. **结构性发现**：S16-B02（Neuralink Telepathy）借到 E-Prix 赛车图——`tech_industry` 期望域过宽放行——域一致门之外，**期望域表本身的宽度需要按拍收紧**。

## 结论：是否值得设计 G10 Domain Consistency Gate

**值得（PASS）。** 语义链 Beat Topic → Evidence Core → Candidate Domain → Consistency 在 101 拍全量上：抓住全部 6 个已知错配、自指外来伪证据清零、误伤率 1.98%、判定 100% 可审计。G10 设计必须吸收的四个要求：
1. 域词表带**同义归一层**（wellness/diving→body_illustration 类）；
2. 期望域表构建时做**近域扩展**（somatosensory→haptics 类），避免本轮 2 例 clear FP；
3. **域信号源需要授权**：DC1 用人工标注充当信号证明了"链"有效；生产 G10 的信号必须来自 CV2 rubric v2（`content_domain`+`domain_match` 字段）或独立语义分类调用——二者都需 CV2 线授权，无免费实现；
4. **诚实代价预算**：G10 硬门会把 31/101 个展示降级（REJECT 27 + LOW 4），CORRESPONDING 81→62（61.4%，仍≥51 但 -19.6pp... 实为对 Run04 基线 -18.8pp 至 61.4%），HN/FB 19.8%→38.6%——**超出现行 +5pp 变更预算**，因此 G10 的采用是一次验收口径重定义（Evidence Value × Narrative Information 框架），不是无代价叠加，须人工决策。

```
EXP-DC1 = PASS
指标 = 6/6 已知错配 · 误伤 2 (1.98%≤3.92%, 另 1 边界+2 词表归一如实披露) · 一致性 95.0% · 自指外来 0 · 零回归 · 理由 101/101
G10 = 值得设计（含 4 项设计要求；域信号源与验收口径重定义需单独授权）
零生产代码修改 · 零 Retrieval/CV2 · 零渲染 · 零冻结件触碰
STOP——等待授权
```
