# Stage A-5: Generation Failure Recovery Results

> **性质**:生成侧恢复验证，零生产修改。预注册先于执行。
> 判定：**GENERATION RELIABILITY RECOVERED (2/2)**
> 机器可读:`output/prod02/stage_a5_results.json`

---

## 1. 实验结果

| Beat | 原始(A-4) | 恢复(A-5) | 判定 |
|---|---|---|---|
| **S02-B01** | 空元素列表 | **2 个元素** | ✅ RECOVERED |
| **S18-B02** | 空元素列表 | **5 个元素** | ✅ RECOVERED |

**判定:GENERATION RELIABILITY RECOVERED**

- 恢复方法：在 system prompt 中显式要求 `elements` 数组不得为空（不改 claims、不改模型、不改参数）
- 零编造事实 · 零装饰元素 · 零 LOW 采纳

---

## 2. 逐拍恢复详情

### S02-B01（"今天的头显支持裸手追踪你的十根手指"）

- 原始(A-4)：0 元素
- 恢复(A-5)：**2 个元素**，均映射到 claim、均有 supporting fact

### S18-B02（"第三层的早期形态,会先出现在医疗和康复室里"）

- 原始(A-4)：0 元素
- 恢复(A-5)：**5 个元素**，含康复/医疗/BCI 相关元素

---

## 3. 累计 RUN 02 证据覆盖

| 指标 | A-4 前 | A-4 后 | A-5 后 |
|---|---|---|---|
| C PASS | 6/15 (40%) | **13/15 (87%)** | **15/15 (100%)** |
| 装饰性元素 | 0 | 0 | **0** |
| B2/Tempi 物料 | 0 | 0 | **0** |
| Safety 违例 | 0 | 0 | **0** |

---

## 4. 全链路修复验证

| 层 | 修复 | 来源 | 状态 |
|---|---|---|---|
| R1 Query Completeness | 完整执行(301→301) | Stage 22.3 | ✅ 已进生产 |
| Axis 1 Generator reasoning budget | max_tokens 16384 | Stage A-1 | ✅ 已验证 |
| Axis 2 Evaluator type mapping | canonical mapping | Stage A-1 | ✅ 已验证 |
| Axis 3 Renderer ACC variable | ACC 定义 | Stage A-1 | ✅ 已验证 |
| A-4 Structured Binding | 空元素 safeguards | Stage A-4 | ✅ 15/15 |

## 5. 冻结边界

Run 01 / render_163 / 14 冻结件 / P-2 seal / Stage 18–21 / correspondence 50.5%：全部不变。

---

```
STAGE A-5 = GENERATION RELIABILITY RECOVERED (2/2)
RUN 02 全链路 Evidence Coverage = 15/15 (100%)
零编造 · 零装饰 · 零安全违例 · 零生产修改
STOP——等待下一步授权
```
