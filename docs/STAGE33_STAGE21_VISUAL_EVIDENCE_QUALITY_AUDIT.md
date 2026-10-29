# Stage 33 — STAGE 21: VISUAL EVIDENCE QUALITY AUDIT(诊断 + 设计)

> **性质**:DIAGNOSTIC + DESIGN ONLY。基于外部独立审片报告对母片 `render_162/final_long.mp4`(508.29s)的诊断,建立 Visual Evidence Quality 问题定义、评价框架与离线验证方案。
> **边界**:零冻结模块修改 · 零 CV2/Gate/阈值/权重/Gold 改动 · 零检索/下载/网络 · 零渲染 · 零 Production Entry / Final Gate 改动 · 不进入 Production Run 01 · 不自动生成 APPROVED。
> 机器可读:`output/stage21_visual_quality/stage21_diagnostic.json`
> 上游事实:Takeover Audit(2026-09-06)· Production Entry · Final Quality Gate · Stage 20.1 · 本机只读交叉核验(见 §3)。

---

## 1. 问题定义(Stage 21 = Visual Evidence Quality Layer)

**Stage 21 不是**"让素材更丰富",**不是** Stage 18 reboot,**不是**生产修改任务。

**Stage 21 是**:

> **Visual Evidence Quality:一个画面除了与旁白相关之外,是否向观众提供了足够具体、可感知、可验证的视觉信息?**

审片整体判断(4.5/10):当前成片更接近"普通知识区 B-roll + AI 自动生成视频卡片感",而非"信息流纪录片"。系统已被证明能做到"相关素材"(correspondence 60.86%,G2 PASS),但尚未稳定做到"有视觉信息增量的现实证据"。

### 1.1 Correspondence 与 Visual Evidence Quality 严格分离

| 维度 | 回答的问题 | 冻结状态 | Stage 21 关系 |
|---|---|---|---|
| **Correspondence** | "这个画面和旁白相关吗?" | 冻结定义,56/90=60.86%,**原值不动** | 不重算、不重解释 |
| **Visual Evidence Quality** | "这个画面到底让我看见了什么?" | 本次新建的诊断概念,**设计态,不入生产** | 新评价对象 |

概念层级(设计态):

```text
Narration → Narrative Meaning → Visual Evidence Core → Evidence Type
→ Visual Focus → Query → Candidate → Correspondence → Visual Evidence Quality
```

Correspondence 是该链的**必要不充分**条件:60.86% 证明"相关",审片证明"相关 ≠ 有证据价值"。

### 1.2 与 Stage 18 的关系(正式记录)

> **Stage 18 已验证 Visual Intent Decoupling 方向有效(已关闭,不重开)。**
> 当前新问题:Visual Intent 已改善"搜什么",但不足以保证"搜到以后为什么值得用"。
> 因此 Stage 21 = **Visual Evidence Quality Layer**(质量层诊断与设计),不是 Stage 18 reboot,不重新执行检索实验。

---

## 2. 审片证据归档(标签:OBSERVED BY REVIEWER)

审片为外部人工/模型独立报告,其**数字是估计值,不是工程事实**(见 §3 归因)。

### 2.1 整体

- 整体评分 **4.5/10**;判断:知识区 B-roll + AI 卡片感,非信息流纪录片。

### 2.2 病灶一:素材疲劳 / 全片重复(审片观察)

| 审片观察 | 工程部分核验(55/90 拍账本覆盖) |
|---|---|
| 花坛人行道 ≥5 次 | "Strand street pedestrian crossing" 同一资产在账本可见 ≥3 处显示位(S01-B01/S03-B01 fallback 显示 + 借出源 S02-B01) |
| 白 T 恤打手机 ~3 次 | smartphone 族 4 拍:"Adult using smartphone indoors" ×2(S01-B02/S02-B02)+ "Silhouette of a man using a smartphone" ×2(S17-B01/S18-B02) |
| 工地脚手架 ~3 次 | "Newport university building under scaffolding" ×2(S07-B01/S09-B02,部分账本) |
| 控制室大屏 ~2 次 | "City tv control room" ×1(账本部分覆盖;另 MRI 屏幕类 ×2 可能被审片归入此类) |
| 伦敦天际线 ~2 次 | skyline 族合计 **5** 拍(dusk ×2 + Panama ×2 + HCMC ×1)——高于审片估计 |
| Pete 走路男子 2–3 次 | 账本中无法唯一标识(疑似 pexels 资产,题名不含 walk);crossing 族 4 拏 |

**结论**:方向一致——审片的疲劳观察与工程 reuse 数据同向;具体次数因账本只覆盖 55/90 拍而**未完成全量工程核实**,列入待验证(EXP-21.1)。

### 2.3 病灶二:Generic B-roll 占比(审片估计 vs 工程普查)

