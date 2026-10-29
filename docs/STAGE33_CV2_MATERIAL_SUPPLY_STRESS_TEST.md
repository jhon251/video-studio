# Stage 3.3 CV-2：Material Supply Capability Validation / Architecture Stress Test

> 状态：架构设计 + benchmark 设计 + 供给可行性验证（隔离实验）+ 现有池分析。**零生产代码、零 pipeline/baseline 修改、零 Coral 重渲染、零 V3 plan 修改。** 完成后 STOP。
>
> **更新（benchmark 已运行）**：A/B/C 确认实验已完成，终判 **INCONCLUSIVE**（确定性代理标签协议失灵：中文词表 × 英文元数据 → 10/10 人工强正例被判 unusable，Top-K usability 指标本轮不可用）。字面树分支（B/C 均不达标 → VISUAL_GENERATION_REQUIRED / DIRECTOR_LAYER_STILL_PRIMARY）因测量协议缺陷而不采纳。详见 `STAGE33_CV2_BENCHMARK_REPORT.md`。已证实子结论：池规模供给存在（20/20 镜有候选）、权利近净（2/399 待人工核对）、下载需缓存+退避（M-S03-162 持续 429 → SUPPLY_FAILURE）。**等待人类裁决，不自行进入实现。**

---

## 一、Q1：素材供给到底是不是第一瓶颈？（可证伪判断 + 本轮证据）

**可证伪命题**：`P_supply`：把候选池扩大 ~10×（33 → 300+）并保证获取稳定性后，Material Usability Rate（Top-5 中可拍该句的素材比例）显著上升，且不依赖视觉模型即可达到可用水平。

**本轮已获得的证据（三类，全部实测）**：

| 证据 | 数据 | 指向 |
|---|---|---|
| E1 现有池分析 | 33 个 ≥50 候选 / 13 镜；**7/20 镜（S01/S02/S10/S13/S15/S16/S18）零候选**；有候选镜平均 2.5 个 | 池规模硬约束真实存在 |
| E2 供给可行性（Commons 实测，隔离实验 `output/stage33/cv2/supply_probe.json`） | 7 查询一次会话采到 **209 个候选**；许可合规率 **96–100%**（CC/PD 为主）；视频 50 个全合规；分辨率达标率 24–84%（按查询）；窄需求"white coral skeleton"仅 2 个 | **扩大 10× 可行**（供给存在且权利干净）；但**窄语义需求（S03 雪白骨架）供给薄**，且检索相关性未验证 |
| E3 获取可靠性 | 缩略图下载首轮 429 率 ~50%，退避重试后多数成功；13 分钟/209 候选 | 供给层必须内置缓存+退避+重试；下载是波动点而非瓶颈 |

**初步判断**：证据强烈支持 `SUPPLY_IS_PRIMARY_BOTTLENECK`（见 §十），但"相关性/可用性"必须由 §五 benchmark + §七 A/B/C 的人工标签实验最终确认——**若扩大池后 usability 不升（B 实验失败），判定回退为 SUPPLY_PLUS_VISUAL_UNDERSTANDING；若 B/C 都失败 → VISUAL_GENERATION_REQUIRED 或 DIRECTOR_LAYER_STILL_PRIMARY**。

---

## 二、Material Requirements Contract（Visual Statement → 素材需求契约）

> 核心转变：**Director 不再直接选择素材，而是描述"我需要什么视觉证据"**；Material Supply Layer 负责提供候选。

| 字段 | 类型 | 语义 | 谁产生 |
|---|---|---|---|
| subject | enum/词表 | 主体对象（珊瑚/鱼群/温度图/潜水员/城市…，必须 grounded 于口播/证据） | Director |
| scene | enum | 场景（水下/海面/岸边/实验室/城市…） | Director |
| visual_role | enum | ESTABLISHING/SUBJECT/DETAIL/ACTION/CONTEXT/EVIDENCE/DATA/COMPARISON/EMOTIONAL/RHYTHM | Director |
| evidence_role | enum | direct_evidence/illustrative/metaphor/anchor | Director |
| preferred_visual_type | enum[] | 优先视觉类型（photo/video/chart/painting=0 默认禁） | Director |
| **forbidden_visual_type** | enum[] | **禁选类型（painting/film_still/portrait 默认禁，纪实风格契约）** | 契约+Director 覆盖 |
| people_presence | enum | none/few/many/subject | Director |
| subject_count | int|null | 主体数量需求 | Director |
| shot_scale | enum | extreme_close/close/medium/wide/establishing | Director |
| composition | enum | center/thirds/negative_space/split/full | Director |
| orientation | enum | landscape/portrait/any | Director |
| style_realism | enum | realistic_photo/documentary/graphic | Director |
| negative_space | bool | 需要留白（供锚点词叠加） | Director |
| text_overlay_suitability | bool | 是否允许画面叠字（人物/密集图默认 false） | Director |
| temporal_suitability | enum | image_only/video_preferred/either | Director |
| minimum_resolution | {w,h} | 默认 1280×720 | 契约 |
| rights | enum[] | SAFE 或 CONDITIONAL+commercial_use（沿用 3.1.4 语义） | Supply Layer |
| confidence | float | 需求置信度 | Director |

