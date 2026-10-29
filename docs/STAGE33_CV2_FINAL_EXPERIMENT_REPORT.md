# Stage 3.3 CV-2 正式实验报告（Protocol v2）

> 状态：**正式 A/B/C 实验完成。结论由数据决定，不预设。** 未修改生产代码、Gold Standard、V3 plan、P1/3.2b/3.1.4 baseline、协议阈值、人工标签。
> 实验后 **STOP**，等待人工裁决。

---

## 1. 实验环境与版本

| 项 | 值 |
|---|---|
| 协议版本 | CV-2 Experiment Protocol **v2**（amendment，SHA256 `E7BF80DAC18E4A170D7FC387FBE003B08D20DC3C3919D6A791B9F30DA137E00D`） |
| Gold Standard（冻结） | `gold_standard_frozen.json`，SHA256 `C70C82D462A82A7D4A3D3D35F80EE65748106AC9B57E4BB74AC81E34B9E448AC` |
| A/B/C harness | `run_abc.py`，SHA256 `DA01D94500EAD1E22406F016FA0C489F379FDA5FFB391570A0EDF3E76E022B8B` |
| A/B/C 结果 | `abc_result.json`，SHA256 `E1468FB0029CAA83C55C87EDE053E9842D20E767DF8F1CF9FC6C8C1B4EFF8A01` |
| 后处理 | `abc_postprocess.json`，SHA256 `CBA2BDE6CC2359EB98E4739766396666078272FB35E3EBFC08D147695B257766` |
| A pool | whitelist 33（不含 constructed probes） |
| B pool | whitelist 33 + Commons 366 = 399（不含 constructed probes） |
| C pool | B + visual attribute filtering |

**Harness 修复记录**（正式运行前，用户授权）：修复 3 处大小写/命名 bug（canonical enum、`canonical_candidate_key`、探针隔离），self-test 6/6 PASS。修复 SHA 已记录。本次正式运行无 harness 改动。

---

## 2. Gold Standard distribution（冻结，73 条）

| 子集 | SP | SN | HN(user) | ORD | 合计 |
|---|---|---|---|---|---|
| natural（59） | 24 | 24 | 3 | 8 | 59 |
| constructed（14） | 1 | 4 | 6 | 3 | 14 |
| **合计** | 25 | 28 | 9 | 11 | 73 |

- **Strict HN = 2**（定义：`NOT_USABLE ∧ HIGH`），`n=2 exploratory`；
- **Historical Failure = 3**：S03×M-S03-162（NOT_USABLE/LOW）、S12×M-S12-607（**USABLE/MEDIUM，人工标签原样**）、S19×M-S19-954（NOT_USABLE/MEDIUM）。

---

## 3. Supply Coverage（Gate A 供给存在性）

### 3.1 A → B 零候选变化

| | A（现有池 33） | B（扩池 399） |
|---|---|---|
| 零候选镜头数 | **7** | **0** |
| 零候选镜头 | S01/S02/S10/S13/S15/S16/S18 | （无） |
| 有候选镜头 | 13/20 | **20/20** |

**7 个历史零候选镜头全部解除**：S01→20、S02→5、S10→20、S13→20、S15→20、S16→20、S18→20（候选数）。

### 3.2 每镜候选数（whitelist + commons）

| shot | wl | commons | A 总数 | B 总数 | shot | wl | commons | B 总数 |
|---|---|---|---|---|---|---|---|---|
| S01 | 0 | 20 | 0 | 20 | S11 | 3 | 17 | 20 |
| S02 | 0 | 5 | 0 | 5 | S12 | 3 | 20 | 23 |
| S03 | 1 | 18 | 1 | 19 | S13 | 0 | 20 | 20 |
| S04 | 3 | 20 | 3 | 23 | S14 | 2 | 20 | 22 |
| S05 | 3 | 20 | 3 | 23 | S15 | 0 | 20 | 20 |
| S06 | 3 | 20 | 3 | 23 | S16 | 0 | 20 | 20 |
| S07 | 2 | 20 | 2 | 22 | S17 | 3 | 6 | 9 |
| S08 | 3 | 20 | 3 | 23 | S18 | 0 | 20 | 20 |
| S09 | 3 | 20 | 3 | 23 | S19 | 2 | 20 | 22 |
| S10 | 0 | 20 | 0 | 20 | S20 | 2 | 20 | 22 |

- A 平均候选/镜（有候选的 13 镜）≈ 2.5；B 平均候选/镜 ≈ 20.0（min 5=S02、max 23）；
- retrieval coverage：A=0.65（13/20）、B/C=1.0（20/20）。