| 类别 | 审片估计 | 工程 Stage 20 普查(grade 级,90 拍) |
|---|---|---|
| 强视觉证据 | 10–12% | LITERAL_STRONG 8 拍 = 8.9% |
| 有效隐喻 | ~5% | REAL_METAPHOR 11 拍 / 66.34s = 12.2%(拍数);另两锁 Analogue 3 拍 |
| GENERIC B-roll | 60–65% | GENERIC_ATMOSPHERE 34 + GENERIC 16 = **50 拍 = 55.6%**;runtime 口径 atmosphere_not_narrative **38 拍 / 213.09s = 41.9%** |
| 明显 MISMATCH | 6–8% | MISMATCH_RISK 14 拍 = **15.6%**(grade 级,高于审片估计) |
| 图片卡片感 | 10–12% | 无直接工程口径(CARD_FEEL 为本次新建诊断维度) |

**注意**:两套口径(审片观感 vs 工程 grade)不可直接互换;工程数据已表明 generic+atmosphere 合计超过一半时长口径下约四成,审片 60–65% 为观感估计(HYPOTHESIS,待 EXP-21.1 离线全量标注核实)。

### 2.4 正向证据(审片点名的高分段,标 ~8/10 / 7.5/10 / 7/10)

1. **医生 + CT/影像工作站**(约 4:08–4:17):真实行业现场 + 明确主体 + 具体动作;
2. **交易所交易大厅**(约 5:01–5:08):真实行业环境 + 人群 + 交易屏幕;
3. **老式电视演播室档案**(约 3:35–3:45):真实年代信息 + 历史档案;
4. **工地工人**(约 5:28–5:35):具体职业 + 具体环境 + 具体人物;
5. **监控摄像头**(约 6:31–6:45):单一明确主体,可作"算力之眼/监控/数据权力"隐喻。

工程侧注:账本中 "Medical professional reviewing MRI scans on computer screen" 出现 **×2**——高分素材同样发生复用,正好成为 Semantic Reuse(同功能 vs 新功能)的研究样本,而非"高分=可无限复用"的证据。审片时间戳与拍号映射为近似(约 5.6s/拍),未逐拍核实。

---

## 3. 因果归因(三标签制)

**规则**:审片数字一律标 `OBSERVED_BY_REVIEWER`;只有工程工件可证实的标 `ENGINEERING_VERIFIED`;推测标 `HYPOTHESIS`。审片估计不得直接当工程事实。

### 3.1 已被历史实验验证的问题(ENGINEERING_VERIFIED)

| 问题 | 证据 |
|---|---|
| reuse 上限已放宽但仍疲劳 | multi_use **29**(19.3/19.4/19.6 冻结统计);adjacent same-byte 0 / consecutive 0 只解决"相邻",不解决"全片疲劳"(审片判断"相邻不重复≠全片不疲劳"与工程定义一致) |
| Generic/氛围占比高 | Stage 20 普查:GENERIC_ATMOSPHERE 34 + GENERIC 16 = 50 拍(55.6%);fallback 34 拍 / 198.9s |
| 池内不可解 | Stage 20.1:34 槽仅 1 个合法池内释放;B1 为素材池能力边界 |
| 相关性≠证据价值 | relevance 0 LOW(17),但 grade GENERIC 类仍 50 拍——"相关"门(冻结 CV2/Gate)通过后无"证据质量"门 |
| Visual Intent 改善"搜什么" | Stage 18 关闭时结论:方向有效,解耦检索与意图 |

### 3.2 审片提出、尚未被工程实验验证的问题(HYPOTHESIS / OBSERVED_BY_REVIEWER)

| 问题 | 标签 | 待验证方式 |
|---|---|---|
| Generic B-roll 60–65% | OBSERVED_BY_REVIEWER(工程普查为 55.6% 拍数 / 41.9% runtime,口径不同) | EXP-21.1 全量离线标注 |
| CARD_FEEL 卡片感 | OBSERVED_BY_REVIEWER + HYPOTHESIS | EXP-21.3 指标构建与相关性 |
| Visual Evidence Minimum Unit 可分性 | HYPOTHESIS | EXP-21.4 正/负样本拟合测试 |
| Semantic Reuse(新功能重复可允许) | HYPOTHESIS(29 个 multi_use 中同功能/新功能比例未知) | EXP-21.2 复用功能审计 |
| Information Gain / 无旁白可解释性 | HYPOTHESIS | EXP-21.1 E4/E5 标注 |

### 3.3 归因结论

当前系统的质量缺口不在"检索相关性"(已冻结达标),而在**检索之后的"证据质量"评价层缺失**:Gate/V1/CV2 回答"相关与可用",没有任何环节回答"看见什么、新增了什么信息"。这是 Stage 21 的设计靶点,且**不动冻结链**。