**不变量**：需求只能引用 grounded 元素（口播原文/证据）；契约字段由 Validator 结构校验；Supply Layer 只能按需求过滤/排序，不得改写需求。

---

## 三、供应链架构（11 层，逐层职责与"不能解决什么"）

```
Narration → Visual Statement → Material Requirements → Candidate Retrieval
→ Rights/Format Filter → Quality Filter → Visual Attribute Filter
→ Semantic/Visual Compatibility Ranking → Top-K Pool → Director Final Selection → Executor
```

| # | 层 | 职责 | 该层解决不了什么 |
|---|---|---|---|
| 1 | Visual Statement | 注意力命题与视觉证据需求（现有 3.3，保留） | 素材的可得性/真实性 |
| 2 | Material Requirements | 把命题转成可过滤的结构化需求（§二契约） | 素材画面内容验证 |
| 3 | Candidate Retrieval | 多路由召回（3.1.4 检索 + 供给扩容路由：分类/全文/实体/视频源），目标召回 300+ 粗候选 | 精确相关性（只保证 recall） |
| 4 | Rights/Format Filter | license/SAFE、格式、时长（硬门槛，先于一切评分） | 素材质量 |
| 5 | Quality Filter | 分辨率/长宽比/文件健康/去重（SHA/感知哈希） | 语义适配 |
| 6 | Visual Attribute Filter | 视觉类型/人物存在/景别/风格过滤（对应 forbidden_visual_type/people_presence 等需求） | 语义相关性的最终判断 |
| 7 | Compatibility Ranking | semantic + 契约字段匹配 + （可选）视觉嵌入，产出 Top-K（K=5） | 创意层面的最终取舍 |
| 8 | Top-K Pool | 候选池交付（含全量 provenance） | — |
| 9 | Director Final Selection | 从 Top-K 选最终素材并写理由（沿用 statement 可解释性） | 池外的可能性（池外即无） |
| 10 | Executor | 渲染执行（现有 3.2b/3.3 执行层） | 素材本身的表达力 |
| 11 | （横切）Supply Operations | 下载/缓存/SHA/退避/生命周期管理 | 源站可用性（不可控，只能容错） |

**关键设计决策**：视觉属性过滤（第 6 层）在 CV-2 用**确定性元数据+轻量分类器**实现（CV-1 证明 CLIP 的 has_person 不可靠 → 该层用：extmetadata 许可/作者、尺寸、文件类型 + **是否引入人物/风格检测器由实验驱动**，见 §八）；**禁止未经实验证明的模型堆叠**。

---

## 四、Benchmark 设计（CV-2 确认实验，进入实现前的前置）

**规模**：≥100 候选（目标 100–300），由 §三 第 1–7 层真实产出 + 人工构造混入。

**必含类别（每类 ≥5）**：强正例（该句可拍）、弱正例、语义相关负例（相关但拍不了这句）、人物剧照、油画、沙滩人物、无关人类活动、错误构图、错误景别、低分辨率、重复素材（去重测试）、视频素材。

**本轮失败样本强制纳入**：
- `S03 × M-S03-162`（电影剧照）：**M-S03-162 当前无法稳定获取（Commons 429 实测）→ 记为 SUPPLY_FAILURE，不替换样本**；若获取成功则入池，若持续失败则单独报告"该负例因供给失败无法进入 benchmark"；
- `S12 × 油画`、`S19 × 沙滩孩子`：必须入池。

**标签**：(candidate, shot, label) 三元组人工标注：`usable / usable_with_edit / not_usable`，≥10 个人工正例与 ≥10 个人工负例（沿用 CV-1 判定口径），全部 SHA+标签留档。

---

## 五、评价指标（Material Usability Rate 体系）

核心：**Top-K 候选中经人工判断可直接用于 Visual Statement 的素材比例**（不是 embedding 分数）。

| 指标 | 定义 |
|---|---|
| Top-1 / Top-3 / Top-5 usability | 各 K 的 usable 占比 |
| strong-positive retention | 强正例保留率 |
| semantic-negative rejection | 语义负例被排低率 |
| visual-negative rejection | 视觉类型负例（油画/剧照）被排低率 |
| person-related false acceptance | 人物误入非人物需求 Top-K 的比例 |
| style mismatch rate | 风格错配率（禁油画却入池） |
| composition mismatch rate | 构图需求不符率 |
| resolution failure rate | 分辨率不达标漏网率 |
| rights failure rate | 权利门漏网率（应为 0） |
| candidate diversity | Top-K 内唯一主体/类型熵 |

**成功线（预固定，不事后调）**：Top-5 usability ≥ 60% 且 rights failure = 0 且 strong-positive retention ≥ 80%。仅作 CV-2 实验判据，非生产 Gate。

---

## 六、A/B/C 对照（"供给 vs 理解"边界）