**结论**：A→B 在"供给存在性"上彻底解决了原 7 个零候选镜头，20/20 全覆盖。

---

## 4. Main Usability（主指标，三档严格区分）

| 指标 | A | B | C |
|---|---|---|---|
| Top-1 usability | 0.538 | 0.400 | 0.389 |
| Top-3 usability | 0.449 | 0.433 | 0.454 |
| **Top-5 usability** | 0.449 | **0.442** | 0.440 |
| usable shot coverage | 0.45 | 0.60 | 0.45 |
| retrieval coverage | 0.65 | 1.00 | 1.00 |

**Top-5 三档分布（labeled 候选）**：

| | A | B | C |
|---|---|---|---|
| USABLE | 16 | 28 | 23 |
| CONDITIONALLY_USABLE | 2 | 5 | 5 |
| NOT_USABLE | 15 | 26 | 21 |

**关键观察**：B 组 Top-5 usability = **0.442 < 0.60**（Gate 失败）。扩池后 Top-5 中 NOT_USABLE 绝对数反而从 15 升到 26——**候选变多 ≠ 视觉质量变好**，大量语义相关但视觉不适合的候选进入了 Top-5。C 组过滤后 Top-5 usability 基本不变（0.440），三档分布也无实质改善。

---

## 5. Strong Positive（SP=24，正式 Gate）

### 5.1 retention（两个口径都报告，不混）

**口径 A：harness "前半保留"口径**（`strong_positive_retention`，Protocol v2 沿用预注册口径）：

| | A | B | C |
|---|---|---|---|
| SP retention（前半） | 0.438 | **0.958** | 0.833 |

**口径 B：Top-K retention（后处理，细粒度分解，非 Gate 口径）**：

| | A | B | C |
|---|---|---|---|
| Top-1 retention | 0.438 | 0.333 | 0.318 |
| Top-3 retention | 1.000 | 0.750 | 0.818 |
| Top-5 retention | 1.000 | 0.875 | 0.864 |

> **披露**：两口径差异源于 A 组每镜候选数极少（多为 1–3 个，SP 天然进 Top-3/5），而 B 组扩池后每镜候选变多，SP 被挤到后半的更多。Gate 判定的"SP retention ≥80%"应明确采用哪个口径——harness 前半口径 B=95.8% PASS，Top-1 口径 B=33.3% FAIL。**本报告不自行裁定，两条都列，供人工裁决。**

### 5.2 false rejection

| | A | B | C |
|---|---|---|---|
| false negative（SP 被 C 过滤） | 0 | 0 | **2** |

C 组误杀 2 个 SP：`S03:commons:File:Dendrogyra cylind...`（珊瑚柱状特写，因"diver/person"关键词? 实际为"museum/painting"类误伤）、`S12:M-S12-607`（渔民油画，人工标 USABLE，但 C 的"painting/oil"过滤把它移除了）。

**重要**：M-S12-607 人工标签是 USABLE/MEDIUM，但 C 组视觉过滤按"painting"关键词将其误杀——这正是"视觉属性过滤会误伤人工认为可用的素材"的直接证据。

---

## 6. Strong Negative（SN=24）

| | A | B | C |
|---|---|---|---|
| SN suppression（后半，harness） | 0.600 | 0.000 | 0.167 |
| SN Top-1 exposure（后处理） | 0.400 | 0.500 | 0.450 |
| SN Top-3 exposure | 1.000 | 0.875 | 0.850 |
| SN Top-5 exposure | 1.000 | 0.958 | 0.950 |

**观察**：扩池后（B）SN 的 suppression 从 A 的 0.6 跌到 0（大量 SN 被挤到前半/Top-K）；C 过滤后只恢复到 0.167，且 SN 仍有 ~45% 进入 Top-1、~85% 进入 Top-3。**确定性视觉过滤对 SN 的压制效果微弱**。

---

## 7. Strict HN（n=2，exploratory only，不参与硬 Gate）

| candidate | A 存在 | B rank | C rank | C 过滤 | Top-1/3/5 | B→C |
|---|---|---|---|---|---|---|
| `S12:1899_Cross_Hauling_the_Nets_Tel_Aviv_Museum_of_Art_anagoria.jpg`（渔夫油画，NOT_USABLE/HIGH） | 否 | 4 | **null** | **✅ 过滤** | B Top-5 | 被过滤（下沉成功） |
| `S05:The_optical_feedback_loop_driving_colourful_coral_bleaching.jpg`（白化机制示意图，NOT_USABLE/HIGH） | 否 | 4 | 4 | ❌ 未过滤 | B Top-5 | 0（未改善） |

