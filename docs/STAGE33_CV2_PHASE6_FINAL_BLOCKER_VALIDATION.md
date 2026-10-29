# STAGE 33 / CV-2 材料供给能力验证 — Phase 6 最终 Blocker 验证报告

> 状态：**Phase 6 完成：最终 Blocker 解析。主线结论已定。STOP，等待人工裁决。**
>
> 本阶段目标：对 Phase 5C 遗留的两个 INCONCLUSIVE（`api_reliability`、`c1_behavior`）做最终验证，
> 完成 `PHASE6_FINAL_BLOCKER_MATRIX` 与五个状态（VISION_CHANNEL / RANKING_CHANNEL /
> DIRECTOR_REQUIREMENT_CONTRACT / API_RELIABILITY / PRODUCTION_INTEGRATION）。
>
> 全程**离线、只读**。未修改 Gold Standard、未修改 3.1.4/V3 计划、未修改任何阈值或权重、
> 未进入生产集成。所有实验均为独立观察，不混入既有质量基准。

---

## 0. 结论摘要（人工裁决用）

**PHASE6_FINAL_BLOCKER_MATRIX（冻结于 2026-09-01）：**

| ID | Blocker | Phase 5C 状态 | Phase 6 验证结果 | 最终状态 |
|---|---|---|---|---|
| B1 | API 可靠性 | INCONCLUSIVE（25% retry + 1% final fail） | **根因确认：max_tokens 预算被模型 hidden reasoning 耗尽**；修正协议参数后 8/8 成功 | **INCONCLUSIVE→可修复（协议参数问题,非 API 故障）** |
| B2 | C1(C1-C/C1-D)漏检 | INCONCLUSIVE（recall 33%,4/6 漏检） | **Director Requirements Contract 将 4/6 漏检全部纠正** | **RESOLVED（方向性验证）** |
| B3 | Director requirement 信号 | CANDIDATE | R1 实验证明 contract 字段显著改变判断（6 C1 全正确） | **VALIDATED（实验性）** |
| B4 | 回退安全性 | PASS（Phase 5B） | 未变 | **PASS** |
| B5 | 历史回归 | PASS（Phase 5B） | 3 个历史案例 2 个无回归,1 个（M-S12-607）暴露 contract 误杀风险 | **PASS（vision 侧）/ contract 设计风险（新发现）** |

**五个状态（最终调用）：**

| 状态 | 值 | 依据 |
|---|---|---|
| VISION_CHANNEL | **VALIDATED** | 75% Top-1 / MRR 0.842 / Top-5 0.938 复用率（Phase 5A frozen） |
| RANKING_CHANNEL | **VALIDATED** | V1 语义排序,实数池 399 验证（Phase 3/5A frozen） |
| DIRECTOR_REQUIREMENT_CONTRACT | **VALIDATED（实验性）** | Track B：6 C1 全纠正；C2 无误杀；S06 chart 被正确接受 |
| API_RELIABILITY | **INCONCLUSIVE（已定位根因,待修复后复测）** | max_tokens=128/512 导致 reasoning 耗尽；2048 下 8/8 成功 |
| PRODUCTION_INTEGRATION | **NOT_READY（维持）** | 见 §7 裁决逻辑 |

> **核心转变**：Phase 5C 时 API reliability 是"未知噪声"（25% retry 无法解释）；
> Phase 6 证明它是**协议参数配置错误**（模型引入 hidden reasoning,预算吃到 max_tokens）。
> 这不是"API 坏了",而是"调用方式需要适配"。但**修复后仍未做长期监控验证**（B1 的
> INCONCLUSIVE 性质从"不可解释"变为"可修复但未复验"）。

---

## 1. Track A — API 可靠性观察（独立 observation）

- 文件：`output/stage33/cv2/phase6_final/reliability/observation.json`
- 协议：复用 Phase 4C 已用 20 张缩略图（固定、无新标签）；每图 1 次请求 + MAX_RETRIES=3；TIMEOUT=180s；temperature=0.1。

**原始观察（max_tokens=128）：**

| 指标 | 值 |
|---|---|
| n | 20 |
| SUCCESS（首次） | 16/20 = 80% |
| SUCCESS（含重试后） | 19/20 = 95% |
| RETRY_EXHAUSTED | 1/20 = 5% |
| retry_rate | 20% |
| fallback_trigger_rate | 5% |

**根因定位（本阶段新增诊断）：**

1. `dump_raw.py` 捕获原始响应：`finish_reason=length`、`completion_tokens=512`、
   `completion_tokens_details.reasoning_tokens=512` —— **512/512 全部为 hidden reasoning,content 为空**。