| 组 | 条件 | 回答的问题 |
|---|---|---|
| A | 现有池（33）+ 现有 semantic retrieval | 基线（≈当前失败） |
| B | **扩大池（≥100）+ 现有 semantic retrieval** | 只扩供给是否够？ |
| C | 扩大池 + 视觉属性过滤/轻量视觉理解 | 是否仍需视觉理解？ |

判定：B 明显改善 → 主要瓶颈=供给；B 失败而 C 改善 → 供给+理解共同瓶颈；B/C 都失败 → 重估 Director/生成/评估。**不预设结论。**

---

## 七、网络与素材获取独立能力测试（本轮已实测）

| 项 | 实测结果 |
|---|---|
| API 检索稳定性 | 7 查询全部成功（13 分钟），无 API 级 429 |
| **下载稳定性** | **缩略图首轮 429 ≈50%**；退避重试（8s×n+抖动）后多数成功 → 供给层必须内置缓存+重试；与历史 M-S03-162/M-S04-221/M-S11-552 下载失败同源 |
| 视频源 | 稳定存在（coral video 一次采样 50 个，100% 许可合规，64% ≥1280×720） |
| 权利元数据 | extmetadata.LicenseShortName 可编程判定，合规率 96–100% |
| 去重 | 标题归一可做（unique_titles 实测）；感知哈希去重待实验 |
| 分辨率 | 达标率按查询 24–84% → Quality Filter 必需 |
| SHA | 下载即录 SHA（本轮已记录部分） |
| 生命周期 | 未测（需缓存与失效策略设计） |

---

## 八、模型堆叠禁令（实验驱动原则）

- 不因"CLIP 不行"引入 VLM/YOLO/分类器堆叠；
- 第 6 层（Visual Attribute Filter）先只用**确定性信号**（类型=内容类型+许可元数据+尺寸；人物/油画信号先由**人工标注的检索元数据**与需求端 forbidden_visual_type 承担）；
- 只有当 B 实验证明"扩池后语义检索无法分离油画/剧照"时，才允许提出"人物/风格检测器"的实验性验证（单独 PoC，同样设成功率线）。

---

## 九、本轮实验产物（隔离）

- `output/stage33/cv2/supply_probe.json`：供给可行性实测（209 候选、权利/分辨率/下载数据）；
- `output/stage33/cv2/supply_probe.py`：探测脚本（不触碰生产链）；
- 本文档：契约/架构/benchmark/指标/A-B-C/决策树。

---

## 十、CV-2 最终决策树输出

> **终判（benchmark 运行后，见 `STAGE33_CV2_BENCHMARK_REPORT.md`）：`INCONCLUSIVE`。** 下方"本轮输出"为 benchmark 运行前的预判，已被实测覆盖：B/C 均不达字面成功线，但根因是确定性代理标签协议失灵（中文词表 × 英文元数据，10/10 人工强正例被判 unusable），属 §十 预留的"证据不足 → INCONCLUSIVE"分支，不落入 VISUAL_GENERATION_REQUIRED / DIRECTOR_LAYER_STILL_PRIMARY。等待人类裁决。

**本轮输出（benchmark 前预判，已被上条更新覆盖）：`SUPPLY_IS_PRIMARY_BOTTLENECK`（证据强支持，附条件）**

依据：
1. E1：现有管线 7/20 镜零候选、33 候选/13 镜——供给硬约束是当前最直接的可解释瓶颈；
2. E2：一次探测即得 209 个许可干净候选（96–100% 合规）且视频供给丰富——**扩大 10× 是现实可行的**；
3. E3：获取层的 429 波动是工程问题（缓存/退避可解），非能力缺口；
4. CV-1：视觉理解（CLIP）已被证明不足以解决"语义相关但视觉不适合"——但 B 组实验（只扩池）尚未运行，因此**不排除** SUPPLY_PLUS_VISUAL_UNDERSTANDING。

**条件（进入实现前的确认实验）**：按 §四/§五/§六 运行 A/B/C 人工标签 benchmark（≥100 候选）。若 B 的 Top-5 usability ≥60% → 终判 `SUPPLY_IS_PRIMARY_BOTTLENECK` 成立，授权设计素材供给层；若 B 不达标而 C 达标 → 改判 `SUPPLY_PLUS_VISUAL_UNDERSTANDING`；若 B/C 均不达标 → 改判 `VISUAL_GENERATION_REQUIRED` 或 `DIRECTOR_LAYER_STILL_PRIMARY`。**证据不足时输出 INCONCLUSIVE，不自行进入实现。**

---

## 十一、纪律与停止线

- 本轮已做：架构设计、benchmark 设计、供给可行性验证、现有池分析、隔离探测实验；
- 未做且禁止：生产代码、pipeline/baseline 修改、Coral 重渲染、V3 plan 修改、CLIP 生产接入、阈值放宽、模板增加、模型堆叠；
- 下一步（待授权）：① 按 §四 构建 ≥100 候选 benchmark（含 3 个失败样本；M-S03-162 若仍不可获取 → 记录 SUPPLY_FAILURE）；② 人工标签（usable/usable_with_edit/not_usable）；③ 运行 A/B/C 与指标；④ 按 §十 输出终判。
- **STOP。**
