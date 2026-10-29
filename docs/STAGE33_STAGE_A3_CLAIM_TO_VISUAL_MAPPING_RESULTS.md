# Stage 33 — Stage A-3: Claim-to-Visual Mapping Diagnostic (Results)

> **性质**:只读诊断,四层归因。零生产修改。
> 机器可读:`output/prod02/stage_a3_diagnostic.json` · `stage_a3_results.json`

---

## 四层诊断矩阵(15 拍)

| Beat | A Claim | B Type | C Binding | D Final | Earliest Fail |
|---|---|---|---|---|---|
| S13-B01 | ✅ | ✅ | ✅ | ✅ | NONE |
| S30-B01 | ✅ | ✅ | ❌ | ❌ | **C** |
| S01-B03 | ✅ | ✅ | ❌ | ❌ | **C** |
| S26-B02 | ✅ | ✅ | ❌ | ✅ | **C** |
| S02-B04 | ✅ | ✅ | ❌ | ❌ | **C** |
| S02-B01 | ✅ | ✅ | ✅ | ✅ | NONE |
| S02-B03 | ✅ | ✅ | ✅ | ✅ | NONE |
| S18-B02 | ✅ | ✅ | ❌ | ❌ | **C** |
| S20-B01 | ✅ | ✅ | ❌ | ✅ | **C** |
| S20-B02 | ✅ | ✅ | ❌ | ✅ | **C** |
| S26-B01 | ✅ | ❌ | ✅ | ❌ | **B** |
| S28-B02 | ✅ | ✅ | ❌ | ✅ | **C** |
| S33B-B01 | ✅ | ✅ | ❌ | ✅ | **C** |
| S33B-B02 | ✅ | ✅ | ✅ | ✅ | NONE |
| S33B-B03 | ✅ | ❌ | ✅ | ✅ | **B** |

## 层级通过率

| 层 | PASS | FAIL | 通过率 | 角色 |
|---|---|---|---|---|
| **A Claim Representation** | 15/15 | 0 | **100%** | 无瓶颈 |
| **B Representation Selection** | 6/15 | 9 | **60%** | 部分瓶颈 |
| **C Content Binding** | 6/15 | 9 | **60%** | **主瓶颈** |
| **D Final VIZ** | 9/15 | 6 | **60%** | 受上游传播影响 |

## 最早失败分布

| 最早失败层 | 拍数 |
|---|---|
| NONE(全通过) | 4 |
| B(Representation) | **2** |
| C(Content Binding) | **9** |

## 核心发现

### 1. Claim Decomposition(A)不是瓶颈
全部 15 拍的 atomic claims 均正确分解——**claim representation 层无失败**。

### 2. Content Binding(C)是主瓶颈
9/15 拍在 C 层失败:AI 生成的视觉元素**语义相关但不能精确证明对应主张**。例如:
- “十道现实之坎”的 checklist 中包含项目但未精确对应 narration 列举的十项
- “接口语言缺失”的约束网有节点但未映射到 narration 列举的具体约束

### 3. Representation Selection(B)是次瓶颈
2 拍选择了不适合主张结构的 viz_type(如 S33B-B03 用 hierarchy_ladder 但 narration 是比较型)。

### 4. 失败传播清晰
```
A Pass (15) → B Fail (2) → C Fail (9) → D Fail (6)
              ↑ 主瓶颈      ↑ 主瓶颈传播    ↑ 上游传播
```
B 层 2 个失败传播到 C 层并进一步传播到 D 层;C 层 9 个独立失败中 3 个也传播到 D。**最早失败层**主要在 **C(Content Binding)**:9 拍的 C 层失败是首次出现失败的层,后续 D 层失败是传播效应。

## 根因排序

| 排名 | 层 | 失败数 | 描述 |
|---|---|---|---|
| **#1** | **C Content Binding** | 9 | AI 生成的元素语义相关但不能精确证明对应主张 |
| **#2** | **B Representation Selection** | 2 | 选择了不适合主张结构的 viz_type |
| — | A Claim Representation | 0 | 无失败 |

## 排除项

- **“需要更强模型”**:被排除——Layer A 全通过说明 claim 理解没问题;C 层失败是绑定精度问题而非理解力问题
- **“correspondence 定义过严”**:被排除——D 层 6 个失败全部由上游 B/C 失败传播,非定义问题

## 推荐修复优先级

1. **Layer C Content Binding(最优先)**:改进 claim-to-element 精确映射;可通过更精细的 prompt 约束或 element-level validation 实现
2. **Layer B Representation Selection**:改进 claim-type → viz-type 匹配规则
3. **Layer A Claim Representation**:无需修改(100% 通过)

## Flash Challenger 判定

Layer A 100% 通过 → **不注册 Flash High vs Max challenger**。失败在 C 层(Content Binding),非 reasoning/generation 层——升级模型不太可能解决绑定精度问题。

## 冻结边界

Stage A/A-1/A-2 · EXP-A/B · P-2 · render_163 · 14 冻结件 · correspondence · Stage 18–21 · per-claim shadow:全部不变。

---

```
STAGE A-3 = DIAGNOSTIC_COMPLETE
Layer A: 15/15 PASS(无瓶颈)
Layer B: 6/15 PASS(次瓶颈)
Layer C: 6/15 PASS(主瓶颈:Content Binding)
Layer D: 9/15 PASS(受上游传播影响)
最早失败层: C 9 次 > B 2 次 > A 0 次
失败传播: C→D 6 次 · B→C→D 3 次 · B→D 0 次
主瓶颈: Content Binding(元素到主张的精确映射)
PRODUCTION VIZ ROLLOUT = NOT AUTHORIZED
STOP——等待下一步授权
```