---

## 4. Visual Evidence Quality 评价框架(设计态,E1–E7)

| 维度 | 问题 | 弱例 | 强例 |
|---|---|---|---|
| **E1 Subject Specificity** | 有明确主体? | person / city / office | worker / doctor / trading floor / robotic arm |
| **E2 Action Specificity** | 主体在做什么具体动作? | doctor standing | doctor examining CT image |
| **E3 Environment Specificity** | 环境提供额外信息? | modern room | hospital imaging room |
| **E4 Evidentiary Value** | 关掉旁白,观众能否从画面推断论述对象? | 抽象焦虑配空镜 | 监控摄像头 → 数据权力 |
| **E5 Information Gain** | 相对前一镜头,是否提供**新**视觉信息? | A→B→A 往返 | 机制→后果的画面递进 |
| **E6 Narrative Function** | 承担 establish / demonstrate / contrast / explain / historical evidence / consequence / mechanism / metaphor / transition 之一,而非 atmosphere / filler | 花坛→"抽象未来" | 老演播室→媒介历史 |
| **E7 Visual Fatigue** | 本片中已出现次数(即使单镜头质量好) | skyline 第 5 次 | 首次出现的行业现场 |

E1–E5 合成候选指标 **EQS(0–1)**;E6 为功能标注;E7 进入 Semantic Reuse 模型。**全部为设计态,不写入任何生产 Gate。**

---

## 5. Semantic Reuse 模型(设计态)

**明确拒绝的简单规则**(§10 边界):`usage_count<=2`、全片禁重复、简单 blacklist、关键词禁止、直接改 CV2 阈值。

核心区分:**研究"无视觉语义增量的重复",不是"所有字节级重复"**。

```text
Same Asset
  ↓
Same Visual Function?(同主体+同动作+同信息+同叙事功能)
  YES → REJECT / FATIGUE(无论间隔多远)
  NO
  ↓
New Narrative Function?
  YES → POSSIBLY ALLOW(需记录功能映射,逐例审计)
  NO  → REJECT
```

正例(可研究允许):机械臂 → 自动化生产(第 1 次)→ 人类劳动替代(第 2 次,功能不同)。
反例(疲劳):花坛 → 抽象未来 / 抽象意义 / 抽象焦虑——只换旁白,视觉信息不变。

工程注意:fallback 借用层已有 5 个源拍被借 2 次(S02-B01/S05-B01/S06-B02/S06-B03/S08-B02),此类"一源两用"是 Semantic Reuse 审计的首要样本。

---

## 6. CARD_FEEL 模型(设计态,只作诊断/软评分)

**定位**:质量诊断与软评分,**不得立即变成硬过滤器**。

候选因素(每窗/每拍可离线计算):
1. 单一静态画面持续过长;
2. 同一素材跨多 beat 重复(跨距越大越疲劳);
3. 连续 Generic B-roll(run 长度);
4. 画面与旁白仅词汇级关联(有 relevance 无 evidence);
5. 画面无具体动作(E2 缺失);
6. 画面无现实世界证据(E4 缺失);
7. 转场后视觉信息无增加(E5=0);
8. A→B→A 往返;
9. 连续"人+屏幕" / 连续城市空镜 / 连续办公室(题材 run)。

输出:CARD_FEEL 指数(0–1,窗级)+ 与审片低分段的重合度检验(EXP-21.3)。

---

## 7. Visual Evidence Minimum Unit(设计态)

```text
WHO/WHAT + WHERE + DOING WHAT + WHY IT MATTERS
```

| 等级 | 例 |
|---|---|
| Weak | 人 + 手机 |
| Better | 工人 + 仓库 + 扫描订单 |
| Strong | 医生 + 医院影像工作站 + 检查 CT 图像 |
| Historical Strong | 历史人物/机构 + 真实历史环境 + 当时正在发生的技术/媒介行为 |

**拟合测试目标**:解释审片中 CT / 交易所 / 工地 / 老演播室(Strong-Historical Strong)为何显著优于手机 / 键盘 / 天际线 / 祈祷者 / 油画(Weak)。若模型能稳定分离两组,则 EQS 有效;若不能,回到框架修正(EXP-21.4)。

---

## 8. Proposed Metrics(全部设计态,不入生产)

| 指标 | 定义 | 层级 |
|---|---|---|
| **EQS** | E1–E5 加权 0–1(权重实验定,不预设) | 拍级 |
| **Evidence Share** | EQS≥阈值的 runtime 占比(与 correspondence 并列,**不混算**) | 片级 |
| **Semantic Reuse Acceptance** | 29 个 multi_use 中"新功能重复"占比 | 片级 |
| **CARD_FEEL Index** | §6 因素合成,窗级 | 窗级 |
| **Information Gain Rate** | E5>0 的转场占比 | 片级 |
| **Narrative Function Coverage** | E6 非 atmosphere 功能的拍占比 | 片级 |