**解读（n=2，仅探索性）**：2 个严格 HN 中，1 个（渔夫油画，标题含"painting"）被 C 组成功过滤下沉，另 1 个（科研示意图，标题无 painting/oil 等关键词）C 组**未能过滤**。说明确定性视觉过滤对"油画/绘画"类陷阱有效，但对"图表/示意图"类陷阱**无能为力**（其标题不含触发过滤的关键词）。**样本极小，仅作信号，不可统计推断。**

---

## 8. Historical Failure Regression（三案例，A/B/C 全测）

| Case | 人工标签 | A rank | B rank | C rank | C 过滤 | Top-1/3/5 | B→C |
|---|---|---|---|---|---|---|---|
| S03 × M-S03-162（电影剧照） | NOT_USABLE/LOW | 1 | 1 | **null** | ✅ 过滤 | Top-1 | 被过滤 |
| S12 × M-S12-607（渔民油画） | **USABLE/MEDIUM** | 1 | 1 | **null** | ✅ 过滤 | Top-1 | 被过滤 |
| S19 × M-S19-954（沙滩孩子） | NOT_USABLE/MEDIUM | 1 | 1 | 1 | ❌ 未过滤 | Top-1 | 0 |

**关键发现**：
1. **S03 剧照**：A/B 组均排 Top-1（检索把它们当最高语义候选），C 组才被过滤。历史失败案例在纯语义检索下**被置顶**，印证"语义相关 ≠ 视觉适合"。
2. **S12 渔民油画（人工标 USABLE）**：C 组按"painting"过滤**误杀**了人工认为可用的素材（与 §5.2 false negative 一致）——确定性过滤与人工判断冲突。
3. **S19 沙滩孩子**：三组均 Top-1，C 组**未过滤**（标题无触发词），历史失败案例无法被确定性过滤解决。

**结论：候选数量增加（A→B）没有改善 Historical Failure 的排序；C 的过滤只对"标题含 painting/film 关键词"的案例有效，且会误伤人工认为可用的 S12 油画。"候选数量增加 ≠ 视觉质量增加"。**

---

## 9. Rights / Download（正式 Gate：rights failure = 0）

| | A | B | C |
|---|---|---|---|
| rights failure（人工标注 UNSAFE） | 0 | 0 | 0 |

**license distribution（Commons 366）**：Public domain 166、CC BY-SA 4.0 85、CC BY 4.0 52、CC BY-SA 3.0 19、CC0 14、CC BY-SA 2.0 14、CC BY 2.0 9、CC BY 3.0 3、**Attribution 2**、CC BY-SA 2.5(±it) 2。

- 上一轮 2 个"rights failure"（Copernicus `Attribution`）**已确认为判定器漏配**（CC BY 短名），本轮 harness 用人工标注的 `rights_status`（全部非 UNSAFE），**rights failure = 0 ✅ 满足 Gate**；
- 下载：实验层已在前置阶段完成（HN 14/14、batch1 20/20、全池缩略图 59/59）；429 需退避重试，M-S03-162 原始 URL 已可 200 获取。本实验主流程不涉及运行时下载。

---

## 10. A→B→C 增益链分析（核心）

### A → B（只扩供给）

- **解决了"没有素材"**：零候选镜 7→0，coverage 0.65→1.0 ✅；
- **但视觉适用性未改善**：Top-5 usability 0.449→0.442（持平略降），Top-5 中 NOT_USABLE 从 15 升到 26；
- **SP Top-1 retention 反而下降**（0.438→0.333），SN suppression 从 0.6 跌到 0。

**回答**："单纯扩大真实素材供给，解决了'没有素材'，但没有解决'素材不合适'。候选变多后，不合适素材反而占据 Top-K。"

### B → C（加视觉过滤）

- Top-5 usability 0.442→0.440（**几乎无改善**）；
- SP retention（前半）0.958→0.833（下降，且误杀 2 个 SP，含 M-S12-607）；
- SN suppression 0→0.167（微升）；
- Strict HN 2 个中 1 个被过滤、1 个未过滤；Historical 3 个中 1 个被过滤（但该案例人工标 USABLE，属误杀）。

**回答**："在素材已足够多后，确定性视觉属性过滤**没有**实质改善视觉适用性，反而引入误伤（SP 被过滤，含人工认为可用的渔民油画）。"

