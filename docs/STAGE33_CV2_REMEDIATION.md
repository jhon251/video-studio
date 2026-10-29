# Stage 3.3 CV-2 Remediation：Valid Measurement（有效测量协议重建）

> 状态：实验层工作（隔离）。**零生产代码、零 pipeline/baseline 修改、零 Coral 重渲染、零 V3 plan 修改、零模型堆叠、零阈值放宽。** Gold Standard 必须是人工冻结标签，AI 不自行生成最终标签。完成后 STOP 等待裁决。

---

## 一、为什么需要 Remediation（前情结论）

上一轮 CV-2 benchmark（`STAGE33_CV2_BENCHMARK_REPORT.md`）终判 **INCONCLUSIVE**，根因是测量协议失灵：

- `semantic_hit` 用中文词表匹配英文元数据 → 33/33 白名单候选、10/10 人工强正例全部被判 `usable=False`；
- 同一批候选 `retention=1.0` 却 `usable=0.0`，协议自相矛盾；
- 因此 Top-K usability 指标不可信，A/B/C 无法裁决。

本轮目标不是"翻译词表继续用原协议"，而是**从根上拆开两个被上一轮混为一谈的维度**，并建立**人工冻结 Gold Standard** 作为唯一评价依据。

---

## 二、测量协议拆分（核心原则）

### 2.1 两个独立维度

| 维度 | 定义 | 谁裁决 |
|---|---|---|
| **Retrieval Relevance**（检索相关性） | 素材是否与 narration / material requirement **语义相关**（"这条素材在讲这个主题吗"） | 自动检索/语义匹配可以**辅助**，但最终相关与否仍以人工标签为准 |
| **Visual Usability**（视觉可用性） | 即使语义相关，素材是否**真的适合作为该镜头的视觉证据**（"这条素材能直接拍进这句话吗"） | **只能由人工冻结标签裁决**；semantic_hit、CLIP 分数、任何自动规则都不得反推 |

**铁律**：`语义高度相关 ≠ 视觉适合`。上一轮三个历史失败案例全部命中这一铁律（见 §五）。

### 2.2 禁止的推断

- 不得用 `semantic_hit`（中文/英文词表子串匹配）判定 Visual Usability；
- 不得用 CLIP/embedding 分数判定 Visual Usability；
- 不得用 `is_painting/is_film/has_person` 关键词命中判定 Visual Usability；
- 自动规则只能产出**排序候选**（ranking），不能产出**标签**（label）。

---

## 三、人工 Gold Standard（冻结标签集）

### 3.1 规模要求（预固定）

| 类别 | 最小数量 | 含义 |
|---|---|---|
| strong positive（强正例） | ≥ 20 | 语义相关 **且** 视觉可用（可直接作为该镜视觉证据） |
| strong negative（强负例） | ≥ 20 | 语义相关 **但** 视觉不可用（或语义不相关且视觉不可用） |
| hard negative（硬负例） | ≥ 10 | **语义高度相关但视觉不可用**——专门回归"语义相关 ≠ 视觉适合" |

> 历史失败案例（S03×M-S03-162、S12×油画渔民、S19×沙滩孩子）必须固定纳入，且属于 hard negative（§五）。

### 3.2 每个素材必标字段（≥10 项）

| 字段 | 类型 | 说明 |
|---|---|---|
| `semantic_relevance` | enum: relevant / partially / irrelevant | 与 narration + material requirement 的语义相关性 |
| `visual_usability` | enum: usable / usable_with_edit / not_usable | **Gold Standard 主字段**，只能人工标 |
| `visual_type` | enum: photo / video / chart / diagram / painting / film_still / illustration / map / other | 视觉类型 |
| `subject` | string | 主体对象（珊瑚/鱼群/温度图/渔民/孩子/城市…） |
| `scene` | string | 场景（水下/海面/岸边/实验室/城市…） |
| `people_presence` | enum: none / few / many / subject | 人物存在性 |
| `documentary_suitability` | enum: yes / no / conditional | 是否适合纪实风格（油画/剧照→no） |
| `text_overlay_suitability` | enum: yes / no | 是否允许画面叠字 |
| `fits_shot` | bool | 是否适合当前 shot（= visual_usability==usable 的人工复核，可独立于主字段记录） |
| `rights_status` | enum: SAFE / CONDITIONAL / UNSAFE / UNKNOWN | 权利状态（由元数据核验得出，见 §四） |

附加（供可解释性，不参与主指标）：`label_role`（strong_pos / strong_neg / hard_neg / unlabeled）、`note`（标注理由，自由文本）。