2. `probe_prompt.py` 对照：同一 prompt,max_tokens 512 → 0/2；1024 → 1/5；2048 → 5/5 成功且 `finish=stop`。
3. T-13（唯一 RETRY_EXHAUSTED）复测：128 → 1/3；**2048 → 3/3 成功**（reasoning 197-300 tokens）。

**结论**：`deepseek-v4-flash-vision-exp` 已引入 **hidden reasoning**（服务侧行为变化,P4C 时代
`usage` 无 reasoning_tokens 字段,output_tokens 191-500 表明当时预算充足）。
原实验（Phase 5B 25.3% retry、Phase 6 Track A 20% retry）的 EMPTY_CONTENT 均因此产生。
**修正为 max_tokens=2048 后,观察到 8/8 成功。** 该修正属于协议参数适配,不改变 prompt/评判标准/阈值。

**为什么仍判 INCONCLUSIVE**：修正仅基于 8 次探针,无长期监控数据；生产级可靠性需要
持续监控（错误率、延迟、重试分布）才能证明。**可修复 ≠ 已验证**。

---

## 2. Track B — Director Requirements Contract 实验（R0 vs R1)

- 文件：`output/stage33/cv2/phase6_final/director_contract/`（`run_contract.py`、`contract_r1.json`、`contract_analysis.json`）
- 设计：R0 = Phase 4C vision（image+narration+focus）；R1 = R0 + 结构化 material requirement
  （镜头目的/需求的视觉模式/可接受/不可接受/口播/焦点）。**prompt 中不含人工标签、C1-C4、期望、排名、ground truth。**
- 样本：6 C1（NOT_USABLE+HIGH）+ 2 C2（USABLE+HIGH,对照证明不误杀）+ 3 historical + S06 chart = 12。
- 执行：12/12 成功,每样本 ≤8 次重试（max_tokens=2048）。

**结果（R0 vs R1）：**

| 样本 | 类别 | R0 | R1 | 判定 |
|---|---|---|---|---|
| Potential impacts of ocean acidification.png (S07) | C1 | NOT_USABLE | NOT_USABLE | 正确保持 |
| Ocean acidification and mean seawater pH.png (S07) | C1 | CONDITIONALLY | **NOT_USABLE** | ✅ 纠正 |
| Consequences of eutrophication...png (S08) | C1 | NOT_USABLE | NOT_USABLE | 正确保持 |
| World Ocean Current Chart - Feb (S15) | C1 | CONDITIONALLY | **NOT_USABLE** | ✅ 纠正 |
| World Ocean Current Chart - Aug (S15) | C1 | CONDITIONALLY | **NOT_USABLE** | ✅ 纠正 |
| South Atlantic Ocean currents 1943 (S15) | C1 | CONDITIONALLY | **NOT_USABLE** | ✅ 纠正 |
| M-S09-456 (S09) | C2 | CONDITIONALLY | **USABLE** | ✅ 提升,无误杀（注：fit=6.5 越界,见 §风险） |
| Staghorn coral closeup.jpg (S02) | C2 | USABLE | USABLE | ✅ 保持 |
| M-S03-162 (S03) | historical | NOT_USABLE | NOT_USABLE | ✅ 无回归 |
| M-S12-607 (S12) | historical | CONDITIONALLY | **NOT_USABLE** | ⚠️ **新误杀**（人类=USABLE/MEDIUM,油画） |
| M-S19-954 (S19) | historical | NOT_USABLE | NOT_USABLE | ✅ 无回归 |
| Temperature Bar Chart (S06) | 硬约束 | CONDITIONALLY | **USABLE** | ✅ chart 未被误杀,无 TYPE_BIAS_FAILURE |

**指标：**

| 指标 | R0 | R1 |
|---|---|---|
| C1 漏检率（NOT_USABLE+HIGH 被漏） | 4/6 = 66.7% | **0/6 = 0%** |
| C2 误杀率 | 0/2 | 0/2 |
| S06 chart 误杀 | 无 | 无 |
| 历史回归（vision 侧） | 0/3 | 0/3（M-S12-607 为 contract 侧问题,见下） |

**解读：**

- Contract 的作用机制：R0 的 RUBRIC_PROMPT 让模型"结合镜头判断",但 4 个漏检（T-29/T-57/T-58/T-59）
  都是"看出类型（chart/map）但认为可作为数据表达"——R0 缺一个**显式的类型排除信号**。
  R1 的"不可接受: charts, documents, static maps"给了模型明确的分类依据,因此 4/6 被纠正。
- 这直接支持 Phase 5C 的假设：**DIRECTOR_REQUIREMENT_SIGNAL = CANDIDATE → VALIDATED（实验性）**。
  "漏检源于 shot requirement 表达不足"得到实验证实：补上 requirement,漏检消失。