### A → C（全链路）

- 供给覆盖从 0.65→1.0（正面）；
- 视觉适用性 Top-5 usability 0.449→0.440（无改善）；
- 引入 SP 误杀 2 个。

**回答**："整个能力链改善了供给覆盖，但没有改善视觉素材选择质量；视觉过滤层在当前确定性实现下净收益为负（误伤 > 陷阱压制）。"

---

## 11. Gate 判定（Protocol v2 成功线，严格执行）

### Gate B（正式）

| 条件 | 目标 | 实测 | 判定 |
|---|---|---|---|
| Top-5 usability | ≥60% | **44.2%** | ❌ FAIL |
| rights failure | =0 | 0 | ✅ PASS |
| SP retention（前半口径） | ≥80% | 95.8% | ✅ PASS |

**B Gate = FAIL**（Top-5 usability 44.2% < 60%）。

> **口径披露**：若 SP retention 采用 Top-1 口径（33.3%），则 SP retention 也 FAIL；采用前半口径（95.8%）则 PASS。无论 SP 口径如何，**Top-5 usability 44.2% 已决定性使 B Gate FAIL**，结论不因 SP 口径摇摆而改变。

### Gate C（探索性，不设硬阈值）

视觉过滤的陷阱压制效果**微弱且带误伤**，不能判定"视觉理解成功"。

---

## 12. 最终能力层判定

**`SUPPLY_LAYER_PARTIALLY_VALIDATED`**

判定依据（数据驱动，非预设）：

1. **供给存在性（正面）**：A→B 使 20/20 镜有候选，7 个历史零候选镜全部解除，rights failure=0，下载可靠——**素材供给层的"供给能力"得到验证**；
2. **视觉适用性（未验证）**：B Top-5 usability 44.2% < 60%（Gate FAIL），扩池后 NOT_USABLE 进入 Top-5 的绝对数上升，Top-5 usability 无改善——**"扩大供给足以让 Stage33 从'无素材退化'走向'可用视觉证据'"这一命题不成立**；
3. **确定性视觉过滤（负面）**：C 对 Top-5 usability 无实质改善，且误杀 2 个 SP（含人工标 USABLE 的渔民油画）；对图表/示意图类陷阱和沙滩孩子类失败无能为力；
4. **Historical Failure（警示）**：S03 剧照在 A/B 组被置顶（语义检索的固有风险），S19 沙滩孩子三组均 Top-1 且 C 未过滤；S12 渔民油画被 C 误杀。

**一句话结论**：扩大真实素材供给**解决了"有没有素材"**（供给层部分有效），但**没有解决"素材合不合适"**（视觉适用性无改善，且确定性过滤有误伤）。因此是"部分验证"，不是"完全验证"，更不是"视觉理解成功"。

---

## 13. 已知局限

1. **Strict HN n=2**：仅探索性证据，无统计效力；
2. **SP retention 口径**：前半 vs Top-1 两口径差异大（95.8% vs 33.3%），本报告并列披露，未自行裁定 Gate 口径；
3. **确定性视觉过滤是"标题关键词"实现**：对标题不含 painting/oil/rmg 等词的油画/示意图/漫画无能为力（S09 版画、S11 矢量图、S20 古书扫描均未被过滤）；更严格的过滤需要更强的视觉理解能力；
4. **Top-5 三档分布中"labeled"候选稀疏**：B 组每镜有 20+ 候选但多数未标注，Top-5 usability 分母为"labeled"候选数，可能与真实 Top-5 全量有偏差；
5. **probe 的 B/C rank 是在"注入临时池"中测得**（probe 天然不在 supply pool），其排名仅代表"若被检索召回后"的相对位置；
6. **下载 429 是间歇性源站限流**，实验主流程不依赖运行时下载，但生产供给层必须内置缓存+退避。

---

## 14. Audit trail

- 协议 v2 amendment：`E7BF80DA...`（含修改理由、证据、时间戳）
- Gold Standard 冻结：`C70C82D4...`（73 条人工标签，冻结后未改）
- Harness 修复：三处 bug（大小写/key 归一化/探针隔离），self-test 6/6 PASS，正式运行前完成
- 正式运行：`abc_result.json`（`E1468FB0...`）+ `abc_postprocess.json`（`CBA2BDE6...`）
- 未修改：生产代码、Gold Standard、V3 plan、P1/3.2b/3.1.4 baseline、协议阈值、人工标签

---

**实验完成。STOP，等待人工裁决。**
