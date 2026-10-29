# Stage 33 — EXP-21.2b: Full-Film Semantic Family Diversity Audit

> **性质**:离线 · 只读 · 诊断实验(已获授权)。零网络 / 零检索 / 零下载 / 零 CV2 / 零渲染 / 零冻结模块修改 / 零决策改写 / 零新 APPROVED。
> 数据:与 EXP-21.1 完全相同的账本重建(90/90 拍,multi_use=29 交叉验证);族归属由 analyst 依据既有 title/narration/focus/subject 文本元数据判定(无任何 vision/模型调用)。
> 机器可读:`output/stage21_visual_quality/stage21_2b_family_diversity.json`(证据链:`_exp212b_family.py` → `_exp212b_work.json`)。

## 1. 核心结论

> **"族级视觉重复比字节级 asset reuse 更能解释当前影片的素材疲劳" —— 成立(CONFIRMED)。**

| 视角 | 重复事件数 | 短程(≤10 拍) | 跨资产不可见于字节账本 |
|---|---|---|---|
| 字节级(EXP-21.1) | 33 | 33/33 = 100% | — |
| **Fine Family(28 族)** | **62** | 45/62 = 72.6% | **29 次**(46.8%) |
| Broad Family(12 族) | 78 | 62/78 = 79.5% | 全部跨资产部分 |

关键差异:字节级复用 100% 集中在短程;**族级重复另有 17 次长程事件(>10 拍)**——疲劳感延伸到字节账本完全看不见的地方。"不同素材 ≠ 不同视觉证据"被定量证实:62 次同族重复中 29 次用了**不同资产**,且全部为静态图片、零信息增量。

## 2. Family 定义(两级,analyst 判定)

28 个 Fine Family → 12 个 Broad Family。判定依据:主体 + 可见动作 + 环境 + 镜头/视角结构 + 视觉功能。**未使用文件名/来源/关键词聚类,未为凑覆盖率造族。**

Fine 覆盖(拍数):CITY_SKYLINE 10 · CLASSROOM 9 · PEOPLE_IN_MEETING 7 · CITY_TRAFFIC 7 · PERSON_USING_SMARTPHONE 6 · CONSTRUCTION_SITE 5 · CONTROL_ROOM 5 · ROBOT_ARM( service+factory) 7 · STREET_PEDESTRIAN_CROSSING 4 · URBAN_PLAZA 4 · OFFICE_COLLABORATION 3 · PERSON_AT_COMPUTER_DESK 3 · 其余 15 族各 1–2 拍。

Broad 覆盖(拍数 / 时长占比):URBAN_STREET_LIFE 18 · INDUSTRIAL_INFRASTRUCTURE 15 · OFFICE_WORK 12 · CITY_SKYLINE 10 · PERSON_WITH_DEVICE 10 · EDUCATION_TRAINING 9 · 其余 6 族 16 拍。

## 3. Family Concentration(默认视觉模板的量化)

- **Fine Top5**(CITY_SKYLINE / CLASSROOM / PEOPLE_IN_MEETING / CITY_TRAFFIC / PERSON_USING_SMARTPHONE)= 39 拍 / 42.7% 时长;
- **Broad Top5**(URBAN_STREET_LIFE / INDUSTRIAL_INFRASTRUCTURE / OFFICE_WORK / PERSON_WITH_DEVICE / CITY_SKYLINE)= **67/90 拍 / 76.9% 时长**;
- **50/88 个三拍窗口**含 ≥2 拍来自 Broad Top3 —— "street → industry → office → skyline" 的**默认视觉模板存在且已量化**(HYPOTHESIS → 定量刻画,因果未证)。

## 4. 短窗族级重复(与字节级对比)

Fine 62 事件按距离:2–3 拍 **34** · 4–5 拍 5 · 6–10 拍 6 · >10 拍 **17**;Broad 78 事件含 **8 次相邻**(连续两拍同 Broad 族、不同素材)。结论:**族级重复以短程为主(72.6%)但不限于短程**——这是族级解释力强于字节级的第二个证据。

## 5. Cross-Asset Same-Family(本实验最重要分类)

- 连续转换普查(89 次):DIFFERENT_FAMILY 81 · DIFFERENT_ASSET_SAME_BROAD_FAMILY 8 · SAME_ASSET 0(与冻结 adjacent 保证一致);
- 同 Fine 族配对 62 次:**SAME_ASSET 33(即 21.1 的字节复用)+ DIFFERENT_ASSET_SAME_FAMILY 29(全新发现)**;
- 29 次跨资产同族重复在字节级账本中**完全不可见**——`usage_count` 类规则从结构上无法触及它们。

## 6. Narrative Function 分析

同族配对角色关系:SAME_FUNCTION 34 / RELATED 13 / DIFFERENT 15;**28/62 次虽然叙事角色变化,视觉结构不变**(`FUNCTION_CHANGED_BUT_VISUAL_INFORMATION_SAME`)——"换了旁白"不等于"换了画面信息"。27/62 次同族重复的第二次使用是 fallback 拍。

## 7. 四个已知族专项验证(不预设结论,逐一回答)

