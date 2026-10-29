# Stage 18 设计诊断:Visual Intent 解耦方案(纯设计,不执行)

> 依据的已证事实:S17(56 对应拍中 54% Generic/Mismatch,主因=Query 焦点过拟合);S17.2(证据核心重排 5/10 可解释提升,机制=复合焦点挡住真实证据);S17.3(冻结 CV-2 在 intent 兼容时给出 0.9 USABLE,在 intent 冲突时把语义 HIGH 的真证据判 0.2——瓶颈锁定在 `visual_intent` 的复合 focus 模板)。
> 约束:不修改 Retrieval/Gate/V1/CV2/素材源/权重。解耦的关键认知:**intent 是数据不是代码**——冻结模块消费 `intent["visual_intent"]` 字符串;本方案在意图生成层产出新的解耦 intent,冻结代码零改动。

## 1. 解耦流水线

```
Narration(口播句)
  → Narrative Meaning(这句话在主张/追问什么 —— 命题核)
  → Visual Evidence Core(观众应该看到的"现实证据"——单一句,具体名词+动作/场景)
  → Evidence Type(证据类型枚举)
  → Visual Focus(唯一核心主体+唯一动作/状态)
  → Query(仅由 Visual Focus 派生的 2-3 条英文关键词)
```

## 2. 字段规范

| 字段 | 内容规则 | 消费方 |
|---|---|---|
| `narrative_meaning` | 一句话命题:口播真正主张/追问什么;禁止出现画面词汇 | 仅解释/审计 |
| `evidence_core` | "观众应该看到什么现实证据":具体名词+动作/场景,一句话;禁止"未来/现代/高科技"类修饰(除非是口播本义) | 仅解释/审计 |
| `evidence_type` | 枚举:`REAL_EVENT`(真实事件/人物/档案/历史影像) · `INDUSTRY_SITE`(行业现场) · `REAL_METAPHOR`(真实场景承载抽象概念) · `DATA_VISUAL`(图表/地图,仅当口播需要数据) · `ATMOSPHERE`(泛用空镜,仅当口播为纯氛围句且无证据可用) | Query 源偏好(既有源内部) + 审计 |
| `visual_focus` | **默认一个核心主体 + 一个动作/状态**;禁止强制多元素同框;禁止把"背景要求"写进 focus | Retrieval 派生 + Gate/CV2 的 focus_hint(兼容字段 `visual_intent` 的唯一内容) |
| `query` | 由 `visual_focus` 派生的 2-3 条英文查询;禁止从 narrative_meaning/evidence_core 直接造词 | Retrieval |
| `forbidden` | 旧模板的强制元素清单(如"城市天际线")——**只记录,永不作为 gate 硬条件** | 仅审计 |
| `provenance` | 口播→命题→证据的推导链 | 仅审计 |

### 类型判定规则(Literal / Metaphorical / Real-world Evidence 的区分)

- **Literal**:口播含具体可摄对象(手机/教室/机器人)→ `visual_focus` = 该对象本身,`evidence_type ∈ {REAL_EVENT, INDUSTRY_SITE}`;
- **Real-world Evidence**:口播为可核查的事实/预测/现象 → focus = 该事实的可见现场(事件/场所/档案影像);
- **Metaphorical**:口播为纯抽象句(哲学/未来/价值)→ `REAL_METAPHOR`:选一个**真实存在**的场景承载(黎明天际线=文明被点亮;十字路口=选择),禁止虚构合成画面;
- 纯氛围句且无任何证据可用 → `ATMOSPHERE`(降级,须在 provenance 记录原因)。

## 3. 字段路由(必须进 Retrieval vs 只供排序/解释)

| 进 Retrieval(唯一输入) | 只供排序/解释(禁止进入检索与硬过滤) |
|---|---|
| `visual_focus`(派生 query 的唯一来源);`evidence_type`(既有源内部偏好:REAL_EVENT→commons 档案,INDUSTRY_SITE→pexels 现场) | `narrative_meaning`、`evidence_core`(排序语义解释)、`forbidden`(仅审计)、`provenance` |

**硬规则**:负向要求(forbidden)不得参与任何 keep/drop 判定;多元素并列(旧模板"主体+天际线+数据屏")在 `visual_focus` 层被结构性消灭——每拍只允许一个 focus。

## 4. 与冻结链的对接(零代码改动)

- Gate 消费 `intent["visual_intent"]` → 新 intent 令该字段 = `visual_focus` 句子(单一主体);
- CV-2 `vision_call(..., focus=intent.visual_intent[:200])` → 同上,17.3 已证明:同一冻结链在 intent 不再强制复合场景时,能正确放行真证据(S30-B01 0.9 USABLE / HIGH);
- V1/排序、Renderer、correspondence 口径均不变。

## 5. 旧 Intent → 新 Intent 转换示例(5 例,全部来自 Top-10 实拍数据)