- **M-S12-607 风险**：油画被判 NOT_USABLE,因 contract 的 `acceptable=["live-action imagery","lifelike shoreline imagery"]`
  排除了艺术作品,而人类标签 USABLE/MEDIUM（油画可作叙事衬底）。
  **这是 contract 内容设计风险（枚举露暴）,不是模型能力缺陷**——R0 反而正确识别为 CONDITIONALLY_USABLE。
  **含义：上生产前,contract 条款须经人工审查（尤其 S12 类"艺术形式作为叙事衬底"场景）;不能直接自动化生成 contract。**
- **数值越界**：M-S09-456 的 `visual_fit_score=6.5`（应 0-1）。说明 contract prompt 下模型偶尔越界,
  但方向（不误杀）仍有效。需在 production 解析中加 schema 校验。

---

## 3. C1 行为分析（Track B 前后对比）

Phase 5C 盲检基线（6 个 C1,T-28/T-29/T-31/T-57/T-58/T-59）：

| C1 | 类型 | R0 输出 | C1 分类 |
|---|---|---|---|
| T-28 (Potential impacts, S07) | diagram | NOT_USABLE | C1-A（正确） |
| T-29 (pH chart, S07) | chart | CONDITIONALLY | **C1-C**（信息价值误判） |
| T-31 (ecosystem diagram, S08) | diagram | NOT_USABLE | C1-A（正确） |
| T-57 (current chart Feb, S15) | map | CONDITIONALLY | **C1-C** |
| T-58 (current chart Aug, S15) | map | CONDITIONALLY | **C1-D**（reason 已说"无法呈现动态",仍 CONDITIONALLY） |
| T-59 (current 1943, S15) | map | CONDITIONALLY | **C1-D**（reason 已说"缺乏真实可拍摄感",仍 CONDITIONALLY） |

Phase 6 Track B（同 6 个 C1,R1）：

| C1 | R1 输出 | 说明 |
|---|---|---|
| T-28 | NOT_USABLE | 保持正确 |
| T-29 | NOT_USABLE | 纠正 |
| T-31 | NOT_USABLE | 保持正确 |
| T-57 | NOT_USABLE | 纠正 |
| T-58 | NOT_USABLE | 纠正 |
| T-59 | NOT_USABLE | 纠正 |

**C1 recall（NOT_USABLE+HIGH）：R0 33% → R1 100%（6/6）。**

**判断**：C1-C/C1-D 不是"模型不能认识类型",而是"模型在缺少显式类型排除时倾向于
保留数据类素材为可用"（语义相关 → 放宽为 CONDITIONALLY）。**contract 给出显式排除规则后,
模型能力足以完成 C1 判别。** 因此：

- 该问题的性质从"模型能力无法修复的限制" → **"可用显式 requirement 约束修复的 prompt 工程问题"**。
- 但 contract 由谁制定、如何审查（避免 M-S12-607 类误杀）是**前置工程问题**——Phase 6 只证明
  **方向可行**,不证明"任意自动生成的 contract 都安全"。

---

## 4. 历史回归审查（Track B 附带验证）

| 案例 | R0 | R1 | 判定 |
|---|---|---|---|
| S03 M-S03-162（黑白剧照） | NOT_USABLE/fit 0.0 | NOT_USABLE | 无回归（vision 识别剧照→不可用） |
| S12 M-S12-607（油画） | CONDITIONALLY/fit 0.65 | **NOT_USABLE** | ⚠️ **R0 不误杀,但 R1 因 contract 误杀** |
| S19 M-S19-954（孩童海滩照） | NOT_USABLE/fit 0.3 | NOT_USABLE | 无回归 |
| S06 chart | CONDITIONALLY/fit 0.8 | USABLE | ✅ chart 被正确接受,无 TYPE_BIAS_FAILURE |

**结论**：vision 通道无历史回归（S03/S06/S19 均保持正确方向）。M-S12-607 的变化
**完全由 contract 内容导致**——这本身是新发现：**contract 内嵌的"可接受/不可接受"枚举
可能引入比模型自身判断更严格的边界**。这一风险必须作为 contract 设计前置条件记录。

---

## 5. 工程可靠性缺口（如实列出,不掩盖）

1. **长期监控缺失**：修正 max_tokens 后仅 8 次探针成功；无生产级持续监控（错误率分布、
   延迟 p95、重试分布）上报机制。**（上次要求的上线前监控指标仍未实现）**