### 3.3 冻结纪律

- 标签集写成 JSON 后，**SHA256 记录**，此后不得修改；
- 若发现标注错误需修正，必须**新增修订版本 + 记录 diff 理由**，不得静默改；
- 不得为了让 A/B/C 结果达标而事后改动标签——这是作弊，直接作废本轮实验。

---

## 四、第二优先级：异常数据人工核验

三类异常必须逐项核验，且**四分类归因**：

| 异常 | 对象 | 四分类 |
|---|---|---|
| rights failures | 上一轮 2 个未过权利门候选 | 真实版权失败 / 判定器缺元数据 / 判定器漏配合法许可 / 下载失败 |
| whitelist candidates | 33 个 | 逐个核对真实可用性与权利（避免上一轮"协议失灵"重演） |
| SUPPLY_FAILURE | M-S03-162 | 下载失败 ≠ 素材不存在（§四已初步归因） |

**禁止把"下载失败"记成"素材不存在"。**

### 4.1 已完成的机械核验结果（AI 可证实的部分）

**① 2 个 rights failures（已定位 + 归因，见 `rights_triage.json`）**

| 候选 | LicenseShortName | 归因 | 结论 |
|---|---|---|---|
| `File:High seawater temperatures in Florida are causing coral bleaching.jpg`（S05, Copernicus Sentinel-2） | `Attribution` | **HEURISTIC_FALSE_NEGATIVE** | 非真实版权失败；`Attribution` 是 Commons 对 CC BY 的短名，上一轮 `_license_ok` 接受串列表漏配该短名 |
| `File:Three new levels of coral bleaching alert (Copernicus 2024-02-12).jpg`（S05, Copernicus Sentinel-2） | `Attribution` | **HEURISTIC_FALSE_NEGATIVE** | 同上 |

分布：`REAL_RESTRICTION=0 / METADATA_MISSING=0 / HEURISTIC_FALSE_NEGATIVE=2`。**即：上一轮"rights_failures=2"并非真实权利失败，是判定器漏配合法许可短名。** 这两个候选的真实许可为 CC BY（Attribution），可商用（须署名）。修正后的权利门漏网数应为 **0**。

**② M-S03-162 下载状态（见 `m_s03_162_probe.json` + `m_s03_162_endpoint_compare.json`）**

- 原始 URL：HTTP **200**，241099 bytes，SHA head `4b0f7b6d1926c5d2`；
- `thumbnail_unscaled` 端点：HTTP **200**，同 SHA。
- 归因：**之前的连续 429 是间歇性源站限流（upload.wikimedia.org），不是素材不存在、也不是端点永久故障。** 素材本体可获取，license=Public domain、SAFE、可商用。它作为 hard-negative 的"供给失败"障碍本轮已消除，可以入池进入人工标签。

**③ 33 个 whitelist candidates（见 `gold_standard_seed.json`）**

- 权利：33/33 license 均合法（CC0 / Public domain / CC BY / CC BY-SA），无 UNSAFE；
- 视觉可用性：**不在此处由 AI 判定**，留待人工标签（这正是本阶段的纪律）；
- 历史提示已内嵌：3 个 hard-neg + 10 个 strong-pos（仅作提示，不冒充冻结标签）。

**④ 附带发现（检索供给形态）**：S03/S18 的 Commons 召回几乎全是古书 PDF 扫描件（`application/pdf`，宽高为页尺寸），非照片/视频。这是检索相关性/供给形态问题，与视觉可用性分开记录——进一步印证协议拆分必要性。

---

## 五、历史 Hard-Negative 回归集（固定，永不从实验剔除）

| 案例 | 语义相关性 | 视觉适合性 | 失效本质 |
|---|---|---|---|
| S03 × M-S03-162（1957 电影剧照） | 高（"深处"→深海/下潜语义相关） | **否**（黑白剧照，非纪实深海画面） | film_still 类型错配 |
| S12 × 油画渔民（RMG 藏画） | 高（渔夫拉网，字面完全相关） | **否**（油画，非纪实） | painting 类型错配 |
| S19 × 沙滩孩子照片 | 高（字面"沙滩孩子"） | **否**（情绪/意境不贴合该句） | 意境错配（无自动字段可判） |

这组案例证明了三类不同的"语义相关但视觉不适合"，是以后任何供给/检索实验的**固定回归锚点**。任何新实验若不能正确下沉这三个案例，直接判实验无效。

---

## 六、A/B/C 重新定义（统一 Gold Standard）

