# Stage 19:Sequence-level Visual Quality / Narrative Progression 设计与离线诊断

> 阶段性质:仅设计与只读诊断。零生产代码改动、零渲染、零新检索、零 Intent/Reuse Policy 变更(复核:`src/` mtime 早于本阶段启动;所有产物在 `docs/` 与 `output/stage33/stage19_experiment/`)。

## 1. 研究问题

单拍素材即使 HIGH 且对应 narration,连续播放时是否形成**视觉证据推进**(evidence progression),还是同义 B-roll 堆叠(sequence redundancy)?核心区分:**素材本身质量**(single-asset quality:CV2 fit / correspondence grade)≠ **素材在序列中的功能质量**(functional quality:在相邻组合中承担推进、对仗、节奏的功能)。

## 2. 数据源(全部现有落盘,只读)

| 数据 | 来源 | 覆盖 |
|---|---|---|
| 播放序、时长、对应类、grade、relevance、narration、abstract 标记 | `stage17_audit.json.rows` | 90/90 |
| 实际展示素材标题(含 fallback 溯源) | `run_14_final.build_ledger` + `stage161_assignments.fallbacks_v3` | 90/90 |
| visual_subject / visual_intent(旧链) | `chain_recovery.json` | 90/90 |
| CV2 fit(素材本身质量) | `verdict_store_1226.cv2`(本拍在用素材) | 有判定即用 |
| evidence_type | Top-10 用 Stage 18 冻结类型;其余按 18 设计文件的分型规则**确定性推导**(仅审计用,不进生产) | 90/90 |

## 3. 指标体系(窗口 = 连续 3 拍,步长 1,共 88 窗)

**A. Sequence Redundancy(RED,0–1,越高越差)**
- A1 素材重复:窗内同标题出现 >1 次(0/1);
- A2 主体冗余:1 − 主体聚类数/3(主体"相同" = visual_subject token Jaccard ≥ 0.34,或 subject∪title Jaccard ≥ 0.45;贪婪聚类);
- A3 氛围堆叠:GENERIC_ATMOSPHERE 拍占比;
- `RED = 0.4·A2 + 0.3·A3 + 0.3·A1`

**B. Evidence Progression(PROG,0–1,越高越好)**
- B1 证据类型多样性:窗内 distinct evidence_type / 3;
- B2 新主体推进率:窗内与前文主体均不同的拍数占比(首拍不计);
- B3 节奏对仗:窗内同时存在具体证据(REAL_EVENT/INDUSTRY_SITE)与非具体证据 → 1.0,否则 0.4;
- `PROG = 0.5·B2 + 0.3·B1 + 0.2·B3`

**C. Narrative-Visual Alignment(ALI,0–1,越高越好)**
- 对窗内每对相邻拍:ΔN = 1 − narration token Jaccard(命题新鲜度);ΔV = 主体相同(0)/不同(1)(视觉新鲜度);sync = 1 − |ΔN − ΔV|;
- `ALI = mean(sync)` —— 命题推进时视觉必须推进;命题延续时视觉允许延续。

**D. Visual Transition / Continuity(CONT,0–1,越高越好)**
- 相邻对罚分:同素材复现 1.0;同主体跨 fallback 边界 0.9;同主体近重复 B-roll 0.7;fallback↔真实且主体无关 0.6(fallback↔真实但弱相关 0.3);双 ATMOSPHERE 相邻 0.5;无关真实转场 0;
- `CONT = 1 − mean(罚分)`

**E. 综合 Sequence Quality(SQS,0–100)**
`SQS = 100·(0.30·PROG + 0.25·(1−RED) + 0.25·ALI + 0.20·CONT)`(权重为设计常数,可校准;全部记录于 diagnostic.meta)。

**单拍质量代理 SBQ(对照用)**:本拍在用素材的冻结 CV2 fit;无判定则 relevance 映射(HIGH .85/MEDIUM .60/LOW .30);再无则 grade 映射。`sbq_basis` 记录来源。

## 4. 离线测量结果(88 窗)

**总体**:SQS mean 84.9,min 53.7,max 100;P25=80.7,P75=91.5。**序列问题真实存在但局域化**:
- 氛围堆叠窗(≥2 拍 GENERIC_ATMOSPHERE):**31/88(35%)**;
- 含硬断点对(罚分 ≥0.6):**54/88(61%)**——主体相同跨 fallback 边界、无关 fallback 跳切为主因;
- 最差集中区:S02–S04(叙事开篇)、S20–S22、S27–S28。