2. **contract 生成与审查机制缺失**：contract 由谁提供？由人工根据 shot requirement 编写？
   还是自动派生（本项目 S01-S20 为人工填写）？**自动派生会引入 M-S12-607 类误杀风险。**
3. **解析 schema 校验缺失**：`visual_fit_score=6.5` 越界说明需 production 归一化/校验层。
4. **prompt 泄漏审计**：Track B 的 contract prompt 已 audit（`leaked_label_fields=0`,
   仅 image+narration+focus_hint+neutral requirement,无 human label/C1-C4/expected/rank）。

---

## 6. 审计与可复现性

| 项 | 状态 |
|---|---|
| Gold Standard（SHA `C70C82D46...448AC`） | 未修改 |
| Phase 3/5A 基准（V1 56.2% / Vision 75.0% / Fused 75.0%） | 未重跑,冻结引用 |
| Phase 5C gate（10 PASS + 2 INCONCLUSIVE） | 引用 |
| Track A 观察 | 独立于 benchmark,不混入 |
| Track B contract | 独立实验,prompt 无泄漏,参数冻结,全字段记录 |
| 所有脚本 | `run_contract.py`/`observe_api.py`/`probe_prompt.py`/`dump_raw.py` 均在 output 目录,可复现 |
| 诊断日志 | `raw_dump.json`、`probe_result.json`（原始响应+探针数据） |

---

## 7. 最终裁决逻辑与五个状态

**已知能力（已验证）**：V1 语义排序（real pool 399,75% Top-1 可复用）→ Top-5 gating →
Vision 评估（DeepSeek Vision,MRR 0.842）→ 失败回退 V1（候选不消失,最差=V1）。

**已验证安全性质**：per-candidate 隔离、异常不影响其他候选、回退确定性、Top-K 合法、
无历史回归（vision 侧）、prompt 无泄漏。

**模型能力边界（已确认）**：
- 旧发现：R0 prompt 下 C1-C/C1-D 漏检 33% recall（类型识别但倾向保留）。
- 新发现：contract 显式排除后 C1 recall 100%,但 **S12 类"艺术形式作叙事衬底"场景
  会被 contract 枚举误杀**——该边界从"模型限制"转移为"contract 设计限制"。

**工程可靠性缺口**：无长期监控（B1 修复后仍未复验）；无 contract 审查/生成机制；
无 schema 校验层。

**尚未验证的假设**：
- contract 完全自动派生是否安全（未测）。
- 修正 max_tokens 后的长期可靠性（未采集）。
- V1 Top-1 在 contract 场景下排序稳定性（未测,但 Phase 5B R5 已验证 N=5 内 Top-5 稳定）。

**最终：**

- `API_RELIABILITY = INCONCLUSIVE`：根因已定位（max_tokens 预算,非 API 故障）,修复后 8/8 成功;
  但**无长期监控数据,不可证明生产级**。
- `DIRECTOR_REQUIREMENT_CONTRACT = VALIDATED（实验性）`：方向验证,C1 漏检 4/6→0/6;
  但 contract 审查机制缺失 → 不作为生产集成放行条件。
- `PRODUCTION_INTEGRATION = NOT_READY`：按裁决规则（API_RELIABILITY INCONCLUSIVE → NOT_READY）。

**为什么不是 READY_WITH_EXPLICIT_LIMITATIONS**：该状态要求"API 可靠性已验证"（PASS 或
"误差可控且已监控"）。当前明确**未采集长期监控**,无法给出"可靠性已验证"声明。
不因 Track B 的 C1 改善而放行——那只是实验方向性证据,不是生产准入。

---

## 8. 下一步（等待人工裁决）

**STOP**。等待人工对以下问题作出裁决：

1. **API_RELIABILITY 是否接受"根因=协议参数,修复=2048"的判定,并授权进入
   长期监控采集（新 Phase 6b）?** 该采集属于在线实验,需人工授权。
2. **DIRECTOR_REQUIREMENT_CONTRACT 方向是否接受（VALIDATED 实验性）?**
   若接受,下一步的 contract 生成/审查机制（避免 M-S12-607 类误杀）需人工指定
   （如"contract 由导演模块人工编写,评审通过后才允许进入 pipeline"）。
3. **Phase 5C 的 INCONCLUSIVE(api_reliability) 是否可在 Phase 6 证据下关闭?**
   若人工认为"根因明确+修复已验证"足以关闭 → API_RELIABILITY=PASS（实验性）;
   若要求长期数据 → 保持 INCONCLUSIVE。
4. **生产集成**：在以上裁决前,不做任何生产集成,不初始化 Phase 7,不继续 benchmark。

> 本报告为最终 Blocker 验证文档。所有实验离线、只读、可复现、无泄漏、无阈值调参。