| 组 | 条件 |
|---|---|
| A | 现有池 + semantic retrieval |
| B | 扩充池 + semantic retrieval |
| C | 扩充池 + semantic retrieval + 确定性视觉属性过滤 |

三组最终评价**统一使用同一份人工冻结 Gold Standard**。

### 6.1 必报指标（12 项）

1. Top-1 Visual Usability
2. Top-3 Visual Usability
3. Top-5 Visual Usability
4. 强正例保留率（strong-positive retention）
5. 强负例下沉率（strong-negative sink）
6. hard-negative 下沉率（hard-negative sink）
7. retrieval coverage（检索覆盖：有候选的镜头数/20）
8. 可用素材覆盖率（20 镜中至少 1 个 usable 候选的镜头比例）
9. rights failure（权利门漏网，应为 0）
10. false negative（被排低/过滤掉的强正例）
11. false positive（被排进 Top-K 的强负例）
12. （附）Top-K 内 usable_with_edit 占比（辅助，不参与主判据）

### 6.2 核心问题（必须分别回答，不得混为一谈）

- **A→B**："扩大素材池是否增加了**真正可用的视觉证据**？"（不是"候选是否更多"）
- **B→C**："视觉属性过滤是否进一步减少**语义相关但视觉不适合**的素材？"（不是"是否换了排序"）

**特别禁止**：用"候选更多/20 镜全有候选/CLIP 分数上升/排名变化"冒充"素材更好"。唯一有效信号是**人工 Gold Standard 上的 usability 变化**。

---

## 七、决策纪律（终判树）

| 结果 | 输出 |
|---|---|
| B 达标 | `SUPPLY_IS_PRIMARY_BOTTLENECK` |
| B 不达标、C 达标 | `SUPPLY_PLUS_VISUAL_UNDERSTANDING` |
| B/C 均不达标 | 再讨论 `VISUAL_GENERATION_REQUIRED` / `DIRECTOR_LAYER_STILL_PRIMARY` |
| 证据不足 | `INCONCLUSIVE` |

**严禁**：调低阈值、修改 Gold Standard、添加更多模型、堆叠规则、修改 V3 Director、修改 Executor、重跑 V3 成片、修改任何 sealed/baseline 资产。

---

## 八、产物清单（隔离，output/stage33/cv2_remediation/ + docs/）

| 产物 | SHA256（前 16） | 说明 |
|---|---|---|
| `collect_pool.py` | B74D6B776AB34598 | 重采集+持久化候选池 |
| `pool_persisted.json` | 10533D48C84432BE | 366 候选完整元数据 |
| `rights_triage.json` | EB6E53C215F115DC | 2 个 rights failures 归因 |
| `probe_m_s03_162.py` / `probe_m_s03_162_endpoints.py` | 356A9DBD / 1E059BD5 | M-S03-162 下载诊断 |
| `m_s03_162_probe.json` | E983C9D11F765421 | 200 OK，SHA 4b0f7b6d |
| `m_s03_162_endpoint_compare.json` | 7EA4B798DBDF23D8 | 两端点均 200 |
| `gold_standard_schema.json` | B5E78768F65BBF96 | 标签集 Schema（10 字段） |
| `build_seed.py` | 8E826A056889A56D | 种子生成（AI 只填元数据） |
| `gold_standard_seed.json` | 22EE92E95B7F472A | 399 候选种子，判断字段待人工 |
| `run_abc.py` | 753B099E2C870DA2 | A/B/C 评价 harness（12 指标） |
| `smoke_test.py` | 19514C33EAA5799E | harness 机械性冒烟测试（非真实结果） |
| 本文档 | 6C5381A11AB30BC4 | 协议与设计 |

- `pool_persisted.json` / `rights_triage.json` / `m_s03_162_*.json`：机械可复现证据；
- `gold_standard_seed.json`：交给人工标注的**候选清单 + 待填字段**，AI 未生成任何 visual_usability / semantic_relevance / label_role 判断；
- `run_abc.py`：**消费冻结 Gold Standard 后**才能产出有效结果；未冻结（`meta.frozen!=true`）直接拒绝运行。

**停止线**：Gold Standard 冻结 → rights 核验 → A/B/C 重跑 → hard-negative 回归 → 报告 → **STOP 等待人工裁决**。不进入生产素材供给实现。

---

## 九、模型纪律

本阶段为测量协议重建与实验归因任务，优先严谨性。架构决策用推荐模型（DeepSeek V4 Pro + Max），不因省 token 换 Flash。