**Top 10 最差窗口**(`stage19_diagnostic.json.worst10`):W07[S03-B02..S04-B01]=53.7、W06=55.0、W50[S21-B01..S22-B01]=55.9、W49=62.2、W67[S27-B03..S28-B02]=68.9、W40、W04、W05、W17、W23。典型病理:
- **W07**:fallback 办公室 → 办公室 REAL_EVENT(主体簇"现代办公室/知识工作者"重复,罚 0.9)→ 无关人群 fallback(罚 0.6)——开篇连续三拍表达同一概念;
- **W50**:S21-B01(HIGH relevance)办公室协作机器人 → S21-B02 fallback(MRI 阅片,溯源语义错位)同主体跨边界(罚 0.9)→ 街道行人跳切(0.6);
- **W67**:S28-B02 的 fallback 溯源素材 = **S29-B02 的在用素材(Abi Hanifa 平板课堂)**——fallback 机制自身制造跨拍语义撞车。

**Top 10 最好窗口**:`best10`,W20[S08-B02..S09-B01]=100、W55/W56[S23..S24]=100、W74=99.3 等。共性:主体逐拍推进、具体↔隐喻节奏交替、fallback 零介入。

**"单拍 HIGH,序列差"案例(8 例,≥5 达标)**:S21-B01(rel HIGH,win 71.7,陷于 W50)、S26-B01、S20-B03(LITERAL_STRONG,win 83.2)、S31-B03、S27-B01、S26-B03、S13-B01、S23-B01(win 89.6)——单拍合格但被邻拍同主体/同氛围稀释。

**"单拍一般,序列功能好"案例(8 例,≥5 达标)**:S30-B01(sbq 0.5,win 95.3,承担"预测"命题的证据锚点)、S13-B03、S35-B01、S08-B02(0.4→90.8,为 S08-B03 控制室做铺垫)、S29-B02、S33-B02、S16-B01、S01-B01(开场氛围功能)。

## 5. 五问回答

1. **序列级问题是否真实存在?** 真实但局域化:61% 窗口含硬断点对、35% 存在氛围堆叠;病灶集中在 3 个区段(S02–S04 / S20–S22 / S27–S28),全片均值尚可(84.9),**不构成全片重排理由**;
2. **现有落盘数据能否可靠测量?** 能。RED/PROG/CONT 完全由客观字段计算;ALI 依赖主体/命题 token 相似度(阈值 0.34/0.45 为设计常数,已记录可校准);非 Top-10 的 evidence_type 为启发式推导(仅审计用)。测量可复现、可审计;
3. **是否值得进入 19.1?** 值得,但范围极窄:仅 3 个最差窗口;
4. **最小可控实验(19.1 建议)**:仅 W07/W50/W67 —— 在**现有已持有素材**(存储池判定 + fallback 溯源池)内做窗口内重指派(不检索、不改 Gate/V1/CV2/Intent/Reuse;只用已带冻结判定的替代素材,质量只升不降),随后**仅渲染这 3 个窗口的局部测试版**,验收:目标窗 SQS +≥10、其余窗口不降、相邻同素材 0、multi_use 不增、correspondence 不变;其中 S28-B02 的 fallback 溯源撞车(S28-B02 溯源到 S29-B02 在用素材)是一处可零成本修复的具体缺陷;
5. **若不可测或收益不足?** 不适用——可测且收益局域明确;但明确**不做全片 resequencing**(均值 84.9 已高,收益/风险比不成立)。

## 6. 产物

- 本设计文档;`stage19_experiment/stage19_diagnostic.json`(meta/weights/thresholds + 90 拍表 + 88 窗全量 + worst/best10 + 16 个案例);
- 零生产文件改动;零渲染。

```
STAGE19 = PASS · STOP
序列级问题真实且可测(61% 窗含硬断点对,35% 氛围堆叠,病灶集中于 S02–S04 / S20–S22 / S27–S28) · worst10/best10 已定位 · HIGH-但-序列差 8 例 / 一般-但-功能好 8 例 · 19.1 最小实验建议:仅 3 窗现有素材重指派 + 局部测试渲染(需授权) · 不做全片重排
STOP——等待下一步授权
```
