# Stage 33 — Stage A: Visualization Generation Capability — Design & Experiment Registration

> **性质**:只读设计 + 实验注册。零生产修改、零渲染、零图片生成(注册 only)。
> 机器可读:`output/prod02/stage_a_design.json`

---

## 1. 核心问题

> **AI 能否自主生成 claim-centered 可视化,使其在 claim coverage / information gain / factual honesty 上达到或超越分析师设计的 mockup?**

这是 Stage 22 全系列的终极能力问题:路由已验证(EXP-B SUPPORTED)、查询已修复(R1)、评价已验证(22.7–22.11)——剩下唯一的缺口是:**谁来画这张图?**

---

## 2. 15 个实验对象(= EXP-B 相同拍集)

每个对象:
- **Control** = EXP-B 分析师设计的 mockup(已封存,seal `96969e60`)
- **Treatment** = AI 自动生成(claim → representation → layout → content → source annotation → QA)

15 个对象的 claim 结构覆盖 8 种 VIZ 类型:timeline ×1 · comparison ×2 · hierarchy_ladder ×5 · constraint_web ×2 · quantitative_chart ×2 · process_flow ×1 · checklist ×1 · split_panel ×1。

## 3. 生成管线(7 步)

```text
Step 1  Claim Parse       narration + claims + provenance → claim structure JSON
Step 2  Representation    claim structure → viz_type + layout spec (rule-based mapping)
Step 3  Content Extract   claim structure + provenance → labeled data points
Step 4  Code Generation   layout spec + labeled data → matplotlib Python code
Step 5  Execution         matplotlib → PNG
Step 6  QA                EQS-lite + factual correctness check
Step 7  Style Check       color tokens + typography + spacing consistency
```

**风格系统(优先级:信息正确 > 美观)**:
- Typography:Microsoft YaHei(标题 20–22pt / 正文 11–13pt / 注释 10–12pt)
- Color tokens:背景 `#0b2e33` · 前景 `#e8eef0` · 强调 `#c9a227` · 正面 `#4e937a` · 警告 `#c9a227` · 负面 `#a04545` · 静音 `#9aa8b0`
- Diagram grammar:blocks = 实体 · arrows = 关系 · bars = 数量 · lists = 枚举
- Animation policy:N/A(静态 mockup;未来能力)

## 4. 七个研究问题

| # | 问题 | 通过标准 |
|---|---|---|
| A1 | AI 能否正确选择 VIZ 类型? | ≥12/15 正确 |
| A2 | AI 能否从 claim 提取正确结构? | ≥12/15 |
| A3 | AI 能否生成事实正确的内容? | ≥12/15 |
| A4 | AI 能否保持 source-grounded? | ≥14/15 |
| A5 | AI 能否避免装饰性 VIZ? | ≥13/15 零装饰 |
| A6 | AI 能否通过视觉 QA? | ≥10/15 EQS ≥ analyst − 0.5 |
| A7 | 生成结果是否稳定? | ≥2/3 重跑结构一致 |

## 5. Pass/Fail 标准(逐对象)

- **PASS**:AI VIZ 覆盖与 analyst mockup 相同的 atomic claim(s) + 无编造事实 + EQS-lite ≥ analyst − 0.5
- **FAIL**:编造数据 / 遗漏关键主张覆盖 / EQS < analyst − 1.0

## 6. 总体分类(预注册)

| 分类 | 条件 |
|---|---|
| **SUPPORTED** | A1–A7 全部通过 |
| **PARTIALLY_SUPPORTED** | A1–A3 + A5–A6 通过但 A4 或 A7 部分通过 |
| **NOT_SUPPORTED** | ≤8/15 对象通过 |
| **INCONCLUSIVE** | 生成失败 > 5 |

## 7. 安全约束

- 每个事实/数字必须溯源到 narration 或 research provenance
- 推测内容必须在图中标注为推测
- 禁止 generic tech decoration(透明电路/发光大脑/抽象网络)
- 禁止编造数值
- 禁止无源图表
- VIZ 永不计入 photographic correspondence

## 8. 成本

| 项 | 估算 |
|---|---|
| LLM 文本调用 | ~134(claim parse + content + code gen + stability) |
| Vision 调用 | ~30(QA 诊断) |
| matplotlib 执行 | 15(本地,免费) |
| 墙钟 | ~30–45 min |
| DeepSeek 依赖 | **是**(需充值) |

## 9. Rollback

删除 `output/prod02/stage_a/` 目录即完全回滚;零生产触碰。

## 10. 冻结边界

EXP-B seal `96969e60` · EXP-A seal · P-2 seal `036d564a` · render_163 baseline · Run 01/02 母片 · 14 冻结模块 · correspondence · Stage 18–21 · per-claim shadow:全部不变。

## 11. 内部一致性检查(7/7 PASS)

- [x] 15 候选与 EXP-B 逐拍匹配(同 beat 同 claim)
- [x] Control artifacts 存在(11 张唯一 mockup 覆盖 15 对象)
- [x] VIZ type taxonomy 覆盖全部 15 对象(8 种类型)
- [x] 优先级排序定义(claim fidelity > info gain > honesty > readability > consistency > polish)
- [x] 风格系统定义(typography / color / diagram grammar / chart grammar / animation)
- [x] Pass/Fail 标准定义(逐对象 + 总体)
- [x] 安全约束定义(6 项)

## 12. 前置条件

DeepSeek 账户充值(生成需 LLM 文本 + vision 调用)。

---

```
VIZ GENERATION EXPERIMENT = READY
STOP——等待 DeepSeek 充值 + 实验执行授权
```