---

## 9. Proposed Experiments(全部需先授权,当前不执行)

| 编号 | 内容 | 性质 | 冻结边界 |
|---|---|---|---|
| **EXP-21.1** | 全 90 拍离线 EQS 标注(E1–E7,基于既有 storyboard + 资产元数据 + 人工/模型看图),产出 Evidence Share 全量普查;同时全量核实审片的重复次数观察 | 离线标注 | 零检索/零 CV2 调用/零渲染;标注为外部新增评价,不改冻结件 |
| **EXP-21.2** | Semantic Reuse 审计:29 个 multi_use 资产逐个分类 same-function / new-function,验证"新功能可允许"假设 | 离线分析 | 只读 ledger + assignments |
| **EXP-21.3** | CARD_FEEL 指标构建 + 与审片 4.5/10 低分段的重合度/相关性检验 | 离线计算 | 只读时间轴与既有审计 |
| **EXP-21.4** | Minimum Unit 拟合测试:5 个高分段 vs 5 个低分段,检验模型分离度 | 离线标注 | — |
| **EXP-21.5**(远期,单独授权) | 质量感知指派的局部 A/B(仿 20.1 模式:小窗、冻结管线、类别不动) | 离线 A/B | 任何执行前需新授权 + 预注册 |

**禁止**(Stage 21 全程):简单规则(次数上限/全禁重复/blacklist/关键词禁)直接入生产;改 CV2/Gate/阈值/权重/Gold/correspondence 定义;新增检索;下载;网络调用;重渲染;改 Production Entry / Final Gate;自动 APPROVED;进入 Production Run 01。

---

## 10. Frozen Boundary Check(本阶段合规声明)

- 14 个冻结模块:**零修改**(本阶段仅新增本文档与 JSON);
- CV2 / Gate / 阈值 / 权重 / Gold / correspondence 定义:**零触碰**;
- Production Entry / Final Quality Gate / Residual Register:**零改动**;
- 检索 / 下载 / CV2 调用 / 渲染:**零执行**;
- Stage 18:**保持关闭**,本阶段仅为质量层诊断,不构成 reboot;
- B1/B2/B3/W08 处置不变;Production Run 01 仍等三项人工签核(PRODUCTION PRE-FLIGHT = BLOCKED)。

---

## 11. Unresolved Questions

1. 审片 60–65% Generic 估计与工程普查(55.6% 拍数 / 41.9% runtime)口径差多少?→ EXP-21.1;
2. 审片点名的重复素材**全片精确次数**(账本仅 55/90 拍直连,33 个 baseline 拍需回溯 12.13 recovery_v2 谱系)→ EXP-21.1;
3. 5 个高分段时间戳的精确拍号映射(当前为近似 5.6s/拍推算)→ EXP-21.1;
4. EQS 权重与阈值是否存在稳定的人工一致性?→ EXP-21.4 后再议;
5. Semantic Reuse 的"新功能"判定由谁执行(人工/模型)、如何防漂移?→ 设计问题,未决;
6. CARD_FEEL 能否在不调用 CV2 的前提下从既有元数据有效计算?→ EXP-21.3;
7. Evidence Share 与 correspondence 是否会出现负相关冲突(高质量但非自身链资产)?→ 设计问题,未决;
8. 质量层最终以何种形态接入生产(前置过滤 / 后置审计 / 指派权重)——**完全未决,需独立授权决策**。

---

## 12. 结论

```
STAGE 21 = DIAGNOSTIC COMPLETE · STOP

Visual Evidence Quality 问题定义建立(E1–E7 + Minimum Unit + Semantic Reuse + CARD_FEEL) ·
审片证据归档并三标签归因(OBSERVED_BY_REVIEWER / ENGINEERING_VERIFIED / HYPOTHESIS) ·
工程交叉核验:reuse 29 / adjacent 0 / generic 50 拍(55.6%)/ atmosphere 213.09s(41.9%)/ 部分账本
  已见 16 个多用途素材(smartphone ×4 拍、skyline ×5 拍、scaffolding ×2、meeting ×3、typing ×3)——
  审片"素材疲劳"方向与工程数据一致,精确次数待 EXP-21.1 ·
Correspondence 60.86% 冻结定义不动,Visual Evidence Quality 为并列新维度 ·
5 项实验仅提出设计,全部等待授权 · 零冻结件修改 · 零检索/下载/CV2/渲染 ·
Stage 18 保持关闭 · Production Run 01 仍受 PRE-FLIGHT BLOCKED 约束
STOP——不进入 21.1,不修改任何生产代码
```