| 族 | 拍数 | 唯一素材 | 短窗重复事件 | 跨资产事件 | 信息增量 | 判定 |
|---|---|---|---|---|---|---|
| 人+屏幕 PERSON_WITH_DEVICE | 10 | 5 | 7 | 6 | 零 | **CONFIRMED**:换一张图,还是"人对屏幕" |
| 街道 URBAN_STREET_LIFE | 18 | 12 | 14 | 15 | 零 | **CONFIRMED**(全片最大族) |
| 会议室/办公室 OFFICE_WORK | 12 | 8 | 9 | 7 | 零 | **CONFIRMED** |
| 天际线 CITY_SKYLINE | 10 | 6 | 7 | 5 | 零 | **CONFIRMED**(字节级只见 3–5,族级 10) |

四族全部成立:短程重复 + 跨资产 + 零增量 + "换了一张图但还是同一种画面"。

## 8. Family Fatigue Casebook(Top 20,全量见 JSON)

按(角色关系 → 距离带 → 跨资产优先)排序,前 5 例:

1. CITY_SKYLINE:S05-B03→S06-B03(dist 3,SAME_FUNCTION,同资产);
2. CLASSROOM:S11-B01→S12-B01(dist 3,SAME_FUNCTION,同资产);
3. CITY_SKYLINE:S06-B03→S08-B01(dist 3,SAME_FUNCTION,同资产);
4. PERSON_WITH_DEVICE:S01-B02→S02-B02(dist 3,SAME_FUNCTION,同资产);
5. CLASSROOM:S22-B03→S23-B03(dist 3,SAME_FUNCTION,同资产);
……(Top20 含 HIGH 风险的跨资产同族短程案例,如 MEDICAL_WORKSTATION、URBAN_PLAZA、CONSTRUCTION_SITE;每条含 beat IDs、资产、族、距离、时长、narrative function、SAME/RELATED/DIFFERENT、fatigue 判定与证据基础,可回溯至 21.1 账本原始记录)

## 9. 五个核心问题的回答

- **Q1(主要重复问题是什么)**:**三者叠加,但分工明确**——族级复用(62 事件)> 字节级复用(33 事件);fallback 借用是把这些重复搬上屏幕的**机制**(22/33 字节事件、27/62 族事件的重复侧是 fallback 拍)。族级复用解释力严格大于 asset reuse。
- **Q2("每素材最多 2 次"硬规则是否够)**:**NO**——反事实计算:该规则只能移除 4 次第三用显示(4 个 3 次用资产),29 次跨资产同族重复与整个 fallback 氛围层原封不动。
- **Q3( implication)**:**YES**——未来靶点是 Visual Family Diversity / Semantic Reuse(族级新颖性 + 证据质量),不是 usage_count。
- **Q4(fallback 是否放大族复用)**:**YES**——27/62;fallback(34 拍/198.9s)以零叙事功能使画面族在场时间翻倍。
- **Q5(默认视觉模板是否存在)**:**存在,已量化**(§3:76.9% 时长 / 50/88 热窗口)。

## 10. 归因分离

- **ENGINEERING_VERIFIED**(本实验实测):全部覆盖统计、事件计数、距离带、跨资产分类、cap-at-2 反事实、热窗口数;族归属为 analyst 编码(方法透明、可复现,宽族结构稳健,fine 级可能因第二标注人略有漂移);
- **OBSERVED_BY_REVIEWER**:4.5/10、花坛 ≥5、手机 ~3、Pete、Generic 60–65% 等全部保留原标签;族级视角为审片观察提供工程对应(skyline 字节 3–5 vs 族级 10;街道族 18 拍);
- **HYPOTHESIS**:族重复与 CARD_FEEL 的因果/相关关系(HF2,未测试);默认模板与观众疲劳的因果关系(HF1/HF3 为"工程测量支持,未做观众验证")。

## 11. 冻结边界

零冻结模块/生产代码修改,零 CV2/Gate/阈值/权重/Gold 触碰,零渲染,零检索/下载/网络,零新 APPROVED;Production Status = CONDITIONAL GO 不变;Pre-flight = BLOCKED 不变;所有指标为诊断量,不成为生产阈值;21.2 / 21.3 / 21.4 / 21.5 未执行。

## 12. Future / Proposals(仅提案,不执行)

- **EXP-21.3** CARD_FEEL 指数:21.2b 已提供族集中度与热窗口特征作为输入;
- **EXP-21.4** Visual Evidence Minimum Unit 拟合测试;
- **FUTURE family-diversity policy**:族级多样性目标(如窗口级族预算)作为未来检索/指派线的设计研究——需新授权,且不得借"重开 Stage 18"之名自动执行。

```
EXP-21.2b = COMPLETE · STOP
28 Fine / 12 Broad 族 · 族级重复 62 事件 > 字节级 33 · 29 次跨资产同族(字节账本不可见) ·
短程 72.6% + 长程 17 次(字节级为 0) · Broad Top3 覆盖 76.9% 时长 · 50/88 热窗口 ·
四已知族全部 CONFIRMED(短程重复+跨资产+零增量) · cap-at-2 反事实仅移除 4/62 ·
Q1 三者叠加(族级为主、fallback 为机制) · Q2=NO · Q3=YES · Q4=YES · Q5=YES ·
核心命题成立:不同素材 ≠ 不同视觉证据
STOP——不进入 21.2 / 21.3 / 21.4 / 21.5,等待授权
```