| Beat | 旧 visual_intent(复合) | 新解耦 intent |
|---|---|---|
| **S30-B01** | "未来城市中机器人手臂在工厂流水线工作,**同时字幕显示预测数据**" | NM:"预测称2035年20%岗位被自动化取代" → EC:"真实工厂里机械臂正在执行一项具体工种,现场有工人" → ET:INDUSTRY_SITE → **VF:"工厂中机械臂执行工种,工人在场"** → Q:`robotic arm factory assembly line worker`(17.3 已验证此路径:USABLE 0.9) |
| **S12-B02** | "特写人类迷茫的眼神,**背景是天平、契约文件崩塌**,场景为空旷广场" | NM:"价值不再由劳动定义,社会契约何以延续(设问)" → EC:"一位真实劳动者正在工作" → ET:REAL_EVENT → **VF:"一名工人在工作现场"** → Q:`construction worker portrait working site` |
| **S34-B01** | "未来城市中,发光的AGI形象从屏幕走出,**与人类并肩站立**于现代办公室" | NM:"AGI 从工具变为伙伴" → EC:"人与机器人并肩完成同一任务" → ET:REAL_METAPHOR → **VF:"人与机器人并肩操作"** → Q:`human robot collaboration working together`(17.3 中 HRC 锯木照片因"非办公室"被拒;新 focus 删除办公室要求) |
| **S08-B03** | "人类与机器人面对面坐谈判桌,**中间悬浮天平与电路图标**" | NM:"人类首次直面与机器共治的伦理困境" → EC:"真实控制中心里人类监督机器系统运转" → ET:INDUSTRY_SITE → **VF:"控制室操作员面对监控屏幕墙"** → Q:`control room operator monitors industrial` |
| **S02-B01** | "未来城市全景,AGI 接管日常,**人类在职业与情感选择中面临抉择**" | NM:"AGI 接管日常,人类选择权面临考验" → EC:"真实城市十字路口(选择的空间隐喻)" → ET:REAL_METAPHOR → **VF:"行人穿过城市十字路口"** → Q:`pedestrian crossing city intersection aerial` |

(对照:S24-B01 属 Metaphorical 类,新 focus = "黎明城市天际线",与现素材一致,不换——证明该方案不会为换而换。)

## 6. 最小可验证 Top-10 实验(设计,不执行)

**输入**:Top-10 拍的冻结 narration;解耦 intent 生成(一次性产出后**冻结哈希**,检索期间不得改写——防 per-candidate 调参);冻结 Retrieval/Gate/V1/CV2 全链原参数;既有素材源(commons/pexels,零新源);verdict 缓存沿用。

**流程**:每拍 ≤25 候选、Gate 后 CV-2 ≤3 次(frozen QUALIFIED 规则)、按冻结规则选 top-1;与原素材冻结判定(verdict_store_1226)对比。

**PASS 门槛(全部满足)**:
1. **≥7/10 拍**新链 best 候选严格优于原素材:`label ∈ {USABLE, CONDITIONALLY_USABLE}` 且 `fit ≥ 原素材 fit + 0.05`(原 fit 从冻结 store 读取,0.35–0.7 区间);
2. 其中 **≥3 拍 semantic_relevance = HIGH**(真实证据质量,不是"能过就行");
3. **0 拍退化**:新链无合格候选的拍必须回退原素材(禁止为通过而降级);
4. 相邻同字节对 = 0、无新增连续同型运动(复用 Stage 16 去重窗口与 16.2 运动规则);
5. 内容风险:敏感画面(地缘/暴力/灾难)由独立评审标记,不占 CV-2 名额、不因质量分放行。

**FAIL 门槛**:PASS-1 < 7/10 → `NO_NEXT_STAGE_REQUIRED`——意味着瓶颈不止 intent 层,剩余缺口为素材覆盖(需新一轮授权讨论,本方案不扩大)。

**对照指标(前后各记一份)**:每拍 `{old: fit/label, new: fit/label, evidence_type, focus句子, 换/不换}`;类型分布 Literal/Metaphor/RealEvidence;correspondence 影响预估(同拍换图,56 拍对应关系不变,spectrum 语义分只统计不修改口径)。

## 7. 明确不做的事

不修改任何冻结模块代码;不新增素材源;不为通过门槛调整 intent 措辞(意图生成一次性冻结);不以 GENERIC 空镜兜底(除非口播属纯氛围句且走 ATMOSPHERE 降级记录)。

---

```
STAGE18-DESIGN = PASS · STOP
解耦链:Narration→Narrative Meaning→Evidence Core→Evidence Type→Visual Focus(单主体)→Query · intent=数据层,冻结代码零改动 · 5 例转换含 17.3 已验证路径 · PASS≥7/10 且 ≥3 HIGH · FAIL→NO_NEXT_STAGE_REQUIRED
STOP——等待下一步授权
```
