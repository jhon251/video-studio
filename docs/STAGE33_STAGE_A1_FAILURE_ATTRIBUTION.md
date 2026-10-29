# Stage 33 — Stage A-1: Failure Attribution & Recovery Experiment Registration

> **性质**:只读设计 + 注册。零执行、零生产修改。Stage A 原始结果永久密封(NOT_SUPPORTED,不覆盖)。
> 机器可读:`output/prod02/stage_a1_registration.json`

---

## 1. Stage A 失败精确归因(来自原始数据)

| 轴 | 失败 | 根因 | 影响 |
|---|---|---|---|
| **Axis 1** Generator | **5 拍** | `deepseek-v4-flash` reasoning 模型消耗 max_tokens 在 reasoning_content(19k–29k 字符),content 为空 → JSON 提取失败 | S13-B01 · S01-B03 · S02-B04 · S02-B01 · S33B-B01 |
| **Axis 2** Evaluator | **15/15** | A1 type_match 将 AI canonical 类型名(checklist/comparison)与 EXP-B 自由文本(3-pillar diagram/ten constraints checklist)直接字符串比较 → 0/15 | **全部 15 拍的 A1 判定无效** |
| **Axis 3** Renderer | **1 拍** | quantitative_chart 分支引用未定义变量 ACC → NameError | S20-B01 |

**失败计数:7 个工程/评价问题,分布在 15 个对象上(部分对象有多个问题)。**

### 逐拍归因

| Beat | Axis | 根因 | 可修复 |
|---|---|---|---|
| S13-B01 | 1 | reasoning 19100 字符 → JSON 提取失败 | ✅ 工程 |
| S01-B03 | 1 | reasoning 空 content | ✅ 工程 |
| S02-B04 | 1 | reasoning 空 content | ✅ 工程 |
| S02-B01 | 1 | reasoning 14142 字符 → JSON 提取失败 | ✅ 工程 |
| S33B-B01 | 1 | reasoning 28848 字符 → JSON 提取失败 | ✅ 工程 |
| S20-B01 | 3 | ACC undefined → NameError | ✅ 工程 |
| 全部 15 | 2 | type mapping 自由文本 vs canonical 不匹配 | ✅ 工程 |

## 2. 三轴修复规格

### Axis 1 — Generator Robustness

- **问题**:`v4-flash` 推理模型将 max_tokens 消耗在 reasoning_content,content 为空
- **修复**:max_tokens 增至 16384 + JSON 从 reasoning_content 提取(含多块/部分解析) + structured output(如可用)
- **验证**:重跑 5 个失败拍,≥4/5 产生有效结构
- **记录**:max_tokens / reasoning_content 长度 / content 长度 / JSON 提取方法 / 重试次数

### Axis 2 — Evaluator Mapping

- **问题**:自由文本 vs canonical 类型名直接字符串比较
- **修复**:建立 canonical type → accepted aliases → rejection rules 映射表;离线回归 15/15
- **映射表**:
  - `hierarchy_ladder`: ladder / ladder roadmap / ladder teaser / five-level ladder / L5 empty / ladder recap / hierarchy
  - `constraint_web`: constraint web / constraint diagram / 3-pillar / constraint graph
  - `comparison`: comparison / split-panel / side-by-side / versus
  - `checklist`: checklist / list diagram / ten constraints / enumeration
  - `quantitative_chart`: quantitative chart / bandwidth log chart / log chart
  - `process_flow`: process flow / flow diagram / sequence
  - `timeline`: timeline / temporal
  - `split_panel`: split panel / two halves / dual panel
- **验证**:15/15 离线 mapping regression(≥12 正确映射)
- **不改 Stage A 原分**:只证明 evaluator bug 存在

### Axis 3 — Renderer Robustness

- **问题**:quantitative_chart 分支 ACC 未定义
- **修复**:定义 ACC 常量 + 8 种 VIZ 类型各 1 个 smoke test
- **验证**:零 runtime exception · 零 missing variable · 零 malformed artifact · 原子写入

## 3. Recovery Experiment(独立新实验,非 Stage A rerun)

- **Control**:EXP-B 分析师 mockup(封存不变)
- **Treatment**:修复后的 AI VIZ generator(三轴修复全部应用)
- **对象**:Stage A 相同 15 拍
- **新参数记录**:max_tokens / reasoning 处理 / evaluator 版本 / renderer 版本

### 判定标准(预注册)

| 分类 | 条件 |
|---|---|
| **ENGINEERING_RECOVERABLE** | ≥13/15 生成+渲染成功 AND ≥12/15 A1 mapping 正确 |
| **CAPABILITY_RECOVERABLE** | ≥10/15 生成+渲染 AND ≥8/15 EQS |
| **CAPABILITY_FAILURE** | ≤9/15 生成 或 ≤7/15 EQS |
| **INCONCLUSIVE** | 执行失败阻碍有效评估 |

### 5 个 GEN_FAIL 专项

> "如果只解决 reasoning/JSON extraction,这 5 个能否正常生成?"

重跑 Axis 1 修复版,测量结构生成成功率。≥4/5 = 工程问题确认;≤2/5 = 能力限制确认。

### S20-B01 专项

确认 ACC undefined 为 renderer bug → 修复 → 独立验证 generation/rendering/factual content/source grounding/visual QA。

### Evaluator Bug 验证

原 A1 = 0/15 **不修改**。新增 `A1_mapping_correctness`:使用 canonical mapping 重新评估 15 个对象,验证实际正确映射数。

## 4. 冻结边界

Stage A 原始结果 = NOT_SUPPORTED(**密封,不覆盖**)· EXP-B seal `96969e60` · EXP-A seal · P-2 seal `036d564a` · render_163 · Run 01/02 · 14 冻结件 · correspondence 50.5% · Stage 18–21 · per-claim shadow:全部不变。

## 5. Production

无论 A-1 结果如何:**Production VIZ Rollout = NOT AUTHORIZED**。

---

```
STAGE A ORIGINAL = SEALED / NOT_SUPPORTED
STAGE A-1 = READY(设计+注册完成,三轴修复规格定义)
STOP——等待执行授权
```
